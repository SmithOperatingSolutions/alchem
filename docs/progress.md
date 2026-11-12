# Alchem progress

Updated: 2026-11-10

## Merged baseline

PRs #1–#11 established the typed functional core, collections/maps and closures, guarded patterns, source locations, sorted traversal, bounded builds/fixtures and native/cross-platform CI.

## Integrated modules, runtime, fault tolerance and tooling

The integrated PR implements the requested areas together, with separate commits for project loading, runtime/source failures, tooling and acceptance hardening.

- Relative multi-file imports, qualified calls/references, deterministic dependency/namespace validation and per-file errors.
- Typed PID capabilities, bounded FIFO mailboxes, immutable data messages, receive ownership, deadlines/cancellation, constant-stack typed state loops, process joins, events/monitors/demonitors, links/unlinks and exit trapping.
- Owned/nested supervisors, permanent/transient/temporary policies, one-for-one/one-for-all/rest-for-one strategies, rolling restart intensity, replacement identities and joined tree shutdown.
- Recoverable worker failures and Alchem runtime frames across imported/anonymous functions, with root rendering and retained worker reports.
- Canonical idempotent formatting, check-only/JSON diagnostics, explicit output/target/build/shutdown/race/trace options, interrupt propagation and safe staged publication.

Local evidence includes the complete race suite and vet, repeated runtime race/lifecycle runs, exact source diagnostics, formatter grammar roundtrips, invalid/canceled build preservation, a race-instrumented two-file supervised echo program, and six-target compilation of that integrated example. The final PR records the native Linux/Windows/macOS and cross-build CI results for its head. See `integration-acceptance.md` and the module/runtime/tooling specifications for the concrete acceptance contracts.

## Review corrections and roadmap completion

PR #13 fixed formatter, frame, equality and shutdown defects and bounded source size, nesting, import graphs and call depth. The following work adds pin patterns, `List`/`Map` operations, a 100,000-process memory budget enforced by a test, Go and Elixir baseline programs with a measuring harness, recorded Alchem and Go results, a non-gating native job for the three remaining OS/architecture pairs, and written regression testing standards. All six OS/architecture pairs have since passed natively and the Elixir baseline is recorded. Restart latency has since been measured.

## Performance work

Seven measured optimization rounds followed (see `benchmarks.md`): the runtime lock was taken off the per-statement and per-message paths, messages became shared immutable values, the mailbox became a ring buffer with one wake channel per process, process bookkeeping and call tracking were trimmed, checked arithmetic and named callbacks were made inlinable, and lists gained a representation with constant-time `prepend`. On a hosted runner with all rounds merged, Alchem is within 1.4 to 1.7 times Go on the five workloads measured there and ahead of Elixir on each.

Measuring restart latency then exposed three costs in the crash-and-restart path, each fixed: looking up a supervised child took the runtime lock, so a caller polling for a replacement held up the supervisor creating it; there was no way to yield, so a polling loop occupied a processor; and every failure resolved its stack frames even when nobody read them. A restart cycle went from about 76 to about 10 microseconds locally, against about 2.3 for a hand-written Go supervisor.

## Current state

As of 2026-11-10, `main` holds everything through PR #21. The six milestones are complete and CI runs natively on all six OS/architecture pairs for every pull request.

Open work is listed in order under "Next" in `roadmap.md`:

1. Program output: writing without a newline, standard error, exit codes and writing files.
2. Faster map updates, the one workload where Elixir is ahead once its startup is subtracted.
3. Benchmarks that time their own phases with `Time.monotonic()`, including a fairer Elixir restart baseline.
4. The remaining 1.5 to 1.7 times gaps against Go, each needing a measurement first.
5. Housekeeping: test time under the race detector, the merged branch, and the CI gate.

How to run the suite, the micro-benchmarks and the three-language harness locally is under "Working locally" in `roadmap.md`. The Elixir baselines have so far only run in CI; `benchmarks/elixir/restart.exs` and `state.exs` in particular were written without a local Elixir and should be read once with one available.

Conventions that have held throughout: each change lands with tests that would have failed before it, performance claims come from the harness with the environment recorded, behaviour changes are stated in the specification in the same commit, and pull requests are rebase-merged after the required `test` check passes.

Known physical/runtime limits are explicit: goroutines share an address space; cancellation is cooperative at generated boundaries and runtime waits; fatal Go runtime errors and blocked OS writes do not acquire BEAM isolation. Maps now update in logarithmic time through a persistent hash trie, and the language has string operations, integer conversion and a clock. Programs can read their arguments, standard input and files. On a hosted runner with all of this merged, Alchem is within 1.5 to 1.7 times Go on processes, messaging, computation and list building, and ahead of Elixir on every workload as a whole program. The open items under "Next" in `roadmap.md` are richer output and faster map updates. Distributed nodes and package registries remain out of scope.

