"""Tests for PolicyGuard — parser, engine, operators, actions, and integration."""
import json
import tempfile
from pathlib import Path

import pytest

from agentguard.errors import PolicyError
from agentguard.policy.parser import (
    Policy, Rule, parse_policy, parse_policy_file,
)
from agentguard.policy.engine import PolicyEngine
from agentguard.policy.actions import (
    action_to_level, VALID_ACTIONS, ACTION_TO_LEVEL,
)
from agentguard.policy.operators import (
    matches, equals, not_equals, contains, startswith, endswith,
    in_set, gt, gte, lt, lte, exists, not_exists,
)
from agentguard.policy_guard import PolicyGuard
from agentguard.result import GuardLevel, CheckResult


# ──────────────────────────────────────────────
# Operators
# ──────────────────────────────────────────────

class TestOperators:
    def test_equals_match(self):
        assert equals("hello", "hello") is True

    def test_equals_no_match(self):
        assert equals("hello", "world") is False

    def test_equals_case_sensitive(self):
        assert equals("Hello", "hello") is False

    def test_not_equals(self):
        assert not_equals("hello", "world") is True
        assert not_equals("x", "x") is False

    def test_contains_case_insensitive(self):
        assert contains("Hello World", "world") is True
        assert contains("Hello World", "xyz") is False

    def test_contains_non_string(self):
        assert contains(123, "12") is False
        assert contains(None, "x") is False

    def test_matches_regex(self):
        assert matches("abc123", r"\d+") is True
        assert matches("abc", r"\d+") is False

    def test_matches_glob_wildcard(self):
        # * → .*
        assert matches("/api/users/123", "/api/*/123") is True
        # ? → .
        assert matches("/api/v1/us3r", "/api/v?/us?r") is True

    def test_matches_non_string(self):
        assert matches(42, r"\d+") is False

    def test_startswith(self):
        assert startswith("hello world", "hello") is True
        assert startswith("hello world", "world") is False

    def test_startswith_non_string(self):
        assert startswith(None, "x") is False
        assert startswith(42, "4") is False

    def test_endswith(self):
        assert endswith("hello world", "world") is True
        assert endswith("hello world", "hello") is False

    def test_endswith_non_string(self):
        assert endswith(None, "x") is False

    def test_in_set(self):
        assert in_set("GET", ["GET", "POST", "PUT"]) is True
        assert in_set("DELETE", ["GET", "POST"]) is False

    def test_gt(self):
        assert gt(10, 5) is True
        assert gt(5, 10) is False
        assert gt("abc", 5) is False

    def test_gte(self):
        assert gte(5, 5) is True
        assert gte(4, 5) is False

    def test_lt(self):
        assert lt(3, 10) is True
        assert lt(10, 3) is False

    def test_lte(self):
        assert lte(5, 5) is True
        assert lte(6, 5) is False

    def test_exists(self):
        assert exists("value") is True
        assert exists(0) is True
        assert exists("") is True
        assert exists(None) is False

    def test_not_exists(self):
        assert not_exists(None) is True
        assert not_exists("value") is False


# ──────────────────────────────────────────────
# Actions
# ──────────────────────────────────────────────

class TestActions:
    def test_valid_actions_set(self):
        assert "allow" in VALID_ACTIONS
        assert "deny" in VALID_ACTIONS
        assert "warn" in VALID_ACTIONS
        assert "ask_human" in VALID_ACTIONS
        assert "modify" in VALID_ACTIONS
        assert "invalid" not in VALID_ACTIONS

    def test_action_to_level_allow(self):
        assert action_to_level("allow") == GuardLevel.PASS

    def test_action_to_level_deny(self):
        assert action_to_level("deny") == GuardLevel.DENY

    def test_action_to_level_warn(self):
        assert action_to_level("warn") == GuardLevel.WARN

    def test_action_to_level_ask_human(self):
        assert action_to_level("ask_human") == GuardLevel.ASK_HUMAN

    def test_action_to_level_modify(self):
        assert action_to_level("modify") == GuardLevel.FIX

    def test_action_to_level_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown action"):
            action_to_level("banana")


