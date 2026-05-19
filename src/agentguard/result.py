"""Guard result data models — GuardLevel, CheckResult, GuardResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GuardLevel(str, Enum):
    """Result level for a single guard check."""
    PASS = "pass"
    WARN = "warn"
    FIX = "fix"
    ASK_HUMAN = "ask_human"
    DENY = "deny"

    @property
    def is_blocking(self) -> bool:
        return self in (GuardLevel.DENY, GuardLevel.ASK_HUMAN)

    @property
    def is_passing(self) -> bool:
        return self == GuardLevel.PASS

    @property
    def is_fixable(self) -> bool:
        return self in (GuardLevel.FIX, GuardLevel.WARN)


@dataclass
class CheckResult:
    """Result from a single guard layer check.
    
    Attributes:
        layer: Which layer produced this result ("schema" / "semantic" / "policy").
        level: Severity/action level.
        message: Human-readable description.
        fix: The auto-fixed output if level is FIX, else None.
        original: Original value that triggered this check.
        confidence: Confidence score 0.0-1.0 for this check.
        metadata: Arbitrary extra data.
    """
    layer: str
    level: GuardLevel
    message: str = ""
    fix: Any = None
    original: Any = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return self.level == GuardLevel.PASS


@dataclass
class GuardResult:
    """Aggregate result from all guard layers.
    
    Attributes:
        level: Highest severity level across all checks.
        output: The (possibly fixed) output. Same as input if PASS.
        checks: Individual check results from each layer, in execution order.
        blocked_by: Which layer blocked (if any).
        metadata: Arbitrary extra data from all layers merged.
    """
    level: GuardLevel = GuardLevel.PASS
    output: Any = None
    checks: list[CheckResult] = field(default_factory=list)
    blocked_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return self.level == GuardLevel.PASS

    @property
    def blocked(self) -> bool:
        return self.level.is_blocking

    @property
    def was_fixed(self) -> bool:
        return self.level == GuardLevel.FIX

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "level": self.level.value,
            "blocked": self.blocked,
            "blocked_by": self.blocked_by,
            "checks": [
                {
                    "layer": c.layer,
                    "level": c.level.value,
                    "message": c.message,
                    "confidence": c.confidence,
                    **(c.metadata or {}),
                }
                for c in self.checks
            ],
        }
