"""Enum value fuzzy matching and auto-fix using Levenshtein distance and heuristics."""

from __future__ import annotations



def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    prev_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            insert = prev_row[j + 1] + 1
            delete = curr_row[j] + 1
            substitute = prev_row[j] + (0 if c1 == c2 else 1)
            curr_row.append(min(insert, delete, substitute))
        prev_row = curr_row

    return prev_row[-1]


def fuzzy_match_enum(
    value: str,
    valid_values: list[str],
    min_confidence: float = 0.6,
    case_sensitive: bool = False,
) -> tuple[str | None, float]:
    """Find the closest valid enum value using multi-strategy matching.

    Strategies applied in order (returns first match above threshold):
    1. **Exact match** — identity (confidence 1.0)
    2. **Case-insensitive exact** — e.g. "get" → "GET" (confidence 0.95)
    3. **Prefix match** — e.g. "cre" → "create" (confidence 0.90)
    4. **Suffix match** — e.g. "lete" → "delete" (confidence 0.85)
    5. **Substring match** — e.g. "EL" → "DELETE" (confidence 0.80)
    6. **Levenshtein distance** — e.g. "DELTE" → "DELETE" (confidence scaled)
    7. **Contains match** — valid value contains the input (confidence 0.75)

    Args:
        value: The value to match.
        valid_values: List of valid enum values.
        min_confidence: Minimum confidence threshold (0.0-1.0).
        case_sensitive: If False, comparison is case-insensitive.

    Returns:
        Tuple of (matched_value, confidence) or (None, 0.0) if no match.
    """
    if not value or not valid_values:
        return None, 0.0

    if case_sensitive:
        compare = value
        valid_compare = valid_values
    else:
        compare = value.upper()
        valid_compare = [v.upper() for v in valid_values]

    # 1. Exact match (fast path)
    for i, vc in enumerate(valid_compare):
        if compare == vc:
            return valid_values[i], 1.0

    # 2. Case-insensitive exact (only when case_sensitive=True)
    if case_sensitive:
        compare_upper = compare.upper()
        for i, vc in enumerate(valid_compare):
            if compare_upper == vc.upper():
                return valid_values[i], 0.95

    # 3. Prefix match (input is a prefix of valid value, length >= 3)
    for i, vc in enumerate(valid_compare):
        if vc.startswith(compare) and len(compare) >= 3:
            return valid_values[i], 0.90

    # 4. Suffix match (input is a suffix of valid value, length >= 3)
    for i, vc in enumerate(valid_compare):
        if vc.endswith(compare) and len(compare) >= 3:
            return valid_values[i], 0.85

    # 5. Substring match (valid value contains input, length >= 2)
    for i, vc in enumerate(valid_compare):
        if len(compare) >= 2 and compare in vc:
            return valid_values[i], 0.80

    # 6. Levenshtein distance
    best_match = None
    best_score = 0.0

    for i, vc in enumerate(valid_compare):
        max_len = max(len(compare), len(vc))
        if max_len == 0:
            continue
        distance = levenshtein_distance(compare, vc)
        similarity = 1.0 - (distance / max_len)

        if similarity > best_score and similarity >= min_confidence:
            best_score = similarity
            best_match = valid_values[i]

    if best_match is not None:
        return best_match, round(best_score, 2)

    # 7. Contains match (valid value is contained in input)
    if len(compare) >= 4:
        for i, vc in enumerate(valid_compare):
            if vc in compare:
                return valid_values[i], 0.75

    return None, 0.0


def suggest_enum(value: str, valid_values: list[str], top_n: int = 3) -> list[tuple[str, float]]:
    """Return top-N suggestions for an invalid enum value, sorted by confidence."""
    scored: list[tuple[str, float]] = []
    for v in valid_values:
        _, confidence = fuzzy_match_enum(value, [v])
        if confidence > 0:
            scored.append((v, confidence))
    scored.sort(key=lambda x: -x[1])
    return scored[:top_n]
