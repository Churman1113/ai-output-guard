"""Tests for the API Proxy router module — LLM API route identification."""
import json
import pytest
from agentguard.proxy.router import (
    match_route, extract_content, set_content, LLMAPIRoute, BUILTIN_ROUTES,
)


class TestMatchRoute:
    def test_openai_chat_match(self):
        route = match_route("https://api.openai.com/v1/chat/completions")
        assert route is not None
        assert route.name == "openai-chat"

    def test_anthropic_match(self):
        route = match_route("https://api.anthropic.com/v1/messages")
        assert route is not None
        assert route.name == "anthropic-messages"

    def test_deepseek_match(self):
        route = match_route("https://api.deepseek.com/v1/chat/completions")
        assert route is not None
        assert route.name == "deepseek-chat"

    def test_gemini_match(self):
        route = match_route("https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent")
        assert route is not None
        assert route.name == "gemini"

    def test_tongyi_match(self):
        route = match_route("https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation")
        assert route is not None
        assert route.name == "tongyi"

    def test_no_match(self):
        route = match_route("https://api.github.com/repos")
        assert route is None

    def test_no_match_plain_text(self):
        route = match_route("https://example.com")
        assert route is None

    def test_unknown_port_still_matches(self):
        route = match_route("https://api.openai.com:8443/v1/chat/completions")
        assert route is not None
        assert route.name == "openai-chat"

    def test_all_providers_covered(self):
        """Ensure we have routes for all major providers."""
        names = {r.name for r in BUILTIN_ROUTES}
        assert "openai-chat" in names
        assert "openai-completion" in names
        assert "anthropic-messages" in names
        assert "gemini" in names
        assert "tongyi" in names
        assert "deepseek-chat" in names


class TestExtractContent:
    def test_openai_chat(self):
        body = {
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello, how can I help?",
                    },
                }
            ],
        }
        result = extract_content(body, ["choices", "0", "message", "content"])
        assert result == "Hello, how can I help?"

    def test_openai_completion(self):
        body = {
            "choices": [
                {"index": 0, "text": "Once upon a time..."},
            ],
        }
        result = extract_content(body, ["choices", "0", "text"])
        assert result == "Once upon a time..."

    def test_anthropic_messages(self):
        body = {
            "content": [
                {"type": "text", "text": "Sure, I can help with that."},
            ],
        }
        result = extract_content(body, ["content", "0", "text"])
        assert result == "Sure, I can help with that."

    def test_none_body(self):
        result = extract_content(None, ["choices", "0", "text"])
        assert result is None

    def test_missing_path(self):
        result = extract_content({"hello": "world"}, ["nonexistent", "path"])
        assert result is None

    def test_empty_body(self):
        result = extract_content({}, ["choices", "0", "text"])
        assert result is None

    def test_deep_nested(self):
        body = {"a": {"b": {"c": {"d": "deep value"}}}}
        result = extract_content(body, ["a", "b", "c", "d"])
        assert result == "deep value"

    def test_non_dict_intermediate(self):
        body = {"a": "string_not_dict"}
        result = extract_content(body, ["a", "b"])
        assert result is None

    def test_out_of_range_index(self):
        body = {"choices": []}
        result = extract_content(body, ["choices", "0", "text"])
        assert result is None

    def test_numeric_value(self):
        body = {"data": {"count": 42}}
        result = extract_content(body, ["data", "count"])
        assert result == "42"  # Should convert to string


class TestSetContent:
    def test_set_openai_chat(self):
        body = {
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": "original"}},
            ],
        }
        result = set_content(body, ["choices", "0", "message", "content"], "modified")
        assert result["choices"][0]["message"]["content"] == "modified"

    def test_set_nested_dict(self):
        body = {"a": {"b": {"c": "old"}}}
        result = set_content(body, ["a", "b", "c"], "new")
        assert result["a"]["b"]["c"] == "new"

    def test_create_intermediate(self):
        body = {}
        result = set_content(body, ["a", "b", "c"], "value")
        assert result["a"]["b"]["c"] == "value"

    def test_set_anthropic(self):
        body = {"content": [{"type": "text", "text": "original"}]}
        result = set_content(body, ["content", "0", "text"], "safe response")
        assert result["content"][0]["text"] == "safe response"
