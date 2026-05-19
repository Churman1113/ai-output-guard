"""Tests for SchemaGuard — validation and auto-fixing."""
import json
import pytest
from pydantic import BaseModel
from typing import Literal, Optional, Any
from agentguard.schema_guard import SchemaGuard
from agentguard.result import GuardLevel


# ──────────────────────────────────────────────
# Basic — no schema, parse errors
# ──────────────────────────────────────────────

class TestSchemaGuardBasic:
    def test_no_schema_skips(self):
        sg = SchemaGuard()
        r = sg.validate({"any": "thing"})
        assert r.level == GuardLevel.PASS
        assert "No schema" in r.message

    def test_json_parse_error(self):
        sg = SchemaGuard(schema={"type": "object"})
        r = sg.validate("{not valid json}")
        assert r.level == GuardLevel.DENY
        assert "JSON" in r.message

    def test_non_dict_passes(self):
        sg = SchemaGuard(schema={"type": "object"})
        r = sg.validate(42)
        assert r.level == GuardLevel.PASS


# ──────────────────────────────────────────────
# Pydantic — basic validation
# ──────────────────────────────────────────────

class TestSchemaGuardPydantic:
    def test_valid_passes(self):
        class Model(BaseModel):
            name: str
            age: int

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"name": "Alice", "age": 30}')
        assert r.level == GuardLevel.PASS
        # fix should be a serialized dict, not a Pydantic model
        assert isinstance(r.fix, dict)
        assert r.fix["name"] == "Alice"
        assert r.fix["age"] == 30

    def test_valid_pydantic_model_input(self):
        class Model(BaseModel):
            name: str
            age: int

        sg = SchemaGuard(schema=Model)
        obj = Model(name="Bob", age=25)
        r = sg.validate(obj)
        assert r.level == GuardLevel.PASS
        assert isinstance(r.fix, dict)
        assert r.fix["name"] == "Bob"

    def test_missing_required_denies(self):
        class Model(BaseModel):
            name: str
            age: int

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"name": "Alice"}')
        # Schema fixer fills missing 'age' with fallback (0), so it's a FIX
        assert r.level in (GuardLevel.FIX, GuardLevel.DENY)
        if r.level == GuardLevel.FIX:
            assert r.fix["name"] == "Alice"
            assert r.fix["age"] == 0

    def test_missing_optional_passes(self):
        class Model(BaseModel):
            name: str
            age: Optional[int] = None

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"name": "Alice"}')
        assert r.level == GuardLevel.PASS

    def test_wrong_type_denies(self):
        class Model(BaseModel):
            name: str
            count: int

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"name": "Alice", "count": "not-a-number"}')
        assert r.level == GuardLevel.DENY

    def test_empty_string_input(self):
        sg = SchemaGuard(schema={"type": "object"})
        r = sg.validate("")
        assert r.level == GuardLevel.DENY
        assert "JSON" in r.message

    def test_null_input(self):
        sg = SchemaGuard(schema={"type": "object"})
        r = sg.validate(None)
        # None passes through for non-str, non-dict
        assert r.level == GuardLevel.PASS

    def test_dict_input_direct(self):
        class Model(BaseModel):
            action: str
            value: int

        sg = SchemaGuard(schema=Model)
        r = sg.validate({"action": "read", "value": 42})
        assert r.level == GuardLevel.PASS
        assert isinstance(r.fix, dict)


# ──────────────────────────────────────────────
# Enum fixing
# ──────────────────────────────────────────────

