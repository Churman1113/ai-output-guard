"""Direct unit tests for enum_fixer.py — fuzzy enum matching."""
import pytest
from agentguard.fix.enum_fixer import (
    levenshtein_distance, fuzzy_match_enum, suggest_enum,
)


class TestLevenshtein:
    def test_identical_strings(self):
        assert levenshtein_distance("hello", "hello") == 0

    def test_one_edit(self):
        assert levenshtein_distance("cat", "cats") == 1
        assert levenshtein_distance("cat", "cut") == 1

    def test_completely_different(self):
        assert levenshtein_distance("abc", "xyz") == 3

    def test_empty_string(self):
        assert levenshtein_distance("", "abc") == 3
        assert levenshtein_distance("abc", "") == 3

    def test_both_empty(self):
        assert levenshtein_distance("", "") == 0

    def test_typo_examples(self):
        # Common enum typos
        assert levenshtein_distance("DELTE", "DELETE") == 1
        assert levenshtein_distance("GETE", "GET") == 1
        # "POTS" -> "POST" is a transposition; standard Levenshtein needs 2 edits
        assert levenshtein_distance("POTS", "POST") == 2
        assert levenshtein_distance("CREAT", "CREATE") == 1
        # "UPDTE" -> "UPDATE": insert "A" → 1 edit
        assert levenshtein_distance("UPDTE", "UPDATE") == 1


class TestFuzzyMatchEnum:
    def test_exact_match(self):
        matched, conf = fuzzy_match_enum("GET", ["GET", "POST"])
        assert matched == "GET"
        assert conf == 1.0

    def test_case_insensitive_match(self):
        """Case-insensitive exact match for non-case_sensitive mode."""
        matched, conf = fuzzy_match_enum("get", ["GET", "POST"])
        assert matched == "GET"
        assert conf == 1.0

    def test_case_sensitive_mode(self):
        """With case_sensitive=True, 'get' should not exact-match 'GET'."""
        matched, conf = fuzzy_match_enum("get", ["GET", "POST"], case_sensitive=True)
        # Should still match via case-insensitive fallback (strategy 2)
        assert matched == "GET"
        assert conf == 0.95

    def test_prefix_match(self):
        """'cre' is a prefix of 'create'."""
        matched, conf = fuzzy_match_enum("cre", ["create", "read", "update", "delete"])
        assert matched == "create"
        assert conf == 0.90

    def test_suffix_match(self):
        """'lete' is a suffix of 'delete'."""
        matched, conf = fuzzy_match_enum("lete", ["create", "read", "update", "delete"])
        assert matched == "delete"
        assert conf == 0.85

    def test_substring_match(self):
        """'EL' is a substring of 'DELETE' (case-insensitive, now length >=2)."""
        matched, conf = fuzzy_match_enum("EL", ["GET", "POST", "PUT", "DELETE", "PATCH"])
        assert matched == "DELETE", f"Expected DELETE, got {matched}"
        assert conf == 0.80

    def test_levenshtein_typo(self):
        """Common typo 'DELTE' → 'DELETE' via Levenshtein."""
        matched, conf = fuzzy_match_enum("DELTE", ["GET", "POST", "DELETE"])
        assert matched == "DELETE"
        assert conf >= 0.8

    def test_levenshtein_close(self):
        matched, conf = fuzzy_match_enum("UPDTE", ["CREATE", "READ", "UPDATE", "DELETE"])
        assert matched == "UPDATE"
        assert conf >= 0.6

    def test_contains_match(self):
        """'GET' is contained in the input 'SOMETHING_GET_123'."""
        matched, conf = fuzzy_match_enum("SOMETHING_GET_123", ["GET", "POST"])
        assert matched == "GET"
        assert conf == 0.75

    def test_no_match(self):
        """Completely unrelated string should not match."""
        matched, conf = fuzzy_match_enum("xyzzy", ["GET", "POST", "DELETE"])
        assert matched is None
        assert conf == 0.0

    def test_empty_value(self):
        matched, conf = fuzzy_match_enum("", ["GET", "POST"])
        assert matched is None
        assert conf == 0.0

    def test_empty_valid_values(self):
        matched, conf = fuzzy_match_enum("GET", [])
        assert matched is None
        assert conf == 0.0

    def test_multiple_valid_values(self):
        """Should return the best match from multiple valid values."""
        matched, conf = fuzzy_match_enum("delet", ["create", "read", "update", "delete"])
        assert matched == "delete"
        assert conf >= 0.6

    def test_short_string_doesnt_prefix_match(self):
        """Strings shorter than 3 chars shouldn't prefix/suffix match."""
        matched, conf = fuzzy_match_enum("x", ["create", "read"])
        # Should fall through to Levenshtein or no match
        assert matched is None or conf < 0.9

    def test_none_value(self):
        matched, conf = fuzzy_match_enum(None, ["GET"])
        assert matched is None
        assert conf == 0.0


class TestSuggestEnum:
    def test_basic_suggestions(self):
        suggestions = suggest_enum("DELTE", ["GET", "POST", "PUT", "DELETE", "PATCH"])
        assert len(suggestions) > 0
        assert suggestions[0][0] == "DELETE"  # Best match first

    def test_max_suggestions(self):
        suggestions = suggest_enum("DELTE", ["GET", "POST", "DELETE"], top_n=2)
        assert len(suggestions) <= 2

    def test_no_suggestions_for_unrelated(self):
        suggestions = suggest_enum("xyzzy", ["GET", "POST"])
        assert len(suggestions) == 0

    def test_suggestions_ordered_by_confidence(self):
        suggestions = suggest_enum("cre", ["create", "read", "update", "delete"])
        assert len(suggestions) > 0
        # Confidence should be descending
        for i in range(len(suggestions) - 1):
            assert suggestions[i][1] >= suggestions[i + 1][1]
