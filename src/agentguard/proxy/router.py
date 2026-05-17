"""LLM API route identification and response extraction.

Defines URL patterns for known LLM providers and the JSONPath-like
extraction rules to pull generated text from API responses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LLMAPIRoute:
    """A known LLM API route pattern with response extraction rules."""
    name: str
    url_pattern: str  # substring match against the request URL
    content_path: list[str]  # dot-path to extract content from response JSON
    request_content_path: list[str] | None = None  # dot-path to extract prompt from request
    method: str = "POST"


# Known LLM API providers and their response structures
BUILTIN_ROUTES: list[LLMAPIRoute] = [
    # OpenAI Chat Completions
    LLMAPIRoute(
        name="openai-chat",
        url_pattern="api.openai.com/v1/chat/completions",
        content_path=["choices", "0", "message", "content"],
        request_content_path=["messages", "-1", "content"],
    ),
    # OpenAI Completions (legacy)
    LLMAPIRoute(
        name="openai-completion",
        url_pattern="api.openai.com/v1/completions",
        content_path=["choices", "0", "text"],
    ),
    # Anthropic Messages
    LLMAPIRoute(
        name="anthropic-messages",
        url_pattern="api.anthropic.com/v1/messages",
        content_path=["content", "0", "text"],
        request_content_path=["messages", "-1", "content"],
    ),
    # Google Gemini
    LLMAPIRoute(
        name="gemini",
        url_pattern="generativelanguage.googleapis.com/v1",
        content_path=["candidates", "0", "content", "parts", "0", "text"],
    ),
    # Alibaba Tongyi Qianwen (通义千问)
    LLMAPIRoute(
        name="tongyi",
        url_pattern="dashscope.aliyuncs.com/api/v1/services/aigc/text-generation",
        content_path=["output", "text"],
    ),
    # DeepSeek
    LLMAPIRoute(
        name="deepseek-chat",
        url_pattern="api.deepseek.com/v1/chat/completions",
        content_path=["choices", "0", "message", "content"],
    ),
]

# Default route when no pattern matches — used as fallback
DEFAULT_ROUTE = LLMAPIRoute(
    name="unknown",
    url_pattern="",
    content_path=["choices", "0", "message", "content"],
)


def match_route(url: str) -> LLMAPIRoute | None:
    """Match a URL against known LLM API routes.

    Args:
        url: The full request URL (e.g., 'https://api.openai.com/v1/chat/completions').

    Returns:
        The matching LLMAPIRoute, or None if no pattern matches.
    """
    # Strip port from URL for pattern matching
    # e.g., "https://api.openai.com:8443/v1/..." -> "https://api.openai.com/v1/..."
    from urllib.parse import urlparse, urlunparse
    try:
        parsed = urlparse(url)
        clean_url = urlunparse(parsed._replace(netloc=parsed.hostname or parsed.netloc))
    except Exception:
        clean_url = url

    for route in BUILTIN_ROUTES:
        if route.url_pattern in clean_url:
            return route
    return None


def extract_content(
    body: dict[str, Any] | None,
    content_path: list[str],
) -> str | None:
    """Extract text content from a JSON response body using a dot-notated path.

    Handles numeric indices in the path (e.g., 'choices.0.message.content').

    Args:
        body: The parsed JSON response body.
        content_path: List of keys/indices to traverse (e.g., ['choices', '0', 'message', 'content']).

    Returns:
        Extracted text string, or None if path doesn't exist.
    """
    if body is None:
        return None

    current: Any = body
    for key in content_path:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(key)
        elif isinstance(current, (list, tuple)):
            try:
                idx = int(key)
                current = current[idx] if 0 <= idx < len(current) else None
            except (ValueError, IndexError):
                return None
        else:
            return None

    return str(current) if current is not None else None


def set_content(
    body: dict[str, Any],
    content_path: list[str],
    new_value: str,
) -> dict[str, Any]:
    """Set text content in a JSON response body at a given dot-notated path.

    Creates intermediate dicts/lists if they don't exist.

    Args:
        body: The parsed JSON response body.
        content_path: Path to set (e.g., ['choices', '0', 'message', 'content']).
        new_value: The new text value.

    Returns:
        The modified body.
    """
    current = body
    for i, key in enumerate(content_path[:-1]):
        if isinstance(current, dict):
            if key not in current:
                current[key] = {} if not content_path[i + 1].isdigit() else []
            current = current[key]
        elif isinstance(current, list):
            idx = int(key)
            while len(current) <= idx:
                current.append({})
            current = current[idx]

    last_key = content_path[-1]
    if isinstance(current, dict):
        current[last_key] = new_value
    elif isinstance(current, list):
        idx = int(last_key)
        while len(current) <= idx:
            current.append(None)
        current[idx] = new_value

    return body
