# Gen, the assertions, and test files

## Gen

All seventeen `Gen` functions and the type `generator[a]`, with the pinned
runtime's values: under `ALCHEM_SEED` a generator gives here, value for
value, what it gives upstream, and a failing property is reported with the
same smallest value after the same number of shrinking steps.
`harness/gen.py` holds 47 programs with the pinned compiler's output
frozen in (every generator under four seeds, one of them past 2**63; 23
failing properties; `ALCHEM_PROPERTY_RUNS`; generators as annotated values,
parameters and results; the six failures of a generator that cannot be
made) and 13 programs the pinned compiler rejects.

- **The numbers.** The pinned runtime draws from Go's `math/rand/v2` PCG
  seeded with `(seed, seed ^ 0x5851f42d4c957f2d)`, and `Gen.bind` starts a
  PCG of its own from a drawn number. The step of the PCG and `Uint64N`
  are machine code (operations 3 and 4 of `spec/crypto-x86_64.s`, reached
  through `Sys.hash`); `library/Gen.alc` draws in the pinned order
  (`Int64N`, `IntN`, `Float64` as the low 53 bits over 2**53). Without a
  seed, or with one that is 0 or no number, the clock's nanoseconds are
  the seed, as upstream.
- **The type.** `generator[a]` is a struct of the library with one field,
  a function from a source of numbers and a size to a `GenTree[a]`: a
  value and a function that makes the trees of the smaller values only
  when a property has failed. `generator` is, with `file`, a type name of
  the library that is not capitalized (`nd_lower` in
  `native-records.alc`, which is `ac_typeword` and this one word); in a program `generator[integer]` annotates a
  binding, a parameter or a result, and `inspect` writes `#generator<>`.
- **Shrinking** is the pinned one: an integer toward 0 or the nearest
  bound by halving the distance; a float to 0, to its whole part and to
  its half; a list by leaving out its first half, its second half and each
  element while the least length holds, then by shrinking an element; a
  tuple's first part, then its second; what `Gen.map` changes, `Gen.filter`
  keeps and `Gen.bind` makes anew from the same seed.
- **`Gen.check(generator, property[, runs])`** needs the type of the
  values to write the failing one, which a function written in Alchem
  cannot see: `native-json.alc` (`jn_check`) adds the description of the
  type as a last argument, as for `JSON.encode`. A property runs in a
  process of its own each time, as upstream runs it (`Testing._spawn`,
  `Task._yield`), so whatever ends that process is its reason: a failure's
  message, or `uncaught throw`.
- **Names.** `Gen.integer`, `Gen.boolean`, `Gen.string` and `Gen.float`
  are functions with the names of types. A function may now have such a
  name, in the library and in a program (`nc_signature` and the start of
  an expression in `native-compiler.alc` ask `nv_member`, which also says
  what a variant or a field may be called), as upstream allows:
  `def integer(...)`, `integer(1)`, `&integer/1`.

## The assertions

`assert`, `refute` and `assert_in_delta` were the compiler's own, with the
pinned messages. In `library/Kernel.alc`, since they are called without a
module name: `assert_raise(text, function)` (the function runs in a
process of its own, as upstream runs it; the reason that process ends
with is compared, and one with an empty message counts as none, as
upstream has it), `capture_io(function)` (descriptor 1 names a file in
memory meanwhile, `memfd_create`; when the function fails what it wrote is
written where it would have gone and the failure passes on, with its own
place and calls), `on_exit(function)` and `flunk`. The receive assertions
are `alchem-processes.md`'s; the time they wait when none is given is
`ALCHEM_TEST_RECEIVE_TIMEOUT`, else 100 ms, as upstream.

## Test files

