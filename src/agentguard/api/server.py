"""Entry point for the agentguard-daemon command.

Starts the AgentGuard HTTP API server. Reads AGENTGUARD_POLICY from
the environment variable for the policy file path.
"""

from __future__ import annotations

import os
import sys


def main():
    """Start the AgentGuard HTTP API daemon."""
    import uvicorn

    policy_path = os.environ.get("AGENTGUARD_POLICY")
    host = os.environ.get("AGENTGUARD_HOST", "127.0.0.1")
    port = int(os.environ.get("AGENTGUARD_PORT", "8765"))

    if policy_path:
        print(f"[agentguard-daemon] Loading policy: {policy_path}", file=sys.stderr)
    print(f"[agentguard-daemon] Starting on {host}:{port}", file=sys.stderr)

    uvicorn.run(
        "agentguard.api:create_app",
        host=host,
        port=port,
        factory=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
