mod arena;
mod buffers;
mod flow;
mod functions;
mod input;
mod json;
mod output;
mod runtime;
mod slicing;

use serde_json::{Map, Value};
use std::collections::HashMap;

type Result<T> = std::result::Result<T, String>;
fn invalid(message: impl std::fmt::Display) -> String {
    format!("E_INVALID_IR: {message}")
}
fn unsupported(message: &str) -> String {
    format!("E_UNSUPPORTED: {message}")
}
fn object<'a>(v: &'a Value, keys: &[&str]) -> Result<&'a Map<String, Value>> {
    let obj = v.as_object().ok_or_else(|| invalid("expected object"))?;
    if obj.keys().any(|key| !keys.contains(&key.as_str())) {
        return Err(invalid("unknown field"));
    }
    Ok(obj)
}
fn text<'a>(obj: &'a Map<String, Value>, key: &str) -> Result<&'a str> {
    obj.get(key)
        .and_then(Value::as_str)
        .ok_or_else(|| invalid(format!("expected string {key}")))
}
fn array<'a>(obj: &'a Map<String, Value>, key: &str) -> Result<&'a Vec<Value>> {
    obj.get(key)
        .and_then(Value::as_array)
        .ok_or_else(|| invalid(format!("expected array {key}")))
}
fn imm32(code: &mut Vec<u8>, value: usize) {
    code.extend_from_slice(&(value as u32).to_le_bytes());
}
fn load(code: &mut Vec<u8>, reg: u8, offset: usize) {
    code.extend_from_slice(&[0x48, 0x8b, 0x84 | (reg << 3), 0x24]);
    imm32(code, offset);
}
enum BinaryOp {
    Add,
    Sub,
    Mul,
}

enum Instruction {
    Const(i64),
    Binary {
        op: BinaryOp,
        lhs: usize,
        rhs: usize,
    },
}