Upstream has no switch for tests. `alchem run FILE` and `alchem test`
build a file the same way, and a program in which some module declares a
`test` has no `main`: the compiler makes one that hands the tests of the
entry module to the runner. `alchem test` only finds the `*_test.alc`
files, runs each, and talks to the runner through the environment
(`ALCHEM_SEED`, `ALCHEM_TEST_ONLY`, `ALCHEM_TEST_TAGS`,
`ALCHEM_TEST_EXCLUDE`, `ALCHEM_TEST_MAX_FAILURES`, `ALCHEM_TEST_TIMEOUT`,
`ALCHEM_TEST_RECEIVE_TIMEOUT`, `ALCHEM_TEST_TRACE`, `ALCHEM_TEST_RESULT`;
`ALCHEM_COVER_FILE` is the coverage of `--cover`: `alchem-failures.md`). The native compiler does the same with the same input: a source
(or a bundle, `alchem-modules.md`) whose first module holds tests compiles
to a program that runs them. No flag is involved on either side.

`harness/testing.py` holds 37 runs of test files with the pinned
compiler's status, output, standard error and result file frozen in
(seeds, selection by name and by tag, the `skip` tag, a failure limit,
traces with their times left out, timeouts, `on_exit`, `setup_all` and
`setup` with contexts, `describe`, `check all`, `doctest` over a bundle of
two files, macros and `fn` clauses in a test file, some 95 assertion
messages) and 16 test files the pinned compiler rejects.

### The rewriting

A test file is rewritten as text before it is compiled, as macros are
(`alchem-macros.md`), by `native-testing.alc` (`tm_`). `nc_rewritten`
runs the passes in this order: the receive assertions (`ac_receives`,
which keeps every line), then the tests (`tm_prepare`), then macros,
protocols and templates (`mx_prepare`) over what the tests left. Each of
the last two gives a text and moved records (`alchem-traces.md`); when
both rewrote, `tm_composed` turns the second's records back through the
first's, so a place is always named in the program as written. A run of
the second text that stood unchanged in the first is cut where the
first's runs end.

- `test "name" do ... end`, `test "name", pattern do`, `setup do`,
  `setup pattern do` and `setup_all do` become functions
  `def test<127>N(c<127>: integer): integer` and `setup<127>N` (byte 127
  continues a name and no program can write it; N is the declaration's
  number). Their bodies stay where they stood, so every place in them is
  its own. The compiler lets such a function end in anything
  (`tm_ours` in `nc_function_plain`): it gives the word of what its body
  ends in, or the word it was given when the body ends in nothing or `{}`.
  That is the context: a setup block that ends in a value replaces it.
