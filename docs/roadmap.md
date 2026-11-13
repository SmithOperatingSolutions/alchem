# Development Roadmap

## M1 — Native Hello World

- [x] Initialize Go module and CLI.
- [x] Define lexer tests including malformed tokens and source positions.
- [x] Implement lexer.
- [x] Define parser tests for valid and invalid modules/functions.
- [x] Implement AST and parser.
- [x] Add semantic checks and negative tests.
- [x] Generate Go for `IO.puts/1`.
- [x] Implement `alchem build <file.alc>`.
- [x] End-to-end test: build fixture, run binary, assert exact output.
- [x] Verify deterministic errors and no output executable on compilation failure.

**Acceptance:** `hello.alc` compiles to a native executable printing `Hello from Alchem!\n`; invalid source exits nonzero with useful diagnostics.

## M2 — Language fundamentals

- [x] Single modules, typed functions, immutable bindings and primitive types.
- [x] Checked arithmetic, boolean expressions and statement conditionals.
- [x] Typed lists/tuples, destructuring/case patterns and named-call pipes.
- [x] Typed maps, immutable collection operations, named callbacks and pattern guards.
- [x] Typed anonymous functions, immutable lexical captures and postfix invocation.
- [x] Deterministic map key/value/entry snapshots and immutable deletion.
- [x] Pin patterns and `List`/`Map` collection operations (reverse, take, drop, contains, sort, range, zip, merge).
- [x] Document evaluation order and error behavior for the implemented subset.

## Developer/project tooling

- [x] Relative file imports, qualified module linking and graph diagnostics.
- [x] Source runtime frames, structured compile diagnostics and canonical formatting.
- [x] Configurable output, targets, build/shutdown deadlines, tracing and race builds.

## M3 — Concurrency

- [x] Typed process IDs, bounded mailboxes, spawn/send/receive with deadlines and cancellation.
- [x] Immutable messages (shared, not copied), explicit capabilities, receive ownership and joined lifecycle cleanup.
- [x] Lifecycle, link/monitor, mailbox and supervisor race tests.
- [x] Measured 100,000-process experiment with a 512 MiB budget (1280 MiB on Windows) enforced by a test (see [benchmarks](benchmarks.md)).

## M4 — Fault tolerance

- [x] Actors, nested supervision trees, three restart strategies/policies, monitors and links.
- [x] Failure injection, restart intensity and shutdown tests; document fatal Go runtime/OS-write limits.

## M5 — Platform builds

- [x] Cross-compile CLI and generated Alchem binaries for Linux/Windows/macOS on AMD64/ARM64 with CGO disabled.
- [x] Native execution on all six OS/architecture combinations: Linux/Windows AMD64 and macOS ARM64 run in the required matrix; Linux/Windows ARM64 and macOS AMD64 run in the non-gating `native-extended` job. All six passed for PR #14.

## M6 — Benchmarking

- [x] Equivalent Go and Elixir baseline programs and a measuring harness.
- [x] Record hardware, versions, memory, latency, throughput, startup and binary size for Alchem and Go.
- [x] Record the Elixir baseline from the Benchmarks workflow.
- [x] Measure restart latency for Alchem and Go; the Elixir figure comes from the next Benchmarks workflow run.

## Since the milestones

Completed after M1 to M6, each with tests and documentation:

- [x] Seven measured optimization rounds: lock-free cancellation checks and sends, shared immutable messages, a ring-buffer mailbox, trimmed process and call bookkeeping, inlinable checked arithmetic and named callbacks, and constant-time `prepend`.
- [x] Maps as persistent hash tries: `put`, `Map.delete` and `Map.merge` share structure with the original.
- [x] Strings: `<>` concatenation, length, slice, contains, split, join, trim, case mapping, and conversion between integers and strings.
- [x] A clock: `Time.monotonic()` for measuring and `Time.now()` for reporting.
- [x] Program input: `System.argv()`, `IO.read_line()`, `IO.read_all()` and `File.read(path)`, bounded and UTF-8 checked.
- [x] Restart path: lock-free child lookup, `Process.sleep(0)` as a yield, and failure frames resolved on demand.
- [x] Automated update pull requests for the commit-pinned CI actions.
- [x] Hosted-runner benchmark table with all seven workloads and Elixir.

