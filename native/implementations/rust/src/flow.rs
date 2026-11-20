//! Typed structured conditionals; branch-local values cannot escape their scope.
use super::functions::{slot, ARGUMENT_REGISTERS};
use super::{arena, buffers, input, output, runtime, slicing};
use super::{array, elf, imm32, invalid, object, text, unsupported, BinaryOp, Result};
use serde_json::Value;
use std::collections::{HashMap, HashSet};

#[derive(Clone, Copy, PartialEq)]
enum Kind {
    I64,
    Bool,
    Bytes,
}
#[derive(Clone, Copy)]
struct TypedSlot {
    slot: usize,
    kind: Kind,
}
struct Op {
    dest: usize,
    action: Action,
}
struct Branch {
    ops: Vec<Op>,
    value: usize,
}
enum Action {
    Slice(usize, usize, usize),
    Read(usize),
    Pack(Vec<usize>),
    Concat(usize, usize, usize),
    Write(usize, usize),
    Bytes(Vec<u8>),
    Len(usize),
    Get(usize, usize, usize),
    Const(i64),
    Binary(BinaryOp, usize, usize),
    Compare(u8, usize, usize),
    Not(usize),
    Call(usize, Vec<usize>),
    If(usize, Branch, Branch),
}
struct Function {
    params: usize,
    ops: Vec<Op>,
    ret: usize,
    frame: usize,
    edges: Vec<usize>,
}
struct Context<'a> {
    slicing: bool,
    input: bool,
    packing: bool,
    construction: bool,
    results: &'a [Kind],
    output: bool,
    names: &'a HashMap<String, usize>,
    signatures: &'a [Vec<(String, Kind)>],
    buffers: bool,
    data_bytes: usize,
    seen: HashSet<String>,
    next: usize,
    edges: Vec<usize>,
}
fn use_value(env: &HashMap<String, TypedSlot>, name: &str, kind: Kind) -> Result<usize> {
    let value = env
        .get(name)
        .ok_or_else(|| invalid("undefined or out-of-scope value"))?;
    if value.kind != kind {
        return Err(invalid("incorrect value type"));
    }
    Ok(value.slot)
}
impl Context<'_> {
    fn lower(
        &mut self,
        instructions: &[Value],
        env: &mut HashMap<String, TypedSlot>,
        depth: usize,
    ) -> Result<Vec<Op>> {
        let mut out = Vec::new();
        for value in instructions {
            let in_ = value
                .as_object()
                .ok_or_else(|| invalid("expected instruction"))?;
            let op = text(in_, "op")?;
            let (keys, kind): (&[&str], Kind) = match op {
                "bytes.slice" if self.slicing => {
                    (&["op", "dest", "buffer", "index", "count"], Kind::Bytes)
                }
                "bytes.read" if self.input => (&["op", "dest", "limit"], Kind::Bytes),
                "bytes.write" if self.output => (&["op", "dest", "value", "stream"], Kind::I64),
                "bytes.const" if self.buffers => (&["op", "dest", "values"], Kind::Bytes),
                "bytes.len" if self.buffers => (&["op", "dest", "value"], Kind::I64),
                "bytes.get" if self.buffers => {
                    (&["op", "dest", "buffer", "index", "default"], Kind::I64)
                }
                "if.bytes" if self.buffers => {
                    (&["op", "dest", "cond", "then", "else"], Kind::Bytes)
                }
                "const.i64" => (&["op", "dest", "value"], Kind::I64),
                "const.bool" | "not.bool" => (&["op", "dest", "value"], Kind::Bool),
                "add.i64" | "sub.i64" | "mul.i64" => (&["op", "dest", "lhs", "rhs"], Kind::I64),
                "eq.i64" | "ne.i64" | "lt.i64" | "le.i64" | "gt.i64" | "ge.i64" => {
                    (&["op", "dest", "lhs", "rhs"], Kind::Bool)
                }
                "call" => {
                    let target = *self
                        .names
                        .get(text(in_, "callee")?)
                        .ok_or_else(|| invalid("undefined callee"))?;
                    (&["op", "dest", "callee", "args"], self.results[target])
                }
                "bytes.pack" if self.packing => (&["op", "dest", "args"], Kind::Bytes),
                "bytes.concat" if self.construction => (&["op", "dest", "lhs", "rhs"], Kind::Bytes),
                "if.i64" => (&["op", "dest", "cond", "then", "else"], Kind::I64),
                "if.bool" => (&["op", "dest", "cond", "then", "else"], Kind::Bool),
                _ => return Err(format!("E_UNKNOWN_OPCODE: {op}")),
            };
            object(value, keys)?;
            let dest = text(in_, "dest")?;
            if dest.is_empty() || !self.seen.insert(dest.to_owned()) {
                return Err(invalid("missing or duplicate SSA destination"));
            }
            let dest_slot = self.next * 8;
            self.next += 1;
            if self.next > 1 << 17 {
                return Err(unsupported("too many IR values"));
            }
            let action = match op {
                "bytes.slice" => Action::Slice(
                    use_value(env, text(in_, "buffer")?, Kind::Bytes)?,
                    use_value(env, text(in_, "index")?, Kind::I64)?,
                    use_value(env, text(in_, "count")?, Kind::I64)?,
                ),
                "bytes.read" => Action::Read(
                    in_.get("limit")
                        .and_then(Value::as_u64)
                        // Version 11, which builds the compiler, reads sources up to 16 MiB.
                        .filter(|v| *v <= if self.slicing { 1 << 24 } else { 1 << 20 })
                        .ok_or_else(|| {
                            invalid(if self.slicing {
                                "expected input limit 0..16777216"
                            } else {
                                "expected input limit 0..1048576"
                            })
                        })?
                        as usize,
                ),
                "bytes.pack" => {
                    let values = array(in_, "args")?;
                    if values.len() > 4096 {
                        return Err(unsupported("pack exceeds 4096 values"));
                    }
                    let args = values
                        .iter()
                        .map(|v| {
                            use_value(
                                env,
                                v.as_str().ok_or_else(|| invalid("expected value name"))?,
                                Kind::I64,
                            )
                        })
                        .collect::<Result<Vec<_>>>()?;
                    Action::Pack(args)
                }
                "bytes.concat" => Action::Concat(
                    use_value(env, text(in_, "lhs")?, Kind::Bytes)?,
                    use_value(env, text(in_, "rhs")?, Kind::Bytes)?,
                    // A concatenated payload is at most 1 MiB; version 11 leaves it to the arena.
                    if self.slicing { 1 << 30 } else { 1 << 20 },
                ),
                "bytes.write" => {
                    let stream = match text(in_, "stream")? {
                        "stdout" => 1,
                        "stderr" => 2,
                        _ => return Err(invalid("expected stdout/stderr stream")),
                    };
                    Action::Write(use_value(env, text(in_, "value")?, Kind::Bytes)?, stream)
                }
                "bytes.const" => {
                    let values = array(in_, "values")?;
                    if values.len() > 1 << 20 {
                        return Err(unsupported("byte literal exceeds 1 MiB"));
                    }
                    self.data_bytes += values.len() + 8;
                    // Version 11, which builds the compiler, holds 16 MiB.
                    if self.data_bytes > if self.slicing { 16 << 20 } else { 4 << 20 } {
                        return Err(unsupported(if self.slicing { "byte data exceeds 16 MiB" } else { "byte data exceeds 4 MiB" }));
                    }
                    let data = values
                        .iter()
                        .map(|v| {
                            v.as_u64()
                                .and_then(|v| u8::try_from(v).ok())
                                .ok_or_else(|| invalid("expected integer byte 0..255"))
                        })
                        .collect::<Result<Vec<_>>>()?;
                    Action::Bytes(data)
                }
                "bytes.len" => Action::Len(use_value(env, text(in_, "value")?, Kind::Bytes)?),
                "bytes.get" => Action::Get(
                    use_value(env, text(in_, "buffer")?, Kind::Bytes)?,
                    use_value(env, text(in_, "index")?, Kind::I64)?,
                    use_value(env, text(in_, "default")?, Kind::I64)?,
                ),
                "const.i64" => Action::Const(
                    in_.get("value")
                        .and_then(Value::as_i64)
                        .ok_or_else(|| invalid("expected signed i64 constant"))?,
                ),
                "const.bool" => Action::Const(i64::from(
                    in_.get("value")
                        .and_then(Value::as_bool)
                        .ok_or_else(|| invalid("expected boolean constant"))?,
                )),
                "not.bool" => Action::Not(use_value(env, text(in_, "value")?, Kind::Bool)?),
                "call" => {
                    let target = *self
                        .names
                        .get(text(in_, "callee")?)
                        .ok_or_else(|| invalid("undefined callee"))?;
                    let arguments = array(in_, "args")?;
                    if arguments.len() != self.signatures[target].len() {
                        return Err(invalid("call arity mismatch"));
                    }
                    let mut args = Vec::new();
                    for (i, arg) in arguments.iter().enumerate() {
                        args.push(use_value(
                            env,
                            arg.as_str()
                                .ok_or_else(|| invalid("expected argument name"))?,
                            self.signatures[target][i].1,
                        )?);
                    }
                    self.edges.push(target);
                    Action::Call(target, args)
                }
                "if.i64" | "if.bool" | "if.bytes" => {
                    if depth >= 16 {
                        return Err(unsupported("conditional nesting exceeds 16"));
                    }
                    let cond = use_value(env, text(in_, "cond")?, Kind::Bool)?;
                    let yes = self.branch(
                        in_.get("then").ok_or_else(|| invalid("missing then"))?,
                        env,
                        kind,
                        depth + 1,
                    )?;
                    let no = self.branch(
                        in_.get("else").ok_or_else(|| invalid("missing else"))?,
                        env,
                        kind,
                        depth + 1,
                    )?;
                    Action::If(cond, yes, no)
                }
                _ => {
                    let lhs = use_value(env, text(in_, "lhs")?, Kind::I64)?;
                    let rhs = use_value(env, text(in_, "rhs")?, Kind::I64)?;
                    match op {
                        "add.i64" => Action::Binary(BinaryOp::Add, lhs, rhs),
                        "sub.i64" => Action::Binary(BinaryOp::Sub, lhs, rhs),
                        "mul.i64" => Action::Binary(BinaryOp::Mul, lhs, rhs),
                        _ => Action::Compare(
                            match op {
                                "eq.i64" => 0x94,
                                "ne.i64" => 0x95,
                                "lt.i64" => 0x9c,
                                "le.i64" => 0x9e,
                                "gt.i64" => 0x9f,
                                _ => 0x9d,
                            },
                            lhs,
                            rhs,
                        ),
                    }
                }
            };
            env.insert(
                dest.to_owned(),
                TypedSlot {
                    slot: dest_slot,
                    kind,
                },
            );
            out.push(Op {
                dest: dest_slot,
                action,
            });
        }
        Ok(out)
    }
    fn branch(
        &mut self,
        value: &Value,
        parent: &HashMap<String, TypedSlot>,
        kind: Kind,
        depth: usize,
    ) -> Result<Branch> {
        let branch = object(value, &["instructions", "value"])?;
        let mut env = parent.clone();
        let ops = self.lower(array(branch, "instructions")?, &mut env, depth)?;
        let value = use_value(&env, text(branch, "value")?, kind)?;
        Ok(Branch { ops, value })
    }
}
pub(super) fn compile(value: &Value) -> Result<Vec<u8>> {
    let p = object(
        value,
        if value.get("version").and_then(Value::as_i64) == Some(11) {
            &["version", "functions", "arena_bytes"]
        } else {
            &["version", "functions"]
        },
    )?;
    let arena_bytes = if p.get("version").and_then(Value::as_i64) == Some(11) {
        p.get("arena_bytes")
            .and_then(Value::as_u64)
            .filter(|v| *v >= 8 && *v <= 1 << 34 && v % 8 == 0)
            .ok_or_else(|| invalid("expected arena_bytes multiple of 8 in 8..17179869184"))?
            as usize
    } else {
        4 << 20
    };
    let inputs = array(p, "functions")?;
    if inputs.is_empty() {
        return Err(invalid("missing functions"));
    }
    let function_limit = if p.get("version").and_then(Value::as_i64) == Some(11) {
        65535
    } else {
        256
    };
    if inputs.len() > function_limit {
        return Err(unsupported("too many functions"));
    }
    let mut names = HashMap::new();
    let mut signatures: Vec<Vec<(String, Kind)>> = Vec::new();
    let mut results = Vec::new();
    let construction = matches!(
        p.get("version").and_then(Value::as_i64),
        Some(8) | Some(9) | Some(10) | Some(11)
    );
    let buffered = matches!(
        p.get("version").and_then(Value::as_i64),
        Some(5) | Some(6) | Some(7) | Some(8) | Some(9) | Some(10) | Some(11)
    );
    for (index, value) in inputs.iter().enumerate() {
        let f = object(value, &["name", "params", "return_type", "blocks"])?;
        let name = text(f, "name")?;
        if name.is_empty() || names.insert(name.to_owned(), index).is_some() {
            return Err(invalid("missing or duplicate function"));
        }
        let blocks = array(f, "blocks")?;
        let result = match text(f, "return_type")? {
            "i64" => Kind::I64,
            "bytes" if construction => Kind::Bytes,
            _ => return Err(unsupported("unsupported return type")),
        };
        results.push(result);
        if blocks.len() != 1 {
            return Err(unsupported("expected one i64 entry block"));
        }
        let b = object(&blocks[0], &["label", "instructions", "terminator"])?;
        if text(b, "label")? != "entry" {
            return Err(unsupported("expected entry block"));
        }
        let params = array(f, "params")?;
        if params.len() > 6 {
            return Err(unsupported("at most six parameters"));
        }
        let mut signature: Vec<(String, Kind)> = Vec::new();
        for value in params {
            let param = object(value, &["name", "type"])?;
            let name = text(param, "name")?;
            if name.is_empty() || signature.iter().any(|p| p.0 == name) {
                return Err(invalid("invalid or duplicate parameter"));
            }
            let kind = match text(param, "type")? {
                "i64" => Kind::I64,
                "bytes" if buffered => Kind::Bytes,
                _ => return Err(unsupported("unsupported function parameter type")),
            };
            signature.push((name.to_owned(), kind));
        }
        signatures.push(signature);
    }
    let main = *names.get("main").ok_or_else(|| invalid("missing main"))?;
    if !signatures[main].is_empty() || results[main] != Kind::I64 {
        return Err(invalid("main must have no parameters"));
    }
    let mut functions = Vec::new();
    let mut data_bytes = 0;
    for (index, value) in inputs.iter().enumerate() {
        let f = value.as_object().expect("validated function");
        let b = f["blocks"][0].as_object().expect("validated block");
        let mut env = HashMap::new();
        for (i, (name, kind)) in signatures[index].iter().enumerate() {
            env.insert(
                name.clone(),
                TypedSlot {
                    slot: i * 8,
                    kind: *kind,
                },
            );
        }
        let mut context = Context {
            slicing: p.get("version").and_then(Value::as_i64) == Some(11),
            input: matches!(
                p.get("version").and_then(Value::as_i64),
                Some(10) | Some(11)
            ),
            packing: matches!(
                p.get("version").and_then(Value::as_i64),
                Some(9) | Some(10) | Some(11)
            ),
            construction,
            results: &results,
            output: matches!(
                p.get("version").and_then(Value::as_i64),
                Some(7) | Some(8) | Some(9) | Some(10) | Some(11)
            ),
            names: &names,
            signatures: &signatures,
            seen: signatures[index].iter().map(|p| p.0.clone()).collect(),
            buffers: buffered,
            data_bytes: 0,
            next: signatures[index].len(),
            edges: Vec::new(),
        };
        let ops = context.lower(array(b, "instructions")?, &mut env, 0)?;
        data_bytes += context.data_bytes;
        if data_bytes > if context.slicing { 16 << 20 } else { 4 << 20 } {
            return Err(unsupported(if context.slicing { "byte data exceeds 16 MiB" } else { "byte data exceeds 4 MiB" }));
        }
        let term = object(
            b.get("terminator")
                .ok_or_else(|| invalid("missing terminator"))?,
            &["op", "value"],
        )?;
        if text(term, "op")? != "ret" {
            return Err(unsupported("only ret terminators"));
        }
        let ret = use_value(&env, text(term, "value")?, results[index])?;
        functions.push(Function {
            params: signatures[index].len(),
            ops,
            ret,
            frame: (context.next * 8 + 15) & !15,
            edges: context.edges,
        });
    }
    let mut active = vec![false; functions.len()];
    let mut heights = vec![0; functions.len()];
    let recursive = matches!(
        p.get("version").and_then(Value::as_i64),
        Some(4) | Some(5) | Some(6) | Some(7) | Some(8) | Some(9) | Some(10) | Some(11)
    );
    if !recursive {
        for i in 0..functions.len() {
            height(i, &functions, &mut active, &mut heights)?;
        }
    }
    let mut code = Vec::new();
    if recursive {
        code.extend_from_slice(&[0x45, 0x31, 0xf6, 0x45, 0x31, 0xff]);
    }
    let mut heap_guards = Vec::new();
    let mut byte_guards = Vec::new();
    if construction {
        arena::init(&mut code, &mut heap_guards, arena_bytes);
    }
    let call_offset = code.len() + 1;
    code.extend_from_slice(&[0xe8, 0, 0, 0, 0]);
    let checked_status = matches!(
        p.get("version").and_then(Value::as_i64),
        Some(6) | Some(7) | Some(8) | Some(9) | Some(10) | Some(11)
    );
    let mut status_guards = Vec::new();
    if checked_status {
        code.extend_from_slice(&[0x48, 0x3d, 0xff, 0, 0, 0, 0x0f, 0x87]);
        status_guards.push(code.len());
        imm32(&mut code, 0);
    }
    code.extend_from_slice(&[0x48, 0x89, 0xc7, 0xb8, 0x3c, 0, 0, 0, 0x0f, 0x05]);
    let mut patches = vec![(call_offset, main)];
    let mut guards = Vec::new();
    let mut blobs = Vec::new();
    let mut output_guards = Vec::new();
    let mut starts = Vec::new();
    for f in &functions {
        starts.push(code.len());
        if recursive {
            let wide = p.get("version").and_then(Value::as_i64) == Some(11);
            guards.extend(runtime::enter(
                &mut code,
                f.frame,
                if wide { 1024 } else { 256 },
                if wide { 4 << 20 } else { 1 << 20 },
            ));
        }
        code.extend_from_slice(&[0x55, 0x48, 0x89, 0xe5, 0x48, 0x81, 0xec]);
        imm32(&mut code, f.frame);
        for (i, reg) in ARGUMENT_REGISTERS.iter().enumerate().take(f.params) {
            slot(&mut code, 0x89, *reg, i * 8);
        }
        emit(
            &mut code,
            &f.ops,
            &mut patches,
            &mut blobs,
            &mut output_guards,
            &mut heap_guards,
            &mut byte_guards,
        )?;
        slot(&mut code, 0x8b, 0, f.ret);
        if recursive {
            runtime::leave(&mut code, f.frame);
        }
        code.extend_from_slice(&[0xc9, 0xc3]);
    }
    for (offset, target) in patches {
        patch(&mut code, offset, starts[target])?;
    }
    if recursive {
        runtime::finish(&mut code, &guards)?;
    }
    if checked_status {
        runtime::finish_status(&mut code, &status_guards)?;
    }
    if !output_guards.is_empty() {
        runtime::finish_output(&mut code, &output_guards)?;
    }
    if construction {
        runtime::finish_alloc(&mut code, &heap_guards)?;
    }
    if !byte_guards.is_empty() {
        runtime::finish_byte(&mut code, &byte_guards)?;
    }
    buffers::finish(&mut code, &blobs)?;
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
    for target in &functions[i].edges {
        h = h.max(1 + height(*target, functions, active, heights)?);
    }
    active[i] = false;
    if h > 64 {
        return Err(unsupported("call depth exceeds 64"));
    }
    heights[i] = h;
    Ok(h)
}
pub(super) fn patch(code: &mut [u8], offset: usize, target: usize) -> Result<()> {
    let delta = i32::try_from(target as i64 - (offset + 4) as i64)
        .map_err(|_| unsupported("relative displacement out of range"))?;
    code[offset..offset + 4].copy_from_slice(&delta.to_le_bytes());
    Ok(())
}
fn emit(
    code: &mut Vec<u8>,
    ops: &[Op],
    patches: &mut Vec<(usize, usize)>,
    blobs: &mut Vec<buffers::Literal>,
    output_guards: &mut Vec<usize>,
    heap_guards: &mut Vec<usize>,
    byte_guards: &mut Vec<usize>,
) -> Result<()> {
    for op in ops {
        match &op.action {
            Action::Slice(b, i, c) => slicing::slice(code, *b, *i, *c, heap_guards)?,
            Action::Read(limit) => input::read(code, *limit, heap_guards)?,
            Action::Pack(args) => arena::pack(code, args, heap_guards, byte_guards),
            Action::Concat(lhs, rhs, limit) => arena::concat(code, *lhs, *rhs, *limit, heap_guards),
            Action::Write(value, stream) => output::write(code, *value, *stream, output_guards)?,
            Action::Bytes(data) => {
                code.extend_from_slice(&[0x48, 0x8d, 0x05]);
                blobs.push(buffers::Literal {
                    offset: code.len(),
                    data: data.clone(),
                });
                imm32(code, 0);
            }
            Action::Len(value) => {
                slot(code, 0x8b, 0, *value);
                code.extend_from_slice(&[0x48, 0x8b, 0x00]);
            }
            Action::Get(buffer, index, fallback) => buffers::get(code, *buffer, *index, *fallback)?,
            Action::Const(value) => {
                code.extend_from_slice(&[0x48, 0xb8]);
                code.extend_from_slice(&value.to_le_bytes());
            }
            Action::Call(target, args) => {
                for (i, arg) in args.iter().enumerate() {
                    slot(code, 0x8b, ARGUMENT_REGISTERS[i], *arg);
                }
                code.push(0xe8);
                patches.push((code.len(), *target));
                imm32(code, 0);
            }
            Action::Not(value) => {
                slot(code, 0x8b, 0, *value);
                code.extend_from_slice(&[0x48, 0x83, 0xf0, 1]);
            }
            Action::If(cond, yes, no) => {
                slot(code, 0x8b, 0, *cond);
                code.extend_from_slice(&[0x48, 0x85, 0xc0, 0x0f, 0x84]);
                let otherwise = code.len();
                imm32(code, 0);
                emit(
                    code,
                    &yes.ops,
                    patches,
                    blobs,
                    output_guards,
                    heap_guards,
                    byte_guards,
                )?;
                slot(code, 0x8b, 0, yes.value);
                code.push(0xe9);
                let end = code.len();
                imm32(code, 0);
                let target = code.len();
                patch(code, otherwise, target)?;
                emit(
                    code,
                    &no.ops,
                    patches,
                    blobs,
                    output_guards,
                    heap_guards,
                    byte_guards,
                )?;
                slot(code, 0x8b, 0, no.value);
                let target = code.len();
                patch(code, end, target)?;
            }
            Action::Binary(operation, lhs, rhs) => {
                slot(code, 0x8b, 0, *lhs);
                slot(code, 0x8b, 1, *rhs);
                code.extend_from_slice(match operation {
                    BinaryOp::Add => &[0x48, 0x01, 0xc8],
                    BinaryOp::Sub => &[0x48, 0x29, 0xc8],
                    BinaryOp::Mul => &[0x48, 0x0f, 0xaf, 0xc1],
                });
            }
            Action::Compare(cc, lhs, rhs) => {
                slot(code, 0x8b, 0, *lhs);
                slot(code, 0x8b, 1, *rhs);
                code.extend_from_slice(&[
                    0x48, 0x39, 0xc8, 0x0f, *cc, 0xc0, 0x48, 0x0f, 0xb6, 0xc0,
                ]);
            }
        }
        slot(code, 0x89, 0, op.dest);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use serde_json::json;
    #[test]
    fn nesting_limit_is_enforced() {
        for depth in [16, 17] {
            let mut branch = json!({"instructions":[{"op":"const.i64","dest":"leaf","value":42}],"value":"leaf"});
            for i in 1..=depth {
                let dest = format!("r{i}");
                let other = format!("n{i}");
                branch = json!({"instructions":[{"op":"if.i64","dest":dest,"cond":"flag","then":branch,"else":{"instructions":[{"op":"const.i64","dest":other,"value":7}],"value":other}}],"value":dest});
            }
            let mut instructions = vec![json!({"op":"const.bool","dest":"flag","value":true})];
            instructions.extend(branch["instructions"].as_array().unwrap().iter().cloned());
            let input=serde_json::to_vec(&json!({"version":3,"functions":[{"name":"main","params":[],"return_type":"i64","blocks":[{"label":"entry","instructions":instructions,"terminator":{"op":"ret","value":branch["value"]}}]}]})).unwrap();
            let result = crate::compile(&input);
            if depth == 16 {
                assert!(result.is_ok());
            } else {
                assert!(matches!(result,Err(ref error) if error.starts_with("E_UNSUPPORTED")));
            }
        }
    }
}
