# Progress

## 2026-11-15

- [x] Establish separate `alchem-native` repository.
- [x] Record three-track research direction and initial design documents.
- [x] Confirm upstream Alchem frontend integration boundaries (pinned pure-function probe).
- [ ] Finalize minimal IR and ABI contracts.
- [x] Add shared fixtures and fail-first test harness.
- [x] Implement and test Go native backend.
- [x] Implement and test Rust native backend.
- [x] Capture reproducible benchmark results (bounded local smoke measurements).
- [x] Evaluate self-hosting prerequisites (remaining milestones in docs/self-hosting.md).

Go baseline verified below; no benchmark result is claimed.


## 2026-11-16 — Cloud Linux verification

- Tested starting revision `01726d7d78ad8431968d0b6e931f7f0665494579` on
  `feat/go-native-backend`, then reran the complete suite with the fixes in this commit.
- Environment: Linux x86_64, Python 3.12.14, Go 1.23.12 linux/amd64,
  Git 2.52.0. Go has no third-party module dependencies.
- Initial `bash scripts/verify-local.sh`: both Python tests passed, then failed
  with `Go: Unknown option: test`; `/usr/bin/go` is not the Go compiler.
  Installed the official Go 1.23.12 archive in `/tmp/go`. The next attempt
  failed because `/home/agent/.cache/go-build` is read-only; used a temporary
  build cache instead. Repository clone also required network-enabled execution
  because the sandbox proxy was unreachable.
- Regression-first `go test -v ./...` reproduced acceptance of trailing JSON
  objects/garbage and positional CLI arguments, plus missing `E_*` diagnostics
  for unknown flags and missing flag values. Fixed decoding to require EOF after
  one JSON document and CLI parsing to reject extra arguments and report
  `E_INVALID_ARGUMENT` for malformed flags.
- Final complete command from repository root:
  `PATH=/tmp/go/bin:$PATH GOCACHE=/tmp/alchem-go-cache bash scripts/verify-local.sh`.
  Result: exit 0; 2 Python manifest tests passed; Go tests and build passed;
  all 3 acceptance cases passed (`return-42`, `add-20-22`,
  `invalid-unknown-op`). Both executable cases exited 42 with empty stdout/stderr.
- Go tests cover malformed JSON, trailing documents/garbage, duplicate SSA
  destinations, undefined lhs/rhs/return values, and invalid CLI arguments.
  Invalid invocations must fail with a coded diagnostic and leave no output.
- Inspected both valid fixtures using `debug/elf`: ELF64, little endian,
  ET_EXEC, EM_X86_64, entry `0x401000`, one read/execute PT_LOAD segment
  at `0x400000`, file/memory sizes matching output, 4096-byte alignment.
  CLI output permissions verified as `0700`. Two compilations of each valid
  fixture produced byte-identical executable contents.
- No remaining test failures with the documented environment overrides.
  The system `go` and default cache remain unsuitable for this workspace.
- Limitations: no Alchem source frontend, only a tiny JSON IR with `const.i64`,
  `add.i64`, and `ret`; one parameterless main/entry block; no branching,
  calls, linker, or runtime. Process exit status truncates to 8 bits.
  Rust and benchmarks remain unverified.
- No production Alchem changes, merge, or workflow dispatch. Push uses
  `[skip ci]` because the docs and harness workflows still have push/PR triggers;
  the Go workflow is manual-only.

### Shared acceptance runner follow-up

- PR #3 had no review comments at the time of inspection.
- Added three runner regression tests first. All three failed against the old
  runner: it silently chmodded nonexecutable compiler output, accepted
  nondeterministic output, and compiled each positive fixture only once.
- The runner now checks executable permissions without modifying output and
  compiles each positive fixture twice to distinct paths, requiring identical
  bytes and successful executable output on both invocations. This applies the
  determinism contract to future backends as well as Go.
- Reran `PATH=/tmp/go/bin:$PATH GOCACHE=/tmp/alchem-go-cache bash scripts/verify-local.sh`:
  exit 0, all 5 Python tests passed, Go tests/build passed, and 3/3 acceptance
  cases passed. `git diff --check` also passed. No remaining failures.
- Original production/CI/merge boundaries remain unchanged; follow-up commit
  uses `[skip ci]`. Next design milestone is to document and freeze the actual
  supported JSON IR contract before expanding instructions or starting Rust.

### Version 1 IR and process contract

- Replaced the illustrative IR draft with the supported JSON version 1 shape,
  required instruction operands, signed i64 limits, wrapping addition, SSA
  ordering, stable diagnostic codes, deterministic output and CLI contract.
  Documented the process entry/exit ABI separately from future callable functions.
- Five new fail-first operand cases demonstrated missing/null constants silently
  becoming zero and instruction operands from other opcodes being ignored.
  Added opcode-specific decoding to reject missing/null/irrelevant fields.
  Added coverage for fractions, exponent notation, booleans, strings, and both
  out-of-range signed integer boundaries.
- Added shared executable fixtures for zero, -1 (exit 255), signed overflow,
  and wrapping addition returning 42. These are compiled twice by the runner,
  checked for identical bytes and executable permissions, then executed.
- Complete verification after the changes:
  `PATH=/tmp/go/bin:$PATH GOCACHE=/tmp/alchem-go-cache bash scripts/verify-local.sh`
  exited 0: 5 Python tests, Go tests/build, and 7/7 acceptance cases passed.
  `git diff --check` passed. No remaining test failures.
- Known validation limits are explicit: the Go decoder still accepts duplicate
  JSON object keys globally and some case-insensitive structural field aliases;
  this is not a complete JSON Schema validator. The v1 producer contract forbids
  depending on those behaviors. Full callable ABI/frontend/Rust work remains open.
- Changes stay on the existing feature branch; commit uses `[skip ci]`.


### Rust baseline and shared differential verification

- Started Rust after the Go baseline was verified, as authorized by the session
  and CLOUD_WORK.md. No Rust toolchain was installed. Installed an isolated
  toolchain under `/tmp/alchem-rustup` and `/tmp/alchem-cargo`:
  rustc 1.85.0 (4d91de4e4 2025-02-17), cargo 1.85.0 (d73d2caf9 2024-12-31).
  The first rustup invocation failed because its executable was renamed;
  rerunning with the required `rustup-init` filename succeeded.
- Added fail-first Rust library tests: valid fixture compilation and unknown-op
  diagnostics initially failed. Added a CLI integration test, confirmed it
  failed against the placeholder CLI, then implemented argument parsing,
  exclusive temporary output creation, executable permissions, and rename.
- Rust emits ELF/x86-64 directly. It does not invoke Go, rustc, GCC, Clang or a
  linker while compiling IR. `serde_json` is a compiler-build dependency; exact
  versions/checksums are in Cargo.lock. Initial fetch required network access;
  all subsequent checks ran `--locked --offline`.
- Added eight shared negative fixtures for duplicate SSA, undefined operands
  and return values, missing/null constants, wrong operands and range overflow.
  Both backends pass all 15 shared acceptance cases.
- Added `scripts/verify-local.sh --with-rust` and 64 seeded differential programs
  with edge constants, arbitrary i64 constants, reused SSA values and wrapping
  additions. Each program's Go/Rust executable bytes match and native exit
  results agree with independently computed Python arithmetic.
- Complete command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup bash scripts/verify-local.sh --with-rust`.
  Results: 5 Python tests; Go tests/build; 4 Rust library tests and 1 CLI
  integration test; Rust build; 15/15 acceptance cases per backend; 64/64
  differential programs. No remaining test failures.
- `cargo clippy --locked --offline --manifest-path implementations/rust/Cargo.toml --all-targets -- -D warnings`
  passed; Rust sources formatted with `cargo fmt`.
- `readelf -h -l /tmp/alchem-rust-elf` on Rust add(20,22) confirmed ELF64,
  little endian, ET_EXEC, x86-64, entry 0x401000, one R E load segment, 4096-byte
  alignment, no section headers; `stat -c '%a %s'` reported `700 4181`.
- Remaining limitations: no frontend, branches, calls, linker, runtime or full
  JSON Schema validation. Duplicate object-key validation is still incomplete;
  Go accepts some case aliases that Rust rejects. These checks do not establish
  behavior on arbitrary malformed input or production readiness.


### Local measurements and frontend boundary inspection

- Added `scripts/benchmark-local.py` and a small `measure-rss.c` helper; recorded
  raw samples for optimized Go/Rust compiler builds at revision `8334491` in
  `docs/measurements/2026-11-16-smoke.json`. Methodology and limitations are in
  `docs/benchmarks.md`; updated the experiment matrix with actual results.
- Benchmark command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup python3 scripts/benchmark-local.py --go /tmp/alchem-native-bench/go --rust /tmp/alchem-native-bench/rust/release/alchem-native-rust --output docs/measurements/2026-11-16-smoke.json`.
  Builds: Go `go build -trimpath`; Cargo `build --release --locked --offline`.
  2 warmups, 20 timed runs, 5 separate RSS runs per input/backend. Both small
  add(20,22) and generated 4096-value workloads emitted identical Go/Rust bytes
  and the expected native exit statuses. No runtime advantage is claimed.
- Initial benchmark attempt failed because `/usr/bin/time` is absent. A Python
  posix_spawn/wait4 trial then showed a shared inherited Python RSS floor; those
  trial samples were discarded. Final RSS uses a minimal C fork/exec/wait4
  helper built by cc 14.2.0, outside the IR compilation path. Compiler processes
  do not invoke cc. Host/scheduling/cache caveats are recorded with the samples.
- Inspected upstream production source read-only at pinned revision
  `0b73f880b108fe5548f79896a91a59a0aa571fda`. No changes were made there.
  The exported syntax parser/analyzer and AST provide an adapter boundary;
  source main is void, unlike the integer-exit IR harness entrypoint. Upstream
  declares Go 1.27. Frontend extraction/entrypoint semantics need explicit
  handling; direct reuse of Build would invoke the Go backend and is unsuitable.


### Pinned frontend library-function probe

- Installed Go 1.27.0 in `/tmp/alchem-go127` to satisfy upstream's declared
  toolchain requirement. Created a separate `adapters/alchem` module, pinned to
  upstream pseudo-version `v0.3.12-0.20261115034408-0b73f880b108` with go.sum
  checksums. Initial fetch required network; subsequent tests/build ran offline.
  An initial go-get attempt from the repository root failed because that root
  has no go.mod; fetching from the adapter module succeeded.
- Added fail-first adapter tests: valid source initially emitted no JSON and all
  invalid-source cases were incorrectly accepted by the stub. Implemented the
  exported upstream ParseModule + Analyze pipeline in library mode, then a
  deliberately restricted typed integer-expression lowering to the shared IR.
- The probe requires one explicitly selected parameterless integer function;
  source main/runtime semantics are not reinterpreted. Unsupported constructs
  are rejected, not silently dropped. CLI errors emit no IR.
- Added `--with-source` to full verification (also runs Go/Rust comparison), and
  six source-to-native probes with deterministic IR and matching Go/Rust output:
  constants, addition, nested addition, -1, signed overflow and minimum i64.
- Complete command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, Rust library/CLI tests/build, 15/15
  acceptance cases per backend, 64 differential programs, adapter tests/build,
  and 6 source probes through both native backends. No remaining test failures.
- Documented supported boundaries and next full-frontend requirements in
  `docs/frontend-boundaries.md`. No modifications to production Alchem; no
  workflow dispatch, PR merge, or production integration.


### Strict JSON object keys

- Added ten regression fixtures for duplicate root/function/block/instruction/
  terminator keys, escaped duplicate keys, and incorrectly cased structural
  fields. All ten failed against Go's old decoder; Rust's test also failed on
  duplicate keys. Both decoders now reject these inputs with `E_INVALID_IR`
  before object fields can be overwritten.
- Go validates decoded key tokens before typed decoding. Rust uses a Serde
  visitor that rejects repeated map keys while constructing JSON values.
  Added serde as an explicit compiler-build dependency using the existing
  locked version/checksums; initial fetch required network, verification offline.
- Added a positive fixture verifying escaped canonical key names and Unicode,
  case-sensitive SSA names still compile and execute correctly. The manifest
  test initially errored on the intentionally wrong-cased version key; corrected
  it to require a valid IR header only for positive fixtures.
- Full command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 5 Rust library tests plus 1 CLI test,
  Rust build, 26/26 shared cases per backend, 64 generated differential programs,
  adapter tests/build and 6 source probes. No remaining test failures.
- Updated the IR validation contract and Rust setup documentation. Existing
  full-frontend/runtime limitations remain. No production changes or merge;
  commit uses `[skip ci]` to avoid Actions runs.


### Wrapping subtraction and multiplication

- Added `sub.i64` and `mul.i64` as additive version 1 IR extensions, with the
  existing lhs/rhs SSA operand shape. Documented ordered subtraction and
  low-64-bit multiplication, both wrapping modulo 2^64 without overflow traps.
- Added tests and fixtures first. Go and Rust positive tests initially failed
  with `E_UNKNOWN_OPCODE`; source-adapter positives initially failed with
  `E_UNSUPPORTED`. Implemented native x86-64 SUB and two-operand IMUL in Rust,
  mirrored in Go, and extended typed frontend expression lowering for - and *.
- Eight positive fixtures cover ordered/reversed subtraction, underflow,
  multiplication, negative operands, zero, and overflow including min-i64 * -1.
  Six negative fixtures cover missing/undefined operands and invalid immediate
  fields for both new opcodes. The seeded differential generator now mixes
  addition, subtraction and multiplication against a Python arithmetic oracle.
  Source probes now include operand order, mixed-expression precedence, negative
  multiplication and overflow; division remains explicitly unsupported.
- Full command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 5 Rust library tests plus 1 CLI test,
  Rust build, 40/40 shared cases per backend, 64 mixed-arithmetic differential
  programs, adapter tests/build and 12 source probes. Native executables match
  byte-for-byte between backends; no remaining test failures.
- Rust remains the leading candidate, with Go maintained as the executable
  reference. The earlier smoke measurements are historical samples from
  revision 8334491, not updated performance claims for this implementation.
- Source support still excludes bindings, parameters, calls, branches, source
  main/runtime behavior and project imports. No production changes or merge;
  commit uses `[skip ci]` to avoid Actions runs.

### First executable Alchem source program

- Added `examples/invoice.alc`, a real public void main/0 with integer bindings,
  multiplication, subtraction and `System.halt(total)`. It computes 12*5-18.
  Added `scripts/build-native.sh` and a Rust `--source FILE --output PROGRAM`
  command, using a sibling prebuilt frontend (or explicit --frontend path).
  Compiler binaries are available locally in build/native; source compilation
  needs no installed Go/Rust/C toolchain after those binaries are built.
- Tests first reproduced rejection of real main/bindings and the missing Rust
  source-mode CLI. Implemented local SSA bindings/aliases, normal main exit 0,
  and a final System.halt. The pinned upstream runtime checks statuses 0..255;
  the adapter proves that range for this static integer subset and rejects
  unsupported out-of-range cases rather than truncating source-language status.
  Explicit library-function probes retain their earlier low-byte return rule.
- Added source-main end-to-end tests with spaces in paths, sibling frontend
  discovery, empty PATH, deterministic output, executable permissions, Go IR
  reference equivalence, invalid source and preservation of existing output.
  A further regression test exposed source overwrite; the driver now rejects
  an output path that resolves to its input source, preserving the source file.
- Full command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 5 Rust library tests plus 2 CLI tests,
  Rust build, 40/40 shared cases per backend, 64 arithmetic differential programs,
  adapter tests/build, 12 library source probes, 6 real-main programs and 5
  source rejection cases plus source-overwrite protection. No remaining failures.
- Build command (exit 0), using the same PATH/cache/frontend overrides:
  `bash scripts/build-native.sh`. Then:
  `build/native/alchem-native --source examples/invoice.alc --output /tmp/alchem-invoice`.
  Executed /tmp/alchem-invoice: exit 42, empty stdout/stderr.
- Built the pinned upstream CLI for comparison only:
  `/tmp/alchem-go127/bin/go -C adapters/alchem build -mod=readonly -o /tmp/alchem-upstream-reference github.com/SmithOperatingSolutions/alchem/cmd/alchem`
  with the documented GOPATH/cache/offline settings. Copied the example to
  /tmp/alchem-upstream-invoice and ran the reference CLI's build command with
  Go 1.27 on PATH. Both native and upstream executables exited 42 with empty
  stdout/stderr. Upstream module sources remained read-only and unchanged.
  This reference build is not part of the native compilation path.
- `strace -f -e trace=execve` initially failed under sandbox ptrace restrictions.
  Network/permission-enabled execution of the same new process trace succeeded:
  only build/native/alchem-native and its sibling alchem-source-probe executed.
  No Go compiler, rustc, Cargo, GCC, Clang or linker ran during source compilation.
- Rust clippy with warnings denied, adapter go vet, shell syntax checks and
  git diff --check passed. Setup, source-mode semantics and scope are documented
  in docs/quickstart.md and the frontend/backend READMEs.
- This is now a usable restricted Alchem executable subset, not full language
  compatibility. IO, general calls, multiple functions, parameters, branches,
  project imports and the actor/runtime system remain unsupported. Production
  Alchem was not modified. Commit uses [skip ci]; no merge or workflow dispatch.


### Authorized checkpoint merge

- The user explicitly authorized merging PR #2 and PR #3 after verification,
  superseding the initial merge-free verification scope for these two PRs.
- Verified exact PR #2 head bb8fabef319f72fac780fc2caa225dcbad922c7f in an isolated
  worktree: both Python tests and all documentation presence checks passed.
  Merged PR #2 as c6fc6512f92248c8f16508a76ba5e9b9d0e5d19f, preserving ancestry
  and using [skip ci]. Its current docs/harness workflows are manual-only.
- Retargeted PR #3 to main and merged that updated baseline into its branch
  without conflicts (local tested revision 4c63be68e726478fc01970f3ecaff06c07abfaa8).
  Only the manual workflow configuration changed relative to the previously
  verified compiler implementation.
- Re-ran the complete local command with the documented toolchain/cache setup:
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Exit 0: Python/Go/Rust/adapter tests and builds, 40/40 cases per backend,
  64 differential programs, 12 library probes, 6 executable-main programs,
  5 source rejections and source-overwrite protection all passed.
- PR #3 is prepared for the authorized checkpoint merge with no remaining
  local-suite failures. [skip ci] is retained; no workflow dispatch or production
  Alchem changes. Future compiler development belongs on a fresh branch from
  the merged checkpoint; self-hosting is still future work.

### Native functions milestone toward self-hosting

- Continued on fresh branch feat/native-functions from verified merged main
  654d3467361ec4613d2085873938903e4d3958b1. Added the explicit self-hosting roadmap
  in docs/self-hosting.md; the Rust/Go implementation is still the bootstrap.
- Specified v2 IR and the internal integer calling convention before codegen.
  V1 remains supported unchanged. V2 has multiple i64 functions, up to six
  parameters, direct calls, full i64 returns, relative call fixups, aligned
  frames and preserved caller SSA values. Function names may be forward refs.
- Added failing Go/Rust tests and fixtures first: existing compilers rejected
  call/parameter fields and version 2. Added a source test that failed because
  the old adapter rejected multiple functions. Implemented the new Rust backend
  module, matching Go reference, and typed source-helper lowering to real calls.
- Added 24 shared fixtures (7 positive and 17 negative), bringing the suite to
  64 cases. Coverage includes identity, zero/six-argument calls, noncommutative
  six-register ordering, nested/forward calls, live caller values, undefined
  callees/arguments, arity, duplicate symbols/parameters, parameter redefinition,
  null/missing fields, >6 parameters and recursive call graphs. One run exposed
  Go classifying null parameter type as unsupported (63/64 passed); fixed it to
  reject malformed parameter fields with E_INVALID_IR, matching Rust.
- Added reverse-dependency-order tests for accepted depth 64 and rejected depth
  65. Graph validation memoizes path height so earlier visits to a callee cannot
  hide a longer later path. Recursive graphs, >256 functions, >6 parameters and
  frames larger than 1 MiB are rejected. These bounds are not a host-stack guarantee.
- Expanded differential testing with 64 seeded v2 programs using 0–6 parameters,
  shuffled declaration order, nested calls, argument permutations and caller
  values live across calls. Together with 64 arithmetic programs, all 128 native
  results match an independent Python oracle and Go/Rust executable bytes match.
- Added examples/invoice-functions.alc, private helpers, nested calls inside
  arguments, six-argument source order, and library probes using helper calls.
  The source adapter uses bounded static evaluation only to prove System.halt
  stays in 0..255; emitted IR retains machine calls. A regression test verifies
  exponentially repeated acyclic calls hit the 100,000-step proof budget.
- Complete command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 7 Rust library tests plus 2 CLI tests,
  Rust build, 64/64 shared cases per backend, 128 differential programs, adapter
  tests/build, 13 library probes, 10 real-main programs and 8 source rejections
  plus output-preservation/source-overwrite protection. No remaining failures.
- Rebuilt release tools with scripts/build-native.sh using the same environment.
  Compiled examples/invoice-functions.alc to /tmp/alchem-invoice-functions.
  Also built its copy with the pinned upstream reference compiler in
  /tmp/alchem-upstream-functions: both exited 42 with empty stdout/stderr.
  No production source changes. The native v1 add(20,22) executable SHA-256
  still matches the historical recorded measurement artifact.
- Rust clippy with warnings denied, adapter go vet and git diff --check passed.
  No Actions dispatch or new PR merge. Next milestone is typed comparisons and
  control flow, then recursion/iteration, byte data and file IO; no self-hosted
  compiler or full Alchem compatibility is claimed yet.

### Typed conditionals and first Alchem-written compiler helper

- Continued on feat/native-functions in the same draft PR #4, as requested.
  Specified v3 structured conditional IR before implementation. V1/V2 remain
  supported unchanged. V3 adds normalized booleans, six signed i64 comparisons,
  not, typed if results, branch-private SSA scopes and native conditional jumps.
- Added failing tests first: Go rejected the new cond field, Rust rejected v3,
  and the old source adapter rejected if values. Implemented new Rust and Go
  modules with matching validation/code generation. Branches can see prior
  parent values and their own locals; sibling/future/self references and wrong
  yield types are rejected. Every branch is validated even when untaken.
- Added 31 shared cases (95 total): both outcomes of all six comparisons,
  signed min/max ordering, boolean not/merge, private yields, type/scope/shape
  errors, and an untaken branch containing an exponentially expensive call
  graph. Native execution must skip that branch. Both backends accept 16 nested
  conditionals and reject 17. Go decodes nested instruction arrays lazily so the
  semantic depth limit is applied before descending further into branch code.
- Source lowering now supports boolean locals/not, integer comparisons, if
  values used in later computation and terminal if statements, including helper
  return paths and main halt paths. Branch-local source bindings do not leak.
  Emitted IR retains both native branch bodies; the bounded halt proof follows
  only the selected source path. Nonterminal statement-if, arbitrary early
  returns, boolean and/or, unless, recursion and loops remain unsupported.
- Added examples/invoice-conditional.alc. Added the first small compiler
  component actually written in Alchem: implementations/alchem/lexer.alc,
  a preliminary ASCII category classifier. It is not a complete lexer or a
  self-hosted compiler. The generated native test main checks all 128 ASCII
  values plus -2, EOF (-1), 128, 255 and maximum i64: 133 independent oracle
  checks, without modifying the component's source file.
- Added 64 seeded v3 differential programs with signed full-width arithmetic,
  comparison edge values, boolean merges/not, nested branches and function
  calls. Each result matches an independent Python signed-i64 evaluator, and
  Go/Rust executable bytes match. Total differential coverage is 192 programs.
- Complete verification command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 9 Rust library tests plus 2 CLI tests,
  Rust build, 95/95 shared cases per backend, 192 differential programs, adapter
  tests/build, 15 library probes, 25 executable-main programs and 8 source
  rejections plus output-preservation/source-overwrite checks. No remaining
  failures. Rust clippy with warnings denied, adapter go vet and diff checks pass.
- Rebuilt release tools with scripts/build-native.sh. Compiled the conditional
  invoice to /tmp/alchem-invoice-conditional and the classifier smoke test to
  /tmp/alchem-lexer-classifier: exit 42 and exit 0 respectively, empty stdout/
  stderr. The invoice's copied source, built separately by the pinned upstream
  reference in /tmp/alchem-upstream-conditionals, also exits 42 with empty output.
  V1 add(20,22) and V2 six-register-call executable bytes match pre-v3 emission.
- Updated IR/ABI, quickstart, frontend/profile docs and the self-hosting roadmap.
  Next steps are bounded iteration/recursion, byte buffers/strings and file IO,
  followed by token assembly/parser/compiler code in Alchem and self-rebuilds.
  No production Alchem changes, workflow dispatch or PR merge. Commit uses
  [skip ci]; this remains bootstrap work rather than completed self-hosting.

### PR #4 merged; bounded recursive traversal

- Explicitly authorized PR #4 merge completed at
  `f5506748c92a3034b772be9d1e395878416f29c5` with [skip ci]. Continued from
  that main checkpoint on feat/native-iteration; new work remains separate.
- Specified V4 before implementing bounded recursive calls. New Go/Rust tests
  first failed on unsupported version; the source regression first failed on
  the prior recursive-graph rejection. V4 retains typed V3 instructions and
  permits recursive graphs; older versions retain their graph restrictions.
- Both native backends initialize private R14/R15 counters and guard each
  function entry before frame allocation. Limits: 256 active functions and
  1 MiB charged frame storage (rounded frame plus 16 bytes per active call).
  Normal returns restore both charges. Failure writes exactly
  `E_RUNTIME_LIMIT: native call/stack budget exceeded\n` to stderr and exits 70
  through Linux syscalls, without Go/Rust runtime dependencies. This requires
  sufficient host stack and does not bound total calls or execution time.
- Source recursive graphs now lower to V4, retaining actual native calls.
  Halt-status proofs remain bounded by 100,000 steps and now explicitly cap
  active proof depth at 256 for V4 (64 otherwise). Infinite source recursion
  fails the proof rather than overflowing the compiler's stack. Added direct
  and mutual recursion source coverage and examples/recursive-sum.alc.
- Added six shared cases: base case, countdown, depth 256 accepted, depth 257
  rejected at runtime, infinite recursion guarded, and unused recursion.
  Shared suite now contains 101 cases. Added 64 seeded six-argument recursive
  differential programs, including signed arithmetic and caller values live
  after recursive calls: Python oracle results and Go/Rust bytes match.
- Added three independently generated runtime-budget checks: a finite recursive
  chain below the depth limit exceeds active frame bytes; 40 large-frame calls
  restore byte charges; 300 shallow calls restore depth. The stack case would
  return 42 without its byte guard, so the depth guard cannot mask its failure.
- The Alchem-written classifier now includes count_digits(first, last), a real
  recursive traversal over integer ordinals. Its smoke main verifies 10 digits
  in ASCII 0..127. This is not byte-buffer traversal or a complete lexer.