## Next

Planned and not started, in intended order. Each item names what "done" means.

### 1. Program output

Programs can read input, write to standard output with or without a newline, write to standard error, write files, and choose their exit status.

- [x] `IO.write(text)`: standard output without a trailing newline.
- [x] `IO.warn(text)` and `IO.puts(:stderr, text)`: a line on standard error.
- [x] `System.halt(code)`: end the program at once with a status from 0 to 255.
- [x] `System.stop(code)`: end the program with a chosen status after orderly shutdown.
- [x] `File.write(path, text)`, with `File.append`, `File.remove`, `File.list` and `File.exists`. They return `result` values rather than a flag and write in place, not through a temporary file; whether to replace atomically is still open.
- Done when: a fixture and a compiled-program test cover each operation, including a write that fails, and the specification states buffering and ordering between processes.

### 2. Faster map updates

On the hosted runner the `state` workload takes 119 ms in Alchem against 78 ms in Elixir once Elixir's startup is subtracted. Go, mutating in place, takes 17 ms.

- [x] Profile `MapPut` on the `state` workload before changing anything: garbage collection of copied slots dominated.
- [x] Store entries and children in separate arrays (a CHAMP trie), so a path copy moves subtree pointers and shares unchanged entries: inserts 34% faster with 61% less allocated, the `state` program 45% faster. Recorded in `benchmarks.md`.
- [ ] Not taken yet: a flat array form for maps of up to about eight entries, and a single allocation per node.
- Done when: `BenchmarkMapPutGrowing` and the `state` workload improve, `hamt_test.go` still passes including the forced-collision runs, and the result is recorded in `benchmarks.md`.

### 3. Benchmarks that measure themselves

Now that `Time.monotonic()` exists, the workloads can time their own phases instead of relying on whole-process wall time.

- [x] Report per-phase times from inside each workload, so startup no longer has to be subtracted and Elixir comparisons are direct.
- [x] Replace the polling in the `restart` workload's Elixir baseline: each new worker announces itself, with a monitor on the one crashing.
- [x] Report a distribution (minimum, median, 99th percentile) for round-trip and restart latency.
- [ ] Re-record the hosted-runner table with the Benchmarks workflow.
- Done when: the harness prints phase times for all three languages and the hosted-runner table is re-recorded.

### 4. Remaining gaps against Go

Ratios on the hosted runner are 1.5 for processes, 1.7 for messaging, 1.6 for computation and 1.5 for list building. What is left is mostly the cost of guarantees, so each of these needs a measurement first.

- [ ] Messaging: a receive that parks takes the mailbox lock twice; look for a single-lock path.
- [ ] Processes: 309 MiB against 270 MiB for 100,000; check the size of the process record and whether the wake channel can be created on first park.
- [ ] Computation: skip call-depth tracking for functions that cannot be part of a call cycle, with the soundness argument written down.

### 5. Housekeeping

- [x] Shorter CI: the race detector on the concurrent packages for pull requests and on every package nightly, Go's build cache kept between runs, and the slowest tests run in parallel.
- [x] Delete the merged working branches on GitHub.
- [ ] Decide whether `native-extended` should join the required CI gate now that it has passed on every pull request since #14.

## Working locally

A development machine with Go 1.23 or newer runs everything except the Elixir baselines; with Elixir 1.18 on OTP 27 on `PATH` the harness measures all three languages.

```sh
go test -race ./...                        # full suite; about a minute
go vet ./... && gofmt -l .                 # both must be clean
go test -race -count=20 ./compiler/actor   # after any runtime concurrency change
go test -run '^$' -bench . -benchmem ./compiler/actor
go run ./benchmarks/harness -runs 7        # Alchem, Go and, when installed, Elixir
go run ./cmd/alchem test tests/fixtures    # every fixture through the CLI
```

