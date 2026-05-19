"""Rule-based intent matcher — keyword + regex + heuristics.

Zero external dependencies, <1ms latency, 99%+ accuracy for deterministic patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agentguard.semantic.intent_registry import Intent, IntentRegistry


@dataclass
class RuleMatch:
    """Result of a single rule match."""
    intent: Intent
    matched_text: str = ""
    match_type: str = ""  # "keyword" | "regex" | "heuristic"
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class RuleMatcher:
    """Matches text against keyword and regex patterns.

    Usage:
        matcher = RuleMatcher()
        matches = matcher.match("DROP TABLE users")
        # -> [RuleMatch(intent=drop_table, confidence=1.0)]
    """

    def __init__(self, registry: IntentRegistry | None = None):
        self._registry = registry or IntentRegistry()
        self._compile()

    def _compile(self) -> None:
        """Pre-compile all regex patterns."""
        self._regex_cache: dict[str, list[re.Pattern]] = {}
        for intent in self._registry._intents.values():
            if intent.patterns:
                self._regex_cache[intent.name] = [
                    re.compile(p, re.IGNORECASE) for p in intent.patterns
                ]

    def match(
        self,
        text: str,
        enabled_intents: list[str] | None = None,
    ) -> list[RuleMatch]:
        """Match text against all enabled intents.
        
        Args:
            text: The text to check (LLM output, SQL query, code snippet etc.)
            enabled_intents: If set, only check these intent names.
                            If None, check all registered intents.
        
        Returns:
            List of RuleMatch results, ordered by severity then confidence.
        """
        if not text or not isinstance(text, str):
            return []

        matches: list[RuleMatch] = []
        text_lower = text.lower()

        for intent in self._registry._intents.values():
            if enabled_intents is not None and intent.name not in enabled_intents:
                continue

            # 1. Keyword matching (fastest, highest confidence)
            for keyword in intent.keywords:
                if keyword.lower() in text_lower:
                    matches.append(RuleMatch(
                        intent=intent,
                        matched_text=keyword,
                        match_type="keyword",
                        confidence=1.0,
                    ))
                    break  # one keyword match is enough

            # 2. Regex matching (if no keyword match)
            if not any(m.intent.name == intent.name for m in matches):
                for pattern in self._regex_cache.get(intent.name, []):
                    m = pattern.search(text)
                    if m:
                        matches.append(RuleMatch(
                            intent=intent,
                            matched_text=m.group(0),
                            match_type="regex",
                            confidence=0.98,
                        ))
                        break

            # 3. Heuristic rules (contextual)
            if not any(m.intent.name == intent.name for m in matches):
                heuristic_match = self._check_heuristics(text, text_lower, intent)
                if heuristic_match:
                    matches.append(heuristic_match)

        # Sort: critical > high > medium > low, then by confidence descending
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        matches.sort(key=lambda m: (
            severity_order.get(m.intent.severity, 99),
            -m.confidence,
        ))

        return matches

    def _check_heuristics(
        self, text: str, text_lower: str, intent: Intent
    ) -> RuleMatch | None:
        """Apply heuristic rules for contextual pattern detection."""
        
        # DELETE without WHERE (SQL context only: requires "from")
        if intent.name == "delete_all":
            if "delete" in text_lower and "from" in text_lower and "where" not in text_lower:
                return RuleMatch(
                    intent=intent,
                    match_type="heuristic",
                    confidence=0.85,
                    metadata={"reason": "DELETE without WHERE clause"},
                )

        # rm -rf on root paths
        if intent.name == "rm_recursive":
            if ("rm" in text_lower and any(
                p in text for p in ["/", "/usr", "/etc", "/var", "/home", "/tmp", "C:\\"]
            )):
                return RuleMatch(
                    intent=intent,
                    match_type="heuristic",
                    confidence=0.90,
                    metadata={"reason": "Recursive remove on system path"},
                )

        # Exposed API key patterns (relaxed)
        if intent.name == "expose_api_key":
            if any(kw in text_lower for kw in ["api_key", "token", "secret"]) and any(
                kw in text_lower for kw in ["print", "console.log", "echo", "export"]
            ):
                return RuleMatch(
                    intent=intent,
                    match_type="heuristic",
                    confidence=0.80,
                    metadata={"reason": "Sensitive value in output statement"},
                )

        return None

    def get_highest_match(self, matches: list[RuleMatch]) -> RuleMatch | None:
        """Return the most critical match from a list."""
        if not matches:
            return None
        return matches[0]  # Already sorted by severity

    def extract_fields_from_output(self, output: Any) -> str:
        """Extract text fields from structured output for matching.
        
        Handles: str, dict, list, Pydantic models.
        """
        if isinstance(output, str):
            return output
        if isinstance(output, dict):
            return " ".join(
                self.extract_fields_from_output(v)
                for v in output.values()
            )
        if isinstance(output, list):
            return " ".join(self.extract_fields_from_output(v) for v in output)
        if hasattr(output, "model_dump"):
            return self.extract_fields_from_output(output.model_dump())
        if hasattr(output, "dict"):
            return self.extract_fields_from_output(output.dict())
        return str(output)
