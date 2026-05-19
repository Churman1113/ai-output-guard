"""MCP (Model Context Protocol) Server for AgentGuard.

Implements JSON-RPC 2.0 over stdio transport, exposing AgentGuard
as MCP Tools and Resources for AI IDEs (Cursor, Copilot, Claude Code, etc.).
"""

from agentguard.mcp.server import MCPServer

__all__ = ["MCPServer"]