- Complete final command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 10 Rust library tests plus 2 CLI tests,
  Rust build, 101/101 shared cases per backend, 256 differential programs,
  3 runtime-budget programs, adapter tests/build, 16 library probes,
  27 executable-main programs and 8 source rejections. Executable permission,
  deterministic output, preservation and source-overwrite checks remain passing.
  Environment remains Linux x86_64, Python 3.12.14, native Go 1.23.12,
  frontend Go 1.27.0 and Rust/Cargo 1.85.0.
- Rust clippy with warnings denied, adapter go vet and git diff --check pass.
  Rebuilt release tools with scripts/build-native.sh. Native recursive sum and
  its copied source built with the pinned upstream compiler both exit 42 with
  empty stdout/stderr; recursive classifier smoke exits 0 with empty output.
  Temporary upstream comparison builds do not modify production source.
- No remaining verification failures. Next: immutable byte buffers with explicit
  bounds/default behavior, then Alchem-written byte cursors and token assembly;
  writable storage, file IO and self-rebuilds remain later milestones. No
  self-hosting or full source compatibility is claimed. No Actions dispatch;
  workflows remain manual-only and commits use [skip ci].
- Published the verified milestone as commit 8d1a37b and draft PR #5:
  https://github.com/SmithOperatingSolutions/alchem-native/pull/5. The new PR
  remains unmerged; later feature work should continue on its existing branch.

### Immutable bytes and Alchem byte cursors (PR #5)

- Continued on feat/native-iteration in draft PR #5. Specified V5 immutable
  buffers and their native ABI before implementation. Go/Rust regression tests
  first failed on unsupported byte data/version; the source regression failed
  on the previous integer-only parameter restriction.
- V5 adds bytes.const, bytes.len, bytes.get and if.bytes. Bytes are typed,
  immutable process-lifetime references to static packed payloads in the ELF's
  RX segment: u64 length plus u8 data. Mixed integer/bytes arguments occupy the
  same six native argument registers; results remain i64. RIP-relative fixups,
  checked loads and direct calls need no linker, heap or host-language runtime.
  V5 retains V4's native depth/active-frame guards; V1–V4 restrictions remain.
- Indexing normalizes a negative index once by adding length; any remaining
  out-of-range index returns an already-evaluated i64 default. NUL and 255 are
  ordinary bytes. Empty buffers always use the default. Each literal is capped
  at 1 MiB and total literal storage including headers at 4 MiB; all branches
  and unused functions count. Unsupported sizes preserve existing output.
- The pinned source adapter lowers a deliberately byte-only list[integer]
  subset: literal elements 0..255, named typed parameters, bindings/aliases,
  conditional byte values, Enum.count and three-argument Enum.at. Empty lists
  require an expected type. Computed elements, list tails, general lists,
  strings, mutation and byte-return signatures remain unsupported. Static
  storage budgets are checked before halt proofs. Proof handles preserve list
  identities while emitted IR retains actual native reads/calls.
- Added 33 shared cases (134 total): index/length/empty/default/boundary behavior,
  negative/extreme i64 indices, byte parameters, both byte-condition outcomes,
  malformed literal elements/fields, operand/call/branch type errors, private
  branch scope, invalid bytes in unused branches, and old-version rejection.
- Added 64 seeded buffer differential programs with mixed six-register recursive
  arguments, private branch literals, empty/nonempty buffers, negative-index
  defaults and references live across calls. Independent Python results match;
  Go/Rust executable bytes match. Total differential programs: 320.
- Added four generated storage-budget programs: exact 1 MiB literal acceptance,
  rejection one byte above; exact 4 MiB total-with-headers acceptance, rejection
  one byte above. Combined with V4 checks, seven budget programs pass.
- Alchem-written lexer helpers now traverse actual data: byte_at (negative or
  out-of-range cursor => EOF -1), count_buffer_digits, skip_spaces and scan_digits.
  Source tests cover all-ASCII digit counting, NUL/255, EOF, whitespace-only
  buffers and digit spans reaching EOF. These use bounded recursion and are not
  yet a complete lexer or unbounded-input scanner. Added examples/byte-cursor.alc.
- Final complete command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 11 Rust library tests plus 2 CLI tests,
  Rust build, 134/134 shared cases per backend, 320 differential programs,
  7 budget programs, adapter tests/build, 18 library probes, 47 executable-main
  programs and 13 source rejections. Deterministic bytes, executable permissions,
  empty-PATH compilation and output/source preservation remain passing.
  Toolchain versions remain those recorded for the previous milestone.
- Rust formatting/clippy with warnings denied, adapter go vet and diff checks
  pass. Rebuilt release tools with scripts/build-native.sh. Separate copied
  source builds with the pinned upstream compiler in /tmp/alchem-upstream-bytes
  match the native byte-cursor exit 42, lexer smoke exit 0, and negative/extreme
  index example exit 42, all with empty stdout/stderr. Production is unchanged.
- No remaining verification failures. Next: token assembly/lexical errors,
  writable storage and iteration for larger inputs, strings/file IO and eventual
  self-rebuilds. Updated the IR/ABI, quickstart, frontend boundary, component
  docs and self-hosting roadmap. Continue in the same draft PR #5; do not merge
  it without an explicit request. Workflows remain manual-only; use [skip ci].


### Alchem-written expression token scanner (PR #5)

- Continued in the same feat/native-iteration branch/draft PR #5. Specified the
  bounded expression lexer API and failure behavior in spec/lexer.md, then added
  the independent Python oracle. Its first run failed on undefined token_start
  against the prior Alchem component. A source binding named length was also
  rejected as a reserved builtin; renamed it before verification.
- Implemented token scanning entirely in implementations/alchem/lexer.alc, using
  the existing V5 byte/call/conditional subset. No new backend opcodes, bootstrap
  dependencies or production lexer changes. Identifiers accept ASCII letters or
  underscore first, then letters/underscore/digits; integers are maximal decimal
  digit runs. Signs and +, -, *, (, ) remain separate tokens. Whitespace is skipped.
- Pull-style token_start/token_kind/token_end return source byte spans without
  copying lexemes or allocating token collections. EOF is an empty span at input
  length. An invalid byte has kind 0 and a one-byte span so callers can recover.
  token_error distinguishes invalid bytes (1), invalid cursors (2), and oversized
  inputs (3). token_count returns the remaining token count or -1 on error;
  first_error returns the exact bad-byte offset, -1 on success, -2 for invalid
  cursor, or -3 for oversized input. Length failure takes precedence.
- Public token requests reject input longer than 128 bytes before scanning.
  This keeps both maximal-span and stream recursion within the existing 256-call
  native budget. The low-level byte cursor helpers retain their prior behavior.
  No Unicode, comments, strings, keyword recognition, integer conversion/overflow,
  token storage or full production-language compatibility is claimed.
- Added 1,227 generated Alchem oracle programs: all 256 single-byte inputs,
  64 seeded streams with every cursor checked, identifier/digit boundaries,
  signs/punctuation, invalid-byte recovery, NUL/non-ASCII, error offsets, EOF,
  minimum/maximum i64 cursors and exact 128/129-byte input bounds. Expected spans
  are independently calculated in Python and compared as full i64 values inside
  Alchem. Both native backends execute the checks, emit identical bytes and
  preserve deterministic output/0700 permissions with an empty host-tool PATH.
- The first combined 128-token summary probe exceeded the independent 100,000-
  step source halt-proof budget. Split whole-stream summaries into separate
  probe programs; each passes without raising compiler limits or bypassing source
  main/halt checking. This proof budget remains an intentional source limitation.
- Separate copied-source comparisons in /tmp/alchem-upstream-token-lexer verify
  the new smoke main, 128-token count and exact invalid-byte offset with the pinned
  upstream compiler: all native/reference programs exit 0 with empty stdout/stderr.
  No production source files are modified by these comparison builds.
- Complete final command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 11 Rust library tests plus 2 CLI tests,
  Rust build, 134/134 shared cases per backend, 320 differential programs,
  7 budget programs, adapter tests/build, 18 library probes, 47 executable-main
  programs, 13 source rejections and all 1,227 lexer oracle programs. Python
  syntax compilation and git diff --check pass. Toolchain versions are unchanged.
- Updated the component docs, lexer contract, quickstart, handoff and self-hosting
  roadmap. No remaining verification failures. Next: checked decimal conversion
  and expression parsing, then writable storage/iteration, file IO and eventual
  self-rebuilds. This is an Alchem-written lexer component, not a self-hosted
  compiler. Publish with [skip ci] to the same draft PR #5 and leave it unmerged;
  all workflows remain manual-only and production Alchem remains untouched.

### PR #5 merged; Alchem integer conversion and expression frontend

- Explicitly authorized PR #5 merge completed at
  `3e432bb465f94c5d3746b42aa03ba561fb7721bc` with [skip ci]. Confirmed zero
  GitHub Actions runs for the merge. Continued from that main checkpoint on
  feat/alchem-parser; new feature work remains separate and unmerged.
- Specified checked decimal spans and arithmetic grammar/error semantics before
  implementation. New independent oracle runs first failed on undefined
  decimal_error and expression_error against the merged Alchem component.
- Added decimal_error/decimal_or and token-integrated integer_error/integer_or,
  entirely in Alchem. Validation rejects malformed spans/sign flags, nondigits,
  oversized input and overflow. Nonpositive accumulation supports minimum i64
  without forming its unrepresentable positive magnitude; the value pass runs
  only after checked validation. Leading zeros and caller-selected fallbacks
  are explicit. Signs remain separate lexer tokens for parser consumption.
- Added a recursive-descent arithmetic parser and separate value pass, also
  entirely in Alchem, using the existing V5 subset without new backend opcodes
  or dependencies. expression_error/expression_or support +, -, *, unary signs,
  parentheses, precedence, left associativity and wrapping i64 arithmetic.
  Checked literals reject overflow; an immediately preceding minus admits the
  minimum-i64 magnitude. Complete expressions must consume EOF. Limits: 128
  bytes and 16 nested signs/parentheses, with explicit lexical/syntax/size/
  overflow/depth error codes. The evaluator emits no AST or machine code.
- Added 496 integer cases in 135 native oracle programs: full i64 boundaries,
  leading zeros, overflow before/after the final digit, all byte values, invalid
  spans and extreme cursors/sign flags, plus lexer-token integration. Added
  354 expression oracle programs covering precedence/associativity, full-width
  wrapping results, unary minimum i64, invalid syntax/bytes, 64 seeded valid
  expressions and invalid continuations, exact input/depth boundaries, 64-term
  chains and mixed deep nesting/long expressions. Python arbitrary-precision
  integers and AST evaluation provide independent expected results. All values
  are compared at full i64 inside Alchem; Go/Rust bytes and execution match.
- Testing exposed repeated leading-whitespace scanning; normalized the root
  cursor once before parsing/evaluation. Deep and some compound evaluator calls
  still exceed the bootstrap's independent 100,000-step source-main halt proof.
  Do not claim arbitrary source-main evaluation support or raise the budget.
  The expression suite uses 188 explicit library probes for value/boundary
  behavior and 166 source-main probes for syntax checks; the ordinary component
  smoke main also retains halt validation. This intentional bootstrap limitation
  is recorded in spec/expressions.md and the benchmark readiness gates.
- Complete final command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 11 Rust library tests plus 2 CLI tests,
  Rust build, 134/134 shared cases per backend, 320 differential programs,
  7 budget programs, adapter tests/build, 18 library probes, 47 executable-main
  programs, 13 source rejections, 1,227 lexer oracle programs, 135 integer oracle
  programs and 354 expression oracle programs. Deterministic bytes, permissions,
  empty-PATH execution and output/source preservation remain passing. Python
  syntax compilation and git diff --check pass. Toolchains remain unchanged.
- Separate copied-source builds with the pinned upstream compiler in
  /tmp/alchem-upstream-parser match native smoke, precedence, overflow diagnostic
  result and minimum-i64 conversion: all exit 0 with empty stdout/stderr.
  Comparison builds do not change production source. Existing prebuilt release
  bootstrap tools compile these new Alchem functions; no host-language codegen
  operation was added to the source compilation path.
- Added docs/self-hosting-benchmarks.md with explicit readiness gates and a
  future A1 -> A2 -> A3 protocol: compiler-profile closure, dynamic runtime/IO,
  Alchem-written semantic/codegen/output stages, A2/A3 byte equality, correctness
  tests, then separated wall-time/RSS/size samples and hashes. No self-hosting
  performance measurement or timeline is claimed. Historical Go/Rust smoke
  measurements remain historical bootstrap results.
- No remaining automated verification failures. Known limitation: static source
  halt proofs can reject expensive evaluator mains; dynamic IO/self-hosting
  requires a runtime status policy. Next: declarations/types/names/calls and
  semantics used by the compiler itself, writable storage/larger-input iteration,
  IO and native code/output generation in Alchem. Continue as a new draft PR
  from feat/alchem-parser; do not merge it without a new explicit request.
  Workflows remain manual-only, commits use [skip ci], production is unchanged.

### Native checked process status; source-proof blocker removed (PR #6)

- Continued on feat/alchem-parser in the same draft PR #6. Specified V6 before
  implementation. New Go/Rust tests first failed on unsupported version; source
  tests failed on the former evaluation-budget and out-of-range proof rejection.
- V6 retains V5 instructions/types/byte ABI and V4 resource guards, and checks
  the full RAX result returned from main in the process stub. An unsigned compare
  against 255 catches negative/large statuses. Valid 0..255 exits normally;
  failure writes exactly `E_HALT_STATUS: expected status 0..255\n` to stderr and
  exits 70 through direct Linux syscalls. Normal status 70 has empty stderr.
  Helper returns remain full i64; call/stack exhaustion keeps E_RUNTIME_LIMIT.
- Executable source consistently lowers to V6, including simple mains. Removed
  the source evaluator and static halt-status proof instead of raising its limits.
  Compilation parses/type-checks/lowers all paths but never runs main/helpers.
  Ordinary completion returns zero; final/terminal-branch System.halt results
  remain native computations. Explicit library probes retain V1–V5/low-byte
  behavior. Experimental source behavior intentionally expands: invalid halt
  statuses compile then fail natively; infinite recursion hits native guards.
- Added 12 shared V6 cases (146 total), covering 0/255/normal 70, negative/256/
  min/max statuses, recursion limits, bytes/branches and wide helper returns.
  Added 64 independently evaluated status differential programs (384 total)
  using wrapping arithmetic, wide helpers, byte-index/default paths and full-i64
  status classification; Go/Rust bytes and results match the Python oracle.
- Compared all 58 positive V1–V5 fixtures against the pre-V6 Go reference binary:
  both current backends emit exactly the previous executable bytes. Older raw
  IR contracts remain unchanged. Native errors do not masquerade as normal 70.
- All 354 expression oracle programs now use ordinary source main; removed the
  188-library-probe workaround. The direct Rust --source CLI additionally checks
  a deeply nested evaluator and an acyclic program with 2^19 leaf calls that
  exceeded the former host-proof budget. A unit check retains all 39 emitted
  call instructions in that source graph, preventing compile-time substitution.
- Source acceptance now covers 52 successful mains, 6 native runtime-error cases
  (including invalid statuses and guarded infinite recursion), and 9 compile-time
  source rejections. Preservation/overwrite, deterministic output, permissions,
  sibling frontend discovery and empty-PATH checks remain passing.
- Complete final command (exit 0):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 12 Rust library tests plus 2 CLI tests,
  Rust build, 146/146 shared cases per backend, 384 differential programs,
  7 budget programs, adapter tests/build, 18 library probes, 52 source mains,
  6 runtime failures with exact expected diagnostics, 9 source rejections,
  1,227 lexer oracle programs, 135 integer oracle programs / 496 cases and
  354 expression oracle source-main programs. Toolchains remain unchanged.
- Rust formatting/clippy with warnings denied, adapter go vet, Python syntax and
  git diff --check pass. Rebuilt release tools with scripts/build-native.sh.
  Copied-source comparisons in /tmp/alchem-upstream-runtime-status match pinned
  upstream behavior on deep-evaluator exit 42, normal status 70 and wide-helper
  exit 42, all with empty stdout/stderr. Invalid-status diagnostics are explicitly
  native-profile messages, not a claim to duplicate production runtime errors.
- Updated V6/ABI, frontend boundaries, quickstart, component/handoff docs and the
  self-hosting benchmark gates. The previously recorded static-proof limitation
  is resolved. Native input/nesting/active-call/frame limits still apply; there
  is no runtime instruction/time budget. Writable storage, IO, broader source
  grammar/semantics and Alchem-written code/output generation remain future work.
  No remaining verification failures or self-hosting performance claim. Publish
  with [skip ci] to the same unmerged draft PR #6; production/workflows unchanged.

### Native byte output and developer delivery checkpoint (PR #6)

- Continued in the same PR #6 with V7 native output, then prepared the requested
  commit/merge handoff. Spec and regressions were added first: Go/Rust rejected
  V7/stream fields, and the source adapter rejected literal IO.puts statements.
- V7 adds bytes.write(value, stream) for stdout/stderr, returning the complete
  i64 byte count. Generated write loops handle short progress and EINTR; zero
  progress or other syscall errors attempt E_RUNTIME_IO on stderr and exit 74.
  SSA slots and all six incoming argument values survive syscalls. Empty buffers
  return zero without writing. There is no formatting/newline at the IR level.
  Partial output is not rolled back; EAGAIN fails, and default Linux signal
  behavior (including SIGPIPE) is retained rather than claimed away.
- Source supports one-argument literal IO.puts, encoded as UTF-8 plus one LF.
  Output works in integer helpers, branches and before later statements. Programs
  with output select V7; other source remains V6. Strings/interpolation/device
  overloads and general IO remain unsupported. Added examples/hello-native.alc.
  No heap, writable buffers, input/file creation or production changes are added.
- Added 13 shared cases (159 total): stdout/stderr, empty output, write ordering,
  live values, untaken output, invalid streams/fields/types and V6 rejection.
  Added 64 binary-output differential programs (448 generated programs total)
  with all-byte payloads, up to 1 MiB output, exact full-width byte counts and
  six-register helper values live across syscalls. Both backends match.
- Output failure tests pass on each backend for closed stdout, /dev/full and a
  deliberately filled nonblocking pipe. The latter forces a short first write
  followed by EAGAIN, verifying progress is not mistaken for complete success.
  strace fault injection forces initial write EINTR; both backends retry and
  deliver the exact payload. The default execution sandbox initially denied
  ptrace; reran the output tests and complete suite with tracing permission.
  Final EINTR result is 2/2, not skipped. The harness reports an explicit skip
  if a future environment cannot trace; developers must not call that a pass.
- Complete final command (exit 0, in execution context permitting ptrace):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 13 Rust library tests plus 2 CLI tests,
  Rust build, 159/159 shared cases per backend, 448 differential programs,
  7 budget programs, all output failure/EINTR checks, adapter tests/build,
  18 library probes, 60 successful source mains, 6 expected native runtime errors,
  9 source rejections, 1,227 lexer oracle programs, 135 integer programs / 496
  cases and 354 expression source-main programs. Existing determinism, executable
  permissions, preservation and empty-PATH checks remain passing.
- Compared all 70 positive V1–V6 fixtures to the pre-V7 reference binary:
  both new backends emit identical legacy bytes. Rust formatting/clippy with
  warnings denied, adapter go vet, Python syntax and git diff --check pass.
  Rebuilt release tools with scripts/build-native.sh. Copied-source comparisons
  in /tmp/alchem-upstream-output match pinned upstream hello output (26 stdout
  bytes, exit 0), UTF-8 output (10 bytes, exit 0) and conditional/helper output
  (4 bytes, exit 42), all with empty stderr. Toolchain versions are unchanged.
- Added docs/HANDOFF.md as the next developer's resume guide: main at PR #6 merge,
  exact local command/environment, code map, current limits and test counts,
  proposed bounded immutable byte construction / typed byte-return slice and
  explicit acceptance criteria. It distinguishes the unimplemented storage,
  input/file IO, compiler grammar/semantic/codegen stages and self-rebuild gates.
  Updated CLOUD_WORK.md, API/spec/ABI, quickstart and benchmark-readiness docs.
- No remaining automated verification failures. User explicitly requested commit
  and merge of PR #6 after this verified checkpoint. Use [skip ci] for feature and
  merge commits; all workflows remain manual-only. Resume new work from the merged
  main checkpoint on a new branch; future PR merges need another request. No
  self-hosting benchmark result or completed Alchem-written compiler is claimed.

### Bounded runtime byte construction and typed returns

- Started feat/native-byte-construction from PR #6's merged main checkpoint
  `61351cbdd5fba099fe89c8e9a06f08d5a21e6263`, following docs/HANDOFF.md.
  This continuation is a new draft PR; prior merge authorization ended at #6.
- Specified V8 lifetime/ownership, ABI, budgets and failures before implementation.
  New Go/Rust tests first failed on unsupported V8; the source test first failed
  on the old integer-only helper-return restriction. Added bytes.concat and typed
  byte helper returns in both native backends. Main stays parameterless i64;
  calls, branch results and return operands are checked against declared types.
- V8 entry mmaps a separate 4 MiB anonymous RW arena (not executable). R12 tracks
  its bump cursor, R13 its end; R14/R15 retain active frame/depth roles. Every
  concat gets a fresh immutable record, including empty+empty. Payload cap is
  1 MiB; allocation charge is align8(length+8). All references live until process
  exit; discarded allocations stay charged and no reclamation/GC is claimed.
  Inputs/RX literals remain unchanged. Copies clear DF and use native byte moves.
- Mapping failure, oversize result or exhausted arena attempts exactly
  `E_RUNTIME_ALLOC: byte allocation failed or limit exceeded\n` on stderr and
  exits 71. Checks occur before copying beyond a bound. Only executed concat
  paths allocate. Static literal budgets remain independent. Generated programs
  add no host-language runtime, libc, external compiler or linker.
- Program-mode source supports two-argument Enum.concat over the byte-only list
  subset and list[integer] helper returns, selecting V8 even for static byte
  helper returns. Added examples/byte-construction.alc. Pure library probes
  intentionally retain their earlier profiles and reject new construction;
  computed list elements/general lists/strings/mutation/input/file IO are not
  added. Existing literal IO.puts composes with byte-returning helpers.
- Added 19 shared cases (178 total): ordering/empty inputs, alias preservation,
  static/dynamic/conditional byte returns, nested aliases, wrong operands/returns/
  call result types/main type/fields and old-version rejection. Added 64 seeded
  construction differential programs (512 generated total) with six mixed
  arguments, recursive returns, branch-local allocations, full-width live values
  and original/returned references surviving later allocations. Independent
  Python byte calculations match both native results and executable bytes.
- Added seven arena-budget programs (14 total budget programs): exact 1 MiB
  result and 4 MiB arena bounds, one-byte/record excess, an untaken oversized
  concat, and exact align8 charging for 2^18 discarded leaf allocations. An
  extra allocation then fails, proving returns do not rewind the arena. Injected
  mmap ENOMEM passes on both backends (2/2); trace checks confirm 4 MiB,
  PROT_READ|PROT_WRITE without PROT_EXEC and anonymous/private mapping.
- Complete final command (exit 0, with tracing permission for fault injection):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 14 Rust library tests plus 2 CLI tests,
  Rust build, 178/178 shared cases per backend, 512 differential programs,
  14 budget programs, output failure/EINTR checks (2/2 injection), mmap failure
  injection (2/2), adapter tests/build, 18 library probes, 67 source mains,
  6 expected native runtime errors, 9 source rejections, 1,227 lexer oracle
  programs, 135 integer programs / 496 cases and 354 expression source mains.
  Deterministic output, permissions, empty-PATH/sibling discovery and output/
  source preservation checks remain passing. Toolchains are unchanged.
- Both new backends match the pre-V8 executable bytes of all 76 positive V1–V7
  fixtures. Rust formatting/clippy with warnings denied, adapter go vet, Python
  syntax and git diff --check pass. Rebuilt release tools with build-native.sh.
  Copied-source comparisons in /tmp/alchem-upstream-construction match pinned
  upstream example/recursive exits 42, empty result exit 0 and output/helper
  exit 42 with six stdout bytes, all with empty stderr. Production is unchanged.
- Updated V8/ABI, frontend/quickstart, handoff and benchmark readiness docs. The
  next slice is checked packing of computed integer values into immutable bytes,
  then binary source output/input. Compiler grammar/semantics and Alchem-written
  machine-code/ELF generation remain future work. No remaining verification
  failures, workflow dispatch, automatic merge or self-hosting performance claim.
  Publish with [skip ci] as a new draft PR; request authorization before merging.

## 2026-11-17 — Checked packing and an Alchem-written executable emitter

- Continued on feat/native-byte-construction in draft PR #7. Specified V9 before
  implementation; new Go/Rust tests first failed on unsupported packing, and the
  source regression failed on the former literal-only list restriction.
- Added bytes.pack with ordered i64 operands and typed bytes result. All values
  are checked as full-width 0..255 before allocation; failure attempts exactly
  `E_RUNTIME_BYTE: expected byte value 0..255\n` and exits 72. Values never silently
  truncate. Packing allocates fresh align8(count+8) immutable records from the
  existing arena, including empty records. Byte validation precedes arena
  capacity validation. Args are capped at 4096 to bound inline code growth;
  larger packs fail compilation with E_UNSUPPORTED and preserve output.
- Source program mode supports computed integer list elements. Elements evaluate
  left to right before byte validation, including side effects. Former [x] and
  [40+2] rejections now work; [-1]/[256] compile and fail natively. Valid literal
  byte lists retain their old static lowering/larger limit. A regression checks
  a 4097-element computed list is rejected while the valid literal form remains
  accepted. General/boolean lists, tails and pure-library construction stay out
  of scope. Added 17 shared cases (195 total), 64 packing differential programs
  (576 total) and 6 pack-limit programs (20 total budget programs), including
  exact charging and byte-error precedence in an already-exhausted arena.
- The user's priority shifted to getting an Alchem-written executable producer
  sooner. Implemented implementations/alchem/encoder.alc, initially a checked
  machine-code fragment, then extended it to construct the complete ELF64 image
  in Alchem: ELF/program headers, padding and process-entry machine code. The
  first factory targets Linux exit statuses 0..255 in a 140-byte executable with
  entry 0x400080, one RX load segment at 0x400000, no interpreter/section table,
  128-byte header area and 12 bytes of code. Wider/general metadata and program
  compilation remain future work; this is a deliberately small target.
- The encoder oracle first failed on undefined emit_exit, then on the new missing
  emit_elf_exit factory. It now independently parses every header/segment field,
  validates code/padding, saves Alchem-produced bytes unchanged and executes all
  256 valid images through both backends; four invalid immediates fail. The
  earlier host-generated ELF wrapper was removed. Tests do not patch fields or
  generate an envelope around the Alchem result.