- A block that takes the context binds its pattern to
  `T<127>.__like(c<127>, chain)`, where the chain is the setup blocks
  before it written again as an expression that is typed and never run:
  `T<127>.__next(T<127>.__next({}, fn _ -> block end), fn context -> block
  end)`. The three intrinsics (`tm_intrinsic`, reached from `jn_or`) keep
  the code of their first argument and take the type from the second;
  `__with` and `__like` reject a context that is nothing, which is
  upstream's `this takes a context, but no setup block above it ends in a
  value`. The order is upstream's (`contexts`, `testMain`): `setup_all`,
  then the blocks of each describe around the test from the outermost in,
  as written; before a setup block only those above it. Describe blocks
  of one name in one block are one group.
- `describe`, the tags (`@tag`, `@describetag`, `@moduletag`: a name, an
  atom, or `name: value` pairs) and what else only says something to the
  runner are taken out of the text.
- `assert(left op right)` in a test or setup block, and in the body of a
  function (`def`, `defp`) of any module of a test program, becomes
  `case left do l -> case T.__as(l, right) do r -> if not (l op r) do
  flunk("assertion failed ... code: ... left: ... right: ...") end end
  end`, and any other `assert(condition)` an `if not (...)` with the
  code. `__as` gives the right side the left's type, as the comparison
  does. The text after `code:` is what upstream's `formatExpr` prints of
  the analysed expression: operators spaced, only the parentheses
  precedence needs (and the ones upstream keeps around an `and` inside an
  `or`), a function of the module the assertion stands in as
  `Module.name(...)`, a struct that module declares (with type parameters
  or without) as `%Module.Name{}`, a constant as its value, a macro's call as its
  template with the arguments in, the bitwise operators and `=~` as the
  calls they are, `~w` and `~s` as their values, strings as Go quotes
  them, a float as `inspect` writes it (the program writes it as it runs)
  except from 0.00001 up to 0.0001. Nothing is printed, as upstream, for
  an expression that holds a `fn`, a capture, an `if`, `case` or `for`,
  an option or result constructor, or a list longer than a line.
  A function's body is found by walking its signature token by token to
  its `do` (`tm_signed`; a record of kind 9), and a `defimpl` block is
  taken whole; one without a body (in a
  protocol) or written with `do:` on its line stays as it is, and so does
  a macro. Where the two sides are of a type variable's type the function
  takes descriptions (`alchem-json.md`, "Type variables").
- `check all pattern <- generator, ..., filter, max_runs: n do body end`
  becomes the call upstream's `desugarChecks` makes:
  `Gen.check(Gen.filter(Gen.bind(ga, fn v0 -> case v0 do a -> Gen.map(gb,
  fn v1 -> case v1 do b -> {v0, v1} end end) end end), fn {a, b} -> filter
  end), fn {a, b} -> body end, n)`.
- `doctest Module` becomes one test for each function of that module
  whose `@doc` holds examples (`alx>` lines, `...>` continuations, the
  lines up to a blank one as the result), named `doctest
  Module.function/arity`, each example `assert((source) == (result))` or
  the source alone; everything in it stands where the function's name
  does, as upstream places it. The module is one of the bundle.
- After the last module a module `Alchem<127>TProcess` is added whose
  `main` calls `Testing._run` with the tests of the first module: name
  (the describe names and its own), `file:line`, tags, and the functions
  to call in turn (the setup blocks, then the test), and the `setup_all`
  functions. Its name starts with `Alchem`, so a trace shows nothing of
  it, as upstream shows none of its runner; a trace names a test `test
  NAME` and a setup block `setup` (`tm_shown` in `nz_names`; the name is
  kept in hexadecimal in a comment behind the function's header).

A program with a test and a `main`, a `setup_all` inside a describe, a
describe deeper than 16, anything but tests, setup blocks, describes and
tags inside a describe, an empty test name, a tag with a space or a
comma, a `check all` that does not start with a generator or takes
another option than `max_runs:` are rejected, as upstream rejects them.

### The runner

`library/Testing.alc` (`_run`; no program can call it) is upstream's
`runTests`: it runs the `setup_all` functions in its own process, selects
(`ALCHEM_TEST_ONLY` in the test's or the module's name, the tags of
`ALCHEM_TEST_TAGS` and `ALCHEM_TEST_EXCLUDE`, `skip` unless asked for),
shuffles by `ALCHEM_SEED` (Go's `rand.Shuffle` over the PCG seeded
`(seed, seed ^ 0x9e3779b97f4a7c15)`: `Gen.source` and `Gen.below`), and
runs each test in a process of its own that is not linked, waiting
`ALCHEM_TEST_TIMEOUT` (60000 ms) or the test's `timeout:` tag
(`infinity` for no limit) and stopping one that passes it (`timed out
after Nms`). What the test registered with `on_exit` then runs, the last
first, in another process (`on_exit failed: ...`, `on_exit timed out
...`): `on_exit` keeps each function with its process in a list at word
104 of the library's state block (80 is the zone files, 88 the logger's
page, 96 the processes). It prints `.` or `F`, or under
`ALCHEM_TEST_TRACE` the module and a line a test with its time, then
each failure as `  N) test NAME (MODULE)`, the place, and the failure's
report with its calls, places shown from the working directory; writes
`passed failed excluded skipped` to `ALCHEM_TEST_RESULT`; stops after
`ALCHEM_TEST_MAX_FAILURES`; and ends with status 1 when a test failed.

`Testing._spawn` names the type `Process.Exit` so that the process
library's types come with it into a program that mentions no process
(`assert_raise` or `Gen.check` alone).

## The commands: `alchem` (`tools/alchem.alc`)

`alchem` is the pinned command line's `test`, `run`, `build`, `check` and
`new`: one program that holds the bundler and the compiler and builds a
program by calling them, not by running another program.
`scripts/build-alchem.py` makes it from three modules: `tools/alchem.alc`;
the bundler `tools/alchem-bundle.alc` without its `main`; and
`AlchemCompiler`, the compiler's own source as the bootstrap assembles it
without its `native_compile` entry and its `main`. The compiler under test
compiles the three, so the compiler inside `alchem` is the one that built
it. (`harness/test_driver.py` builds it and holds 71 runs of the pinned
commands in eleven projects with what they print: tests that pass and
fail, a file that does not compile, a program that ends before its tests
are over, seeds, `--only`, tags, `--trace`, `--max-failures`, `--cover` and
`--cover-min`, fixtures, every way the flags can be wrong, `examples/testing`
and `examples/kv` of the pinned tree.)

    alchem test [flags] PATH...
    alchem run FILE [ARGUMENT...]
    alchem build [-o OUT] [-locked] FILE
    alchem check [-locked] FILE
    alchem new DIRECTORY

A file is bundled with its imports (`Bundler.bundle`) and the bundle
compiled by `AlchemCompiler.nc_compile`, the function the standalone
compiler's entry calls: a bundle over 4,194,303 bytes gives the
standalone compiler's `E_RUNTIME_INPUT: input exceeds byte limit`, and a
program it does not take its one message. Inside `alchem` the compiler's
code is an ordinary module of a traced program: its arithmetic is
checked and the collector runs, where a compiler entry neither traces
nor collects. Compiling the compiler's own source this way gives the same
bytes as the standalone compiler in about the same time, in about 70 MB
where the entry's arena grows past 2 GB.

- **`test`** is `testrunner.TestFiles` and `RunTests` (`cmd/alchem/main.go`,
  `testrunner/tests.go`). Flags are read as Go's `flag` package reads them
  (`-name`, `--name`, `-name=value`, `-name value`, `--` ends them; the
  messages and the usage text for a flag that is unknown, has no value or a
  wrong one, and `-h`): `-cover`, `-cover-min`, `-exclude`, `-jobs`,
  `-max-failures`, `-only`, `-receive-timeout`, `-seed`, `-tag`,
  `-timeout`, `-trace`, durations as `time.ParseDuration` reads them. The
  test files are those named and the `*_test.alc` under each directory
  (walked in the order of the names; a directory whose name starts with a
  dot is left out), each once, sorted; then shuffled by the seed as Go's
  `rand.Shuffle` over `rand.NewPCG(seed, seed)` does it (`Gen.source`,
  `Gen.below`), a seed of 0 being one of the clock. Each is built into
  `$TMPDIR/alchem-tests-N/testI` and run with what it writes to both
  streams printed after it, and with the runner's settings in its
  environment (`ALCHEM_SEED`, `ALCHEM_TEST_ONLY`, `_TAGS`, `_EXCLUDE`,
  `_MAX_FAILURES`, `_TIMEOUT`, `_RECEIVE_TIMEOUT`, `_TRACE`, `_RESULT`,
  `ALCHEM_COVER_FILE`). The result file gives the counts; a file that does
  not compile and a program that leaves no result file are reported as
  upstream reports them (`did not compile:`, `stopped before finishing its
  tests: exit status N`) and counted as files not run. Then `Finished in
  N.N seconds`, the counts, `Randomized with seed N`, and with `-cover`
  the table `Percentage | File` and `lines not run:` from the cover files
  (percentages as Go's `%.1f` writes the float: the exact value of the
  double rounded, a tie to the even digit, through `Float.ratio`). Status
  1 when a test failed or a file was not run, or the total is below
  `-cover-min` (`coverage N% is below the required N%`); 2 for a wrong
  command line.
- A directory that holds programs and no test file is run as **fixtures**
  (`testrunner.RunContext`): each `name.alc` is built and run in a
  directory of its own, and its standard output, status and standard error
  are held to `name.stdout`, `name.exitcode` and `name.stderr`
  (`name.test.alc` only has to pass, or to fail with an assertion); `PASS
  name` for each, and the first that differs ends the run with upstream's
  message.
- **`run`** builds into `$TMPDIR/alchem-run-N` and runs the program with
  the arguments, its standard input and output this program's own
  (`/bin/sh` opens `/proc/$PPID/fd/0` and `1` again for it); its status is
  the command's, 255 for one a signal ended.
- **`build`** of a file with no `def main` gives the pinned `FILE:1:1:
  missing main/0`; otherwise it writes the executable to `-o OUT`, or beside the working
  directory under the file's name without `.alc`. `-target` must be
  `linux/amd64`; `-json`, `-race`, `-trace`, `-timeout`,
  `-shutdown-timeout` and `-max-call-depth` are read and change nothing.
- **`check`** builds and throws the executable away (a test file is built
  as the program it is; a module with no `main` as the import of a program
  that does nothing, named by a path relative to the work directory, since
  an import is joined to the importing file's directory); **`new`** writes the
  project the pinned command writes (`main.alc`, `lib/NAME.alc`,
  `test/NAME_test.alc`, `.gitignore`, `README.md`) and prints the same
  lines.

Not as the pinned command line:

- **A file that does not compile** is reported with the compiler's one
  message (`E_COMPILE: invalid or unsupported Alchem function program`) or
  the bundler's (`E_BUNDLE: ...`) where upstream prints its diagnostic with
  the place: the compiler has no diagnostics to print. For the same reason
  `check -json` and `build -json` print no structured diagnostic.
- **A test program that a signal ended** is reported as `signal: killed`
  whatever the signal: `System.cmd` gives -1 for every signal, as
  upstream's does.
- **`-jobs`** is read; the files are built and run one after another. The
  text is the same (upstream holds each file's output back until the files
  before it have printed theirs); a run takes longer.
- **An entry that is a directory** (a project, whose `main.alc` upstream
  takes) is not taken by `run`, `build` and `check`: the entry has to end
  in `.alc` (a file, or a file of a package as the bundler reads one).
- **The other commands** of the pinned command line have no counterpart:
  `fmt` needs upstream's formatter (`compiler/format.go`: its parser with
  comments kept, and a printer); `alx` a shell that keeps the definitions
  and statements given so far and compiles each input with them
  (`cmd/alchem/shell.go`); `lsp` a language server, which lives on the
  diagnostics the compiler does not have; `syntax`, `doc`, `agent-guide`,
  `agent-install` and `docs` the texts of upstream's `guide` package and
  the documentation it reads from sources; `version` names upstream's
  compiler and its Go toolchain.

## Documents written as sigils

`@doc ~S"""` and `@moduledoc ~S"""` (and `~s` without a value) are
documents like a plain heredoc (`sg_attribute`), and `doctest Module`
takes the examples of one, a `~S` text as it is written (`tm_docs`,
`tm_inside`). Upstream's `examples/kv` is written that way; all of its
tests run.

## Differences that remain

- An assertion on `Markup.to_string(~h"""...""")`, a `~h` heredoc
  inside `assert(...)`, does not compile: the text of the assertion is not
  made for a template sigil (`tests/fixtures/templates_test.alc`).

- The text after `code:` follows upstream for the forms above. Not
  followed: a call of a macro of another module that `use` brought in, a
  macro whose template is more than one expression in a `quote`, and a
  float literal of more than 15 figures from 0.00001 up to
  0.0001 (its figures are written as they stand). A constructor of a sum
  type the program declares, written bare, was not compared with
  upstream.
- A test's name in a trace is cut after 240 bytes (a name record of the
  trace routine holds 255).
- A file of 2,000 tests that take a context compiles in about nine
  seconds: the setup blocks before each test are typed once more for it.
- `capture_io` needs `memfd_create` (Linux 3.17); where the call is
  refused the program ends with status 74.
