use serde_json::json;
use tool_arg_coerce::{coerce_args, coerce_one, Type};

#[test]
fn string_to_int() {
    assert_eq!(coerce_one(json!("42"), Type::Int), Some(json!(42)));
}

#[test]
fn string_to_bool() {
    assert_eq!(coerce_one(json!("true"), Type::Bool), Some(json!(true)));
    assert_eq!(coerce_one(json!("no"), Type::Bool), Some(json!(false)));
}

#[test]
fn single_array_to_scalar() {
    assert_eq!(coerce_one(json!(["only"]), Type::String), Some(json!("only")));
    assert_eq!(coerce_one(json!([42]), Type::Int), Some(json!(42)));
}

#[test]
fn passes_through_correct_type() {
    assert_eq!(coerce_one(json!(7), Type::Int), Some(json!(7)));
}

#[test]
fn no_obvious_fix_is_none() {
    assert_eq!(coerce_one(json!({"x":1}), Type::Int), None);
}

#[test]
fn coerce_args_fixes_named_fields() {
    let raw = json!({ "count": "42", "ok": "yes", "extra": "untouched" });
    let fixed = coerce_args(raw, &[("count", Type::Int), ("ok", Type::Bool)]);
    assert_eq!(fixed["count"], json!(42));
    assert_eq!(fixed["ok"], json!(true));
    assert_eq!(fixed["extra"], json!("untouched"));
}
