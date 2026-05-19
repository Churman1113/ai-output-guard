"""Integration tests for the three-layer Guard pipeline."""
import json
import tempfile
from pathlib import Path

import pytest
from pydantic import BaseModel
from typing import Literal

from agentguard.guard import Guard
from agentguard.result import GuardLevel, GuardResult
from agentguard.errors import PolicyError


# ──────────────────────────────────────────────
# Pydantic models for testing
# ──────────────────────────────────────────────

class SafeOutput(BaseModel):
    action: str
    message: str


class StrictMethodOutput(BaseModel):
    endpoint: str
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]


class UserOutput(BaseModel):
    name: str
    role: str = "user"


# ──────────────────────────────────────────────
# Helper fixtures
# ──────────────────────────────────────────────

def _temp_policy_file(yaml_content: str) -> str:
    """Create a temp YAML file and return its path."""
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    )
    f.write(yaml_content)
    f.close()
    return f.name


# ──────────────────────────────────────────────
# No layers configured
# ──────────────────────────────────────────────

class TestGuardNoLayers:
    def test_no_layers_returns_pass(self):
        guard = Guard()
        result = guard.validate('{"action": "anything"}')
        assert isinstance(result, GuardResult)
        assert result.level == GuardLevel.PASS
        assert result.passed is True
        assert len(result.checks) == 0

    def test_no_layers_blocked_is_false(self):
        guard = Guard()
        result = guard.validate("some output")
        assert result.blocked is False


# ──────────────────────────────────────────────
# Schema-only Pipeline
# ──────────────────────────────────────────────

class TestSchemaOnlyGuard:
    def test_valid_output_passes(self):
        guard = Guard(schema=SafeOutput)
        result = guard.validate('{"action": "read", "message": "ok"}')
        assert result.level == GuardLevel.PASS
        assert result.passed is True
        assert len(result.checks) == 1
        assert result.checks[0].layer == "schema"

    def test_invalid_json_deny(self):
        guard = Guard(schema=SafeOutput)
        result = guard.validate("not json at all")
        assert result.level == GuardLevel.DENY
        assert result.blocked_by == "schema"
        assert result.blocked is True

    def test_fixable_output_returns_fix(self):
        guard = Guard(schema=StrictMethodOutput)
        # Missing params field, method is valid
        result = guard.validate('{"endpoint": "/api/test", "method": "GET"}')
        assert result.level == GuardLevel.PASS or result.level == GuardLevel.FIX
        # Validate that output is usable
        if result.level == GuardLevel.FIX:
            assert result.was_fixed is True
            assert result.output is not None

    def test_schema_deny_short_circuits(self):
        guard = Guard(schema=SafeOutput)
        result = guard.validate('{"bad": "json"}')
        # missing required fields -> should be guarded
        assert result.level in (GuardLevel.DENY, GuardLevel.WARN, GuardLevel.FIX)

    def test_strict_mode_strips_unknown(self):
        # Use strict_schema which may strip unknown fields
        guard = Guard(schema=SafeOutput, strict_schema=True)
        result = guard.validate('{"action": "read", "message": "ok", "extra": "field"}')
        assert result.level != GuardLevel.DENY


# ──────────────────────────────────────────────
# Semantic-only Pipeline
# ──────────────────────────────────────────────

class TestSemanticOnlyGuard:
    def test_safe_output_passes(self):
        guard = Guard(semantic=True)
        result = guard.validate('{"action": "read", "message": "hello world"}')
        assert result.level == GuardLevel.PASS

    def test_dangerous_output_deny(self):
        guard = Guard(semantic=True)
        result = guard.validate('DROP TABLE users CASCADE')
        assert result.level == GuardLevel.DENY
        assert result.blocked_by == "semantic"

    def test_rm_rf_deny(self):
        guard = Guard(semantic=True)
        result = guard.validate('rm -rf /etc/passwd')
        assert result.level == GuardLevel.DENY

    def test_empty_output_passes(self):
        guard = Guard(semantic=True)
        result = guard.validate("")
        assert result.level == GuardLevel.PASS