- Added scripts/emit-alchem-executable.py as an explicit bootstrap/export bridge.
  It compiles/runs the Alchem emitter, observes its bytes through existing IR
  output and saves stdout unchanged with 0700/atomic replacement. It constructs
  no ELF header/code. --save-emitter retains the configured Alchem executable,
  which reproduces its image with an empty PATH and no frontend/backend/Python/
  host compiler invocation. The saved emitter is configured during bootstrap;
  accepting new runtime source input is the next priority, not claimed complete.
  Driver export, invalid-status preservation and source/tool overwrite protection
  are tested. Each output replacement is atomic, not a two-file transaction.
- Manual demonstration:
  `python3 scripts/emit-alchem-executable.py --status 42 --output /tmp/alchem-built-exit42 --save-emitter /tmp/alchem-elf-emitter42`.
  The target exits 42 and the saved emitter returns the identical image with
  PATH empty. Image size 140 bytes; SHA-256:
  `5e7532fffd82f1b4a1de51a470131101f62ab03af31a8805788d611a349f4c3d`.
  readelf confirms ET_EXEC/AMD64, entry 0x400080, phoff 64, one RX segment,
  file/memory size 0x8c and alignment 0x1000. Reproducible demo artifacts also
  exist under ignored build/native/alchem-built-exit42 and alchem-elf-emitter42.
- Final complete command (exit 0, with ptrace permitted for fault injection):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Passed 5 Python tests, Go tests/build, 15 Rust library tests plus 2 CLI tests,
  Rust build, 195/195 shared cases per backend, 576 differential programs,
  20 budget programs, output/EINTR and mmap failure injection (both 2/2), adapter
  tests/build, 18 library probes, 73 successful source mains, 13 expected runtime
  errors, 5 source rejections, 1,227 lexer oracle programs, 135 integer programs /
  496 cases, 354 expression source-main programs and 260 complete ELF-writer cases.
  Driver/saved-emitter empty-PATH and output-preservation checks pass. No automated
  verification failures remain; toolchain versions are unchanged.
- Both current backends exactly match all 85 pre-V9 positive V1–V8 executable
  fixtures. Rust formatting/clippy with warnings denied, adapter go vet, Python
  syntax and git diff --check pass. Rebuilt release bootstrap tools. Pinned
  upstream copied-source comparisons match computed-byte exit 42, ordered output
  exit 42 with 13 stdout bytes, and the current complete ELF-writer smoke exit 0,
  all with empty stderr. Production Alchem is unchanged.
- Updated V9/ABI, emitter contract, quickstart, handoff and self-hosting readiness.
  Next: bounded runtime input and a typed bytes-to-bytes executable entry/output
  path, then connect the existing arithmetic frontend to this ELF writer. The
  current small emitter is real executable production, not a general compiler,
  full Alchem compatibility or an A1/A2/A3 self-rebuild benchmark. Keep this work
  on unmerged PR #7 with [skip ci]; no workflow dispatch or automatic merge.


## 2026-11-17 — Reusable compiler written in Alchem, runtime source to executable

- Consolidated the user's requested next work into an end-to-end milestone:
  bootstrap once, then feed different runtime expressions into the same saved
  Alchem executable and receive complete runnable ELF bytes. Updated the roadmap
  around this deliverable, the compiler's own Alchem subset, and self-rebuilds/
  benchmarks. There is no defensible completion percentage; most general compiler
  implementation is still ahead. Component counts did not measure that distance.
- TDD: the native-input harness first failed because V10 was rejected. The
  compiler acceptance harness then failed because the bootstrap implementation
  was missing. Implemented V10 bytes.read in independent Go/Rust backends and
  connected existing Alchem components via compiler.alc. No production source
  was modified. Existing normal frontend modes retain their contracts.
- V10 reads fd 0 through EOF into a fresh immutable arena record, with required
  integer limit 0..1048576, short-read accumulation, EINTR retry and one byte of
  lookahead. Charge is align8(limit+9), including capacity even at EOF. Oversize
  input fails with E_RUNTIME_INPUT/65 rather than truncating; other read errors
  use E_RUNTIME_IO/74. Existing arena guards/resource semantics remain active.
  spec/ir-v10.md and abi.md specify the exact errors/register roles/limits.
- scripts/bootstrap-alchem-compiler.py assembles tracked Alchem function bodies
  and adds a typed native stdin/call/stdout entry bridge. Alchem performs runtime
  parsing, checked literal conversion, wrapping arithmetic evaluation and all ELF
  writing. Empty compiler results explicitly mean source rejection (65, stderr,
  no stdout). The script performs no runtime source interpretation or ELF patching.
  Bootstrap output is atomic 0700, tested for failure preservation and source/tool
  overwrite rejection. The build-native script now builds alchem-arithmetic too.
- The reusable language remains deliberately arithmetic-only: <=128 bytes,
  nesting <=16, +,-,*, unary signs, parentheses, i64 literals/wrapping and result
  0..255, folded into a 140-byte exit ELF. It is not general Alchem syntax or
  self-hosted. Input is runtime data, not compiled-in configuration. Shell output
  redirection is not atomic preservation and is documented separately.
- New compiler acceptance: bootstrap once per backend, then 327 valid runtime
  sources (all 256 statuses, precedence/associativity, overflow wrapping, exact
  size boundary and 64 seeded expressions), plus 13 source/size rejections.
  Independently parse headers/code, save bytes unchanged and execute every image;
  repeat determinism, empty PATH, permissions and byte-identical Go/Rust compiler
  artifacts pass. No re-bootstrap occurs between runtime source programs.
- Input acceptance: 9 data/boundary cases per backend, including empty/NUL/255,
  exact 0/128/256/1MiB limits and overflow; full arena reservation charges at
  exact capacity/exhaustion; preserved six-register helper parameters, returned
  references, EOF, short reads, closed fd, invalid/missing/extra/versioned IR and
  existing-output preservation. Read EINTR injection passes 2/2 with tracing.
- Final complete local command, exit 0 (ptrace permitted):
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Log: /tmp/alchem-v10-complete.log. Python 5; Go tests/build; Rust 15 library +
  2 CLI tests/build; adapter tests/build; 195 shared cases/backend; 576 existing
  differential programs; 20 existing budget/pack programs; new input/compiler
  suites above. Existing source checks: 18 library probes, 73 mains, 13 expected
  native errors, 5 rejections; 1,227 lexer programs; 135 integer programs/496
  cases; 354 expressions; 260 complete ELF-writer cases. Write EINTR, read EINTR
  and mmap ENOMEM injections each pass 2/2; RW/non-executable arena traces pass.
- Additional verification: all 93 existing positive V1–V9 IR fixtures emit bytes
  identical to the pre-V10 backend through both new backends. Rebuilt the prior
  Go source in a temporary archive with -buildvcs=false (VCS stamping is not
  available in an extracted tree). Rustfmt/clippy -D warnings, Python syntax,
  diff checks and the release build script pass. Versions: native Go1.23.12,
  pinned-frontend Go1.27.0, Rust1.85.0, Python3.12.14.
- Real release demonstration with PATH empty: `6*7` produces exit42;
  `(10+5)*3` produces exit45 with the same saved compiler. readelf verifies the
  140-byte target layout. A strace shows one compiler execve, anonymous RW mmap,
  stdin reads and a 140-byte stdout write; no child/host tool invocation.
  Ignored build/native/alchem-arithmetic is 33,685 bytes, mode0700, SHA-256
  `4dc04dc11128120050388486c7964e6f8daca8a75e4ac9d510db061ce055e4b7`.
  Target42 SHA-256 remains
  `5e7532fffd82f1b4a1de51a470131101f62ab03af31a8805788d611a349f4c3d`.
- Next acceptance: the compiler's own source subset, not another standalone
  opcode. The assembled current compiler is 14,516 bytes and 47 functions.
  It requires larger-input storage, declarations/types/scoped names, calls and
  semantic checking, general instruction/branch/frame encoding and wide ELF
  fields. Then A1/A2/A3 rebuilds and correctness gates precede benchmarks.
  Updated handoff/specs/quickstart/readiness to distinguish delivered runtime
  compilation from self-hosting. No remaining automated verification failures;
  no self-hosting performance claim, production modifications or Actions dispatch.
  Publish on the existing branch/draft PR #7 with [skip ci], without merging.


## 2026-11-17 — Alchem-written integer/function source compiler

- Continued directly into the user's requested compiler-source milestone.
  Implemented implementations/alchem/native-compiler.alc rather than extending
  isolated native IR features. No Go/Rust backend changes or new IR profile were
  needed: V10 bootstraps the entire compiler through the explicit native IO entry.
- TDD acceptance first failed on missing --language functions; subsequent added
  tests failed on conditionals, recursion, declaration order and exact 16-slot
  capacity before those behaviors were implemented/fixed. The final source suite
  verifies complete source-to-native behavior, not just parser/helper return values.
- The Alchem compiler parses modules, public/private helper signatures and main,
  whitespace/comments, checked i64 literals, arithmetic, bindings and scoped if.
  It resolves names, arities and integer parameter/return requirements across
  all definitions/branches. It emits real native operations, six-register calls,
  fixed local frames, conditional jumps, forward/self/mutual recursion and
  a complete ELF with an immutable function-address table. Main can occur in
  any declaration order. No host source evaluation/folding occurs in this mode.
- Generated programs check main's full status is 0..255 and active frames<=256;
  either error exits70 without output/diagnostic in the new private ABI. Exact
  main+f(254)..f(0) depth succeeds; f(255) fails. This ABI is documented separately
  from the bootstrap IR diagnostic ABI. Literals are range-checked during source
  compilation and emitted as exact native decimal multiply/subtract sequences;
  normal arithmetic wraps full i64. Helper return values are never truncated.
- Codegen/ELF writing are Alchem-written, including branch lengths and function
  addresses. File/memory sizes now use bounded u16 fields, allowing images beyond
  255 bytes. Layout: header128, entry64, 16*u64 address table128, function code;
  entry0x400080, one RX segment at0x400000, no interpreter/sections. This is still
  bounded metadata, not unrestricted full-width ELF or an external ABI/linker.
- New runtime source profile: 4096 bytes, 16 functions, six integer parameters,
  16 live slots/path, 128 body tokens, 16 expression nesting/operator-chain bounds
  and 16KiB function code. Native byte arena/call limits remain active while the
  compiler runs; repeated immutable construction/re-emission is not a scalable
  storage strategy. Byte-list types/operations, boolean locals/operators, strings,
  imports and general runtime/file APIs are unsupported. Normal main without halt
  and explicit return are not in this initial source profile. Errors/limits are
  explicit in spec/alchem-source-profile.md.
- scripts/build-native.sh now builds alchem-compiler alongside alchem-arithmetic
  and the original tools. --language functions selects the new bootstrap mode;
  default arithmetic behavior and reproduction remain passing. The native bridge
  calls nc_compile(bytes)->bytes and emits generic source rejection65 with no
  stdout on empty result. Protected components include the new source compiler.
- Final new source acceptance passes through both bootstrap backends:
  67 successful programs, 21 source rejections and 3 generated-program runtime
  limits. Cases include 32 seeded arithmetic-helper programs; signed comparisons,
  branch-local bindings and inaccessible-name rejection; all six parameters;
  forward/self/mutual calls, declaration order, comments/private helpers; full
  i64 arithmetic, exact 16-function/16-slot boundaries; recursion256/257 and bad
  process statuses. Every successful image executes with empty PATH and repeat
  bytes match. Saved Go/Rust compiler artifacts match byte-for-byte. All positive
  cases also pass the pinned frontend's independent parser/type checker and
  existing native backend execution oracle.
- Complete local command exits0 with ptrace permission:
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Log /tmp/alchem-functions-complete.log. Existing counts unchanged: Python5;
  Go tests/build; Rust15 library+2CLI; adapter tests/build; 195 shared/backend;
  576 differential programs; 20 resource/pack programs; 9 input boundary cases
  plus auxiliary input checks; read/write EINTR and mmap ENOMEM each2/2;
  18 library probes, 73 mains, 13 native errors, 5 source rejections; lexer1227,
  integers135/496cases, expressions354, encoder260; arithmetic compiler327 valid/
  13 rejections perbackend. New function compiler suite above also passes.
  Release build script, Python syntax and diff checks pass. Tool versions remain
  Go1.23.12/frontendGo1.27.0/Rust1.85.0/Python3.12.14.
- Real demo examples/alchem-compiler-demo.alc (109 source bytes) is parsed by the
  saved compiler with empty PATH and produces a 451-byte executable exiting42.
  readelf confirms complete headers/segment sizes. Disassembly shows parameter
  storage, multiply and indirect native helper call rather than a folded exit.
  strace shows one compiler execve, anonymous RW mmap, stdin reads and a 451-byte
  stdout write; no child/host tool invocation. Ignored artifacts:
  build/native/alchem-compiler, 93,626 bytes, SHA-256
  `c4252324debc838abbe4ac27d6a7800f1b6ba30692e47c04601225f05ec4c472`;
  build/native/alchem-functions-exit42 SHA-256
  `763c6d3e5f128cbc85648261a5bb5ea931d629f9cb306e0acdef39581e88f14a`.
- Profile closure inventory is now measured, not inferred from component counts:
  assembled function compiler42,410 bytes/109 functions; pinned frontend reports
  67 integer+42 byte returns and 175 integer+142 byte parameters across definitions.
  It cannot compile itself under its 4096-byte/16-function integer-only profile.
  Next integrated work is typed byte lists/returns and Enum operations, scalable
  source/symbol/output storage/iteration, larger address tables and full-width
  metadata. docs/compiler-profile-inventory.md gives the next byte source-program
  acceptance and docs/HANDOFF.md the resume point. Self-rebuild/benchmarks remain
  gated. No remaining automated failures, no production modification or Actions
  dispatch. Publish on the existing draft PR #7 with [skip ci], without merging.


## 2026-11-17 — Typed byte source compiler and Alchem-written byte runtime

- Continued the recorded byte-source acceptance without a new native IR version
  or Go/Rust codegen changes. The first end-to-end test failed because the saved
  compiler rejected list[integer] signatures. Implemented typed byte source and
  its native runtime emitter entirely in Alchem, retaining the integer path.
- Parser value packets now carry cursor/type/code; local environments record
  integer versus byte kind. Signatures check integer/list annotations, each call
  argument, declared returns and conditional result agreement. Arithmetic,
  comparisons, indices/defaults and System.halt require integers. Byte references
  can cross six-register mixed calls, recursive calls, returns and scoped branches.
  Both branches and unused definitions remain checked. All list values are byte
  buffers; standalone [] infers bytes in this profile, while pinned-frontend
  positive fixtures provide the expected list context it requires.
- Added computed/literal lists up to 32 elements, evaluated left to right before
  full-width 0..255 checks. Invalid values exit 72 without truncation. All lists,
  including literals/empty values, allocate fresh immutable records. Enum.count,
  signed Enum.at with negative normalization/default, and Enum.concat are emitted
  by implementations/alchem/native-runtime.alc. All arguments evaluate eagerly;
  no host interpreter, linked runtime or AST evaluator executes in the target.
- Generated entry maps a separate 4 MiB anonymous RW/non-executable arena. R12/R13
  are bump/end, records charge align8(length+8), no reclamation; empty pack costs 8,
  one-byte pack 16. Concat checks payload <=1 MiB. mmap/arena/result failure exits 71;
  pack range checks precede allocation, even at full capacity. Generated-program
  private errors have no stderr/output, matching the documented source ABI;
  compiler-process errors retain bootstrap diagnostics. Entry is now 192 bytes,
  function table at file 320, code at 448; entry address remains 0x400080. Earlier
  integer source output layout changes but semantics are preserved. Raw bootstrap
  IR V1–V10 is untouched. Contracts were specified in spec/alchem-byte-profile.md.
- New byte-source suite passes through both bootstrap backends: 45 successful
  programs, 22 type/profile rejections, 4 byte-range failures and 9 arena/evaluation-
  order programs per backend. Positive programs also agree with independent
  pinned frontend/native backend execution. Cases cover seeded byte data/NUL/255,
  exact 32 lists, mixed six arguments and byte returns, aliases surviving calls,
  untouched original input, nested/scoped byte if values and untaken invalid pack,
  signed extreme indexing/defaults, empty concat, recursive construction,
  mismatched argument/return/branch types, arithmetic on bytes and list tails.
- Resource checks cover exactly 4 MiB of one-byte and empty records, the next empty
  failure, invalid 256 before exhausted-capacity checking, exact 1 MiB concat and a
  too-large result while capacity remains. A later element/default recursively
  hitting the call guard proves eager evaluation precedes packing/index fallback.
  Generated mmap ENOMEM injection passes 2/2 with ptrace permitted.
- Complete local suite exits 0 with tracing permitted:
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Log /tmp/alchem-typed-bytes-complete.log. All retained tests pass: Python 5;
  Go tests/build; Rust 15 library+2 CLI/build; adapter tests/build; 195 shared cases/
  backend; 576 differential programs; 20 budget/pack programs; input suite;
  read/write EINTR and bootstrap mmap ENOMEM each 2/2; source 18 library, 73 mains,
  13 native errors, 5 rejections; lexer 1227; integers 135/496 cases; expressions 354;
  encoder 260; arithmetic compiler 327 valid/13 rejections; integer source compiler
  67 valid/21 rejections/3 runtime limits per backend. New byte suite above is
  included in verify-local.sh. Release build, Python syntax and diff checks pass.
  Tool versions remain Go 1.23.12/frontend Go 1.27.0/Rust 1.85.0/Python 3.12.14.
- Demo examples/alchem-byte-compiler-demo.alc (415 source bytes) compiles with
  empty PATH to a 1,192-byte ELF that exits 42. The target branches, returns bytes,
  packs a computed value and concatenates without changing the original input.
  readelf verifies headers/segment sizes. Compiler trace shows one execve, RW
  mmap, stdin reads and a 1,192-byte write, no host-tool children. Generated-target
  trace confirms one separate RW/non-executable arena mapping. Ignored artifacts:
  build/native/alchem-compiler 110,292 bytes, SHA-256
  `3b51885388eba44b8911564e94e8c4ce799fbcc311ea7c2eef1eae479997fd4e`;
  build/native/alchem-bytes-exit42 SHA-256
  `0c5ab4554b4e2b00fc07c6894f05f71207afb727a0d91ab80864d5f1bf53c5f5`.
  Prior integer demo now 579 bytes, same exit 42. Arithmetic compiler remains
  byte-identical at 33,685 bytes/hash 4dc04dc11128120050388486c7964e6f8daca8a75e4ac9d510db061ce055e4b7.
- Closure inventory updated from actual assembled source: 50,987 bytes,
  133 functions, 72 integer/61 byte returns, 206 integer/169 byte parameters.
  Its largest computed list is 128 elements; largest static list 43. Typed byte
  syntax/runtime is implemented, but current input 4096/functions 16/list 32/code 16 KiB
  limits, bounded recursive scans and repeated immutable output copying still
  prevent self-compilation. The bootstrap binary itself exceeds u16 ELF sizes.
  Next integrated acceptance is component-sized source beyond 4096 bytes/16
  functions with 128-element construction, scalable traversal/output storage and
  full-width metadata, then a reproduced generated-compiler IO entry. No self-
  rebuild/benchmark is claimed. Handoff/specs/readiness/quickstart updated.
  No remaining automated failures, production modifications or Actions dispatch.
  Publish to the existing branch/draft PR #7 with [skip ci], without merging.

## 2026-11-17 — Verified self-hosting and first native self-build baseline

- Completed the requested scaling work through actual native self-rebuilds.
  The Alchem-written compiler consumes its exact assembled source, emits A1,
  A1 emits A2, and A2 emits A3. All three images are byte-identical through both
  independent Go/Rust seeds and run correctness/rejection suites with empty PATH.
  This is self-hosting for the documented integer/byte profile, not full production
  Alchem compatibility. Production Alchem is unchanged; draft PR #7 stays unmerged.
- TDD: scaling acceptance first failed at the 4096-byte stdin limit. After larger
  traversal/output work, the computed 128/wide-ELF fixture still exhausted the
  compiler arena. Native bulk slicing removed the remaining recursive-copy
  overhead. Compiler-entry acceptance first failed because generated programs
  entered the smoke main rather than processing runtime bytes. Implemented the
  explicit native_compile(bytes)->bytes protocol and native IO entry in Alchem.
- Scaling changes are algorithmic as well as bounded resource configuration:
  batched declaration/body/list-span traversal; balanced name search and code
  construction; expression spans compiled once in evaluation order; function
  lengths retained alongside code rather than a second codegen pass; balanced
  pack validation/stores; native Enum.slice; validated inline byte-literal copies;
  compact small integer immediates. Constant literals still allocate fresh and
  retain exact charging; invalid values retain full-width runtime checks.
- Current bounds: source 65535 bytes, 192 functions, 128 list elements, 1024 body
  tokens, 16 live slots/expression nesting, 65535 bytes per function, 512 KiB total
  function code (each branch still 16 KiB). Bounded u32 sizes/addresses replace the
  former u16 executable-size restriction. Entry 1024 bytes, function table at
  file 1152, function code at 2688, entry address remains 0x400080. Larger-source,
  128-element computed-list and >64KiB executable fixtures pass through both
  backends, including deterministic bytes and executing the results.
- V11 adds required arena_bytes (aligned 8..64 MiB) and native bytes.slice. Negative
  count fails 73 before bounds; index normalizes once and count clamps safely to
  available length, preserving original buffers. Forty independent slice cases
  cover signed extremes, binary data and backend byte equality. Source Enum.slice
  lowers to V11 with default 4 MiB; compiler bootstrap overrides 16 MiB. Earlier IR
  profiles retain exact 4 MiB bytes/behavior. All 93 positive raw V1–V9 fixtures plus
  an explicit V10 input program match the pre-V11 backend byte-for-byte.
- Compiler entries map 16 MiB; ordinary generated programs retain 4 MiB, so existing
  resource/error tests remain meaningful. Native stdin reads <=65535 with lookahead,
  short-read accumulation and EINTR retry, calls public native_compile/1, rejects
  empty results with E_COMPILE/65, completes binary stdout writes and exits 0.
  Overflow/read/write diagnostics/statuses match the declared entry contract.
  Native entry read/write EINTR injection passes 4/4, including closed stdin and
  /dev/full checks. IO instructions/messages and every ELF byte are emitted in
  Alchem; no host wrapper patches generated artifacts or runs during rebuilds.
- Assembled distribution: 54,038 bytes, 135 functions, 50 integer/85 byte returns,
  193 integer/166 byte parameters across definitions. Assembly explicitly selects
  nine shared lexer primitives; the original full lexer component/oracles are
  unchanged. Thereafter native rebuilds consume the same single Alchem file,
  without Python source assembly or host parser/compiler invocation.
  Source SHA-256:
  `f848b2a599ad76efe8c382b66904f6418eaf255745ed44b2eca4e5ba4bcd9683`.
- A1/A2/A3 are 81,371 bytes, all SHA-256:
  `8bb870477b9cca4059d0e717717e09e6448782d9a155353a9bd2f9d226a5785c`.
  The same result is produced from both Go/Rust seeds. All three generated stages
  pass 67 integer programs/21 rejections/3 runtime limits and 49 byte programs/
  25 type/profile rejections/5 byte-or-slice failures/9 arena/evaluation-order
  programs. Every successful fixture also agrees with the pinned source/native
  oracle. Generated-program mmap failure injection passes 3/3 at these stages.
- Exact arena charges measured via the documented R12/R13 registers at syscall
  stops, with ptrace permitted: 6,299,072 bytes for A0->A1 and 9,066,304 for A1->A2
  and A2->A3, identical through both seeds; all within 16 MiB. An initial tracer
  option error reported zero and failed the check; corrected TRACESYSGOOD and
  reran, retaining all six successful measurements. No skip is counted as pass.
- scripts/build-self-hosted.py now bootstraps A0 and verifies A1/A2/A3 plus an
  executable byte smoke before publishing. build-native.sh publishes A3 as
  build/native/alchem-compiler, plus A0, compiler-source.alc and self-host.json.
  Individual files are atomic, not a group transaction. Failed-build preservation
  of all published files is tested. Generated source/binaries remain ignored;
  hashes/reproduction are recorded in docs rather than committing executables.
- Complete local command exits 0, with tracing permitted:
  `PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source`.
  Log /tmp/alchem-self-host-complete.log. Existing counts remain Python 5,
  Go tests/build, Rust 15 library+2 CLI/build, adapter tests/build, 195 shared cases
  per backend, 576 differential programs, 20 budget/pack programs, stdin checks;
  source 18 library/73 mains/13 errors/5 rejections; lexer 1227, integers 135/496 cases,
  expressions 354, encoder 260, arithmetic compiler 327 valid/13 rejections. Updated
  integer max-function and byte max-list rejection boundaries match the new
  profile. Native V11/scaling/entry/self-hosting gates above are included. Read/
  write EINTR and bootstrap mmap faults pass 2/2; entry EINTR 4/4; generated mmap
  faults 2/2 for seed paths and3/3 for generated stages. All six arena measurements
  are present. Rustfmt/clippy -D warnings, adapter go vet, Python syntax, diff checks
  and the release build script pass. Versions: native Go 1.23.12, frontend Go 1.27.0,
  Rust 1.85.0, Python 3.12.14.
- After correctness/rebuild gates passed, recorded the first actual self-build
  baseline in benchmarks/self-hosting-baseline-2026-11-17.json. Two warmups then
  ten warm-cache separate processes, every output compared to the input compiler:
  median 60.869736 ms, range 58.351328..85.184566 ms; OS wait4 peak RSS 13,440 KiB in
  this session. Wall time includes Python launch/wait, native startup, stdin file
  reads, compilation and stdout file write; comparison is outside timing. RSS is
  process high-water mark/launch history, not the traced arena charge. Linux
  x86-64/kernel 6.18.57/AMD EPYC 9V74 metadata and load/raw samples are recorded.
  This is one cloud-session baseline, no CPU isolation or Go/Rust performance
  comparison; independent repetitions are needed before optimization claims.
- Handoff, quickstart, source/IR/ABI contracts, profile inventory and benchmark
  readiness now reflect the verified self-hosted state. Next work is controlled
  repeat measurements and deliberate profile expansion while retaining native
  rebuild/correctness gates. Full production Alchem integration remains separate.
  No remaining automated failures, Actions dispatch or production modifications.
  Publish with [skip ci] to the same draft PR #7; do not merge without a new request.

## 2026-11-17 — self-hosted compiler components and first library batch

User scope is both compiler/runtime and standard library, compiler first. PR #7
was explicitly authorized and merged at fa605a68ca47734264e721ce025c2713ff53b9ad.
Continuation branch: feat/self-hosted-core-modules; publish a new draft PR.
Production Alchem and workflow configuration remain unchanged.

- Added fail-first acceptance for a native core-module builder and full existing
  lexer/integer/expression/encoder oracle programs compiled through A3. The first
  builder check failed because the builder did not exist. Implemented a manifest,
  Alchem byte-service adapters and signed decimal formatting, then made the
  standard build compile all five tools with A3. Arithmetic no longer takes the
  host frontend/backend route in the standard build. Go/Rust seed/reference
  checks remain. The compiler/runtime itself already participates in A1/A2/A3.
