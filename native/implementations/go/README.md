# Experimental Go native backend

Minimal direct ELF generator for Linux x86-64. Reads the shared JSON IR and emits native instructions without invoking an external compiler **during fixture compilation**. Building the compiler itself uses Go.

Supported: one parameterless `main`, `const.i64`, `add.i64`, `sub.i64`, `mul.i64`, and `ret`. Each SSA value receives a stack slot. The result is passed to Linux `exit(2)` through a syscall; exit status only preserves the low eight bits. This is not a general Alchem frontend, linker, runtime, or complete ABI implementation.

```sh
cd implementations/go
go build -o /tmp/alchem-native-go .
cd ../..
python3 harness/run.py --compiler /tmp/alchem-native-go
```

See [the version 1 JSON IR contract](../../spec/ir.md) and [process entry/exit contract](../../spec/abi.md) for operand validation, wrapping arithmetic, diagnostics, and limits. Future work includes functions, branches, proper linking, runtime, and security review.

Version 2 supports multiple direct integer functions with up to six parameters,
full i64 return values, bounded acyclic call graphs and a System V integer-register
calling convention. It is the executable reference for the Rust implementation.
See [v2 IR](../../spec/ir-v2.md) and [ABI](../../spec/abi.md). V1 output is unchanged.

V3 adds typed booleans, signed comparisons and structured conditionals with
branch-private SSA values. It is verified against Rust and independent native
oracles. See [v3 IR](../../spec/ir-v3.md); v1/v2 executable bytes are unchanged.