## Usable programs

Go interop (`extern`, `require`), implicit returns, multi-clause functions, floats, string interpolation, structs, sum types, `option`/`result`, generics, additional `String`, `Float`, `File`, `System` and `IO` functions, the typed `Server` behaviour, private functions and versioned remote packages are implemented with fixtures (`clauses`, `text_numbers`, `types`, `stdlib`) and compiler tests, including dependency and package resolution against a file-based module proxy. The minimum Go version is 1.27. `if`/`case` values, supervised servers, type-checked Go bindings (methods, opaque types, structs, variadics, callbacks), equality on type variables and the lock file followed. Fetching from the public module proxy is covered by an opt-in test (`ALCHEM_NETWORK_TESTS=1`). A line that starts with `(`, `[` or `-` now begins a new statement, and string ordering comparisons, previously rejected, are accepted.

## Elixir-style library and testing

The language gained inferred anonymous functions and captures, ranges, `in`, `cond`, `raise` and the list and power operators; the library gained `Enum`, lazy `Stream` with chunked file reading, and some twenty further modules (358 function signatures, listed in the generated `library-reference.md`); and `alchem test` gained test files with nested `describe`, `setup`, seeds and line coverage. The library runtime is tree-shaken per program, so a program that uses none of it builds and links as before. `Float.round` now returns a float and `Float.trunc` is gone, in favour of the Kernel `round` and `trunc`. What is still missing, in order, is under "Next" in `elixir-parity.md`.

## Control flow, dates and test context

Comments, `try`/`rescue`/`after`, `with`, `for` comprehensions, the regex, word, string and calendar sigils, the four date and time structs, and test context, tags and doctests followed. Rescuing restores the call depth a failure skipped, and a request to stop a process is never rescued. Still to do is under "Next" in `elixir-parity.md`.

## Documentation in the compiler

Heredoc strings and `@moduledoc`, `@doc` and `@typedoc` replaced comments as documentation. Every library function now carries a description and examples beside its signature, and the language has a set of syntax topics; the tests run every example and reject an undocumented function. `alchem syntax`, `alchem doc`, `alchem agent-guide` and `alchem agent-install` serve that material, and `alchem docs` writes the reference pages from it. A test or task may now call `Process.self`, choosing its mailbox type on first use.

## Standard library benchmarks and the first optimisations

A suite of 193 cases, each written in Alchem, Elixir and Go, now measures the library (see `stdlib-benchmarks.md`). Its first run found Alchem faster than Elixir in 123 cases. The slowest were then changed in the runtime: strings grown by `<>` are extended in place, maps are built and merged through a builder that changes its own nodes in place, map traversal collects values with keys and radix-sorts integer keys, rescued failures no longer record a stack, list subtraction counts, sorting no longer goes through reflection, and zip and the positional list updates work on lists directly. JSON encoding, the set operations and several list operations followed. Alchem is now faster in 142 cases; what remains is listed on that page.

## Parity: defaults, clauses, comprehension options and more library

Default arguments, anonymous functions with clauses, the `into:`, `uniq:` and `reduce:` options of `for`, interpolating sigils and regular expressions as arguments to `String.replace` and `String.split` closed most of the language list in `elixir-parity.md`. The library gained `Enum.into`, `chunk_while`, fallbacks for `Enum.min` and `Enum.max`, `Calendar.strftime`, `URI` encoding and query strings, and `Version.parse` and `compare`; tests gained `on_exit`, `capture_io`, `assert_receive` and `refute_receive`. Float text and rounding to a precision now give Elixir's results. Each addition carries its documentation and checked examples, so `alchem doc`, `alchem syntax` and the generated reference pages describe it.

## Receive assertions take patterns

`assert_receive(self, pattern)` and `refute_receive(self, pattern)` are statements that match a pattern, with an optional guard, against the test's mailbox: the first matching message is taken and the pattern's names are bound, as in ExUnit. The runtime gained a selective receive that leaves the other messages in place.

## The rest of the parity list

`unless`, the `~c` sigil and sigils a program defines; test files compiled and run in parallel; `Duration`, `shift` and time zones for `DateTime`; `URI.parse`, `Version.match?`, `Logger` and `OptionParser`. The cached runtime package was measured instead of built: tree-shaking already keeps the library's cost under a tenth of a second per build.

## Atoms, keyword lists, protocols and ports

Atoms became a type, `[name: value]` a keyword list with a `Keyword` module, and `defprotocol` with `defimpl` gives functions that are chosen by the type of their first argument when the program is compiled. `Port` runs an external program and delivers its output as messages. Macros, distribution between nodes and Hex packages are recorded in `elixir-parity.md` as things the design cannot do, with the reasons.