# ──────────────────────────────────────────────
# Parser — Data Models
# ──────────────────────────────────────────────

class TestRuleDataclass:
    def test_defaults(self):
        r = Rule(name="test_rule")
        assert r.name == "test_rule"
        assert r.priority == 0
        assert r.condition == {}
        assert r.action == "deny"
        assert r.message == ""
        assert r.timeout is None
        assert r.fallback == "deny"
        assert r.audit is True

    def test_full_init(self):
        r = Rule(
            name="full",
            priority=50,
            condition={"all": []},
            action="warn",
            message="Watch out!",
            timeout=30,
            fallback="allow",
            audit=False,
        )
        assert r.action == "warn"
        assert r.priority == 50
        assert r.timeout == 30
        assert r.fallback == "allow"
        assert r.audit is False


class TestPolicyDataclass:
    def test_defaults(self):
        p = Policy()
        assert p.version == "1.0"
        assert p.on_no_match == "allow"
        assert p.on_error == "pass"
        assert p.rules == []
        assert p.source_path == ""

    def test_custom_defaults(self):
        p = Policy(defaults={"on_no_match": "deny", "on_error": "deny"})
        assert p.on_no_match == "deny"
        assert p.on_error == "deny"

    def test_on_no_match_falls_back_to_default(self):
        p = Policy()
        assert p.on_no_match == "allow"


# ──────────────────────────────────────────────
# Parser — parse_policy (YAML string)
# ──────────────────────────────────────────────

class TestParsePolicy:
    def test_minimal_yaml(self):
        yaml_text = "rules: []"
        p = parse_policy(yaml_text)
        assert isinstance(p, Policy)
        assert p.version == "1.0"
        assert p.rules == []

    def test_single_rule(self):
        yaml_text = """
rules:
  - name: "test rule"
    priority: 10
    condition:
      field: endpoint
      operator: equals
      value: "/admin"
    action: deny
    message: "Access denied"
"""
        p = parse_policy(yaml_text)
        assert len(p.rules) == 1
        r = p.rules[0]
        assert r.name == "test rule"
        assert r.priority == 10
        assert r.condition == {"field": "endpoint", "operator": "equals", "value": "/admin"}
        assert r.action == "deny"
        assert r.message == "Access denied"

    def test_multiple_rules_sorted_by_priority(self):
        yaml_text = """
rules:
  - name: low
    priority: 10
    condition:
      field: x
      operator: equals
      value: 1
    action: warn
  - name: high
    priority: 100
    condition:
      field: x
      operator: equals
      value: 1
    action: deny
  - name: mid
    priority: 50
    condition:
      field: x
      operator: equals
      value: 1
    action: warn
"""
        p = parse_policy(yaml_text)
        assert len(p.rules) == 3
        # Sorted descending by priority
        assert p.rules[0].name == "high"
        assert p.rules[1].name == "mid"
        assert p.rules[2].name == "low"

    def test_same_priority_preserves_order(self):
        yaml_text = """
rules:
  - name: first
    priority: 10
    condition:
      field: x
      operator: equals
      value: 1
    action: deny
  - name: second
    priority: 10
    condition:
      field: x
      operator: equals
      value: 1
    action: warn
"""
        p = parse_policy(yaml_text)
        # Python's sort is stable, so order within same priority is preserved
        assert p.rules[0].name == "first"
        assert p.rules[1].name == "second"

    def test_version_defaults(self):
        yaml_text = """
version: "1.0"
rules:
  - name: v1_rule
    condition:
      field: x
      operator: equals
      value: 1
    action: deny
"""
        p = parse_policy(yaml_text)
        assert p.version == "1.0"

    def test_defaults_on_no_match(self):
        yaml_text = """
defaults:
  on_no_match: deny
  on_error: deny
rules:
  - name: test
    condition:
      field: x
      operator: equals
      value: 1
    action: deny
"""
        p = parse_policy(yaml_text)
        assert p.on_no_match == "deny"
        assert p.on_error == "deny"

    def test_rule_with_all_condition(self):
        yaml_text = """
rules:
  - name: "complex rule"
    priority: 100
    condition:
      all:
        - field: method
          operator: equals
          value: "DELETE"
        - field: endpoint
          operator: contains
          value: "/prod/"
    action: deny
"""
        p = parse_policy(yaml_text)
        assert len(p.rules) == 1
        assert p.rules[0].condition == {
            "all": [
                {"field": "method", "operator": "equals", "value": "DELETE"},
                {"field": "endpoint", "operator": "contains", "value": "/prod/"},
            ]
        }

    def test_rule_with_any_condition(self):
        yaml_text = """
rules:
  - name: "either or"
    condition:
      any:
        - field: role
          operator: equals
          value: "admin"
        - field: role
          operator: equals
          value: "superadmin"
    action: deny
"""
        p = parse_policy(yaml_text)
        assert "any" in p.rules[0].condition
        assert len(p.rules[0].condition["any"]) == 2

    def test_parse_error_invalid_yaml(self):
        with pytest.raises(ValueError, match="Failed to parse policy YAML"):
            parse_policy(":: invalid :: yaml ::")   # pragma: allowlist secret — test fixture

    def test_parse_error_not_a_dict(self):
        with pytest.raises(ValueError, match="must be a mapping"):
            parse_policy("- list item")

    def test_invalid_rule_raw_skipped(self):
        yaml_text = """
rules:
  - just a string
  - name: valid
    condition:
      field: x
      operator: equals
      value: 1
    action: deny
"""
        # Non-dict rule entries are rejected by validator
        with pytest.raises(PolicyError, match="must be a dict"):
            parse_policy(yaml_text)