- Core builds schedule at most four independent native compilations, with empty
  child PATH. Every module compiles and passes a smoke before any publication.
  Outputs include native executables, exact source and compiler/source/artifact
  hashes. Each file is atomic; the whole set is not transactional. Checks cover
  executable modes, manifest hashes, repeated publication equality and preserving
  all existing files after a failed compile.
- Added Enum byte sum/reverse/take/drop: initial tests failed with source rejection
  on Enum.sum. Implemented typed dispatch and native instructions emitted by
  Alchem. Sum allocates nothing; other operations produce fresh aligned records.
  Signed counts clamp without negating minimum i64. Read-only pinned upstream
  compiler/library.go.txt confirms take/drop's negative-count behavior. The
  auditable assembly reference is not a build input; generated compilers never
  invoke an assembler. A test initially exceeded the documented expression-depth
  bound when checking 128 bytes; split assertions into bounded programs.
- A1=A2=A3 now contain 83,359 bytes, SHA-256
  45e9d42ac398e5d8bb1f054cbb3e675014c22f276b0641712f69ee8d5b41f053.
  Source is 55,818 bytes/140 functions, SHA-256
  dbc3376e9d72ff47a2411830b25aa281c5f2f3a6848bdbbca969b0c66482a066.
  Traced arena charges through both seeds: A0->A1 6,480,440 bytes;
  native A1->A2 and A2->A3 9,305,192 bytes, below 16 MiB.
- Existing self-hosted component oracles: lexer 1227 programs, integer 496 cases,
  expression 354 programs, encoder 260 programs. New native tool protocols:
  lexer 336 inputs, signed integers 100, expressions 177, arithmetic 177 and
  encoder 256 valid images, plus invalid inputs. All 256 generated exit images
  are executed. Every generated compiler stage checks 400 Enum cases, 8 type/
  arity rejections, immutability/live references and reverse arena exhaustion.
- Verification: the final complete suite exits 0, with no skips or failures. Full command uses the same toolchain
  environment recorded above, bash scripts/verify-local.sh --with-source, with
  tracing permitted. Final log /tmp/alchem-core-enum-complete.log. Initial core-only
  complete suite also passed (/tmp/alchem-core-complete.log). Release standard
  build passes (/tmp/alchem-enum-build.log). Python syntax, shell syntax and
  git diff --check pass. Versions remain Go 1.23.12/frontend 1.27.0,
  Rust 1.85.0 and Python 3.12.14.
- docs/core-modules.md and HANDOFF.md track exact artifacts and next work.
  All existing Alchem compiler components are on the native self-hosted build;
  full production library conversion is incomplete. The next substantial work
  is shared String/boolean/option support, followed by library API groups.
  General lists, callbacks, imports, actors and foreign runtime remain outside
  this bounded profile. The original timing baseline belongs to the previous
  source/compiler hashes; do not present it as a current optimization result.

Current-hash warm self-build sample (2 warmups, 10 byte-verified processes):
median 65.186 ms, range 60.498–94.655 ms, peak wait4 RSS 13440 KiB.
Raw samples: benchmarks/self-hosting-core-2026-11-17.json. Single cloud session,
no isolation or controlled speed comparison; arena charge is measured separately.

## 2026-11-17 — typed native strings, decimal strings and output

Continuation on feat/self-hosted-core-modules / draft PR #8, with no merge,
production edits or Actions dispatch. The user requested continued autonomous work.

- Added fail-first native string/output acceptance, initially rejected by the old
  compiler. Implemented distinct string type, literal scanning/decoding, typed
  arguments/returns/branches, concat (<>) and byte_size in Alchem. The new
  native-strings.alc is part of the actual self-built compiler source. Strings
  share immutable record storage with bytes but cannot be implicitly mixed.
  Function flags reserve private*16 so string-return metadata cannot collide with
  private integer functions; the public byte native_compile signature stays exact.
- A 128-byte literal exposed per-byte mutual recursion exceeding the compiler's
  depth bound. Replaced it with bounded chunks; the full boundary now compiles.
  Unknown/truncated escapes, raw controls, oversize/unterminated/interpolated
  literals are rejected. Unicode text is preserved as raw UTF-8 bytes; \xHH
  supports every byte, including NUL. Full Unicode escape syntax is deferred.
- Added main-body IO.puts(string), emitted by Alchem: complete payload plus LF,
  EINTR retries on payload/newline, short-write advancement, zero-progress/error
  exit74. Bound values survive syscalls. No void helper/device overload is claimed.
  Added native Integer.to_string(i64), including minimum i64, with fresh exact
  aligned arena charging and canonical ASCII. No host formatting/runtime call.
- Compatibility audit caught stale upstream registry prose: String.length is
  implemented as graphemeCount in compiler/codegen.go, not code-point count.
  Removed an experimental code-point implementation before publication and added
  explicit rejection coverage. Grapheme length remains unimplemented; do not
  relabel code-point or byte length as compatible String.length.
- Regression checks exposed an Integer namespace binding collision; confirmed it
  against the compiler, reserved the namespace, rebuilt and reran the checks.
  Output acceptance covers 412 programs, 28 rejections, all 256 hexadecimal byte
  escapes, 40 seeded text inputs, 103 full-width decimal values, mixed six-argument
  calls, live references, closed stdout and /dev/full. Five injected writes per
  generated stage cover payload/newline EINTR, zero progress and short progress.
  Five traced target programs per stage also verify exact string/decimal arena
  charges (8/16/32/40 bytes).
- Source: 63,989 bytes/158 functions (52 integer/106 byte returns; 223 integer/
  200 byte parameters), SHA-256
  cba221ab21ee77d8533b3973d0b613810a83a2d20aeff33f3972625609cff374.
  A1/A2/A3: 94,569 bytes, SHA-256
  db64336a62703ac3cb8a3dc27368af32bb9712905f0de39621e6749a3ef04225.
  Traced self-build arena charges through both seeds are 7,433,536 bytes for
  A0->A1 and 11,514,640 for each native rebuild, within 16 MiB.
  Standard release build passes. The new demo compiles and runs with empty PATH,
  printing Hello, Alchem! followed by LF.
- Final verification: complete suite exits 0, with no skips or failures. Command uses the previously recorded
  toolchain environment and bash scripts/verify-local.sh --with-source, with
  tracing permitted; log /tmp/alchem-strings-verified.log. An intermediate run
  overlapped source edits and failed its final artifact-equality check; discarded
  that run and restarted the complete suite on the frozen implementation.
  Python syntax, shell syntax and diff checks pass.
- Contracts: spec/alchem-string-profile.md and the puts/integer instruction
  references (references only, never build inputs). Coverage/handoff now track
  typed strings and integer output. Remaining foundations include stored booleans,
  option/result and grapheme APIs. Source has only 1,546 bytes of headroom under
  the current cursor bound; resolve source scaling before large library groups.

String checkpoint self-build baseline: 2 warmups, 10 byte-verified samples,
median 84.080 ms, range 81.672–117.077 ms; peak wait4 RSS 13440 KiB.
Raw record: benchmarks/self-hosting-strings-2026-11-17.json. Single cloud session,
launch/IO included, no CPU isolation or controlled comparison with older hashes.

## 2026-11-17 — source headroom, stored booleans and predicate APIs

Continued on feat/self-hosted-core-modules / draft PR #8 without production
changes, workflow changes or merge. The user requested continued work.

- Added fail-first compaction tests, then implemented a lexical formatting/comment
  compactor for initial source assembly. Quoted contents/escapes, token boundaries
  and statement newlines are preserved. A further CR-only comment regression
  failed, was fixed and now passes. Four unit checks cover these boundaries,
  idempotence and actual source size. The pre-boolean actual source shrank from
  63,989 to 55,008 bytes; compiling both with the saved compiler produced its
  exact existing ELF. Readable components remain intact. Python is only initial
  assembly orchestration; native self-rebuilds consume the compact source exactly.
- Added fail-first native stored-boolean acceptance. Implemented canonical true/
  false, typed parameters/returns/bindings/branches, recursive calls, not, signed
  comparison values and boolean equality/inequality in Alchem. Conditions require
  boolean and numeric/boolean types cannot mix. Logical and/or is still absent.
  Metadata kind3 uses public flag6/private22, preserving distinct string flags.
- Added terminal question marks in identifiers and native Enum.empty?(bytes).
  Then added fail-first String predicate checks and Alchem-emitted contains?,
  starts_with? and ends_with?. Their exact byte behavior follows the pinned
  strings.Contains/HasPrefix/HasSuffix paths; empty patterns match, oversized
  patterns do not. Both operands evaluate eagerly, including an unused pattern.
  Predicates allocate no records. Contains uses bounded naive search; no search
  speed claim. The assembly file is an audit reference, never a build input.
- New native boolean/predicate suite: 462 programs and 13 rejections, including
  signed extremes, 24 seeded numeric pairs, boolean/private/recursive/mixed-six-
  argument calls, predicate-named helpers, eager depth failure and 291 string
  matching programs over empty/repeated/UTF-8/binary/seeded data. Four traced
  programs per generated stage check zero allocation for booleans/comparisons,
  only the empty byte record for Enum.empty?, and only the two string operands
  for string predicates. Existing source/byte/string/Enum suites remain gates.
- Current readable assembly: 67,601 bytes; compact native input: 58,262 bytes,
  165 functions, 52 integer/113 byte returns, 232 integer/216 byte parameters.
  Actual input SHA-256:
  e2a283c4b04c3ca8028257a6044e1f9f30d7d799de712b4745acc1c4014bc1b7.
  A1/A2/A3 image: 100,073 bytes, SHA-256
  968fd10452b14c891357891a32df53b3463629850a7a494d9e9826683bdc1272.
  Traced charges through both seeds: A0->A1 7,896,640 bytes; native rebuilds
  12,983,056 bytes, within 16 MiB. Release build passes; 7,273 input bytes of
  headroom remain under unchanged limits. The predicate demo compiles/runs with
  empty PATH, printing Alchem Native plus LF and exiting 0.
- Final verification: complete suite exits 0, no skips or failures. Full command uses the previously
  recorded toolchain environment and bash scripts/verify-local.sh --with-source,
  tracing permitted; log /tmp/alchem-booleans-complete.log. Contracts, coverage,
  architecture and developer resume notes now reflect completed compaction and
  boolean support. Remaining work is option/result/tagged values, general
  collections, logical operators and further String APIs. String.length is still
  rejected until compatible grapheme behavior exists.

Boolean checkpoint self-build sample: 2 warmups, 10 byte-verified samples,
median 99.291 ms, range 95.678–140.871 ms; wait4 peak RSS 13440 KiB.
Raw record: benchmarks/self-hosting-booleans-2026-11-17.json. Launch/IO included;
one cloud session, no controlled comparison with earlier source hashes.
Python/shell syntax and diff checks pass; all generated-stage arena and fault
injections are present.

### Comparison-parser fast path

After the feature suite passed, isolated operator detection behind a first-byte
check. Non-comparison expressions now return without constructing six operator
literal records. Published the verified feature baseline as commit
43b62f599b0a4e81a31d4419c25539a83468eaa4, then reran the complete suite after this
optimization: exit0, no skips/failures, log /tmp/alchem-booleans-final.log. All
three generated stages retain 462 boolean/predicate programs, 13 rejections and
4/4 arena checks, plus existing integer/byte/Enum/string/component gates.

Final input is 58,542 compact bytes (67,879 readable), 166 functions,
53 integer/113 byte returns and 233 integer/217 byte parameters. Input SHA-256:
ffb753870d24f2b153c7f592a9d2c3b5b53846110cbce8ad324f203a87f77153.
A1=A2=A3 through both seeds: 100,376 bytes, SHA-256:
76a1011ec3cac1f2bbf18d00e48d54f48540c5eff7b2ddc4557582ee6402efb7.
Traced charges: A0->A1 7,913,776 bytes, native self-builds 12,628,824, within16MiB.
Input headroom is 6,993 bytes. Readable component files remain intact.

scripts/benchmark-compiler-pair.py records alternating AB/BA processes on the
same final source, byte-checking every output against the final compiler image.
Two warmup pairs then ten sample pairs: medians 101.975 ms before, 98.534 ms after.
Separate tracing after timing measures 13,019,736 bytes before vs12,628,824 after:
390,912 fewer charged bytes for identical input/output. Raw samples, hashes,
order, host/load and methodology: benchmarks/boolean-parser-fastpath-2026-11-17.json.
This is one shared cloud session with no CPU isolation; no stable speed claim or
Go/Rust comparison. The final compiler also reproduces the old baseline compiler
exactly when given its saved source. Release build, new demo, Python/shell syntax
and diff checks pass. No Actions dispatch, production changes or merge.

## 2026-11-17 — pinned graphemes, logical operators and typed option libraries

User focus: grapheme behavior, boolean/option types and broader library coverage.
Continued feat/self-hosted-core-modules / draft PR #8. No production/workflow
changes, Actions dispatch or merge.

- Audited the exact pinned compiler/library.go.txt grapheme code. Its Unicode17
  classes handle controls/CRLF, marks/prepend, Hangul, regional pairs and emoji
  ZWJ chains; Indic-conjunct rules are omitted and pictographic ranges approximate.
  Ported that behavior, without claiming full UAX#29 conformance. Added a613-range
  property snapshot with Unicode version/reference-section SHA-256. Five-byte
  records and algorithmic Hangul keep data compact; runtime binary-searches them.
  Checked Alchem literal functions emit the entire native runtime/table; no Go
  Unicode service or assembler participates in native compilation. Regeneration
  from the audit assembly/snapshot is deterministic and explicitly a dev step.
- Added String.length, grapheme String.slice and option-returning String.first/
  last. Count handles ASCII fast-path, malformed UTF-8 one byte at a time, long
  clusters and all range-boundary contexts. A Go oracle is extracted unchanged
  from the pinned section; its complete property snapshot must match Unicode17.
  A retained older compiler fails the new count fixture. Integration tests caught
  and fixed the first/last option payload-type tag. Full new checks per stage:
  1546 counts,480 slices and220 first/last results against reference boundaries.
- Added typed flat options over integer/bytes/string/boolean, some/none and
  exhaustive case expressions in either arm order. Some preserves full64-bit
  scalar/pointer payloads and charges16 bytes; none is null/no allocation. Branch
  unification, typed calls/returns/private recursion and extraction scopes are
  checked. Untyped none requires a payload context; nested/result types remain
  unsupported. Fail-first order/type cases and scope/rejection checks pass.
- Expanded Enum.at(bytes,index)/fetch to option results; retained eager default
  overloads. Added List.first/last option and eager-default overloads. New option
  suite:131 programs,9 rejections and11 exact target-arena measurements per stage,
  including zero/false/empty values, signed extrema and seeded payload/index cases.
- Added strict short-circuit and/or with normal precedence above/below comparisons
  as documented. Both operands are type checked, even when skipped at runtime.
  Fail-first truth/precedence/unused-infinite-recursion cases pass. Expanded
  boolean suite:478 programs/16 rejections plus4 arena measurements per stage.
- Identifier compaction extends the initial source assembly while preserving
  quoted text, namespace members, reserved words and public entry names. An
  actual pre-feature compiler source produced its exact existing ELF after
  alpha-renaming. A prototype alias collided with fn in the pinned frontend;
  fixed reserved-name generation and verified the bootstrap. Five compaction
  tests plus all real source builds pass. Native rebuilds consume identical
  compact input without another assembly/minification step.
- Raised the source function-table capacity to256 (code begins3200) while keeping
  active runtime frames256. Full-suite boundary testing caught linear address
  construction exhausting call depth at256 functions; replaced it with balanced
  address ranges/length sums. The256-function last-id255 program now runs42;
  257-function input is rejected. Did not mask this by raising call depth.
- The native library self-build really exhausted the old16MiB compiler budget
  (exit71). Compiler-entry/seed budgets are now32MiB, normal programs remain4MiB
  and old raw-IR contracts are unchanged. Tracing through both seeds measures
  A0->A1 10,870,144 bytes; native rebuilds18,449,112, proving why16MiB was inadequate.
  Pair-benchmark tracing now requires explicit before/after budgets, or records
  no arena measurement; it no longer assumes every compiler uses16MiB.
- Actual input63,580 bytes from95,621 readable bytes;219 functions,60 integer/
  159 byte returns and280 integer/288 byte parameters. Input SHA-256:
  ff5e225dda68c3845d79b5b9e75d3b326c74d3410ae0eb36a8d9a7d4c8984e63.
  A1=A2=A3 through both seeds:128,734 bytes, SHA-256:
  536bb6650cef321f73c8bce8c2c12f6e08eb736e9ec58ab77e27327248879fd9.
- Final complete command exits0, no skips/failures:
  PATH=/tmp/go/bin:/tmp/alchem-cargo/bin:$PATH GOCACHE=/tmp/alchem-go-cache GOPATH=/tmp/alchem-go127-path CARGO_HOME=/tmp/alchem-cargo RUSTUP_HOME=/tmp/alchem-rustup ALCHEM_FRONTEND_GO=/tmp/alchem-go127/bin/go bash scripts/verify-local.sh --with-source.
  Final log /tmp/alchem-graphemes-options-final.log. The earlier run's actual
  256-function failure is in /tmp/alchem-graphemes-options-complete.log, now fixed.
  Ten Python checks, Go/Rust/adapter suites, all old native/component/differential
  gates, new library/arena suites at every generated stage and all six measured
  self-builds pass. Release build, native combined demo, data regeneration,
  Python/shell syntax and diff checks pass. New demo prints combining-accent e
  and the complete joined astronaut emoji using empty PATH.
- Versions: native Go1.23.12, pinned frontend Go1.27.0, Rust1.85.0, Python3.12.14;
  optional regeneration used GNU binutils2.44. An initial oracle build used the
  read-only default cache; corrected GOCACHE to the recorded writable cache.
  Remaining work is results/tuples/nested types, general collections/IO and source
  scaling (only1,955 input bytes remain). Do not redo completed option/grapheme work.

Current-hash self-build timing:2 warmups and10 byte-verified processes, median
136.523 ms, range 122.175–164.883 ms; wait4 peak RSS 18176 KiB.
Raw record benchmarks/self-hosting-graphemes-options-2026-11-17.json includes
host/load and source/compiler hashes. One cloud session, launch/IO included, no
controlled speed comparison with older feature sets.

## 2026-11-17 — PR8 merge and source-capacity continuation

User explicitly requested merging PR8, then source capacity, structural types,
general collections and further library APIs. Marked the tested draft ready and
merged its exact head5a2bb98 at45f9a8a23a52622a237ca4a5fa9364cd153cea79. GitHub
confirmed merged and zero Actions runs. Continuation feat/native-type-collections
starts at that merge; new work will use a new draft PR. Production is untouched.

- Fail-first tests rejected source with real declarations past64KiB. Widened
  parser/value/argument/signature/environment/list/string cursor formats to u24
  and the native reader/source cap to1,048,575 bytes. Retained u16 executable
  lengths and bounded u32 addresses separately. Generic entry reads one extra byte
  for rejection; no partial ELF is emitted. Whitespace/comment skipping now covers
  the wider range. Local-slot and library-IO metadata inconsistencies exposed
  during initial rebuild were fixed before the final run.
- Real declarations, local bindings, calls and Unicode after64KiB work through
  256KiB and at the exact1MiB-minus-one limit. Over-limit and malformed late source
  reject with empty stdout. Native entry checks65,535/65,536/1,048,575 binary bytes,
  overflow, closed input, errors and EINTR. All self-built stages run capacity tests.
  The actual95,987-byte readable compiler source also reproduces A3 exactly.
- Complete verify-local --with-source exits0 with tracing, no failures/skips.
  Log /tmp/alchem-wide-complete.log. Existing Go/Rust/component/source/Unicode/
  option/boolean gates, native entry faults, rebuild equality, publication failure
  preservation and all six self-build arena measurements pass. Python and shell
  syntax/diff checks pass. Same recorded offline toolchain environment as above.
- Current input63,835 bytes/222 functions, source SHA-256:
  248e24108a4f5d20dfb9733909e7bf6cdcae615bf5a26d3b9091120bfcd2dbef.
  A1=A2=A3 image129,362 bytes, SHA-256:
  e5a7deb882470a8617acec63eaede174fce27b35b19b733c10e60b233fb202f8.
  Traced A0 charge13,013,856 bytes; native rebuild20,623,568, within32MiB. Normal
  programs remain4MiB. Input headroom is984,740 bytes, replacing the old1,955.
  Structural tuple/result/nested-type work follows on the continuation branch.

## 2026-11-17 — structural types on draft PR9

Capacity checkpoint1b68099 is pushed on feat/native-type-collections and draft
PR9 is open. PR8 remains merged; the continuation is not authorized for merge.
No Actions runs were triggered and production Alchem is untouched.

- Added failing native cases before implementation. Replaced byte type tags with
  collision-free60-bit structural words in parser values, return records,
  arguments and environments. Added recursive type unification for partial none/
  ok/error constructors, nested option annotations, immutable0..6-field tuples,
  checked static elem, result constructors and exhaustive scoped cases in either
  order. Unit tuples support result[tuple[],string]. User runtime remains native
  machine code and4MiB checked allocation, with no host fallback/new IR version.
- Expanded the function table to512 slots and used u16 environment function IDs;
  native active-frame limits remain256. The reference IR still caps256 functions,
  so its old oracle boundary remains and the new512/513 boundary is checked by
  deterministic native compilation, execution and rejection independently.
- Full bash scripts/verify-local.sh --with-source exits0 with tracing, no skips or
  remaining failures: /tmp/alchem-structural-verified.log. All existing Go/Rust,
  frontend, differential/component/library/Unicode/fault/publication gates pass.
  A1/A2/A3 each pass46 structural programs,17 rejections and tuple exhaustion,
  alongside the original119 arithmetic/transport checks. Expanded independent
  prefix-tree/merge/word tests subsequently pass263 cases at each identically
  rebuilt stage. Readable109,133-byte source also reproduces the same image.
- Initial full-run failures exposed the reference IR capacity mismatch and
  constructor interception of an ordinary variable named error. Both are fixed;
  name compatibility has its own regression test. Earlier logs are retained in
  /tmp/alchem-structural-complete*.log, not counted as passing final runs.
- Current compact source71,396 bytes/253 functions (80 integer/172 byte helper
  returns;346 integer/323 byte parameters). Source SHA-256:
  24b69948737359bfa70b4ff9f5a387dfaf07993575f5bf807b12d35cc2b56c35.
  A1=A2=A3 is149,234 bytes, SHA-256:
  19776c0477c0294769425473407f9aba66f0f5c26be2badaf74aa34a94f9d09f.
  Traced A0 build16,633,840 bytes; native rebuild26,498,336 within32MiB. Same
  recorded offline toolchains as the previous entry. New structural demo executes
  without PATH and prints accepted:42 / negative:7 with the documented spaces.
- Continue general collections, then further library APIs. The prepared general
  collection tests correctly fail on the legacy byte-only profile; that next
  milestone is not claimed complete by this checkpoint.

## 2026-11-17 — general collections and native library expansion

Continued all four requested areas on draft PR9 after merging PR8. Capacity and
structural types were already pushed; this batch adds general storage/iteration
and further APIs across Enum, String, Integer, IO and System. Production Alchem
and workflow settings remain untouched; publish with [skip ci] and do not merge
this continuation without a new request.

- Fail-first tests showed full-width integer lists exiting72 and string/nested
  lists/callbacks/maps rejecting. Introduced explicit bytes/b[...] and migrated
  compiler components/demos. The initial seed adapter translates that spelling
  to its existing byte IR while preserving strings/comments. Native source and
  rebuilds are unchanged inputs; old byte-test fixtures migrate explicitly, and
  new collection tests run directly without rewriting.
- Added immutable full64-bit integer/string/nested lists, typed &name captures
  and fn signatures, map/filter/reduce callbacks, option/default lookups and
  general count/concat/slice/reverse/take/drop/sum. Added typed integer/string/
  boolean-keyed maps, literals/new, content lookup, immutable put/delete,
  keys/values/entries/to_list and iteration over entries. An extra regression
  caught insertion-order output; fresh map results now sort keys to match the
  pinned scalar/byte-string order. Old maps remain unchanged.
- Ported Enum.join/filter, Integer.to_string bases2..36, signed digits and checked
  undigits, String.duplicate, main-body IO.write and System.pid/system_time/
  os_time/stop. Outputs match independent numeric/byte oracles; real clock/PID
  checks and interrupted/short/zero/full/closed write/clock-failure paths pass.
  Exact supported behavior and remaining API gaps are in the two new collection/
  library specifications and docs/HANDOFF.md.
- The larger seed exceeded256 functions. V11 now permits512; V1–V10 retain256
  and all prior valid encodings. Fail-first shared tests check both boundaries,
  real execution, Go/Rust equality and preserving existing output/mode on error.
  A subsequent native self-build hit the256-call guard; a traced stack identified
  parser dispatch overhead, which was shortened without raising the call limit.
  The expanded A2 build then exhausted32MiB. Compiler-entry/seed budgets are now
  explicitly64MiB; ordinary target arenas remain4MiB.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures/skips:
  /tmp/alchem-expanded-verified.log. Every A1/A2/A3 runs831 general collection
  programs/9 rejections plus callback exhaustion,262 map programs/12 rejections,
  186 expanded-library programs/6 rejections,4 syscall injections and26 exact
  allocation measurements. All old integer/byte/Enum/string/boolean/option/
  Unicode/structural/IR/backend/component/publication gates pass. The earlier
  /tmp/alchem-collections-library-final.log stopped on an obsolete rejection of
  the newly supported two-argument formatter; it now checks extra arity instead,
  and the complete final run passes. Earlier intermediate failures are not counted.
- Standard release `bash scripts/build-native.sh` exits0 and publishes A3 plus
  all five self-hosted core tools: /tmp/alchem-expanded-release.log. The135,792-byte
  readable source reproduces A3 exactly. Collection/library/grapheme regeneration
  is byte-identical. Python/shell syntax and diff checks pass. The new collection
  demo runs with empty PATH, including signed/string lists and sorted map output.
- Compact source89,611 bytes/305 functions, with83 integer/221 byte helper returns
  and383 integer/380 byte parameters; input headroom958,964 bytes. Source SHA-256:
  e321cc3dc4038f663542cc0fcd31a71d0aebab2fce64415052d5360489b35702.
  A1=A2=A3 is192,202 bytes, SHA-256:
  fafcbae3797508b4d05a39dbaad74a3c81db70c8a775ad9b7e33d3b0b39ec932.
  Both seeds produce these same bytes. All six traced builds pass: A0 charge
  21,719,016 bytes, native charge34,536,120 within64MiB. Same recorded offline
  toolchains as previous entries; optional regeneration uses binutils2.44.
