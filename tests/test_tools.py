"""
tests/test_tools.py — Tool behavior, focused on the arithmetic sandbox.

The calculator previously used eval() with {"__builtins__": {}}, which is not a
sandbox. These tests pin the escapes shut.
"""

import pytest

from registries.tool_registry import SCHEMA_REGISTRY, TOOL_REGISTRY
from tools.general_tools import calculate, safe_eval


class TestSafeEval:
    """The AST evaluator must do real arithmetic and nothing else."""

    @pytest.mark.parametrize(
        "expression,expected",
        [
            ("2 + 2", 4),
            ("(25 * 4) + 10", 110),
            ("15 * 890 / 100", 133.5),
            ("2 ** 10", 1024),
            ("-5 + 3", -2),
            ("17 % 5", 2),
            ("17 // 5", 3),
            ("((2 + 3) * (4 - 1)) / 5", 3.0),
        ],
    )
    def test_evaluates_arithmetic(self, expression, expected):
        assert safe_eval(expression) == expected

    @pytest.mark.parametrize(
        "expression",
        [
            # The classic eval escape: reach object internals, then subclasses,
            # then anything at all.
            "().__class__.__base__.__subclasses__()",
            "__import__('os').system('echo pwned')",
            "open('/etc/passwd').read()",
            "[x for x in range(10)]",
            "lambda: 1",
            "globals()",
            "'a' * 10",
            "x + 1",
            "print(1)",
        ],
    )
    def test_rejects_non_arithmetic(self, expression):
        with pytest.raises(ValueError):
            safe_eval(expression)

    def test_rejects_huge_exponent(self):
        """9**9**9 parses as valid arithmetic but would hang the agent loop."""
        with pytest.raises(ValueError, match="exponent too large"):
            safe_eval("9**9**9")

    def test_rejects_booleans_as_numbers(self):
        with pytest.raises(ValueError):
            safe_eval("True + 1")

    def test_rejects_syntax_error(self):
        with pytest.raises(ValueError, match="could not parse"):
            safe_eval("2 +")


class TestCalculateTool:
    """The tool wrapper returns strings — never raises — so the agent can recover."""

    def test_returns_result_string(self):
        assert "110" in calculate("(25 * 4) + 10")

    def test_division_by_zero_is_a_message(self):
        assert "division by zero" in calculate("5 / 0")

    def test_escape_attempt_is_a_message_not_an_exception(self):
        result = calculate("().__class__.__base__.__subclasses__()")
        assert "error" in result.lower()
        assert "not allowed" in result


class TestToolRegistration:
    """The @tool decorator must register callables and derive matching schemas."""

    def test_every_tool_has_a_schema(self):
        assert set(TOOL_REGISTRY) == set(SCHEMA_REGISTRY)

    def test_schema_names_match_registry_keys(self):
        for name, schema in SCHEMA_REGISTRY.items():
            assert schema["function"]["name"] == name

    def test_derives_parameters_from_annotations(self):
        params = SCHEMA_REGISTRY["request_refund"]["function"]["parameters"]
        assert params["required"] == ["order_id", "reason"]
        assert params["properties"]["order_id"]["type"] == "string"
        # Annotated metadata becomes the parameter description.
        assert "HZ002" in params["properties"]["order_id"]["description"]

    def test_zero_argument_tool_has_empty_properties(self):
        params = SCHEMA_REGISTRY["get_current_time"]["function"]["parameters"]
        assert params["properties"] == {}
        assert params["required"] == []