Run the harness before and after a performance change on the same machine and record both; figures from different machines are not comparable. The **Benchmarks** workflow remains the reference for the published table.

## M7 — Usable programs

- [x] Go interop: `extern` bindings to standard-library, required-module and project-local Go functions, with checked conversions.
- [x] Implicit returns and multi-clause functions with guards and structural exhaustiveness checking.
- [x] Floats, string concatenation and interpolation, and `String`/`Integer`/`Float` functions.
- [x] Structs, sum types, `option` and `result`.
- [x] Generic functions, structs and sum types.
- [x] `File`, `System`, `Time` and `IO` functions and the typed request/reply `Server`.
- [x] Private functions and versioned remote packages.
- [x] `if` and `case` as value-producing expressions.
- [x] Restartable supervised servers.
- [x] `extern` checked against Go type information by `alchem check`; bindings to methods, opaque Go types, structs, variadic functions, callbacks and multiple results.
- [x] Equality on type variables as an inferred requirement on callers.
- [x] `alchem.lock` and `--locked`.
- [x] Servers as named children of a user `Supervisor` (`Supervisor.server`), registered before `Supervisor.start` returns.
- [ ] Bindings to generic Go functions and to Go interfaces implemented in Alchem.

## M8 — Elixir-style library and testing

- [x] `fn x -> ... end` and `&(&1 ...)` with inferred types, ranges, `in`, `++`, `--`, `**`, `cond`, `raise`, names ending in `?` and `!`.
- [x] `Enum` and lazy `Stream`, including chunking and `File.stream!`, over lists, maps, sets, ranges and streams.
- [x] `List`, `Map`, `MapSet`, `String`, `Integer`, `Float`, Kernel functions, `Bitwise`, `Base`, `Path`, `Regex`, `Task`, `Agent`, `JSON`, `inspect`, and more of `File`, `System` and `IO`.
- [x] Test files with `test`, nested `describe` and `setup`; seeds, `--only`, `--trace`, `--max-failures` and line coverage.
- [x] `#` comments, `try`/`rescue`/`after`, `with`, `for` comprehensions, sigils and `=~`.
- [x] `Date`, `Time`, `NaiveDateTime` and `DateTime`.
- [x] Test context with `setup_all`, tags and doctests.
- [ ] Everything listed under "Next" in [Elixir parity](elixir-parity.md).

## M9 — Releases

- [x] `alchem version`, stamped by release builds and by `go install`.
- [x] Builds without an installed Go: the pinned release is downloaded once, checked against recorded SHA-256 sums, and run with its own `GOROOT`.
- [x] Release workflow: a `v*` tag builds archives for six targets with checksums, checks that the Linux binary builds a program without Go, and publishes a GitHub release. See [releasing](releasing.md).
- [x] Apache-2.0 license, shipped in every release archive.
- [x] The shell is `alchem alx` and documentation examples use `alx>`, so nothing is named after Elixir's tools.
- [x] `tools/provenance` checks the documentation for passages shared with Elixir's; see [provenance](provenance.md).
- [x] Tag `v0.1.0`.
- [ ] Install script and package-manager formulas (Homebrew, Scoop) that point at the release archives.
- [ ] Sign or notarize the macOS and Windows binaries.

## M10 — Building on Alchem

- [x] `WebSocket`: upgrading an `HTTP.serve` request, a client with `ws://` and `wss://`, text and binary messages, pings and the closing handshake handled by the runtime, active mode and message size limits.
- [x] `Crypto`: secure random bytes, hashes, HMAC and constant-time comparison.
- [x] `~h` HTML templates that escape what they interpolate, and the `Markup` type.

## Workflow

For each task: define acceptance criteria → failing test → minimal implementation → full regression suite → review → commit.