- Current-hash warm self-build:2 warmups,10 output-verified processes; median
  220.16ms, observed213.57–259.70ms, wait4 peak RSS32,768–32,896KiB. Raw record:
  benchmarks/self-hosting-collections-library-2026-11-17.json. One shared cloud
  session with host/load metadata; launch/IO included. Different compiler/source
  hashes and uncontrolled conditions preclude a speed comparison with older
  milestones or Go/Rust. RSS is separate from traced arena charge.

No remaining failures in the verified suite. Remaining feature coverage includes
exact Integer.parse errors/base parsing, IO.gets/general void helpers, further
Unicode/String and environment APIs, closures/imports and optimized map storage.
The handoff gives exact resume priorities and file/contract locations.

## 2026-11-17 — mise toolchain pins and arm64-host container

- Added mise.toml (Go 1.27.4, Rust 1.100.0, Python 3.15.2) with fetch/verify/build
  tasks, docker/Dockerfile and scripts/linux-container.sh for a linux/amd64 image
  built from the same pins. One Go replaces the separate 1.23.12/1.27.0 pair.
- Host: macOS arm64, OrbStack (Rosetta x86-64 emulation). No real x86-64 run yet
  with these versions.
- mise run linux:build passes: A1/A2/A3 match, compiler 192,202 bytes, image SHA
  fafcbae3797508b4d05a39dbaad74a3c81db70c8a775ad9b7e33d3b0b39ec932 and source SHA
  e321cc3dc4038f663542cc0fcd31a71d0aebab2fce64415052d5360489b35702, both unchanged
  from the previous toolchains. Collections demo runs; empty-PATH rebuild is
  byte-identical.
- mise run linux:verify does NOT pass under emulation. Failures, all traced to
  emulation rather than the toolchain change:
  - Rust tests/cli.rs source_mode_requires_an_existing_frontend_and_preserves_output:
    posix_spawn of a missing binary reports success (child exits 127), so the
    driver prints E_SOURCE instead of E_IO.
  - harness/arena_limits.py mmap ENOMEM injection: strace injection has no effect.
  - harness/self_host.py arena measurement: ptrace GETREGS returns EIO.
- With that Rust test skipped and strace removed (injection gates report 0/N), the
  Go acceptance (195/195), Go/Rust comparison, frontend probes and every source
  gate up to compiler_entry pass; the run then stops at the self_host.py ptrace
  measurement. Later gates (core_modules, core_tools) were not reached.

## 2026-11-17 — real x86-64 run with mise pins; fast iteration check

- Host: Linux 6.8.0 x86-64 (real hardware, 16 CPUs), mise pins Go 1.27.4,
  Rust 1.100.0, Python 3.15.2.
- Complete `bash scripts/verify-local.sh --with-source` exits0 with no failures
  or skips in about339s. The Rust CLI test, mmap ENOMEM strace injection (2/2
  backends) and self_host.py ptrace arena measurements that failed under Rosetta
  all pass here, confirming those were emulation artifacts. Slowest steps:
  core_modules.py ~103s, self_host.py ~88s, lexer.py ~80s, expressions.py ~23s;
  every step before the source gates finishes in ~20s.
- Added scripts/verify-quick.py (`mise run verify:quick`, `linux:quick`): builds
  A0 with the Rust seed, requires A1==A2 and runs the 14 self-hosted stage gates
  once against A2, in parallel, with optional name filters. All 14 pass in 8.2s
  (type_words ~7s bounds it); a single gate takes ~2s. It reports SKIP output as
  failure. It is an iteration aid and does not replace the full run above.

## 2026-11-17 — Integer.parse with exact pinned error text

- Added Integer.parse(string) and parse(string,base) returning
  result[integer,string]. Parsing follows Go strconv.ParseInt; errors are
  strconv.Quote(input) + " is not an integer" (+ " in base N" for the base form),
  matching the pinned runtime byte for byte. An explicit base outside 2..36,
  including 0, exits73 like the other base APIs.
- spec/print-ranges.json (740 printable ranges, generated from Go 1.27.4
  strconv.IsPrint, Unicode 17.0.0) drives quoting. The runtime
  (spec/integer-parse-x86_64.s, 5,004 bytes) is emitted once per program in the
  function-table slot after the user functions, not inline: 15 inlined call
  sites already exceeded the 65,535-byte function limit. Programs calling it may
  define at most 511 functions; a 512-function program that only mentions it
  still compiles.
- harness/integer_parse.py: 796 results/error texts (signs, bases, i64 and u64
  boundaries, all 256 single bytes, invalid/overlong/surrogate UTF-8, printable
  range edges, random runes) against Python ParseInt/Quote oracles, plus invalid
  bases, arena fit/exhaustion, the 511/512-function boundary and 7 rejections.
  The oracle output equals the pinned upstream compiler's (`alchem run`, built
  offline from the module cache) on all 796 cases. A mutated oracle fails.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips, 5m42s on the real x86-64 host; Integer.parse passes at A1/A2/A3.
  Source 106,034 bytes/331 functions, SHA-256
  d56f9aad2fdcb4b87993ac5763ded0770cc89e5cab2db3aaa5053d66884b3939.
  A1=A2=A3 203,816 bytes, SHA-256
  12bad57fc8a81de178734392c5523b60a15922bf340d0b2556dc510816ef218d.
  Traced self-build charges: A0 24,230,520 bytes, native 37,840,104 within 64MiB.

## 2026-11-17 — IO.read_line and IO.read_all

- Added IO.read_line(): option[string] and IO.read_all(): string as expressions.
  Lines drop "\n" then one "\r"; end of input gives none; a final unterminated line
  is returned. Text must be valid UTF-8 and lines at most 1,048,576 bytes (exit73);
  read failures exit74 with EINTR retried; read_all beyond the 4MiB arena exits71
  (the pinned runtime allows 16MiB). read_line reads one byte per syscall, so it
  never consumes input after its newline.
- Routines are new Intel-syntax sections in spec/library-x86_64.s with a Go
  utf8.Valid-equivalent macro; regenerating the library data leaves every
  existing routine byte-identical.
- Native output equals the pinned upstream build of the same program on nine
  inputs covering CRLF, lone CR, empty/unterminated lines, read_all after
  read_line and invalid UTF-8 (upstream exits2 with a diagnostic; native exits73).
- harness/io_input.py: 189 input/read-sequence runs against a Go ReadSlice/
  TrimSuffix/utf8.Valid oracle, 1MiB line boundary, no over-read (a following
  `cat` receives the rest), delayed chunked pipe, arena exhaustion, closed stdin,
  read EINTR/EIO injection (3/3) and 6 rejections. A mutated oracle fails.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (5m56.359s). Source 109,092 bytes/334 functions, SHA-256
  371ac1ae0689e84dbda01a02b0866419f4c42b85fd0a9476ac0db24eed2d9873.
  A1=A2=A3 206,875 bytes, SHA-256
  e4dda6790957bcf537874a596edd686c365fea42ac70bb32619704079d7e5539.
  Traced self-build charges: A0 24,710,816 bytes, native 38,585,384 within 64MiB.

## 2026-11-17 — System.argv and System.get_env

- Native entry stubs (main and compiler entry) now begin with mov r14,rsp, keeping
  the initial argc/argv/envp block, which stays intact above all frames. No other
  generated code or runtime routine uses R14 (the grapheme routine saves it).
- System.argv(): list[string] gives os.Args[1:] with each run of invalid UTF-8
  replaced by one U+FFFD (strings.ToValidUTF8), copied per call.
  System.get_env(name): option[string] and get_env(name,default): string take the
  first envp entry whose text before its first "=" equals the name; empty names,
  and names containing "=" or NUL, never match. Values are returned byte for byte.
- The UTF-8 check in spec/library-x86_64.s is now a reusable utf8_width macro;
  read_line/read_all still pass their full gate.
- Native output equals the pinned upstream build for four raw execve cases
  (duplicate keys, "A=B" lookups, entries without "=", invalid-UTF-8 runs, argc0).
- harness/system_env.py: 44 raw argv/envp runs against Go-semantics oracles,
  repeated-copy arena exhaustion (exit71) and 7 rejections. A mutated oracle that
  stops collapsing invalid runs fails.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (5m56s). Source 112,133 bytes/339 functions, SHA-256
  08219ff3882363312ac9f1700ecb3b6d30287567b4db3887cf4b795f3c091a91.
  A1=A2=A3 210,456 bytes, SHA-256
  519cc5c6ff26ef637d938326c591d5aad058deab839487cd4ccd1c3335a5b0f7.
  Traced self-build charges: A0 25,188,704 bytes, native 39,281,272 within 64MiB.

## 2026-11-17 — IO statements in helpers and branches

- The pinned language has no void helpers: `alchem run` rejects unannotated,
  `: void`, used and recursive forms alike ("returns void, which is not a valid
  type"). The gap was output inside helpers: IO.puts/IO.write were accepted only
  in main. They are now statements in any function body and at the start of any
  if/else branch, before the value. Untaken branches do not run them.
- harness/effect_helpers.py: 8 programs (helper output, recursion, argument
  evaluation order, nested branches, bindings after output, 200 recursive lines,
  empty output, string results) whose stdout and exit status equal the pinned
  upstream `alchem run` on every case; closed stdout exits74; 5 rejections.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (6m02s). Source 112,750 bytes/341 functions, SHA-256
  528a214625306ca667fee994bcb3c69d2e115eabdb4fc14ada91435dddd2759e.
  A1=A2=A3 212,243 bytes, SHA-256
  ff16cc78df9a435c624ce84987840dcf91bfc0e90fe10608ee7594eb9764bb01.
  Traced self-build charges: A0 25,408,904 bytes, native 39,686,160 within 64MiB.

## 2026-11-17 — File.read with exact pinned error reasons

- Added File.read(path): result[string,string]. It opens O_RDONLY|O_CLOEXEC,
  retries EINTR, reads to end of file, always closes, and requires valid UTF-8.
  Errors are the pinned runtime's os.PathError text ("open PATH: ...",
  "read PATH: is a directory", "invalid argument" for an embedded NUL) using Go
  1.27.4's errno texts (spec/errno-messages.json, generated by
  scripts/generate-errno-messages.go), or "file is not valid UTF-8".
- The runtime (spec/file-read-x86_64.s, 3,989 bytes) is the second shared
  runtime after the user functions: slot functions+1, with an empty
  Integer.parse slot when only File.read is used. Detection is a generalized
  source scan (na_mentions); programs calling File.read may define 510 functions.
  The shared literal emitter moved into scripts/generate-parse-runtime.py and
  still reproduces native-parse-data.alc exactly.
- harness/file_read.py: 22 paths against an os.Open/ReadAll/utf8.Valid oracle
  whose output equals the pinned upstream `alchem run` on all 22, arena
  exhaustion, 200 reads under a 16-descriptor limit, open/read EINTR and read
  EIO injection (3/3) and 6 rejections.
- Observed existing limit, unchanged here: `"ok:" <> s` for a 1.3MB string exits71.
  (Corrected later the same day: this is the documented 1MiB concatenation
  payload cap shared with byte concatenation, not extra arena cost.)
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (5m56s). Source 128,630 bytes/362 functions, SHA-256
  59b47b54cdf17540fef892266a5c9593b087ea4a9ff8f703dcb8dfe60349731e.
  A1=A2=A3 222,258 bytes, SHA-256
  11d197e3dd3b149fc12db4940c51fc15f4b6e33fef50c05a25b995a6240144e6.
  Traced self-build charges: A0 27,361,544 bytes, native 42,427,520 within 64MiB.

## 2026-11-17 — string equality, split, replace, count, valid?, trim

- `==`/`!=` now compare strings byte for byte; ordering on strings is still
  rejected. Added String.split(s,sep), String.replace(s,old,new),
  String.count(s,pattern), String.valid?(s), String.trim(s) and the bare
  String.contains/starts_with/ends_with names. All follow the Go functions the
  pinned runtime calls (strings.Split/ReplaceAll/Count/TrimSpace,
  utf8.ValidString); an empty split separator exits73.
- Routines are new sections in spec/library-x86_64.s. A function body holds at
  most 1024 tokens, so the 528-byte replace literal was rejected by the
  self-built compiler; scripts/generate-library-runtime.py now emits routines
  over 448 bytes as part functions. Routine bytes are unchanged.
- harness/string_ops.py: 180 cases (160 seeded random over spaces, separators,
  multibyte and invalid UTF-8, plus 20 edges) against Python oracles, including a
  DecodeLastRune reimplementation for trailing trim. The oracle equals the pinned
  upstream `alchem run` output on all 180; a mutated space set fails. Also the
  empty-separator and arena-exhaustion exits and 11 rejections.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (5m58s). Source 135,361 bytes/377 functions, SHA-256
  eb615da63fa5e0383cd8822431a42bbbb08c15e1b06fa7bdaaa0ec8b86ef6c05.
  A1=A2=A3 229,651 bytes, SHA-256
  dc6bdc96e89db215c67ca8324325ed88c4fb14dce3b996ef88dc0ef4f168a15a.
  Traced self-build charges: A0 28,391,040 bytes, native 43,826,592 within 64MiB.

## 2026-11-17 — string concatenation no longer capped at 1MiB

- String `<>` shared byte concatenation's 1MiB payload cap (exit71), which the
  pinned runtime does not have. Strings now use ns_concat_emit: the same size,
  arena check and copy code without the cap, so results are bounded by the 4MiB
  arena. Byte Enum.concat keeps its cap and its emitted code is unchanged.
- harness/string_ops.py adds a 1.4MB concatenation that succeeds and a further
  2.8MB one that exits71 from the arena check.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (5m59s). Source 135,471 bytes/380 functions, SHA-256
  5e894ad4347990e32f4aef55cb117bd41e5143bc01de0f5aced5312347f1e4a6.
  A1=A2=A3 230,064 bytes, SHA-256
  591b94345eaad5f3984fb234b79256a4f11c68b254f6f0846c45f9359bff8b66.
  Traced self-build charges: A0 28,494,936 bytes, native 43,944,896 within 64MiB.

## 2026-11-17 — String.upcase, downcase and to_integer

- String.upcase/downcase follow Go strings.ToUpper/ToLower: simple per-rune
  mappings from spec/case-ranges.json (203 upper and 185 lower stride ranges
  generated by scripts/generate-case-ranges.go from Go 1.27.4, Unicode 17.0.0),
  and each invalid byte becomes U+FFFD. The runtime (spec/case-map-x86_64.s,
  3,246 bytes) is the third shared runtime, slot functions+2; such programs may
  define 509 functions.
- String.to_integer(s[,base]) reuses the Integer.parse runtime in a failing
  mode: a non-integer or a base outside 2..36 exits73 where the pinned runtime
  fails the process. Mentioning it also includes the parse runtime.
- harness/string_case.py: 150 strings covering every mapped rune plus the
  neighbours and stride gaps of every range, 105 integers, 27 failing
  conversions, the 509/510 and 511 function boundaries and 9 rejections. The
  oracle equals the pinned upstream `alchem run` on all 255 successful calls; a
  one-rune oracle mutation fails.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (6m05s). Source 147,250 bytes/396 functions, SHA-256
  9f9cf2bd5eae70b51d1eae352f1d447fa2914df3a364dfb5e3122cd760af5afb.
  A1=A2=A3 238,999 bytes, SHA-256
  282b06839282076641473e7a94e7ae4c1176c971949a71b6a638418646301623.
  Traced self-build charges: A0 30,132,056 bytes, native 46,170,056 within 64MiB.

## 2026-11-17 — realistic compiler capacity limits

- Reason: the compiler source had reached 396 of 512 functions and a native
  self-build charged 46.2MB of the 64MiB compiler arena.
- Functions: 512 -> 4096 (native and seed IR V11; V1-V10 keep 256). The native
  function table is no longer a fixed 512 slots: it holds one entry per used
  slot and code follows it, so a minimal program shrank from about 5.3KB to
  1,205 bytes. Call sites address slots with a 16-bit file offset (8047 max).
- Compiler arena: 64MiB -> 1GiB, reserved lazily with MAP_NORESERVE in native
  compiler entries; seed arena_bytes may be up to 1GiB and the bootstrap uses it.
  A native self-build charges about 313 bytes per source byte, so 1GiB covers
  the 1MiB source limit about three times.
- Total code: 512KiB -> 960KiB, the most that fits because the image is one byte
  payload and byte concatenation caps payloads at 1MiB.
- Two recursions scaled with function count and hit the 256-frame guard near
  2000 functions: table batches (8 -> 64 per batch) and record counting by
  subtraction (now steps of 4096/256/16/1).
- Measured at the limit: a 4096-function program compiles in 1.7s, 271KB image,
  about 246MB peak, because the function table is copied per declaration.
- Boundary tests moved to 4096/4097 (alchem_compiler.py, function_capacity.py),
  4095/4096 for Integer.parse, 4093/4094 for the case runtime, and 1GiB/1GiB+8
  for arena_bytes.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (6m47s). Source 147,381 bytes/397 functions, SHA-256
  894f0b1382cb313f3fb532cc93a664f270f62fe423abb6d8d58d04c14d64c3e4.
  A1=A2=A3 238,265 bytes, SHA-256
  1b7a3539ebc0dd40ec88ffcd69160b5c0382a08ed05e20848f6254cb845773bc.
  Traced self-build charges: A0 29,747,248 bytes, native 45,800,248 within 1GiB.

## 2026-11-17 — string ordering, one-sided trims, File.write, case-arm output

- `<`, `<=`, `>`, `>=` on strings order by unsigned bytes with a proper prefix
  first (Go string comparison). String.trim_leading/trim_trailing reuse the
  trim routine split into leading/trailing/finish macros; String.trim's bytes
  are unchanged.
- File.write(path,content): result[tuple[],string] follows os.WriteFile with
  mode 0644: create or truncate, write all bytes with EINTR retry, close, and
  report "open/write/close PATH: reason". Reads and writes share the file
  runtime (4,268 bytes) and its table slot.
- IO.puts/IO.write at the start of case arms already compiled, because arms use
  the branch parser extended earlier; they are now tested.
- Gates: string_ops.py has 290 cases (ordering and one-sided trims added);
  file_read.py checks 7 writes on disk, 9 failing writes, write EINTR/EIO and
  close EIO injection (6/6 with the read injections) and 200 writes under a
  16-descriptor limit; effect_helpers.py has two case-arm programs. Oracles
  equal the pinned upstream `alchem run` on all 290 string cases, 10 effect
  programs and 10 write results.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (6m54s). Source 151,213 bytes/401 functions, SHA-256
  6e2986f1d28d9271070e86b07d3811d83115872dd01ca4ff2de7f7c622c7f1dc.
  A1=A2=A3 242,007 bytes, SHA-256
  68ca1247338c3f7c33d2656a7d1be1e76a0c85e1da21fc9c7b22d645b4050b81.
  Traced self-build charges: A0 30,314,320 bytes, native 46,565,232 within 1GiB.

## 2026-11-17 — PR #10 merged; grapheme strings, File.append/remove

- PR #10 (dev environment, quick verification, library expansion, capacity
  limits) merged to main as f5e94e1 on request; no Actions runs. Work continues
  on feat/grapheme-strings-closures.
- String.reverse (grapheme clusters), String.capitalize (ToTitle of the first
  grapheme, ToLower of the rest; a title table joins spec/case-ranges.json) and
  String.pad_leading/pad_trailing (graphemes measured, runes filled, invalid
  fill bytes as U+FFFD). The grapheme runtime gained reverse and
  first-cluster-length operations.
- The grapheme runtime is now the fourth shared runtime (slot functions+3). It
  was inlined at about 4.5KB per call, so 14 grapheme calls in one function
  exceeded the 65,535-byte function limit; this also applied to the existing
  String.length/slice/first/last.
