"""Configuration loading and management."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GuardConfig:
    """Main configuration for Guard.
    
    Attributes:
        policy_path: Path to a YAML policy file.
        auto_fix: Enable auto-fix for schema errors.
        fail_open: If True, guard errors pass through. If False, DENY on guard error.
        schema_timeout_ms: Max ms for schema validation.
        semantic_timeout_ms: Max ms for semantic check.
        policy_timeout_ms: Max ms for policy check.
        audit_enabled: Enable audit logging.
        audit_store: "memory" (default) or file path.
        semantic_mode: "rule" (default) or "classifier" or "embedding".
        dangerous_intents: List of intent names to block.
        on_fail: Default action when a check fails: "deny" | "ask_human" | "warn".
    """
    policy_path: str | None = None
    auto_fix: bool = True
    fail_open: bool = True
    schema_timeout_ms: int = 100
    semantic_timeout_ms: int = 500
    policy_timeout_ms: int = 200
    audit_enabled: bool = True
    audit_store: str = "memory"
    semantic_mode: str = "rule"
    dangerous_intents: list[str] = field(default_factory=lambda: [
        "drop_table", "delete_all", "truncate", "rm_recursive",
        "execute_shell", "ssh_connect", "sudo",
        "access_secret", "expose_api_key",
    ])
    on_fail: str = "deny"

    @classmethod
    def from_dict(cls, d: dict) -> GuardConfig:
        """Create config from dict, only using known keys."""
        known = {
            k: d[k] for k in cls.__dataclass_fields__
            if k in d
        }
        return cls(**known)
