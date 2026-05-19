"""Tests for the MCP Server — JSON-RPC 2.0 protocol handling and tool execution."""

from __future__ import annotations

import json
import io
import sys
import time
from pathlib import Path

import pytest

from agentguard.mcp.server import MCPServer
from agentguard.mcp.tools import TOOL_REGISTRY, VERSION


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def server():
    """Create a fresh MCP server (not started — manual dispatch)."""
    return MCPServer()


@pytest.fixture
def capture_stdio():
    """Capture stdout during server operations."""
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    yield sys.stdout
    sys.stdout = old_stdout


@pytest.fixture
def policy_dir(tmp_path):
    """Create a temp directory with sample policy files."""
    (tmp_path / "prod.yaml").write_text("""
version: "1.0"
rules:
  - name: allow-read
    condition:
      field: action
      operator: equals
      value: read
    action: allow
""")
    (tmp_path / "staging.yaml").write_text("""
version: "1.0"
rules:
  - name: deny-delete
    condition:
      field: action
      operator: equals
      value: delete
    action: deny
  - name: warn-write
    condition:
      field: action
      operator: equals
      value: write
    action: warn
""")
    (tmp_path / "broken.yaml").write_text("not: valid: yaml: [")
    return tmp_path


# ── JSON-RPC Protocol Tests ───────────────────────────────

class TestMCPProtocol:
    """Test the JSON-RPC 2.0 protocol layer."""

    def test_initialize_returns_capabilities(self, server):
        result = server._handle_initialize({})
        assert result["protocolVersion"] == "2024-11-05"
        assert "capabilities" in result
        assert "tools" in result["capabilities"]
        assert "resources" in result["capabilities"]
        assert result["serverInfo"]["name"] == "agentguard-mcp"
        # Version should come from tools.VERSION
        assert result["serverInfo"]["version"] == VERSION

    def test_initialized_sets_flag(self, server):
        server._handle_initialized({})
        assert server._initialized is True

    def test_tools_list_returns_all_tools(self, server):
        result = server._handle_tools_list({})
        tools = result["tools"]
        tool_names = {t["name"] for t in tools}
        assert tool_names == set(TOOL_REGISTRY.keys())
        # Verify new P0 tools are present
        assert "guard_fix" in tool_names
        assert "guard_reload_policy" in tool_names
        assert "guard_list_policies" in tool_names
        for tool in tools:
            assert "description" in tool
            assert "inputSchema" in tool

    def test_tools_list_count(self, server):
        result = server._handle_tools_list({})
        # Original 5 + 3 new P0 tools = 8
        assert len(result["tools"]) == 8

    def test_resources_list_returns_all_resources(self, server):
        result = server._handle_resources_list({})
        resources = result["resources"]
        resource_uris = {r["uri"] for r in resources}
        assert "agentguard://policy" in resource_uris
        assert "agentguard://stats" in resource_uris

    def test_unknown_method_raises(self, server, capture_stdio):
        with pytest.raises(Exception):
            server._handle_tools_call({"name": "nonexistent_tool", "arguments": {}})

    def test_shutdown_handled(self, server):
        result = server._handle_shutdown({})
        assert result == {}


# ── Tool Execution Tests ──────────────────────────────────

