# Standalone Alchem-written arithmetic compiler

Build bootstrap tools and the compiler with `bash scripts/build-native.sh`, or
use existing tools with `python3 scripts/bootstrap-alchem-compiler.py`. Override
--frontend, --backend and --output to select paths. Bootstrap uses the pinned
frontend and either native backend once. Output replacement is atomic, 0700 and
preserves existing bytes if bootstrap fails. Source/bootstrap-tool overwrite is
rejected. A writable destination directory must already exist.

The saved Linux x86-64 executable reads a new source expression from stdin on
each invocation, writes binary ELF to stdout and exits 0. It runs with an empty
PATH, with no subprocess or host interpreter. Example:

```sh
printf '(5+2)*6\n' | build/native/alchem-arithmetic > /tmp/program
chmod 700 /tmp/program
/tmp/program
echo "$?"  # 42
```

The shell creates the file and sets its mode. The compiler writes bytes only; it
does not create/chmod/atomically replace output files. Shell redirection can
truncate an existing file even when compilation fails. Use a temporary file and
rename after a successful compilation when preservation is needed.

Input: 0..128 bytes through EOF, ASCII decimal checked signed-i64 literals,
whitespace, unary +/-, binary +,-,* and parentheses. Precedence/associativity,
wrapping arithmetic and nesting limit 16 follow expressions.md. The result must
be 0..255; output is the complete 140-byte ELF described in encoder.md, whose
process exit is that result. Arithmetic is folded inside the Alchem compiler;
this is not general runtime arithmetic instruction selection. Identifiers,
functions, bindings, comments and full Alchem source are not accepted.

Empty/invalid expressions, invalid bytes, overflowed literals, excess nesting
and results outside 0..255 return no stdout, attempt exactly
`E_COMPILE: invalid expression or result outside 0..255\n` on stderr and exit 65.
Excess input uses the V10 input-limit error (65); read/write IO errors use 74,
arena errors 71, and native call/stack limits 70. Partial stdout on an IO failure
is not rolled back. The reader waits for EOF; there is no time limit.

The implementation is assembled from lexer.alc, encoder.alc and compiler.alc.
The bootstrap discards their module envelopes/smoke mains and combines function
bodies under one module. This avoids adding production imports or maintaining
duplicated component code. It does no runtime source parsing/evaluation or ELF
construction in Python/Go/Rust. Its explicit IR entry bridge reads bounded stdin,
calls the typed `compile_expression(bytes)->bytes` function, treats empty bytes as
source rejection, and writes the nonempty image. That convention is specific to
this compiler, not a general byte pipeline API. The bridge is implemented with
native syscalls, not an external runtime. General binary source APIs remain work.

Acceptance in harness/arithmetic_compiler.py bootstraps once per backend and
uses that same saved executable for all 327 valid runtime sources and 13
rejections. It checks ELF fields/code against an independent Python oracle,
executes every image, compares repeat bytes and Go/Rust compiler bytes, checks
permissions/failed-bootstrap preservation and runs with empty PATH. The 128-byte
bound is deliberately smaller than compiler source; self-compilation is pending.
