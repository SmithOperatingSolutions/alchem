# Native compiler

A compiler for Alchem written in Alchem. It builds native executables for
Linux x86-64 and Windows x64, and for Linux ARM64 and macOS by translating
each function, without Go, a C compiler or LLVM in the compilation path. It compiles itself: the
compiler it builds from its own source builds the same bytes again
(A1 = A2 = A3). The aim is an Alchem that is self-hosted.

All 878 counted examples of the syntax and library references give the same
output, status and errors as programs built by the Go compiler of this
repository. Where the two still differ, `spec/` says so and why.

## Build and run

Requires Linux x86-64 and Python 3 ([mise](https://mise.jdx.dev) installs
the one of `mise.toml`), and neither Go nor Rust. From this directory:

```sh
mise install python
mise run build
build/native/alchem-compiler < examples/alchem-byte-compiler-demo.alc > /tmp/demo
chmod 700 /tmp/demo
/tmp/demo
echo "$?"  # 42
```

On other hosts run the same steps in the linux/amd64 container
(`mise run linux:build`). See [the quickstart](docs/quickstart.md).

## The pinned release

The build starts from a released compiler: `pinned-compiler.json` names
the release and the SHA-256 of the archive of each target, and
`scripts/pinned-compiler.py` downloads the one for the machine into
`build/pinned`, refuses it unless its sum is the pinned one, and takes the
compiler out. That compiler builds the source (A1), A1 builds it again
(A2), and the two must be the same bytes. `ALCHEM_PINNED_COMPILER=PATH`
uses a compiler already at hand instead, with no network.

A release is the compiler as a program of each target it builds itself on
(Linux x86-64, Linux ARM64, macOS ARM64, Windows x64), each alone in an
archive whose bytes depend on the compiler only
(`scripts/release-compilers.py`). The workflow *Native compiler release*
builds them, has each compile its own source on its target, which must
give it again byte for byte, and publishes them as a prerelease under a
`native-compiler-` tag.

**Moving the pin.** The pinned compiler must be able to compile the
source. A change it cannot compile (the compiler's source using something
of the language the pinned compiler does not have yet) is made in two
steps:

1. Merge what gives the compiler the new thing, in source the pinned
   compiler still compiles. Run *Native compiler release* on `main` with
   the next tag (`native-compiler-2`) and `publish` set.
2. In the change that uses the new thing, set `release` in
   `pinned-compiler.json` to that tag and `sha256` to the sums of the
   release's `SHA256SUMS`.

A change of what the compiler makes of its own code (a runtime it
embeds, such as the collector, or the code it emits for the compiler's
source) makes A1, which the pinned compiler made, differ from A2, though
both compile alike. It is made in one change, before it is merged:

1. Run *Native compiler release* on the change's branch with the next tag,
   `publish` and `converge` set: A2 must make itself again (A2 == A3), A3
   is released, and each target must make itself from its archive.
2. In the same change, set `release` and `sha256` to that release. A1 is
   then A2 again, which is what CI requires.

Nothing else needs a new release: a pin may stay behind the source for as
long as it compiles it.

**The seed.** Before there was a release the first stage was made from the
source by the Go compiler's frontend (`adapters/alchem`) and a Rust backend
(`implementations/rust`). `scripts/verify-quick.py --seed` and the complete
suite still start so (`mise install`, `mise run fetch`, `mise run
fetch:seed`), and the nightly run of CI checks that the compiler made from
the seed is, byte for byte, the one made from the pinned release: the
first stage can still be made without a released compiler.

## Linux ARM64

`scripts/build-arm64.py` builds the compiler that targets ARM64;
`scripts/fetch-arm64-tools.sh` fetches QEMU and an assembler to run and check
its programs on x86-64. The design, and its one known difference from the Go
compiler's ARM64 programs, are in [spec/arm64.md](spec/arm64.md).

## macOS ARM64

`scripts/build-arm64.py --darwin` builds the compiler that makes macOS ARM64
programs: position-independent Mach-O executables that call libSystem and
carry an ad-hoc code signature the compiler computes
([spec/darwin-arm64.md](spec/darwin-arm64.md)). With `--macos PATH` that
compiler also compiles itself into a macOS program, which runs the gates on
macOS:

```sh
python3 scripts/build-arm64.py --darwin --compiler build/dev/A2 \
  --output build/dev/alchem-compiler-darwin --macos build/dev/alchem-compiler-macos
python3 scripts/verify-darwin.py build/dev/alchem-compiler-macos   # on macOS
```

## Windows x64

`scripts/build-windows.py` builds the compiler that makes Windows programs,
and that compiler as a Windows program: PE executables whose code is the
Linux image, its system calls made by a layer over kernel32 and Winsock
([spec/windows.md](spec/windows.md)). CI runs it on Windows, where it must
make itself again byte for byte and its programs print what those of the Go
compiler print there (`scripts/windows-examples.py`).

## Verification

```sh
python3 scripts/verify-quick.py             # the fixpoint and the gates, in parallel, from the pinned release
python3 scripts/verify-quick.py --seed      # the same from the seed, with the gates that take the seed's parts
bash scripts/verify-local.sh --with-source  # the complete suite, from the seed
```

On a Mac with Apple silicon, `scripts/verify-arm64.sh [GATE...]` runs the
gates and the corpus in a native Linux ARM64 container in about nine minutes.
macOS checks every new program before its first run, a sixth of a second
each, and the gates run thousands: there they take four times as long.

A file made from other files (the runtimes, the library's data, the tables
of `tools/`) is committed, and CI makes every one of them again on each pull
request and fails on a difference (*Derived files*). In the container, as the
machine code depends on the assembler:

```sh
bash scripts/linux-container.sh python3 scripts/verify-derived.py           # compare
bash scripts/linux-container.sh python3 scripts/verify-derived.py --write   # regenerate what differs
```

The complete suite needs ptrace permission for fault injection and register
measurements; a skip is not a pass. The Go compiler of this repository is the
reference the gates compare against: they need Go (`mise install go`, `mise
run fetch`), a build does not.

## Documents

- [Architecture](docs/architecture.md) and [self-hosting](docs/self-hosting.md).
- `spec/`: the IR, the ABI and executable format, the memory collector, the
  processes, every profile of the language, and the differences that remain.
- [Benchmarks](docs/benchmarks.md) and [self-hosting
  measurements](docs/self-hosting-benchmarks.md).

## License

Apache License 2.0; see [LICENSE](LICENSE).
