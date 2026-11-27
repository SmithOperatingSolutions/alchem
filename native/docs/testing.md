# Testing

How to check a change to `native/` so that the answer is the one CI gives.
The gates need a real Linux x86-64 machine: emulated x86-64, as the
container is on Apple silicon, fails a third of them whatever the change
(*Emulation*).

## Before a pull request

On Linux x86-64, natively or in the development container:

```sh
bash scripts/check.sh           # everything, as a pull request's CI checks it
bash scripts/check.sh maps      # only the gates whose names match
mise run linux:check            # the same in the container
```

On a Mac with Apple silicon:

```sh
bash scripts/verify-arm64.sh            # the ARM64 compiler's gates, natively, about nine minutes
```

and the pull request's CI is the check of the x86-64 gates. `verify-arm64.sh`
leaves out `boolean_library`, `lists` and `options`, which trace a process
by its x86-64 registers. `check.sh`
stops at once on emulated x86-64 rather than report failures that are not
the change's (`ALCHEM_CHECK_EMULATED=1` runs it anyway).

`scripts/check.sh` runs what the pull request jobs *x86-64* and *Derived
files* of `.github/workflows/native.yml` run, with their settings:

1. the pinned Go command (`build/dev/alchem-upstream`), the reference every
   gate compares against;
2. the fixpoint from the pinned release (A1 = A2) and the gates
   (`verify-quick.py --jobs 4`, 14 GiB a gate);
3. the seed (Go frontend, Rust backend) makes the compiler the pinned
   release makes, byte for byte;
4. every derived file is what its generator makes (`verify-derived.py`).

On a Linux x86-64 machine `bash scripts/check.sh` runs the same without the
container. A change to `check.sh` or to those jobs is made to both.

## What else CI runs

| CI job | When | Locally |
|---|---|---|
| ARM64 | pull requests | CI runs `verify-quick.py arm64` on an ARM64 runner; on a Mac, `bash scripts/verify-arm64.sh` runs the ARM64 compiler's gates in a native ARM64 container |
| macOS ARM64, 4 parts | pull requests | `python3 scripts/verify-darwin.py build/dev/alchem-compiler-macos` on a Mac, after building it ([README](../README.md#macos-arm64)) |
| Windows x64 | pull requests | on Windows only ([spec/windows.md](../spec/windows.md)) |
| Complete suite | nightly, on request | `mise run linux:verify` (`verify-local.sh --with-source`) |
| Random search | nightly, on request | `generate-program-cases.py build/dev/alchem-upstream --search build/dev/alchem COUNT --seed S` (`.github/workflows/search.yml`) |

A pull request whose inputs passed these jobs before is not checked again
(`.github/scripts/native-verified.sh`).

## One build directory per machine

In the container `native/build` is `native/build/container-amd64` (or
`container-arm64`) of the host (`scripts/linux-container.sh`). A compiler,
the pinned command or anything else built for one machine is never found
by another, and the host's own `native/build` holds only what the host
built. To start from nothing, remove that one directory.

What persists between runs, and so can make two runs differ:

- `build/dev`: the compiler stages and the pinned Go command, made again
  when the source or the pin changes;
- `build/alchem`: `alchem` programs, kept by the bytes of the compiler and
  the source that made them;
- the container's volume `alchem-native-cache-ARCH`: Go's and Rust's build
  caches and `$HOME` (with `alchem run`'s program cache,
  `~/.cache/alchem/programs`).

## Memory and time

A runaway program can take the whole machine. Everything the gates run goes
through `scripts/limited` (`ALCHEM_MEMORY`, `ALCHEM_SECONDS`): a systemd
user scope on Linux, `scripts/bounded.py` on macOS, which has no other
ceiling. Run a compiler or a compiled program by hand the same way:

```sh
ALCHEM_MEMORY=4G ALCHEM_SECONDS=300 scripts/limited build/dev/A2 < program.alc > program
```

In the container `ALCHEM_CONTAINER_MEMORY` caps everything at once
(`verify-arm64.sh` sets 12g).

## Emulation

On Apple silicon the x86-64 container runs under Rosetta. The compiler
builds there and reaches its fixpoint, and most gates pass, but about thirty
fail whatever the change: ptrace fails (EIO), strace's fault injection does
nothing, a program under an address-space limit stops Rosetta itself
("Could not mmap data for the VMTracker slab allocator"), and some floats
print with a digit more. `verify-arm64.sh` runs at the machine's own speed
and checks the ARM64 compiler. A skip is not a pass: when a gate cannot run
where you are, CI is the check.

## Flakes

A check that passes and fails on the same input is a defect, not bad luck.
Run it again with the same seed and the same `--jobs` until the rate is
known (`--repeat` where the script has it), and fix the cause.
