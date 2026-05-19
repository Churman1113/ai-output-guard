"""Tests for SemanticGuard, IntentRegistry, and RuleMatcher."""
import pytest
from agentguard.semantic_guard import SemanticGuard
from agentguard.semantic.intent_registry import (
    Intent, IntentCategory, IntentRegistry, BUILTIN_INTENTS,
)
from agentguard.semantic.rule_matcher import RuleMatcher
from agentguard.result import GuardLevel


class TestIntentRegistry:
    def test_builtin_intents_count(self):
        registry = IntentRegistry()
        # At least 15 built-in intents
        assert len(registry) >= 15

    def test_get_intent(self):
        registry = IntentRegistry()
        intent = registry.get("drop_table")
        assert intent is not None
        assert intent.category == IntentCategory.DATA_DESTRUCTION
        assert intent.severity == "critical"

    def test_list_critical(self):
        registry = IntentRegistry()
        critical = registry.list_critical()
        assert len(critical) > 0
        assert all(i.severity == "critical" for i in critical)

    def test_list_by_category(self):
        registry = IntentRegistry()
        data_intents = registry.list_by_category(IntentCategory.DATA_DESTRUCTION)
        assert len(data_intents) > 0
        assert all(i.category == IntentCategory.DATA_DESTRUCTION for i in data_intents)

    def test_register_custom(self):
        registry = IntentRegistry(intents=[])
        custom = Intent(
            name="custom_risk",
            category=IntentCategory.COMPLIANCE_RISK,
            severity="medium",
            keywords=["custom_keyword"],
        )
        registry.register(custom)
        assert registry.get("custom_risk") is custom
        assert "custom_risk" in registry

    def test_list_names(self):
        registry = IntentRegistry()
        names = registry.list_names()
        assert "drop_table" in names
        assert "execute_shell" in names


class TestRuleMatcher:
    @pytest.fixture
    def matcher(self):
        return RuleMatcher()

    def test_drop_table_keyword(self, matcher):
        matches = matcher.match("DROP TABLE users")
        assert len(matches) > 0
        assert any(m.intent.name == "drop_table" for m in matches)

    def test_delete_from_pattern(self, matcher):
        matches = matcher.match("DELETE FROM users")
        assert len(matches) > 0

    def test_rm_rf_keyword(self, matcher):
        matches = matcher.match("rm -rf /var/log")
        assert len(matches) > 0
        assert any(m.intent.name == "rm_recursive" for m in matches)

    def test_execute_shell_detection(self, matcher):
        matches = matcher.match("os.system('rm -rf /')")
        assert len(matches) > 0
        assert any(m.intent.name == "execute_shell" for m in matches)

    def test_safe_text_no_matches(self, matcher):
        matches = matcher.match("hello world, how are you?")
        assert len(matches) == 0

    def test_empty_text(self, matcher):
        matches = matcher.match("")
        assert len(matches) == 0

    def test_none_text(self, matcher):
        matches = matcher.match(None)
        assert len(matches) == 0

    def test_heuristic_delete_without_where(self, matcher):
        # "DELETE FROM table" without WHERE should trigger heuristic
        matches = matcher.match("DELETE FROM users")
        # Should match delete_all via heuristic or keyword
        assert any(
            m.intent.name == "delete_all"
            for m in matches
        )

    def test_heuristic_delete_with_where_passes(self, matcher):
        # "DELETE FROM table WHERE id=1" should NOT trigger heuristic
        matches = matcher.match("DELETE FROM users WHERE id = 1")
        delete_matches = [m for m in matches if m.intent.name == "delete_all"]
        # But keywords may still match "delete from"
        for m in delete_matches:
            # Heuristic should not fire (WHERE is present)
            assert m.match_type != "heuristic"

    def test_rest_delete_not_flagged(self, matcher):
        # REST API DELETE should not trigger SQL heuristic
        matches = matcher.match('{"method": "DELETE", "endpoint": "/api/users"}')
        # Should not have delete_all from heuristic
        heuristic_matches = [
            m for m in matches
            if m.intent.name == "delete_all" and m.match_type == "heuristic"
        ]
        assert len(heuristic_matches) == 0

    def test_filtered_intents(self, matcher):
        matches = matcher.match(
            "os.system('ls')",
            enabled_intents=["drop_table", "delete_all"],
        )
        # execute_shell not enabled, so should not match
        assert not any(m.intent.name == "execute_shell" for m in matches)

    def test_api_key_exposure(self, matcher):
        matches = matcher.match('print(api_key="sk-secret123")')
        assert any(m.intent.name == "access_secret" for m in matches)

    def test_extract_from_dict(self, matcher):
        text = matcher.extract_fields_from_output({
            "action": "execute",
            "command": "rm -rf /tmp/data",
        })
        assert "rm -rf" in text
        assert "execute" in text

    def test_extract_from_pydantic(self, matcher):
        from pydantic import BaseModel
        class Cmd(BaseModel):
            action: str
            command: str
        text = matcher.extract_fields_from_output(
            Cmd(action="exec", command="DROP TABLE data")
        )
        assert "DROP TABLE" in text


class TestSemanticGuard:
    @pytest.fixture
    def guard(self):
        return SemanticGuard()

    def test_drop_table_deny(self, guard):
        r = guard.check('DROP TABLE users')
        assert r.level == GuardLevel.DENY

    def test_safe_pass(self, guard):
        r = guard.check('{"action": "read", "message": "hello"}')
        assert r.level == GuardLevel.PASS

    def test_empty_pass(self, guard):
        r = guard.check("")
        assert r.level == GuardLevel.PASS

    def test_rm_rf_deny(self, guard):
        r = guard.check('rm -rf /etc/passwd')
        assert r.level == GuardLevel.DENY

    def test_structured_output_check(self, guard):
        r = guard.check({"query": "DROP TABLE users CASCADE"})
        assert r.level == GuardLevel.DENY

    def test_rest_delete_not_denied(self, guard):
        r = guard.check('{"endpoint": "/api/users", "method": "DELETE"}')
        assert r.level == GuardLevel.PASS

    def test_custom_intents_filter(self):
        guard = SemanticGuard(dangerous_intents=["drop_table", "truncate"])
        r = guard.check("rm -rf /tmp")  # rm_recursive not enabled
        assert r.level == GuardLevel.PASS

    def test_match_metadata(self, guard):
        r = guard.check("DROP TABLE important_data")
        assert r.metadata is not None
        assert "matched_intent" in r.metadata
        assert r.metadata["matched_intent"] == "drop_table"
        assert "matches" in r.metadata
        assert len(r.metadata["matches"]) > 0
