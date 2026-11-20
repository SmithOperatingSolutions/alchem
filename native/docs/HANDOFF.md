# Developer handoff — library expansion, modules and capacity

PR #11 was merged at aa9ab32 on request. Work continues on
fix/upstream-parity; do not push or merge without another request. Production
Alchem and GitHub Actions remain untouched. Use [skip ci] and local verification.

The goal is a self-hosted Alchem. The native profile now covers typed scalars
and structures, general collections, a broad String/Integer/IO/File/System
library checked against the pinned upstream compiler, and multi-module programs
with bundled imports. This does not mean every production language feature or
standard-library function is complete.

## Reproduce

```sh
mise install                # Go 1.27.4, Rust 1.100.0, Python 3.15.2 (mise.toml)
mise run fetch              # only online step; later checks build offline
mise run verify             # scripts/verify-local.sh --with-source
mise run build              # scripts/build-native.sh
build/native/alchem-compiler < examples/alchem-collections-demo.alc > /tmp/demo
chmod 700 /tmp/demo
/tmp/demo
env -i PATH= build/native/alchem-compiler < build/native/compiler-source.alc > /tmp/rebuilt
cmp build/native/alchem-compiler /tmp/rebuilt
```

For quick incremental checks while editing, use mise run verify:quick [GATE...]
(about 8s; one A1==A2 compiler, stage gates in parallel). Keep mise run verify
for pre-commit and for every result recorded in docs/progress.md.

Those tasks need a Linux x86-64 host. Elsewhere use the linux/amd64 container:
mise run linux:fetch, linux:verify, linux:build and linux:shell (Docker; see
scripts/linux-container.sh). One Go now serves both the reference backend and the
pinned frontend, so ALCHEM_FRONTEND_GO is no longer needed. binutils is only for
optional runtime regeneration. Under user-mode x86-64 emulation on arm64 (Rosetta/
qemu-user) ptrace, strace injection and posix_spawn error reporting do not behave
like a real kernel, so the tracing gates and one Rust CLI test cannot pass there;
the full suite still has to be run on real x86-64. Skips are not passes.
Latest verified results and any failures are recorded in docs/progress.md.

## Artifacts and invariants

Standard build publishes self-built A3, A0, compiler-source.alc, self-host.json,
five self-hosted core tools and the import bundler alchem-bundle. Each file publishes atomically; the set is not
a transaction. Failed checks preserve existing outputs. Binaries are not committed.

Current source:2,268,090 bytes/3693 functions. Source SHA:
2ea182b60bed135aa06c3f42eaa0caf3ea555e87f1f7eb590678d58fa6c2354c.
A1=A2=A3:3,347,517 bytes, image SHA:
b073530c5119fb8a9747bc14650546c77ac1fa16cd3c4cd0cacb51c1b523836f.
Both seeds produce identical images. Native rebuilds use empty PATH with no host
parser/compiler/assembler/linker. All actual compiler components use bytes/b[...].
The seed adapter alone translates that spelling to its older byte IR. General
list/map/callback compilation is implemented by the Alchem compiler itself.

Source<=4,194,303 bytes (spec/source-capacity.md);65,535 functions and 65,536 table records (a module header, struct, sum type or further clause is a record; spec/alchem-modules.md);4096 literal list/map elements (128 byte-literal elements);
live slots, parts of a tuple and the bytes of a structural type bounded by the source and memory alone (spec/source-capacity.md); expressions nest200 deep;total code<=1GiB, with 32-bit function lengths and image size. Source cursors are24-bit
(22 bits of position below the two flag bits of a value); full
structural types travel after a length byte. Function records27 bytes (with a module index and the
position of the result annotation), environment name records8 bytes plus the type, with u16 function IDs. Table starts1152 with one u64 per used slot;
code follows it. Every native program runs on its own stack mapping (1GiB reserved lazily); each
function checks the stack pointer against its limit and counts active calls in R15 (100000 below main,
as upstream); seed IR retains its
separate charged-stack bound (1MiB and 256 calls; 4MiB and 1024 calls for V11, which builds the compiler).
Compiler entries reserve 16 GiB lazily, or the largest half of that the system grants down to 1 GiB
(1 GiB was nearly used by a dense 1 MiB program: 874 MB); ordinary
programs reserve 16 GiB lazily too, or the largest half the system grants down to 4 MiB
(memory nothing refers to is given back: spec/alchem-memory.md). A function's call to
itself in return position is a jump, as upstream, and the library written in Alchem is not counted in R15. Traced native rebuild charge is17,179,803,648 bytes (address space: the compiler reserves the 16 GiB arena lazily and collects, near 53 MB resident). V11 seed IR permits65535 functions, arena_bytes up to 16 GiB
and a 4 MiB bytes.read; earlier versions retain256 functions and 1 MiB.