# ──────────────────────────────────────────────
# Parser — parse_policy_file
# ──────────────────────────────────────────────

class TestParsePolicyFile:
    def test_reads_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("""
rules:
  - name: "file_rule"
    condition:
      field: x
      operator: equals
      value: 1
    action: warn
""")
            path = f.name

        try:
            p = parse_policy_file(path)
            assert len(p.rules) == 1
            assert p.rules[0].name == "file_rule"
            assert p.source_path == path
        finally:
            Path(path).unlink()

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            parse_policy_file("/nonexistent/policy.yaml")


# ──────────────────────────────────────────────
# PolicyEngine
# ──────────────────────────────────────────────

class TestPolicyEngine:
    @pytest.fixture
    def engine(self):
        return PolicyEngine()

    def test_no_rules_returns_none(self, engine):
        p = Policy(rules=[])
        assert engine.evaluate(p, {"x": 1}) is None

    def test_single_condition_match(self, engine):
        p = parse_policy("""
rules:
  - name: match_method
    priority: 100
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: deny
""")
        result = engine.evaluate(p, {"method": "DELETE"})
        assert result is not None
        assert result.name == "match_method"

    def test_single_condition_no_match(self, engine):
        p = parse_policy("""
rules:
  - name: match_method
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: deny
""")
        result = engine.evaluate(p, {"method": "GET"})
        assert result is None

    def test_first_match_wins(self, engine):
        yaml_text = """
rules:
  - name: high_priority
    priority: 200
    condition:
      field: endpoint
      operator: contains
      value: "/admin"
    action: deny
  - name: low_priority
    priority: 10
    condition:
      field: endpoint
      operator: contains
      value: "/"
    action: warn
"""
        p = parse_policy(yaml_text)
        result = engine.evaluate(p, {"endpoint": "/admin/dashboard"})
        # Both match, but high_priority should win
        assert result.name == "high_priority"
        assert result.action == "deny"

    def test_second_rule_when_first_no_match(self, engine):
        yaml_text = """
rules:
  - name: narrow
    priority: 100
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: deny
  - name: broad
    priority: 50
    condition:
      field: endpoint
      operator: contains
      value: "/api/"
    action: warn
"""
        p = parse_policy(yaml_text)
        result = engine.evaluate(p, {"method": "GET", "endpoint": "/api/users"})
        # First rule doesn't match (method != DELETE), second should
        assert result is not None
        assert result.name == "broad"

    def test_all_and_condition(self, engine):
        p = parse_policy("""
rules:
  - name: "requires both"
    priority: 100
    condition:
      all:
        - field: method
          operator: equals
          value: "DELETE"
        - field: endpoint
          operator: contains
          value: "/prod/"
    action: deny
""")
        # Both match
        assert engine.evaluate(p, {"method": "DELETE", "endpoint": "/prod/items"}) is not None
        # Only one matches
        assert engine.evaluate(p, {"method": "DELETE", "endpoint": "/test/items"}) is None
        # Neither matches
        assert engine.evaluate(p, {"method": "GET", "endpoint": "/test/items"}) is None

    def test_any_or_condition(self, engine):
        p = parse_policy("""
rules:
  - name: "either one"
    priority: 100
    condition:
      any:
        - field: method
          operator: equals
          value: "DELETE"
        - field: method
          operator: equals
          value: "POST"
    action: deny
""")
        assert engine.evaluate(p, {"method": "DELETE"}) is not None
        assert engine.evaluate(p, {"method": "POST"}) is not None
        assert engine.evaluate(p, {"method": "GET"}) is None

    def test_empty_condition_no_match(self, engine):
        p = Policy(rules=[Rule(name="empty_cond", condition={})])
        assert engine.evaluate(p, {"x": 1}) is None

    def test_empty_all_list_no_match(self, engine):
        p = Policy(rules=[
            Rule(name="empty_all", condition={"all": []})
        ])
        assert engine.evaluate(p, {"x": 1}) is None

    def test_empty_any_list_no_match(self, engine):
        p = Policy(rules=[
            Rule(name="empty_any", condition={"any": []})
        ])
        assert engine.evaluate(p, {"x": 1}) is None

    def test_nested_dot_notation(self, engine):
        p = parse_policy("""
rules:
  - name: nested_check
    priority: 100
    condition:
      field: user.role
      operator: equals
      value: "admin"
    action: deny
""")
        result = engine.evaluate(p, {"user": {"role": "admin", "name": "test"}})
        assert result is not None
        assert result.name == "nested_check"
        # Non-matching nested
        result2 = engine.evaluate(p, {"user": {"role": "viewer"}})
        assert result2 is None

    def test_nested_dot_notation_missing_key(self, engine):
        p = parse_policy("""
rules:
  - name: nested_check
    condition:
      field: user.role
      operator: equals
      value: "admin"
    action: deny
""")
        # No 'user' key at all
        result = engine.evaluate(p, {"method": "GET"})
        assert result is None

    def test_unknown_operator_returns_false(self, engine):
        p = Policy(rules=[
            Rule(name="unknown_op", condition={
                "field": "method",
                "operator": "quantum_compare",
                "value": "X",
            })
        ])
        assert engine.evaluate(p, {"method": "X"}) is None

    def test_missing_field_in_condition(self, engine):
        p = Policy(rules=[
            Rule(name="no_field", condition={"operator": "equals", "value": "x"})
        ])
        assert engine.evaluate(p, {"a": "x"}) is None

    def test_non_dict_output(self, engine):
        p = parse_policy("""
rules:
  - name: check
    condition:
      field: x
      operator: exists
    action: deny
""")
        # Non-dict output — _get_field returns None
        assert engine.evaluate(p, "just a string") is None

    def test_gt_operator(self, engine):
        p = parse_policy("""
rules:
  - name: max_amount
    condition:
      field: amount
      operator: gt
      value: 1000
    action: deny
""")
        assert engine.evaluate(p, {"amount": 2000}) is not None
        assert engine.evaluate(p, {"amount": 500}) is None

    def test_exists_operator(self, engine):
        p = parse_policy("""
rules:
  - name: has_secret
    condition:
      field: api_key
      operator: exists
    action: deny
""")
        assert engine.evaluate(p, {"api_key": "sk-123"}) is not None
        assert engine.evaluate(p, {"method": "GET"}) is None

    def test_not_exists_operator(self, engine):
        p = parse_policy("""
rules:
  - name: missing_required
    condition:
      field: auth_token
      operator: not_exists
    action: deny
""")
        assert engine.evaluate(p, {"method": "GET"}) is not None
        assert engine.evaluate(p, {"auth_token": "token123"}) is None


