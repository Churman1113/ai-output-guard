"""Dashboard backend — serves the Vue 3 frontend and AI Output Guard API.

Usage:
    # Development (frontend on port 3000, API on port 8765)
    python -m dashboard.backend.main

    # Production (single port, serves both frontend and API)
    AGENTGUARD_PORT=3000 python -m dashboard.backend.main
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from agentguard.api import create_app as create_guard_api


def create_app() -> FastAPI:
    """Create the dashboard FastAPI application with static file serving."""
    # Create the Guard API app
    policy_path = os.environ.get("AGENTGUARD_POLICY")
    app = create_guard_api(policy_path=policy_path)

    # Serve Vue 3 static files in production
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")

    return app


app = create_app()


def main():
    """Start the dashboard server."""
    import uvicorn

    host = os.environ.get("AGENTGUARD_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENTGUARD_PORT", "8765"))

    print(f"[ai-output-guard-dashboard] Starting on http://{host}:{port}", file=sys.stderr)
    uvicorn.run(
        "dashboard.backend.main:app",
        host=host,
        port=port,
        log_level="info",
        reload=True,
    )


if __name__ == "__main__":
    main()
