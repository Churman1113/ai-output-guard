"""Response transformation for LLM API proxy.

Handles modification of LLM API responses based on Guard results:
- PASS: original response, no modification
- FIX: replace output with fixed version, add X-AgentGuard-Fix header
- WARN: original response, add X-AgentGuard-Warning header
- DENY: replace output with safety message, add X-AgentGuard-Blocked header
- ASK_HUMAN: return 202 with confirmation details
"""

from __future__ import annotations

import json
import time
from typing import Any

from agentguard.result import GuardLevel, GuardResult
from agentguard.proxy.router import extract_content, set_content, LLMAPIRoute


# Header names for proxy metadata
HEADER_PREFIX = "X-AgentGuard"
HEADER_BLOCKED = f"{HEADER_PREFIX}-Blocked"
HEADER_FIX = f"{HEADER_PREFIX}-Fix"
HEADER_WARNING = f"{HEADER_PREFIX}-Warning"
HEADER_AUDIT_ID = f"{HEADER_PREFIX}-Audit-ID"
HEADER_LATENCY = f"{HEADER_PREFIX}-Latency-Ms"
HEADER_LEVEL = f"{HEADER_PREFIX}-Level"


# Safe fallback message when LLM output is blocked
BLOCKED_OUTPUT_MESSAGE = json.dumps({
    "role": "assistant",
    "content": (
        "[This response was blocked by AI Output Guard safety policy. "
        "The AI-generated content was flagged as potentially unsafe. "
        "Please review your request and try again.]"
    ),
})


# Safe fallback when LLM output is modified
def _build_safety_notice(result: GuardResult) -> str:
    """Build a safety notice for modified/blocked responses."""
    checks = []
    for c in result.checks:
        checks.append(f"  - [{c.level.value.upper()}] {c.layer}: {c.message}")

    return (
        "[AI Output Guard Safety Notice]\n"
        f"The following response was {'blocked' if result.blocked else 'modified'} "
        f"by AI Output Guard ({result.blocked_by or 'unknown'} layer).\n"
        f"Audit ID: {result.audit_id or 'N/A'}\n"
        "Details:\n"
        + "\n".join(checks)
    )


def transform_response(
    original_body: dict[str, Any] | str,
    route: LLMAPIRoute,
    guard_result: GuardResult,
) -> tuple[dict[str, Any] | str, dict[str, str], int]:
    """Transform an LLM API response based on Guard result.

    Args:
        original_body: The original LLM API response body (parsed dict or raw string).
        route: The matched LLM API route (for content path extraction).
        guard_result: The result from Guard validation.

    Returns:
        Tuple of (modified_body, response_headers, http_status_code).
    """
    headers: dict[str, str] = {
        HEADER_AUDIT_ID: guard_result.audit_id or "",
        HEADER_LATENCY: str(guard_result.metadata.get("latency_ms", round(time.time() * 1000))),
        HEADER_LEVEL: guard_result.level.value,
    }

    latency = guard_result.metadata.get("latency_ms", 0)
    if isinstance(latency, float):
        headers[HEADER_LATENCY] = f"{latency:.1f}"

    # Parse body if it's a string
    body: dict[str, Any] | None = None
    body_is_str = False
    if isinstance(original_body, str):
        body_is_str = True
        try:
            body = json.loads(original_body)
        except json.JSONDecodeError:
            body = None
    elif isinstance(original_body, dict):
        body = original_body

    # Extract original LLM output for reference
    original_content = None
    if body and not body_is_str:
        original_content = extract_content(body, route.content_path)

    level = guard_result.level

    # ── PASS: no modification ──
    if level == GuardLevel.PASS:
        return original_body, headers, 200

    # ── FIX: replace content with fixed version ──
    if level == GuardLevel.FIX:
        headers[HEADER_FIX] = "true"
        if body and not body_is_str and guard_result.output is not None:
            fixed_str = str(guard_result.output)
            body = set_content(body, route.content_path, fixed_str)
            return body, headers, 200
        return original_body, headers, 200

    # ── WARN: pass through with warning header ──
    if level == GuardLevel.WARN:
        blocked_by = guard_result.blocked_by or "unknown"
        top_check = guard_result.checks[-1] if guard_result.checks else None
        warning_msg = top_check.message if top_check is not None else "Content warning"
        headers[HEADER_WARNING] = warning_msg
        headers[HEADER_BLOCKED] = blocked_by
        return original_body, headers, 200

    # ── ASK_HUMAN: return 202 with details ──
    if level == GuardLevel.ASK_HUMAN:
        top_check = guard_result.checks[-1] if guard_result.checks else None
        approval_body = {
            "status": "requires_approval",
            "message": top_check.message if top_check is not None else "This action requires human approval",
            "audit_id": guard_result.audit_id,
            "original": str(original_content or original_body),
            "agentguard": {
                "level": "ask_human",
                "blocked_by": guard_result.blocked_by,
                "checks": [
                    {"layer": c.layer, "level": c.level.value, "message": c.message}
                    for c in guard_result.checks
                ],
            },
        }
        return approval_body, headers, 202

    # ── DENY: replace content with safety message ──
    if level == GuardLevel.DENY:
        headers[HEADER_BLOCKED] = guard_result.blocked_by or "unknown"

        safe_message = _build_safety_notice(guard_result)

        if body and not body_is_str:
            body = set_content(body, route.content_path, safe_message)
            return body, headers, 200
        else:
            # Raw text response — wrap it
            wrapped = {
                "id": "agentguard-blocked",
                "object": "chat.completion",
                "created": int(time.time()),
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": safe_message,
                    },
                }],
            }
            return wrapped, headers, 200

    # Fallback: pass through unchanged
    return original_body, headers, 200
