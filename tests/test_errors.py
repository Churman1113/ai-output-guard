"""Tests for exception hierarchy."""
import pytest
from agentguard.errors import (
    GuardError,
    SchemaValidationError,
    SemanticGuardError,
    PolicyError,
    FixError,
    GuardTimeoutError,
    ConfigError,
)


class TestGuardError:
    def test_base_exception(self):
        with pytest.raises(GuardError):
            raise GuardError("test error")

    def test_message(self):
        try:
            raise GuardError("something went wrong")
        except GuardError as e:
            assert str(e) == "something went wrong"


class TestSchemaValidationError:
    def test_is_guard_error(self):
        with pytest.raises(GuardError):
            raise SchemaValidationError("schema invalid")

    def test_message(self):
        try:
            raise SchemaValidationError("field missing")
        except SchemaValidationError as e:
            assert "field missing" in str(e)


class TestSemanticGuardError:
    def test_is_guard_error(self):
        with pytest.raises(GuardError):
            raise SemanticGuardError("dangerous content")

    def test_message(self):
        try:
            raise SemanticGuardError("matched intent: drop_table")
        except SemanticGuardError as e:
            assert "drop_table" in str(e)


class TestPolicyError:
    def test_is_guard_error(self):
        with pytest.raises(GuardError):
            raise PolicyError("policy violated")

    def test_message(self):
        try:
            raise PolicyError("rule blocked")
        except PolicyError as e:
            assert str(e) == "rule blocked"


class TestFixError:
    def test_is_guard_error(self):
        with pytest.raises(GuardError):
            raise FixError("cannot fix")

    def test_structured_fields(self):
        """FixError accepts optional original and attempt keyword fields."""
        try:
            raise FixError("fix failed", original={"x": 1}, attempt={"x": "1"})
        except FixError as e:
            assert e.original == {"x": 1}
            assert e.attempt == {"x": "1"}
            assert "fix failed" in str(e)

    def test_fields_default_to_none(self):
        """original and attempt default to None when not provided."""
        try:
            raise FixError("bare error")
        except FixError as e:
            assert e.original is None
            assert e.attempt is None

    def test_message_with_details(self):
        try:
            raise FixError("fix failed: bad → good")
        except FixError as e:
            assert "fix failed" in str(e)
            assert "good" in str(e)


class TestGuardTimeoutError:
    def test_is_guard_error(self):
        with pytest.raises(GuardError):
            raise GuardTimeoutError("timeout in schema layer")

    def test_layer_field(self):
        """GuardTimeoutError accepts optional layer keyword field."""
        try:
            raise GuardTimeoutError("timed out", layer="policy")
        except GuardTimeoutError as e:
            assert e.layer == "policy"
            assert "timed out" in str(e)

    def test_layer_defaults_to_none(self):
        """layer defaults to None when not provided."""
        try:
            raise GuardTimeoutError("bare timeout")
        except GuardTimeoutError as e:
            assert e.layer is None

    def test_message_contains_layer(self):
        try:
            raise GuardTimeoutError("timed out in policy layer")
        except GuardTimeoutError as e:
            assert "policy" in str(e)


class TestConfigError:
    def test_is_guard_error(self):
        with pytest.raises(GuardError):
            raise ConfigError("bad config")

    def test_message(self):
        try:
            raise ConfigError("invalid policy path")
        except ConfigError as e:
            assert "invalid policy path" in str(e)