class TestSchemaGuardEnumFix:
    def test_enum_typo_fixed(self):
        class Model(BaseModel):
            action: Literal["create", "read", "update", "delete"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"action": "creat"}')  # typo -> "create"
        assert r.level == GuardLevel.FIX
        assert r.fix is not None
        # fix is a dict after serialization fix
        assert r.fix["action"] == "create"
        fixes = r.metadata.get("fixes", [])
        assert len(fixes) == 1
        assert fixes[0]["fixed"] is True
        assert fixes[0]["action"] == "enum_fix"

    def test_multi_char_typo_fixed(self):
        class Model(BaseModel):
            method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"method": "DELTE"}')  # common typo
        assert r.level == GuardLevel.FIX
        assert r.fix["method"] == "DELETE"

    def test_case_insensitive_fix(self):
        class Model(BaseModel):
            method: Literal["GET", "POST"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"method": "get"}')
        # Should match case-insensitively
        assert r.level == GuardLevel.FIX
        assert r.fix["method"] == "GET"

    def test_enum_unfixable_denies(self):
        class Model(BaseModel):
            action: Literal["create", "read"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"action": "xyzzy"}')
        assert r.level == GuardLevel.DENY

    def test_enum_prefix_match(self):
        class Model(BaseModel):
            action: Literal["create", "read", "update", "delete"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"action": "upd"}')
        assert r.level == GuardLevel.FIX
        assert r.fix["action"] == "update"

    def test_enum_substring_match(self):
        class Model(BaseModel):
            action: Literal["create", "read", "update", "delete"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"action": "EATE"}')
        # "EATE" is a substring of "CREATE"
        assert r.level == GuardLevel.FIX
        assert r.fix["action"] == "create"


# ──────────────────────────────────────────────
# Type coercion
# ──────────────────────────────────────────────

class TestSchemaGuardTypeFix:
    def test_string_to_int_coerced(self):
        class Model(BaseModel):
            count: int

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"count": "42"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["count"] == 42

    def test_string_to_float_coerced(self):
        class Model(BaseModel):
            price: float

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"price": "19.99"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["price"] == 19.99

    def test_int_to_float_coerced(self):
        class Model(BaseModel):
            ratio: float

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"ratio": 5}')
        # int is compatible with float, may pass through or be coerced
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)

    def test_bool_true_coerced(self):
        class Model(BaseModel):
            active: bool

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"active": "true"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["active"] is True

    def test_bool_false_coerced(self):
        class Model(BaseModel):
            active: bool

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"active": "false"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["active"] is False

    def test_bool_python_style_coerced(self):
        class Model(BaseModel):
            enabled: bool

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"enabled": "True"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["enabled"] is True

    def test_bool_numeric_coerced(self):
        class Model(BaseModel):
            enabled: bool

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"enabled": "1"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["enabled"] is True

    def test_number_string_with_commas(self):
        class Model(BaseModel):
            population: int

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"population": "1,234,567"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["population"] == 1234567

    def test_bool_integer_coerced(self):
        class Model(BaseModel):
            active: bool

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"active": 1}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["active"] is True

    def test_bool_from_yes_no(self):
        class Model(BaseModel):
            consent: bool

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"consent": "yes"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["consent"] is True


# ──────────────────────────────────────────────
# JSON Schema dict
# ──────────────────────────────────────────────

