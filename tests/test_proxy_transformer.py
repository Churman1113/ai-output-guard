"""Tests for the API Proxy transformer — response modification based on Guard results."""
import json
from typing import Optional

import pytest

from agentguard.result import GuardLevel, GuardResult, CheckResult
from agentguard.proxy.router import LLMAPIRoute
from agentguard.proxy.transformer import (
    transform_response, HEADER_BLOCKED, HEADER_FIX, HEADER_WARNING,
    HEADER_AUDIT_ID, HEADER_LATENCY, HEADER_LEVEL,
)


OPENAI_ROUTE = LLMAPIRoute(
    name="openai-chat",
    url_pattern="api.openai.com/v1/chat/completions",
    content_path=["choices", "0", "message", "content"],
)

ANTHROPIC_ROUTE = LLMAPIRoute(
    name="anthropic-messages",
    url_pattern="api.anthropic.com/v1/messages",
    content_path=["content", "0", "text"],
)


def _make_check(layer: str, level: GuardLevel, message: str) -> CheckResult:
    return CheckResult(layer=layer, level=level, message=message, confidence=1.0)


def _make_result(level: GuardLevel, blocked_by: Optional[str] = None,
                 output: Optional[str] = None) -> GuardResult:
    checks = [_make_check(blocked_by or "schema", level, f"Test {level.value}")]
    result = GuardResult(
        level=level,
        output=output,
        checks=checks,
        blocked_by=blocked_by,
        metadata={"latency_ms": 5.2},
    )
    # Set audit_id manually since guard.py normally does this
    object.__setattr__(result, "audit_id", "ag-test123")
    return result


class TestTransformPass:
    def test_pass_returns_original(self):
        body = {"choices": [{"message": {"content": "Hello"}}]}
        result = _make_result(GuardLevel.PASS)
        transformed, headers, status = transform_response(body, OPENAI_ROUTE, result)
        assert status == 200
        assert transformed == body
        assert headers[HEADER_LEVEL] == "pass"
        assert HEADER_BLOCKED not in headers

    def test_pass_string_body(self):
        body_str = "plain text response"
        result = _make_result(GuardLevel.PASS)
        transformed, headers, status = transform_response(body_str, OPENAI_ROUTE, result)
        assert status == 200
        assert transformed == body_str


class TestTransformFix:
    def test_fix_replaces_content(self):
        body = {"choices": [{"message": {"content": "original"}}]}
        result = _make_result(GuardLevel.FIX, output='{"fixed": "output"}')
        transformed, headers, status = transform_response(body, OPENAI_ROUTE, result)
        assert status == 200
        assert headers[HEADER_FIX] == "true"
        assert headers[HEADER_LEVEL] == "fix"

    def test_fix_without_output_returns_original(self):
        body = {"choices": [{"message": {"content": "original"}}]}
        result = _make_result(GuardLevel.FIX, output=None)
        transformed, headers, status = transform_response(body, OPENAI_ROUTE, result)
        assert status == 200
        assert transformed == body


class TestTransformWarn:
    def test_warn_passes_through_with_headers(self):
        body = {"choices": [{"message": {"content": "potentially risky"}}]}
        result = _make_result(GuardLevel.WARN, blocked_by="semantic")
        result.checks = [_make_check("semantic", GuardLevel.WARN, "Risky content detected")]
        transformed, headers, status = transform_response(body, OPENAI_ROUTE, result)
        assert status == 200
        assert transformed == body  # Pass through unchanged
        assert HEADER_WARNING in headers
        assert HEADER_BLOCKED in headers
        assert headers[HEADER_BLOCKED] == "semantic"

    def test_warn_contains_warning_message(self):
        body = {"choices": [{"message": {"content": "test"}}]}
        result = _make_result(GuardLevel.WARN, blocked_by="policy")
        result.checks = [_make_check("policy", GuardLevel.WARN, "Policy warning: large response")]
        transformed, headers, status = transform_response(body, OPENAI_ROUTE, result)
        assert "large response" in headers[HEADER_WARNING]


class TestTransformDeny:
    def test_deny_replaces_content_with_safety_message(self):
        body = {"choices": [{"message": {"content": "DROP TABLE users"}}]}
        result = _make_result(GuardLevel.DENY, blocked_by="semantic")
        transformed, headers, status = transform_response(body, OPENAI_ROUTE, result)
        assert status == 200
        assert HEADER_BLOCKED in headers
        assert headers[HEADER_BLOCKED] == "semantic"
        assert headers[HEADER_LEVEL] == "deny"
        # Content should be replaced with safety message
        content = transformed["choices"][0]["message"]["content"]
        assert "AgentGuard" in content
        assert "blocked" in content

    def test_deny_anthropic_format(self):
        body = {"content": [{"type": "text", "text": "dangerous output"}]}
        result = _make_result(GuardLevel.DENY, blocked_by="policy")
        transformed, headers, status = transform_response(body, ANTHROPIC_ROUTE, result)
        assert status == 200
        content = transformed["content"][0]["text"]
        assert "AgentGuard" in content

    def test_deny_non_json_body(self):
        body_str = "raw text response"
        result = _make_result(GuardLevel.DENY, blocked_by="semantic")
        transformed, headers, status = transform_response(body_str, OPENAI_ROUTE, result)
        assert status == 200
        # Non-JSON body should get wrapped in a chat completion format
        assert isinstance(transformed, dict)
        assert "choices" in transformed


class TestTransformAskHuman:
    def test_ask_human_returns_202(self):
        body = {"choices": [{"message": {"content": "deploy to production"}}]}
        result = _make_result(GuardLevel.ASK_HUMAN, blocked_by="policy")
        result.checks = [_make_check("policy", GuardLevel.ASK_HUMAN, "Production deploy needs approval")]
        transformed, headers, status = transform_response(body, OPENAI_ROUTE, result)
        assert status == 202
        assert transformed["status"] == "requires_approval"
        assert "audit_id" in transformed
        assert "agentguard" in transformed

    def test_ask_human_includes_check_details(self):
        body = {"choices": [{"message": {"content": "deploy"}}]}
        result = _make_result(GuardLevel.ASK_HUMAN, blocked_by="policy")
        result.checks = [_make_check("policy", GuardLevel.ASK_HUMAN, "Needs review")]
        transformed, headers, status = transform_response(body, OPENAI_ROUTE, result)
        assert len(transformed["agentguard"]["checks"]) == 1
        assert transformed["agentguard"]["checks"][0]["layer"] == "policy"


class TestTransformHeaders:
    def test_all_results_have_audit_id(self):
        body = {"choices": [{"message": {"content": "test"}}]}
        for level in [GuardLevel.PASS, GuardLevel.WARN, GuardLevel.DENY]:
            result = _make_result(level)
            _, headers, _ = transform_response(body, OPENAI_ROUTE, result)
            assert HEADER_AUDIT_ID in headers
            assert headers[HEADER_AUDIT_ID] == "ag-test123"

    def test_all_results_have_latency(self):
        body = {"choices": [{"message": {"content": "test"}}]}
        result = _make_result(GuardLevel.PASS)
        _, headers, _ = transform_response(body, OPENAI_ROUTE, result)
        assert HEADER_LATENCY in headers
        assert float(headers[HEADER_LATENCY]) > 0