class TestToolExecution:
    """Test each MCP tool's handler function."""

    # ── guard_validate ──

    def test_guard_validate_safe_output(self):
        from agentguard.mcp.tools import tool_guard_validate
        result = tool_guard_validate({"output": '{"action": "read", "target": "users"}'})
        assert result["passed"] is True
        assert result["blocked"] is False
        assert "checks" in result

    def test_guard_validate_dangerous_output(self):
        from agentguard.mcp.tools import tool_guard_validate
        result = tool_guard_validate({"output": "DROP TABLE users; DELETE FROM accounts;"})
        assert result["blocked"] is True
        assert result["blocked_by"] == "semantic"
        assert result["level"] == "deny"

    def test_guard_validate_with_context(self):
        from agentguard.mcp.tools import tool_guard_validate
        result = tool_guard_validate({
            "output": "read",
            "context": {"source": "cursor-ide", "file": "main.py"},
        })
        assert "context" in result
        assert result["context"]["source"] == "cursor-ide"

    # ── guard_set_policy ──

    def test_guard_set_policy_valid(self):
        from agentguard.mcp.tools import tool_guard_set_policy
        result = tool_guard_set_policy({
            "policy": """
version: "1.0"
rules:
  - name: test-rule
    condition:
      field: action
      operator: equals
      value: read
    action: allow
"""
        })
        assert result["status"] == "ok"
        assert result["rules_loaded"] == 1

    def test_guard_set_policy_invalid(self):
        from agentguard.mcp.tools import tool_guard_set_policy
        result = tool_guard_set_policy({
            "policy": """
rules:
  - name: bad-rule
"""
        })
        assert result["status"] == "error"

    # ── guard_get_audit ──

    def test_guard_get_audit_empty(self):
        from agentguard.mcp.tools import tool_guard_get_audit
        result = tool_guard_get_audit({"limit": 5})
        assert "total" in result
        assert "entries" in result
        assert result["shown"] == 0

    def test_guard_get_audit_after_validation(self):
        from agentguard.mcp.tools import tool_guard_validate, tool_guard_get_audit
        from agentguard import Guard
        shared_guard = Guard(semantic=True)
        tool_guard_validate({"output": '{"action": "read"}'}, shared_guard=shared_guard)
        result = tool_guard_get_audit({"limit": 10}, shared_guard=shared_guard)
        assert result["total"] >= 1

    def test_guard_get_audit_pagination_offset(self):
        from agentguard.mcp.tools import tool_guard_validate, tool_guard_get_audit
        from agentguard import Guard
        shared_guard = Guard(semantic=True)
        # Create 3 entries
        for i in range(3):
            tool_guard_validate({"output": f'test-{i}'}, shared_guard=shared_guard)

        result = tool_guard_get_audit({"limit": 2, "offset": 1}, shared_guard=shared_guard)
        assert result["offset"] == 1
        assert result["shown"] == 2
        # matched should be >= 3
        assert result["matched"] >= 3

    def test_guard_get_audit_time_range(self):
        from agentguard.mcp.tools import tool_guard_validate, tool_guard_get_audit
        from agentguard import Guard
        shared_guard = Guard(semantic=True)

        before = time.time()
        tool_guard_validate({"output": "test-time-filter"}, shared_guard=shared_guard)
        after = time.time()

        # Filter to entries after 'before'
        result = tool_guard_get_audit({"from_time": before}, shared_guard=shared_guard)
        assert result["matched"] >= 1

        # Filter with to_time before the event should match 0
        result_before = tool_guard_get_audit({"to_time": before - 1}, shared_guard=shared_guard)
        assert result_before["matched"] == 0

    def test_guard_get_audit_iso_time_field(self):
        from agentguard.mcp.tools import tool_guard_validate, tool_guard_get_audit
        from agentguard import Guard
        shared_guard = Guard(semantic=True)
        tool_guard_validate({"output": "test-iso"}, shared_guard=shared_guard)
        result = tool_guard_get_audit({"limit": 1}, shared_guard=shared_guard)
        if result["entries"]:
            entry = result["entries"][0]
            assert "iso_time" in entry
            assert "T" in entry["iso_time"]  # ISO 8601 format

    def test_guard_get_audit_level_filter(self):
        from agentguard.mcp.tools import tool_guard_validate, tool_guard_get_audit
        from agentguard import Guard
        shared_guard = Guard(semantic=True)
        tool_guard_validate({"output": '{"action": "read"}'}, shared_guard=shared_guard)
        tool_guard_validate({"output": "DROP TABLE users;"}, shared_guard=shared_guard)

        result = tool_guard_get_audit({"level": "deny"}, shared_guard=shared_guard)
        assert result["matched"] >= 1
        for entry in result["entries"]:
            assert entry["result"] == "deny"

    def test_guard_get_audit_respects_limit(self):
        from agentguard.mcp.tools import tool_guard_validate, tool_guard_get_audit
        from agentguard import Guard
        shared_guard = Guard(semantic=True)
        for i in range(10):
            tool_guard_validate({"output": f'test-{i}'}, shared_guard=shared_guard)

        result = tool_guard_get_audit({"limit": 3}, shared_guard=shared_guard)
        assert result["shown"] == 3

    # ── guard_status ──

    def test_guard_status(self):
        from agentguard.mcp.tools import tool_guard_status
        result = tool_guard_status({})
        assert result["server"] == "agentguard-mcp"
        assert result["version"] == VERSION
        assert "layers" in result
        assert "config" in result
        assert "audit_entries" in result
        assert result["layers"]["semantic"] is True

    # ── guard_add_intent ──

    def test_guard_add_intent(self):
        from agentguard.mcp.tools import tool_guard_add_intent
        result = tool_guard_add_intent({
            "name": "test_custom_intent",
            "patterns": ["hack_the_planet", "disable_security"],
            "severity": "critical",
        })
        assert result["status"] == "ok"
        assert result["intent"]["name"] == "test_custom_intent"

    def test_guard_add_intent_missing_name(self):
        from agentguard.mcp.tools import tool_guard_add_intent
        result = tool_guard_add_intent({"patterns": ["test"]})
        assert result["status"] == "error"


