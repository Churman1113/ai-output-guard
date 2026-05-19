"""API Proxy — zero-intrusion safety layer for LLM API calls.

Acts as a transparent HTTP forward proxy. AI tools point their HTTP_PROXY
to this server, and all LLM API calls are automatically intercepted,
validated by AgentGuard, and either passed through, modified, or blocked.

Usage:
    # Docker (recommended)
    docker run -p 8080:8080 -e AGENTGUARD_POLICY=/policies/prod.yaml agentguard/proxy

    # Python
    python -m agentguard.proxy.server

    # Client side (AI tool)
    export HTTP_PROXY=http://localhost:8080
    export HTTPS_PROXY=http://localhost:8080
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from agentguard import Guard
from agentguard.proxy.interceptor import ProxyInterceptor


def create_app(
    policy_path: str | None = None,
    guard: Guard | None = None,
) -> FastAPI:
    """Create the API Proxy FastAPI application.

    Args:
        policy_path: Optional path to a YAML policy file.
        guard: Optional pre-configured Guard instance. If not provided,
               one is created with semantic checking enabled.

    Returns:
        Configured FastAPI application.
    """
    # Shared interceptor (persists guard state and audit logs)
    if guard is None:
        guard = Guard(semantic=True, policy=policy_path)
    interceptor = ProxyInterceptor(guard=guard)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Startup and shutdown lifecycle."""
        try:
            yield
        finally:
            await interceptor.close()

    app = FastAPI(
        title="AgentGuard API Proxy",
        description="Zero-intrusion safety proxy for LLM API calls",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.interceptor = interceptor
    app.state.policy_path = policy_path

    # ── Health check ──

    @app.get("/health")
    @app.head("/health")
    async def health():
        return {
            "status": "healthy",
            "server": "agentguard-proxy",
            "version": "0.1.0",
            "policy": policy_path or "none (semantic only)",
            "audit_entries": guard.audit_log.count,
        }

    # ── Catch-all proxy handler ──

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    async def proxy_handler(request: Request, path: str) -> Response:
        """Catch-all handler that proxies requests to LLM APIs."""
        url = str(request.url)
        method = request.method
        body = await request.body()
        headers = dict(request.headers)

        status_code, resp_headers, resp_body = await interceptor.forward(
            method=method,
            url=url,
            headers=headers,
            body=body,
        )

        if isinstance(resp_body, dict):
            content_type = resp_headers.get("content-type", "application/json")
            if "json" in content_type:
                body_bytes = __import__("json").dumps(resp_body, ensure_ascii=False).encode("utf-8")
            else:
                body_bytes = str(resp_body).encode("utf-8")
        elif isinstance(resp_body, str):
            body_bytes = resp_body.encode("utf-8")
        else:
            body_bytes = str(resp_body).encode("utf-8")

        response = Response(
            content=body_bytes,
            status_code=status_code,
            headers={
                k: str(v) for k, v in resp_headers.items()
                if k.lower() not in ("content-length", "content-encoding", "transfer-encoding")
            },
            media_type=resp_headers.get("content-type", "application/json"),
        )
        response.headers["content-length"] = str(len(body_bytes))
        return response

    return app


# Entry point
app = create_app()


def main():
    """Start the API Proxy server."""
    import uvicorn

    policy_path = os.environ.get("AGENTGUARD_POLICY")
    host = os.environ.get("AGENTGUARD_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENTGUARD_PORT", "8080"))

    if policy_path:
        print(f"[agentguard-proxy] Policy: {policy_path}", file=sys.stderr)
    print(f"[agentguard-proxy] Listening on {host}:{port}", file=sys.stderr)
    print(f"[agentguard-proxy] Set HTTP_PROXY=http://{host}:{port} in your AI tools", file=sys.stderr)

    uvicorn.run(
        "agentguard.proxy.server:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