Remaining ceilings, in the order the compiler will meet them: the pinned parser of the
seed frontend reads 1,048,576 bytes, so scripts/bootstrap-alchem-compiler.py lowers a
longer compiler source in parts (frontend_ir; the source is 851,625 bytes, and a
4,194,303-byte one of 7,864 functions was built seed -> A1 == A2 that way); the source limit
of 4,194,303 bytes (byte concatenation is bounded only
by the arena natively and in V11 seed IR, and total code by 1 GiB), which the
compiler's own source meets long before the 65,535 functions a program may have
(1,862 functions now: a library function written in Alchem no longer adds one,
spec/alchem-library-profile.md); what still
grows with the square of a count is listed in spec/source-capacity.md ("Costs that grow faster than the program"). The function table is no
longer copied per declaration and is searched through a name index, so a program of
60,000 small functions compiles in about eleven seconds and 2.2 GB (spec/alchem-modules.md);
what remains is about 37 KB of arena per small function. A function body is
no longer capped at1024 tokens,65535 code bytes or16 statements, nor a branch at
16KiB, and statements are joined in runs of doubling length, so a body of 20,000
statements compiles in about a second.

## Supported behavior

Typed integers/bytes/strings/booleans, recursively nested options/tuples/results/
lists/maps, scoped branches/bindings, private/forward/recursive direct calls,
short-circuit and/or, exhaustive some/none and ok/error cases. Unit tuples support
ok({}); elem uses a checked static index. Unknown constructor/empty collection
holes unify structurally with declarations, calls, defaults and other branches.

General lists retain full integers/pointers; a tail is an address inside its
list and an element is put before a list without copying it (spec/alchem-lists.md). Native map/filter/reduce callbacks
are typed function values: &name or anonymous functions with captured bindings
(spec/alchem-closures.md), stored, passed, returned and called directly.
Maps support integer/string/boolean keys, nested values, literals/new, get/fetch/
has_key?/put/delete, keys/values/entries/to_list and count/empty?. String keys use
content equality; enumeration is sorted by pinned scalar/byte-string key order.
Implementation uses linear lookup/copies and sorting of fresh results; do not
claim optimized hash-map performance. All values remain immutable.

Further APIs include Enum.join, Integer base formatting/digits/checked undigits,
String.duplicate, IO.write, System.pid/system_time/os_time/stop. Main-body puts/
write retain complete-write/error handling. Existing byte APIs and pinned
Unicode17 grapheme behavior remain checked. Indic-conjunct rules remain omitted
and pictographic ranges approximate, matching the pinned runtime's limitations.

## Verification and next work

Per self-built stage:831 general collection programs/9 rejections plus callback
exhaustion,262 map programs/12 rejections,186 added-library programs/6 rejections,
real PID/clock checks,4 library syscall injections and26 exact arena charges.
Also46 structural programs/17 rejections/tuple exhaustion,263 type-word cases,
existing integer/byte/Enum/string/boolean/options/Unicode gates and all core tools.
The full suite includes Go/Rust equality, V10/V11 capacity boundaries, all six
self-build memory measurements and publication preservation. Readable source
rebuilds to the identical image. Commands/logs are in docs/progress.md.

Next developer priorities:

1. Done this session: Integer.parse, IO.read_line/read_all, System.argv/get_env
   (entry stubs keep the initial stack in R14), IO statements in helpers and
   branches (the pinned language has no void helpers), File.read, and string
   ==/!=, split, replace, count, valid?, trim, upcase, downcase, to_integer.
   Also string ordering, trim_leading/trailing, File.write and IO statements in
   case arms, String.reverse/capitalize/pad_*, File.append/remove. The grapheme
   runtime is now shared. Imports work through scripts/bundle-alchem.py and
   multi-module bundles (spec/alchem-modules.md). Closures and calls through
   function values are in (spec/alchem-closures.md).
