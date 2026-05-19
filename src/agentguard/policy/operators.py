"""Policy DSL operators — condition matching functions."""

from __future__ import annotations

import re
from typing import Any


def matches(field_value: Any, pattern: str) -> bool:
    """Regex pattern matching. Converts glob-like `*` to `.*` for convenience."""
    if not isinstance(field_value, str):
        return False
    # Support glob-like wildcards
    regex = pattern.replace("*", ".*").replace("?", ".")
    return bool(re.search(regex, str(field_value), re.IGNORECASE))


def equals(field_value: Any, expected: Any) -> bool:
    """Exact equality, case-sensitive."""
    return field_value == expected


def not_equals(field_value: Any, expected: Any) -> bool:
    """Negated exact equality."""
    return field_value != expected


def contains(field_value: Any, substring: str) -> bool:
    """Case-insensitive substring match."""
    if not isinstance(field_value, str):
        return False
    return substring.lower() in str(field_value).lower()


def startswith(field_value: Any, prefix: str) -> bool:
    """Case-insensitive prefix match."""
    if not isinstance(field_value, str):
        return False
    return str(field_value).lower().startswith(prefix.lower())


def endswith(field_value: Any, suffix: str) -> bool:
    """Case-insensitive suffix match."""
    if not isinstance(field_value, str):
        return False
    return str(field_value).lower().endswith(suffix.lower())


def in_set(field_value: Any, values: list) -> bool:
    """Check if field value is in a set of values."""
    return field_value in values


def gt(field_value: Any, threshold: float) -> bool:
    """Greater than comparison."""
    try:
        return float(field_value) > float(threshold)
    except (ValueError, TypeError):
        return False


def gte(field_value: Any, threshold: float) -> bool:
    """Greater than or equal comparison."""
    try:
        return float(field_value) >= float(threshold)
    except (ValueError, TypeError):
        return False


def lt(field_value: Any, threshold: float) -> bool:
    """Less than comparison."""
    try:
        return float(field_value) < float(threshold)
    except (ValueError, TypeError):
        return False


def lte(field_value: Any, threshold: float) -> bool:
    """Less than or equal comparison."""
    try:
        return float(field_value) <= float(threshold)
    except (ValueError, TypeError):
        return False


def exists(field_value: Any, _unused: Any = None) -> bool:
    """Check if field exists (not None)."""
    return field_value is not None


def not_exists(field_value: Any, _unused: Any = None) -> bool:
    """Check if field does not exist (is None)."""
    return field_value is None


# Mapping of operator name -> function
OPERATOR_MAP: dict[str, callable] = {
    "matches": matches,
    "equals": equals,
    "not_equals": not_equals,
    "contains": contains,
    "startswith": startswith,
    "endswith": endswith,
    "in": in_set,
    "gt": gt,
    "gte": gte,
    "lt": lt,
    "lte": lte,
    "exists": exists,
    "not_exists": not_exists,
}
