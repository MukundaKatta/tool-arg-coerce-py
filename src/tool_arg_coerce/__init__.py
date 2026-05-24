"""tool-arg-coerce - fix common LLM type mistakes in tool args.

LLMs hallucinate types. They produce `"5"` when the schema asks for an
integer. They produce `"true"` instead of a boolean. They sometimes JSON-
encode arrays into a string. `coerce()` walks the args against a JSON
Schema and fixes the easy cases before validation, so your agent loop
doesn't waste a turn round-tripping a one-character typo.

    from tool_arg_coerce import coerce

    schema = {
        "type": "object",
        "properties": {
            "q": {"type": "string"},
            "n": {"type": "integer"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "active": {"type": "boolean"},
        },
    }

    args = {"q": "anthropic", "n": "5", "tags": '["a","b"]', "active": "true"}
    fixed, warnings = coerce(args, schema)
    # fixed == {"q": "anthropic", "n": 5, "tags": ["a", "b"], "active": True}
    # warnings == ["n: coerced str '5' to int", ...]

Pass `strict=True` to raise `CoerceError` instead of returning warnings.
Unknown types and structural mismatches return the value unchanged with
no warning — this lib is for the easy cases. For full validation, follow
up with [`agentvet`](https://github.com/MukundaKatta/agentvet).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

__version__ = "0.1.0"
__all__ = [
    "coerce",
    "coerce_value",
    "CoerceError",
    "CoerceResult",
]


class CoerceError(ValueError):
    """Raised in strict mode when a value can't be coerced."""

    def __init__(self, path: str, value: Any, target_type: str):
        self.path = path
        self.value = value
        self.target_type = target_type
        super().__init__(
            f"{path}: could not coerce {value!r} to {target_type}"
        )


@dataclass
class CoerceResult:
    """Container for `coerce()` output."""

    value: Any
    warnings: list[str]


# ---- single-value coercion ------------------------------------------------


_TRUTHY = {"true", "1", "yes", "on", "y", "t"}
_FALSY = {"false", "0", "no", "off", "n", "f"}


def coerce_value(
    value: Any,
    target_type: str,
    *,
    path: str = "$",
    strict: bool = False,
) -> tuple[Any, list[str]]:
    """Coerce one value to a JSON Schema `type` name.

    Supported targets: "string", "integer", "number", "boolean", "array",
    "object", "null". For "array" and "object" we also accept a JSON-encoded
    string (`'[1,2]'` → `[1, 2]`, `'{"a":1}'` → `{"a": 1}`).
    """
    warnings: list[str] = []

    if target_type == "string":
        if isinstance(value, str):
            return value, warnings
        if isinstance(value, (int, float, bool)):
            warnings.append(f"{path}: coerced {type(value).__name__} to str")
            return str(value), warnings
        return _fail(strict, path, value, "string", value, warnings)

    if target_type == "integer":
        return _to_int(value, path, strict, warnings)

    if target_type == "number":
        return _to_number(value, path, strict, warnings)

    if target_type == "boolean":
        return _to_bool(value, path, strict, warnings)

    if target_type == "array":
        if isinstance(value, list):
            return value, warnings
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                return _fail(strict, path, value, "array", value, warnings)
            if isinstance(parsed, list):
                warnings.append(f"{path}: parsed JSON string to array")
                return parsed, warnings
        return _fail(strict, path, value, "array", value, warnings)

    if target_type == "object":
        if isinstance(value, dict):
            return value, warnings
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError):
                return _fail(strict, path, value, "object", value, warnings)
            if isinstance(parsed, dict):
                warnings.append(f"{path}: parsed JSON string to object")
                return parsed, warnings
        return _fail(strict, path, value, "object", value, warnings)

    if target_type == "null":
        if value is None:
            return value, warnings
        if isinstance(value, str) and value.lower() in {"null", "none", ""}:
            warnings.append(f"{path}: coerced {value!r} to None")
            return None, warnings
        return _fail(strict, path, value, "null", value, warnings)

    # unknown target type — return as-is
    return value, warnings


# ---- whole-args coercion -------------------------------------------------


