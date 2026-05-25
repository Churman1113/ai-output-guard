"""MCP (Model Context Protocol) Server for AI Output Guard.

Implements JSON-RPC 2.0 over stdio transport, exposing AI Output Guard
as MCP Tools and Resources for AI IDEs (Cursor, Copilot, Claude Code, etc.).
"""

from agentguard.mcp.server import MCPServer

__all__ = ["MCPServer"]
