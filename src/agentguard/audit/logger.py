"""Audit logger — records every guard check for compliance and debugging."""

from __future__ import annotations

import time
import json
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: float = field(default_factory=time.time)
    input_preview: str = ""  # Truncated input
    output_preview: str = ""  # Truncated output
    result_level: str = ""
    blocked_by: str | None = None
    checks_summary: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    """Collects and stores audit log entries.

    Defaults to in-memory storage. Can be configured for file storage.
    """

    def __init__(self, store: str = "memory"):
        self._store = store
        self._entries: list[AuditEntry] = []

    def log(self, entry: AuditEntry) -> None:
        """Record an audit entry."""
        self._entries.append(entry)

        if self._store != "memory":
            self._flush_to_file(entry)

    def _flush_to_file(self, entry: AuditEntry) -> None:
        """Append entry to log file."""
        try:
            with open(self._store, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), default=str) + "\n")
        except Exception:
            pass  # Audit failure should never crash the main flow

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    @property
    def count(self) -> int:
        return len(self._entries)

    def recent(self, n: int = 10) -> list[AuditEntry]:
        return self._entries[-n:]

    def clear(self) -> None:
        self._entries.clear()