# ── guard_fix Tool Tests (P0: Code Action Support) ───────

class TestGuardFix:
    """Test the guard_fix tool for schema repair and fix suggestions."""

    SIMPLE_SCHEMA = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["read", "write", "delete"]},
            "target": {"type": "string"},
            "priority": {"type": "integer"},
        },
        "required": ["action", "target"],
    }

    def test_fix_auto_missing_required_fills_defaults(self):
        """Auto mode: missing required fields should be filled."""
        from agentguard.mcp.tools import tool_guard_fix
        result = tool_guard_fix({
            "output": '{"action": "read"}',
            "expected_schema": self.SIMPLE_SCHEMA,
            "fix_mode": "auto",
        })
        assert result["fixes_applied"] is True
        assert result["fix_mode"] == "auto"
        output = json.loads(result["output"])
        assert "target" in output  # Required field filled

    def test_fix_auto_enum_correction(self):
        """Auto mode: invalid enum value should be fuzzy-matched."""
        from agentguard.mcp.tools import tool_guard_fix
        result = tool_guard_fix({
            "output": '{"action": "reed", "target": "users"}',
            "expected_schema": self.SIMPLE_SCHEMA,
            "fix_mode": "auto",
        })
        assert result["fixes_applied"] is True
        output = json.loads(result["output"])
        assert output["action"] == "read"  # "reed" → "read"

    def test_fix_auto_type_coercion(self):
        """Auto mode: string integer should be coerced to int."""
        schema_with_int = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
        }
        from agentguard.mcp.tools import tool_guard_fix
        result = tool_guard_fix({
            "output": '{"count": "42"}',
            "expected_schema": schema_with_int,
            "fix_mode": "auto",
        })
        assert result["fixes_applied"] is True
        output = json.loads(result["output"])
        assert output["count"] == 42

    def test_fix_suggest_does_not_modify(self):
        """Suggest mode: returns suggestions without modifying output."""
        from agentguard.mcp.tools import tool_guard_fix
        result = tool_guard_fix({
            "output": '{"action": "reed", "target": "users"}',
            "expected_schema": self.SIMPLE_SCHEMA,
            "fix_mode": "suggest",
        })
        # Output should be unchanged in suggest mode
        output = json.loads(result["output"])
        assert output["action"] == "reed"  # Not fixed
        assert len(result["fix_log"]) >= 1

    def test_fix_strict_strips_unknown_fields(self):
        """Strict mode: unknown fields should be stripped."""
        from agentguard.mcp.tools import tool_guard_fix
        result = tool_guard_fix({
            "output": '{"action": "read", "target": "users", "extra_field": "should-be-removed"}',
            "expected_schema": self.SIMPLE_SCHEMA,
            "fix_mode": "strict",
        })
        output = json.loads(result["output"])
        assert "extra_field" not in output
        assert "action" in output
        assert "target" in output

    def test_fix_no_schema_falls_back_to_guard(self):
        """Without schema: should run guard validation and return fix hints."""
        from agentguard.mcp.tools import tool_guard_fix
        result = tool_guard_fix({
            "output": "DROP TABLE users; DELETE FROM accounts;",
            "fix_mode": "auto",
        })
        # Should have semantic-level fix hints
        assert "fix_log" in result
        # Semantic guard should catch this
        has_semantic_hint = any(
            entry.get("layer") == "semantic" for entry in result["fix_log"]
        )
        assert has_semantic_hint

    def test_fix_invalid_fix_mode_defaults_to_auto(self):
        """Invalid fix_mode should default to 'auto'."""
        from agentguard.mcp.tools import tool_guard_fix
        result = tool_guard_fix({
            "output": '{"action": "read"}',
            "expected_schema": self.SIMPLE_SCHEMA,
            "fix_mode": "invalid_mode",
        })
        assert result["fix_mode"] == "auto"

    def test_fix_non_json_output(self):
        """Non-JSON output with schema should report parse error."""
        from agentguard.mcp.tools import tool_guard_fix
        result = tool_guard_fix({
            "output": "not valid json {{{",
            "expected_schema": self.SIMPLE_SCHEMA,
            "fix_mode": "auto",
        })
        assert len(result["fix_log"]) >= 1
        assert any("JSON" in entry.get("error", "") for entry in result["fix_log"])

    def test_fix_clean_output_no_changes(self):
        """Clean valid output should have no fixes applied."""
        from agentguard.mcp.tools import tool_guard_fix
        result = tool_guard_fix({
            "output": '{"action": "read", "target": "users", "priority": 1}',
            "expected_schema": self.SIMPLE_SCHEMA,
            "fix_mode": "auto",
        })
        assert result["fixes_applied"] is False


