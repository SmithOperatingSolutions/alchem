# JSON IR version 2 — direct integer functions

Version 1 remains supported unchanged. Version 2 adds multiple named functions,
up to six i64 parameters per function, and direct calls. Every function has one
entry block and returns i64. There is exactly one parameterless `main`; the
process entry stub calls it and exits with the low eight bits of its result.

Parameters are required arrays of objects with exactly `name` (a nonempty SSA
name) and `type` (`i64`). Parameters define the initial SSA namespace of each
function; instruction destinations cannot reuse them. Function names must be
nonempty and unique. Function-local SSA names may repeat across functions.

A call instruction has exactly these non-null fields:

```json
{"op":"call","dest":"answer","callee":"sum","args":["left","right"]}
```

The callee must exist, argument count must match its signature, and each argument
must name a previously defined i64 value in the caller. Forward function
references are permitted. A call returns an i64 into its destination. The
existing arithmetic instructions and `ret` terminator keep their meaning;
function ret returns to its caller, while process exit belongs to the entry stub.

All functions are validated before code generation. Unknown/duplicate symbols,
invalid parameters/operands/arity and undefined values are `E_INVALID_IR`.
Unsupported types, more than six parameters, more than 256 functions, recursive
call graphs or call depth exceeding 64 are `E_UNSUPPORTED`. Each function's
16-byte-rounded frame remains limited to 1 MiB. These limits do not guarantee
that every host stack can execute the maximum permitted call chain.

There are no branches, block arguments, indirect/external calls, variadic calls,
floating-point arguments, heap/runtime or linker. Recursion needs control flow
and is deliberately rejected in this straight-line milestone. Symbols and call
relocations are resolved internally; no external tool is invoked.

The internal integer calling convention is documented in abi.md. Version 2 is
a new version because ret now has callable-function semantics and the program
shape permits multiple functions; old v1 programs retain their original bytes.

[Version 3](ir-v3.md) adds typed booleans, signed comparisons and structured
conditional yields while retaining the V2 function calling convention.
