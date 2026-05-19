"""Tests for GuardConfig."""
from agentguard.config import GuardConfig


class TestGuardConfig:
    def test_defaults(self):
        cfg = GuardConfig()
        assert cfg.auto_fix is True
        assert cfg.fail_open is True
        assert cfg.schema_timeout_ms == 100
        assert cfg.semantic_timeout_ms == 500
        assert cfg.policy_timeout_ms == 200
        assert cfg.audit_enabled is True
        assert cfg.audit_store == "memory"
        assert cfg.semantic_mode == "rule"
        assert cfg.on_fail == "deny"
        assert cfg.policy_path is None

    def test_default_dangerous_intents(self):
        cfg = GuardConfig()
        assert "drop_table" in cfg.dangerous_intents
        assert "execute_shell" in cfg.dangerous_intents
        assert "access_secret" in cfg.dangerous_intents

    def test_custom_values(self):
        cfg = GuardConfig(
            auto_fix=False,
            fail_open=False,
            on_fail="ask_human",
            policy_path="policies/prod.yaml",
        )
        assert cfg.auto_fix is False
        assert cfg.fail_open is False
        assert cfg.on_fail == "ask_human"
        assert cfg.policy_path == "policies/prod.yaml"

    def test_from_dict(self):
        d = {
            "auto_fix": False,
            "fail_open": False,
            "on_fail": "warn",
            "audit_store": "/tmp/audit.log",
        }
        cfg = GuardConfig.from_dict(d)
        assert cfg.auto_fix is False
        assert cfg.fail_open is False
        assert cfg.on_fail == "warn"
        assert cfg.audit_store == "/tmp/audit.log"

    def test_from_dict_ignores_unknown_keys(self):
        d = {
            "auto_fix": True,
            "unknown_key": "should be ignored",
        }
        cfg = GuardConfig.from_dict(d)
        assert cfg.auto_fix is True
        # unknown_key should not cause error