# ── guard_reload_policy Tests (P0: Hot Reload) ───────────

class TestGuardReloadPolicy:
    """Test the guard_reload_policy tool for hot-reloading policies."""

    def test_reload_valid_policy(self, policy_dir):
        from agentguard.mcp.tools import tool_guard_reload_policy
        result = tool_guard_reload_policy({
            "policy_path": str(policy_dir / "prod.yaml"),
        })
        assert result["status"] == "ok"
        assert result["rules"] == 1
        assert "prod.yaml" in result["policy_path"]

    def test_reload_multi_rule_policy(self, policy_dir):
        from agentguard.mcp.tools import tool_guard_reload_policy
        result = tool_guard_reload_policy({
            "policy_path": str(policy_dir / "staging.yaml"),
        })
        assert result["status"] == "ok"
        assert result["rules"] == 2
        assert result["version"] == "1.0"

    def test_reload_missing_file(self):
        from agentguard.mcp.tools import tool_guard_reload_policy
        result = tool_guard_reload_policy({
            "policy_path": "/nonexistent/policy.yaml",
        })
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_reload_no_path_provided(self):
        from agentguard.mcp.tools import tool_guard_reload_policy
        result = tool_guard_reload_policy({})
        assert result["status"] == "error"
        assert "No policy path" in result["message"]


# ── guard_list_policies Tests (P0: Policy Discovery) ─────

