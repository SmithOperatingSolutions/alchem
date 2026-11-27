# Build and run the self-hosted Alchem compiler

Requires Linux x86-64 and [mise](https://mise.jdx.dev), which installs the
Python of the repository's mise.toml. A build needs neither Go nor Rust:

```sh
mise install python
mise run build
```

On other hosts (for example Apple Silicon) run the same step in the linux/amd64
container: `mise run linux:build`. Emulated x86-64 can build and run the
compiler but cannot pass the ptrace/strace gates of the full suite.

The build downloads the released compiler `pinned-compiler.json` names, once,
and checks its sum. That compiler builds the current source (A1), A1 builds it
again (A2) and A2 once more (A3); the three must be the same bytes. A3 is then
published as build/native/alchem-compiler ([self-hosting](self-hosting.md)).
Generated binaries are ignored build artifacts.

## Compile with Alchem

```sh
build/native/alchem-compiler < examples/alchem-byte-compiler-demo.alc > /tmp/demo
chmod 700 /tmp/demo
/tmp/demo
echo "$?"  # 42
```

The saved compiler is written/built in Alchem and runs with an empty PATH. It
supports typed integers/bytes/strings/booleans and nested structural types,
general lists/maps, named callbacks, library operations and native ELF output. See
[the bounded profile](../spec/alchem-source-profile.md). It is self-hosted for
that profile, not compatible with all production Alchem features.

Programs split across files use `import "path.alc"`; bundle them first, since
the compiler itself opens no files (see [modules](../spec/alchem-modules.md)):

```sh
build/native/alchem-bundle app.alc | build/native/alchem-compiler > /tmp/app
```

The compiler reads stdin and writes binary stdout; the shell creates/chmods the
file. Redirect through a temporary file and rename after success if preserving
an existing executable matters. Direct redirection can truncate on source error.

## The `alchem` command

The build also makes `build/native/alchem`: the pinned command line's `test`,
`run`, `build`, `check` and `new` in one executable that holds the bundler and
the compiler and calls them, so no other program needs to be in `PATH`
(see [the commands](../spec/alchem-testing-gen.md)):

```sh
build/native/alchem new my-app && cd my-app
../build/native/alchem run main.alc Ada    # Hello, Ada!
../build/native/alchem test test
../build/native/alchem build -o my-app main.alc
```

`python3 scripts/build-alchem.py --compiler COMPILER --output alchem` makes it
with any compiler of this tree.

## Rebuild without host compilers

```sh
env -i PATH= build/native/alchem-compiler < build/native/compiler-source.alc > /tmp/rebuilt
chmod 700 /tmp/rebuilt
cmp build/native/alchem-compiler /tmp/rebuilt
```

No frontend, backend, Go, Rust, Python, Cargo or linker is needed for that rebuild.
compiler-source.alc is the exact assembled distribution; self-host.json records
source/bootstrap/stage hashes. The builder also retains alchem-compiler-bootstrap
(A0). Individual publication files are atomic; failed rebuild checks preserve the
previous publication.

## Other research tools

The original Rust driver/prebuilt pinned frontend remain for IR/source oracle
work, with some broader source features such as literal IO.puts. `mise run
build` no longer makes them (it starts from the pinned release and needs
neither Go nor Rust); `cargo build --release` in `implementations/rust` and
`go build` in `adapters/alchem` do:

```sh
build/native/alchem-native --source examples/invoice.alc --output /tmp/invoice
/tmp/invoice
echo "$?"  # 42
build/native/alchem-native --source examples/hello-native.alc --output /tmp/hello
/tmp/hello
```

That driver needs its alchem-source-probe sibling. IR mode remains
--target x86_64-unknown-linux-gnu --input FILE.json --output FILE. Failed compiler
output replacement is atomic/preserving and cannot overwrite the input source.
The old build/native/alchem-arithmetic mode still folds small expressions:

```sh
printf '6*7\n' | build/native/alchem-arithmetic > /tmp/answer
chmod 700 /tmp/answer
/tmp/answer
echo "$?"  # 42
```

## Verify and measure

```sh
bash scripts/verify-local.sh --with-source
python3 scripts/benchmark-self-host.py \
  --compiler build/native/alchem-compiler --source build/native/compiler-source.alc \
  --samples 10 --warmups 2 --output /tmp/self-build.json
```

For iteration, `mise run verify:quick` (scripts/verify-quick.py) bootstraps A0,
requires the A1==A2 fixpoint and runs every gate once against A2 in parallel.
Pass name filters to narrow it (`mise run verify:quick -- maps graphemes`;
`--list` shows gates). Before a pull request, `bash scripts/check.sh` runs
what its CI checks, with CI's settings; [testing](testing.md) says what each
check covers and where it runs.

The full suite checks native profiles, source/components, A1/A2/A3, all generated
stages' correctness/rejections and measured arena limits. Ptrace/strace permission
is needed for fault injection and register measurements; skips are not passes.
See [the initial baseline](self-hosting-benchmarks.md).

Try examples/alchem-collections-demo.alc for signed integer/string lists,
map/filter/reduce, sorted map entries and library output. Native byte buffers
use bytes/b[...]; ordinary list[integer] values now preserve all64 bits.
