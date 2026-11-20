# Architecture

Alchem Native is an isolated Linux x86-64 compiler laboratory. The Alchem-written
compiler now rebuilds itself and builds the remaining compiler components for a
bounded integer/byte profile. Production Alchem remains unchanged.

## Bootstrap and native pipelines

The seed path is pinned Alchem frontend -> typed IR -> Go or Rust backend -> A0.
Both backends implement the same IR and provide independent executable oracles.
They emit machine code and ELF directly without invoking another native compiler.

The normal distribution is assembled Alchem source -> A0 -> A1 -> A2 -> A3.
A1/A2/A3 must be byte-identical. Each generated stage must pass integer/byte and
library correctness/rejection tests. A3 then compiles the full lexer, decimal
conversion, expression evaluator, ELF encoder and arithmetic compiler into native
tools. These compilations and native tool execution run with an empty PATH.
No Go, Rust, Python, assembler or linker participates in native source compilation.
native-booleans.alc handles stored booleans, typed comparisons, short-circuit logic and predicates. native-options.alc handles
flat options/cases; native-graphemes.alc and its checked data component emit the
pinned Unicode17 grapheme runtime.
Python remains the build/publication/test orchestrator and assembles module bodies
into supported single-file inputs, compacting formatting/comments while preserving
quoted content and token/newline boundaries. General imports are not implemented.

## Implementation and contracts

implementations/alchem/native-compiler.alc parses and validates typed source,
emits machine instructions and constructs ELF. native-runtime.alc constructs the
arena, byte operations and Linux syscall entry. native-strings.alc adds typed
string literals/concat/byte length, Integer.to_string and main-body IO.puts. Other Alchem components and their
artifact manifest are documented in [core modules](core-modules.md).
implementations/go and implementations/rust remain seed/reference implementations.

Target programs use immutable byte records in a bounded non-executable RW arena,
signed i64 arithmetic, typed direct/recursive calls and scoped conditional values.
The source compiler uses its documented private register ABI; see
spec/alchem-source-profile.md, alchem-byte-profile.md and compiler-scaling.md.
Entry code reads/writes files through Linux syscalls and reports bounded errors.
The bootstrap IR contracts through V11 remain independently specified and tested.

## Verification and limits

Tests compare behavior against Python/pinned source oracles, compare Go/Rust ELF,
rebuild all native compiler stages, measure arena charges under tracing and inject
syscall failures. Build outputs carry hashes and use checked atomic publication.
Performance samples retain source/compiler hashes and correctness checks.

Full production compatibility is still work: further String APIs, general collections,
result/tuple/nested types, higher-order functions, imports,
actors, macros and foreign runtime integration. These shared foundations gate the
remaining standard-library conversion; see the core module coverage table.