class TestGuardListPolicies:
    """Test the guard_list_policies tool for scanning policy files."""

    def test_list_policies_in_directory(self, policy_dir):
        from agentguard.mcp.tools import tool_guard_list_policies
        result = tool_guard_list_policies({
            "directory": str(policy_dir),
        })
        assert result["status"] == "ok"
        assert result["count"] >= 2  # prod.yaml + staging.yaml

        names = {p["name"] for p in result["policies"]}
        assert "prod" in names
        assert "staging" in names

    def test_list_policies_includes_rules_count(self, policy_dir):
        from agentguard.mcp.tools import tool_guard_list_policies
        result = tool_guard_list_policies({
            "directory": str(policy_dir),
        })
        for p in result["policies"]:
            if p["name"] == "prod":
                assert p["rules"] == 1
            elif p["name"] == "staging":
                assert p["rules"] == 2

    def test_list_policies_broken_has_error_flag(self, policy_dir):
        from agentguard.mcp.tools import tool_guard_list_policies
        result = tool_guard_list_policies({
            "directory": str(policy_dir),
        })
        broken = [p for p in result["policies"] if p["name"] == "broken"]
        if broken:
            assert "error" in broken[0]

    def test_list_policies_nonexistent_directory(self):
        from agentguard.mcp.tools import tool_guard_list_policies
        result = tool_guard_list_policies({
            "directory": "/nonexistent/dir",
        })
        assert result["status"] == "error"

    def test_list_policies_no_directory_defaults_ok(self):
        """Should not crash when no directory is specified."""
        from agentguard.mcp.tools import tool_guard_list_policies
        result = tool_guard_list_policies({})
        assert result["status"] == "ok"
        assert "directory" in result

    def test_list_policies_shows_active(self, policy_dir):
        from agentguard.mcp.tools import tool_guard_list_policies
        result = tool_guard_list_policies({
            "directory": str(policy_dir),
        })
        assert "active_policy" in result


# ── Resource Tests ────────────────────────────────────────

class TestResources:
    """Test MCP resource handlers."""

    def test_resource_policy_no_file(self):
        from agentguard.mcp.resources import resource_policy
        content = resource_policy(None)
        data = json.loads(content)
        assert data["status"] == "no_policy"

    def test_resource_policy_with_file(self, tmp_path):
        from agentguard.mcp.resources import resource_policy
        policy_file = tmp_path / "test-policy.yaml"
        policy_file.write_text("version: \"1.0\"\nrules: []")
        content = resource_policy(str(policy_file))
        assert "version" in content
        assert "rules" in content

    def test_resource_stats(self):
        from agentguard.mcp.resources import resource_stats
        content = resource_stats(None)
        data = json.loads(content)
        assert "total_validations" in data
        assert "by_level" in data
        assert "pass_rate" in data


# ── Tool Schema Validation ────────────────────────────────

class TestToolSchemas:
    """Verify all tool schemas are well-formed."""

    def test_all_tools_have_required_fields(self):
        for name, tool in TOOL_REGISTRY.items():
            assert "description" in tool, f"{name}: missing description"
            assert "inputSchema" in tool, f"{name}: missing inputSchema"
            assert "handler" in tool, f"{name}: missing handler"
            assert callable(tool["handler"]), f"{name}: handler not callable"

    def test_input_schemas_are_valid_json_schema(self):
        for name, tool in TOOL_REGISTRY.items():
            schema = tool["inputSchema"]
            assert schema["type"] == "object"
            assert "properties" in schema
            if "required" in schema:
                for field in schema["required"]:
                    assert field in schema["properties"], \
                        f"{name}: required field '{field}' not in properties"

    def test_tool_names_match_registry_keys(self):
        for name in TOOL_REGISTRY:
            assert name.startswith("guard_"), f"Tool '{name}' should start with 'guard_'"

    def test_new_p0_tools_registered(self):
        """Verify all P0 enhancement tools are registered."""
        assert "guard_fix" in TOOL_REGISTRY
        assert "guard_reload_policy" in TOOL_REGISTRY
        assert "guard_list_policies" in TOOL_REGISTRY

    def test_guard_fix_schema_has_fix_mode_enum(self):
        schema = TOOL_REGISTRY["guard_fix"]["inputSchema"]
        fix_mode = schema["properties"]["fix_mode"]
        assert "enum" in fix_mode
        assert set(fix_mode["enum"]) == {"auto", "suggest", "strict"}

    def test_guard_get_audit_has_time_filters(self):
        schema = TOOL_REGISTRY["guard_get_audit"]["inputSchema"]
        props = schema["properties"]
        assert "from_time" in props
        assert "to_time" in props
        assert "offset" in props

    def test_guard_reload_policy_schema(self):
        schema = TOOL_REGISTRY["guard_reload_policy"]["inputSchema"]
        assert "policy_path" in schema["properties"]
        # Not required — can use env var fallback
        assert "required" not in schema or "policy_path" not in schema.get("required", [])

    def test_guard_list_policies_schema(self):
        schema = TOOL_REGISTRY["guard_list_policies"]["inputSchema"]
        assert "directory" in schema["properties"]


