"""Semantic Guard — detects dangerous LLM output via rule matching.

v0.1: Rule mode only (keyword + regex + heuristics). Zero external dependencies.
Future: Classifier, Embedding, LLM-as-Judge modes.
"""

from __future__ import annotations

from typing import Any

from agentguard.result import CheckResult, GuardLevel
from agentguard.semantic.rule_matcher import RuleMatcher
from agentguard.semantic.intent_registry import IntentRegistry


class SemanticGuard:
    """Detects dangerous, malicious, or inappropriate content in LLM output."""

    def __init__(
        self,
        dangerous_intents: list[str] | None = None,
        registry: IntentRegistry | None = None,
        mode: str = "rule",
    ):
        self._mode = mode
        self._registry = registry or IntentRegistry()
        self._matcher = RuleMatcher(registry=self._registry)
        self._enabled_intents = dangerous_intents

    def check(self, output: Any) -> CheckResult:
        """Run semantic safety check on output.
        
        Returns:
            CheckResult — DENY if dangerous, PASS if safe.
        """
        text = self._matcher.extract_fields_from_output(output)

        if not text or not text.strip():
            return CheckResult(
                layer="semantic",
                level=GuardLevel.PASS,
                message="Empty output, no semantic check needed",
                confidence=1.0,
            )

        matches = self._matcher.match(text, enabled_intents=self._enabled_intents)

        if not matches:
            return CheckResult(
                layer="semantic",
                level=GuardLevel.PASS,
                message="No dangerous intent detected",
                confidence=1.0,
            )

        # Report all matches
        match_details = []
        highest_severity = "low"
        severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}

        for m in matches:
            match_details.append({
                "intent": m.intent.name,
                "category": m.intent.category.value,
                "severity": m.intent.severity,
                "matched_text": m.matched_text,
                "match_type": m.match_type,
                "confidence": m.confidence,
            })
            if severity_order.get(m.intent.severity, 0) > severity_order.get(highest_severity, 0):
                highest_severity = m.intent.severity

        # Critical and high severity -> DENY
        if highest_severity in ("critical", "high"):
            top = matches[0]
            return CheckResult(
                layer="semantic",
                level=GuardLevel.DENY,
                message=f"Dangerous intent detected: {top.intent.name} ({top.intent.severity}) — {top.intent.description}",
                original=str(text)[:200],
                confidence=top.confidence,
                metadata={
                    "matched_intent": top.intent.name,
                    "matches": match_details,
                },
            )

        # Medium and low -> WARN
        top = matches[0]
        return CheckResult(
            layer="semantic",
            level=GuardLevel.WARN,
            message=f"Potentially risky: {top.intent.name} ({top.intent.severity}) — {top.intent.description}",
            original=str(text)[:200],
            confidence=top.confidence,
            metadata={
                "matched_intent": top.intent.name,
                "matches": match_details,
            },
        )

    @property
    def mode(self) -> str:
        return self._mode
