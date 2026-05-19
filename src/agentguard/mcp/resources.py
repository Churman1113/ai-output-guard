"""MCP Resource definitions for AgentGuard.

Resources are read-only data that AI IDEs can access, such as
the current policy YAML and audit statistics.
"""

from __future__ import annotations

import json
from typing import Any


def resource_policy(policy_path: str | None = None) -> str:
    """Read and return the current AgentGuard policy as YAML/JSON."""
    if not policy_path:
        return json.dumps({
            "status": "no_policy",
            "message": "No policy file configured",
        }, indent=2)

    try:
        from pathlib import Path
        content = Path(policy_path).read_text(encoding="utf-8")
        return content
    except FileNotFoundError:
        return json.dumps({
            "status": "error",
            "message": f"Policy file not found: {policy_path}",
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
        }, indent=2)


def resource_stats(policy_path: str | None = None) -> str:
    """Read and return audit statistics."""
    try:
        from agentguard import Guard
        guard = Guard(semantic=True, policy=policy_path)

        entries = guard.audit_log.entries
        total = len(entries)

        level_counts = {"pass": 0, "warn": 0, "fix": 0, "ask_human": 0, "deny": 0}
        blocked_by_counts = {}

        for entry in entries:
            level = entry.result_level
            if level in level_counts:
                level_counts[level] += 1
            if entry.blocked_by:
                blocked_by_counts[entry.blocked_by] = blocked_by_counts.get(entry.blocked_by, 0) + 1

        return json.dumps({
            "total_validations": total,
            "by_level": level_counts,
            "blocked_by_layer": blocked_by_counts,
            "pass_rate": f"{(level_counts['pass'] / total * 100):.1f}%" if total > 0 else "0.0%",
            "deny_rate": f"{(level_counts['deny'] / total * 100):.1f}%" if total > 0 else "0.0%",
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
        }, indent=2)


# ── Resource Registry ─────────────────────────────────────

RESOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "policy": {
        "uri": "agentguard://policy",
        "name": "Current Policy",
        "description": "The currently active AgentGuard policy rules in YAML format",
        "mimeType": "application/x-yaml",
        "handler": resource_policy,
    },
    "stats": {
        "uri": "agentguard://stats",
        "name": "Audit Statistics",
        "description": "Aggregate statistics from the audit log: pass/deny rates, blocked-by-layer counts",
        "mimeType": "application/json",
        "handler": resource_stats,
    },
}
