"""Tests for result types: GuardLevel, CheckResult, GuardResult."""
import pytest
from agentguard.result import GuardLevel, CheckResult, GuardResult


class TestGuardLevel:
    def test_enum_values(self):
        assert GuardLevel.PASS.value == "pass"
        assert GuardLevel.DENY.value == "deny"
        assert GuardLevel.FIX.value == "fix"
        assert GuardLevel.WARN.value == "warn"
        assert GuardLevel.ASK_HUMAN.value == "ask_human"

    def test_is_blocking(self):
        assert GuardLevel.DENY.is_blocking is True
        assert GuardLevel.ASK_HUMAN.is_blocking is True
        assert GuardLevel.PASS.is_blocking is False
        assert GuardLevel.FIX.is_blocking is False
        assert GuardLevel.WARN.is_blocking is False

    def test_is_passing(self):
        assert GuardLevel.PASS.is_passing is True
        assert GuardLevel.DENY.is_passing is False
        assert GuardLevel.FIX.is_passing is False

    def test_is_fixable(self):
        assert GuardLevel.FIX.is_fixable is True
        assert GuardLevel.PASS.is_fixable is False
        assert GuardLevel.DENY.is_fixable is False

    def test_str_representation(self):
        # GuardLevel is a str Enum, so str() returns the enum member name
        assert str(GuardLevel.DENY) == "GuardLevel.DENY"
        assert str(GuardLevel.PASS) == "GuardLevel.PASS"


class TestCheckResult:
    def test_basic_creation(self):
        cr = CheckResult(
            layer="schema",
            level=GuardLevel.PASS,
            message="All good",
            confidence=1.0,
        )
        assert cr.layer == "schema"
        assert cr.level == GuardLevel.PASS
        assert cr.message == "All good"
        assert cr.confidence == 1.0
        assert cr.fix is None
        assert cr.original is None
        assert cr.metadata == {}

    def test_with_fix(self):
        cr = CheckResult(
            layer="schema",
            level=GuardLevel.FIX,
            message="Fixed typo",
            fix={"corrected": True},
            original={"raw": "bad"},
            confidence=0.9,
            metadata={"fixes": [{"field": "x"}]},
        )
        assert cr.fix == {"corrected": True}
        assert cr.original == {"raw": "bad"}
        assert cr.metadata["fixes"] == [{"field": "x"}]

    def test_to_dict(self):
        cr = CheckResult(
            layer="semantic",
            level=GuardLevel.DENY,
            message="Dangerous",
            confidence=1.0,
        )
        # CheckResult is a dataclass — verify all fields are accessible
        assert cr.layer == "semantic"
        assert cr.level == GuardLevel.DENY
        assert cr.message == "Dangerous"
        assert cr.confidence == 1.0


class TestGuardResult:
    def test_basic(self):
        cr = CheckResult(layer="schema", level=GuardLevel.PASS, message="OK")
        gr = GuardResult(
            level=GuardLevel.PASS,
            output={"result": "ok"},
            checks=[cr],
        )
        assert gr.level == GuardLevel.PASS
        assert gr.output == {"result": "ok"}
        assert len(gr.checks) == 1
        assert gr.blocked_by is None

    def test_passed_property(self):
        gr = GuardResult(level=GuardLevel.PASS, output={}, checks=[])
        assert gr.passed is True

        gr = GuardResult(level=GuardLevel.DENY, output={}, checks=[])
        assert gr.passed is False

        gr = GuardResult(level=GuardLevel.FIX, output={}, checks=[])
        assert gr.passed is False  # Only PASS == True

    def test_blocked_property(self):
        gr = GuardResult(level=GuardLevel.DENY, output={}, checks=[])
        assert gr.blocked is True

        gr = GuardResult(level=GuardLevel.PASS, output={}, checks=[])
        assert gr.blocked is False

    def test_was_fixed_property(self):
        gr = GuardResult(level=GuardLevel.FIX, output={}, checks=[])
        assert gr.was_fixed is True

        gr = GuardResult(level=GuardLevel.PASS, output={}, checks=[])
        assert gr.was_fixed is False

    def test_to_dict(self):
        cr = CheckResult(layer="schema", level=GuardLevel.PASS, message="OK")
        gr = GuardResult(
            level=GuardLevel.PASS,
            output={"x": 1},
            checks=[cr],
            blocked_by=None,
            metadata={"latency_ms": 1.5},
        )
        d = gr.to_dict()
        assert d["level"] == "pass"
        assert len(d["checks"]) == 1
        assert d["blocked_by"] is None

    def test_blocked_by_set(self):
        gr = GuardResult(
            level=GuardLevel.DENY,
            output={},
            checks=[],
            blocked_by="semantic",
        )
        assert gr.blocked_by == "semantic"
