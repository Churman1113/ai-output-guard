"""Policy file validator — structural and semantic checks."""

from __future__ import annotations

from typing import Any

from agentguard.policy.actions import VALID_ACTIONS
from agentguard.policy.operators import OPERATOR_MAP


def validate_policy(policy_data: dict[str, Any]) -> list[str]:
    """Validate policy structure and return list of errors.
    
    Returns empty list if valid.
    """
    errors: list[str] = []

    if not isinstance(policy_data, dict):
        errors.append("Policy root must be a dict/mapping")
        return errors

    # Check version
    version = policy_data.get("version")
    if version not in ("1.0", None):
        errors.append(f"Unknown policy version: {version}. Supported: 1.0")

    # Check defaults
    defaults = policy_data.get("defaults", {})
    if isinstance(defaults, dict):
        for key in ("on_no_match", "on_error"):
            val = defaults.get(key)
            if val is not None and val not in VALID_ACTIONS:
                errors.append(f"Defaults.{key} invalid action: '{val}'. Valid: {sorted(VALID_ACTIONS)}")

    # Check rules
    rules = policy_data.get("rules", [])
    if not isinstance(rules, list):
        errors.append("rules must be a list")
        return errors

    seen_names: set[str] = set()
    for i, rule in enumerate(rules):
        prefix = f"rules[{i}]"
        if not isinstance(rule, dict):
            errors.append(f"{prefix}: must be a dict")
            continue

        # Name
        name = rule.get("name")
        if not name:
            errors.append(f"{prefix}: missing 'name'")
        elif name in seen_names:
            errors.append(f"{prefix}: duplicate rule name '{name}'")
        else:
            seen_names.add(name)

        # Priority
        priority = rule.get("priority")
        if priority is not None and not isinstance(priority, (int, float)):
            errors.append(f"{prefix}: priority must be a number")

        # Condition
        condition = rule.get("condition", {})
        if not isinstance(condition, dict):
            errors.append(f"{prefix}: condition must be a dict")
        elif not condition:
            errors.append(f"{prefix}: condition is empty")
        else:
            # Recursively validate conditions
            errors.extend(_validate_condition(condition, f"{prefix}.condition"))

        # Action
        action = rule.get("action")
        if not action:
            errors.append(f"{prefix}: missing 'action'")
        elif action not in VALID_ACTIONS:
            errors.append(f"{prefix}: invalid action '{action}'. Valid: {sorted(VALID_ACTIONS)}")

    return errors


def _validate_condition(condition: dict, path: str) -> list[str]:
    """Recursively validate condition blocks."""
    errors: list[str] = []

    # Logical combinators
    if "all" in condition:
        sub = condition["all"]
        if not isinstance(sub, list):
            errors.append(f"{path}.all: must be a list")
        else:
            for j, cond in enumerate(sub):
                if isinstance(cond, dict):
                    errors.extend(_validate_condition(cond, f"{path}.all[{j}]"))
        return errors

    if "any" in condition:
        sub = condition["any"]
        if not isinstance(sub, list):
            errors.append(f"{path}.any: must be a list")
        else:
            for j, cond in enumerate(sub):
                if isinstance(cond, dict):
                    errors.extend(_validate_condition(cond, f"{path}.any[{j}]"))
        return errors

    # Single condition
    field = condition.get("field")
    if not field:
        errors.append(f"{path}: missing 'field'")

    operator = condition.get("operator", "equals")
    if operator not in OPERATOR_MAP:
        errors.append(f"{path}: unknown operator '{operator}'")

    return errors