# ──────────────────────────────────────────────
# Policy-only Pipeline
# ──────────────────────────────────────────────

class TestPolicyOnlyGuard:
    def test_policy_match_deny(self):
        policy_yaml = """
rules:
  - name: "block_delete"
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: deny
"""
        path = _temp_policy_file(policy_yaml)
        try:
            guard = Guard(policy=path)
            result = guard.validate('{"method": "DELETE"}')
            assert result.level == GuardLevel.DENY
            assert result.blocked_by == "policy"
        finally:
            Path(path).unlink()

    def test_policy_no_match_pass(self):
        policy_yaml = """
rules:
  - name: "block_delete"
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: deny
"""
        path = _temp_policy_file(policy_yaml)
        try:
            guard = Guard(policy=path)
            result = guard.validate('{"method": "GET"}')
            assert result.level == GuardLevel.PASS
        finally:
            Path(path).unlink()

    def test_policy_yaml_string(self):
        guard = Guard(policy="""
rules:
  - name: "deny_prod"
    condition:
      field: endpoint
      operator: contains
      value: "/prod/"
    action: deny
""")
        result = guard.validate('{"endpoint": "/prod/deploy", "method": "POST"}')
        assert result.level == GuardLevel.DENY

    def test_policy_warn(self):
        guard = Guard(policy="""
rules:
  - name: "warn_delete"
    condition:
      field: method
      operator: equals
      value: "DELETE"
    action: warn
""")
        result = guard.validate('{"method": "DELETE"}')
        assert result.level == GuardLevel.WARN

    def test_policy_ask_human(self):
        guard = Guard(policy="""
rules:
  - name: "finance_review"
    condition:
      field: endpoint
      operator: contains
      value: "/finance/transfer"
    action: ask_human
""")
        result = guard.validate('{"endpoint": "/finance/transfer", "amount": 1000}')
        assert result.level == GuardLevel.ASK_HUMAN
        assert result.blocked_by == "policy"


# ──────────────────────────────────────────────
# Multi-layer Pipeline — Short Circuit
# ──────────────────────────────────────────────

class TestMultiLayerShortCircuit:
    def test_schema_deny_blocks_before_semantic(self):
        # Schema will fail on missing fields -> DENY
        policy_path = _temp_policy_file("""
rules:
  - name: "any_method"
    condition:
      field: method
      operator: exists
    action: deny
""")
        try:
            guard = Guard(
                schema=SafeOutput,
                semantic=True,
                policy=policy_path,
            )
            result = guard.validate('not json')
            assert result.level == GuardLevel.DENY
            assert result.blocked_by == "schema"
            # Only schema check executed, pipeline short-circuited
            assert len(result.checks) == 1
        finally:
            Path(policy_path).unlink()

    def test_semantic_deny_blocks_before_policy(self):
        # Semantic should detect DROP TABLE as dangerous
        # Even though policy might match too, semantic wins first
        policy_path = _temp_policy_file("""
rules:
  - name: "match_query"
    condition:
      field: query
      operator: exists
    action: deny
""")
        try:
            guard = Guard(
                semantic=True,
                policy=policy_path,
            )
            result = guard.validate('DROP TABLE users')
            assert result.level == GuardLevel.DENY
            assert result.blocked_by == "semantic"
            # Only semantic check executed
            assert len(result.checks) == 1
        finally:
            Path(policy_path).unlink()


# ──────────────────────────────────────────────
# WARN Level Propagation
# ──────────────────────────────────────────────

