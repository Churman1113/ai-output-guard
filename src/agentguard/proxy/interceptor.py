"""HTTP request interceptor — forwards requests to LLM APIs and captures responses.

Acts as a transparent forward proxy for AI tools. Only intercepts requests
that match known LLM API patterns; all other requests are forwarded directly.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from agentguard import Guard
from agentguard.result import GuardLevel
from agentguard.proxy.router import match_route, extract_content
from agentguard.proxy.transformer import transform_response


# Default timeout for upstream LLM API calls (seconds)
UPSTREAM_TIMEOUT = 60.0

# Maximum response body size to buffer (10 MB)
MAX_BODY_SIZE = 10 * 1024 * 1024


class ProxyInterceptor:
    """Intercepts HTTP requests, forwards to LLM APIs, validates responses.

    Usage:
        interceptor = ProxyInterceptor()
        response = await interceptor.forward(method, url, headers, body)
    """

    def __init__(
        self,
        guard: Guard | None = None,
        timeout: float = UPSTREAM_TIMEOUT,
    ):
        self._guard = guard or Guard(semantic=True)
        self._timeout = timeout
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
        )

    async def forward(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, dict[str, str], Any]:
        """Forward an HTTP request to the upstream server and validate the response.

        Args:
            method: HTTP method (GET, POST, etc.).
            url: Full upstream URL.
            headers: Request headers (will have Host/X-Forwarded-For cleaned).
            body: Raw request body bytes.

        Returns:
            Tuple of (status_code, response_headers, response_body).
            response_body is a dict (JSON) or string (raw text).
        """
        route = match_route(url)

        # Non-LLM request — forward without guard validation
        if route is None:
            return await self._forward_direct(method, url, headers, body)

        # Extract request body as string for context
        request_text = ""
        if body:
            try:
                body_dict = json.loads(body)
                request_text = extract_content(body_dict, route.request_content_path) if route.request_content_path else ""
            except (json.JSONDecodeError, TypeError):
                request_text = body.decode("utf-8", errors="replace")[:500]

        # Forward to LLM API
        status_code, resp_headers, resp_body = await self._forward_direct(
            method, url, headers, body,
        )

        # Only validate successful responses
        if status_code != 200:
            return status_code, resp_headers, resp_body

        # Extract LLM output text from response
        output_text = None
        if isinstance(resp_body, dict):
            output_text = extract_content(resp_body, route.content_path)
        elif isinstance(resp_body, str):
            output_text = resp_body

        if not output_text:
            return status_code, resp_headers, resp_body

        # Run Guard validation
        result = self._guard.validate(output_text)

        # Transform response based on Guard result
        transformed_body, proxy_headers, new_status = transform_response(
            resp_body, route, result,
        )

        # Merge proxy headers into response headers
        resp_headers.update(proxy_headers)

        return new_status, resp_headers, transformed_body

    async def _forward_direct(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, dict[str, str], Any]:
        """Forward a request directly without guard validation."""
        # Clean hop-by-hop headers
        clean_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in (
                "host", "x-forwarded-for", "x-forwarded-proto",
                "x-forwarded-host", "via", "proxy-connection",
                "transfer-encoding", "connection",
            )
        }

        try:
            response = await self._client.request(
                method=method,
                url=url,
                headers=clean_headers,
                content=body,
            )

            # Read response body
            resp_body: Any = None
            content_type = response.headers.get("content-type", "")
            resp_bytes = await response.aread()

            if "application/json" in content_type:
                try:
                    resp_body = json.loads(resp_bytes)
                except json.JSONDecodeError:
                    resp_body = resp_bytes.decode("utf-8", errors="replace")
            else:
                resp_body = resp_bytes.decode("utf-8", errors="replace")

            # Build response headers (forward most original headers)
            resp_headers = dict(response.headers)
            # Remove transfer-encoding as we're re-serializing
            resp_headers.pop("transfer-encoding", None)
            resp_headers.pop("content-encoding", None)
            resp_headers["content-length"] = "0"  # Will be set by caller

            return response.status_code, resp_headers, resp_body

        except httpx.TimeoutException:
            return 504, {"content-type": "application/json"}, {
                "error": "Upstream LLM API timeout",
                "agentguard": {"blocked": False, "reason": "timeout"},
            }
        except httpx.RequestError as e:
            return 502, {"content-type": "application/json"}, {
                "error": f"Upstream LLM API connection error: {e}",
                "agentguard": {"blocked": False, "reason": "connection_error"},
            }

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