# ── Dispatch Tests ────────────────────────────────────────

class TestDispatch:
    """Test the JSON-RPC message dispatch logic."""

    def test_dispatch_initialize(self, server, capture_stdio):
        msg = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        server._dispatch(msg)
        output = capture_stdio.getvalue()
        for line in output.strip().split("\n"):
            try:
                data = json.loads(line)
                if data.get("id") == 1:
                    assert "result" in data
                    assert data["result"]["protocolVersion"] == "2024-11-05"
            except json.JSONDecodeError:
                continue

    def test_dispatch_tools_list(self, server, capture_stdio):
        msg = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        server._dispatch(msg)
        output = capture_stdio.getvalue()
        for line in output.strip().split("\n"):
            try:
                data = json.loads(line)
                if data.get("id") == 2:
                    assert "result" in data
                    assert "tools" in data["result"]
                    # Should include new P0 tools
                    tool_names = {t["name"] for t in data["result"]["tools"]}
                    assert "guard_fix" in tool_names
            except json.JSONDecodeError:
                continue

    def test_dispatch_unknown_method(self, server, capture_stdio):
        msg = {"jsonrpc": "2.0", "id": 3, "method": "unknown/method", "params": {}}
        server._dispatch(msg)
        output = capture_stdio.getvalue()
        for line in output.strip().split("\n"):
            try:
                data = json.loads(line)
                if data.get("id") == 3:
                    assert "error" in data
                    assert data["error"]["code"] == -32601  # METHOD_NOT_FOUND
            except json.JSONDecodeError:
                continue

    def test_dispatch_notification_no_response(self, server, capture_stdio):
        msg = {"jsonrpc": "2.0", "method": "initialized"}
        server._dispatch(msg)
        output = capture_stdio.getvalue()
        assert output.strip() == "" or '"id"' not in output

    def test_dispatch_tools_call_guard_fix(self, server, capture_stdio):
        """Dispatch a tools/call for the new guard_fix tool."""
        msg = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "guard_fix",
                "arguments": {
                    "output": '{"action": "read"}',
                    "expected_schema": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string"},
                            "target": {"type": "string"},
                        },
                        "required": ["action", "target"],
                    },
                    "fix_mode": "auto",
                },
            },
        }
        server._dispatch(msg)
        output = capture_stdio.getvalue()
        for line in output.strip().split("\n"):
            try:
                data = json.loads(line)
                if data.get("id") == 10:
                    assert "result" in data
                    content = data["result"]["content"]
                    assert len(content) == 1
                    result_json = json.loads(content[0]["text"])
                    assert "fix_mode" in result_json
            except json.JSONDecodeError:
                continue

    def test_dispatch_tools_call_guard_reload_policy(self, server, capture_stdio, policy_dir):
        """Dispatch a tools/call for the new guard_reload_policy tool."""
        msg = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "guard_reload_policy",
                "arguments": {
                    "policy_path": str(policy_dir / "prod.yaml"),
                },
            },
        }
        server._dispatch(msg)
        output = capture_stdio.getvalue()
        for line in output.strip().split("\n"):
            try:
                data = json.loads(line)
                if data.get("id") == 11:
                    assert "result" in data
                    result_json = json.loads(data["result"]["content"][0]["text"])
                    assert result_json["status"] == "ok"
            except json.JSONDecodeError:
                continue