- File.append(path,content) and File.remove(path) join the file runtime
  (os.OpenFile with O_APPEND; os.Remove's unlink-then-rmdir error choice).
- Gates: string_graphemes.py, 255 cases against the pinned grapheme oracle and
  Go case/rune rules (equal to the pinned upstream output on all 255);
  file_read.py adds 11 append/remove steps checked on disk and against os
  errors. Native output equals upstream on the combined smoke program.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (7m18s). Source 160,711 bytes/420 functions, SHA-256
  ef1f4699215262c6e1ff5738cccf48ef9eba78ea920fb055b290a5f7fa2976d8.
  A1=A2=A3 252,707 bytes, SHA-256
  f701c1d8a3b901a025a9c1fb040dc2b4b64cf09bb2975c564ec1f416ba0c20a7.
  Traced self-build charges: A0 31,898,200 bytes, native 48,804,848 within 1GiB.

## 2026-11-17 — modules and imports

- The compiler now accepts a bundle of several modules and resolves
  `Module.function` calls. Table records grew from 25 to 27 bytes (a u16 owning
  module index) and each module has a header record that takes a table slot but
  emits no code. Rules follow the pinned language, confirmed by experiment:
  calls into another module must be qualified and directly imported (not
  transitive), `defp` stays private, a module may qualify itself, imported
  modules cannot define main, and 49 library namespaces are reserved names.
- The compiler opens no files, so scripts/bundle-alchem.py follows
  `import "path.alc"` lines from an entry file and rewrites each module's
  imports to `import "module:Name"` after its header. It reports missing files,
  cycles, duplicate module names and imported mains. See spec/alchem-modules.md.
- Limits split: 4096 user functions across all modules and 8000 table records.
  Shared runtimes use slots beyond the records, so the earlier 4095/4094/4093/
  4092 reductions are gone. Table building is now sixteen steps per level over
  four levels.
- Added scripts/check-compiler-functions.py, which compiles each compiler
  function alone against stubs to find the one a profile limit rejects, and
  reports duplicate definitions.
- harness/modules.py: 5 bundled projects, 6 visibility rejections, 4 bundler
  errors, 13 invalid bundles, a 200-module call chain, 300 modules, and 4096/4097
  functions across 64 modules. All 11 import experiments and the gate's projects
  agree with the pinned upstream `alchem run` on the unbundled files.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (6m59s). Source 165,086 bytes/434 functions, SHA-256
  9ab761c1e00b8c5bb3fb06875bd2e39e9b408842e1665c8ab7117d6d28ce6451.
  A1=A2=A3 263,543 bytes, SHA-256
  5111861b68f0247babcd75095ce0e9cddf85db30b24969bd48bd7eeef1fc9538.
  Traced self-build charges: A0 33,546,072 bytes, native 51,367,688 within 1GiB.

## 2026-11-17 — closures and calls through function values

- Anonymous functions: `fn(x: integer): integer do ... end` and
  `fn x -> ... end`, with captured enclosing bindings, nested lambdas, bindings
  and output statements in bodies, and calls through values as `f(1)` or
  `f.(1)`. Unannotated lambdas take parameter types from an Enum.map/filter/
  reduce list, a callee's `fn[...]` parameter, a function value's type or the
  enclosing function's declared `fn[...]` result.
- A function value is now a pointer to a record (code address, then captures)
  passed in R10. A function-table slot is such a record, so `&name` allocates
  nothing; the three runtime callback sites call through the record. Lambda code
  is emitted inside its enclosing function behind a jump. See
  spec/alchem-closures.md, implementations/alchem/native-functions.alc.
- The body scanner counts an unannotated `fn` as a block opener (not `fn(` or
  the type `fn[`), since its `end` has no `do`.
- Found by comparing with upstream: a lambda parameter shadowing an enclosing
  binding is an error there, so it is rejected natively; and a lambda body that
  failed to compile made the compiler exit72 (a negative type word in a byte
  literal) instead of rejecting with65. Both fixed and tested.
- Native limits beyond upstream: an unannotated lambda must be the last
  argument, a call result cannot be called directly, six parameters, and every
  enclosing binding is captured within the 16 live slots. `&(&1 + &2)`-style
  short forms and `&Module.function` are not implemented.
- harness/closures.py: 10 programs, arena and frame limits, 13 rejections. All
  10 programs' output equals the pinned upstream `alchem run`.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (7m10s). Source 170,615 bytes/454 functions, SHA-256
  51296e00cdcd5cbe52e76f6c3d18f944d01cad628b39f6abbcc76e670aa8b46a.
  A1=A2=A3 277,720 bytes, SHA-256
  2f89b171d59a82e7b630f285d02ce71f41dbfc0748cf2349e47c18760c51063d.
  Traced self-build charges: A0 35,319,656 bytes, native 55,940,320 within 1GiB.

## 2026-11-17 — captures, references, lambdas in any argument, annotated bindings

- Captures `&(&1 + &2)`, `&String.length(&1)`, `&Module.function(&1)`,
  `&helper(&1) + 1` and `&value.(&1)`; references `&name/arity`, `&Module.name`
  and `&Module.name/arity` under the import visibility rules.
- An unannotated lambda or capture may now be any argument, and several may
  appear in one call. An argument list records each as deferred (source position
  and offset in the argument code); once the callee's parameter types are known
  they are compiled last first and spliced in, so evaluation stays left to
  right. Callees that give no types reject deferred arguments centrally
  (nc_arguments).
- A function-valued call result is called at once: `adder(10)(5)`,
  `adder(10).(5)`, `mk()(6)(7)`, when the parenthesis is on the same line.
- Annotated bindings `name: type = value`, which were not accepted at all
  before; a `fn[...]` annotation types a lambda or capture.
- Matches upstream on rejections: nested captures (also through a nested fn),
  `&N` inside a nested fn or outside a capture, a capture with no placeholder
  or with a parameter count other than the expected one, wrong reference arity.
- Native limit kept: `&String.length/1` (a library reference by arity) is not
  accepted; `&String.length(&1)` is. Noted while drafting a bundler in Alchem:
  a function type whose parameter and result types exceed the 60-bit type word
  is rejected, so Enum.reduce accumulators are limited to about 24 bits of type.
- 79 programs compared with the pinned upstream `alchem run`; all outcomes
  equal except that library reference. Two mutations (dropping the placeholder
  count check, dropping the deferred-offset shift) each fail harness/closures.py.
- harness/closures.py: 16 programs, 33 rejections; harness/modules.py: 6
  projects, 9 visibility rejections.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (7m05s). Source 175,853 bytes/474 functions, SHA-256
  7386ffd32af91c99a372d91e6034d08fbca0a1ee2e8a3b8c9b19d4700b3ad67c.
  A1=A2=A3 290,547 bytes, SHA-256
  20e3b376a17f66c02a880dcd614a7549c173b69e7eaf528aa35e4d64ae5da57e.
  Traced self-build charges: A0 36,979,752 bytes, native 58,995,992 within 1GiB.

## 2026-11-17 — IO.warn; the import bundler written in Alchem

- `IO.warn(string)` is an output statement wherever IO.puts is: the text and a
  newline on standard error. A failed write there is ignored, as the pinned
  runtime does (closed and full stderr both leave the exit status alone), while
  standard output still exits74.
- tools/alchem-bundle.alc is the import bundler as an Alchem program: the first
  multi-function tool outside the compiler that the self-hosted compiler
  builds (43,677 bytes). scripts/build-native.sh publishes it as alchem-bundle,
  so `alchem-bundle app.alc | alchem-compiler > app` has no Python in it. It
  uses File.read, System.argv, maps, results, closures, captures, references by
  arity and annotated bindings, and also passes the pinned upstream
  `alchem check`; built by upstream it writes the same bundles.
- harness/modules.py builds it with the compiler under test at each stage and
  compares 61 bundles byte for byte with scripts/bundle-alchem.py (15 projects
  under four path spellings, and a CRLF file with a module name containing
  "do", a one-line module and a commented defmodule), its four errors on
  standard error with status1, usage with status2, and runs every project
  through it.
- Its paths are compared after lexical cleaning; symbolic links are not
  resolved, unlike the Python reference.
- Limit met while writing it: a function type whose parameter and result types
  exceed the 60-bit type word is rejected, so its state is one
  map[string,string]. Wider types are the next planned change after
  &Library.function/arity.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (7m02s). Source 176,121 bytes/477 functions, SHA-256
  5983995cf8d97fcd1f011f319cf186815fd43812f6081f3afb082aa39c78feb1.
  A1=A2=A3 294,146 bytes, SHA-256
  b4838237b1b850c5080a882336276b5c6a5dc945b73661f7e452968c2298e19f.
  Traced self-build charges: A0 37,255,136 bytes, native 59,310,272 within 1GiB.

## 2026-11-17 — library functions by arity

- `&String.length/1`, `&Integer.to_string/1`, `&Enum.sum/1`, `&byte_size/1`,
  `&System.pid/0`: a name with an arity that is no function or module of the
  program is the capture `&name(&1, ..., &N)`. The compiler builds that text
  from the name in the source and compiles it as a capture with no enclosing
  bindings, so every library call form is covered without a second code path.
- As upstream: it needs a typed context whose parameter count is the arity, is
  rejected inside another capture, and an unknown name or a missing arity is
  rejected. 20 programs compared with the pinned upstream `alchem run`, all
  equal. This removes the last known difference in function-value forms.
- harness/closures.py: 17 programs, 38 rejections.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (7m08s). Source 177,379 bytes/480 functions, SHA-256
  7aa6cbe18679765c3d6e90796e4f4ec24c269c344c94730e6338d28e5ecc78a9.
  A1=A2=A3 297,865 bytes, SHA-256
  acba10a0b9054aa925d3f6346eabdf5e1ada07718ae94ef274d939610bbddf66.
  Traced self-build charges: A0 37,723,200 bytes, native 60,230,896 within 1GiB.

## 2026-11-17 — wider structural types

- A type was one 60-bit integer of four-bit tags. It is now a byte string in
  the same prefix form (one byte per tag, a count byte for tuples and
  functions) of up to 47 bytes; an empty byte string is no type and marks every
  failure. Environment records, argument packets and type lists hold types in
  48-byte cells; value packets hold a length byte and the type; the function
  table holds the position of each result annotation, so its records stay 27
  bytes and table construction costs no more than before.
- What it buys: fn[string, T, T] has room for a T of 22 bytes where it had about
  24 bits. Enum.reduce over tuple[list[string], map[string, integer], integer],
  and over result[tuple[tuple[list[string], map[string, string]], string],
  string] (the state the Alchem bundler had to avoid), now compile, with named
  callbacks, lambdas and function values. Six such programs equal the pinned
  upstream `alchem run`, including a mismatch rejection.
- Done in two steps, each required to compile 6,358 programs from 18 gates to
  executables byte-identical to the compiler before the change (a wrapper that
  runs both compilers, used as the gates' compiler): first the field widths
  with types still integers, then the representation. Both had no differences.
  The seed frontend's type checker located every site of the second step on
  the readable source.
- harness/type_words.py is rewritten for the encoding: 393 cases against an
  independent tree oracle (boundaries, children, cells, the 47-byte limit,
  merging). It found that a truncated tuple or function type was not reported
  as malformed; fixed. harness/structural_types.py adds seven programs with
  large types, one at exactly 47 bytes, and three rejections one byte beyond.
- Cost: the traced native self-build charge rose from 60,230,896 to
  148,926,128 bytes (of 1GiB) and the seed's from 37,723,200 to 91,791,368,
  since types are now allocated values; a self-build stage takes about 0.55s
  instead of 0.37s and the full suite 8m16s instead of 7m08s.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (8m16s). Source 178,109 bytes/483 functions, SHA-256
  8608e273c313312c33db69962f91058ae2105f69ada5f762d4497666fdea2319.
  A1=A2=A3 306,323 bytes, SHA-256
  3407bfd20d2e8f50aa0114c41fea0e0714707ea917d98f0b5ed8da43fbb4bc82.

## 2026-11-18 — types stored at their own length

- The 47-byte type limit came from fixed 48-byte fields. Environment records,
  argument packets and type lists now hold each type after its length byte, so
  a type may take 255 bytes; records are walked in slot order instead of
  indexed. Nesting is bounded at 32 levels, for annotations (it was 12) and for
  inferred types, because the compiler recurses once per level; anything deeper
  or longer is rejected at compilation, never truncated.
- Without the padding the traced native self-build charge fell from
  148,926,128 to 64,358,216 bytes (it was 60,230,896 before types became byte
  strings), the seed's from 91,791,368 to 40,296,128, and a self-build stage
  takes about 0.40s again.
- Checked like the previous step: 6,370 compilations from 18 gates against the
  compiler before the change, with one difference, the intended one (a type
  nested 15 levels is now accepted).
- harness/type_words.py: 411 cases with the 255-byte and 32-level boundaries,
  type lists and entry replacement. harness/structural_types.py: a 252-byte type
  as an annotation and as an inferred tuple, 32 levels of option, and
  rejections one level and one tuple beyond. The 252-byte program exposed a
  byte-by-byte type comparison that overflowed the compiler's 256 frames
  (exit70); it now halves its range.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (7m33s). Source 179,226 bytes/493 functions, SHA-256
  e7452fc5b641f14de8ab7b35c3d1b000972f71f7bd38829b0e88d00447fa67a0.
  A1=A2=A3 308,156 bytes, SHA-256
  dd93b501553a19acc91c3b021cf704d45d04c644de494907849d14a1ee28f92e.

## 2026-11-18 — the pipe operator; bundler rewritten with tuples and pipes

- `left |> name(args)` for every kind of call: module and imported functions,
  function values, library functions with optional arguments, builtins and
  constructors. Looser than + and <>, tighter than comparisons; the target must
  be a call; left is evaluated first. A pipeline may end in IO.puts(),
  IO.write() or IO.warn() as a statement in main, helpers, branches and lambdas.
- The piped value waits in a frame slot under a nameless environment record at
  the target's "(", where the argument list takes it as its first argument, so
  no call path needed its own pipe support (elem reads its tuple there). The
  target is compiled a second time without the record, and a call whose code is
  the same is rejected: it did not take the value (System.pid(), IO.read_all()).
- 39 programs compared with the pinned upstream `alchem run`, all equal.
  harness/pipes.py: 4 programs, 16 rejections, nesting to the expression limit
  (seven deep) and a chain of 40; it is the 25th quick gate and runs per stage.
- tools/alchem-bundle.alc now keeps its state as
  tuple[list[string], map[string, string], map[string, string], map[string, string]]
  and folds imports over result[tuple[state, list[string]], string], the shape
  the 60-bit type word could not hold, and uses pipes and captures throughout.
  Still 61 bundles identical to scripts/bundle-alchem.py at every stage, and it
  passes the pinned upstream `alchem check`. The binary shrank from 43,677 to
  41,252 bytes.
- Found while rewriting it: `none` and `some` cannot name a binding natively
  (upstream accepts `none`); documented as a native limit, not changed.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (7m40s). Source 181,853 bytes/502 functions, SHA-256
  d7c72dd4f37c538b8c5459380cba2a2e59ab7ba1846c9468bfa085fca4498c9b.
  A1=A2=A3 315,273 bytes, SHA-256
  0525e2d9c7caf92a2d0362777d4f91ff3355c735fd54d25cdc3e8b52775a6a1d.
  Traced self-build charges: A0 41,264,424 bytes, native 66,055,128 within 1GiB.

## 2026-11-18 — none/some as binding names; images beyond 1 MiB

- `none` and `some` may name bindings and parameters, as upstream allows; a
  binding of that name hides the constructor in its scope and case patterns
  keep their meaning. Seven programs compared with upstream, all equal.
- The image was one byte payload under the 1 MiB concatenation cap. Byte
  concatenation is now bounded only by the arena, natively and for V11 seed IR
  (V8 to V10 keep their specified 1 MiB), so the seed-built and self-built
  compilers both emit larger images. Total code is capped at 15 MiB; in
  practice the 1,048,575-byte source limit is reached first.
- harness/source_capacity.py builds a 1.6 MB image of 100 functions and calls
  the ones above the 1 MiB mark; harness/alchem_byte_compiler.py now expects a
  byte concatenation past 1 MiB to succeed and one past the arena to exit71.
- Seen while sizing that test: a branch of about 120 output statements makes
  the compiler exit70 (its own 256-frame guard) instead of rejecting with65.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips. Source 181,875 bytes/502 functions, SHA-256
  fa95a7876c7dc4f3602048430655ac2c344895eae8426aecf27e29378d468f53.
  A1=A2=A3 311,289 bytes, SHA-256
  cd7a3cee2c9f55f301da1139e1859de6df46a282a1e33816d028279c0e35da8a.
  Traced self-build charges: A0 41,021,208 bytes, native 65,486,248 within 1GiB.

## 2026-11-18 — structs and sum types, local and imported

- Structs: `struct Name do field: type = default ... end`, `%Name{...}` with
  fields in any order and defaults, `value.field` (also after calls, literals,
  elem, parentheses and capture placeholders), and `%Name{value | field: new}`.
- Sum types: `type Name do variant(field: type) ... end`, `Name.variant(args)`,
  and `case` over variants with field names, `_`, catch-all arms, and the
  pinned exhaustiveness and unreachable-arm rules; recursive types work.
- Both are nominal and work across imports as `Module.Name`:
  `%Geo.Size{width: 3}`, `x: Geo.Shape`, `Geo.Shape.rect(2, 5)` and the pattern
  `Geo.Shape.rect(w, h)`. This closes "imported types and structs", which first
  needed the types themselves.
- A named type is tag 13 or 14 plus the position of its declared name; an
  annotation is parsed as tag 15 (where it was written) and resolved against
  the function table at each use. Declarations take a table record (flag 64 or
  128) and no code. implementations/alchem/native-records.alc,
  spec/alchem-records.md.
- A branch no longer checks which word follows its value; every caller already
  checked (else, end, the next pattern), and variant arms need any pattern
  there. Checked against the earlier compiler on 6,386 compilations: the only
  differences were programs using features added since.
- A binding without a type (an annotation naming no declaration) is now
  rejected, and nameless environment records (piped values, case subjects) are
  carried into lambdas without a name, which also fixes two pipes around one
  lambda being taken for a duplicate binding.
- 50 struct and sum type programs compared with the pinned upstream compiler,
  49 equal; the difference, `==` between two struct values, is next.
  harness/records.py: 5 programs, 27 rejections, 9 invalid declarations, and
  arena exhaustion on a tree of 2^17 nodes; it is the 26th quick gate.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (7m43.700s). Source 195,542 bytes/546 functions, SHA-256
  4a985de26fbb65bf434acded8cc6eedab2dab55266c1d75a22dbdbed6a0fc488.
  A1=A2=A3 349,501 bytes, SHA-256
  e4b1c8b869f7fee5d1c454dd869739d3c01d6e714fa17fa6f132af22a68e779c.
  Traced self-build charges: A0 46,403,536 bytes, native 74,636,440 within 1GiB.

## 2026-11-18 — structural equality

- `==` and `!=` compare lists, tuples, options, results, maps, structs and sum
  types by structure, as upstream does. Function values, and anything holding
  one, are rejected; ordering stays with integers and strings. Before this,
  `==` existed only for integers, booleans and strings.
- Values carry no type at run time, so the comparison is code made for the
  type (implementations/alchem/native-equality.alc): fields chain and skip at
  the first difference, lists and maps loop, and each struct or sum type gets
  an equality function in its declaration's table slot, which had no code
  before, so recursive types compare by recursion. That function returns at
  once for the same record and stops with status 70 when 7 MiB of stack are in
  use; a chain of 2,000 nodes compares.
- 25 programs compared with the pinned upstream compiler, all equal.
  harness/equality.py: 240 random typed pairs (nested lists, tuples, options,
  results and maps) against a structural oracle, struct, sum type and map
  programs, 9 rejections; three mutations of jump distances and of the variant
  test each fail it. It is the 27th quick gate.
- Found on the way: a backward jump's distance went through a number encoder
  that recurses once per megabyte of value and overflowed the compiler's
  frames; backward distances now take the low bytes of the two's complement.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (7m40.487s). Source 201,621 bytes/572 functions, SHA-256
  2faf4946fd004b03d591cd20486541f1ad711d18af571423bc3cfb9bf532265c.
  A1=A2=A3 365,325 bytes, SHA-256
  1987795f95ae02e34502066bb9fb47ecf9b1bc60782ea5989789ad469d34a710.
  Traced self-build charges: A0 48,604,728 bytes, native 78,113,296 within 1GiB.

## 2026-11-18 — general patterns

- Patterns are general (implementations/alchem/native-patterns.alc,
  spec/alchem-patterns.md): `case` over a value of any type with nested
  patterns for tuples, structs, sum variants, options, results, lists
  (`[]`, `[p, q]`, `[head | tail]`) and maps (`%{key => p}`), integer and string
  literals, booleans, `_`, names, `^name` pins and `when` guards.
- `pattern = value` binds a pattern's names and stops with
  `pattern match failed` on standard error and status 2 when it does not
  match. A parameter of a named function may be a pattern that matches every
  value of its type; a parameter of `fn p -> ... end` may be any pattern.
- Exhaustiveness and unreachable arms use the matrix usefulness test over
  pattern trees, so `{true, n}` with `{false, n}` is complete, a missing pair
  of variants is found, and a repeated literal or an arm after a complete set
  is rejected, as upstream does.
- The cases with one arm per constructor keep their direct code; every other
  case goes through the matcher, so earlier programs compile as before.
- Found on the way: an expression directly before an arm's `->` read the
  arrow's `-` as a minus; and `fn [head | tail] ->` is told from the function
  type `fn[...]` by whether its parameters lead to an arrow.
- 70 programs compared with the pinned upstream compiler, all equal except
  that upstream adds the source location to `pattern match failed` and rejects
  a struct pattern as a lambda parameter, which works natively.
  harness/patterns.py: 8 programs, 21 rejections, 4 invalid parameters; it is
  the 28th quick gate.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (8m12.738s). Source 222,073 bytes/633 functions, SHA-256
  2514aad1ee3f1c1a8354cc34532b73e398ef599ba37ccafd55a11674802874fb.
  A1=A2=A3 420,565 bytes, SHA-256
  ab9076e64a7c11295239ba9b03d9c67b353b5a31505d32f1febd44e51ef3a0b6.
  Traced self-build charges: A0 57,275,008 bytes, native 95,355,888 within 1GiB.

## 2026-11-18 — type variables: generic functions and types

- A lowercase type name that is no built-in type is a type variable
  (implementations/alchem/native-generics.alc, spec/alchem-generics.md).
- Generic functions: a call matches the declared parameter types against its
  arguments into a substitution that gives the result type; lambdas among the
  arguments take the types the other arguments settle. Values are one word
  whatever their type, so a generic function is compiled once.
- Generic structs and sum types, `struct Pair[a, b]` and `type Tree[t]`: an
  instance is tag 18 or 19 with its declaration, argument count and arguments;
  literals and constructors settle the parameters, and field reads, updates
  and patterns use the fields' types with the arguments in place.
- Equality through type variables: a generic function takes one hidden
  comparator per type variable after its parameters (0 for words, 1 for
  strings, else a function value), and the equality function of a generic
  type takes the comparators of its arguments. `same(x: t, y: t)`, a recursive
  `contains` and `==` on `Tree[t]` work.
- `&name`, `&name/arity` and `&Module.name` for a generic function make a
  function value for the types the use site expects; without an expected type
  they are rejected, which also keeps a plain reference from skipping the
  comparators.
- Found on the way: scans of a type for variables recursed once per byte and
  overflowed the compiler's frames on a 252-byte type; they now go part by
  part after a halving byte search.
- 45 programs compared with the pinned upstream compiler: all equal, apart
  from four that upstream cannot infer and the native compiler accepts.
  harness/generics.py: 3 programs, 11 rejections, 6 invalid declarations;
  harness/modules.py adds generic functions of an imported module. 29 quick
  gates.
- A self-build stage now takes about 0.85s (0.45s before patterns and
  generics), mostly from checking each call for a generic callee.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (8m51.851s). Source 238,293 bytes/698 functions, SHA-256
  ee9768501de6707c1bdfd89f563af227e205911210d1d2672fef7cb52140ef25.
  A1=A2=A3 459,288 bytes, SHA-256
  a0a7573f6c91d348d09ad4d9e162f66aadba6ce8ab5b89930696bd424be31539.
  Traced self-build charges: A0 66,339,488 bytes, native 117,334,960 within 1GiB.

## 2026-11-18 — Inference parity, allocation-free comparators, six type parameters

- The native compiler now rejects what the pinned compiler cannot type. A
  value that needs a type from its context (`none`, `[]`, `%{}`, a variant of
  a generic type, a lambda in a generic call, an open generic result) is
  marked, and a context that gives no type rejects it: unannotated bindings,
  first list elements, left operands, first library arguments, earlier
  generic arguments. An annotated binding gives its type to a whole call.
  Struct and variant patterns as lambda parameters and generic function
  references for generic parameters are rejected as upstream does.
  harness/inference.py: 8 accepted programs and 38 rejections, each checked
  against the pinned compiler; about 85 probes agree. 44 older test programs
  that upstream also rejects were given annotations.
- Comparators for compound type arguments without type variables are code
  behind a jump (address below 4 GiB, called directly); a million generic
  calls with a list argument now run, where the arena record per call made
  the program exit 71.
- Generic structs and sum types compare with up to six type parameters
  (comparators five and six travel in R10 and RAX); it was four.
- 30 quick gates.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (9m7.039s). Source 244,003 bytes/723 functions, SHA-256
  24eef1cfc26f5c8b17db28ceeb402ed04acf6348a0064d2d3906b48282ef5c7f.
  A1=A2=A3 472,581 bytes, SHA-256
  9401545d5dd51d5967514013be971330c374c43cb0498388f7c474e220410f67.
  Traced self-build charges: A0 70,174,088 bytes, native 122,907,440 within 1GiB.

## 2026-11-18 — Stack mapping in place of the 256-frame guard; long bodies; any number of type parameters

- The 256-frame guard is gone. Every native program, the compiler included,
  switches at entry to its own stack mapping (1 GiB reserved lazily, or the
  largest half the system grants down to 1 MiB) and each function compares
  the stack pointer with the limit in R15; past it the program exits 70. A
  sum recursing 2,000,000 deep now runs; it stopped at 256.
- A branch of about 110 output statements made the compiler exit 70 (its own
  frames). Behind that were more caps, all removed: 16 statements per function
  body, 1024 body tokens, 16 KiB of code per if branch and per and/or operand,
  65535 code bytes per function (lengths in the function table are now 24
  bits). harness/long_bodies.py: 17/120/600 statements in a branch, a helper
  and main, and calls 257, 100000 and 2000000 deep.
- Generic structs and sum types take any number of type parameters (it was
  six at the declaration): past six, the comparators for == travel as an
  array on the caller's stack, and a generic function takes its values past
  the sixth on the stack. harness/generics.py adds a nine-parameter struct
  and a seven-parameter sum type, checked against the pinned compiler.
- Known and next: a body of several thousand statements exhausts the 1 GiB
  compiler arena, since each statement copies the code after it; statements
  that are calls whose value is dropped, and if/case used as statements, are
  still rejected. Both are addressed by the statement-block rework that
  follows.
- 31 quick gates.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (9m13.482s). Source 245,483 bytes/728 functions, SHA-256
  2810b94158973a25c033c97df023ec69ca2fbea5ce3af888d0c81287fab55fbe.
  A1=A2=A3 469,180 bytes, SHA-256
  446da0195bb3b8dae8da9b278c9e801836d85222260dec952d63474699dfa0f3.
  Traced self-build charges: A0 70,496,896 bytes, native 123,409,768 within 1GiB.

## 2026-11-18 — Statements as upstream takes them; Enum.each; bodies of 20,000 statements

- Statements follow the pinned compiler (native-blocks.alc replaces the
  chained body and branch compilers): a call whose value is dropped, if and
  case as statements (else optional, branches need not agree or end in
  values), main that ends without System.halt, System.halt in any function,
  a fn whose body ends in a statement (it returns the empty tuple), and
  Enum.each over a list or a map. All of these were rejected before. What a
  statement may not be is rejected as upstream rejects it: an operator
  expression, a literal, a name, a constructor that is not the block's last
  line, a statement if as a value.
- Statements are joined in runs of doubling length. A body of 3000 output
  statements exhausted the 1 GiB compiler arena (each statement copied the
  code after it); 20,000 now compile in about a second.
- harness/statements.py: 6 programs and 12 rejections, each checked against
  the pinned compiler. harness/long_bodies.py adds 20,000 statements in a
  branch and in main. One older rejection test expected main without
  System.halt to be refused; upstream accepts it.
- Not done here: the rest of upstream's Enum (find, any?, all?, sort, zip
  and others) and its try, for and actor forms are outside the native
  profile.
- 32 quick gates.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (9m29.824s). Source 248,655 bytes/752 functions, SHA-256
  813a02d49f34e6cf7d74b7a55f766540b8666576490b220332500ff6c4f59268.
  A1=A2=A3 475,334 bytes, SHA-256
  a67ad8ba2dd34d0fc71672a3e02a648d10f4c89e641966ef00e3814a2854b4ca.
  Traced self-build charges: A0 86,491,048 bytes, native 140,019,104 within 1GiB.

## 2026-11-18 — Failure traces with file, line, column and calls; call depth limit as upstream

- A program that cannot go on ends as the pinned runtime ends it: status 2
  and `file:line:column: reason`, then one line per active call. It was the
  bare line `pattern match failed`. The routine is spec/trace-x86_64.s
  (native-trace-data.alc); native-trace.alc appends its tables: newline
  positions, files, one name per function-table slot, and the bytes that
  continue a character, since columns count characters.
- Frames are 144 bytes: sixteen slots, the position of the statement being
  run and the frame's closure records. An `if` or `case` used as a value
  inside an expression pushes a record, because the pinned compiler makes it
  a closure and shows it in a trace.
- Calls nest 100000 deep below main, as upstream; one more stops the program
  with `call depth exceeded` and the 61 calls around it. The interim limit
  was the stack mapping alone (exit 70); that check stays, with the limit now
  kept below the initial stack pointer and R15 counting calls again.
- Bundles keep every file's lines (an import line becomes an empty line, the
  rewritten imports sit on the header's line) and start with a manifest of
  each file's length and absolute path, so a trace names the real file and
  line. Both bundlers changed together; upstream running
  tools/alchem-bundle.alc gives the same bundle. `System.cwd!()` was added
  for it.
- The compiler itself is not traced (a program with a native_compile entry
  stores no positions and carries no tables); its image grew from 475 KB to
  527 KB from the wider entries.
- harness/traces.py: ten runs across two bundled files, each equal to what
  the pinned compiler prints for the same files: imported modules, lambdas,
  value-position case, a non-ASCII column, 63 calls shown of 202, the depth
  limit. Gates that asserted the old message or exit 70 on unbounded
  recursion now assert the trace.
- Not matched: `System.halt` with a status outside 0..255 still exits 70
  (upstream prints `exit status must be between 0 and 255`), and deep traces
  of the pinned runtime depend on what its Go compiler inlined.
- 33 quick gates.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (10m22.777s). Source 256,139 bytes/778 functions, SHA-256
  cd44b968c3c4404d6146819aad6cb23fb450fbc3c62864dcd2ba34057af454bd.
  A1=A2=A3 526,849 bytes, SHA-256
  b5356ac166a024a629b110ad89948b3c4efde2a3ba88d94c1034959b6d6269d0.
  Traced self-build charges: A0 98,429,176 bytes, native 153,828,560 within 1GiB.

## 2026-11-18 — Package imports from the module cache, with alchem.lock

- Package imports: `import "host/owner/repo@v1.2.0/lib/file.alc"` is read
  from the Go module cache by both bundlers, with the pinned compiler's
  rules: the shape of the import, one version of a package per program, a
  package's relative imports stay inside it, imports followed in the order of
  their text. `alchem.lock` beside the entry file is checked and written as
  upstream writes it; `--locked` writes nothing and fails on a missing entry.
  An entry written as a package file runs a program the package carries.
- The bundlers do not download. Fetching verifies the archive against Go's
  checksum database over TLS, which a program built by this compiler cannot
  do; a missing package is an error naming `go mod download`.
- The compiler skips `@moduledoc`, `@doc` and other attributes with their
  string or heredoc value, and `require "name" "version"` lines; a package's
  documented files did not compile before.
- harness/packages.py: a program over a package, the lock file, --locked, a
  program run from a package and seven errors, both bundlers agreeing. The
  same files run through the pinned compiler with a local module proxy give
  the same output, the same failure trace into the package file, the same
  lock file and the same errors.
- Not supported: `extern` (it binds Go code).
- 34 quick gates.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (10m14.783s). Source 257,267 bytes/784 functions, SHA-256
  dd1c327ceb291369d0e85ddc130416f3b5786674d7a47df0c5cc05f4fbfffc42.
  A1=A2=A3 529,391 bytes, SHA-256
  47966357bc49d215e682237c074d5af46cdd5db23e3bdc6a0d1df05415b343ef.
  Traced self-build charges: A0 99,025,656 bytes, native 154,809,552 within 1GiB.

## 2026-11-18 — String interpolation, heredocs, larger literals, exit status message

- Found while testing packages and closed: `#{expression}` in strings
  (string, integer and boolean values, as upstream), heredocs with the closing
  line's indentation removed and expressions inside, string literals past 128
  bytes, list and map literals up to 4096 elements (128 before), and
  `System.halt` outside 0..255 ending with upstream's message and trace
  instead of a silent 70.
- harness/literals.py: 7 programs and 7 rejections, each checked against the
  pinned compiler. Three older rejection tests asserted the removed limits.
- Still native ceilings, each tied to a fixed layout: six parameters per
  function (argument packets hold six types), sixteen live bindings (frame
  slots are addressed with one-byte offsets), and expressions nested 16 deep.
- 35 quick gates.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (10m13.794s). Source 262,192 bytes/800 functions, SHA-256
  bba5ca8903551327a12cde07a9b9b46e7c573f3187d728a10108d57d06710602.
  A1=A2=A3 542,415 bytes, SHA-256
  4765df718258e56897726e6980e63c5246bd4960ad4bf515ea824a8cee8bff5c.
  Traced self-build charges: A0 101,560,744 bytes, native 158,834,632 within 1GiB.

## 2026-11-18 — Expression nesting and operator chains past 16

- Expressions and blocks nest 200 deep and a chain of one operator takes
  4096 operands; both stopped at 16, so a sum of 17 terms or a concatenation
  of 17 strings was rejected. The limits dated from the 256-frame guard.
- harness/literals.py adds 100 nested parentheses, a 61-term sum, a 40-part
  concatenation, 30 conditions and 25 nested calls, checked against the
  pinned compiler. harness/pipes.py: eight nested pipes now run; seventeen
  are refused by the frame's sixteen slots.
- 35 quick gates.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (10m12.946s). Source 262,210 bytes/800 functions, SHA-256
  0aca3f0ff39d2ab506f0fa3f4f6a7cf982e348c0b329613bdfaa5a415b157253.
  A1=A2=A3 542,543 bytes, SHA-256
  7155a4b8a8afa876a6c7049aaa3ed0f8b4bf0ef4b084e2a0f7463e187f01ee95.
  Traced self-build charges: A0 101,571,272 bytes, native 158,845,320 within 1GiB.

## 2026-11-18 — Any number of parameters, tuple elements and live bindings up to 250

- The fixed layouts behind the last ceilings are gone. A function takes 200
  parameters and a call 250 arguments (six before): an argument packet holds
  one type per argument and a byte of marks each, and arguments past the
  sixth travel on the stack until the call returns. Tuples and function
  types take 250 parts (six before).
- A function holds 250 live bindings (sixteen before). Every slot access
  goes through nc_slot: the first sixteen keep their one-byte offsets, later
  ones lie below the frame's trace words with 32-bit offsets, and the frame
  is sized from the function's finished code.
- A pipe decided whether its call took the piped value by compiling the call
  twice, which doubled the work per nesting level: twelve nested pipes took
  0.4 s and seventeen exhausted the arena. It now looks for the load of the
  pipe's slot; forty nested pipes compile at once.
- harness/wide.py: five programs (7 to 30 parameters, lambdas and function
  values of 7 to 9, a generic function of 7, tuples of 9, a struct of 10
  fields, a variant of 8, 200 live bindings, recursion with 30 locals), each
  equal to the pinned compiler's output. Older tests of the six-parameter,
  six-element and sixteen-binding rejections were removed.
- The bounds that remain come from one byte: the slot in an environment
  record and the count in a type.
- 36 quick gates.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (10m28.349s). Source 263,720 bytes/804 functions, SHA-256
  c225e9bc88148e77955ea73f5e0cd9b1236324984adb4d30e964c85e516e706c.
  A1=A2=A3 543,058 bytes, SHA-256
  bd0344ad4c5052b286534684507e90bd4e05523170bc2c5bc77bbded71ddd9d2.
  Traced self-build charges: A0 100,593,232 bytes, native 158,098,648 within 1GiB.

## 2026-11-18 — Checked arithmetic, Kernel functions, cond, list operators, inspect; coverage measured

- Measured against the pinned compiler's own documentation: every example in
  its syntax reference (47 programs) and library reference (825 sessions) is
  run through both compilers. 5 of 872 produced the pinned output before this
  work and 70 do after it. The measuring script is outside the tree; the
  numbers are the guide to what to build next.
- Integer arithmetic is the pinned language's: `/`, `%` and `**` exist, and
  `+ - * **`, unary minus, `abs`, `/` and `Enum.sum` end the program with
  `integer overflow`, a zero divisor with `division by zero`, a negative
  exponent with its own message, each with the trace. A compiler entry keeps
  wrapping `+ - *`, which is what the seed gives it. The expression
  evaluator in lexer.alc, whose contract is wrapping arithmetic, no longer
  relies on the language for it (wrap_add, wrap_multiply and the rest).
- `&&`, `||` and `!`; `++`, `--` and `in` on lists (the last two compare by
  the element type's equality); `cond`, whose arms the block reader finds by
  their tokens; `rem div abs min max length hd tl to_string map_size assert`
  called without a module name or as `Kernel.name`.
- `inspect` and `IO.inspect` for every kind of value but one of a type
  variable's type: the compiler writes a description of the type behind the
  call and one routine walks the value by it.
- Strings take the pinned escapes, code points included; a statement may be
  any expression piped into a call.
- The failure routine takes any message: a number in its table or a string.
- harness/operators.py (51 programs, 12 rejections) and
  harness/inspection.py (6 programs, 11 rejections) hold what the pinned
  compiler prints. 38 quick gates.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (11m36.810s). Source 286,365 bytes/870 functions, SHA-256
  529b0c42de90ae1d035f85708ad536a058293a5ca66d425a1a6cf5d51ecc3092.
  A1=A2=A3 591,778 bytes, SHA-256
  f60853ef272d441d76f0381dc7e1f74090a03ab3e0e7c9fdc3d6afb1aa2e8532.
  Traced self-build charges: A0 125,320,224 bytes, native 191,386,384 within 1GiB.

## 2026-11-18 — Library written in Alchem; unless, one-line if, constants; seed call depth

- Library functions are now written in Alchem. `library/Enum.alc`, `List.alc`,
  `Map.alc`, `String.alc` and `Kernel.alc` hold 161 functions; the compiler
  appends the ones a program mentions as modules `AlchemEnum2` and the like
  (one per library module and number of parameters) and looks a library call
  it has no code of its own for up there. A name may have several forms for
  one number of arguments, which is how `Enum.sort`, `min` and `max` exist
  for integers and for strings.
- The map routines take a type variable's key type from its comparator at
  run time, so generic functions over maps compile.
- `unless`, the one-line `if c, do: a, else: b`, module constants
  (`@name value`), names ending in `!`.
- The seed backends bound a program at 256 nested calls. The seed-built
  compiler met that bound compiling its own most deeply nested functions,
  which showed as E_RUNTIME_LIMIT once the source held 1282 functions. IR
  version 11, which only compiler builds use, now allows 1024 calls and
  4 MiB of stack in both backends.
- 194 of the 872 examples of the pinned syntax and library references now
  agree (70 at the last entry). harness/library.py holds 244 programs, of
  them the reference's own examples that pass, with the pinned output;
  harness/forms.py holds the language forms. 40 quick gates.
- Not done: these library functions take lists only, not maps, ranges or
  streams; a list built element by element is copied at each step, so
  sorting costs n squared; failures inside them are traced into the
  appended module; the ordered functions exist for integers and strings.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (16m19.023s). Source 431,742 bytes/1156 functions, SHA-256
  936fa95471e6a2b452647ebee4e5b0eac4cea254f3e7b881e1eb400bafdaaab2.
  A1=A2=A3 754,541 bytes, SHA-256
  4581176059932007a2b90fa6902eb4b3cf696327ed21c9c4213425f50cdbb8e6.
  Traced self-build charges: A0 167,525,856 bytes, native 248,262,816 within 1GiB.

## 2026-11-18 — Atoms, ranges, raise; library of 562 functions; 356 of 872 examples

- 356 of the 872 examples of the pinned syntax and library references agree
  (194 at the last entry).
- Atoms and keyword lists, ranges, `raise`, `String.to_atom`; see
  spec/alchem-operators.md.
- The library written in Alchem holds 562 functions: Path, Range, Base,
  Bitwise, URI, Version, IO.ANSI, Keyword and Atom are new, and Enum, List,
  Map, String, Integer and Kernel were widened (maps and ranges as
  enumerables, option forms that take atoms). Most of it was written by
  agents working in copies of the tree, each on its own library files, and
  merged here.
- A library name takes up to nine forms per number of arguments. The library
  text is packed by byte pairs inside the compiler, and a module's functions
  are tested against a program only when the module is mentioned.
- The full verification takes 26 minutes now (16 before): the compiler is
  1.25 MB and every program compiled by a gate is scanned for library names.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (26m14.534s). Source 742,026 bytes/1811 functions, SHA-256
  c42f25a6208f80de9971c55074316024f37c62976bf36506a1a125eba2923466.
  A1=A2=A3 1,251,728 bytes, SHA-256
  cfe8376d49d9edfa33badf85e5d238cfdf85512d2ee05ecb3a4877963ecadca2.
  Traced self-build charges: A0 285,158,176 bytes, native 412,083,048 within 1GiB.

## 2026-11-18 — Clauses, with, for, floats; verification in six minutes; 386 of 872

- 386 of the 872 examples of the pinned references agree (356 at the last
  entry): function clauses, guards, default arguments, functions of one name
  by parameter count or type, `return` (spec/alchem-clauses.md); `with` and
  `for` (spec/alchem-comprehensions.md); floats (spec/alchem-floats.md);
  structs declared by library files visible everywhere.
- The full verification takes under six minutes (26 before). The gates ran
  three times, on A1, A2 and A3, which are compared byte for byte just
  before: they run once now, on A3, each in a process of its own, side by
  side. type_words and core_modules compile their programs in parallel, and
  the second compile that checks determinism is taken for one program in
  eight.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (5m45.387s). Source 832,489 bytes/2073 functions, SHA-256
  19b7e9f7030cae0be7f499b1d06976285ea5f001eb228b57c30066d5ece87fde.
  A1=A2=A3 1,438,837 bytes, SHA-256
  6d4e0f22e6cda2cbb11f14a2b1e0bb1cf50d70af41f601e182fc1fc8da612c07.
  Traced self-build charges: A0 408,366,752 bytes, native 538,077,272 within 1GiB.

## 2026-11-18 — Sigils, indexing, library messages; verification in three minutes; 401 of 872

- 401 of the 872 examples of the pinned references agree (386 at the last
  entry): sigils, value[index], literal patterns on the left of `=`,
  references to library functions, lambdas typed by an earlier lambda's
  result (spec/alchem-sigils.md); library failures with the pinned
  messages, URI.merge, Version requirements, OptionParser.
- The full verification takes under three minutes. The steps of
  scripts/verify-local.sh that do not depend on each other run side by side
  (bg/join in the script); every program is again compiled twice for the
  determinism check. The log holds the same passing lines as before.
- The packed library text numbers its symbols by frequency, which brought
  the compiler's source from 916 KB to 851 KB of the 1 MiB a source may
  have. That limit is the next thing in the way of more library.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (2m56.963s). Source 850,853 bytes/2224 functions, SHA-256
  44f26ea4d96d237ee8ffb038135ba7b0d881466a86e4eec1284da7d25e07c302.
  A1=A2=A3 1,579,298 bytes, SHA-256
  cd6805c6a80446ccf839dee706d10fd5519ff2f4d702112642320701bb87b7bc.
  Traced self-build charges: A0 454,334,000 bytes, native 597,231,416 within 1GiB.

## 2026-11-18 — Dates and times; 490 of 872

- 490 of the 872 examples of the pinned references agree (401 at the last
  entry). The date and time library (Date, Time, NaiveDateTime, DateTime,
  Duration, Calendar) is written in Alchem; with the date sigils and their
  inspect it passes 89 of its 94 examples. The five that fail need the
  time-zone database: DateTime knows UTC and fixed offsets.
- A struct a library file declares is appended when the program's text
  holds its file's module name, its own name or a text given after `also`
  in its header (the date sigils).
- The compiler's source is 945 KB of the 1 MiB a source may have. Raising
  that limit is in progress and has to be merged before more library text.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (3m16.070s). Source 945,010 bytes/2427 functions, SHA-256
  706246b911ef1beff19bc0e235462c227e0a72c4318057e88a95e9badef9883c.
  A1=A2=A3 1,713,345 bytes, SHA-256
  ce400dd83d78f4ca3a21313d39d15e78222a4e89ee8d8e09954128993952983e.
  Traced self-build charges: A0 502,627,232 bytes, native 655,718,472 within 1GiB.

## 2026-11-18 — Source limit 4 MiB; try and exceptions; 494 of 872

- 494 of the 872 examples of the pinned references agree (490 at the last
  entry).
- The source limit is 4,194,303 bytes (spec/source-capacity.md): entry
  stub, checks, V11 input in both seed backends, 32-bit code sizes, a 64-bit
  trace word, and a compiler arena of 16 GiB reserved lazily. The seed
  frontend, whose parser stops at 1 MiB, lowers a longer compiler source in
  parts. harness/grown_compiler.py builds a 4 MiB compiler source
  seed -> A1 == A2. The compiler's own source is 964 KB.
- try, rescue, catch, else, after, throw and defexception
  (spec/alchem-try.md): a chain of handler records on the stack that the
  failure routine consults before it prints.
- The next ceiling is 4096 functions per program: the compiler has about
  2,500, and every library function written in Alchem adds one.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (5m25.258s). Source 964,033 bytes/2485 functions, SHA-256
  93b664b76aa94603b65ad2ad7e49bc44842afbffbf7a88476e796035a8a0f99c.
  A1=A2=A3 1,762,553 bytes, SHA-256
  52cb3a31082e3bb824fa429fc86c64d7bd91000b74fad1c6860f33363f3616eb.
  Traced self-build charges: A0 520,928,112 bytes, native 680,557,696 within 1GiB.

## 2026-11-18 — Files and system, ordering forms, memory ceiling; 570 of 872

- 570 of the 872 examples of the pinned references agree (494 at the last
  entry).
- Float forms and ordering of tuples, lists, booleans and atoms in the
  library; a stopgap MapSet; Markup, Function, Crypto.secure_compare. Known
  wrong result: tuples and lists whose parts are themselves tuples or lists
  are not ordered (spec/alchem-library-profile.md); the compiler-made
  ordering that cures it is in progress.
- The file and system library (spec/alchem-system.md): File, System,
  Path.wildcard, IO on files, System.cmd running external programs, radix
  integer literals. System-call primitives exist only inside the library.
  A failure inside a library function is reported at the call that entered
  the library, without the library's frames.
- A test program run by the pinned compiler with no memory ceiling grew to
  58 GB and the kernel's out-of-memory killer ended the session.
  scripts/limited now runs a command in a systemd user scope with MemoryMax
  and a timeout; the verification scripts run themselves under it and the
  pinned compiler is reached through a wrapper that does.
- Gate subprocess timeouts are two minutes: the shorter ones were guards
  against hangs and failed gates on a loaded machine.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m26.901s). Source 1,033,338 bytes/3023 functions, SHA-256
  bea8ca8768b9cad9a2646093040ad183e36162d8441d70cbb5cadb6583f635af.
  A1=A2=A3 1,826,138 bytes, SHA-256
  14f4135a76dc2e113f5bbe432399b5b79b93f86da1f8bc46dbdd6fda20a30d9a.
  Traced self-build charges: A0 569,509,944 bytes, native 733,051,384 within 1GiB.

## 2026-11-18 — Sets, streams, lazy ranges; 610 of 872

- 610 of the 872 examples of the pinned references agree (570 at the last
  entry).
- Sets and streams (spec/alchem-sets-streams.md): set[T] and stream[T] are
  types of their own, MapSet and Stream are written in Alchem, a range is
  lazy (first, last, step), File.stream!, IO.stream and Date.range are
  streams, and a map may be keyed by tuples. A library name takes up to
  sixteen forms.
- harness/source_capacity.py retries a just-written program that another
  thread's fork still holds open; it had failed one full run.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (5m18.229s). Source 1,126,194 bytes/3229 functions, SHA-256
  9c0699a48a26e7d6600580c777018e881a3f5ed8845ca3d1d98843e60cae6e5c.
  A1=A2=A3 1,956,248 bytes, SHA-256
  fc60e8d0b158970d505544bf5623251f4187e55ab6fb5c9d315fc0ebf169b861.
  Traced self-build charges: A0 626,352,776 bytes, native 808,275,144 within 1GiB.

## 2026-11-18 — Regular expressions; 625 of 872

- 625 of the 872 examples of the pinned references agree (610 at the last
  entry).
- Regular expressions (spec/alchem-regex.md): the ~r sigil, =~, the Regex
  module and the String forms that take a regex. A port of Go's
  regexp/syntax compiles a literal while the program is compiled; the
  matcher is written in Alchem. Checked against Go's regexp on thousands of
  generated cases. Patterns such as (a|a)*b take exponential time, and a
  repetition of more than one character over a long subject meets the call
  depth limit.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (5m18.889s). Source 1,310,166 bytes/3491 functions, SHA-256
  d9444492f1e13c8d31c0ab14ad5c5463b3f56b07a9a1a46fc3477a7183e977a5.
  A1=A2=A3 2,181,967 bytes, SHA-256
  8b1087f43afac8b33ba8c34b9fcd7034510f1991482c51234a410051ecb50562.
  Traced self-build charges: A0 712,856,880 bytes, native 920,318,488 within 1GiB.

## 2026-11-18 — Compiler-made ordering; 65,535 functions; single-pass library lookup

- 625 of the 872 examples of the pinned references agree (unchanged: this
  round is correctness and capacity).
- Ordering is made by the compiler for the type (spec/alchem-ordering.md):
  a type variable's comparator answers equality or a three-way order, the
  ordered library functions are single generic entries, and sorting is Go's
  stable and unstable sorts as machine code. The known wrong result is gone:
  tuples and lists of any nesting order as the pinned compiler orders them.
  Tuple map keys use the same comparator.
- A program may hold 65,535 functions (4,096 before) in the compiler and
  both seed backends; the function table is built without copying and
  carries a name index. The library is chosen in one reading of the
  program and its generated data is one packed string per module and an
  index. A 60,000-function program compiles in about ten seconds; the
  compiler builds its own source in about three.
- The full verification takes two minutes.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (1m58.683s). Source 1,230,995 bytes/1889 functions, SHA-256
  c5b717d431dd0e9813b50e4f4050ef86be4f4a9c2643852eb5d16a99a61299ca.
  A1=A2=A3 1,666,418 bytes, SHA-256
  2bf83378dcd2c13ebe067b3e7168216ea9045516133c1e1f2fb002a3eeb15bbe.
  Traced self-build charges: A0 458,738,688 bytes, native 636,446,184 within 1GiB.

## 2026-11-18 — Tail calls; 16 GiB lazy arena

- 625 of the 872 examples of the pinned references agree (unchanged).
- Self calls in return position are jumps under the pinned compiler's rule
  (spec/alchem-tail-calls.md): a loop of ten million turns runs in constant
  stack, and library functions written in Alchem no longer count toward the
  call depth, as the pinned runtime's own functions do not.
- An ordinary program reserves 16 GiB lazily (4 MiB before), halving down
  to 4 MiB when the system refuses; the gates that measure charged bytes or
  expect exhaustion run under an address-space floor and keep their
  meaning. File.read and IO.read_all have the pinned 16 MiB limits.
- Nothing is reclaimed, and a list is copied on prepend and on taking a
  tail, so building or walking a list of n elements in a loop costs about
  4 n squared bytes: a list of 20,000 built by consing takes 3.1 GB where
  the pinned runtime takes 7 MB. This is now the main memory difference.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (1m56.928s). Source 1,236,492 bytes/1911 functions, SHA-256
  be673d986eb1ec249f60a215d544b43d04f4882a05d91e1fb0f1a0fa5012c8f5.
  A1=A2=A3 1,679,593 bytes, SHA-256
  29f9fc965beb15f6d6193f7e4d6117c4f6c9416c8befbed9317ffc01c5120cf3.
  Traced self-build charges: A0 471,559,488 bytes, native 658,614,688 within 1GiB.

## 2026-11-18 — Processes; 734 of 872

- 734 of the 872 examples of the pinned references agree (625 at the last
  entry).
- Processes (spec/alchem-processes.md): spawn, send, receive with after,
  links, monitors, exits, and the modules over them: Process, Task,
  Task.Supervisor, Agent, Server, Supervisor, DynamicSupervisor, Registry,
  Port and the receive assertions of Testing. Processes are green threads
  inside the one thread; the scheduler and the modules are written in
  Alchem. Every documented example of these modules passes. Blocking system
  calls hold up every process and nothing is preempted; where the pinned
  runtime's order is a race, the order here is first in, first out.
- Node and Stream.publish are not built.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (2m49.769s). Source 1,439,114 bytes/2008 functions, SHA-256
  540ca41711b1e999c2f56d64147e560fc1be207dbf9dcd8be645f241aaaddf7a.
  A1=A2=A3 1,854,546 bytes, SHA-256
  9634f060fcf7efc463ce92705950c0316835392e62e04e72eadcabc0faedb115.
  Traced self-build charges: A0 522,955,456 bytes, native 726,257,016 within 1GiB.

## 2026-11-18 — Macros, protocols, templates; 742 of 872

- 742 of the 872 examples of the pinned references agree (734 at the last
  entry).
- Macros (spec/alchem-macros.md), protocols (spec/alchem-protocols.md) and
  HTML templates with the whole of Markup (spec/alchem-templates.md). A
  program using them is rewritten as text before compilation; a fifth trace
  table of moved records turns a position back to the place in the program
  as written.
- Parser gaps closed (spec/alchem-parsing.md): a line starting with `(` or
  `[` after a name, a binding followed by an unannotated `fn`, `hd([])` as a
  case arm, variants and struct fields named like types, `fn` with clauses.
- (Fixed in the next entry.) A struct or variant field whose type is an undeclared type
  variable makes the compiler exit 72 without a message; the pinned
  compiler says `unknown type`.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (2m10.575s). Source 1,500,391 bytes/2214 functions, SHA-256
  43be91cc6f21b8d5d400efca1f83e9b86a8613c5713de90155340ef846cfcddb.
  A1=A2=A3 1,999,500 bytes, SHA-256
  ad8b726872ea5c679bbff86edf6cbee6022482afafd122f1fee5414155cb4d2c.
  Traced self-build charges: A0 567,761,400 bytes, native 792,275,968 within 1GiB.

## 2026-11-18 — Undeclared type variables in declarations

- 742 of the 872 examples agree (unchanged).
- A struct or variant field whose type mentions a type variable the
  declaration does not declare is rejected, as the pinned compiler rejects
  it; the compiler exited 72 without a message before. This was the last
  status-72 case the fuzzing of the macro round left.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (2m8.167s). Source 1,501,354 bytes/2219 functions, SHA-256
  91cdf40613b5318daaafa921c779b688af81872e6b0ea5074669ec5857a556d2.
  A1=A2=A3 2,001,508 bytes, SHA-256
  7b2762ef820103a152c5c8958fd53cdacb7fdcc76a7beca50829e39aeed63946.
  Traced self-build charges: A0 568,477,224 bytes, native 793,418,912 within 1GiB.

## 2026-11-18 — Lists that do not copy

- 742 of the 872 examples agree (unchanged: this round is memory and time).
- A list is a run of counted pairs (spec/alchem-lists.md): the tail of a
  list is an address inside it and `[x | list]` writes into the unclaimed
  pair below, so both are constant. Building 20,000 elements by prepending
  and summing by `[h | t]` takes 7 MB (3.1 GB before); ten million take
  408 MB against the pinned runtime's 207 MB.
- The library's element-by-element builders are linear (dedup, zip,
  chunk_every, flat_map, with_index, scan, graphemes, codepoints and the
  rest): each ran out of 6 GB at 100,000 elements before and is within a
  factor of about two of the pinned runtime at a million now.