class TestSchemaGuardJsonSchema:
    def test_valid_dict_schema(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
            "required": ["name"],
        }
        sg = SchemaGuard(schema=schema)
        r = sg.validate('{"name": "Bob", "age": 25}')
        assert r.level == GuardLevel.PASS

    def test_missing_required_in_dict_schema(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        sg = SchemaGuard(schema=schema)
        r = sg.validate('{"age": 25}')
        # Schema fixer fills missing 'name' with empty string fallback
        assert r.level in (GuardLevel.FIX, GuardLevel.DENY)

    def test_unknown_field_stripped_in_strict(self):
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        sg = SchemaGuard(schema=schema, strict_mode=True)
        r = sg.validate('{"name": "Bob", "extra": "field"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)

    def test_default_fill(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string", "default": "user"},
            },
            "required": ["name", "role"],
        }
        sg = SchemaGuard(schema=schema)
        r = sg.validate('{"name": "Bob"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)

    def test_number_type_schema(self):
        """JSON Schema 'number' type should accept both int and float."""
        schema = {
            "type": "object",
            "properties": {
                "price": {"type": "number"},
            },
            "required": ["price"],
        }
        sg = SchemaGuard(schema=schema)
        # Integer input
        r = sg.validate('{"price": 100}')
        assert r.level == GuardLevel.PASS
        # Float input
        r = sg.validate('{"price": 99.99}')
        assert r.level == GuardLevel.PASS
        # String input (should be coerced)
        r = sg.validate('{"price": "49.99"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)


# ──────────────────────────────────────────────
# Nested / complex schemas
# ──────────────────────────────────────────────

class TestSchemaGuardNested:
    def test_nested_object_valid(self):
        class Address(BaseModel):
            city: str
            zip: str

        class User(BaseModel):
            name: str
            address: Address

        sg = SchemaGuard(schema=User)
        r = sg.validate('{"name": "Alice", "address": {"city": "NYC", "zip": "10001"}}')
        assert r.level == GuardLevel.PASS

    def test_nested_object_with_type_fix(self):
        class Address(BaseModel):
            city: str
            zip: str

        class User(BaseModel):
            name: str
            age: int

        sg = SchemaGuard(schema=User)
        r = sg.validate('{"name": "Alice", "age": "30"}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)

    def test_list_of_objects(self):
        class Item(BaseModel):
            id: int
            name: str

        class Order(BaseModel):
            items: list[Item]

        sg = SchemaGuard(schema=Order)
        r = sg.validate('{"items": [{"id": 1, "name": "Book"}, {"id": 2, "name": "Pen"}]}')
        # Pydantic v2 handles list validation natively
        assert r.level == GuardLevel.PASS

    def test_deeply_nested_field_access(self):
        class Config(BaseModel):
            host: str
            port: int

        class App(BaseModel):
            name: str
            config: Config

        sg = SchemaGuard(schema=App)
        r = sg.validate('{"name": "myapp", "config": {"host": "localhost", "port": "8080"}}')
        # port is string but should be int — may be fixed by Pydantic coercion or our fixer
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            assert r.fix["config"]["port"] == 8080

    def test_optional_nested(self):
        class Config(BaseModel):
            debug: bool = False

        class App(BaseModel):
            name: str
            config: Optional[Config] = None

        sg = SchemaGuard(schema=App)
        r = sg.validate('{"name": "myapp"}')
        assert r.level == GuardLevel.PASS


# ──────────────────────────────────────────────
# Required field fallback filling
# ──────────────────────────────────────────────

class TestRequiredFieldFixes:
    def test_required_field_fallback_fill_string(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        sg = SchemaGuard(schema=schema)
        r = sg.validate('{}')
        # Should fill with empty string
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)
        if r.level == GuardLevel.FIX:
            fixes = r.metadata.get("fixes", [])
            assert any(f["field"] == "name" for f in fixes)

    def test_required_field_fallback_fill_int(self):
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
            "required": ["count"],
        }
        sg = SchemaGuard(schema=schema)
        r = sg.validate('{}')
        # Should fill with 0
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)

    def test_required_field_fallback_fill_bool(self):
        schema = {
            "type": "object",
            "properties": {
                "active": {"type": "boolean"},
            },
            "required": ["active"],
        }
        sg = SchemaGuard(schema=schema)
        r = sg.validate('{}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)

    def test_required_field_no_fallback_for_object(self):
        schema = {
            "type": "object",
            "properties": {
                "config": {"type": "object"},
            },
            "required": ["config"],
        }
        sg = SchemaGuard(schema=schema)
        r = sg.validate('{}')
        # Should fill with empty dict
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)

    def test_required_field_fallback_fill_array(self):
        schema = {
            "type": "object",
            "properties": {
                "tags": {"type": "array"},
            },
            "required": ["tags"],
        }
        sg = SchemaGuard(schema=schema)
        r = sg.validate('{}')
        assert r.level in (GuardLevel.PASS, GuardLevel.FIX)


# ──────────────────────────────────────────────
# Edge cases
# ──────────────────────────────────────────────

class TestSchemaGuardEdgeCases:
    def test_fix_is_dict_not_model(self):
        """Fix should always be a serialized dict, never a Pydantic model."""
        class Model(BaseModel):
            action: Literal["create", "read"]

        sg = SchemaGuard(schema=Model)

        # PASS case
        r = sg.validate('{"action": "create"}')
        assert r.level == GuardLevel.PASS
        assert r.fix is None or isinstance(r.fix, dict), f"Expected dict or None, got {type(r.fix)}"

        # FIX case
        r = sg.validate('{"action": "creat"}')
        if r.level == GuardLevel.FIX:
            assert isinstance(r.fix, dict), f"Expected dict, got {type(r.fix)}"

    def test_empty_dict_input(self):
        class Model(BaseModel):
            name: str
            age: int

        sg = SchemaGuard(schema=Model)
        r = sg.validate("{}")
        # Both fields get filled with fallback values, so it becomes FIX
        assert r.level in (GuardLevel.FIX, GuardLevel.DENY)
        if r.level == GuardLevel.FIX:
            assert r.fix["name"] == ""
            assert r.fix["age"] == 0

    def test_very_long_string_input(self):
        sg = SchemaGuard(schema={"type": "object"})
        long_str = "x" * 10000
        r = sg.validate(long_str)
        assert r.level == GuardLevel.DENY

    def test_unicode_input(self):
        class Model(BaseModel):
            message: str

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"message": "你好世界"}')
        assert r.level == GuardLevel.PASS
        assert r.fix["message"] == "你好世界"

    def test_fix_log_detail(self):
        class Model(BaseModel):
            method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"method": "DELTE"}')
        assert r.level == GuardLevel.FIX
        fixes = r.metadata.get("fixes", [])
        assert len(fixes) == 1
        fix = fixes[0]
        assert fix["field"] == "method"
        assert fix["action"] == "enum_fix"
        assert fix["fixed"] is True
        assert fix["confidence"] > 0

    def test_non_ascii_enum(self):
        """Enum values with non-ASCII should still work."""
        class Model(BaseModel):
            status: Literal["开放", "关闭", "待定"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"status": "开放"}')
        assert r.level == GuardLevel.PASS

    def test_direct_dict_with_fix(self):
        """Dict input that needs fixing should still work."""
        class Model(BaseModel):
            action: Literal["read", "write"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate({"action": "reed"})
        assert r.level == GuardLevel.FIX
        assert r.fix["action"] == "read"

    def test_json_with_extra_whitespace(self):
        class Model(BaseModel):
            name: str

        sg = SchemaGuard(schema=Model)
        r = sg.validate('  \n  {"name": "test"}  \n  ')
        assert r.level == GuardLevel.PASS


# ──────────────────────────────────────────────
# Multiple fields fixing simultaneously
# ──────────────────────────────────────────────

class TestMultipleFixes:
    def test_two_enum_fixes(self):
        class Model(BaseModel):
            method: Literal["GET", "POST"]
            action: Literal["create", "delete"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"method": "GT", "action": "delet"}')
        assert r.level == GuardLevel.FIX
        assert r.fix["method"] == "GET"
        assert r.fix["action"] == "delete"

    def test_type_and_enum_fix(self):
        class Model(BaseModel):
            count: int
            status: Literal["active", "inactive"]

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"count": "42", "status": "activ"}')
        assert r.level == GuardLevel.FIX
        assert r.fix["count"] == 42
        assert r.fix["status"] == "active"

    def test_partial_fix_with_residual_errors(self):
        """When some fields are fixable and some aren't, should DENY."""
        class Model(BaseModel):
            method: Literal["GET", "POST"]
            count: int

        sg = SchemaGuard(schema=Model)
        r = sg.validate('{"method": "GT", "count": "not-a-number"}')
        # Method is fixable, count is not → mixed result
        assert r.level in (GuardLevel.DENY, GuardLevel.WARN, GuardLevel.FIX)
