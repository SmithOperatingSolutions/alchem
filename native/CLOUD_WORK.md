# Cloud Work handoff — Alchem Native

## Objective

Continue converting compiler/runtime components and then standard-library modules
to the self-hosted path. The user requested both, compiler first. PR #7 was
explicitly authorized and merged at fa605a68ca47734264e721ce025c2713ff53b9ad.
PR #8 was subsequently authorized and merged at 45f9a8a23a52622a237ca4a5fa9364cd153cea79.
Continue feat/native-type-collections from that merge: expand source capacity,
then tuples/results/nested types, general collections and broader library APIs.
Continuation is draft PR #9 (https://github.com/SmithOperatingSolutions/alchem-native/pull/9); publish updates there; do not merge it without another request.
Do not modify production Alchem. Alchem is the primary self-hosted path; Go/Rust remain bootstrap references.
See docs/HANDOFF.md for the developer resume point, test command, code map and
next acceptance criteria; docs/self-hosting.md tracks the larger goal.

## Environment

Use Linux x86-64 with Python 3.9+, Go 1.23+ for the reference backend, Rust/Cargo
1.85+ for the native backend, and Go 1.27+ for the pinned upstream frontend.
Go's native module has no third-party dependencies. Rust and the frontend have
locked/pinned build dependencies; populate their caches once, then verify offline.
Inspect installed tools and preserve existing edits before changing code.

## Execution

Run `bash scripts/verify-local.sh --with-source` from repository root for the
complete suite. `--with-rust` omits the source checks; no flag runs only the Go
baseline. Builds use temporary directories and offline dependency resolution.
Use ALCHEM_FRONTEND_GO to select a separate Go 1.27 binary. Exact working PATH,
GOPATH, Rust homes and build-cache overrides are recorded in docs/progress.md.

## Required follow-up

1. Record actual versions, commands, results and failures in docs/progress.md.
2. Add regression/acceptance tests first, implement behavior, then rerun the suite.
3. Check executable permissions, deterministic bytes, native results, and invalid
   IR/source rejection. Keep Go/Rust differential checks and source probes passing.
4. Document IR/ABI changes and unsupported features before extending codegen.
5. Commit/push with [skip ci] and open/update a new draft PR from
   feat/native-type-collections. Do not merge it without an explicit request;
   merge authorization applied through PR #8.

## Current verified milestone

V1 arithmetic and V2 direct functions remain supported. V3 adds signed
comparisons, boolean locals, typed conditional results and branch-private SSA
values. The source adapter supports if values and terminal if statements.
implementations/alchem/lexer.alc is the first Alchem-written classifier component.
V4 adds bounded recursive calls, reserving R14/R15 for native active-frame/depth
counters; exceeding 1 MiB or 256 calls prints E_RUNTIME_LIMIT and exits 70.
V5 adds immutable static byte buffers, checked indexing with negative indices
and defaults, length, byte parameters and typed byte conditionals. The source
adapter maps literal list[integer] values restricted to bytes and Enum.count/at.
The Alchem expression lexer now exposes identifier/integer/punctuation spans,
EOF, lexical errors and stream traversal, with an explicit 128-byte token-input
bound (spec/lexer.md). Checked decimal conversion and a bounded arithmetic
parser/evaluator are now written in Alchem too (spec/integer-literals.md and
spec/expressions.md). All executable source now uses V6: native entry checks
main status 0..255 (E_HALT_STATUS/exit 70 on failure), without compile-time
execution or proof limits. All 354 evaluator probes now use ordinary source main.
V7 adds native byte writes and literal IO.puts with EINTR/short-write handling
and explicit runtime IO errors. See spec/ir-v7.md for supported output and limits.
V8 adds immutable runtime concatenation, typed byte returns and a separate
bounded 4 MiB RW arena; see spec/ir-v8.md. Source supports two-argument
Enum.concat and list[integer] helper returns in program mode.
V9 adds checked packing of computed integer byte values and a 4096-element pack
bound. Out-of-range values fail with E_RUNTIME_BYTE/exit 72, without truncation.
The Alchem encoder now constructs complete 140-byte Linux ELF images, including
headers/padding/code; tests execute all 256 valid images without a host envelope.
scripts/emit-alchem-executable.py exports them and can retain a standalone
configured Alchem emitter (spec/encoder.md).
V10 adds bounded native stdin; the saved Alchem arithmetic compiler now accepts
new runtime expressions and emits complete ELF with no host tools on PATH.
Build it with scripts/build-native.sh and run build/native/alchem-arithmetic.
See spec/arithmetic-compiler.md for the 128-byte arithmetic-only contract and
explicit bootstrap IO bridge. It cannot compile its own 14,516-byte source.
The new Alchem-written integer/function source compiler accepts modules, scoped
bindings, signed branches and direct/forward/recursive calls; it emits real
machine instructions and complete bounded ELF. Build-native also produces
alchem-compiler; see spec/alchem-source-profile.md. No new IR version is needed.
The Alchem compiler now rebuilds its actual assembled source: A1=A2=A3 through
both Go/Rust seeds, with correctness/rejections and measured arena checks at all
stages. Source89,611 bytes/305 functions; native compiler192,202 bytes. Standard
build publishes A3, compiler-source.alc and self-host.json. Compiler entry IO is
emitted in Alchem; native rebuilds need no host tools. V11 adds explicit compiler
arena budgets and bulk bytes.slice; V1–V10 bytes/contracts remain unchanged.
Batched/balanced traversal, saved function lengths and literal-copy emission
support the larger profile. See docs/HANDOFF.md and docs/self-hosting.md.
The first warm-cache self-build baseline is recorded, not a Go/Rust comparison.
All existing Alchem compiler components now build through A3 as five native core
tools. Enum byte reverse/take/drop/sum are emitted in Alchem and checked at every
self-built stage. Typed strings, literals, concat, byte_size, Integer.to_string and main-body IO.puts
are implemented in Alchem; see spec/alchem-string-profile.md. Stored booleans,
Enum.empty? and String contains?/starts_with?/ends_with? are now native too.
Source capacity now leaves958,964 input bytes after the current compiler,
while compaction preserves quoted content and token/statement boundaries. Grapheme count/slice/first/last now match the pinned Unicode17 runtime; recursive
options/tuples/results, exhaustive case expressions, short-circuit and/or, Enum.at/fetch options
and List.first/last overloads are verified. The function table has512 slots and
compiler-entry arena64MiB; ordinary programs keep4MiB. General collections and an expanded library subset are implemented. Next: remaining
standard-library foundations and API groups as tracked
in docs/core-modules.md, preserving self-build/correctness gates. Full production language/integration
remains separate; do not modify production Alchem or merge this draft PR.

## CI budget

Do not trigger GitHub Actions. All workflows are manual-only; use local checks.
Do not dispatch workflows or change production settings. If a tool or permission
blocks a check, record the exact blocker rather than claiming it passed.

## Current continuation

Source capacity is widened and verified to1,048,575 bytes. Parser/signature/env/
string/list cursor fields are24-bit, separately from executable lengths. Full
verify-local --with-source passes, including all self-built stages and exact
input boundaries. Structural types, tuples/results and nested options now pass the complete suite.
General collections/maps/typed iteration and added APIs across all five requested
modules are implemented. Preserve current verification and document remaining
API gaps; see the updated docs/HANDOFF.md. Do not redo completed PR8/grapheme/option work.
