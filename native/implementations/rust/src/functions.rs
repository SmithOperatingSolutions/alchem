//! Version 2 direct integer calls. V1 code generation remains unchanged.
use super::{array, elf, imm32, invalid, object, text, unsupported, BinaryOp, Result};
use serde_json::Value;
use std::collections::HashMap;

struct Signature {
    params: Vec<String>,
}
enum Op {
    Const(i64),
    Binary(BinaryOp, usize, usize),
    Call(usize, Vec<usize>),
}
struct Function {
    params: Vec<String>,
    slots: HashMap<String, usize>,
    instructions: Vec<(usize, Op)>,
    ret: usize,
    frame: usize,
}
pub(super) const ARGUMENT_REGISTERS: [u8; 6] = [7, 6, 2, 1, 8, 9];

pub(super) fn compile(value: &Value) -> Result<Vec<u8>> {
    let p = object(value, &["version", "functions"])?;
    let inputs = array(p, "functions")?;
    if inputs.is_empty() {
        return Err(invalid("missing functions"));
    }
    if inputs.len() > 256 {
        return Err(unsupported("too many functions"));
    }
    let mut names = HashMap::new();
    let mut signatures = Vec::new();
    for (index, value) in inputs.iter().enumerate() {
        let f = object(value, &["name", "params", "return_type", "blocks"])?;
        let name = text(f, "name")?;
        if name.is_empty() || names.insert(name.to_owned(), index).is_some() {
            return Err(invalid("missing or duplicate function name"));
        }
        let blocks = array(f, "blocks")?;
        if text(f, "return_type")? != "i64" || blocks.len() != 1 {
            return Err(unsupported("expected i64 function with one entry block"));
        }
        let b = object(&blocks[0], &["label", "instructions", "terminator"])?;
        if text(b, "label")? != "entry" {
            return Err(unsupported("expected entry block"));
        }
        let params = array(f, "params")?;
        if params.len() > 6 {
            return Err(unsupported("at most six integer parameters"));
        }
        let mut parameters = Vec::new();
        for value in params {
            let parameter = object(value, &["name", "type"])?;
            let name = text(parameter, "name")?;
            if name.is_empty() || parameters.iter().any(|p| p == name) {
                return Err(invalid("missing or duplicate parameter"));
            }
            if text(parameter, "type")? != "i64" {
                return Err(unsupported("only i64 parameters are supported"));
            }
            parameters.push(name.to_owned());
        }
        signatures.push(Signature { params: parameters });
    }
    let main = *names.get("main").ok_or_else(|| invalid("missing main"))?;
    if !signatures[main].params.is_empty() {
        return Err(invalid("main must have no parameters"));
    }
    let mut functions = Vec::new();
    for (index, value) in inputs.iter().enumerate() {
        let f = value.as_object().expect("validated function");
        let b = &f["blocks"][0];
        let b = b.as_object().expect("validated block");
        let params = signatures[index].params.clone();
        let mut slots: HashMap<String, usize> = params
            .iter()
            .enumerate()
            .map(|(i, name)| (name.clone(), i * 8))
            .collect();
        let mut instructions = Vec::new();
        for value in array(b, "instructions")? {
            let in_ = value
                .as_object()
                .ok_or_else(|| invalid("expected instruction"))?;
            let op = text(in_, "op")?;
            object(
                value,
                match op {
                    "const.i64" => &["op", "dest", "value"],
                    "add.i64" | "sub.i64" | "mul.i64" => &["op", "dest", "lhs", "rhs"],
                    "call" => &["op", "dest", "callee", "args"],
                    _ => return Err(format!("E_UNKNOWN_OPCODE: {op}")),
                },
            )?;
            let dest = text(in_, "dest")?;
            if dest.is_empty() || slots.contains_key(dest) {
                return Err(invalid("missing or duplicate SSA destination"));
            }
            let instruction = match op {
                "const.i64" => Op::Const(
                    in_.get("value")
                        .and_then(Value::as_i64)
                        .ok_or_else(|| invalid("expected signed i64 constant"))?,
                ),
                "call" => {
                    let callee = *names
                        .get(text(in_, "callee")?)
                        .ok_or_else(|| invalid("undefined callee"))?;
                    let arguments = array(in_, "args")?;
                    if arguments.len() != signatures[callee].params.len() {
                        return Err(invalid("call arity mismatch"));
                    }
                    let mut args = Vec::new();
                    for arg in arguments {
                        let name = arg
                            .as_str()
                            .ok_or_else(|| invalid("expected SSA argument name"))?;
                        args.push(
                            *slots
                                .get(name)
                                .ok_or_else(|| invalid("undefined call argument"))?,
                        );
                    }
                    Op::Call(callee, args)
                }
                _ => {
                    let lhs = *slots
                        .get(text(in_, "lhs")?)
                        .ok_or_else(|| invalid("undefined lhs"))?;
                    let rhs = *slots
                        .get(text(in_, "rhs")?)
                        .ok_or_else(|| invalid("undefined rhs"))?;
                    let op = match op {
                        "add.i64" => BinaryOp::Add,
                        "sub.i64" => BinaryOp::Sub,
                        _ => BinaryOp::Mul,
                    };
                    Op::Binary(op, lhs, rhs)
                }
            };
            let slot = slots.len() * 8;
            slots.insert(dest.to_owned(), slot);
            instructions.push((slot, instruction));
        }
        let terminator = object(
            b.get("terminator")
                .ok_or_else(|| invalid("missing terminator"))?,
            &["op", "value"],
        )?;
        if text(terminator, "op")? != "ret" {
            return Err(unsupported("only ret terminators"));
        }
        let ret = *slots
            .get(text(terminator, "value")?)
            .ok_or_else(|| invalid("undefined return value"))?;
        let frame = (slots.len() * 8 + 15) & !15;
        if frame > 1 << 20 {
            return Err(unsupported("too many IR values"));
        }
        functions.push(Function {
            params,
            slots,
            instructions,
            ret,
            frame,
        });
    }
    let mut active = vec![false; functions.len()];
    let mut heights = vec![0; functions.len()];
    for i in 0..functions.len() {
        height(i, &functions, &mut active, &mut heights)?;
    }
    let mut code = vec![0xe8, 0, 0, 0, 0];
    let mut patches = vec![(1, main)];
    code.extend_from_slice(&[0x48, 0x89, 0xc7, 0xb8, 0x3c, 0, 0, 0, 0x0f, 0x05]);
    let mut starts = Vec::new();
    for function in &functions {
        starts.push(code.len());
        code.extend_from_slice(&[0x55, 0x48, 0x89, 0xe5, 0x48, 0x81, 0xec]);
        imm32(&mut code, function.frame);
        for (index, name) in function.params.iter().enumerate() {
            slot(
                &mut code,
                0x89,
                ARGUMENT_REGISTERS[index],
                function.slots[name],
            );
        }
        for (dest, instruction) in &function.instructions {
            match instruction {
                Op::Const(value) => {
                    code.extend_from_slice(&[0x48, 0xb8]);
                    code.extend_from_slice(&value.to_le_bytes());
                }
                Op::Binary(op, lhs, rhs) => {
                    slot(&mut code, 0x8b, 0, *lhs);
                    slot(&mut code, 0x8b, 1, *rhs);
                    code.extend_from_slice(match op {
                        BinaryOp::Add => &[0x48, 0x01, 0xc8],
                        BinaryOp::Sub => &[0x48, 0x29, 0xc8],
                        BinaryOp::Mul => &[0x48, 0x0f, 0xaf, 0xc1],
                    });
                }
                Op::Call(callee, args) => {
                    for (index, arg) in args.iter().enumerate() {
                        slot(&mut code, 0x8b, ARGUMENT_REGISTERS[index], *arg);
                    }
                    code.push(0xe8);
                    patches.push((code.len(), *callee));
                    imm32(&mut code, 0);
                }
            }
            slot(&mut code, 0x89, 0, *dest);
        }
        slot(&mut code, 0x8b, 0, function.ret);
        code.extend_from_slice(&[0xc9, 0xc3]);
    }
    for (offset, callee) in patches {
        let displacement = starts[callee] as i64 - (offset + 4) as i64;
        let displacement = i32::try_from(displacement)
            .map_err(|_| unsupported("call displacement out of range"))?;
        code[offset..offset + 4].copy_from_slice(&displacement.to_le_bytes());
    }
    Ok(elf(&code))
}

