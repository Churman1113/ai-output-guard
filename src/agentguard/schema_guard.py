"""Schema Guard — validates and auto-fixes structured LLM output."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ValidationError

from agentguard.result import CheckResult, GuardLevel
from agentguard.fix.schema_fixer import fix_schema_output


class SchemaGuard:
    """Validates LLM output against expected schema.

    Supports both Pydantic models and raw JSON Schema dicts.
    Auto-fixes enum typos, type coercions, missing defaults, extra fields.
    """

    def __init__(
        self,
        schema: type[BaseModel] | dict[str, Any] | None = None,
        strict_mode: bool = False,
    ):
        self._schema = schema
        self._strict_mode = strict_mode

    def validate(self, output: Any) -> CheckResult:
        """Validate and optionally auto-fix output.
        
        Returns:
            CheckResult with level, fix, and fix_details in metadata.
        """
        if self._schema is None:
            return CheckResult(
                layer="schema",
                level=GuardLevel.PASS,
                message="No schema configured, skipping",
                confidence=1.0,
            )

        # Parse string to dict first
        raw = output
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                return CheckResult(
                    layer="schema",
                    level=GuardLevel.DENY,
                    message="JSON parse error: input is not valid JSON",
                    original=raw,
                    confidence=1.0,
                )

        # Pydantic model validation
        if isinstance(self._schema, type) and issubclass(self._schema, BaseModel):
            return self._validate_pydantic(output, raw)

        # Raw JSON Schema validation
        if isinstance(self._schema, dict):
            return self._validate_json_schema(output, raw)

        return CheckResult(
            layer="schema",
            level=GuardLevel.PASS,
            message="Unsupported schema type, skipping",
            confidence=1.0,
        )

    def _validate_pydantic(
        self, output: dict, raw: Any
    ) -> CheckResult:
        try:
            validated = self._schema.model_validate(output)
            # Serialize model to dict for consistent downstream consumption
            validated_dict = validated.model_dump()
            return CheckResult(
                layer="schema",
                level=GuardLevel.PASS,
                message="Schema validation passed",
                confidence=1.0,
                fix=validated_dict,
            )
        except ValidationError as e:
            # Attempt auto-fix
            schema_dict = self._schema.model_json_schema()
            fixed_output, fix_log = fix_schema_output(
                output, schema_dict, strict_mode=self._strict_mode
            )

            if fix_log and all(f["fixed"] for f in fix_log):
                try:
                    validated = self._schema.model_validate(fixed_output)
                    # Serialize model to dict for consistent downstream consumption
                    validated_dict = validated.model_dump()
                    return CheckResult(
                        layer="schema",
                        level=GuardLevel.FIX,
                        message=f"Auto-fixed {len(fix_log)} schema issues",
                        fix=validated_dict,
                        original=raw,
                        confidence=0.9,
                        metadata={"fixes": fix_log},
                    )
                except ValidationError:
                    pass

            # Return with fix attempts even if not all succeeded
            if fix_log:
                # Check if any fixes were unfixable — those should be DENY
                has_unfixable = any(not f.get("fixed", False) for f in fix_log)
                all_fixed = not has_unfixable
                return CheckResult(
                    layer="schema",
                    level=GuardLevel.WARN if all_fixed else GuardLevel.DENY,
                    message=f"Schema validation failed: {e.errors()}",
                    original=raw,
                    confidence=0.5 if all_fixed else 1.0,
                    metadata={
                        "errors": e.errors(),
                        "fixes": fix_log,
                    },
                )

            return CheckResult(
                layer="schema",
                level=GuardLevel.DENY,
                message=f"Schema validation failed: {e.errors()}",
                original=raw,
                confidence=1.0,
                metadata={"errors": e.errors()},
            )

    def _validate_json_schema(
        self, output: dict, raw: Any
    ) -> CheckResult:
        # For raw JSON Schema, use our fixer only
        fixed_output, fix_log = fix_schema_output(
            output, self._schema, strict_mode=self._strict_mode
        )

        if not fix_log:
            return CheckResult(
                layer="schema",
                level=GuardLevel.PASS,
                message="JSON Schema validation passed",
                confidence=1.0,
            )

        all_fixed = all(f.get("fixed", False) for f in fix_log)
        if all_fixed:
            return CheckResult(
                layer="schema",
                level=GuardLevel.FIX,
                message=f"Auto-fixed {len(fix_log)} schema issues",
                fix=fixed_output,
                original=raw,
                confidence=0.9,
                metadata={"fixes": fix_log},
            )

        unfixed = [f for f in fix_log if not f.get("fixed")]
        return CheckResult(
            layer="schema",
            level=GuardLevel.DENY if unfixed else GuardLevel.WARN,
            message=f"Schema issues: {', '.join(f['error'] for f in unfixed)}",
            original=raw,
            confidence=0.7,
            metadata={"fixes": fix_log},
        )
