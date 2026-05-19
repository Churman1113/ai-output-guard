"""MCP Tool definitions for AgentGuard.

Each tool is registered with a name, description, JSON Schema for inputs,
and a handler function.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from agentguard import Guard

VERSION = "0.2.0"


# ── Helper ────────────────────────────────────────────────

def _make_guard(policy_path: str | None = None):
    """Create a Guard instance with given policy."""
    return Guard(
        semantic=True,
        policy=policy_path,
    )


# ── Tool Handlers ─────────────────────────────────────────

def tool_guard_validate(args: dict, policy_path: str | None = None, shared_guard=None) -> dict:
    """Validate a piece of AI-generated output through the guard pipeline."""
    output = args.get("output", "")
    context = args.get("context", {})

    guard = shared_guard if shared_guard is not None else _make_guard(policy_path)
    result = guard.validate(output)

    response = {
        "passed": result.passed,
        "blocked": result.blocked,
        "level": result.level.value,
        "blocked_by": result.blocked_by,
        "checks": [
            {
                "layer": c.layer,
                "level": c.level.value,
                "message": c.message,
                "confidence": c.confidence,
            }
            for c in result.checks
        ],
        "latency_ms": result.metadata.get("latency_ms", 0),
    }

    # Include fixed output if available
    if result.was_fixed:
        response["fixed_output"] = str(result.output)

    if context:
        response["context"] = context

    return response


def tool_guard_set_policy(args: dict, policy_path: str | None = None, shared_guard=None) -> dict:
    """Dynamically update the guard policy from YAML content."""
    policy_yaml = args.get("policy", "")

    try:
        from agentguard.policy_guard import PolicyGuard
        guard = PolicyGuard.from_yaml(policy_yaml)
        rules_count = len(guard.policy.rules) if guard.policy else 0
        return {
            "status": "ok",
            "rules_loaded": rules_count,
            "message": f"Policy updated: {rules_count} rules active",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


def tool_guard_get_audit(args: dict, policy_path: str | None = None, shared_guard=None) -> dict:
    """Query the audit log for recent guard events with time-range and pagination."""
    limit = int(args.get("limit", 20))
    level_filter = args.get("level")
    from_time = args.get("from_time")  # ISO 8601 timestamp or unix float
    to_time = args.get("to_time")
    offset = int(args.get("offset", 0))

    guard = shared_guard if shared_guard is not None else _make_guard(policy_path)

    # Resolve time filters
    from_ts = None
    to_ts = None
    if from_time is not None:
        from_ts = _parse_timestamp(from_time)
    if to_time is not None:
        to_ts = _parse_timestamp(to_time)

    # Get all entries (reverse chronological for offset support)
    all_entries = list(reversed(guard.audit_log.entries))

    # Apply filters
    filtered = []
    for entry in all_entries:
        # Time range filter
        if from_ts is not None and entry.timestamp < from_ts:
            continue
        if to_ts is not None and entry.timestamp > to_ts:
            continue
        # Level filter
        if level_filter is not None and entry.result_level != level_filter:
            continue
        filtered.append(_format_audit_entry(entry))

    # Pagination
    total_filtered = len(filtered)
    page = filtered[offset:offset + min(limit, 100)]

    return {
        "total": guard.audit_log.count,
        "matched": total_filtered,
        "shown": len(page),
        "offset": offset,
        "limit": min(limit, 100),
        "entries": page,
    }


def tool_guard_fix(args: dict, policy_path: str | None = None, shared_guard=None) -> dict:
    """Analyze and fix AI output that fails schema validation. Code Action support.

    Three modes:
      - "auto": Apply fixes transparently (returns fixed output)
      - "suggest": Only suggest fixes without modifying output
      - "strict": Strip unknown fields, apply all fixes

    Also supports semantic/policy fix explanations when the output was blocked
    by those layers.
    """
    output = args.get("output", "")
    expected_schema = args.get("expected_schema")
    fix_mode = args.get("fix_mode", "auto")

    if fix_mode not in ("auto", "suggest", "strict"):
        fix_mode = "auto"

    strict_mode = fix_mode == "strict"

    response: dict[str, Any] = {
        "fix_mode": fix_mode,
        "fixes_applied": False,
        "fix_log": [],
        "output": output,
    }

    # ── Schema-level fixes ──
    if expected_schema and isinstance(expected_schema, dict):
        try:
            from agentguard.fix.schema_fixer import fix_schema_output
            fixed_output, fix_log = fix_schema_output(output, expected_schema, strict_mode=strict_mode)
            response["fix_log"].extend(fix_log)
            if fix_log:
                response["fixes_applied"] = True
            if fix_mode != "suggest":
                response["output"] = json.dumps(fixed_output, ensure_ascii=False) if isinstance(fixed_output, dict) else str(fixed_output)
        except Exception as e:
            response["fix_log"].append({
                "field": "__root__",
                "error": f"Schema fix error: {e}",
                "fixed": False,
                "confidence": 0.0,
            })

    # ── Semantic/policy-level explanation ──
    # If no schema is provided, run a validation to get fix hints
    if not expected_schema:
        guard = shared_guard if shared_guard is not None else _make_guard(policy_path)
        result = guard.validate(output)
        for check in result.checks:
            if check.level.value in ("fix", "warn", "deny"):
                response["fix_log"].append({
                    "layer": check.layer,
                    "level": check.level.value,
                    "message": check.message,
                    "fixed": check.fix is not None,
                    "fix": str(check.fix) if check.fix is not None else None,
                    "confidence": check.confidence,
                })
                if check.fix is not None and fix_mode != "suggest":
                    response["output"] = str(check.fix)
                    response["fixes_applied"] = True

    return response


def tool_guard_reload_policy(args: dict, policy_path: str | None = None, shared_guard=None) -> dict:
    """Hot-reload policy from a file path without restarting the MCP server.

    Returns the new policy summary after reload.
    """
    new_path = args.get("policy_path", policy_path)

    if not new_path:
        return {
            "status": "error",
            "message": "No policy path provided. Specify policy_path or set AGENTGUARD_POLICY env var.",
        }

    policy_file = Path(new_path)
    if not policy_file.exists():
        return {
            "status": "error",
            "message": f"Policy file not found: {new_path}",
        }

    try:
        from agentguard.policy_guard import PolicyGuard
        pg = PolicyGuard.from_file(str(policy_file))
        rules_count = len(pg.policy.rules) if pg.policy else 0

        summary = {
            "status": "ok",
            "message": f"Policy reloaded from {new_path}",
            "policy_path": new_path,
            "rules": rules_count,
            "version": pg.policy.version if pg.policy else "unknown",
        }

        if pg.policy and pg.policy.defaults:
            summary["defaults"] = pg.policy.defaults

        return summary
    except Exception as e:
        return {"status": "error", "message": str(e)}


def tool_guard_list_policies(args: dict, policy_path: str | None = None, shared_guard=None) -> dict:
    """Scan a directory for available policy YAML files.

    Defaults to scanning the directory of the current policy_path,
    or the current working directory if none is set.
    """
    directory = args.get("directory")

    if not directory:
        if policy_path:
            directory = str(Path(policy_path).parent)
        else:
            directory = os.getcwd()

    scan_dir = Path(directory)
    if not scan_dir.exists() or not scan_dir.is_dir():
        return {
            "status": "error",
            "message": f"Directory not found: {directory}",
        }

    policies = []
    for ext in ("*.yaml", "*.yml"):
        for p in sorted(scan_dir.glob(ext)):
            try:
                content = p.read_text(encoding="utf-8")
                # Quick parse to extract version/name without full loading
                from agentguard.policy_guard import PolicyGuard
                pg = PolicyGuard.from_file(str(p))
                rules_count = len(pg.policy.rules) if pg.policy else 0
                policies.append({
                    "path": str(p),
                    "name": p.stem,
                    "size_bytes": p.stat().st_size,
                    "rules": rules_count,
                    "version": pg.policy.version if pg.policy else "unknown",
                })
            except Exception:
                # Include unparseable files with error flag
                policies.append({
                    "path": str(p),
                    "name": p.stem,
                    "size_bytes": p.stat().st_size,
                    "error": "Failed to parse policy",
                })

    active = policy_path if policy_path else "none"

    return {
        "status": "ok",
        "directory": str(scan_dir),
        "active_policy": active,
        "count": len(policies),
        "policies": policies,
    }


def tool_guard_status(args: dict, policy_path: str | None = None, shared_guard=None) -> dict:
    """Report current guard configuration and status."""
    guard = shared_guard if shared_guard is not None else _make_guard(policy_path)

    status = {
        "server": "agentguard-mcp",
        "version": VERSION,
        "layers": {
            "schema": guard._schema_guard is not None,
            "semantic": guard._semantic_guard is not None,
            "policy": guard._policy_guard is not None,
        },
        "config": {
            "auto_fix": guard._config.auto_fix,
            "fail_open": guard._config.fail_open,
            "on_fail": guard._config.on_fail,
            "semantic_mode": guard._config.semantic_mode,
        },
    }

    if guard._policy_guard and guard._policy_guard.policy:
        status["policy"] = {
            "rules": len(guard._policy_guard.policy.rules),
            "version": guard._policy_guard.policy.version,
            "defaults": guard._policy_guard.policy.defaults,
        }

    if policy_path:
        status["policy_path"] = policy_path

    status["audit_entries"] = guard.audit_log.count

    return status


def tool_guard_add_intent(args: dict, policy_path: str | None = None, shared_guard=None) -> dict:
    """Add a custom dangerous intent to the semantic guard."""
    name = args.get("name", "")
    patterns = args.get("patterns", [])
    description = args.get("description", "")
    severity = args.get("severity", "medium")
    category = args.get("category", "compliance_risk")

    if not name:
        return {"status": "error", "message": "name is required"}

    try:
        from agentguard.semantic.intent_registry import IntentRegistry, Intent, IntentCategory
        registry = IntentRegistry()
        intent = Intent(
            name=name,
            category=IntentCategory(category),
            description=description or f"Custom intent: {name}",
            severity=severity,
            keywords=patterns,
        )
        registry.register(intent)
        return {
            "status": "ok",
            "message": f"Intent '{name}' added with {len(patterns)} patterns",
            "intent": {
                "name": name,
                "category": category,
                "severity": severity,
                "patterns": patterns,
            },
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── Helpers ───────────────────────────────────────────────

def _parse_timestamp(ts: Any) -> float | None:
    """Parse an ISO 8601 string or numeric timestamp to a unix float."""
    if ts is None:
        return None
    if isinstance(ts, (int, float)):
        return float(ts)
    if isinstance(ts, str):
        # Try ISO 8601 first
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return dt.timestamp()
        except (ValueError, TypeError):
            pass
        # Fallback: try as numeric string
        try:
            return float(ts)
        except (ValueError, TypeError):
            return None
    return None


def _format_audit_entry(entry: Any) -> dict:
    """Format an AuditEntry into a clean dict for API output."""
    return {
        "timestamp": entry.timestamp,
        "iso_time": _ts_to_iso(entry.timestamp),
        "result": entry.result_level,
        "blocked_by": entry.blocked_by,
        "input_preview": entry.input_preview,
        "output_preview": entry.output_preview,
        "checks": entry.checks_summary,
    }


def _ts_to_iso(ts: float) -> str:
    """Convert a unix timestamp to ISO 8601 string."""
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


# ── Tool Registry ─────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict[str, Any]] = {
    "guard_validate": {
        "description": "Validate AI-generated output through the AgentGuard safety pipeline. Returns whether the output passed, was blocked, or was auto-fixed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output": {
                    "type": "string",
                    "description": "The AI-generated output to validate (JSON string or plain text)",
                },
                "context": {
                    "type": "object",
                    "description": "Optional context about the validation request",
                },
            },
            "required": ["output"],
        },
        "handler": tool_guard_validate,
    },
    "guard_fix": {
        "description": "Analyze and fix AI output that fails validation. Supports schema auto-fix (missing fields, type coercion, enum matching), semantic fix suggestions, and policy compliance hints. Three modes: auto (apply fixes), suggest (hints only), strict (strip unknowns).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "output": {
                    "type": "string",
                    "description": "The AI-generated output that needs fixing",
                },
                "expected_schema": {
                    "type": "object",
                    "description": "Optional JSON Schema to validate and fix against",
                },
                "fix_mode": {
                    "type": "string",
                    "enum": ["auto", "suggest", "strict"],
                    "description": "Fix mode: 'auto' applies fixes, 'suggest' returns suggestions only, 'strict' strips unknown fields (default: auto)",
                },
            },
            "required": ["output"],
        },
        "handler": tool_guard_fix,
    },
    "guard_set_policy": {
        "description": "Dynamically update the AgentGuard policy with new YAML rules.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy": {
                    "type": "string",
                    "description": "YAML policy content with rules, defaults, and version",
                },
            },
            "required": ["policy"],
        },
        "handler": tool_guard_set_policy,
    },
    "guard_reload_policy": {
        "description": "Hot-reload the guard policy from a file path without restarting the MCP server.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "policy_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the YAML policy file to reload",
                },
            },
        },
        "handler": tool_guard_reload_policy,
    },
    "guard_list_policies": {
        "description": "Scan a directory for available AgentGuard policy YAML files. Returns a list with rules count and version for each.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory path to scan for policy files (defaults to current policy's directory or CWD)",
                },
            },
        },
        "handler": tool_guard_list_policies,
    },
    "guard_get_audit": {
        "description": "Query the audit log for guard validation events with time-range filtering and pagination.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of entries to return per page (default: 20, max: 100)",
                },
                "level": {
                    "type": "string",
                    "description": "Filter by result level: pass, warn, fix, ask_human, deny",
                    "enum": ["pass", "warn", "fix", "ask_human", "deny"],
                },
                "from_time": {
                    "type": "string",
                    "description": "ISO 8601 timestamp or unix float — only show entries after this time",
                },
                "to_time": {
                    "type": "string",
                    "description": "ISO 8601 timestamp or unix float — only show entries before this time",
                },
                "offset": {
                    "type": "integer",
                    "description": "Number of entries to skip for pagination (default: 0)",
                },
            },
        },
        "handler": tool_guard_get_audit,
    },
    "guard_status": {
        "description": "Report the current AgentGuard configuration, active layers, and policy status.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
        "handler": tool_guard_status,
    },
    "guard_add_intent": {
        "description": "Add a custom dangerous intent pattern to the semantic guard for detection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Unique name for the intent (e.g., 'exec_arbitrary_code')",
                },
                "patterns": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Keyword or regex patterns to match",
                },
                "description": {
                    "type": "string",
                    "description": "Human-readable description of the intent",
                },
                "severity": {
                    "type": "string",
                    "enum": ["critical", "high", "medium", "low"],
                    "description": "Severity level (default: medium)",
                },
                "category": {
                    "type": "string",
                    "enum": ["data_destruction", "system_operation", "network_risk", "credential_leak", "compliance_risk"],
                    "description": "Intent category (default: compliance_risk)",
                },
            },
            "required": ["name"],
        },
        "handler": tool_guard_add_intent,
    },
}