# ──────────────────────────────────────────────
# PolicyGuard
# ──────────────────────────────────────────────

class TestPolicyGuard:
    def test_no_policy_returns_pass(self):
        guard = PolicyGuard()
        result = guard.check({"method": "DELETE"})
        assert result.level == GuardLevel.PASS
        assert result.layer == "policy"
        assert "No policy configured" in result.message

    def test_from_yaml_deny_match(self):
        guard = PolicyGuard.from_yaml("""
rules:
  - name: "block dangerous"
    priority: 100
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: deny
""")
        result = guard.check({"method": "DELETE"})
        assert result.level == GuardLevel.DENY
        assert result.metadata["rule"] == "block dangerous"
        assert result.metadata["matched"] is True

    def test_from_yaml_warn_match(self):
        guard = PolicyGuard.from_yaml("""
rules:
  - name: "watch"
    condition:
      field: method
      operator: equals
      value: "PATCH"
    action: warn
""")
        result = guard.check({"method": "PATCH"})
        assert result.level == GuardLevel.WARN

    def test_from_yaml_ask_human_match(self):
        guard = PolicyGuard.from_yaml("""
rules:
  - name: "needs review"
    condition:
      field: endpoint
      operator: contains
      value: "/finance/"
    action: ask_human
""")
        result = guard.check({"endpoint": "/finance/transfer"})
        assert result.level == GuardLevel.ASK_HUMAN

    def test_no_match_uses_default(self):
        guard = PolicyGuard.from_yaml("""
defaults:
  on_no_match: deny
rules:
  - name: "catch_all"
    condition:
      field: role
      operator: equals
      value: "admin"
    action: allow
""")
        result = guard.check({"role": "guest"})
        assert result.level == GuardLevel.DENY
        assert result.metadata["matched"] is False

    def test_no_match_default_allow(self):
        guard = PolicyGuard.from_yaml("""
rules:
  - name: specific
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: deny
""")
        result = guard.check({"method": "GET"})
        assert result.level == GuardLevel.PASS
        assert result.metadata["action"] == "allow"

    def test_string_output_parsed_as_json(self):
        guard = PolicyGuard.from_yaml("""
rules:
  - name: check_method
    condition:
      field: method
      operator: equals
      value: "POST"
    action: deny
""")
        result = guard.check('{"method": "POST"}')
        assert result.level == GuardLevel.DENY

    def test_invalid_json_string_falls_back_to_raw(self):
        guard = PolicyGuard.from_yaml("""
rules:
  - name: match_raw
    condition:
      field: raw
      operator: exists
    action: warn
""")
        result = guard.check("not { json } at all")
        # Gets wrapped in {"raw": "..."} because JSON parse fails
        assert result.level == GuardLevel.WARN  # 'raw' field exists

    def test_from_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False
        ) as f:
            f.write("""
rules:
  - name: "file_based"
    condition:
      field: action
      operator: equals
      value: "delete"
    action: deny
""")
            path = f.name

        try:
            guard = PolicyGuard.from_file(path)
            assert guard.policy is not None
            assert len(guard.policy.rules) == 1
            result = guard.check({"action": "delete"})
            assert result.level == GuardLevel.DENY
        finally:
            Path(path).unlink()

    def test_rule_message_in_result(self):
        guard = PolicyGuard.from_yaml("""
rules:
  - name: custom_msg
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: deny
    message: "Delete operations are prohibited"
""")
        result = guard.check({"method": "DELETE"})
        assert "Delete operations are prohibited" in result.message

    def test_rule_metadata_audit_flag(self):
        guard = PolicyGuard.from_yaml("""
rules:
  - name: silent_rule
    audit: false
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: deny
""")
        result = guard.check({"method": "DELETE"})
        assert result.metadata["audit"] is False

    def test_policy_property(self):
        guard = PolicyGuard.from_yaml("""
rules:
  - name: test
    condition:
      field: x
      operator: equals
      value: 1
    action: deny
""")
        assert guard.policy is not None
        assert isinstance(guard.policy, Policy)
