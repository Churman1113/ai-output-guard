"""YAML policy DSL parser."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agentguard.errors import PolicyError
from agentguard.policy.validator import validate_policy


@dataclass
class Rule:
    """A single policy rule."""
    name: str
    priority: int = 0
    condition: dict[str, Any] = field(default_factory=dict)
    action: str = "deny"
    message: str = ""
    timeout: int | None = None
    fallback: str = "deny"
    audit: bool = True


@dataclass
class Policy:
    """A parsed policy file."""
    version: str = "1.0"
    defaults: dict[str, str] = field(default_factory=lambda: {
        "on_no_match": "allow",
        "on_error": "pass",
    })
    rules: list[Rule] = field(default_factory=list)
    source_path: str = ""

    @property
    def on_no_match(self) -> str:
        return self.defaults.get("on_no_match", "allow")

    @property
    def on_error(self) -> str:
        return self.defaults.get("on_error", "pass")


def parse_policy(yaml_text: str, source_path: str = "") -> Policy:
    """Parse YAML policy text into a Policy object.
    
    Uses yaml.safe_load to prevent arbitrary code execution.
    """
    try:
        raw = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse policy YAML: {e}")

    if not isinstance(raw, dict):
        raise ValueError("Policy YAML must be a mapping (dict)")

    policy = Policy(
        version=raw.get("version", "1.0"),
        defaults=raw.get("defaults", {}),
        source_path=source_path,
    )

    for rule_raw in raw.get("rules", []):
        if not isinstance(rule_raw, dict):
            raise PolicyError(f"Each rule must be a dict, got {type(rule_raw).__name__}")

        rule = Rule(
            name=rule_raw.get("name", "unnamed"),
            priority=rule_raw.get("priority", 0),
            condition=rule_raw.get("condition", {}),
            action=rule_raw.get("action", "deny"),
            message=rule_raw.get("message", ""),
            timeout=rule_raw.get("timeout"),
            fallback=rule_raw.get("fallback", "deny"),
            audit=rule_raw.get("audit", True),
        )
        policy.rules.append(rule)

    # Sort by priority descending (higher = checked first)
    policy.rules.sort(key=lambda r: -r.priority)

    # Validate before returning
    validation_errors = validate_policy(raw)
    if validation_errors:
        raise PolicyError("\n".join(validation_errors))

    return policy


def parse_policy_file(path: str | Path) -> Policy:
    """Parse a YAML policy file from disk."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Policy file not found: {path}")

    yaml_text = path.read_text(encoding="utf-8")
    return parse_policy(yaml_text, source_path=str(path))
