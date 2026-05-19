"""Shared test fixtures for AgentGuard."""
import pytest
from pydantic import BaseModel
from typing import Literal


@pytest.fixture
def api_request_model():
    """Simple API request Pydantic model."""
    class APIRequest(BaseModel):
        endpoint: str
        method: str
        params: dict = {}
    return APIRequest


@pytest.fixture
def api_request_strict_model():
    """API request with enum-constrained method."""
    class APIRequestStrict(BaseModel):
        endpoint: str
        method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]
        params: dict = {}
    return APIRequestStrict


@pytest.fixture
def valid_api_json():
    return '{"endpoint": "/api/users", "method": "GET", "params": {}}'


@pytest.fixture
def missing_field_json():
    return '{"method": "POST"}'


@pytest.fixture
def drop_table_json():
    return '{"action": "execute_sql", "query": "DROP TABLE users"}'


@pytest.fixture
def rm_rf_json():
    return '{"action": "execute", "command": "rm -rf /etc/config"}'


@pytest.fixture
def safe_json():
    return '{"action": "safe", "message": "hello world"}'


@pytest.fixture
def invalid_json():
    return '{endpoint: /api/test}'


@pytest.fixture
def prod_policy_yaml():
    return """
rules:
  - name: "block production"
    priority: 100
    condition:
      all:
        - field: endpoint
          operator: contains
          value: "/prod/"
    action: deny
"""


@pytest.fixture
def warn_delete_policy_yaml():
    return """
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
