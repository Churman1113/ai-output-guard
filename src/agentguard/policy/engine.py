"""Policy rule matching engine.

Evaluates rules against structured output in priority order.
First match wins — the highest-priority rule that matches determines the result.
"""

from __future__ import annotations

from typing import Any

from agentguard.policy.operators import OPERATOR_MAP
from agentguard.policy.parser import Policy, Rule


class PolicyEngine:
    """Evaluate policy rules against LLM output."""

    def evaluate(self, policy: Policy, output: Any) -> Rule | None:
        """Evaluate all rules in priority order. Returns first matching rule or None.
        
        Args:
            policy: Parsed Policy object with sorted rules.
            output: The LLM output to check (parsed dict or raw).
        
        Returns:
            First matching Rule, or None if no rule matched.
        """
        for rule in policy.rules:
            if self._rule_matches(rule, output):
                return rule
        return None

    def _rule_matches(self, rule: Rule, output: Any) -> bool:
        """Check if a single rule's condition matches the output."""
        condition = rule.condition
        if not condition:
            return False

        # Handle logical combinations: 'all' (AND) and 'any' (OR)
        if "all" in condition:
            return self._check_all(condition["all"], output)
        if "any" in condition:
            return self._check_any(condition["any"], output)

        # Single condition
        return self._check_condition(condition, output)

    def _check_all(self, conditions: list[dict], output: Any) -> bool:
        """AND combinator — all conditions must match."""
        if not conditions:
            return False
        return all(self._check_condition(c, output) for c in conditions)

    def _check_any(self, conditions: list[dict], output: Any) -> bool:
        """OR combinator — any condition must match."""
        if not conditions:
            return False
        return any(self._check_condition(c, output) for c in conditions)

    def _check_condition(self, condition: dict, output: Any) -> bool:
        """Evaluate a single condition {field, operator, value}."""
        field = condition.get("field", "")
        operator_name = condition.get("operator", "equals")
        expected = condition.get("value")

        if not field:
            return False

        # Extract the field value from output (supports dot-notation: "params.scope")
        actual = self._get_field(output, field)

        # Look up the operator function
        op_func = OPERATOR_MAP.get(operator_name)
        if op_func is None:
            return False

        # Special case: exists/not_exists don't need a value parameter
        if operator_name in ("exists", "not_exists"):
            return op_func(actual)

        return op_func(actual, expected)

    def _get_field(self, output: Any, field_path: str) -> Any:
        """Extract a nested field value using dot-notation.
        
        Examples:
            _get_field({"a": {"b": 1}}, "a.b") -> 1
            _get_field({"x": "hello"}, "x") -> "hello"
        """
        if not isinstance(output, dict):
            return None

        parts = field_path.split(".")
        current = output

        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

            if current is None:
                return None

        return current
