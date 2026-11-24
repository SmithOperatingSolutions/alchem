# Self-hosting

The compiler is written in Alchem and compiles itself: given its own source
it writes itself again, byte for byte. That holds on each of the four
targets it runs on, and it is what every build and every release checks
first.

## The stages

A build starts from a compiler that already exists and ends with one made
from the current source by itself:

| Stage | Made by | From |
| --- | --- | --- |
| A0 | (downloaded) | The released compiler `pinned-compiler.json` names |
| A1 | A0 | The current source |
| A2 | A1 | The current source |
| A3 | A2 | The current source |

A1 is the first compiler made from the current source, by an older
compiler. A2 is the same source compiled by A1. If the source means what it
says, A1 and A2 are the same bytes: a difference is a compiler that does
not compile itself as it compiles others. `scripts/verify-quick.py`
requires A1 = A2; `scripts/build-self-hosted.py`, which `mise run build`
runs, goes one stage further and requires A1 = A2 = A3 before it publishes
anything to `build/native`.

The source every stage reads is one file: the files of
`implementations/alchem` put together into one module by
`scripts/bootstrap-alchem-compiler.py`, the same bytes for each stage. The
build writes it beside the compiler as `compiler-source.alc`, with
`self-host.json` (the sums of the source and of each stage).

A stage is made with nothing else: the compiler reads the source on
standard input and writes the executable on standard output, with an empty
`PATH`.

```sh
env -i PATH= build/native/alchem-compiler < build/native/compiler-source.alc > /tmp/rebuilt
cmp build/native/alchem-compiler /tmp/rebuilt
```

## Where A0 comes from

`pinned-compiler.json` names a release of the compiler and the SHA-256 of
its archive for each target. `scripts/pinned-compiler.py` downloads the one
for the machine once, refuses it unless its sum is the pinned one, and
takes the compiler out. `ALCHEM_PINNED_COMPILER=PATH` uses a compiler
already at hand, with no network.

The pinned compiler only has to be able to compile the current source. It
may stay behind the source for as long as it does; a change that uses
something of the language the pinned compiler does not have yet is made in
two steps, a release first and then the change that moves the pin
([README](../README.md#the-pinned-release)).

## The other targets

The compilers for the other targets are the same source with the target's
constant changed ([architecture](architecture.md#one-source-four-targets)).
Each is made twice: once by the Linux x86-64 compiler, which gives a Linux
program that makes the target's programs (the cross compiler), and once by
that cross compiler, which gives the compiler as a program of the target.

| Target | Cross compiler | The compiler on the target |
| --- | --- | --- |
| Linux ARM64 | `build-arm64.py` | The cross compiler compiling its own source |
| macOS ARM64 | `build-arm64.py --darwin` | The same with `--macos PATH` |
| Windows x64 | `build-windows.py` | `alchem-compiler-windows.exe` |

On its target, each must make itself again byte for byte from its own
source. CI checks this on a machine of each target, and
`scripts/verify-darwin.py` checks it on macOS before it runs the gates.

## Releases

A release of the compiler is the compiler as a program of each of the four
targets, each alone in an archive whose bytes depend on the compiler only,
so the same source gives the same sums on any machine
(`scripts/release-compilers.py`). The workflow *Native compiler release*
builds the archives on Linux, then on a machine of each target takes the
compiler out of its archive and has it compile its own source, which must
give the archive's compiler again. Only then are they published, as a
prerelease under a `native-compiler-` tag. These are what `native/` builds
from; they are not the `alchem` people install.

`alchem` holds the compiler as a module, compiled from the same source by
the compiler that builds it (`scripts/build-alchem.py`). The workflow
*Release* builds it for the four targets from the pinned compiler, with
neither Go nor Rust, and runs each on a machine of its own target before
publishing ([releasing](../../docs/releasing.md)).

## The seed

Before there was a release, A0 was made from the source by the Go
compiler's frontend (`adapters/alchem`) and a backend written in Rust
(`implementations/rust`). That path is kept so that the first stage can
still be made without a released compiler:

```sh
mise install && mise run fetch && mise run fetch:seed
python3 scripts/verify-quick.py --seed
```

The nightly run of CI makes the compiler from the seed and requires that
it is, byte for byte, the one made from the pinned release. Nothing else
uses Rust, and a build uses neither Go nor Rust.

## What is not self-hosted yet

- **The gates** compare against the Go compiler, so running them needs Go
  ([architecture](architecture.md#what-go-and-rust-are-still-for)).
- **The builds and the gates are run by Python** (`scripts/`, `harness/`).
  Python does not take part in compiling: it puts the compiler's source
  together, starts the stages and compares their bytes.
- **Windows on ARM64** has no compiler of its own; the x64 program runs
  there.
