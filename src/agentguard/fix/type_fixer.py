"""Type coercion and conversion fixer.

Handles conversion between JSON-compatible types:
    str → int, float, bool, list, dict
    int → float, str
    float → int, str
    bool → str
"""

from __future__ import annotations

import json
from typing import Any


def _strip_whitespace(value: str) -> str:
    """Strip whitespace and common formatting characters."""
    return value.strip().strip('"\'')


def try_coerce(value: Any, target_type: type) -> tuple[Any, bool]:
    """Try to coerce a value to the target type.

    Handles cross-type coercion including:
    - Numeric strings to int/float
    - Boolean strings ("true"/"false", "True"/"False", "1"/"0")
    - JSON arrays/objects from strings
    - Numeric types between int and float

    Args:
        value: The value to coerce.
        target_type: The target Python type.

    Returns:
        Tuple of (coerced_value, success).
    """
    # Same type — no coercion needed
    if isinstance(value, target_type):
        return value, True

    # --- str → target ---
    if isinstance(value, str):
        cleaned = _strip_whitespace(value)

        if target_type is str:
            return value, True

        if target_type is bool:
            lower = cleaned.lower()
            if lower in ("true", "1", "yes", "on", "t", "y"):
                return True, True
            if lower in ("false", "0", "no", "off", "f", "n"):
                return False, True

        if target_type is int:
            try:
                # Handle common number formats
                cleaned_num = cleaned.replace(",", "").replace("_", "")
                return int(float(cleaned_num)), True
            except (ValueError, TypeError, OverflowError):
                pass

        if target_type is float:
            try:
                cleaned_num = cleaned.replace(",", "").replace("_", "")
                return float(cleaned_num), True
            except (ValueError, TypeError, OverflowError):
                pass

        if target_type is list:
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, list):
                    return parsed, True
            except (json.JSONDecodeError, ValueError):
                pass
            # Try single-element list
            return [cleaned], True

        if target_type is dict:
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    return parsed, True
            except (json.JSONDecodeError, ValueError):
                pass

        return value, False

    # --- int → target ---
    if isinstance(value, int) and not isinstance(value, bool):  # bool is subclass of int
        if target_type is float:
            return float(value), True
        if target_type is str:
            return str(value), True
        if target_type is bool:
            return value != 0, True

    # --- float → target ---
    if isinstance(value, float):
        if target_type is int:
            return int(value), True
        if target_type is str:
            return str(value), True
        if target_type is bool:
            return value != 0.0, True

    # --- bool → target ---
    if isinstance(value, bool):
        if target_type is int:
            return int(value), True
        if target_type is float:
            return float(value), True
        if target_type is str:
            return str(value).lower(), True

    # --- list → target ---
    if isinstance(value, list):
        if target_type is str:
            return json.dumps(value, ensure_ascii=False), True
        if target_type is dict and len(value) == 1 and isinstance(value[0], dict):
            return value[0], True

    # --- dict → target ---
    if isinstance(value, dict):
        if target_type is str:
            return json.dumps(value, ensure_ascii=False), True
        if target_type is list:
            return [value], True

    return value, False


def fix_type(value: object, expected_type: Any) -> tuple[object, bool]:
    """Attempt to fix type mismatches.

    Checks if the value is already the correct type, then attempts coercion.
    Supports both single types and tuples of types (e.g., (int, float) for JSON 'number').

    Args:
        value: The value to potentially fix.
        expected_type: The target Python type or tuple of types.

    Returns:
        Tuple of (fixed_value, was_fixed: bool).
    """
    if value is None:
        return value, False

    # Handle union types (tuple of types, e.g., (int, float))
    if isinstance(expected_type, tuple):
        # First check if value is already compatible with ANY type in the union
        if isinstance(value, expected_type):
            return value, False  # Already compatible
        # Try coercion against each type, preferring the closest match
        for t in expected_type:
            coerced, ok = try_coerce(value, t)
            if ok:
                return coerced, True
        return value, False

    # Already correct type — nothing to fix
    if isinstance(value, expected_type):
        return value, False

    # Try coercion
    coerced, ok = try_coerce(value, expected_type)
    if ok and not isinstance(coerced, type(value)):
        # Only count as "fixed" if the type actually changed
        return coerced, True

    return value, False
