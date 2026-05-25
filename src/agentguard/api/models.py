"""Pydantic models for the AI Output Guard HTTP API.

Defines request/response schemas for validate, audit, and status endpoints.
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


# ── Request Models ────────────────────────────────────────

class ValidateRequest(BaseModel):
    """Request body for POST /api/v1/validate."""

    output: str = Field(..., description="The AI-generated output to validate (JSON string or plain text)")
    context: dict[str, Any] = Field(default_factory=dict, description="Optional context about the validation request")


class PolicyUpdateRequest(BaseModel):
    """Request body for POST /api/v1/policy."""

    policy: str = Field(..., description="YAML policy content with rules, defaults, and version")


class AddIntentRequest(BaseModel):
    """Request body for POST /api/v1/intents."""

    name: str = Field(..., description="Unique name for the intent")
    patterns: list[str] = Field(default_factory=list, description="Keyword or regex patterns to match")
    description: str = Field("", description="Human-readable description of the intent")
    severity: str = Field("medium", description="Severity level: critical/high/medium/low")
    category: str = Field("compliance_risk", description="Intent category")


# ── Response Models ───────────────────────────────────────

class CheckDetail(BaseModel):
    """Detail of a single guard check."""

    layer: str
    level: str
    message: str
    confidence: float


class ValidateResponse(BaseModel):
    """Response for POST /api/v1/validate."""

    passed: bool
    blocked: bool
    level: str
    blocked_by: Optional[str] = None
    checks: list[CheckDetail] = Field(default_factory=list)
    latency_ms: float = 0
    context: Optional[dict[str, Any]] = None
    fixed_output: Optional[str] = None


class AuditEntry(BaseModel):
    """A single audit log entry."""

    timestamp: float
    result: str
    blocked_by: Optional[str] = None
    input_preview: str
    output_preview: str
    checks: List[dict] = Field(default_factory=list)


class AuditResponse(BaseModel):
    """Response for GET /api/v1/audit."""

    total: int
    shown: int
    entries: list[AuditEntry] = Field(default_factory=list)


class StatusResponse(BaseModel):
    """Response for GET /api/v1/status."""

    server: str
    version: str
    layers: dict[str, bool]
    config: dict[str, Any]
    policy: Optional[dict[str, Any]] = None
    policy_path: Optional[str] = None
    audit_entries: int


class ErrorResponse(BaseModel):
    """Standard error response."""

    status: str = "error"
    message: str
    detail: Optional[str] = None
