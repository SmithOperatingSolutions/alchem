# Alchem Native

Independent research laboratory for a native Alchem compiler, isolated from the production [Alchem](https://github.com/SmithOperatingSolutions/alchem) repository.

## Research tracks

- **Go:** reference architecture and experimental native code generator.
- **Rust:** equivalent native compiler implementation.
- **Alchem:** a native compiler written in Alchem, with verified self-rebuilds for its documented native profile.

## Self-hosted compiler

```sh
bash scripts/build-native.sh
build/native/alchem-compiler < examples/alchem-byte-compiler-demo.alc > /tmp/demo
chmod 700 /tmp/demo
/tmp/demo
echo "$?"  # 42
```

A1, A2 and A3 rebuild the actual assembled source with identical bytes and pass
correctness/rejection tests with empty PATH. The standard build publishes A3,
its source and hash manifest, plus five self-hosted core tools. See
[core module coverage](docs/core-modules.md), [quickstart](docs/quickstart.md),
[self-hosting evidence](docs/self-hosting.md) and
[initial measurements](docs/self-hosting-benchmarks.md). This is bounded native
profile compatibility; production Alchem remains unchanged.

The compiler also supports typed strings, concatenation, byte_size, Integer formatting and main-body
IO.puts/write. Try examples/alchem-string-demo.alc; its native executable prints
`Hello, Alchem!`. See [the string contract](spec/alchem-string-profile.md).

Stored booleans and byte/string predicates are also native; try
examples/alchem-predicate-demo.alc. See
[boolean and predicate support](spec/alchem-boolean-profile.md). Source assembly
compacts formatting; native rebuilds consume the exact same compact source.

Pinned-runtime grapheme length/slice/first/last, recursive options, tuples and results and
short-circuit boolean operators are now native too. Try
examples/alchem-grapheme-options-demo.alc; see [grapheme compatibility](spec/alchem-grapheme-profile.md)
and [typed options](spec/alchem-options-profile.md).
[Structural types](spec/alchem-structural-types.md) preserve nested values across
calls and returns; try examples/alchem-structural-types-demo.alc.

The native source limit is now 4,194,303 bytes; see [source capacity](spec/source-capacity.md).

## Bootstrap foundation

1. Specify a minimal typed intermediate representation and Linux x86-64 ABI.
2. Define shared positive and negative compiler fixtures.
3. Build Go and Rust prototypes that emit executables without invoking an external compiler in the Alchem compilation path.
4. Run differential correctness tests and record compile time, peak memory, binary size, and execution performance.
5. Document decisions and progress before any integration into the production compiler.

**Rules:** test-first changes; deterministic outputs; no modifications to the production Alchem repository; pin dependencies; report measurements rather than assuming Rust or Go wins.

See `docs/architecture.md`, `docs/progress.md`, and `spec/ir.md` for the evolving design.

## Try the experimental source compiler

The [invoice example](examples/invoice.alc) now compiles from real Alchem source
using the Rust backend. Follow [the quickstart](docs/quickstart.md) to build the
two prebuilt tools, then:

```sh
build/native/alchem-native --source examples/invoice.alc --output /tmp/invoice
/tmp/invoice
echo "$?"  # 42
```

The [hello example](examples/hello-native.alc) prints a literal line using native
IO.puts. [Developer handoff](docs/HANDOFF.md) records the resume point and next task.

Supported: one main, integer bindings/arithmetic, bounded recursive integer helper
functions with up to six parameters, signed comparisons, conditional values,
checked computed byte lists/concatenation and byte-valued helpers, literal IO.puts, and a final System.halt.
Executable source uses V6 native status checks: values outside 0..255 emit
E_HALT_STATUS and exit 70. Main/helpers are not executed during compilation.
This remains a restricted subset; production Alchem is unchanged.

## Local verification

`bash scripts/verify-local.sh` runs the Go baseline. After fetching the locked
Rust dependencies, `bash scripts/verify-local.sh --with-rust` runs both backends
and the shared differential suite. See `implementations/rust/README.md` for setup.

`bash scripts/verify-local.sh --with-source` additionally tests the pinned Alchem
frontend's integer functions and restricted executable-main adapter. It needs Go 1.27 and the cached upstream
module; see `adapters/alchem/README.md`. This is not a complete source frontend.

Local measurements and their limits are in `docs/benchmarks.md`; pinned upstream
integration boundaries are in `docs/frontend-boundaries.md`.

The [self-hosting roadmap](docs/self-hosting.md) tracks the path to a compiler written in Alchem; functions/calls, typed conditionals, bounded recursion and immutable bytes are verified. The first compiler
component written in Alchem is [a bounded ASCII expression lexer](implementations/alchem/lexer.alc),
with checked integer conversion and an arithmetic parser/evaluator. Bounded runtime byte construction is verified too. Compiler
declarations/semantics, binary source output and file IO are next.
An [emitter written in Alchem](implementations/alchem/encoder.alc) now builds
complete 140-byte Linux ELF images. Try `python3 scripts/emit-alchem-executable.py
--status 42 --output /tmp/exit42` after building the bootstrap tools. It is a
small executable-producing component, not a general or self-hosted compiler.
[Self-hosting benchmark gates](docs/self-hosting-benchmarks.md) remain explicit;
no self-rebuild performance result is claimed.

General signed-integer/string/nested lists, immutable maps and typed named-function
map/filter/reduce are now native. Try examples/alchem-collections-demo.alc; see
[collections](spec/alchem-collections-profile.md) and
[additional library APIs](spec/alchem-library-profile.md). Byte buffers now use
explicit bytes/b[...] syntax. Source input capacity is 4,194,303 bytes.

## License

Apache License 2.0; see [LICENSE](LICENSE).
