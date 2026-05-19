"""Guard — three-layer progressive validation orchestrator.

Schema -> Semantic -> Policy
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agentguard.result import GuardLevel, CheckResult, GuardResult
from agentguard.config import GuardConfig
from agentguard.errors import ConfigError
from agentguard.schema_guard import SchemaGuard
from agentguard.semantic_guard import SemanticGuard
from agentguard.policy_guard import PolicyGuard
from agentguard.audit.logger import AuditLogger, AuditEntry
from agentguard.semantic.intent_registry import IntentRegistry


class Guard:
    """Three-layer progressive AI output safety engine.

    Usage:
        guard = Guard(schema=MyModel, semantic=True, policy="prod.yaml")
        result = guard.validate(llm_output)
        if result.passed:
            use(result.output)
    """

    def __init__(
        self,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        semantic: bool = False,
        dangerous_intents: list[str] | None = None,
        policy: str | None = None,
        on_fail: str = "deny",
        auto_fix: bool = True,
        fail_open: bool = True,
        strict_schema: bool = False,
    ):
        """Initialize a Guard instance.

        Args:
            schema: Pydantic model, JSON Schema dict, or None (skip schema check).
            semantic: Enable semantic safety check (v0.1: rule mode only).
            dangerous_intents: Specific intents to block. None = all critical/high.
            policy: Path to YAML policy file, or YAML string, or None.
            on_fail: Default action when validation fails ("deny"/"warn"/"ask_human").
            auto_fix: Enable automatic schema fixing.
            fail_open: If True, guard internal errors pass through. If False, deny.
            strict_schema: Strip unknown fields in schema validation.
        """
        self._config = GuardConfig(
            auto_fix=auto_fix,
            fail_open=fail_open,
            on_fail=on_fail,
        )

        # Schema Guard
        self._schema_guard = SchemaGuard(
            schema=schema,
            strict_mode=strict_schema,
        ) if schema else None

        # Semantic Guard
        self._semantic_guard = SemanticGuard(
            dangerous_intents=dangerous_intents,
        ) if semantic else None

        # Policy Guard
        self._policy_guard = None
        if policy:
            if policy.endswith((".yaml", ".yml")) and Path(policy).exists():
                self._policy_guard = PolicyGuard.from_file(policy)
            else:
                self._policy_guard = PolicyGuard.from_yaml(policy)

        # Audit
        self._audit = AuditLogger(store=self._config.audit_store)

    def validate(self, output: Any) -> GuardResult:
        """Run the three-layer validation pipeline.

        Args:
            output: The LLM output to validate. Can be:
                - raw string (will be parsed as JSON if possible)
                - dict (already parsed)
                - Pydantic model instance

        Returns:
            GuardResult with level, (possibly fixed) output, and check details.
        """
        start = time.time()
        checks: list[CheckResult] = []
        current_output = output
        blocked_by: str | None = None
        final_level = GuardLevel.PASS

        # --- Layer 1: Schema ---
        if self._schema_guard:
            try:
                check = self._schema_guard.validate(current_output)
                checks.append(check)

                if check.level == GuardLevel.DENY:
                    final_level = GuardLevel.DENY
                    blocked_by = "schema"
                    return self._build_result(
                        current_output, checks, blocked_by, final_level, start
                    )

                if check.level == GuardLevel.FIX and check.fix is not None:
                    current_output = check.fix
                    final_level = GuardLevel.FIX  # May be overridden later
                elif check.level == GuardLevel.PASS and check.fix is not None:
                    # Use the validated dict for downstream consistency
                    current_output = check.fix

                if check.level == GuardLevel.WARN and final_level not in (
                    GuardLevel.DENY, GuardLevel.ASK_HUMAN
                ):
                    final_level = GuardLevel.WARN

            except Exception as e:
                if not self._config.fail_open:
                    checks.append(CheckResult(
                        layer="schema",
                        level=GuardLevel.DENY,
                        message=f"Schema Guard error: {e}",
                    ))
                    return self._build_result(
                        current_output, checks, "schema", GuardLevel.DENY, start
                    )
                checks.append(CheckResult(
                    layer="schema",
                    level=GuardLevel.WARN,
                    message=f"Schema Guard error (fail-open): {e}",
                ))

        # --- Layer 2: Semantic ---
        if self._semantic_guard:
            try:
                check = self._semantic_guard.check(current_output)
                checks.append(check)

                if check.level == GuardLevel.DENY:
                    blocked_by = "semantic"
                    return self._build_result(
                        current_output, checks, blocked_by, GuardLevel.DENY, start
                    )

                if check.level == GuardLevel.WARN and final_level not in (
                    GuardLevel.DENY, GuardLevel.ASK_HUMAN, GuardLevel.FIX
                ):
                    final_level = GuardLevel.WARN

            except Exception as e:
                if not self._config.fail_open:
                    return self._build_result(
                        current_output, checks, "semantic", GuardLevel.DENY, start
                    )
                checks.append(CheckResult(
                    layer="semantic",
                    level=GuardLevel.WARN,
                    message=f"Semantic Guard error (fail-open): {e}",
                ))

        # --- Layer 3: Policy ---
        if self._policy_guard:
            try:
                check = self._policy_guard.check(current_output)
                checks.append(check)

                if check.level == GuardLevel.DENY:
                    blocked_by = "policy"
                    return self._build_result(
                        current_output, checks, blocked_by, GuardLevel.DENY, start
                    )

                if check.level == GuardLevel.ASK_HUMAN:
                    blocked_by = "policy"
                    return self._build_result(
                        current_output, checks, blocked_by, GuardLevel.ASK_HUMAN, start
                    )

                if check.level == GuardLevel.WARN and final_level not in (
                    GuardLevel.DENY, GuardLevel.ASK_HUMAN, GuardLevel.FIX
                ):
                    final_level = GuardLevel.WARN

            except Exception as e:
                if not self._config.fail_open:
                    return self._build_result(
                        current_output, checks, "policy", GuardLevel.DENY, start
                    )
                checks.append(CheckResult(
                    layer="policy",
                    level=GuardLevel.WARN,
                    message=f"Policy Guard error (fail-open): {e}",
                ))

        return self._build_result(current_output, checks, blocked_by, final_level, start)

    def _build_result(
        self,
        output: Any,
        checks: list[CheckResult],
        blocked_by: str | None,
        final_level: GuardLevel,
        start_time: float,
    ) -> GuardResult:
        latency_ms = (time.time() - start_time) * 1000

        # Serialize output for audit preview
        try:
            preview = json.dumps(
                output if isinstance(output, dict) else str(output)[:200]
            )
        except Exception:
            preview = str(output)[:200]

        # Audit
        self._audit.log(AuditEntry(
            input_preview=str(output)[:200],
            output_preview=preview,
            result_level=final_level.value,
            blocked_by=blocked_by,
            checks_summary=[
                {"layer": c.layer, "level": c.level.value, "message": c.message}
                for c in checks
            ],
            metadata={"latency_ms": round(latency_ms, 2)},
        ))

        return GuardResult(
            level=final_level,
            output=output,
            checks=checks,
            blocked_by=blocked_by,
            metadata={"latency_ms": round(latency_ms, 2)},
        )

    @property
    def audit_log(self) -> AuditLogger:
        return self._audit
