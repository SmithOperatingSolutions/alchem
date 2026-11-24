# Architecture

`native/` holds a compiler for Alchem written in Alchem, the library it
compiles into a program, and `alchem`, the command line people install. A
program is compiled from its source straight to an executable of its target:
there is no Go, no C compiler, no assembler and no linker in the path, and
the compiler runs with an empty `PATH`.

This is the map. Each part has a file in `spec/` that says exactly what it
does and where it still differs from the Go compiler of this repository.

## The parts

| Part | Where | What it is |
| --- | --- | --- |
| The compiler | `implementations/alchem/native-*.alc` | Reads one source from standard input and writes an executable to standard output |
| The library | `library/*.alc` | `Enum`, `String`, `File`, `Process`, `TLS` and the rest, written in Alchem and compiled into a program that uses them |
| The front end | `tools/alchem-lexer.alc`, `alchem-parse.alc`, `alchem-check.alc`, `alchem-typing.alc`, `alchem-format.alc` | A second reading of a source file that gives the tokens, the tree, the formatter and the messages of the Go front end |
| The commands | `tools/alchem.alc` with `alchem-bundle.alc`, `alchem-fetch.alc`, `alchem-guide.alc`, `alchem-lsp.alc`, `alchem-alx.alc` | `alchem`: one program that holds the bundler, the front end and the compiler |
| The gates | `harness/*.py`, `scripts/verify-quick.py`, `scripts/verify-darwin.py` | Programs with the Go compiler's output, status and failure trace recorded, run against the compiler |

## The compiler

The compiler's source is the files of `implementations/alchem` put together
into one module by `scripts/bootstrap-alchem-compiler.py` (`source_text`):
about 2.9 MB and 4,000 functions. The compiler compiles from the source
bytes as it reads them. It keeps no syntax tree: each function is parsed,
checked and turned into machine code in one pass, and the image is laid out
when every function is known.

Each file holds one concern, and the name says which:
`native-patterns.alc`, `native-clauses.alc`, `native-generics.alc`,
`native-floats.alc`, `native-processes.alc`, `native-try.alc` and so on. A
file ending in `-data.alc` is generated: machine code assembled from a
reference in `spec/*.s`, or tables, written by a `scripts/generate-*.py`.

A program the compiler refuses gets one message from it. The place and the
reason a person reads come from the front end (below), which `alchem` runs
first.

## One source, four targets

The target is a constant of the build, not something passed through the
compiler's functions. Two functions of the source say which compiler it
is, and a build script changes them before compiling:

| Target | Constant | Built by | Programs |
| --- | --- | --- | --- |
| Linux x86-64 | as in the source | the build itself | Static ELF, system calls made directly |
| Linux ARM64 | `nc_arm()` 1 | `scripts/build-arm64.py` | Static ELF |
| macOS ARM64 | `nc_arm()` 3 | `scripts/build-arm64.py --darwin` | Position-independent Mach-O that calls libSystem, with an ad-hoc signature the compiler computes |
| Windows x64 | `nc_win()` 1 | `scripts/build-windows.py` | PE, over kernel32 and Winsock |

Every compiler takes one branch everywhere, so adding a target leaves the
others' output byte for byte what it was.

**ARM64** is a translation. The emitters, and the passes that read the code
they made, stay those of x86-64: the ARM64 compiler builds each function's
x86-64 code and translates it instruction by instruction before the image
is laid out (`native-x86arm.alc`, [spec/arm64.md](../spec/arm64.md)). The
runtime routines that are machine code of their own are assembled for ARM64
separately.

**macOS** builds on the ARM64 compiler. macOS loads a program wherever it
chooses and allows no direct system calls, so the code makes its addresses
from where the image was loaded and reaches the system through libSystem
([spec/darwin-arm64.md](../spec/darwin-arm64.md)).

**Windows** runs the Linux x86-64 image at the same addresses. Every system
call instruction is replaced by one of the same length that faults, and a
layer in the program handles the fault and does the call's work with
kernel32 and Winsock ([spec/windows.md](../spec/windows.md)).

## The operating-system layer

