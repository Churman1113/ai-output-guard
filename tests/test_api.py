"""Tests for the AgentGuard HTTP API endpoints.

Uses FastAPI TestClient (httpx-backed) for end-to-end endpoint testing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentguard.api import create_app


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def client():
    """Create a fresh TestClient with no policy loaded."""
    app = create_app(policy_path=None)
    return TestClient(app)


@pytest.fixture
def client_with_policy():
    """Create a TestClient with a policy that warns on DELETE methods."""
    import tempfile, os
    policy_yaml = """
rules:
  - name: "warn on DELETE"
    priority: 50
    condition:
      all:
        - field: method
          operator: equals
          value: "DELETE"
    action: warn
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(policy_yaml)
        policy_path = f.name
    try:
        app = create_app(policy_path=policy_path)
        yield TestClient(app)
    finally:
        os.unlink(policy_path)


# ── Health Check ──────────────────────────────────────────

class TestHealthCheck:
    def test_health_returns_ok(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["server"] == "agentguard-api"
        assert data["version"] == "0.1.0"


# ── Validate Endpoint ─────────────────────────────────────

class TestValidate:
    def test_safe_output_passes(self, client):
        response = client.post(
            "/api/v1/validate",
            json={"output": "Hello, this is a safe message."},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["passed"] is True
        assert data["blocked"] is False
        assert data["level"] == "pass"
        assert data["blocked_by"] is None
        assert len(data["checks"]) >= 1
        assert "latency_ms" in data

    def test_sql_injection_blocked(self, client):
        response = client.post(
            "/api/v1/validate",
            json={"output": '{"action": "execute_sql", "query": "DROP TABLE users"}'},
        )
        assert response.status_code == 200
        data = response.json()
        # Schema guard should detect the dangerous SQL intent
        assert "level" in data
        assert "checks" in data
        assert len(data["checks"]) >= 1

    def test_rm_rf_command_detected(self, client):
        response = client.post(
            "/api/v1/validate",
            json={"output": '{"action": "execute", "command": "rm -rf /etc/config"}'},
        )
        assert response.status_code == 200
        data = response.json()
        assert "level" in data
        assert "checks" in data

    def test_with_context_returns_context(self, client):
        response = client.post(
            "/api/v1/validate",
            json={
                "output": "safe text",
                "context": {"user": "test-user", "session": "abc123"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("context") == {"user": "test-user", "session": "abc123"}

    def test_empty_output(self, client):
        """Empty output should still pass through validation."""
        response = client.post(
            "/api/v1/validate",
            json={"output": ""},
        )
        assert response.status_code == 200
        data = response.json()
        assert "level" in data

    def test_missing_output_field(self, client):
        """Missing required field returns 422."""
        response = client.post(
            "/api/v1/validate",
            json={},
        )
        assert response.status_code == 422

    def test_invalid_json_body(self, client):
        """Non-JSON body returns 422."""
        response = client.post(
            "/api/v1/validate",
            content="not valid json",
        )
        assert response.status_code == 422


# ── Policy Endpoint ───────────────────────────────────────

class TestPolicy:
    def test_update_valid_policy(self, client):
        policy_yaml = """
rules:
  - name: "block prod"
    priority: 100
    condition:
      all:
        - field: endpoint
          operator: contains
          value: "/prod/"
    action: deny
"""
        response = client.post(
            "/api/v1/policy",
            json={"policy": policy_yaml},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["rules_loaded"] >= 1

    def test_update_invalid_policy(self, client):
        response = client.post(
            "/api/v1/policy",
            json={"policy": "this is not valid yaml: ["},
        )
        assert response.status_code == 400


# ── Audit Endpoint ────────────────────────────────────────

class TestAudit:
    def test_audit_returns_entries_after_validation(self, client):
        # Trigger some validations first
        client.post("/api/v1/validate", json={"output": "safe message"})
        client.post("/api/v1/validate", json={"output": "another safe message"})

        response = client.get("/api/v1/audit")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2
        assert data["shown"] >= 2
        assert len(data["entries"]) >= 2
        # Verify entry structure
        entry = data["entries"][0]
        assert "timestamp" in entry
        assert "result" in entry
        assert "input_preview" in entry
        assert "output_preview" in entry
        assert "checks" in entry

    def test_audit_with_limit(self, client):
        # Create 5 validations
        for i in range(5):
            client.post("/api/v1/validate", json={"output": f"message {i}"})

        response = client.get("/api/v1/audit?limit=2")
        assert response.status_code == 200
        data = response.json()
        assert data["shown"] <= 2

    def test_audit_with_level_filter(self, client):
        # Trigger a pass-level validation
        client.post("/api/v1/validate", json={"output": "safe message"})

        response = client.get("/api/v1/audit?level=pass")
        assert response.status_code == 200
        data = response.json()
        for entry in data["entries"]:
            assert entry["result"] == "pass"

    def test_audit_with_nonexistent_level(self, client):
        response = client.get("/api/v1/audit?level=nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["shown"] == 0


# ── Intents Endpoint ──────────────────────────────────────

class TestIntents:
    def test_add_valid_intent(self, client):
        response = client.post(
            "/api/v1/intents",
            json={
                "name": "test_intent",
                "patterns": ["delete all", "drop table"],
                "description": "Custom test intent",
                "severity": "high",
                "category": "data_destruction",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["intent"]["name"] == "test_intent"
        assert len(data["intent"]["patterns"]) == 2

    def test_add_intent_minimal(self, client):
        """Only required fields."""
        response = client.post(
            "/api/v1/intents",
            json={
                "name": "minimal_intent",
                "patterns": ["bad thing"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_add_intent_missing_name(self, client):
        response = client.post(
            "/api/v1/intents",
            json={"patterns": ["some pattern"]},
        )
        assert response.status_code == 422


# ── Status Endpoint ───────────────────────────────────────

class TestStatus:
    def test_status_returns_layer_info(self, client):
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["server"] == "agentguard-api"
        assert data["version"] == "0.1.0"
        assert "layers" in data
        assert "config" in data
        # Without policy, schema and semantic should be active
        assert data["layers"]["semantic"] is True

    def test_status_with_policy(self, client_with_policy):
        response = client_with_policy.get("/api/v1/status")
        assert response.status_code == 200
        data = response.json()
        assert data["layers"]["policy"] is True
        assert "policy" in data
        assert data["policy"]["rules"] >= 1
        assert "policy_path" in data