/// Validate the v1 IR, then lower directly to x86-64 instructions and ELF.
pub fn compile(input: &[u8]) -> Result<Vec<u8>> {
    let value = serde_json::from_slice::<json::UniqueValue>(input)
        .map_err(invalid)?
        .0;
    let p = object(
        &value,
        if value.get("version").and_then(Value::as_i64) == Some(11) {
            &["version", "functions", "arena_bytes"]
        } else {
            &["version", "functions"]
        },
    )?;
    if p.get("version").and_then(Value::as_i64) == Some(2) {
        return functions::compile(&value);
    }
    if matches!(
        p.get("version").and_then(Value::as_i64),
        Some(3) | Some(4) | Some(5) | Some(6) | Some(7) | Some(8) | Some(9) | Some(10) | Some(11)
    ) {
        return flow::compile(&value);
    }
    let functions = array(p, "functions")?;
    if p.get("version").and_then(Value::as_i64) != Some(1) || functions.len() != 1 {
        return Err(invalid("expected version 1 with exactly one function"));
    }
    let f = object(&functions[0], &["name", "params", "return_type", "blocks"])?;
    let params_empty = match f.get("params") {
        None | Some(Value::Null) => true,
        Some(Value::Array(params)) => params.is_empty(),
        _ => return Err(invalid("expected params array")),
    };
    let blocks = array(f, "blocks")?;
    if text(f, "name")? != "main"
        || text(f, "return_type")? != "i64"
        || !params_empty
        || blocks.len() != 1
    {
        return Err(unsupported(
            "only parameterless main returning i64 with one entry block is supported",
        ));
    }
    let b = object(&blocks[0], &["label", "instructions", "terminator"])?;
    if text(b, "label")? != "entry" {
        return Err(unsupported("expected entry block"));
    }
    let instructions = array(b, "instructions")?;
    let mut slots = HashMap::new();
    let mut lowered = Vec::new();
    for value in instructions {
        let in_ = value
            .as_object()
            .ok_or_else(|| invalid("expected instruction"))?;
        let op = text(in_, "op")?;
        let keys: &[&str] = match op {
            "const.i64" => &["op", "dest", "value"],
            "add.i64" | "sub.i64" | "mul.i64" => &["op", "dest", "lhs", "rhs"],
            _ => return Err(format!("E_UNKNOWN_OPCODE: {op}")),
        };
        object(value, keys)?;
        let dest = text(in_, "dest")?;
        if dest.is_empty() || slots.contains_key(dest) {
            return Err(invalid("missing or duplicate SSA destination"));
        }
        let instruction = match op {
            "const.i64" => Instruction::Const(
                in_.get("value")
                    .and_then(Value::as_i64)
                    .ok_or_else(|| invalid("expected signed i64 constant"))?,
            ),
            _ => {
                let lhs = slots
                    .get(text(in_, "lhs")?)
                    .copied()
                    .ok_or_else(|| invalid("undefined lhs"))?;
                let rhs = slots
                    .get(text(in_, "rhs")?)
                    .copied()
                    .ok_or_else(|| invalid("undefined rhs"))?;
                let op = match op {
                    "add.i64" => BinaryOp::Add,
                    "sub.i64" => BinaryOp::Sub,
                    _ => BinaryOp::Mul,
                };
                Instruction::Binary { op, lhs, rhs }
            }
        };
        slots.insert(dest, lowered.len() * 8);
        lowered.push(instruction);
        if lowered.len() > (1 << 20) / 8 {
            return Err(unsupported("too many IR values"));
        }
    }
    let terminator = object(
        b.get("terminator")
            .ok_or_else(|| invalid("missing terminator"))?,
        &["op", "value"],
    )?;
    if text(terminator, "op")? != "ret" {
        return Err(unsupported("only ret terminator supported"));
    }
    let ret = slots
        .get(text(terminator, "value")?)
        .copied()
        .ok_or_else(|| invalid("undefined return value"))?;
    let stack_size = (lowered.len() * 8 + 15) & !15;
    let mut code = vec![0x48, 0x81, 0xec];
    imm32(&mut code, stack_size);
    for (index, instruction) in lowered.iter().enumerate() {
        match instruction {
            Instruction::Const(value) => {
                code.extend_from_slice(&[0x48, 0xb8]);
                code.extend_from_slice(&value.to_le_bytes());
            }
            Instruction::Binary { op, lhs, rhs } => {
                load(&mut code, 0, *lhs);
                load(&mut code, 3, *rhs);
                code.extend_from_slice(match op {
                    BinaryOp::Add => &[0x48, 0x01, 0xd8],
                    BinaryOp::Sub => &[0x48, 0x29, 0xd8],
                    BinaryOp::Mul => &[0x48, 0x0f, 0xaf, 0xc3],
                });
            }
        }
        code.extend_from_slice(&[0x48, 0x89, 0x84, 0x24]);
        imm32(&mut code, index * 8);
    }
    load(&mut code, 7, ret);
    code.extend_from_slice(&[0xb8, 0x3c, 0, 0, 0, 0x0f, 0x05]);
    Ok(elf(&code))
}