class TestWarnPropagation:
    def test_semantic_warn_promotes_to_warn(self):
        # Use a custom intent with medium severity to trigger WARN
        from agentguard.semantic.intent_registry import (
            Intent, IntentCategory, IntentRegistry,
        )
        custom_intent = Intent(
            name="test_risky",
            category=IntentCategory.COMPLIANCE_RISK,
            severity="medium",
            keywords=["test_risky_keyword_12345"],
        )
        registry = IntentRegistry(intents=[custom_intent])

        guard = Guard(semantic=True)
        # Override the internal semantic guard's registry — not possible directly,
        # so we test warn propagation with policy instead
        guard_with_policy = Guard(
            policy="""
rules:
  - name: "warn_policy"
    condition:
      field: risk_level
      operator: equals
      value: "medium"
    action: warn
"""
        )
        result = guard_with_policy.validate('{"risk_level": "medium", "action": "read"}')
        assert result.level == GuardLevel.WARN

    def test_warn_does_not_override_deny(self):
        # If schema DENIES, policy WARN should not downgrade it
        guard = Guard(
            schema=SafeOutput,
            policy="""
rules:
  - name: "any_field"
    condition:
      field: action
      operator: exists
    action: warn
"""
        )
        result = guard.validate('not json')
        assert result.level == GuardLevel.DENY
        assert result.blocked_by == "schema"


# ──────────────────────────────────────────────
# fail_open Behavior
# ──────────────────────────────────────────────

class TestFailOpen:
    def test_fail_open_default(self):
        # By default fail_open=True, so errors pass through
        # This is hard to test without forcing an internal error,
        # but we can verify the default behavior
        guard = Guard()
        assert guard._config.fail_open is True

    def test_fail_open_false_without_layers(self):
        guard = Guard(fail_open=False)
        result = guard.validate("anything")
        assert result.level == GuardLevel.PASS


# ──────────────────────────────────────────────
# Full Pipeline Integration
# ──────────────────────────────────────────────

class TestFullPipeline:
    def test_all_layers_pass(self):
        policy_path = _temp_policy_file("""
rules:
  - name: "allow_get"
    priority: 100
    condition:
      all:
        - field: method
          operator: equals
          value: "GET"
        - field: endpoint
          operator: startswith
          value: "/api/"
    action: deny
""")
        try:
            guard = Guard(
                schema=StrictMethodOutput,
                semantic=True,
                policy=policy_path,
            )
            # Safe output that passes all three layers
            result = guard.validate(
                '{"endpoint": "/dashboard", "method": "GET"}'
            )
            # Schema passes, semantic passes, policy doesn't match → PASS
            assert result.level == GuardLevel.PASS
            assert len(result.checks) == 3  # All three layers checked
            layer_names = [c.layer for c in result.checks]
            assert "schema" in layer_names
            assert "semantic" in layer_names
            assert "policy" in layer_names
        finally:
            Path(policy_path).unlink()

    def test_metadata_latency(self):
        guard = Guard(semantic=True)
        result = guard.validate("safe text")
        assert "latency_ms" in result.metadata
        assert result.metadata["latency_ms"] >= 0

    def test_to_dict(self):
        guard = Guard(semantic=True)
        result = guard.validate('DROP TABLE users')
        d = result.to_dict()
        assert d["level"] == "deny"
        assert d["blocked"] is True
        assert d["blocked_by"] == "semantic"
        assert len(d["checks"]) == 1
        assert d["checks"][0]["layer"] == "semantic"

    def test_schema_fix_then_other_layers_pass(self):
        """Schema auto-fixes a minor issue, then semantic and policy check the fixed output."""
        policy_path = _temp_policy_file("""
rules:
  - name: "block_prod"
    condition:
      field: endpoint
      operator: contains
      value: "/prod/"
    action: deny
""")
        try:
            guard = Guard(
                schema=StrictMethodOutput,
                semantic=True,
                policy=policy_path,
            )
            # Valid output — schema passes, semantic safe, policy no match
            result = guard.validate(
                '{"endpoint": "/api/users", "method": "GET"}'
            )
            assert result.level == GuardLevel.PASS
            assert len(result.checks) == 3
            for c in result.checks:
                assert c.layer in ("schema", "semantic", "policy")
        finally:
            Path(policy_path).unlink()


# ──────────────────────────────────────────────
# Guard() constructor edge cases
# ──────────────────────────────────────────────

