"""AgentGuard HTTP API — FastAPI sub-application.

Provides a REST API for the guard engine, enabling non-Python clients
(notably the TypeScript LSP Server) to invoke guard validation over HTTP.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI

from agentguard import Guard


def create_app(policy_path: Optional[str] = None) -> FastAPI:
    """Create a FastAPI application with a shared Guard instance.

    Args:
        policy_path: Optional path to a YAML policy file. If not provided,
                     the guard runs with semantic-only mode.

    Returns:
        Configured FastAPI application ready to serve.
    """
    app = FastAPI(
        title="AgentGuard API",
        description="AI output safety middleware — HTTP API for guard validation",
        version="0.1.0",
    )

    # Shared guard instance — audit logs persist across requests
    app.state.guard = Guard(semantic=True, policy=policy_path)
    app.state.policy_path = policy_path

    # Register routes (lazy import to avoid circular deps)
    from agentguard.api.routes import router
    app.include_router(router, prefix="/api/v1")

    return app
