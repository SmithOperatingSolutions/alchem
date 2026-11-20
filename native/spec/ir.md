# Minimal Alchem JSON IR — version 1 baseline

This contract describes the implemented Go baseline and the input/output contract
for future backends. [Version 2](ir-v2.md) adds direct integer functions and [v3](ir-v3.md) adds typed
conditionals. [V4](ir-v4.md) adds bounded recursive calls; [V5](ir-v5.md) adds immutable byte buffers, and [V6](ir-v6.md) checks process status and [V7](ir-v7.md) adds byte output; [V8](ir-v8.md) adds runtime byte construction/returns and [V9](ir-v9.md) checked packing. This page specifies v1. The backends consume IR directly. An experimental
[pinned source adapter](../adapters/alchem/README.md) supports integer library functions and a restricted executable main with
bindings and final System.halt; it is not a complete Alchem frontend.

## Serialization and structure

Input is one UTF-8 JSON object; trailing whitespace is allowed, but additional
JSON documents or trailing garbage are rejected. Producers must use the exact
lowercase field names below and unique object keys. Object key order and JSON
whitespace carry no semantic meaning. Unknown fields are rejected.

```json
{
  "version": 1,
  "functions": [{
    "name": "main",
    "params": [],
    "return_type": "i64",
    "blocks": [{
      "label": "entry",
      "instructions": [
        {"op": "const.i64", "dest": "a", "value": 20},
        {"op": "const.i64", "dest": "b", "value": 22},
        {"op": "add.i64", "dest": "answer", "lhs": "a", "rhs": "b"}
      ],
      "terminator": {"op": "ret", "value": "answer"}
    }]
  }]
}
```

Version must be integer 1. There is exactly one function: parameterless `main`
returning `i64`, with exactly one block named `entry`. Producers emit `params: []`;
the current decoder also treats absent/null params as empty. Instructions execute
in array order, followed by the block terminator. Every SSA destination is a
nonempty string assigned exactly once. References must name earlier instructions
in the same block; forward references and self-references are invalid. Names are
case-sensitive. The baseline allocates 8 bytes per SSA value, rounds the stack
allocation to 16 bytes, and rejects allocations larger than 1 MiB.

## Operations

| Operation | Exact fields | Meaning |
| --- | --- | --- |
| `const.i64` | `op`, `dest`, `value` | Define a signed 64-bit integer constant. |
| `add.i64` | `op`, `dest`, `lhs`, `rhs` | Add two earlier i64 values, wrapping modulo 2^64. |
| `sub.i64` | `op`, `dest`, `lhs`, `rhs` | Subtract rhs from lhs, wrapping modulo 2^64. |
| `mul.i64` | `op`, `dest`, `lhs`, `rhs` | Multiply two earlier i64 values, retaining the low 64 bits. |
| `ret` terminator | `op`, `value` | End the process with the referenced i64 value as exit status. |

Instruction fields are required and non-null; operands belonging to another
opcode are invalid. Constants use JSON integer notation in the range
-9223372036854775808 through 9223372036854775807. Fractions, exponent notation,
strings, booleans, null, and out-of-range constants are rejected. Zero must be
explicitly written as `"value": 0`. Addition, subtraction and multiplication
wrap modulo 2^64 and never trap on overflow. Subtraction is ordered: lhs minus
rhs. Multiplication has the same low-64-bit result for signed or unsigned
interpretations. `sub.i64` and `mul.i64` are additive v1 extensions; older
backends reject those opcodes rather than changing existing program behavior.
The `ret` value is an SSA name, not a numeric literal. Linux exposes only the low
8 bits of the result as process exit status; for example -1 exits 255. The
baseline produces no stdout/stderr from the compiled program.

## Compiler interface and diagnostics

```
alchem-native --target x86_64-unknown-linux-gnu --input INPUT.json --output PROGRAM
```

Success exits 0 and emits a Linux x86-64 ELF executable with owner permissions
`0700`. Repeated compilations of identical input to different output paths must
produce identical bytes. No external compiler or linker is invoked during IR
compilation. Compilation failure exits nonzero with a diagnostic on stderr:

| Code | Examples |
| --- | --- |
| `E_INVALID_IR` | Malformed JSON, unsupported version/function count, unknown fields, invalid instruction operands, duplicate SSA destinations, undefined references. |
| `E_UNKNOWN_OPCODE` | Unrecognized instruction opcode. |
| `E_UNSUPPORTED` | Unsupported target, function/block shape, return type, terminator, or stack allocation size. |
| `E_INVALID_ARGUMENT` | Missing input/output flags, malformed flags, or positional arguments. |
| `E_IO` | Failed input read or output creation/write/rename. |

Diagnostics may contain additional explanatory text; only the code is stable.
When several errors exist, which is reported first is not part of the contract.
Output is written to a temporary file then renamed on success; invalid IR does
not create output or replace an existing output file.

## Validation limits and future work

Both backends reject duplicate object keys at every depth, comparing decoded
key names so escaped aliases also count as duplicates. Field names must match
exactly, including case. JSON escapes in canonical key names and Unicode SSA
names remain supported. This is not a complete JSON Schema validator.

V1 has no branches, comparisons, calls, parameters, linking, or runtime.
V2 adds internal functions, parameters and calls; see ir-v2.md.
A future IR version must define block arguments/phi values, control-flow typing,
function symbols, external calling conventions, traps, relocations, and debug
metadata before those features are implemented. The current process-entry/exit
behavior is not a reusable function ABI.
