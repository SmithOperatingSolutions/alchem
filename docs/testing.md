# Dual-language testing strategy

## Regression testing standards

Every change to the compiler, runtime or tooling meets these before it merges:

1. **A failing test first.** A defect fix adds a test that fails on the old code and names the behaviour it protects. A feature adds tests for its acceptance criteria.
2. **Positive and negative coverage.** New syntax or operations get type-check tests for accepted and rejected programs, with the expected diagnostic text.
3. **Exact runtime diagnostics.** Anything that can fail at runtime has a case in `TestRuntimeSourceDiagnostics` asserting the file, line, column and message.
4. **An executable fixture.** User-visible language behaviour is exercised end to end by a program in `tests/fixtures` with exact expected output. Fixtures are also the formatter's round-trip corpus, so every new form is automatically checked for idempotent, program-preserving formatting.
5. **Bounds are tested at the bound.** Each limit (source size, nesting, chains, modules, call depth, range size, memory budget) has a test that crosses it and asserts the diagnostic or failure.
6. **The whole suite, not the touched package.** `go test -race ./...`, `go vet ./...` and `gofmt -l .` are clean locally, and the required CI gate is green on Linux, Windows and macOS before merge.
7. **No weakened tests.** A test is never skipped, loosened or deleted to make a change pass; if behaviour changes on purpose, the test and the specification change together in the same commit.
8. **Measurements are reproducible.** Performance claims come from `benchmarks/harness` with the environment recorded, and budgets are enforced by tests rather than by prose.

## Current executable tests

Go's test runner validates compiler behavior and builds/runs Alchem fixture programs. Run `go test ./...`, `go test -race ./...`, and `go vet ./...`. The shared `tests/fixtures/hello.alc` and `hello.stdout` form the initial behavioral contract.

## Executable fixture contract

`alchem test <directory>` discovers `.alc` files in sorted order. Ordinary programs require a matching `.stdout` file; `.test.alc` programs check exit status and assertions. An optional `.exitcode` file declares the expected nonnegative exit status (default zero).

Each executable runs with its temporary build directory as cwd, a 30-second execution deadline, and at most 1 MiB retained per output stream. Exceeding either stream limit fails the fixture. Compilation uses the Go toolchain with a two-minute default deadline; library callers may supply their own context. Failed or canceled builds leave existing destination files unchanged. Temporary cwd isolates relative files; this is not a security sandbox.

Stdout and stderr are captured independently. An optional `.stderr` file checks stderr exactly. Successful fixtures without this file require empty stderr. Expected failing assertion fixtures without it must contain `assertion failed` on stderr; known language failures now emit stable Alchem locations instead of Go panic traces. Ordinary `.stdout` checks never include stderr.

Assertions accept typed boolean expressions, including comparisons, bindings and function calls. Test blocks remain deferred.

## Parallel validation plan

1. Add a Go-side contract test and fixture for each language feature.
2. Implement the feature, and verify its compiled output.
3. Add executable Alchem-side assertions once functions, comparisons and test syntax are implemented.
4. Run Go and Alchem suites independently in CI, with matching expected outcomes.
5. For cross-backend or differential tests, compare observable behavior and diagnostics, accounting for intentional platform differences.

Use explicit test timeouts and bounded resources for concurrency cases. Keep test results separate so failures cannot be masked.


## Combined language regressions

`language.alc` verifies arithmetic precedence/associativity, negative division/remainder, short-circuiting around zero division, nested conditionals and scopes, typed forward and recursive calls, and left-to-right argument evaluation with visible output. Go integration tests compile programs that must fail at runtime for overflow or zero division. Parser/semantic tests reject type, arity, scope and return-path violations.

Build cancellation tests use a fake Unix toolchain process, verify deadline errors with `errors.Is`, preserve an existing output file, and check staged-file cleanup. The shell-specific test is skipped on Windows. Context cancellation terminates the direct child and bounds pipe waiting; descendant-process isolation is not guaranteed.

## Collections and runtime locations

`collections.alc` combines nested list/tuple values, access and deep equality, empty-list context, recursive list processing, tuple returns, exact/head-tail/nested destructuring, wildcard/literal matching, boolean/list/tuple cases, and pipe chains. Visible output verifies one-time case subjects and tuple-length arguments plus left-to-right pipe argument evaluation.