## Nodes and macros

Programs connect as nodes and their processes exchange messages by copying: the compiler generates an encoder and decoder for each message type, a process is found by a registered name, and a handle inside a message lets the receiver reply. Macros are templates, with `quote`, `unquote`, `do` blocks, hygiene and `use`. Both had been recorded as impossible; what remains impossible is narrower, macros that run code while compiling and Hex packages.

## Remote monitors and streams between nodes

`Process.monitor` works on a process of another node, reporting its exit or the loss of its node. A stream is offered to other nodes with `Stream.publish` and read with `Node.stream`, which pulls it a chunk at a time from the node that holds it. A fault in ports was fixed on the way: stopping a port's owner now ends the program, as documented.

## Encrypted node connections

Connections between nodes use TLS 1.3, and the cookie proof is tied to the TLS session so that it cannot be relayed. `encrypted: false` turns encryption off for a trusted network; nodes connect only when their settings match. The node code moved into a package of its own: adding distribution had made every program about 400 KB larger whether or not it used nodes, and now only programs that use nodes link networking and encryption.

## Toward a useful language

The gaps that kept Alchem from long-running services were closed: servers can name themselves, schedule their own requests and hear of other processes' exits; `Registry` and `DynamicSupervisor` were added; `defexception`, `throw` and `try ... else` complete error handling; and `TCP` and an `HTTP` client and server let programs talk to the network. The tooling gained `alchem run`, `alchem new`, an interactive shell (`alchem alx`) and a language server (`alchem lsp`).

`examples/kv`, a Redis-like server of about 1,650 lines with tests over real connections, was then written to find what a real program runs into. It turned up list construction with `[head | tail]`, functions overloaded by arity with `&name/arity` references, imports after `@moduledoc`, `IO.puts(:stderr, ...)`, `System.tmp_dir!`, builtin names such as `get` as variants, clearer errors for reserved function names, and a formatter that wrote every operator in parentheses and split every short `fn` over three lines. All of those were fixed. Two differences from Elixir stayed for a while: heredocs were literal, and library functions overloaded by number of arguments only. Both are gone; see the next section.

## Completing the parity list

What the parity table still listed as missing was then done, with a fixture or test for each part and a runnable example for every new function:

- **Servers and supervision:** `Server.mailbox` (what `handle_info` receives) and `Server.continue`; `Process.send_after` to a name. `Registry` gained partitions, entries with process ids, `match`, `select`, `dispatch`, `update_value` and metadata. `DynamicSupervisor` gained `max_children`. `Task.async` is now linked to its caller, with `Task.start`, `start_link` and `Task.Supervisor` beside it. Agents take names and timeouts.
- **Networking:** active TCP sockets that deliver `TCP.Event` messages; packet framing by line or length header; UDP. HTTP gained streamed bodies both ways, timeouts and size limits, HTTPS serving, and routing by path pattern.
- **Distribution:** `Node.serve` with `call` and `cast`; global names; reconnection; links to processes of other nodes, through a new exit frame.
- **Testing:** property testing with `check all` and shrinking generators; tags with values.
- **Library:**
  - Strings count grapheme clusters, and `String.normalize` has tables generated from Unicode 17.
  - Ranges are `Range` structs.
  - Maps and sets take float and tuple keys.
  - Files can be opened as handles.
  - Any value encodes as JSON.
  - Also added: the `Version` struct; Elixir-style `OptionParser`; Logger metadata and handlers; and port modes.
  - The remaining smaller functions of `Enum`, `Map`, `Keyword`, `String`, `File`, `System`, the calendar types and `URI`.
- **Language:**
  - Heredocs read escapes and interpolation, with `~S"""` for literal text.
  - Library functions overload by argument type, and by a function literal's arity.
  - New syntax: `f.(x)`, `&String.length/1`, bitwise operators, `elem`/`put_elem`, struct field defaults, and `0x`/`0o`/`0b` and `1_000` literals.
  - A `for` whose body ends in an effect gives `{}` for each element instead of being an error.

Some of this changes behaviour:
- `compare` returns `:lt`, `:eq` or `:gt`.
- `System.cmd/2` returns standard output only.
- `Version.parse` returns a struct.
- Calendar values print as sigils.
- A failing `Task.async` ends its caller, as in Elixir.

What the table still lists as missing is either impossible here, such as macros that compute and Hex packages, or follows from static types, such as heterogeneous keyword lists and dynamic `apply`.

`go run ./tools/coverage` measures coverage across the compiler, the tools and the runtime that compiled programs carry, and CI holds it above a minimum.
