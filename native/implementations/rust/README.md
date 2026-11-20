# Experimental Rust native backend

Rust implementation of [v1](../../spec/ir.md) and [v2 direct-function IR](../../spec/ir-v2.md), and [v3 typed conditionals](../../spec/ir-v3.md). Like Go, it
validates instructions and SSA references, emits x86-64 machine instructions and
an ELF executable directly, and exits through Linux syscall 60. It never invokes
another compiler or linker during IR compilation. The source CLI can invoke a prebuilt pinned frontend for a restricted Alchem
main; see [the quickstart](../../docs/quickstart.md). V2 supports up to six i64 arguments, direct calls and full i64 returns.
Recursion, loops, external/indirect calls, linking and the production runtime
remain unsupported; the tested internal calling convention is in spec/abi.md.

Requires Rust/Cargo 1.85+ on Linux x86-64. `serde` and `serde_json` are compiler-build
dependencies; transitive versions/checksums are committed in `Cargo.lock`. Initial
setup needs registry access, then verification uses the locked offline cache:

```sh
cargo fetch --locked --manifest-path implementations/rust/Cargo.toml
cargo test --locked --offline --manifest-path implementations/rust/Cargo.toml
cargo build --locked --offline --manifest-path implementations/rust/Cargo.toml
python3 harness/run.py --compiler "$PWD/implementations/rust/target/debug/alchem-native-rust"
bash scripts/verify-local.sh --with-rust
```

The combined command builds both backends in a temporary directory, tests them
against the shared positive/negative fixtures, and runs 192 deterministic seeded
arithmetic programs against an independent low-byte arithmetic oracle. It also
requires byte-identical ELF output between Go and Rust. Current code generation
is intentionally identical; this is not evidence of an optimization advantage.

CLI tests cover invalid arguments, native execution, permissions `0700`, and
preservation of existing output on invalid IR. Output uses exclusive temporary
file creation and rename in the destination directory. Duplicate JSON keys are rejected during deserialization, before values can be
overwritten; field names are case-sensitive. See the documented IR validation limits.

Source mode accepts `--source FILE --output PROGRAM` and locates the sibling
`alchem-source-probe`, or a supplied `--frontend PATH`. It defaults to the Linux
x86-64 target and rejects simultaneous --source/--input or source overwrite.
The frontend is invoked as a prebuilt process; no toolchain runs during source
compilation. Frontend diagnostics are returned as `E_SOURCE`; a missing frontend
is `E_IO`. Existing output is preserved when source validation fails.