- Still different: `acc ++ [x]` in a loop keeps 16 n squared / 2 bytes
  (nothing is reclaimed); an element takes 16 bytes against 8.
- Found on the way and fixed: a map type whose key cannot be a key is
  rejected as the pinned compiler rejects it; Enum.split/2, count_until/2
  and slice/2 with a range compile beside Enum.max or Enum.min.
- File.mkdir_p! and File.rm_rf! do not exist in the pinned compiler
  either (`undefined function`), so their rejection is not a difference.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (2m33.531s). Source 1,506,128 bytes/2221 functions, SHA-256
  8a8d55de51aca9c396168c3262085a9e767aca5be83db31e380899ae6dd6894c.
  A1=A2=A3 2,006,279 bytes, SHA-256
  5d98a5e8ac8ca593a233aef0b1f768b7e240d74b735e683c5b4c9cb41bcaef46.
  Traced self-build charges: A0 570,255,976 bytes, native 795,774,664 within 1GiB.

## 2026-11-18 — Network and DiskStore; 788 of 872

- 788 of the 872 examples of the pinned references agree (742 at the last
  entry).
- TCP, UDP, HTTP (client and server), WebSocket and DiskStore
  (spec/alchem-network.md), written in Alchem over raw system calls.
  Sockets are non-blocking and the scheduler serves waiting processes with
  ppoll. The server's wire bytes match the pinned runtime's over 70 raw
  cases; DiskStore's file format is byte-identical.
- TLS is not built (https, wss, connect_tls, serve_tls): a peer that is not
  TLS gets the pinned runtime's error text; a real TLS peer is refused with
  `tls: the handshake is not built`.
- HTTP.json waits for JSON; the 13 DiskStore examples wait for
  Crypto.strong_rand_bytes. Compressed bytes are valid but not Go's.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (2m30.604s). Source 1,858,305 bytes/2282 functions, SHA-256
  0ad736db2735727107f6c3d2f58b01271c5372f87a50571058f302765f3535d3.
  A1=A2=A3 2,272,667 bytes, SHA-256
  9d6d79bcffc7bb36c860b6a7f01742c787baa787bf3b61d736803cea0adfc0bc.
  Traced self-build charges: A0 647,353,464 bytes, native 894,305,472 within 1GiB.

## 2026-11-18 — Crypto, JSON, Logger, Gen, test runner; 851 of 872

- 851 of the 872 examples of the pinned references agree (788 at the last
  entry). The 21 that remain: Node (15), the nodes syntax example,
  Stream.publish, String.normalize, File.mkdir, File.rmdir and extern.
- Crypto (digests, HMAC and PBKDF2 as machine code, spec/alchem-crypto.md),
  JSON driven by the compiler's type description (spec/alchem-json.md),
  time zones read from TZif files (spec/alchem-time-zones.md), Logger with
  metadata per process (spec/alchem-logger.md), Gen with the pinned
  generator's values and shrinking, and the test runner
  (spec/alchem-testing-gen.md): a program that declares a test gets the
  pinned runner's main, with describe, setup, tags, check all, doctest,
  selection, seed shuffle, timeouts and the pinned failure report.
- Not built: the bitwise operators (|||, &&&, ^^^, <<<, >>>, ~~~) do not
  compile in any program; coverage (ALCHEM_COVER_FILE); TLS.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (2m43.940s). Source 2,142,796 bytes/2567 functions, SHA-256
  141b3622c506d61b5060dace7a626b78644fa04710749399cf841a4fd153d82f.
  A1=A2=A3 2,604,317 bytes, SHA-256
  7554c79c2efa36e4bae5cfb98ee15a42c5e7382b44a5f741091b8ad380a4ed7f.
  Traced self-build charges: A0 745,175,144 bytes, native 1,055,607,824 within 1GiB.

## 2026-11-18 — Node distribution; 868 of 872

- 868 of the 872 examples of the pinned references agree (851 at the last
  entry). The four that remain: String.normalize, File.mkdir, File.rmdir
  and extern.
