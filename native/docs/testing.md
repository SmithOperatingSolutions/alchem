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
| Fuzzing | nightly, on request; the gate `fuzz` on pull requests | `fuzz-compiler.py build/dev/A2 COUNT --seed S` (`.github/workflows/search.yml`) |
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

## Coverage

`alchem test -cover` reports the lines of the code under test that ran;
`-cover-functions` adds, for each file, how many functions ran and those
none of whose lines ran (`spec/alchem-testing-gen.md`). The aim is to
reach every function with a test, so that the native compiler needs no
other implementation to be trusted.

The compiler itself is one module of more than 1 MiB, which `alchem test`
does not take; `scripts/compiler-reach.py` builds the test that compiles
programs with it and prints the same report, file by file of
`implementations/alchem`:

```sh
bash scripts/linux-container.sh python3 scripts/compiler-reach.py build/dev/A2 --gates --jobs 4 --keep build/work/reach
python3 scripts/compiler-reach.py build/dev/A2 --search build/dev/alchem-upstream 2000 1   # the random search's cases
```

`--gates` runs the gates with a compiler that keeps every text it is given
and counts all of them (`--gates maps sets` only the gates so named): those
of `verify-quick.py`, `core_modules` and `core_tools` of the complete
suite, and with `--seed FRONTEND BACKEND` the gates that take the seed's
two as well. A text of more than 1 MiB, the compiler's own source and the
commands bundled with it, is left out and counted. The test asks what the
`alchem` command asks of the compiler: the program, why it is refused when
it is, and of one program in ten whether it would be taken.

The code for ARM64, macOS and Windows is reached only by a compiler for
them. `--others N` builds the test for each of the five systems and gives
the four others one program in N: the first table is Linux x86-64 alone,
the second every system together, and the functions listed are those that
no system ran.

On a Mac the gates that emulation fails stop early and count only what
they compiled until then: the figure to go by is that of a Linux x86-64
machine, which `.github/workflows/reach.yml` gives once a week and on
request (`--others 4`, with the seed's gates), as the job's summary and an
artifact.

What the gates did not reach of what a program can reach has programs of
its own in `harness/reached.py` (the gate `reached`), each with what the
pinned command prints for it. The report still lists functions that
compiling a program does not run, for four reasons:

- the ARM64 instruction encoders the compiler itself does not use
  (`a_eor`, `a_ret`, `a_csel` and others of `native-arm64.alc`):
  `harness/arm64.py` calls each and compares its words with the
  assembler's;
- the arithmetic and the SHA-256 written by steps for the seed's
  frontend, in whose place every other build has `native-fast.alc` and
  `native-sha.alc` (`nc_quot256`, the `sh_` functions of
  `native-macho.alc`, the decoder of `native-x86arm.alc`): the seed's
  build runs the arithmetic, and CI holds the compiler it makes to the one
  the pinned release makes. No check runs the SHA-256 by steps;
- forms of x86-64 code the translator to ARM64 has and the compiler does
  not write (`xa_carry_op`, `xa_add_image`): `harness/x86_to_arm64.py`
  translates instructions of its own;
- four for which no program was found: the lookups in a table that has no
  index yet (`nc_find_range`, `nd_find_range`, `ny_module_plain`) and
  where a quoted part of a regular expression with a byte that is no
  UTF-8 ends (`rx_qe`: such a source is refused before it).

## Fuzzing

`scripts/fuzz-compiler.py COMPILER COUNT --seed S` asks of the compiler
what no other compiler is needed to judge. A program of the gates with a
few small changes, which is mostly no program any more, must be taken
(status 0, an executable) or refused (status 65, nothing): any other
status, a signal, more than two minutes or more than 2 GiB is a failure.
A program made with what it prints (thousands of bindings, long sums,
nested conditions, many functions and clauses, long lists) must be taken,
twice alike, and print that. The cases of a seed are the same every time;
`--keep DIR` writes those that fail, a changed one made smaller first.

The gate `fuzz` runs 2,250 cases of one seed and the texts of
`harness/fuzz-cases.json`, each of which once ended the compiler. Every
night `.github/workflows/search.yml` runs 500,000 with the date as the
seed. A case that fails is mended in the compiler and its text added to
`fuzz-cases.json`.

The compiler ends with status 72 and says nothing when it writes a
position that is -1 into a record. `scripts/compiler-where.py` says where:

```sh
python3 scripts/compiler-where.py build/dev/A2 build/fuzz/000123.alc --built build/work/where
```

It builds, in a few seconds, the compiler that is traced (its source with a
function `native_traced`: `spec/alchem-failures.md`, "Bytes"), gives it the
text, and prints the reason and the functions that led there, each with its
file and line in `implementations/alchem`. The nightly job does so for
every case that failed and keeps what it printed with the cases.
