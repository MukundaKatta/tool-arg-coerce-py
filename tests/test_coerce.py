"""Tests for tool_arg_coerce."""

from __future__ import annotations

import pytest

from tool_arg_coerce import CoerceError, coerce, coerce_value


# ---- coerce_value: integer ------------------------------------------------


def test_int_passthrough():
    v, w = coerce_value(5, "integer")
    assert v == 5 and w == []


def test_str_to_int_warns():
    v, w = coerce_value("5", "integer")
    assert v == 5
    assert any("coerced" in msg and "int" in msg for msg in w)


def test_str_float_to_int_when_integral():
    v, w = coerce_value("5.0", "integer")
    assert v == 5
    assert w  # warning recorded


def test_str_non_integer_fails():
    v, w = coerce_value("5.5", "integer")
    assert v == "5.5"  # fallback: return original
    assert w == []  # no warning when not coerced


def test_bool_not_treated_as_int():
    # bool is int subclass in Python; we explicitly reject it
    v, w = coerce_value(True, "integer")
    assert v is True
    assert w == []


def test_strict_raises_on_uncoercible_int():
    with pytest.raises(CoerceError) as exc:
        coerce_value("abc", "integer", strict=True)
    assert exc.value.target_type == "integer"
    assert exc.value.value == "abc"


# ---- coerce_value: number ------------------------------------------------


def test_str_to_number():
    v, w = coerce_value("3.14", "number")
    assert v == 3.14
    assert w


def test_int_to_number_passthrough():
    v, w = coerce_value(7, "number")
    assert v == 7 and w == []


# ---- coerce_value: boolean ----------------------------------------------


@pytest.mark.parametrize(
    "s, expected", [("true", True), ("True", True), ("1", True), ("yes", True),
                    ("false", False), ("FALSE", False), ("0", False), ("no", False)],
)
def test_bool_truthy_falsy_strings(s, expected):
    v, w = coerce_value(s, "boolean")
    assert v is expected
    assert w  # warning


def test_bool_passthrough():
    v, w = coerce_value(True, "boolean")
    assert v is True and w == []


def test_int_0_1_to_bool():
    assert coerce_value(1, "boolean")[0] is True
    assert coerce_value(0, "boolean")[0] is False


def test_int_2_not_to_bool():
    v, w = coerce_value(2, "boolean")
    assert v == 2  # no coercion
    assert w == []


def test_bool_unknown_string_falls_back():
    v, w = coerce_value("maybe", "boolean")
    assert v == "maybe"
    assert w == []


# ---- coerce_value: string -----------------------------------------------


def test_str_passthrough():
    v, w = coerce_value("hi", "string")
    assert v == "hi" and w == []


def test_int_to_str_warns():
    v, w = coerce_value(42, "string")
    assert v == "42"
    assert w


# ---- coerce_value: array & object ---------------------------------------


def test_array_passthrough():
    v, w = coerce_value([1, 2], "array")
    assert v == [1, 2] and w == []


def test_json_string_to_array():
    v, w = coerce_value('["a","b"]', "array")
    assert v == ["a", "b"]
    assert w


def test_object_passthrough():
    v, w = coerce_value({"a": 1}, "object")
    assert v == {"a": 1} and w == []


def test_json_string_to_object():
    v, w = coerce_value('{"a":1}', "object")
    assert v == {"a": 1}
    assert w


def test_invalid_json_string_falls_back():
    v, w = coerce_value("not json", "array")
    assert v == "not json"
    assert w == []


# ---- coerce_value: null --------------------------------------------------


def test_none_to_null():
    v, w = coerce_value(None, "null")
    assert v is None and w == []


@pytest.mark.parametrize("s", ["null", "None", ""])
def test_str_to_null(s):
    v, w = coerce_value(s, "null")
    assert v is None
    assert w


# ---- coerce (whole args) -------------------------------------------------


SCHEMA = {
    "type": "object",
    "properties": {
        "q": {"type": "string"},
        "n": {"type": "integer"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "active": {"type": "boolean"},
    },
}


def test_coerce_fixes_mixed_types():
    args = {"q": "anthropic", "n": "5", "tags": '["a","b"]', "active": "true"}
    fixed, warnings = coerce(args, SCHEMA)
    assert fixed == {"q": "anthropic", "n": 5, "tags": ["a", "b"], "active": True}
    assert len(warnings) >= 3


def test_coerce_passes_through_unknown_keys():
    args = {"q": "x", "extra": {"deep": 1}}
    fixed, _ = coerce(args, SCHEMA)
    assert fixed["extra"] == {"deep": 1}


def test_coerce_no_op_when_already_right_type():
    args = {"q": "x", "n": 5, "tags": ["a"], "active": True}
    fixed, warnings = coerce(args, SCHEMA)
    assert fixed == args
    assert warnings == []


def test_coerce_array_items_coerced():
    schema = {"type": "object", "properties": {
        "ids": {"type": "array", "items": {"type": "integer"}},
    }}
    fixed, w = coerce({"ids": ["1", "2", "3"]}, schema)
    assert fixed["ids"] == [1, 2, 3]
    assert len(w) == 3


def test_coerce_nested_object_recursed():
    schema = {"type": "object", "properties": {
        "filter": {"type": "object", "properties": {
            "active": {"type": "boolean"},
            "n": {"type": "integer"},
        }},
    }}
    fixed, w = coerce({"filter": {"active": "yes", "n": "10"}}, schema)
    assert fixed == {"filter": {"active": True, "n": 10}}


def test_coerce_strict_raises():
    args = {"n": "not a number"}
    with pytest.raises(CoerceError):
        coerce(args, SCHEMA, strict=True)


def test_coerce_non_dict_args_strict_raises():
    with pytest.raises(CoerceError):
        coerce("not a dict", SCHEMA, strict=True)  # type: ignore[arg-type]


def test_coerce_returns_warnings_with_paths():
    args = {"n": "5"}
    _, warnings = coerce(args, SCHEMA)
    assert any("$.n" in w for w in warnings)