- Node distribution (spec/alchem-nodes.md): all of Node, remote handles and
  Stream.publish, speaking the pinned runtime's wire protocol, plain and
  over TLS 1.3 written in Alchem (X25519, ChaCha20-Poly1305, Ed25519). A
  native node and a node built by the pinned compiler give identical output
  in every pairing, including the pinned tree's own nodes and cluster
  programs.
- The sendable check on mailbox types is done where the pinned compiler
  does it. Library reads of standard input wait cooperatively in a program
  with processes.
- Different: a native dialler does not verify the server certificate (the
  pinned nodes present ECDSA P-256, whose arithmetic is not built; the
  pinned runtime skips verification too and the cookie proof is bound to
  the session); one cipher suite and curve; curve arithmetic is not
  constant time. The TLS of TCP and HTTP (connect_tls, serve_tls, https,
  wss) is still not built on it.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (2m51.605s). Source 2,311,897 bytes/2620 functions, SHA-256
  f558e356965a9e4c0fd2cc8b20650faaf49964dd2d1f4bb14f855998c9b48339.
  A1=A2=A3 2,751,875 bytes, SHA-256
  09f178bdd71c1552c2a6d90aa336b76912cecd475a6a012793700063886f2fbe.
  Traced self-build charges: A0 787,573,768 bytes, native 1,111,546,040 within 1GiB.

## 2026-11-19 — TLS for TCP, HTTP, WebSocket and nodes; 868 of 872

- 868 of the 872 examples of the pinned references agree (unchanged). The
  four that remain: String.normalize, File.mkdir, File.rmdir and extern.
- TLS (spec/alchem-tls.md) in library/TLS.alc, used by TCP.connect_tls,
  HTTP.serve_tls, https, wss and nodes: TLS 1.3 and 1.2, client and server,
  AES-GCM, ChaCha20-Poly1305 and AES-CBC-SHA, X25519 and P-256/384/521,
  and certificate verification as crypto/x509 does it (chains, dates,
  names, constraints, key usage, system roots; RSA PKCS #1 and PSS, ECDSA,
  Ed25519). HTTPS_PROXY tunnels with CONNECT. The bignum, AES and ChaCha
  code is machine code (spec/tls-x86_64.s, runtime slot functions+7).
- A dialling node now checks the CertificateVerify signature.
- Process._stack asks for an eighth, not a half, when a stack size is
  refused, so a program carrying TLS still fits a 3 GiB address space.
- A program may define its own module named TLS.
- Different: no session resumption; no X25519MLKEM768 or ML-DSA; the HTTP
  client offers http/1.1 only (no HTTP/2); the ClientHello bytes are not
  Go's; certificate policies and e-mail/URI name constraints are not
  evaluated; an unparseable certificate is always "x509: malformed
  certificate"; RSA signs without CRT or blinding; Ed25519 and the code
  around the machine code are not constant time; secrets are not wiped.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (3m10.013s). Source 2,531,964 bytes/2670 functions, SHA-256
  a0b91f86353e66199f26423e1b03e42e6c2597720854f5628db4f07ac0cc39bf.
  A1=A2=A3 2,921,384 bytes, SHA-256
  cd5dccf24fa1cbe196a7940c7aafd7af0dab239e2a62d66ea0913b396456c406.
  Traced self-build charges: A0 837,342,008 bytes, native 1,174,887,128 within 1GiB.

## 2026-11-19 — Compiler gaps closed; 871 of 872

- 871 of the 872 examples of the pinned references agree (868 at the last
  entry). The one that remains is extern, which is dropped.
- An expected function type reaches a lambda in every position, the body is
  held to the expected result, value.(args) works on any function value,
  and function and stream values pass through generic library functions.
- Bitwise operators &&& ||| ^^^ <<< >>> ~~~ compile, with the pinned
  precedence and shift semantics.
- Fixed limits removed or set to the pinned thresholds (spec/source-capacity.md):
  token scan budgets, 4096 elements, 64-character names, comment lines,
  type nesting; 250 variants and 250 struct fields. Variant tags from 128
  matched the wrong case arm; fixed.
- String literals, atoms, heredocs and sigil texts sit in the image and
  cost no allocation. Library selection reads code only, not comments or
  string text.
- String.normalize, written in Alchem from the pinned Unicode tables. The
  File.mkdir and File.rmdir examples had stale cached answers
  (scripts/upstream-examples.py --refresh).
- The pinned tree's kv project compiles and its tests pass; bare reduce
  passed its callback arguments in the wrong order and is fixed. Of the
  tree's 136 programs, 109 give identical output.
- Gate harness/gaps.py: 2,052 programs frozen from the pinned compiler.
- Different: 250 live bindings per function (one-byte slot numbers); 200
  parameters, 249 arguments, 250 tuple parts; 255-byte structural types;
  about 5,000 case arms or clauses exhaust memory; a user generic that
  compares function values compiles where the pinned compiler rejects it;
  machine-code builtins exit instead of raising for assert_raise; a zero
  range step does not raise; JSON on a type variable; a ~h heredoc inside
  assert; "socket options at their edges" crashes.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (3m53.405s). Source 2,958,841 bytes/2771 functions, SHA-256
  e2ef116d89fd477b110ab185b503ba675b21a40845c4c1b7569fb95c4bf60489.
  A1=A2=A3 3,255,745 bytes, SHA-256
  aeba51500b57fb4abf152b91b7b4dfea5823a5e401ee496ed581420603dcd5ef.
  Traced self-build charges: A0 1,195,533,448 bytes, native 1,570,053,096 within 1GiB.

## 2026-11-19 — Runtime failures and tree parity; 871 of 872

- 871 of the 872 examples of the pinned references agree (unchanged); 115
  of the pinned tree's 136 programs give identical output (109 before).
- Machine-code builtins raise instead of exiting (spec/alchem-failures.md):
  Enum.slice, String.duplicate/split/slice/to_integer/pad, Integer
  to_string/parse/digits/undigits, IO.read_line/read_all, with the pinned
  message and trace, and the pinned runtime's panics as "<runtime>: panic".
- A zero range step raises; Range.size/disjoint?/split/shift wrap as the
  pinned ones do (disjoint? was quadratic and did not finish at the edges).
- The zero value beside false of a timed-out Process.receive is built for
  structs, ranges and sum types (it crashed). Monotonic time counts from
  program start.
- A ~h template inside an assertion gets its assertion text.
- Test programs count statements and write ALCHEM_COVER_FILE with the
  pinned lines and counts.
- The nodes gate builds the second program before it starts the first; the
  pinned shop waits ten seconds, which a build on a loaded machine exceeded.
- Different: JSON.encode!/decode_as on a type variable (a comparator per
  type variable carries no type description); there is no native driver
  that finds and runs test files, so nothing prints the --cover table;
  the option/result zero of a timed-out receive shows none/error, not nil;
  case over a sum-type nil takes the last arm; Kernel.not(x) and a
  statement ending |> elem(0) compile where the pinned compiler rejects.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m21.664s). Source 2,990,996 bytes/2833 functions, SHA-256
  4f25f609e605f815850ce702c50d162aec30f8042d9b6b55a4afe048694f3ea4.
  A1=A2=A3 3,303,966 bytes, SHA-256
  06440c3cfce3743e684399502208fed181411a55111fae31b00e539295953f3f.
  Traced self-build charges: A0 1,216,226,088 bytes, native 1,597,815,024 within 1GiB.

## 2026-11-19 — Fixed limits removed; 871 of 872

- 871 of the 872 examples of the pinned references agree (unchanged).
- Fixed limits removed (spec/source-capacity.md): 250 live bindings per
  function (slots are wide in environment records, captures and plans);
  counts of arguments, tuple parts, parameters, variants, fields and type
  parameters; 255-byte structural types; number literals of any length.
- Case arms, cond arms, function clauses, interpolations, list, string and
  struct literals and for/try bodies compile in near-linear time and
  memory (native-arms.alc): 50,000 case arms in 3.4 s where 5,000
  exhausted 6 GB.
- A generic function that compares values of a type variable rejects a
  type without equality, by the pinned compiler's fixpoint
  (native-needs.alc). An argument for an enum parameter that needs its
  type from context is rejected as the pinned compiler does
  (native-enumerable.alc).
- Wrong result fixed: a map literal past 4,096 entries compiled entry n as
  entry n-4096.
- Different, all costs rather than limits: about 8,000 bindings in one
  function; for generators, with clauses and parts of one pattern past
  about 1,000 to 2,000; 300 type variables of one generic function; 5,000
  arguments of one call; about 2,000 lambdas each capturing a large frame;
  inspect, JSON and node descriptions of a type over 64 KiB; 65,534
  parameters.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (6m11.971s). Source 3,034,419 bytes/3022 functions, SHA-256
  2c2b326a22217e89dc82818b87ef80cfb9623cc13f9dcf0ee774bde37e35a156.
  A1=A2=A3 3,376,564 bytes, SHA-256
  b1b9594ad86fee338c55c9802e60fe076930743fb270cd9f549930253d216dfe.
  Traced self-build charges: A0 1,323,231,904 bytes, native 1,720,464,408 within 1GiB.

## 2026-11-19 — Memory reclamation; 871 of 872

- 871 of the 872 examples of the pinned references agree (unchanged).
- Memory is reclaimed (spec/alchem-memory.md, spec/memory-x86_64.s): a
  conservative, non-moving mark-sweep collector. A bitmap marks where
  values start; roots are the registers, every stack, the library's own
  mappings and the state block; a collection runs after 8 MiB of
  allocation or as much as was live. The compiler itself leaves it off, so
  its charges are unchanged. System.memory and System.collect_garbage.
- Gate harness/memory_reclaim.py: sixteen long-running programs under an
  address-space limit of image + 512 MiB with at most 64 MiB resident, all
  of which exhaust memory with the compiler before this entry.
- A library function's call of itself by module name is a jump (10,000
  tasks touched about 9 GB of stack; now 46 MB). Maps past 32 entries with
  integer, boolean, string or atom keys are persistent B-trees. Enum.uniq
  is no longer quadratic. Bitwise functions are the inline operators.
- Different: suite/calendar runs about 40 times slower than the pinned
  compiler's program (the date library reads a field list by calls);
  float to_string/parse have no fast path; <> in a loop copies the whole
  string; maps with float or tuple keys stay flat; frame slots are roots
  until the function returns; regex, String.split on whitespace and
  String.slice are slow.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m9.026s). Source 3,061,334 bytes/3082 functions, SHA-256
  02420401598fbbea4fe6144139f846361ad3767b0dd3da96f46d028289d40437.
  A1=A2=A3 3,406,294 bytes, SHA-256
  7f4aa7810481f996694e092c5d6795f7ab6705152397e2eb2e76bbf387d28a2a.
  Traced self-build charges: A0 1,333,030,184 bytes, native 1,732,747,176 within 1GiB.

## 2026-11-19 — JSON through type variables; 871 of 872

- 871 of the 872 examples of the pinned references agree (unchanged); the
  pinned tree's storage_test matches.
- JSON.encode!/encode/decode_as and inspect work on types that mention a
  type variable (spec/alchem-json.md, native-described.alc): a generic
  function that needs it takes a hidden description per type variable
  beside its comparators; node 35 is an indirect description, node 36 an
  inspect-only one. The "reads b from JSON" rejection is reproduced.
- &JSON.encode!/1, &JSON.encode/1 and &JSON.decode_as/1 compile.
- In test programs, assertions in def bodies and defimpl blocks print code,
  left and right as the pinned runner does.
- Different: a type of 255 or more parts given to a variable can be
  inspected but gives a run-time JSON error; polymorphic recursion
  compiles where the pinned compiler's Go build stops with an
  instantiation cycle.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (8m0.465s). Source 3,077,609 bytes/3145 functions, SHA-256
  21faa91ad026e641a06210c01f7a64c9e4b81a90ff35c9647f48e00ae7d9a688.
  A1=A2=A3 3,443,420 bytes, SHA-256
  3d359fb75414c5ffe389f224d4a892c1dc5c6d3057cefcfd1ce8fbdd2d7edfbb.
  Traced self-build charges: A0 1,345,262,248 bytes, native 1,751,231,120 within 1GiB.

## 2026-11-19 — Compile cost of long blocks; 871 of 872

- 871 of the 872 examples of the pinned references agree (unchanged).
- A block whose environment passes 1,024 bytes keeps its records in indexed
  stores and compiles each statement in a window holding only the records
  its text names (native-scope.alc): 10,000 bindings in 1.7 s and 340 MB
  (was exhausted at 3 GB; the pinned compiler takes 6.6 s). A function value
  in such a block captures only what its statement names.
- Heredoc lines with #{} are joined in doubling runs; tuple and variant
  pattern parts are parsed linearly, and {a, ^a} = ... is a compile error as
  in the pinned compiler; 2,000 nested fn[...] types are refused at once.
- Different (spec/source-capacity.md): with clauses past about 1,000 and
  with-else arms past about 500; 300 type variables of one generic function;
  list patterns past about 1,000 elements; tuple patterns past about 8,000
  parts; 5,000 call arguments.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m52.669s). Source 3,096,559 bytes/3230 functions, SHA-256
  152794b807127c564c71a7eda0ead59ed82928afc6969dd33e070749dc47fff7.
  A1=A2=A3 3,488,076 bytes, SHA-256
  04e5a64e2e23445755ad2e432718f052b9db9484b6d5582433f0a496ecc6cb6b.
  Traced self-build charges: A0 1,395,536,624 bytes, native 1,872,377,688 within 1GiB.

## 2026-11-19 — Nil forms and the test driver; 871 of 872

- 871 of the 872 examples of the pinned references agree (unchanged).
- The zero of a timed-out receive for an option, a result or a sum type is
  a nil that is none of their constructors, as in the pinned runtime: it
  inspects as nil, equals only itself, matches no constructor pattern, and
  a case or clauses over it fail with "no case branch matched"
  (spec/alchem-failures.md; harness/nil_forms.py, 260 programs). A pid that
  is a zero fails with "invalid or foreign PID".
- Kernel.x without a call, and calls that are no statements or give no
  value, are rejected as the pinned compiler rejects them (520 programs).
- tools/alchem-test.alc: the pinned command line's test (with every flag,
  fixtures and the --cover table), run, build, check and new, an Alchem
  program the native compiler builds (harness/test_driver.py, 49 runs in
  eleven projects).
- Different: a file that does not compile is reported with the compiler's
  one message (it has no diagnostics); -jobs runs files one after another;
  fmt, alx, lsp, syntax, doc and version have no counterpart.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m38.418s). Source 3,106,782 bytes/3244 functions, SHA-256
  dc20b887ced2ac228818d0893c712dfeefa04d47748cc405617b25424ad3e843.
  A1=A2=A3 3,502,044 bytes, SHA-256
  6e1d5d0cfb9828a48ae370294748c50d558b8db1892c954191a2d0c371c6d370.
  Traced self-build charges: A0 1,604,059,872 bytes, native 2,086,340,832 within 1GiB.

## 2026-11-19 — Owned accumulators and tree maps for every key; 871 of 872

- 871 of the 872 examples of the pinned references agree (unchanged).
- Owned accumulators (spec/alchem-memory.md, "Owned values"): in the
  accumulator of an Enum.reduce fn or a for ... reduce, and a string
  parameter a function hands on to itself, Map.put/update/put_new,
  MapSet.put and <> change the value in place where no program can tell,
  as the pinned compiler's owned folds and actor.Concat do; the bit is
  cleared at every other read and at each collection.
- Maps past 32 entries are trees whatever their keys; keys that are or hold
  a NaN stand after all others and are never searched for.
- The sweep no longer zeroes what dies; a range is zeroed when it is taken.
  Recursive functions clear slots of bindings that are over, and zero
  their frame at entry when they make values.
- Merge fixes: the fold-accumulator environment record is 53 (48 was taken
  by native-scope.alc); two source scans of native-memory.alc (gm_folded,
  gm_worded) went one byte per call and exceeded the seed-built compiler's
  call budget, and now go by halves.
- Different: appends and puts in other shapes still copy; a binding keeps
  its value until return outside a self-recursive function; there is no
  note that a value holds no addresses, so lists of megabytes are scanned
  and cleared; collections stop the program.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m50.576s). Source 3,129,441 bytes/3317 functions, SHA-256
  caf27f4b86a2bff6ed6dc1073744bd7ce1fa5b814f5158f107110b65528e7986.
  A1=A2=A3 3,556,599 bytes, SHA-256
  8a016d7068ba64d1d005184f4c5585c65609c360f75e03452b51c774eb5326ae.
  Traced self-build charges: A0 1,633,391,680 bytes, native 2,124,356,232 within 1GiB.

## 2026-11-19 — Library and code speed; 871 of 872

- 871 of the 872 examples of the pinned references agree (unchanged).
- Code (spec/alchem-speed.md, native-speed.alc): an integer literal is one
  instruction; a plain right operand leaves the left in RCX; division and
  remainder by a constant are a multiplication; integer comparisons in
  if/cond jump on the flags; Bitwise functions are the operators' code at
  the call; floor/ceil/trunc/round of a float are in line when it fits.
- Library: dates and times within 2**31 compute in plain arithmetic, struct
  to struct; String.split/1, split/2, replace/3, slice/at/first/last/reverse
  of ASCII text, and regular expressions go through the text once;
  Enum.sort of integers and strings uses the unstable sort; frequencies,
  uniq and group_by count through a table; MapSet.new, Map.merge and
  MapSet.union work in order; process links come out in one step.
- Gate harness/speed.py: 15 programs, 3,764 lines of pinned output.
- Different: restart forks to write a failing process's trace (about 15
  times the pinned time); list -- list is quadratic; regex groups re-run
  the match; a call of a function value per element costs a frame;
  date fields beyond 2**31 fail with integer overflow where Go normalises.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m43.059s). Source 3,205,926 bytes/3391 functions, SHA-256
  a012768c377b501bcea46f1e8c1840f151f810331049fc2e8dfee8e136a6509d.
  A1=A2=A3 3,616,846 bytes, SHA-256
  0e1c677a55fbe2e68df91be5b0745ef23f2398da0390de5f7071518a9f908e16.
  Traced self-build charges: A0 1,667,282,112 bytes, native 2,166,328,624 within 1GiB.

## 2026-11-19 — extern left out of the example count; 871 of 871

- `scripts/upstream-examples.py` no longer counts syntax/extern: `extern`
  binds a function to a Go function by name, a native program has no Go
  runtime to call, and `extern` is dropped in favour of running external
  processes. Every other example of the pinned references agrees: 871 of
  871. No compiler change; the last full verification (a156b77) stands.

## 2026-11-19 — kv through the test driver

- Every file of the pinned examples/kv checks as the pinned `alchem check`
  does (programs, the eight lib/ modules and the four test files), and its
  29 tests pass. `check` of a module with no main named the module by an
  absolute path that the bundler joined to its work directory; a test file
  was wrapped as an import. `build` of a file with no main gives the pinned
  `missing main/0`. Seven kv runs added to harness/test_driver.py (71 runs,
  all agreeing with the pinned command line).

## 2026-11-19 — One alchem executable

- `alchem` is one executable: the test, run, build, check and new commands
  (tools/alchem.alc, was tools/alchem-test.alc) with the bundler and the
  compiler inside, compiling by a call of `AlchemCompiler.nc_compile` rather
  than through /bin/sh, ALCHEM_COMPILER and ALCHEM_BUNDLE.
  scripts/build-alchem.py makes it (4.7 MB); build-native.sh installs
  build/native/alchem. Compiling the compiler's own source inside it gives
  A2's bytes in 8.0 s (A2 8.2 s) at a 70 MB peak (A2 2.1 GB): the collector
  runs there. test_driver's 71 runs pass through it with no compiler or
  bundler in the environment.
- Fixed in every traced program: zf_patch took twelve bytes of data in a
  call's arguments (a byte literal) for a routine's exit and rewrote them;
  `Enum.concat(x, b[1,191,87,0,0,0,184,60,0,0,0,15,5,2])` gave
  `0,1,233,91,...`. Data behind a literal's jump is now passed over
  (spec/alchem-failures.md).
- Twelve byte tests could leave 64 bits (they only wrapped in a compiler
  entry): nine of 8 to 14 byte differences and three of 4 or 5 differences
  of two-byte pairs, each split with nc_and. Every gate's compiles were run
  through A2 and the compiler inside alchem side by side: the same bytes. 891 programs (upstream
  examples, examples/, tools/) compile to the same bytes inside alchem as
  with A2; upstream examples 871/871.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m41s). Source 3,206,995 bytes/3394 functions, SHA-256
  a7ed76bcc27f0bf8cadb6889f215499466398793afda784cb78229a7a763e056.
  A1=A2=A3 3,618,989 bytes, SHA-256
  17d0c67fab112b9e93448103085985f5259e869d7b7a8d849807349822550d93.
  Traced self-build charges: A0 1,668,262,728 bytes, native 2,167,735,672 within 1GiB.

## 2026-11-19 — Pair tests within 64 bits

- The two-byte pair tests split (native-testing.alc, native-sigils.alc),
  found by running every gate's compiles through A2 and alchem side by side.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m45s). Source 3,207,009 bytes/3394 functions, SHA-256
  ae13001cd434c41e405ad2e1c5b0e222ea6848b52ef9e702cd39dcb19301acfd.
  A1=A2=A3 3,619,017 bytes, SHA-256
  d6ca817772a440c8b8fa927f67b6d0b614ab54c82603ed933f2c775d5c6b9642.
  Traced self-build charges: A0 1,668,300,120 bytes, native 2,167,788,304 within 1GiB.

## 2026-11-19 — Source files within 1 MiB; programs up to 16 MiB

- Bundlers (tools/alchem-bundle.alc, scripts/bundle-alchem.py) refuse a
  source file over 1 MiB as the pinned compiler does:
  `PATH: read source: source exceeds 1048576 bytes`; a file of exactly
  1,048,576 bytes is read. alchem's own build bundles its compiler module
  (one file of 3 MB) without the check.
- Programs up to 16,776,191 bytes (was 4,194,303): a value's flags
  (nw_mark, nx_impure) are a byte after its position instead of bits 23
  and 22 of it, so a position takes all 24 bits. Before any constant moved,
  the new layout compiled all 891 corpus programs and every gate's compiles
  to the same bytes as the compiler before it. Scan budgets, the trace
  word (position in the low 24 bits, tr_place), lines past a position in
  `for` and `try` (ty_record sets the high half when bit 31 is set), the
  compiler entry's read, the bootstrap bridge and seed IR V11 (both
  backends) follow. The pinned compiler runs five files of about 1 MB each
  (5 MB); the native one now does too (harness/modules.py, 168427), and
  refused it before. Issue #19 is to go past 16 MiB.
- source_capacity traces failures at positions past 4, 8 and 12 MiB and at
  16,776,191 bytes; grown_compiler grows the compiler's source to 16,776,191
  bytes (A0 5.1 GB, A2 6.3 GB, 27 s); compiler_entry and input read 16 MiB.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m52.284s). Source 3,207,138 bytes/3395 functions, SHA-256
  5b390f5dd79f0500212b381b933696db8aa557351ad3fd32aadbd3d4fb87620b.
  A1=A2=A3 3,619,479 bytes, SHA-256
  78f015eefde10da47727ea4dc6943d79cad700da46cf35fa7647c5b6a0e77eea.
  Traced self-build charges: A0 1,687,226,264 bytes, native 2,192,882,560 within 1GiB.

## 2026-11-19 — Library text in base64; alchem run with a socket for input

- `alchem run` tested the program's standard input and output with `:`, a
  special built-in: when /proc could not open one again (a socket), the
  redirection ended the shell with status 2 and no output, where the pinned
  command runs the program. The tests use `true` now; test_driver runs a
  program with a socket for input. A socket is still not passed through as
  the pinned command passes it (issue #20).
- The library's packed text is held as base64 byte literals `b"..."`
  (nl_coded_value; the seed adapter reads them as lists), 512 characters
  each: a seed-built compiler fails on a literal of 1,024. The compiler's
  source went from 3,207,138 to 2,019,287 bytes, its self-build from 8.0 s to
  5.3 s; alchem's source from 3.27 MB to 2.08 MB. All 891 corpus programs
  compile to the same bytes as before. Seed IR V11 holds 16 MiB of byte
  constants (was 4 MiB; bytes_limits checks both), which the compiler's source
  grown to 16 MiB needs now that most of it is data.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m35.174s). Source 2,019,287 bytes/3400 functions, SHA-256
  187ee650083c1f319987df6f5bd880bb9808d5bba40588fd9c5765e062ea3e76.
  A1=A2=A3 3,019,358 bytes, SHA-256
  0f787edad2a016d6b6ab10faf52a71c476d35ced2c529dc91cd2ba4f41fdd1f5.
  Traced self-build charges: A0 979,562,528 bytes, native 1,325,290,776 within 1GiB.

## 2026-11-20 — Linux ARM64 by translation; compilers collect

- Linux ARM64 (`-target linux/arm64` of the pinned compiler): the compiler
  builds x86-64 code and translates each function to ARM64
  (native-x86arm.alc); the runtimes are translated from spec/*-x86_64.s
  (scripts/x86-to-arm64.py). All 885 corpus programs that compile run under
  QEMU as their x86-64 builds do; TLS, coverage, the SIGSEGV guard and
  compiler entries work; the compiler built for ARM64 compiles itself under
  QEMU to the x86-64 compiler byte for byte. Floats are those of the pinned
  compiler's ARM64 programs (Go's fused multiply-adds, its ARM64 Log, Exp,
  Pow), but for which product of a sum of two Go fuses (spec/arm64.md).
- Compilers collect: a compiler entry reads its input through the reserve
  and grow hooks; the compiler's self-build went from 1.47 GB to 53 MB.
- library/JSON.alc reads type-description offsets as two unsigned bytes
  (an 8-byte read made them negative when the code after them had its top
  bit set).
- New gates: arm64 (encoders, runs, compiler entries, self-hosting under
  QEMU), x86_to_arm64 (both translations against native x86-64 under QEMU),
  arm64_floats (500 results against the pinned compiler's ARM64 and x86-64
  programs).
- One run before the recorded one failed in tls on the pinned compiler's
  own client ("a certificate required, 1.3": the server's TLS 1.3 alert
  raced its first write, "connection reset by peer"); the native client gave
  the expected result in that run, and the next run passed.
- Complete `bash scripts/verify-local.sh --with-source` exits0, no failures or
  skips (4m48.409s). Source 2,268,090 bytes/3693 functions, SHA-256
  2ea182b60bed135aa06c3f42eaa0caf3ea555e87f1f7eb590678d58fa6c2354c.
  A1=A2=A3 3,347,517 bytes, SHA-256
  b073530c5119fb8a9747bc14650546c77ac1fa16cd3c4cd0cacb51c1b523836f.
  Traced self-build charges: A0 1,163,551,528 bytes, native 17,179,803,648
  (address space: the native compiler now reserves the 16 GiB arena every
  program reserves, lazily, and collects; it stays near 53 MB resident).
