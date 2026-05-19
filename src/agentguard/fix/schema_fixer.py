"""Schema auto-fix orchestrator.

Coordinates enum fixer + type fixer for repairing invalid structured output.
Supports recursive fixing of nested objects and basic array item validation.
"""

from __future__ import annotations

import json
from typing import Any

from agentguard.fix.enum_fixer import fuzzy_match_enum
from agentguard.fix.type_fixer import fix_type


def _schema_type_to_python(type_name: str | None) -> type | None:
    """Convert JSON Schema type name to Python type.

    'number' maps to (int, float) since JSON numbers can be either.
    """
    if type_name == "number":
        return (int, float)  # Accept either
    return {
        "string": str,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }.get(type_name) if type_name else None


def _get_nested(data: dict, path: list[str]) -> Any:
    """Safely traverse nested dict using a field path."""
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _set_nested(data: dict, path: list[str], value: Any) -> None:
    """Set a value at a nested path, creating intermediate dicts as needed."""
    current = data
    for key in path[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[path[-1]] = value


def _del_nested(data: dict, path: list[str]) -> None:
    """Delete a key at a nested path."""
    current = data
    for key in path[:-1]:
        if not isinstance(current, dict):
            return
        current = current.get(key)
        if current is None:
            return
    if isinstance(current, dict):
        current.pop(path[-1], None)


def _fix_field(
    field: str,
    value: Any,
    field_schema: dict[str, Any],
    result: dict[str, Any],
    fix_log: list[dict[str, Any]],
    path: list[str] | None = None,
) -> Any:
    """Attempt to fix a single field. Returns the (possibly fixed) value.

    Handles type coercion, enum fuzzy matching, and recursively fixes nested objects.
    """
    if field_schema is None:
        return value

    current_path = (path or []) + [field]
    expected_type = _schema_type_to_python(field_schema.get("type"))
    enums = field_schema.get("enum")
    sub_props = field_schema.get("properties")
    items_schema = field_schema.get("items")

    # --- Type fix ---
    if expected_type and not isinstance(value, expected_type):
        fixed, was_fixed = fix_type(value, expected_type)
        if was_fixed:
            result[field] = fixed
            fix_log.append({
                "field": ".".join(str(p) for p in current_path),
                "error": f"Type mismatch: expected {expected_type}, got {type(value).__name__}",
                "fixed": True,
                "action": "type_coerce",
                "confidence": 0.9,
                "new_value": str(fixed),
            })
            value = fixed

    # --- Enum fix ---
    if enums and isinstance(value, str) and value not in enums:
        matched, confidence = fuzzy_match_enum(value, enums)
        if matched and confidence >= 0.6:
            result[field] = matched
            fix_log.append({
                "field": ".".join(str(p) for p in current_path),
                "error": f"Invalid enum value '{value}', fixed to '{matched}'",
                "fixed": True,
                "action": "enum_fix",
                "confidence": round(confidence, 2),
            })
            value = matched
        elif matched is None:
            fix_log.append({
                "field": ".".join(str(p) for p in current_path),
                "error": f"Invalid enum value '{value}', valid: {enums}",
                "fixed": False,
                "confidence": 0.0,
            })

    # --- Nested object fix (recursive) ---
    if sub_props and isinstance(value, dict):
        _fix_object_fields(value, sub_props, fix_log, current_path)

    # --- Array items fix ---
    if items_schema and isinstance(value, list):
        items_type = _schema_type_to_python(items_schema.get("type"))
        items_props = items_schema.get("properties")
        fixed_items: list[Any] = []
        for i, item in enumerate(value):
            if items_props and isinstance(item, dict):
                item_copy = dict(item)
                _fix_object_fields(item_copy, items_props, fix_log, current_path + [str(i)])
                fixed_items.append(item_copy)
            elif items_type and not isinstance(item, items_type):
                fixed_item, was_fixed = fix_type(item, items_type if isinstance(items_type, type) else items_type)
                if was_fixed:
                    fix_log.append({
                        "field": ".".join(str(p) for p in current_path + [str(i)]),
                        "error": f"Array item type mismatch: expected {items_type}",
                        "fixed": True,
                        "action": "type_coerce",
                        "confidence": 0.9,
                    })
                    fixed_items.append(fixed_item)
                else:
                    fixed_items.append(item)
            else:
                fixed_items.append(item)

        if fixed_items != value:
            result[field] = fixed_items

    return value


def _fix_object_fields(
    output: dict[str, Any],
    properties: dict[str, dict[str, Any]],
    fix_log: list[dict[str, Any]],
    path: list[str] | None = None,
) -> None:
    """Fix all fields in a flat or nested object according to its JSON Schema properties."""
    for field, field_schema in properties.items():
        if field not in output:
            continue
        value = output[field]
        _fix_field(field, value, field_schema, output, fix_log, path)


def fix_schema_output(
    output: Any,
    expected_schema: dict[str, Any],
    strict_mode: bool = False,
) -> tuple[Any, list[dict[str, Any]]]:
    """Attempt to fix schema violations in structured output.

    Applies fixes in order:
    1. Required field filling (with defaults)
    2. Type coercion (str→int, str→bool, etc.)
    3. Enum fuzzy matching (Levenshtein distance)
    4. Nested object recursive fixing
    5. Strict mode: strip unknown fields

    Args:
        output: The JSON-parsed output (dict) or raw str.
        expected_schema: JSON Schema dict with 'properties' and 'required'.
        strict_mode: If True, strip unknown fields.

    Returns:
        Tuple of (fixed_output, fix_log).
    """
    fix_log: list[dict[str, Any]] = []

    # Parse string to dict if needed
    original = output
    if isinstance(output, str):
        try:
            output = json.loads(output)
        except json.JSONDecodeError:
            return original, [{
                "field": "__root__",
                "error": "JSON parse error — input is not valid JSON",
                "fixed": False,
                "confidence": 0.0,
            }]

    if not isinstance(output, dict):
        return output, fix_log

    result = dict(output)  # Shallow copy for top level
    props = expected_schema.get("properties", {})

    # Known fix actions for deduplication tracking
    fixed_fields: set[tuple[str, ...]] = set()

    # ── Step 1: Required fields ──
    required = expected_schema.get("required", [])
    for field in required:
        if field not in result:
            field_schema = props.get(field, {})
            default = field_schema.get("default")
            if default is not None:
                result[field] = default
                fix_log.append({
                    "field": field,
                    "error": f"Missing required field '{field}', filled with default",
                    "fixed": True,
                    "action": "default_fill",
                    "confidence": 1.0,
                })
                fixed_fields.add((field,))
            else:
                # Try type-appropriate empty value
                field_type = field_schema.get("type")
                fallback = {
                    "string": "",
                    "integer": 0,
                    "number": 0,
                    "boolean": False,
                    "array": [],
                    "object": {},
                }.get(field_type)
                if fallback is not None:
                    result[field] = fallback
                    fix_log.append({
                        "field": field,
                        "error": f"Missing required field '{field}', filled with empty {field_type}",
                        "fixed": True,
                        "action": "default_fill_fallback",
                        "confidence": 0.5,
                    })
                    fixed_fields.add((field,))
                else:
                    fix_log.append({
                        "field": field,
                        "error": f"Missing required field '{field}' (no default available)",
                        "fixed": False,
                        "confidence": 0.0,
                    })

    # ── Step 2: Fix each existing field ──
    for field in list(result.keys()):
        value = result[field]
        field_schema = props.get(field)

        if field_schema is None:
            # Unknown field
            if strict_mode:
                del result[field]
                fix_log.append({
                    "field": field,
                    "error": f"Unknown field '{field}' stripped in strict mode",
                    "fixed": True,
                    "action": "strip",
                    "confidence": 1.0,
                })
            continue

        _fix_field(field, value, field_schema, result, fix_log)

    return result, fix_log