def coerce(
    args: dict[str, Any],
    schema: dict[str, Any],
    *,
    strict: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    """Coerce a dict of args against the top-level schema.

    Only the `properties` mapping of the top-level schema is consulted;
    nested objects ARE recursed into when their `type` is "object" and
    `properties` is supplied. Arrays with `items` schema get each element
    coerced. Unknown properties pass through unchanged.
    """
    if not isinstance(args, dict):
        if strict:
            raise CoerceError("$", args, "object")
        return args, []  # type: ignore[return-value]

    out: dict[str, Any] = {}
    warnings: list[str] = []
    props = schema.get("properties") or {}

    for key, value in args.items():
        sub_schema = props.get(key)
        if sub_schema is None:
            out[key] = value
            continue
        target = sub_schema.get("type")
        if target is None:
            out[key] = value
            continue
        path = f"$.{key}"
        coerced, sub_warnings = _coerce_recursive(
            value, sub_schema, path=path, strict=strict
        )
        out[key] = coerced
        warnings.extend(sub_warnings)

    return out, warnings


def _coerce_recursive(
    value: Any,
    schema: dict[str, Any],
    *,
    path: str,
    strict: bool,
) -> tuple[Any, list[str]]:
    target = schema.get("type")
    if target is None:
        return value, []

    if target == "object":
        coerced, w = coerce_value(value, "object", path=path, strict=strict)
        if not isinstance(coerced, dict) or "properties" not in schema:
            return coerced, w
        nested_out = {}
        nested_warnings = list(w)
        for k, v in coerced.items():
            sub = schema["properties"].get(k)
            if sub is None or sub.get("type") is None:
                nested_out[k] = v
                continue
            nv, nw = _coerce_recursive(
                v, sub, path=f"{path}.{k}", strict=strict
            )
            nested_out[k] = nv
            nested_warnings.extend(nw)
        return nested_out, nested_warnings

    if target == "array":
        coerced, w = coerce_value(value, "array", path=path, strict=strict)
        items_schema = schema.get("items")
        if not isinstance(coerced, list) or not isinstance(items_schema, dict):
            return coerced, w
        items_target = items_schema.get("type")
        if items_target is None:
            return coerced, w
        new_items = []
        item_warnings = list(w)
        for i, item in enumerate(coerced):
            iv, iw = _coerce_recursive(
                item, items_schema, path=f"{path}[{i}]", strict=strict
            )
            new_items.append(iv)
            item_warnings.extend(iw)
        return new_items, item_warnings

    return coerce_value(value, target, path=path, strict=strict)


# ---- helpers --------------------------------------------------------------


def _to_int(value: Any, path: str, strict: bool, warnings: list[str]):
    if isinstance(value, bool):  # bool is int subclass; check first
        return _fail(strict, path, value, "integer", value, warnings)
    if isinstance(value, int):
        return value, warnings
    if isinstance(value, float):
        if value.is_integer():
            warnings.append(f"{path}: coerced float {value} to int")
            return int(value), warnings
        return _fail(strict, path, value, "integer", value, warnings)
    if isinstance(value, str):
        try:
            n = int(value)
        except (TypeError, ValueError):
            try:
                f = float(value)
            except (TypeError, ValueError):
                return _fail(strict, path, value, "integer", value, warnings)
            if f.is_integer():
                warnings.append(f"{path}: coerced str {value!r} to int")
                return int(f), warnings
            return _fail(strict, path, value, "integer", value, warnings)
        warnings.append(f"{path}: coerced str {value!r} to int")
        return n, warnings
    return _fail(strict, path, value, "integer", value, warnings)


def _to_number(value: Any, path: str, strict: bool, warnings: list[str]):
    if isinstance(value, bool):
        return _fail(strict, path, value, "number", value, warnings)
    if isinstance(value, (int, float)):
        return value, warnings
    if isinstance(value, str):
        try:
            f = float(value)
        except (TypeError, ValueError):
            return _fail(strict, path, value, "number", value, warnings)
        warnings.append(f"{path}: coerced str {value!r} to number")
        return f, warnings
    return _fail(strict, path, value, "number", value, warnings)


def _to_bool(value: Any, path: str, strict: bool, warnings: list[str]):
    if isinstance(value, bool):
        return value, warnings
    if isinstance(value, str):
        low = value.lower().strip()
        if low in _TRUTHY:
            warnings.append(f"{path}: coerced str {value!r} to True")
            return True, warnings
        if low in _FALSY:
            warnings.append(f"{path}: coerced str {value!r} to False")
            return False, warnings
        return _fail(strict, path, value, "boolean", value, warnings)
    if isinstance(value, int):
        # 0/1 only; other ints feel like a type mistake, not a bool
        if value in (0, 1):
            warnings.append(f"{path}: coerced int {value} to bool")
            return bool(value), warnings
        return _fail(strict, path, value, "boolean", value, warnings)
    return _fail(strict, path, value, "boolean", value, warnings)


def _fail(
    strict: bool,
    path: str,
    value: Any,
    target: str,
    fallback: Any,
    warnings: list[str],
):
    if strict:
        raise CoerceError(path, value, target)
    return fallback, warnings