Go integration tests assert exact `source.alc:line:column: message` diagnostics and exit code 2 for assertions, overflow, division, negative/out-of-range/empty-list access and failed nested matches. A separate called-function test ensures locations identify the failed operator inside that function. Temporary source paths containing spaces exercise safe embedding. Parser/semantic tests cover invalid collection types, heterogeneous values, index restrictions, repeated/shadowing pattern captures, scope escape, non-exhaustive cases, unreachable arms and invalid pipe targets.

## Operations, callbacks, maps and guards

`operations.alc` verifies immutable prepend/concat, ordered map/filter/reduce, empty callbacks, heterogeneous accumulator/result types, function-valued bindings/parameters/returns, callbacks stored in maps, map copy-on-update and structural equality, eager defaults, deterministic key/value evaluation and dynamic collisions, partial/nested map patterns and guarded case fallthrough. Visible output checks callback/constructor order and skips guards on failed patterns.

Negative semantic tests cover callback types/arity/results, function-containing equality, invalid map types and keys, duplicate literal/pattern keys, pattern captures, guard scope and exhaustive return paths. Exact integration diagnostic checks include missing map keys, failed map matches and arithmetic errors in a guard. The existing fixtures remain regression coverage for separate declared-function and local-binding names.

## Closure regressions

`closures.alc` compiles inline map/filter/reduce callbacks, returned/nested closures, separate factory captures, immutable map captures after copy-on-update, closures stored in lists/maps, zero-argument/immediate invocation, and closures inside guards. Visible output asserts that a returned callee runs once before its argument. Negative parser/semantic tests cover result types/paths, duplicate/shadowing parameters, undefined/forward/self references, scope escape, noncallable values and function equality. Exact integration assertions retain the arithmetic source location inside an anonymous callback.

## Deterministic traversal regressions

`map_traversal.alc` checks sorted keys/values/entries for integer, boolean and string keys, integer bounds and lexical prefixes/Unicode strings, empty maps, snapshot stability, immutable deletion with present/absent keys, nested/function-valued entries, and entries-to-filter/map pipelines. Visible output verifies one map evaluation per operation and map-before-key evaluation for deletion. Parser/semantic tests reject nonmaps, wrong arity, wrong deletion key types and incorrect annotated result types.

## Platform CI

Pull requests and pushes to `main` run native race/integration tests, `go vet`, and an actual CLI build/run smoke test on Ubuntu, Windows and macOS using Go 1.27.x. Ubuntu also runs current stable Go. Runner architecture and exact Go version are printed in job logs; the matrix does not claim every architecture is executed natively. The Unix shell fake-toolchain test remains skipped on Windows.

A separate Ubuntu job cross-compiles the CLI and `examples/closures.alc` for Linux, Windows and Darwin on AMD64 and ARM64 with `CGO_ENABLED=0`. Its artifact contains target binaries retained for seven days. Cross-build success verifies compilation, not execution or race behavior on those targets. Native Go tests keep their normal CGO configuration for race support.

The final `test` job preserves the existing aggregate check name and succeeds only when every native matrix leg and the cross-build job succeed. The matrix uses `fail-fast: false` so one platform does not hide failures on another. Workflow/job deadlines and per-build/per-fixture deadlines bound separate parts of the work.

`.gitattributes` enforces LF checkout for text, keeping exact `.stdout`/`.stderr` fixture comparisons consistent on Windows as well as Unix. `artifacts/` is ignored locally. This workflow does not publish releases or deploy binaries.

## Integrated module, actor and tooling acceptance

`compiler/project_test.go` covers qualified imports/references, deterministic cycle/missing/duplicate/visibility/entry diagnostics, imported error positions, cross-file runtime frames, and the two-file supervised echo example built with the race detector. Process fixtures exercise typed self/spawn/send/receive, monitor/link events, cancellation and joins; supervisor fixtures exercise replacement and intensity shutdown.

`compiler/actor` race tests cover shared message delivery and receive ownership, queue bounds/FIFO/dead behavior, blocked sender wakeup, monitors/demonitor flushing, trapped/untrapped links, unlinking, concurrent lifecycle cleanup, every restart strategy and policy, rolling windows, nested linked supervisors and subtree shutdown. Repeated race runs stress these transitions. These verify the defined cooperative runtime; fatal Go runtime failures and blocked OS writes are explicit limits.