The library reaches the system through a handful of primitives, the module
`Sys`, which the compiler compiles only inside the library: a system call
with its arguments, the address of a string, reads and writes of memory
([spec/alchem-system.md](../spec/alchem-system.md)). Files, directories,
the environment, external programs, sockets and time are written in Alchem
over them (`library/File.alc`, `System.alc`, `TCP.alc`, `Sys.alc`),
following the Go runtime call by call so that results and error texts are
the same.

The library is one for every system. A function that must differ has a
branch for the system, and a program carries only the branches of the
functions it uses.

## What a program holds

- **The code of the functions it uses.** The library is appended to a
  program as source and compiled with it; a function nothing reaches is
  left out ([spec/alchem-library-profile.md](../spec/alchem-library-profile.md)).
- **Memory that is given back.** A collector that marks without moving
  values, taking every word that could be an address for one
  ([spec/alchem-memory.md](../spec/alchem-memory.md)).
- **Processes.** A program is one thread. Its processes are coroutines of
  that thread, each with a stack of its own, written in Alchem over five
  operations the compiler gives the library
  ([spec/alchem-processes.md](../spec/alchem-processes.md)). A program that
  uses none of the process modules holds none of this.
- **Failures as the Go runtime reports them**: the status, the message and
  the trace with each frame's file and line
  ([spec/alchem-failures.md](../spec/alchem-failures.md),
  [spec/alchem-traces.md](../spec/alchem-traces.md)).
- **Networking and TLS** written in Alchem over sockets
  ([spec/alchem-network.md](../spec/alchem-network.md),
  [spec/alchem-tls.md](../spec/alchem-tls.md)).

## The front end and `alchem`

The compiler opens no files and reads one source. `alchem` is what makes a
project of files into that source and gives a person the messages:

1. **The bundler** follows the imports of the entry file and writes every
   module once, with a header that says which file each line came from, so
   a failing program names its file and line. Packages are fetched and
   locked without Go ([spec/alchem-modules.md](../spec/alchem-modules.md)).
2. **The front end** reads each file as the Go front end does: its lexer's
   tokens, its parser's tree, the checker's messages with line and column
   ([spec/alchem-front-end.md](../spec/alchem-front-end.md)). `alchem check`,
   `alchem fmt` and the language server are built on it.
3. **The compiler** is inside `alchem` as an ordinary module, the same
   source that was built into the compiler that built `alchem`, and is
   called rather than run (`scripts/build-alchem.py`).

So `alchem build`, `run`, `test`, `check`, `fmt`, `new`, `lsp`, `alx` and
the commands that print documentation are one executable that needs nothing
else installed ([spec/alchem-commands.md](../spec/alchem-commands.md),
[spec/alchem-testing-gen.md](../spec/alchem-testing-gen.md)). Releases ship
it for the four targets.

## Verification

The Go compiler of this repository is the reference. A gate holds programs
with what the Go compiler's program printed, its status and its failure
trace recorded, and requires the same of the native compiler's program;
where the two are known to differ, the spec of that part says so and why.

- `scripts/verify-quick.py` builds the compiler from the pinned release,
  requires that it makes itself again (see
  [self-hosting](self-hosting.md)), and runs the gates in parallel on
  Linux x86-64.
- `scripts/verify-darwin.py` runs the gates on macOS with the compiler for
  macOS; CI runs the Windows compiler on Windows and the ARM64 one on
  ARM64 and under emulation.
- `scripts/upstream-examples.py` runs every example of the syntax and
  library references through both compilers.

Python runs the builds and the gates. It is not part of compiling a
program.

## What Go and Rust are still for

Building the compiler and `alchem`, and compiling a program, need neither.

- **Go** is needed to run the gates, because the reference they compare
  against is the Go compiler: the programs in `scripts/pinned-*` print the
  Go lexer's, parser's, formatter's and checker's results from the module
  of the release their `go.mod` names, and several gates run the Go
  `alchem` beside the native one. Generating the recorded data
  (`scripts/generate-*-cases.py`, `scripts/generate-guide-data.py`) needs
  it too.
- **Rust** is needed only for the seed: the first stage made from the
  source by the Go frontend (`adapters/alchem`) and a Rust backend
  (`implementations/rust`), as it was before there was a released
  compiler. The nightly run of CI makes it and requires that the compiler
  from the seed is, byte for byte, the one from the pinned release.
