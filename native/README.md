# Native compiler

A compiler for Alchem written in Alchem. It builds native executables for
Linux x86-64, and for Linux ARM64 by translating each function, without Go,
a C compiler or LLVM in the compilation path. It compiles itself: the
compiler it builds from its own source builds the same bytes again
(A1 = A2 = A3). The aim is an Alchem that is self-hosted.

All 871 counted examples of the syntax and library references give the same
output, status and errors as programs built by the Go compiler of this
repository. Where the two still differ, `spec/` says so and why.

## Build and run

Requires Linux x86-64 and [mise](https://mise.jdx.dev), which installs the
Go, Rust and Python of `mise.toml`. From this directory:

```sh
mise install
mise run fetch
mise run build
build/native/alchem-compiler < examples/alchem-byte-compiler-demo.alc > /tmp/demo
chmod 700 /tmp/demo
/tmp/demo
echo "$?"  # 42
```

On other hosts run the same steps in the linux/amd64 container
(`mise run linux:fetch`, `mise run linux:build`). See
[the quickstart](docs/quickstart.md).

Go and Rust build only the seed: the Go compiler's frontend
(`adapters/alchem`) and a Rust backend (`implementations/rust`) build the
compiler written in Alchem (`implementations/alchem`) once, and every later
stage is built by the one before it.

## Linux ARM64

`scripts/build-arm64.py` builds the compiler that targets ARM64;
`scripts/fetch-arm64-tools.sh` fetches QEMU and an assembler to run and check
its programs on x86-64. The design, and its one known difference from the Go
compiler's ARM64 programs, are in [spec/arm64.md](spec/arm64.md).

## macOS ARM64

`scripts/build-arm64.py --darwin` builds the compiler that makes macOS ARM64
programs: position-independent Mach-O executables that call libSystem and
carry an ad-hoc code signature the compiler computes. It is the work of
[spec/darwin-arm64.md](spec/darwin-arm64.md), and not complete: most system
calls are still to come.

## Verification

```sh
python3 scripts/verify-quick.py             # the fixpoint and every gate, in parallel
bash scripts/verify-local.sh --with-source  # the complete suite
```

The complete suite needs ptrace permission for fault injection and register
measurements; a skip is not a pass. The Go compiler of this repository is the
reference the gates compare against.

## Documents

- [Architecture](docs/architecture.md) and [self-hosting](docs/self-hosting.md).
- `spec/`: the IR, the ABI and executable format, the memory collector, the
  processes, every profile of the language, and the differences that remain.
- [Benchmarks](docs/benchmarks.md) and [self-hosting
  measurements](docs/self-hosting-benchmarks.md).

## License

Apache License 2.0; see [LICENSE](LICENSE).