fn height(
    i: usize,
    functions: &[Function],
    active: &mut [bool],
    heights: &mut [usize],
) -> Result<usize> {
    if active[i] {
        return Err(unsupported("recursive call graph"));
    }
    if heights[i] != 0 {
        return Ok(heights[i]);
    }
    active[i] = true;
    let mut h = 1;
    for (_, instruction) in &functions[i].instructions {
        if let Op::Call(target, _) = instruction {
            h = h.max(1 + height(*target, functions, active, heights)?);
        }
    }
    active[i] = false;
    if h > 64 {
        return Err(unsupported("call depth exceeds 64"));
    }
    heights[i] = h;
    Ok(h)
}
pub(super) fn slot(code: &mut Vec<u8>, op: u8, reg: u8, offset: usize) {
    code.extend_from_slice(&[0x48 | ((reg >> 3) << 2), op, 0x84 | ((reg & 7) << 3), 0x24]);
    imm32(code, offset);
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    #[test]
    fn reverse_order_call_depth_is_bounded() {
        for helpers in [63, 64] {
            let mut functions = Vec::new();
            for i in (-1..helpers).rev() {
                let name = if i == -1 {
                    "main".into()
                } else {
                    format!("f{i}")
                };
                let instruction = if i == helpers - 1 {
                    json!({"op":"const.i64", "dest":"r", "value":42})
                } else {
                    json!({"op":"call", "dest":"r", "callee":format!("f{}", i+1), "args":[]})
                };
                functions.push(json!({"name":name,"params":[],"return_type":"i64","blocks":[{"label":"entry","instructions":[instruction],"terminator":{"op":"ret","value":"r"}}]}));
            }
            let result = compile(&json!({"version":2,"functions":functions}));
            if helpers == 63 {
                assert!(result.is_ok());
            } else {
                assert!(matches!(result, Err(ref error) if error.starts_with("E_UNSUPPORTED")));
            }
        }
    }
}
