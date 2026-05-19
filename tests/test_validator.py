"""Tests for policy validator and parser integration."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from agentguard.errors import PolicyError
from agentguard.policy.parser import parse_policy, parse_policy_file
from agentguard.policy.validator import validate_policy


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_policy(**overrides) -> dict:
    """Return a minimal valid policy dict with optional overrides."""
    base = {
        "version": "1.0",
        "defaults": {"on_no_match": "allow", "on_error": "warn"},
        "rules": [
            {
                "name": "block_admin",
                "priority": 100,
                "condition": {"field": "role", "operator": "equals", "value": "admin"},
                "action": "deny",
                "message": "admin access denied",
            },
            {
                "name": "warn_region",
                "priority": 50,
                "condition": {"field": "region", "operator": "in", "value": ["BR", "AR"]},
                "action": "warn",
            },
        ],
    }
    base.update(overrides)
    return base


# ===========================================================================
# Unit tests — validate_policy()
# ===========================================================================

class TestValidatePolicy:
    """Tests for the standalone validate_policy() function."""

    def test_valid_policy_returns_empty(self):
        result = validate_policy(_valid_policy())
        assert result == []

    def test_minimal_policy_is_valid(self):
        """A policy with just one basic rule is valid."""
        minimal = {
            "version": "1.0",
            "rules": [
                {
                    "name": "simple",
                    "condition": {"field": "x", "operator": "equals", "value": 1},
                    "action": "allow",
                }
            ],
        }
        assert validate_policy(minimal) == []

    def test_non_dict_root(self):
        errors = validate_policy([])  # type: ignore[arg-type]
        assert any("must be a dict" in e for e in errors)

    def test_unknown_version(self):
        errors = validate_policy(_valid_policy(version="3.0"))
        assert any("Unknown policy version" in e for e in errors)

    def test_version_none_is_ok(self):
        """Version=None should pass (treated as 1.0)."""
        errors = validate_policy(_valid_policy(version=None))
        assert not any("Unknown policy version" in e for e in errors)

    def test_invalid_default_action(self):
        policy = _valid_policy(defaults={"on_no_match": "destroy"})
        errors = validate_policy(policy)
        assert any("on_no_match" in e and "destroy" in e for e in errors)

    def test_default_action_none_is_ok(self):
        errors = validate_policy(_valid_policy(defaults={"on_no_match": None}))
        assert not any("on_no_match" in e for e in errors)

    def test_rules_must_be_list(self):
        errors = validate_policy(_valid_policy(rules="not_a_list"))
        assert any("must be a list" in e for e in errors)

    def test_rule_must_be_dict(self):
        policy = _valid_policy(rules=["not_a_dict"])
        errors = validate_policy(policy)
        assert any("must be a dict" in e for e in errors)

    def test_missing_rule_name(self):
        policy = _valid_policy(rules=[{"condition": {"field": "x"}, "action": "deny"}])
        errors = validate_policy(policy)
        assert any("missing 'name'" in e for e in errors)

    def test_duplicate_rule_names(self):
        policy = _valid_policy(rules=[
            {"name": "dup", "condition": {"field": "a"}, "action": "allow"},
            {"name": "dup", "condition": {"field": "b"}, "action": "deny"},
        ])
        errors = validate_policy(policy)
        assert any("duplicate rule name" in e for e in errors)

    def test_invalid_rule_action(self):
        policy = _valid_policy(rules=[{
            "name": "bad_action",
            "condition": {"field": "x"},
            "action": "destroy",
        }])
        errors = validate_policy(policy)
        assert any("invalid action" in e and "destroy" in e for e in errors)

    def test_priority_must_be_number(self):
        policy = _valid_policy(rules=[{
            "name": "bad_priority",
            "condition": {"field": "x"},
            "action": "deny",
            "priority": "high",
        }])
        errors = validate_policy(policy)
        assert any("priority must be a number" in e for e in errors)

    def test_priority_none_is_ok(self):
        policy = _valid_policy(rules=[{
            "name": "ok_priority",
            "condition": {"field": "x"},
            "action": "deny",
            "priority": None,
        }])
        errors = validate_policy(policy)
        assert not any("priority" in e for e in errors)

    def test_condition_not_dict(self):
        policy = _valid_policy(rules=[{
            "name": "bad_cond",
            "condition": "not_a_dict",
            "action": "deny",
        }])
        errors = validate_policy(policy)
        assert any("condition must be a dict" in e for e in errors)

    def test_empty_condition(self):
        policy = _valid_policy(rules=[{
            "name": "empty_cond",
            "condition": {},
            "action": "deny",
        }])
        errors = validate_policy(policy)
        assert any("condition is empty" in e for e in errors)

    def test_unknown_operator(self):
        policy = _valid_policy(rules=[{
            "name": "bad_op",
            "condition": {"field": "x", "operator": "magic", "value": 1},
            "action": "deny",
        }])
        errors = validate_policy(policy)
        assert any("unknown operator" in e and "magic" in e for e in errors)

    def test_missing_field_in_condition(self):
        policy = _valid_policy(rules=[{
            "name": "no_field",
            "condition": {"operator": "equals", "value": 1},
            "action": "deny",
        }])
        errors = validate_policy(policy)
        assert any("missing 'field'" in e for e in errors)

    def test_all_combinator_valid(self):
        """all combinator with valid sub-conditions should pass."""
        policy = _valid_policy(rules=[{
            "name": "all_rule",
            "condition": {
                "all": [
                    {"field": "role", "operator": "equals", "value": "admin"},
                    {"field": "region", "operator": "in", "value": ["US"]},
                ]
            },
            "action": "deny",
        }])
        errors = validate_policy(policy)
        # Should have no condition errors for this rule
        assert all("all_rule" not in e for e in errors)

    def test_all_combinator_non_list(self):
        policy = _valid_policy(rules=[{
            "name": "bad_all",
            "condition": {"all": "not_a_list"},
            "action": "deny",
        }])
        errors = validate_policy(policy)
        assert any("must be a list" in e for e in errors)

    def test_any_combinator_valid(self):
        """any combinator with valid sub-conditions should pass."""
        policy = _valid_policy(rules=[{
            "name": "any_rule",
            "condition": {
                "any": [
                    {"field": "tier", "operator": "equals", "value": "free"},
                    {"field": "tier", "operator": "equals", "value": "trial"},
                ]
            },
            "action": "warn",
        }])
        errors = validate_policy(policy)
        assert all("any_rule" not in e for e in errors)

    def test_any_combinator_non_list(self):
        policy = _valid_policy(rules=[{
            "name": "bad_any",
            "condition": {"any": {"field": "x"}},
            "action": "deny",
        }])
        errors = validate_policy(policy)
        assert any("must be a list" in e for e in errors)

    def test_nested_all_any_valid(self):
        """Deeply nested all/any combinators should validate correctly."""
        policy = _valid_policy(rules=[{
            "name": "nested",
            "condition": {
                "all": [
                    {"field": "role", "operator": "equals", "value": "user"},
                    {
                        "any": [
                            {"field": "plan", "operator": "equals", "value": "pro"},
                            {"field": "plan", "operator": "equals", "value": "enterprise"},
                        ]
                    },
                ]
            },
            "action": "allow",
        }])
        errors = validate_policy(policy)
        assert all("nested" not in e for e in errors)

    def test_sub_condition_errors_in_all(self):
        """Errors inside all sub-conditions should be reported."""
        policy = _valid_policy(rules=[{
            "name": "bad_sub",
            "condition": {
                "all": [
                    {"field": "x", "operator": "magic_op"},
                    {"field": "y", "operator": "equals", "value": 1},
                ]
            },
            "action": "deny",
        }])
        errors = validate_policy(policy)
        assert any("magic_op" in e for e in errors)

    def test_multiple_errors_collected(self):
        """Multiple independent errors should all be reported."""
        policy = _valid_policy(
            version="99.0",
            rules=[
                {"name": "dup", "condition": {}, "action": "destroy"},
                {"name": "dup", "condition": {"field": "x", "operator": "wizard"}},
            ],
        )
        errors = validate_policy(policy)
        assert len(errors) >= 4  # unknown version, duplicate, invalid action, empty condition, bad operator


# ===========================================================================
# Integration tests — parse_policy() with validator
# ===========================================================================

class TestParsePolicyValidation:
    """Integration: parse_policy() raises PolicyError on invalid YAML."""

    def test_valid_yaml_parses(self):
        policy = parse_policy("""
