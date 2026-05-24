# tool-arg-coerce-py

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/tool-arg-coerce-py.svg)](https://pypi.org/project/tool-arg-coerce-py/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Python port of [tool-arg-coerce](https://crates.io/crates/tool-arg-coerce).** Fix common LLM type mistakes in tool args before validation. Zero deps.

```python
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
```

The LLM produced `"5"` when your schema asks for `integer`. It produced `"true"` instead of a boolean. It JSON-encoded an array into a string. You could surface a validation error and waste a turn round-tripping the model's typo. `tool-arg-coerce-py` fixes the easy cases first.

## What it does

- `"5"` / `"5.0"` → `5` when target is `integer`
- `"3.14"` → `3.14` when target is `number`
- `"true"` / `"yes"` / `"1"` / `"on"` → `True`; `"false"` / `"no"` / `"0"` / `"off"` → `False`
- `42` → `"42"` when target is `string`
- `'["a","b"]'` → `["a", "b"]` when target is `array`
- `'{"a":1}'` → `{"a": 1}` when target is `object`
- `"null"` / `"None"` / `""` → `None` when target is `null`
- Recurses into `array.items` and `object.properties`
- Treats `bool` as **not** an integer (Python's `bool < int` subclass quirk)

What it does NOT do: full JSON-schema validation. For that, follow up with [`agentvet`](https://github.com/MukundaKatta/agentvet).

In strict mode, coercion failures raise `CoerceError(path, value, target_type)`. Default mode returns the original value untouched with no warning — the lib is for the easy cases.

## Install

```bash
pip install tool-arg-coerce-py
```

## API

```python
from tool_arg_coerce import coerce, coerce_value, CoerceError

# top-level
coerce(args: dict, schema: dict, strict=False) -> (dict, list[str])

# single value
coerce_value(value, target_type: str, path="$", strict=False) -> (Any, list[str])
```

## Companion libraries

The full pipeline for an LLM tool call:

```
LLM args
  ↓ tool-arg-defaults.apply    fill missing kwargs
  ↓ tool-arg-coerce-py.coerce  fix type mistakes
  ↓ agentvet.validate          strict schema check
  ↓ tool(...)
```

- Rust: [`tool-arg-coerce`](https://crates.io/crates/tool-arg-coerce) — this lib's sibling crate.
- [`tool-arg-defaults`](https://github.com/MukundaKatta/tool-arg-defaults) — fill in missing kwargs before coercion.
- [`agentvet`](https://github.com/MukundaKatta/agentvet) — strict validation after coercion.
- [`tool-schema-from-fn`](https://github.com/MukundaKatta/tool-schema-from-fn) — generate the schema you'll pass here.

## License

MIT
