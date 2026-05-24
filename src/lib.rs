//! # tool-arg-coerce
//!
//! Fix common type slips in LLM-generated tool arguments.
//!
//! LLMs often emit `"42"` instead of `42` for an integer argument,
//! `["x"]` instead of `"x"` when the schema wants a scalar, or
//! `"true"` for a bool. This crate gives you a `coerce_one` function
//! that fixes the obvious cases for a single value, and `coerce_args`
//! that walks an object against a typed schema.
//!
//! ## Example
//!
//! ```
//! use tool_arg_coerce::{coerce_one, Type};
//! use serde_json::json;
//!
//! assert_eq!(coerce_one(json!("42"), Type::Int), Some(json!(42)));
//! assert_eq!(coerce_one(json!("true"), Type::Bool), Some(json!(true)));
//! assert_eq!(coerce_one(json!(["only"]), Type::String), Some(json!("only")));
//! ```

#![deny(missing_docs)]

use serde_json::{json, Value};

/// Target type for coercion.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Type {
    /// Signed 64-bit integer.
    Int,
    /// f64.
    Float,
    /// Bool.
    Bool,
    /// String.
    String,
}

/// Coerce one value to `ty`. Returns `None` if no obvious fix exists.
pub fn coerce_one(v: Value, ty: Type) -> Option<Value> {
    // Single-element array -> scalar.
    let v = if let Value::Array(ref arr) = v {
        if arr.len() == 1 {
            arr[0].clone()
        } else {
            v
        }
    } else {
        v
    };

    match ty {
        Type::Int => match v {
            Value::Number(n) => n.as_i64().map(|i| json!(i)),
            Value::String(s) => s.trim().parse::<i64>().ok().map(|i| json!(i)),
            Value::Bool(b) => Some(json!(if b { 1 } else { 0 })),
            _ => None,
        },
        Type::Float => match v {
            Value::Number(n) => n.as_f64().map(|f| json!(f)),
            Value::String(s) => s.trim().parse::<f64>().ok().map(|f| json!(f)),
            _ => None,
        },
        Type::Bool => match v {
            Value::Bool(b) => Some(json!(b)),
            Value::String(s) => match s.trim().to_ascii_lowercase().as_str() {
                "true" | "yes" | "y" | "1" => Some(json!(true)),
                "false" | "no" | "n" | "0" => Some(json!(false)),
                _ => None,
            },
            Value::Number(n) => n.as_i64().map(|i| json!(i != 0)),
            _ => None,
        },
        Type::String => Some(match v {
            Value::String(s) => json!(s),
            Value::Number(n) => json!(n.to_string()),
            Value::Bool(b) => json!(b.to_string()),
            Value::Null => json!(""),
            _ => json!(v.to_string()),
        }),
    }
}

/// Walk a JSON object, coercing fields named in `schema`.
///
/// Fields not in `schema` pass through unchanged.
pub fn coerce_args(mut args: Value, schema: &[(&str, Type)]) -> Value {
    if let Value::Object(map) = &mut args {
        for (name, ty) in schema {
            if let Some(slot) = map.remove(*name) {
                if let Some(fixed) = coerce_one(slot.clone(), *ty) {
                    map.insert((*name).to_string(), fixed);
                } else {
                    // Re-insert the original if we can't fix it.
                    map.insert((*name).to_string(), slot);
                }
            }
        }
    }
    args
}
