# Compiler components written in Alchem

Current status: the Alchem-written compiler now rebuilds itself for its native
integer/byte profile. Build-native publishes A3, assembled source and a manifest;
A1/A2/A3 are identical and pass the source suites. See docs/self-hosting.md for
proof/reproduction. The component history below remains useful for API/oracles.


`lexer.alc` is the first small component of the future Alchem-written compiler:
a bounded ASCII expression frontend implemented entirely in Alchem. It
uses integer functions, signed comparisons, nested conditionals and bounded
recursive ordinal/byte-buffer traversal, compiled to
native code by the current bootstrap. It does not implement the complete production Alchem lexer,
read source files, or make the compiler self-hosted.

Its profile defines these numeric categories:

| Code | Category |
| --- | --- |
| 0 | Unrecognized input |
| 1 | Space, tab, LF or CR |
| 2 | ASCII letter or underscore (identifier start) |
| 3 | ASCII digit |
| 4–8 | +, -, *, (, ) respectively |
| 9 | EOF sentinel -1 |

Other negative values and non-ASCII inputs return 0. These are preliminary native
profile categories, not a claim to match production Alchem's full Unicode lexer.
Identifiers begin with a letter/underscore and continue with letters, underscores
or digits. Integers are maximal decimal digit runs; signs remain separate tokens.

```sh
bash scripts/build-native.sh
build/native/alchem-native --source implementations/alchem/lexer.alc --output /tmp/lexer-smoke
/tmp/lexer-smoke
```

The smoke test exits 0. Full verification generates a replacement test main and
checks all 128 ASCII values plus -2, EOF, 128, 255 and maximum i64 against an
independent Python classification oracle. The original component is not modified.
The generated program is built/executed through Rust, compared byte-for-byte
with the Go reference, and checked for deterministic output.

The recursive `count_digits(first, last)` helper traverses an inclusive ordinal
range; its smoke test verifies 10 digits across ASCII 0..127. This exercises
native recursive calls. `count_buffer_digits(values, index)` traverses actual
immutable byte data; `byte_at` returns EOF (-1) for negative/out-of-range cursor
positions. `skip_spaces` and `scan_digits` return the exclusive end cursor.
Their smoke/oracle cases include NUL, 255, EOF, all-ASCII digit counting,
whitespace-only buffers and digit spans ending at EOF.

These recursive helpers share the native 256-call/1 MiB active-frame budget;
they are not unbounded input scanners.

The pull-style token API exposes token_start, token_kind and token_end, returning
byte spans without copying source text or allocating a token collection.
Whitespace is skipped. token_error distinguishes invalid bytes, invalid cursors
and input longer than 128 bytes. Invalid bytes have a one-byte span; callers may
advance to token_end to recover. EOF has an empty span at length. token_count
counts a valid stream; first_error reports the exact first invalid byte offset.
See [the lexer contract](../../spec/lexer.md) for all return codes and limits.

For `[32,97,95,49,32,43,32,48,48,52,50]` (ASCII ` a_1 + 0042`):

| Token | Kind | Start | Exclusive end |
| --- | --- | --- | --- |
| a_1 | 2 | 1 | 4 |
| + | 4 | 5 | 6 |
| 0042 | 3 | 7 | 11 |
| EOF | 9 | 11 | 11 |

The shared lexer oracle tests all 256 single-byte inputs, 64 seeded byte streams,
every cursor in those streams, maximal spans, error offsets/recovery, EOF and
exact 128/129-byte boundaries. Expected spans are calculated independently in
Python, compared as full i64 values inside Alchem, then executed through both
backends with deterministic byte-identical output. Whole-stream
summaries remain separate probes to keep failures easy to locate.

This expression profile recognizes identifiers, integers, +, -, *, (, ).
Keywords, integer conversion/overflow, comments, strings and the rest of production
Alchem syntax remain future work. It is a bounded expression profile, not the complete production frontend.

Checked decimal conversion now supports the full signed-i64 range, explicit
nondigit/span/sign/size/overflow errors and caller-selected fallback values.
The arithmetic parser/evaluator handles unary signs, parentheses, left-associative
+/- and higher-precedence multiplication. Arithmetic wraps, while literals are
checked. Syntax nesting is bounded to 16 and input to 128 bytes. See
[integer literals](../../spec/integer-literals.md) and
[expressions](../../spec/expressions.md) for exact semantics.

The independent integer oracle runs 496 cases in 135 programs; the expression
oracle runs 354 programs against Python AST/arbitrary-precision calculations.
Values are compared as full i64 inside Alchem. All 354 expression probes now
use source main: V6 checks process status at runtime, so the former compile-time
halt-proof/library-probe workaround is gone. Native input/depth/resource limits
remain in effect; IO and arbitrary language features are still unsupported.

Next components require declarations/types/names and compiler semantics,
writable storage, strings and file IO
to turn source bytes into tokens and eventually parse and compile the compiler's
own Alchem source. See docs/self-hosting.md for the bootstrap sequence.

`encoder.alc` now constructs complete small Linux x86-64 ELF executables in
Alchem: ELF/program headers, padding and a 12-byte exit sequence. Every image byte
is produced by Alchem functions using computed lists and concatenation. The
oracle parses headers independently and executes all 256 valid images; four
out-of-range i64 immediates fail. No host-generated ELF wrapper remains.

```sh
python3 scripts/emit-alchem-executable.py --status 42 --output /tmp/exit42 --save-emitter /tmp/alchem-emitter42
```

The helper uses bootstrap tools to compile/run the emitter and save its output
unchanged. The retained configured emitter itself runs with an empty PATH and
can reproduce that image with no frontend/backend/host compiler installed.
It is not yet a general source compiler or self-hosted. See
[the complete small-target contract](../../spec/encoder.md) for its 140-byte
layout, temporary IR export bridge and remaining work.

The components now form a reusable arithmetic compiler through compiler.alc:

```sh
bash scripts/build-native.sh
printf '6*7\n' | build/native/alchem-arithmetic > /tmp/answer
chmod 700 /tmp/answer
/tmp/answer
echo "$?"  # 42
```

Bootstrap once; subsequent invocations accept new source from stdin with no
bootstrap tools or interpreter on PATH. Alchem performs parsing/evaluation and
constructs every ELF byte. The bootstrap adds only the native IO entry bridge.
This bounded arithmetic language is not the Alchem subset needed to rebuild the
compiler itself. See spec/arithmetic-compiler.md and docs/self-hosting.md.

`native-compiler.alc` is now the Alchem-written source compiler for the bounded
integer/function profile. Build-native also creates alchem-compiler, which takes
new Alchem modules on stdin and emits actual native arithmetic, helper calls,
recursion, scoped branches and complete ELF output. It has its own token spans,
function-signature table, local environments, checked literal code generation,
branch encodings and function-address layout. It does not invoke the pinned
frontend at runtime. See spec/alchem-source-profile.md and
docs/compiler-profile-inventory.md for supported syntax and self-hosting gaps.

The same compiler now supports list[integer] byte parameters/returns, inferred
typed locals, matching branch result types, checked computed lists and
Enum.count/at/concat. native-runtime.alc emits its allocation/packing/indexing/
concat code entirely in Alchem, with a separate bounded RW/non-executable arena.
The byte demo exercises helper returns, branching and immutable live references.
See spec/alchem-byte-profile.md. Batched traversal, saved lengths, native slicing and bounded u32 metadata now
support self-compilation. Full production-language compatibility remains separate.
