"""Direct unit tests for schema_fixer.py — auto-fixing logic."""
import pytest
from agentguard.fix.schema_fixer import fix_schema_output


class TestFixSchemaOutput:
    def test_no_fix_needed(self):
        output = {"name": "Alice", "age": 30}
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "age": {"type": "integer"},
            },
        }
        fixed, log = fix_schema_output(output, schema)
        assert fixed == output
        assert log == []

    def test_required_field_default_fill(self):
        output = {"name": "Alice"}
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "role": {"type": "string", "default": "user"},
            },
            "required": ["name", "role"],
        }
        fixed, log = fix_schema_output(output, schema)
        assert fixed["role"] == "user"
        assert any(f["field"] == "role" and f["fixed"] for f in log)

    def test_required_field_fallback_fill(self):
        output = {}
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        fixed, log = fix_schema_output(output, schema)
        assert "name" in fixed
        assert fixed["name"] == ""  # fallback empty string

    def test_type_coercion_str_to_int(self):
        output = {"count": "42"}
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
        }
        fixed, log = fix_schema_output(output, schema)
        assert fixed["count"] == 42
        assert any(f["action"] == "type_coerce" for f in log)

    def test_type_coercion_str_to_bool(self):
        output = {"active": "true"}
        schema = {
            "type": "object",
            "properties": {
                "active": {"type": "boolean"},
            },
        }
        fixed, log = fix_schema_output(output, schema)
        assert fixed["active"] is True
        assert any(f["action"] == "type_coerce" for f in log)

    def test_enum_fix(self):
        output = {"method": "DELTE"}
        schema = {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                },
            },
        }
        fixed, log = fix_schema_output(output, schema)
        assert fixed["method"] == "DELETE"
        assert any(f["action"] == "enum_fix" for f in log)

    def test_strict_mode_strips_unknown(self):
        output = {"name": "Alice", "extra": "field"}
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        }
        fixed, log = fix_schema_output(output, schema, strict_mode=True)
        assert "extra" not in fixed
        assert any(f["action"] == "strip" for f in log)

    def test_json_string_input(self):
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
            },
            "required": ["name"],
        }
        fixed, log = fix_schema_output('{"name": "Alice"}', schema)
        assert fixed["name"] == "Alice"

    def test_invalid_json_string(self):
        schema = {"type": "object"}
        fixed, log = fix_schema_output("not json", schema)
        # Should return original and error entry
        assert log[0]["fixed"] is False
        assert "JSON" in log[0]["error"]

    def test_non_dict_output(self):
        fixed, log = fix_schema_output(42, {"type": "object"})
        assert fixed == 42
        assert log == []

    def test_number_type_handling(self):
        """JSON Schema 'number' should handle both int and float."""
        output = {"price": 100}
        schema = {
            "type": "object",
            "properties": {
                "price": {"type": "number"},
            },
        }
        fixed, log = fix_schema_output(output, schema)
        # int should be left as-is (compatible with number type)
        assert fixed["price"] == 100
        assert log == []

    def test_number_type_str_coercion(self):
        output = {"price": "49.99"}
        schema = {
            "type": "object",
            "properties": {
                "price": {"type": "number"},
            },
        }
        fixed, log = fix_schema_output(output, schema)
        assert isinstance(fixed["price"], (int, float))
        assert any(f["action"] == "type_coerce" for f in log)

    def test_nested_object_fixing(self):
        """Nested objects should be recursively fixed."""
        output = {"config": {"host": "localhost", "port": "8080"}}
        schema = {
            "type": "object",
            "properties": {
                "config": {
                    "type": "object",
                    "properties": {
                        "host": {"type": "string"},
                        "port": {"type": "integer"},
                    },
                },
            },
        }
        fixed, log = fix_schema_output(output, schema)
        assert fixed["config"]["host"] == "localhost"
        assert fixed["config"]["port"] == 8080
        assert any("port" in f["field"] for f in log)

    def test_deeply_nested(self):
        """Three levels of nesting should still work."""
        output = {
            "app": {
                "database": {
                    "host": "db.example.com",
                    "port": "5432",
                }
            }
        }
        schema = {
            "type": "object",
            "properties": {
                "app": {
                    "type": "object",
                    "properties": {
                        "database": {
                            "type": "object",
                            "properties": {
                                "host": {"type": "string"},
                                "port": {"type": "integer"},
                            },
                        },
                    },
                },
            },
        }
        fixed, log = fix_schema_output(output, schema)
        assert fixed["app"]["database"]["host"] == "db.example.com"
        assert fixed["app"]["database"]["port"] == 5432

    def test_enum_and_type_together(self):
        """Fix both enum and type issues simultaneously."""
        output = {"method": "DELTE", "count": "42"}
        schema = {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"],
                },
                "count": {"type": "integer"},
            },
        }
        fixed, log = fix_schema_output(output, schema)
        assert fixed["method"] == "DELETE"
        assert fixed["count"] == 42
        # Should have two fixes
        fix_actions = [f["action"] for f in log]
        assert "enum_fix" in fix_actions
        assert "type_coerce" in fix_actions

    def test_required_field_no_default(self):
        """Required field with no default should still attempt fallback."""
        output = {}
        schema = {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "count": {"type": "integer"},
                "active": {"type": "boolean"},
                "items": {"type": "array"},
                "meta": {"type": "object"},
            },
            "required": ["status", "count", "active", "items", "meta"],
        }
        fixed, log = fix_schema_output(output, schema)
        # All should be filled with type-appropriate empty values
        assert fixed["status"] == ""        # empty string
        assert fixed["count"] == 0          # zero
        assert fixed["active"] is False     # false
        assert fixed["items"] == []         # empty list
        assert fixed["meta"] == {}          # empty dict