2. Broaden String APIs using the pinned grapheme/UTF-8 rules; preserve malformed
   input and provenance tests. Do not substitute code-point slicing.
3. Closures and imports are in, with & captures and references, lambdas in any
   argument position, calls of call results, annotated bindings and library
   functions by arity (&String.length/1). Structs and sum types, local and
   imported, are in, and == compares compound values by structure
   (spec/alchem-records.md). Patterns are general: case over any type with
   nested patterns, literals, pins, guards, lists and maps, pattern bindings
   and parameters, with the matrix exhaustiveness test (spec/alchem-patterns.md).
   Type variables are in: generic functions, generic structs and sum types,
   and equality through type variables (spec/alchem-generics.md).
   Package imports are in (spec/alchem-modules.md): read from the Go module
   cache, with alchem.lock. The bundler is now
   an Alchem program (tools/alchem-bundle.alc, built to
   build/native/alchem-bundle and checked against scripts/bundle-alchem.py), and
   IO.warn writes to standard error. The pipe operator |> works for every kind
   of call and may end in IO.puts() as a statement (spec/alchem-closures.md). Types are byte strings of up to255 bytes
   (they were one60-bit word), so reduce accumulators and function types over
   tuples and results of collections now compile.
4. Coverage of the pinned language is measured, not estimated:
   `python3 scripts/upstream-examples.py` runs every example of the pinned
   syntax and library references (47 programs, 825 library sessions) through
   both compilers. All 871 agree. The one example of `extern`
   (syntax/extern) is not counted: `extern` binds a function to a Go function
   by name, a native program has no Go runtime to call, and it is dropped in
   favour of running external processes. `--only lib/Enum --show 5` prints
   failures. Function clauses, guards on functions, default arguments,
   functions of one name with several numbers of parameters or parameter
   types, `return` and `raise` are compiled (spec/alchem-clauses.md,
   harness/clauses.py), and so are `with` and `for`
   (spec/alchem-comprehensions.md, harness/comprehensions.py); `try` is not
   compiled yet. A new library function usually
   belongs in library/*.alc; run scripts/generate-prelude.py after editing.
   Other known differences: a function holds 250 live bindings and takes 200
   parameters, a call 250 arguments (an environment record keeps its slot in
   one byte); a value of a type variable's type cannot be inspected (a generic
   function receives a comparator per type variable, not a description);
   `min`/`max` take integers, floats, booleans and strings only; `extern` binds Go
   code; packages are read from the module cache and never downloaded.
   The seed backends bound a program at 256 nested calls and 1 MiB of
   stack. The seed-built compiler (A0) met the first while compiling the
   compiler's own deepest functions (it stopped with E_RUNTIME_LIMIT once the
   source held 1282 functions, by the depth of the halving over them), so
   IR version 11, which only compiler builds use, now allows 1024 calls and
   4 MiB in both seeds. Other versions keep 256 and 1 MiB.
   The full verification can run in a copy of the tree (rsync to a scratch
   directory, run scripts/verify-local.sh there) while the tree is edited.
5. Measure after correctness using exact source/compiler hashes. Historical
   timings used smaller compilers; they are not controlled speed comparisons.

## Code map

| Area | Files |
| --- | --- |
| Parser/type/codegen | implementations/alchem/native-compiler.alc; native-types.alc; native-structures.alc |
| General lists/callbacks/maps | native-collections.alc; native-maps.alc; native-collection-data.alc |
| Functions and closures | native-functions.alc |
| Structs and sum types | native-records.alc |
| Structural equality | native-equality.alc |
| Order of values, sorting, library failures named at the call | native-ordering.alc; native-sort-data.alc; spec/sort-runtime.c; spec/sort-stable-x86_64.s; spec/sort-unstable-x86_64.s; scripts/generate-sort-runtime.py; spec/alchem-ordering.md; harness/ordering.py; harness/ordering-cases.json.xz; scripts/generate-ordering-cases.py |
| Patterns | native-patterns.alc |
| Statements and expressions compiled in windows of a long environment | native-scope.alc (spec/source-capacity.md, "Costs that grow faster than the program") |
| Arities, defaults, clauses, forms, return, raise | native-clauses.alc |
| Type variables | native-generics.alc |
| Blocks and statements | native-blocks.alc |
| Memory given back (the collector, allocation hooks, maps of many entries as trees) | native-memory.alc; native-memory-data.alc; spec/memory-x86_64.s; scripts/generate-memory-runtime.py (`--stress`: the testing variant); spec/alchem-memory.md; harness/memory_reclaim.py |
| Tail calls, entry and exit of library functions, the arena of a program | native-tail.alc; nc_arena_init in native-runtime.alc; spec/alchem-tail-calls.md; harness/tail_calls.py; harness/native_memory.py (floor_arena, measured charge) |
| with and for | native-comprehensions.alc |
| Floats | native-floats.alc; native-float-data.alc; spec/float-x86_64.s; scripts/generate-float-runtime.py; spec/alchem-floats.md; harness/floats.py |
| Sets, streams, lazy ranges, enumerables as library arguments, tuple keys, library frames left out of traces | native-sets.alc; library/MapSet.alc; library/Stream.alc (spec/alchem-sets-streams.md, harness/sets.py, harness/streams.py) |
| Sigils, value[index], references to library functions written in Alchem | native-sigils.alc (spec/alchem-sigils.md, harness/sigils.py) |
| try, rescue, catch, else, after, defexception, throw | native-try.alc and the start of spec/trace-x86_64.s (spec/alchem-try.md, harness/exceptions.py) |
| Regular expressions | native-regex.alc (Go's regexp/syntax: parse, simplify, compile; also library text); native-regex-data.alc; native-sigils.alc (sg_rx, sg_regex, sg_match); library/Regex.alc (matcher); spec/alchem-regex.md; spec/regex-tables.json; scripts/generate-regex-tables.go, generate-regex-data.py; harness/regex.py |
| Macros (defmacro, quote, use), and the rewriting of a program before it is compiled | native-macros.alc (spec/alchem-macros.md, harness/macros.py); the moved records of spec/trace-x86_64.s |
| Protocols (defprotocol, defimpl) | native-protocols.alc (spec/alchem-protocols.md, harness/protocols.py) |
| HTML templates (~h, ~H) and Markup | native-templates.alc, library/Markup.alc (spec/alchem-templates.md, harness/templates.py) |
| Parser forms: ( and [ on a new line, fn with clauses, ( call ) statements, member names | spec/alchem-parsing.md, harness/parsing.py |
| Failure traces | native-trace.alc; native-trace-data.alc; spec/trace-x86_64.s; scripts/generate-trace-runtime.py |
| Further APIs | native-library.alc; native-library-data.alc; shared runtimes native-parse-data.alc (Integer.parse, String.to_integer), native-file-data.alc (File.read), native-case-data.alc (String.upcase/downcase/capitalize), native-grapheme-data.alc (graphemes) |
| Byte/string/boolean/options | native-runtime.alc; native-strings.alc; native-booleans.alc; native-options.alc |
| Unicode | native-graphemes.alc; native-grapheme-data.alc; spec/grapheme-ranges.json |
| Runtime references/regeneration | spec/collections-x86_64.s; library-x86_64.s; integer-parse-x86_64.s; print-ranges.json; scripts/generate-*-runtime.py; generate-print-ranges.go |
| Seeds/build | adapters/alchem/native_bytes.go; scripts/bootstrap-alchem-compiler.py; build-self-hosted.py; build-core-modules.py |
| New gates | harness/pipes.py; harness/records.py; harness/equality.py; harness/patterns.py; harness/generics.py; harness/inference.py; harness/long_bodies.py; harness/statements.py; harness/traces.py; harness/packages.py; harness/literals.py; harness/wide.py; harness/integer_parse.py; io_input.py; system_env.py; effect_helpers.py; file_read.py; string_ops.py; string_case.py; string_graphemes.py; modules.py; closures.py; general_collections.py; maps.py; library_expansion.py; collection_memory.py; function_capacity.py |
| Tools written in Alchem | tools/alchem-bundle.alc (import bundler; reference scripts/bundle-alchem.py), tools/alchem.alc (the test, run, build, check and new commands; scripts/build-alchem.py makes `alchem`, one executable with the bundler and the compiler inside, which it calls; spec/alchem-testing-gen.md) |
| Contracts | spec/alchem-source-profile.md; alchem-structural-types.md; alchem-collections-profile.md; alchem-library-profile.md |
