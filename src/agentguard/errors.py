"""Exception hierarchy for AgentGuard."""

from __future__ import annotations

from typing import Any


class GuardError(Exception):
    """Base exception for all AgentGuard errors."""
    pass


class SchemaValidationError(GuardError):
    """Raised when Schema Guard encounters an unfixable structural error."""
    pass


class SemanticGuardError(GuardError):
    """Raised when Semantic Guard encounters an internal error."""
    pass


class PolicyError(GuardError):
    """Raised when Policy Guard encounters a YAML/rule error."""
    pass


class FixError(GuardError):
    """Raised when auto-fix cannot be applied.

    Attributes:
        original: The original value that could not be fixed.
        attempt: The attempted fix value.
    """

    def __init__(self, message: str, *, original: Any = None, attempt: Any = None) -> None:
        super().__init__(message)
        self.original = original
        self.attempt = attempt


class GuardTimeoutError(GuardError):
    """Raised when a guard layer exceeds its timeout.

    Attributes:
        layer: The guard layer that timed out (e.g., 'schema', 'semantic', 'policy').
    """

    def __init__(self, message: str, *, layer: str | None = None) -> None:
        super().__init__(message)
        self.layer = layer


class ConfigError(GuardError):
    """Raised when configuration is invalid."""
    pass