version: "1.0"
rules:
  - name: ok
    condition:
      field: status
      operator: equals
      value: active
    action: allow
""")
        assert len(policy.rules) == 1
        assert policy.rules[0].name == "ok"

    def test_invalid_action_raises_policy_error(self):
        with pytest.raises(PolicyError, match="invalid action"):
            parse_policy("""
version: "1.0"
rules:
  - name: bad
    condition:
      field: x
    action: destroy
""")

    def test_duplicate_names_raise_policy_error(self):
        with pytest.raises(PolicyError, match="duplicate rule name"):
            parse_policy("""
version: "1.0"
rules:
  - name: same
    condition:
      field: a
    action: allow
  - name: same
    condition:
      field: b
    action: deny
""")

    def test_missing_name_raises_policy_error(self):
        with pytest.raises(PolicyError, match="missing 'name'"):
            parse_policy("""
version: "1.0"
rules:
  - condition:
      field: x
    action: deny
""")

    def test_empty_condition_raises_policy_error(self):
        with pytest.raises(PolicyError, match="condition is empty"):
            parse_policy("""
version: "1.0"
rules:
  - name: empty
    condition: {}
    action: deny
""")

    def test_unknown_operator_raises_policy_error(self):
        with pytest.raises(PolicyError, match="unknown operator"):
            parse_policy("""
version: "1.0"
rules:
  - name: bad_op
    condition:
      field: x
      operator: sorcery
    action: deny
""")


class TestParsePolicyFileValidation:
    """Integration: parse_policy_file() also validates via parse_policy()."""

    def test_valid_file_parses(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("""
version: "1.0"
rules:
  - name: file_rule
    condition:
      field: env
      operator: equals
      value: prod
    action: deny
""")
            f.flush()
            path = Path(f.name)

        try:
            policy = parse_policy_file(path)
            assert len(policy.rules) == 1
            assert policy.rules[0].name == "file_rule"
        finally:
            path.unlink()

    def test_invalid_file_raises_error(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("""
version: "1.0"
rules:
  - name: bad
    condition: {}
    action: nope
""")
            f.flush()
            path = Path(f.name)

        try:
            with pytest.raises(PolicyError):
                parse_policy_file(path)
        finally:
            path.unlink()