Formatter tests parse every fixture, verify idempotence and re-check the resulting program. CLI tests cover formatting check/write and invalid-batch preservation, structured errors and invalid options. Build tests cover no-trace output, successful executable replacement, failed/canceled build preservation, staged-file cleanup and deterministic invalid-source errors.

Native platform jobs additionally check and format-check `examples/system`, build it with the CLI and run it. Cross jobs compile that integrated module/actor/supervisor executable for all six targets, replacing the earlier closure-only smoke program. Final PR CI evidence is required before declaring the integrated acceptance complete.

## Pins, collection operations and scale

`pins_lists.alc` exercises pin patterns in tuples, lists, maps and `case`, and every `List`/`Map` operation including empty, oversized-count and piped uses. `compiler/syntax/pins_lists_test.go` covers accepted programs and each rejection diagnostic. `TestRuntimeSourceDiagnostics` asserts the positions of failed pins, negative counts and oversized ranges. `TestHundredThousandProcessesWithinMemoryBudget` enforces the 512 MiB budget described in [benchmarks](benchmarks.md).

## Extended native platforms

The `native-extended` CI job runs the unit suite, every fixture and the supervised example natively on Linux ARM64, Windows ARM64 and macOS AMD64, first asserting the runner's actual `GOOS/GOARCH`. It is not part of the required gate, so results on those three platforms are evidence only for runs where the job completed; it first passed on all three for PR #14.

## Performance regressions

`compiler/actor/bench_test.go` benchmarks the cancellation check, spawn/join, request/reply and structured-message paths; run them before and after any runtime change and record the comparison. `TestEqualityUsesCheapestCorrectForm`, `TestNamedCallbacksBecomeDirectLoops` and `TestLeafFunctionsSkipCallTracking` pin the shape of generated code that the optimizations depend on; `TestArithmeticBoundaryResults` and `TestBusyProcessesAreCancellable` guard the behaviour those shapes must preserve. Optimizations to locking are accepted only with the race suite repeated (`go test -race -count=20 ./compiler/actor`).

## List representation

`list_sharing.alc` checks that prepending twice to one list, prepending to a tail, a `take` or a `drop`, and prepending to an empty list all leave every other view intact, that callbacks run in list order, and that two processes prepending to the same shared list each get a correct result. `TestSharedListPrependsAreRaceFree` builds that fixture with the race detector where the toolchain has one and runs it twenty times. Every other collection fixture exercises the same representation through literals, patterns, indexing, pipelines and map snapshots.

## Restart path

`TestChildLookupWhileRestarting` crashes a supervised worker 200 times while polling for each replacement, asserting that a lookup never returns an already replaced PID, that the replacement is ready to receive, and that the retained report is intact. `BenchmarkCrashAndRestart` tracks the cost of one cycle.

## Map representation

`compiler/actor/hamt_test.go` checks the map against a Go map through thousands of random puts, overwrites and deletes, asserting that every earlier version is unchanged, and repeats the run with hash functions that collide partially and completely so the collision buckets are exercised. It also covers string and boolean keys, absent keys and two processes extending one shared map. `map_sharing.alc` checks the same properties from the language: old versions after `put` and `Map.delete`, large maps, sorted snapshots, merging, dynamic duplicate keys, nested values, patterns and maps sent between processes. `TestEqualityUsesCheapestCorrectForm` asserts that generated code contains no reflective comparison.

## Strings and time

`strings_time.alc` covers concatenation, code-point length and slicing including multi-byte text and out-of-range bounds, contains, split and join round trips, trimming, case mapping, integer formatting and parsing at the 64-bit limits and for malformed input, and both clocks. `compiler/syntax/strings_time_test.go` covers accepted programs, each rejection diagnostic and the precedence of `<>`. `TestRuntimeSourceDiagnostics` asserts the positions of negative slice bounds and an empty separator.

## Program input

`compiler/input_test.go` runs compiled programs with real arguments, standard input and files: arguments with spaces and non-ASCII text, lines with both line endings and an empty line, the remainder of input, end of input, and a file's contents. It asserts the limits at and just past the bound (a 1 MiB line, 16 MiB of input), invalid UTF-8 on each path with a source location, and that `File.read` reports a missing file, a directory, an oversized file and non-text data as an `error` with a reason that tells them apart. `input_absent.alc` covers a program started with no arguments and no input.