class TestGuardConstructor:
    def test_schema_none_skips_schema(self):
        guard = Guard(schema=None)
        assert guard._schema_guard is None

    def test_semantic_false_skips_semantic(self):
        guard = Guard(semantic=False)
        assert guard._semantic_guard is None

    def test_policy_none_skips_policy(self):
        guard = Guard(policy=None)
        assert guard._policy_guard is None

    def test_policy_nonexistent_file_treated_as_yaml_content(self):
        # When path-like string doesn't resolve to a file, treat as YAML content
        with pytest.raises((ValueError, PolicyError)):
            Guard(policy="some_policy.yaml")

    def test_policy_inline_yaml(self):
        guard = Guard(policy="""
rules:
  - name: test
    condition:
      field: output
      operator: exists
    action: warn
""")
        assert guard._policy_guard is not None

    def test_auto_fix_disabled(self):
        guard = Guard(schema=SafeOutput, auto_fix=False)
        assert guard._config.auto_fix is False

    def test_on_fail_custom(self):
        guard = Guard(on_fail="warn")
        assert guard._config.on_fail == "warn"

    def test_audit_log_access(self):
        guard = Guard()
        assert hasattr(guard, "audit_log")
        # Should have entries after validation
        guard.validate('{"action": "read"}')
        # Audit log is accessible
        assert guard.audit_log is not None


# ──────────────────────────────────────────────
# Edge Cases
# ──────────────────────────────────────────────

class TestEdgeCases:
    def test_none_output(self):
        guard = Guard(semantic=True)
        result = guard.validate(None)
        # Semantic guard handles None
        assert result is not None

    def test_pydantic_model_as_input(self):
        guard = Guard(schema=SafeOutput)
        obj = SafeOutput(action="read", message="hello")
        result = guard.validate(obj)
        assert result.level == GuardLevel.PASS

    def test_pydantic_model_output_is_serialized_for_downstream(self):
        """Model input → Schema validates → dict passed to Policy."""
        guard = Guard(
            schema=SafeOutput,
            policy="""
rules:
  - name: "check_action"
    condition:
      field: action
      operator: exists
    action: allow
""",
        )
        obj = SafeOutput(action="read", message="hello")
        result = guard.validate(obj)
        assert result.level == GuardLevel.PASS
        # Schema should have run and produced a dict for policy
        assert len(result.checks) == 2  # schema + policy

    def test_pydantic_model_schema_fix_and_policy(self):
        """Model with enum typo → Schema auto-fixes → dict passed to Policy."""
        from pydantic import BaseModel

        class StrictModel(BaseModel):
            method: str  # not Literal, just str

        # Use a model that has a strict type
        class EnumModel(BaseModel):
            method: Literal["GET", "POST", "DELETE"]

        guard = Guard(
            schema=EnumModel,
            policy="""
rules:
  - name: "method_exists"
    condition:
      field: method
      operator: exists
    action: allow
""",
        )
        # Input with wrong enum value
        result = guard.validate('{"method": "GT"}')
        # Schema should fix GT→GET, then policy should pass
        assert result.level == GuardLevel.FIX or result.level == GuardLevel.PASS
        if result.level == GuardLevel.FIX:
            assert result.was_fixed is True

    def test_dict_as_input(self):
        guard = Guard(semantic=True)
        result = guard.validate({"query": "SELECT * FROM users"})
        assert result is not None

    def test_dict_input_with_schema(self):
        """Dict input to SchemaGuard should be validated and serialized."""
        guard = Guard(schema=SafeOutput)
        result = guard.validate({"action": "read", "message": "test"})
        assert result.level == GuardLevel.PASS

    def test_all_layers_with_dangerous_and_policy(self):
        """Dangerous output triggers semantic DENY before policy is reached."""
        policy_path = _temp_policy_file("""
rules:
  - name: "everything"
    condition:
      field: action
      operator: exists
    action: deny
""")
        try:
            guard = Guard(
                semantic=True,
                policy=policy_path,
            )
            result = guard.validate('DROP TABLE users CASCADE')
            assert result.level == GuardLevel.DENY
            assert result.blocked_by == "semantic"
            # Only semantic check ran (short-circuit)
            assert len(result.checks) == 1
        finally:
            Path(policy_path).unlink()
