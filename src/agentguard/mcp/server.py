"""MCP Server — JSON-RPC 2.0 protocol handler over stdio transport.

Implements the Model Context Protocol lifecycle:
    1. initialize  →  client learns server capabilities
    2. initialized →  client confirms ready
    3. Normal operation (tools/list, tools/call, resources/list, resources/read)
    4. Shutdown
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any

from agentguard.mcp.tools import TOOL_REGISTRY, VERSION
from agentguard.mcp.resources import RESOURCE_REGISTRY
from agentguard import Guard

# JSON-RPC 2.0 error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

# MCP server info
SERVER_NAME = "agentguard-mcp"
SERVER_VERSION = VERSION


class MCPServer:
    """MCP protocol server over stdio.

    Reads JSON-RPC 2.0 messages from stdin, dispatches to handlers,
    writes responses to stdout. Stderr is reserved for logging/debug.
    """

    def __init__(self, policy_path: str | None = None):
        self._policy_path = policy_path
        self._initialized = False
        self._guard = Guard(semantic=True, policy=policy_path)
        self._handlers = {
            "initialize": self._handle_initialize,
            "initialized": self._handle_initialized,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "shutdown": self._handle_shutdown,
        }

    # ── Lifecycle ──────────────────────────────────────────

    def run(self) -> None:
        """Start the MCP server. Reads stdin line-by-line until EOF/shutdown."""
        self._log("MCP Server starting...")
        self._log(f"Server: {SERVER_NAME} v{SERVER_VERSION}")
        if self._policy_path:
            self._log(f"Policy: {self._policy_path}")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError as e:
                self._send_error(None, PARSE_ERROR, f"Parse error: {e}")
                continue

            self._dispatch(msg)

    def _dispatch(self, msg: dict[str, Any]) -> None:
        """Route a JSON-RPC message to the correct handler."""
        msg_id = msg.get("id")
        method = msg.get("method", "")

        # Handle responses (from client back to server — rare in stdio)
        if "result" in msg or "error" in msg:
            return  # Server ignores responses in stdio transport

        # Notification (no id)
        if msg_id is None:
            if method in self._handlers:
                self._handlers[method](msg)
            return

        # Request
        if method not in self._handlers:
            self._send_error(msg_id, METHOD_NOT_FOUND, f"Unknown method: {method}")
            return

        try:
            params = msg.get("params", {})
            result = self._handlers[method](params)
            self._send_result(msg_id, result)
        except Exception as e:
            self._log(f"Error handling {method}: {traceback.format_exc()}")
            self._send_error(msg_id, INTERNAL_ERROR, str(e))

    # ── Handlers ───────────────────────────────────────────

    def _handle_initialize(self, params: dict) -> dict:
        """Respond with server capabilities."""
        self._log("Handling initialize...")
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
            },
            "serverInfo": {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
            },
        }

    def _handle_initialized(self, msg: dict) -> None:
        """Client confirms initialization complete."""
        self._initialized = True
        self._log("Client initialized — ready for requests")

    def _handle_tools_list(self, params: dict) -> dict:
        """List available MCP Tools."""
        tools = []
        for name, tool in TOOL_REGISTRY.items():
            tools.append({
                "name": name,
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            })
        return {"tools": tools}

    def _handle_tools_call(self, params: dict) -> dict:
        """Execute a MCP Tool."""
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        if tool_name not in TOOL_REGISTRY:
            raise ValueError(f"Unknown tool: {tool_name}")

        handler = TOOL_REGISTRY[tool_name]["handler"]
        result = handler(tool_args, self._policy_path, self._guard)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, indent=2),
                }
            ]
        }

    def _handle_resources_list(self, params: dict) -> dict:
        """List available MCP Resources."""
        resources = []
        for name, resource in RESOURCE_REGISTRY.items():
            resources.append({
                "uri": resource["uri"],
                "name": name,
                "description": resource["description"],
                "mimeType": resource.get("mimeType", "text/plain"),
            })
        return {"resources": resources}

    def _handle_resources_read(self, params: dict) -> dict:
        """Read a MCP Resource."""
        uri = params.get("uri", "")

        for name, resource in RESOURCE_REGISTRY.items():
            if resource["uri"] == uri:
                handler = resource["handler"]
                content = handler(self._policy_path)
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": resource.get("mimeType", "text/plain"),
                            "text": content,
                        }
                    ]
                }

        raise ValueError(f"Unknown resource: {uri}")

    def _handle_shutdown(self, params: dict) -> dict:
        """Handle shutdown request."""
        self._log("Shutting down...")
        return {}

    # ── Transport ──────────────────────────────────────────

    def _send_result(self, msg_id: Any, result: Any) -> None:
        """Send a JSON-RPC success response."""
        response = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": result,
        }
        self._write(response)

    def _send_error(self, msg_id: Any, code: int, message: str) -> None:
        """Send a JSON-RPC error response."""
        response = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": code,
                "message": message,
            },
        }
        self._write(response)

    def _write(self, data: dict) -> None:
        """Write a JSON-RPC message to stdout."""
        line = json.dumps(data, ensure_ascii=False)
        sys.stdout.write(line + "\n")
        sys.stdout.flush()

    @staticmethod
    def _log(msg: str) -> None:
        """Log to stderr (never to stdout — that's the protocol channel)."""
        print(f"[agentguard-mcp] {msg}", file=sys.stderr, flush=True)


def main():
    """Entry point for the agentguard-mcp command.
    
    Reads AGENTGUARD_POLICY from environment variable for policy path.
    """
    import os
    policy_path = os.environ.get("AGENTGUARD_POLICY")
    server = MCPServer(policy_path=policy_path)
    server.run()
