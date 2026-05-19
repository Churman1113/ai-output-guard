"""Policy Guard — YAML DSL-powered access control and compliance checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentguard.result import CheckResult, GuardLevel
from agentguard.policy.parser import Policy, parse_policy, parse_policy_file
from agentguard.policy.engine import PolicyEngine
from agentguard.policy.actions import action_to_level


class PolicyGuard:
    """Applies policy rules to LLM output.

    Usage:
        guard = PolicyGuard.from_file("policies/production.yaml")
        result = guard.check(output)
    """

    def __init__(self, policy: Policy | None = None):
        self._policy = policy
        self._engine = PolicyEngine()

    @classmethod
    def from_file(cls, path: str | Path) -> PolicyGuard:
        """Create PolicyGuard from a YAML policy file."""
        policy = parse_policy_file(path)
        return cls(policy=policy)

    @classmethod
    def from_yaml(cls, yaml_text: str) -> PolicyGuard:
        """Create PolicyGuard from a YAML string."""
        policy = parse_policy(yaml_text)
        return cls(policy=policy)

    def check(self, output: Any) -> CheckResult:
        """Check output against configured policy rules.
        
        Returns:
            CheckResult with the action from the first matching rule,
            or default action if no rules match.
        """
        if self._policy is None:
            return CheckResult(
                layer="policy",
                level=GuardLevel.PASS,
                message="No policy configured, skipping",
                confidence=1.0,
            )

        # Ensure output is parseable as dict
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                output = {"raw": output}
        elif hasattr(output, "model_dump"):
            # Pydantic v2 model — serialize to dict
            output = output.model_dump()
        elif hasattr(output, "dict"):
            # Pydantic v1 model — serialize to dict
            output = output.dict()

        # Evaluate rules
        matched_rule = self._engine.evaluate(self._policy, output)

        if matched_rule is None:
            # No rule matched — use default
            default_action = self._policy.on_no_match
            level = action_to_level(default_action)
            return CheckResult(
                layer="policy",
                level=level,
                message=f"No policy rule matched (default: {default_action})",
                confidence=1.0,
                metadata={"action": default_action, "matched": False},
            )

        # Rule matched
        level = action_to_level(matched_rule.action)
        return CheckResult(
            layer="policy",
            level=level,
            message=matched_rule.message or f"Policy rule '{matched_rule.name}' matched",
            confidence=1.0,
            metadata={
                "rule": matched_rule.name,
                "action": matched_rule.action,
                "priority": matched_rule.priority,
                "audit": matched_rule.audit,
                "matched": True,
            },
        )

    @property
    def policy(self) -> Policy | None:
        return self._policy
