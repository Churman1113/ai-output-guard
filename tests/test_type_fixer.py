"""Direct unit tests for type_fixer.py — type coercion and fixing."""
import pytest
from agentguard.fix.type_fixer import fix_type, try_coerce


# ──────────────────────────────────────────────
# try_coerce
# ──────────────────────────────────────────────

class TestTryCoerce:
    def test_str_to_int(self):
        assert try_coerce("42", int) == (42, True)
        assert try_coerce("0", int) == (0, True)
        assert try_coerce("-5", int) == (-5, True)

    def test_str_to_int_with_formatting(self):
        """Handle commas and underscores in numbers."""
        assert try_coerce("1,234", int) == (1234, True)
        assert try_coerce("1_000_000", int) == (1000000, True)

    def test_str_to_float(self):
        assert try_coerce("3.14", float) == (3.14, True)
        assert try_coerce("0.5", float) == (0.5, True)
        assert try_coerce("-2.5", float) == (-2.5, True)

    def test_str_to_bool_true(self):
        assert try_coerce("true", bool) == (True, True)
        assert try_coerce("True", bool) == (True, True)
        assert try_coerce("1", bool) == (True, True)
        assert try_coerce("yes", bool) == (True, True)
        assert try_coerce("on", bool) == (True, True)
        assert try_coerce("t", bool) == (True, True)
        assert try_coerce("y", bool) == (True, True)

    def test_str_to_bool_false(self):
        assert try_coerce("false", bool) == (False, True)
        assert try_coerce("False", bool) == (False, True)
        assert try_coerce("0", bool) == (False, True)
        assert try_coerce("no", bool) == (False, True)
        assert try_coerce("off", bool) == (False, True)
        assert try_coerce("f", bool) == (False, True)
        assert try_coerce("n", bool) == (False, True)

    def test_str_to_list_json(self):
        assert try_coerce('[1, 2, 3]', list) == ([1, 2, 3], True)

    def test_str_to_list_single(self):
        """A plain string gets wrapped in a single-element list."""
        result, ok = try_coerce("hello", list)
        assert ok is True
        assert result == ["hello"]

    def test_str_to_dict(self):
        assert try_coerce('{"key": "value"}', dict) == ({"key": "value"}, True)

    def test_int_to_float(self):
        assert try_coerce(5, float) == (5.0, True)

    def test_int_to_bool(self):
        assert try_coerce(1, bool) == (True, True)
        assert try_coerce(0, bool) == (False, True)

    def test_float_to_int(self):
        assert try_coerce(3.9, int) == (3, True)

    def test_float_to_bool(self):
        assert try_coerce(0.0, bool) == (False, True)
        assert try_coerce(1.5, bool) == (True, True)

    def test_bool_to_str(self):
        assert try_coerce(True, str) == ("true", True)
        assert try_coerce(False, str) == ("false", True)

    def test_same_type(self):
        """Same type should always succeed."""
        assert try_coerce("hello", str) == ("hello", True)
        assert try_coerce(42, int) == (42, True)

    def test_uncoercible(self):
        """Values that can't be coerced should return failure."""
        result, ok = try_coerce("not a number", int)
        assert ok is False
        assert result == "not a number"

    def test_none_value(self):
        """None passed to try_coerce should fail gracefully."""
        result, ok = try_coerce(None, str)
        assert ok is False  # None is not coercible to string
        result, ok = try_coerce(None, int)
        assert ok is False


# ──────────────────────────────────────────────
# fix_type
# ──────────────────────────────────────────────

class TestFixType:
    def test_already_correct_type(self):
        """Already correct type should return unchanged."""
        fixed, was_fixed = fix_type(42, int)
        assert fixed == 42
        assert was_fixed is False

    def test_string_to_int(self):
        fixed, was_fixed = fix_type("42", int)
        assert fixed == 42
        assert was_fixed is True

    def test_string_to_bool(self):
        fixed, was_fixed = fix_type("true", bool)
        assert fixed is True
        assert was_fixed is True

    def test_none_value(self):
        """None should never be fixed."""
        fixed, was_fixed = fix_type(None, int)
        assert fixed is None
        assert was_fixed is False

    def test_int_float_union(self):
        """(int, float) union type — JSON Schema 'number'."""
        fixed, was_fixed = fix_type(42, (int, float))
        assert fixed == 42
        assert was_fixed is False

        fixed, was_fixed = fix_type(3.14, (int, float))
        assert fixed == 3.14
        assert was_fixed is False

        fixed, was_fixed = fix_type("42", (int, float))
        assert fixed == 42
        assert was_fixed is True

        fixed, was_fixed = fix_type("3.14", (int, float))
        assert isinstance(fixed, (int, float))
        assert was_fixed is True

    def test_bool_to_int(self):
        fixed, was_fixed = fix_type(True, int)
        # True is already a subclass of int in Python, so it's not "fixed"
        assert fixed is True  # Still the same bool object
        assert was_fixed is False

    def test_bool_to_float(self):
        fixed, was_fixed = fix_type(False, float)
        assert fixed == 0.0
        assert was_fixed is True

    def test_list_to_str(self):
        fixed, was_fixed = fix_type([1, 2, 3], str)
        assert was_fixed is True
        assert "1" in fixed
