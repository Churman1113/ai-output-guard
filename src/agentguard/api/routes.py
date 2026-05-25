"""API route handlers for the AI Output Guard HTTP API.

Each endpoint uses the shared Guard instance stored in app.state.guard,
ensuring audit logs and state persist across requests.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, HTTPException

from agentguard.api.models import (
    ValidateRequest,
    ValidateResponse,
    PolicyUpdateRequest,
    AddIntentRequest,
    AuditResponse,
    AuditEntry,
    StatusResponse,
    CheckDetail,
)

router = APIRouter()


def _get_guard(request: Request):
    """Retrieve the shared Guard instance from app state."""
    guard = request.app.state.guard
    if guard is None:
        raise HTTPException(status_code=500, detail="Guard not initialized")
    return guard


# ── POST /validate ────────────────────────────────────────

@router.post(
    "/validate",
    response_model=ValidateResponse,
    summary="Validate AI-generated output",
    description="Run the full guard pipeline (schema → semantic → policy) on a piece of AI-generated output.",
)
async def validate(request: Request, body: ValidateRequest):
    guard = _get_guard(request)
    result = guard.validate(body.output)

    response = ValidateResponse(
        passed=result.passed,
        blocked=result.blocked,
        level=result.level.value,
        blocked_by=result.blocked_by,
        checks=[
            CheckDetail(
                layer=c.layer,
                level=c.level.value,
                message=c.message,
                confidence=c.confidence,
            )
            for c in result.checks
        ],
        latency_ms=result.metadata.get("latency_ms", 0),
    )

    if body.context:
        response.context = body.context

    if result.was_fixed:
        response.fixed_output = str(result.output)

    return response


# ── POST /policy ──────────────────────────────────────────

@router.post(
    "/policy",
    response_model=dict,
    summary="Update guard policy",
    description="Dynamically reload the guard policy from YAML content.",
)
async def update_policy(request: Request, body: PolicyUpdateRequest):
    try:
        from agentguard.policy_guard import PolicyGuard
        guard = PolicyGuard.from_yaml(body.policy)
        rules_count = len(guard.policy.rules) if guard.policy else 0
        return {
            "status": "ok",
            "rules_loaded": rules_count,
            "message": f"Policy updated: {rules_count} rules active",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── GET /audit ────────────────────────────────────────────

@router.get(
    "/audit",
    response_model=AuditResponse,
    summary="Query audit log",
    description="Retrieve recent guard validation events from the audit log.",
)
async def get_audit(
    request: Request,
    limit: int = 20,
    level: Optional[str] = None,
):
    guard = _get_guard(request)
    entries = guard.audit_log.recent(min(limit, 100))

    filtered = []
    for entry in entries:
        if level is not None and entry.result_level != level:
            continue
        filtered.append(AuditEntry(
            timestamp=entry.timestamp,
            result=entry.result_level,
            blocked_by=entry.blocked_by,
            input_preview=entry.input_preview,
            output_preview=entry.output_preview,
            checks=entry.checks_summary,
        ))

    return AuditResponse(
        total=guard.audit_log.count,
        shown=len(filtered),
        entries=filtered,
    )


# ── POST /intents ─────────────────────────────────────────

@router.post(
    "/intents",
    response_model=dict,
    summary="Add custom dangerous intent",
    description="Register a new dangerous intent pattern in the semantic guard.",
)
async def add_intent(request: Request, body: AddIntentRequest):
    try:
        from agentguard.semantic.intent_registry import IntentRegistry, Intent, IntentCategory
        registry = IntentRegistry()
        intent = Intent(
            name=body.name,
            category=IntentCategory(body.category),
            description=body.description or f"Custom intent: {body.name}",
            severity=body.severity,
            keywords=body.patterns,
        )
        registry.register(intent)
        return {
            "status": "ok",
            "message": f"Intent '{body.name}' added with {len(body.patterns)} patterns",
            "intent": {
                "name": body.name,
                "category": body.category,
                "severity": body.severity,
                "patterns": body.patterns,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── GET /status ───────────────────────────────────────────

@router.get(
    "/status",
    response_model=StatusResponse,
    summary="Guard engine status",
    description="Report current guard configuration, active layers, and audit stats.",
)
async def get_status(request: Request):
    guard = _get_guard(request)

    status = StatusResponse(
        server="agentguard-api",
        version="0.1.0",
        layers={
            "schema": guard._schema_guard is not None,
            "semantic": guard._semantic_guard is not None,
            "policy": guard._policy_guard is not None,
        },
        config={
            "auto_fix": guard._config.auto_fix,
            "fail_open": guard._config.fail_open,
            "on_fail": guard._config.on_fail,
            "semantic_mode": guard._config.semantic_mode,
        },
        audit_entries=guard.audit_log.count,
    )

    if guard._policy_guard and guard._policy_guard.policy:
        status.policy = {
            "rules": len(guard._policy_guard.policy.rules),
            "version": guard._policy_guard.policy.version,
            "defaults": guard._policy_guard.policy.defaults,
        }

    policy_path = request.app.state.policy_path
    if policy_path:
        status.policy_path = policy_path

    return status


# ── Health check ──────────────────────────────────────────

@router.get(
    "/health",
    response_model=dict,
    summary="Health check",
    description="Simple health check endpoint.",
)
async def health():
    return {"status": "ok", "server": "agentguard-api", "version": "0.1.0"}