fn elf(code: &[u8]) -> Vec<u8> {
    let mut out = vec![0; 0x1000 + code.len()];
    out[..7].copy_from_slice(b"\x7fELF\x02\x01\x01");
    for (offset, value) in [(16, 2u16), (18, 62), (52, 64), (54, 56), (56, 1)] {
        out[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
    }
    for (offset, value) in [(20, 1u32), (64, 1), (68, 5)] {
        out[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
    }
    let size = out.len() as u64;
    for (offset, value) in [
        (24, 0x401000u64),
        (32, 64),
        (80, 0x400000),
        (96, size),
        (104, size),
        (112, 0x1000),
    ] {
        out[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
    }
    out[0x1000..].copy_from_slice(code);
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::{json, Value};

    fn program(instructions: Value, result: &str) -> Value {
        json!({"version":1,"functions":[{"name":"main","params":[],"return_type":"i64","blocks":[{"label":"entry","instructions":instructions,"terminator":{"op":"ret","value":result}}]}]})
    }

    #[test]
    fn valid_fixtures_are_deterministic_elf() {
        for name in [
            "return-42",
            "add-20-22",
            "return-zero",
            "return-negative",
            "add-overflow",
            "add-wrap-to-42",
            "sub-84-42",
            "sub-reversed",
            "mul-6-7",
            "mul-overflow",
        ] {
            let input = std::fs::read(format!("../../fixtures/ir/{name}.json")).unwrap();
            let first = compile(&input).unwrap();
            assert_eq!(first, compile(&input).unwrap());
            assert_eq!(&first[..7], b"\x7fELF\x02\x01\x01");
            assert_eq!(u16::from_le_bytes(first[18..20].try_into().unwrap()), 62);
            assert_eq!(
                u64::from_le_bytes(first[24..32].try_into().unwrap()),
                0x401000
            );
            assert_eq!(u32::from_le_bytes(first[68..72].try_into().unwrap()), 5);
        }
    }

    #[test]
    fn invalid_operands_and_ssa_are_rejected() {
        for instructions in [
            json!([{"op":"const.i64","dest":"x"}]),
            json!([{"op":"const.i64","dest":"x","value":null}]),
            json!([{"op":"const.i64","dest":"x","value":0,"lhs":"x"}]),
            json!([{"op":"const.i64","dest":"x","value":1.5}]),
            json!([{"op":"const.i64","dest":"x","value":9223372036854775808u64}]),
            json!([{"op":"const.i64","dest":"x","value":1},{"op":"const.i64","dest":"x","value":2}]),
            json!([{"op":"add.i64","dest":"x","lhs":"missing","rhs":"missing"}]),
            json!([]),
        ] {
            let input = serde_json::to_vec(&program(instructions, "x")).unwrap();
            assert!(compile(&input).unwrap_err().starts_with("E_INVALID_IR"));
        }
    }

    #[test]
    fn malformed_and_trailing_json_are_rejected() {
        for input in [b"{".as_slice(), b"null", b"{}{}", b"{} garbage"] {
            assert!(compile(input).unwrap_err().starts_with("E_INVALID_IR"));
        }
    }

    #[test]
    fn unknown_opcode_has_stable_diagnostic() {
        let input = include_bytes!("../../../fixtures/ir/invalid-unknown-op.json");
        assert!(compile(input).unwrap_err().starts_with("E_UNKNOWN_OPCODE"));
    }

    #[test]
    fn strict_json_keys_are_rejected() {
        for name in [
            "duplicate-root-key",
            "duplicate-function-key",
            "duplicate-block-key",
            "duplicate-instruction-key",
            "duplicate-terminator-key",
            "duplicate-escaped-key",
            "cased-root-key",
            "cased-function-key",
            "cased-block-key",
            "cased-terminator-key",
        ] {
            let input = std::fs::read(format!("../../fixtures/ir/invalid-{name}.json")).unwrap();
            let result = compile(&input);
            assert!(
                matches!(result, Err(ref error) if error.starts_with("E_INVALID_IR")),
                "{name}: invalid JSON keys were accepted"
            );
        }
    }

    #[test]
    fn version2_functions_compile() {
        for name in [
            "identity",
            "forward-zero-args",
            "six-args",
            "preserves-values",
            "nested",
            "argument-order",
        ] {
            let input = std::fs::read(format!("../../fixtures/ir/v2-call-{name}.json")).unwrap();
            let first = compile(&input).unwrap();
            assert_eq!(first, compile(&input).unwrap());
        }
    }

    #[test]
    fn version3_conditionals_compile() {
        let input = include_bytes!("../../../fixtures/ir/v3-private-yields.json");
        assert!(compile(input).is_ok());
    }

    #[test]
    fn version4_recursion_compiles() {
        assert!(compile(include_bytes!("../../../fixtures/ir/v4-infinite.json")).is_ok());
    }
    #[test]
    fn version5_bytes_compile() {
        assert!(compile(include_bytes!("../../../fixtures/ir/v5-parameter.json")).is_ok());
    }
    #[test]
    fn version6_checked_status_compiles() {
        assert!(compile(include_bytes!("../../../fixtures/ir/v6-status-256.json")).is_ok());
    }
    #[test]
    fn version7_output_compiles() {
        assert!(compile(include_bytes!("../../../fixtures/ir/v7-stdout.json")).is_ok());
    }
    #[test]
    fn version8_construction_compiles() {
        assert!(compile(include_bytes!("../../../fixtures/ir/v8-byte-return.json")).is_ok());
    }
    #[test]
    fn version9_packing_compiles() {
        assert!(compile(include_bytes!("../../../fixtures/ir/v9-pack-ordered.json")).is_ok());
    }
}
