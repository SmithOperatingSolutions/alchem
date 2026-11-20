# Self-hosted native Alchem source profile

The Alchem-written compiler rebuilds itself for this bounded profile. Build it
with scripts/build-native.sh; the published build/native/alchem-compiler is A3,
not the Go/Rust seed. See docs/self-hosting.md for source/stage hashes and gates.

```sh
build/native/alchem-compiler < examples/alchem-byte-compiler-demo.alc > /tmp/demo
chmod 700 /tmp/demo
/tmp/demo
echo "$?"  # 42
```

Input is source on stdin, output complete Linux x86-64 ELF on stdout. Shell file
creation/chmod is outside the compiler. Redirection is not atomic preservation.
The builder validates native rebuild equality and smoke before publishing;
individual publication files are atomic, not a multi-file transaction.

## Syntax and checking

- One defmodule UppercaseName do ... end, whitespace and # line comments.
- Up to 65535 functions, public def or private defp, any order. One name may
  have several numbers of parameters, default arguments, clauses with patterns
  and guards, and forms for arguments of different types
  (alchem-clauses.md). Exactly one public main() do with no parameters/return annotation.
- Helper parameters/returns are integer, bytes, string, boolean, nested options/tuples/results,
  general lists/maps or typed callback signatures, up to six
  arguments. Calls check each argument and declared return type; main cannot be
  called. Direct, forward, self-recursive and mutually recursive calls work.
- Checked signed-i64 decimal literals, unary signs, parentheses and the
  operators of alchem-operators.md, which fail on overflow as the pinned
  language does (a compiler entry keeps wrapping +,-,*).
  Minimum i64 requires immediate unary minus. Arithmetic and calls emit native
  instructions, not compile-time function evaluation. Small literals may use a
  compact immediate; larger values use exact native decimal construction.
- Bindings infer full structural types. No rebinding or shadowing in an active scope;
  at most 16 live parameter/local slots per lexical path. Names use complete spans.
  `name: type = value` declares the binding's type; the value must be compatible.
- If values preserve full structural types; both branch types must unify. Conditions
  require boolean values; integer comparisons (==,!=,<,<=,>,>=) return boolean. Nested branches and branch-
  local bindings work; their locals cannot escape or cross branches. Every
  definition and both branches are checked, even unused/untaken ones.
- Ordinary main ends in System.halt(integer), or terminal if paths ending in
  halt, with earlier typed bindings and IO.puts(string)/IO.write(string) statements allowed. `return value` leaves any
  other function early (alchem-clauses.md); main has no return. Full main status must be 0..255 at runtime.
- Byte literals b[...] have up to128 integer expressions, checked0..255 at
  runtime, and use the explicit bytes type. Constant-byte copies preserve fresh
  allocation semantics. General [...] literals instead store full64-bit elements
  with list[T] type, including signed integers, strings and nested values.
- `b"..."` is a byte literal in base64 (RFC 4648 alphabet, `=` padding only in
  the last group) of up to 4096 characters, also of type bytes
  (`nl_coded_value`); the seed adapter turns it into a list. It holds the
  library's packed text in a third of the characters `b[...]` takes. A
  seed-built compiler reads a literal of 768 characters but not one of 1,024
  (its calls nest 1,024 deep), so scripts/generate-prelude.py writes 512.
- General immutable collection operations, maps and typed named-function
  iteration are specified in alchem-collections-profile.md. Byte-buffer APIs keep
  their separate alchem-byte-profile.md contract.

String syntax, concatenation, byte_size and main-body IO.puts are specified in
alchem-string-profile.md.

Stored booleans, not and predicates are specified in alchem-boolean-profile.md.
Logical and/or and typed option cases are now specified in alchem-boolean-profile.md
and alchem-options-profile.md. Additional library APIs are in
alchem-library-profile.md. Structural types are specified in alchem-structural-types.md. Imports, actors, macros, externs,
foreign runtime integration, general mutation and unlisted library APIs are outside
this profile. Integer/byte program fixtures also pass the pinned upstream parser/
type checker/native oracle; empty-list fixtures provide the context it requires.
The new string/output suite uses independent byte-stream and decimal oracles.

## Explicit compiler entry

A public native_compile(source: bytes): bytes helper opts the
module into compiler-entry IO. It must have exactly that signature; a private or
incorrectly typed marker is rejected. A void main/0 remains for upstream syntax
compatibility, but process entry calls native_compile instead. The compiler's
assembled source uses a wrapper calling nc_compile. This source convention is
explicit and reserved; it is not arbitrary runtime entry selection.

The entry reserves a 16 GiB RW arena lazily (or the largest half of that the system grants,
down to 1 GiB), reads up to 16776191 bytes through EOF with one-byte
lookahead, calls the typed function, writes a nonempty result completely and
exits 0. Empty result attempts E_COMPILE: invalid or unsupported Alchem function
program plus LF and exits 65, with no stdout. Oversized input reports
E_RUNTIME_INPUT: input exceeds byte limit plus LF/65. Read/write failure reports
the corresponding E_RUNTIME_IO message/74. Short reads/writes accumulate; EINTR
retries; zero-progress writes and EAGAIN fail. Default SIGPIPE handling remains.
There is no timeout/rollback of partial output. Diagnostic writes are best effort.
All entry instructions/data are emitted in Alchem; no host wrapper patches ELF.

## Bounds and storage

Source<=16776191 bytes, functions<=65535, list elements<=128, body tokens<=1024,
identifier/numeric runs<=64 bytes. Unary/parenthesis/if expression nesting and
successive operators per sum/product level cap at 16. Main binding/branch traversal
has a combined budget16. Comment lines use at most 64 chunks of 16 bytes; balanced
ignored-token traversal handles long whitespace/comment sequences within input
bounds. Each function has at most 65535 code bytes and each branch at most 16KiB;
total function code<=1GiB; function lengths and the image size are 32-bit fields
(source-capacity.md). In practice the 4,194,303-byte source limit or the 16 GiB
arena is reached first: a dense source gives about 6 code bytes per source byte
and charges about 870 arena bytes per source byte.

Batched declaration/body/list traversal and balanced name search bound call stack
growth. List span collection compiles each expression once in order. Balanced
code bundles retain function lengths; address layout does not recompile bodies.
Native Enum.slice provides one bulk copy rather than recursive copying.

The compiler's own execution budget is 16 GiB (seed IR V11 and generated compiler
entry), reserved lazily so only touched pages cost memory. Every native program,
the compiler included, runs on its own stack mapping of 1 GiB reserved the same
way (the largest half of that the system grants, down to 1 MiB); each function
checks the stack pointer against its limit, kept just below the initial stack
pointer, and counts itself among the active calls in R15, at most 100000 below
main as in the pinned runtime.
A native self-build charges about313 bytes per source byte. The function
table is no longer rebuilt per declaration (it charged about250MB at4096
functions; alchem-modules.md): a program charges about 40 KB for each small
function, 2.3 GB at 60,000. Tracing measured 21,719,016 charged bytes for A0
building A1 and 34,536,120 for native rebuilds. Resource failures are explicit; these
bounds do not promise arbitrary programs inside the lexical size cap avoid every
resource limit. Ordinary generated programs retain 4 MiB; details below.

## ELF and private ABI

| File range | Contents |
| --- | --- |
| 0..127 | ELF/program header and padding |
| 128..1151 | Process/compiler entry and padding |
| 1152 onward | One absolute u64 address per table slot: user functions, then shared runtimes |
| 1152+8*slots onward | Functions in declaration order, with inline constant data, then shared runtimes |

ET_EXEC/AMD64/little endian, entry 0x400080, one RX PT_LOAD at 0x400000, alignment 4096,
no interpreter/sections. Sizes/addresses and relative lengths use bounded u32
encoding inside 64-bit ELF fields. This is not arbitrary linking/64-bit layout.

RAX returns integers, canonical booleans or typed record/function pointers. RDI,RSI,RDX,RCX,R8,R9 pass typed
the first six arguments and the stack the rest, which stay there until the call
returns; callees save them into an RBP frame: 16 slots, then the position of
the statement being run and the frame's closure records
(`spec/alchem-traces.md`), then as many further slots as the function's code
reaches (250 was the most; now what the source binds). A slot past the sixteenth is addressed with a
32-bit offset (from the 255th on behind a marking instruction, `nc_slot`), and the frame's size is read off the function's finished code. Expression
stack temporaries preserve left-to-right evaluation. R11 addresses the immutable
function table. R12/R13 are arena bump/end; R15 active calls. No external System V
ABI, external calls or unwinding is supported.

Ordinary main status >255 or a call past the stack limit exits 70 without diagnostics;
a call past the depth limit ends the program with status 2 and a trace. Byte value,
slice count and allocation errors use private statuses 72/73/71. Compiler entry IO
errors are the messages above; seed compiler execution retains bootstrap IR
runtime diagnostics. Arithmetic mode and raw IR versions retain their contracts.

The current 89,611-byte/305-function distribution closes over this profile and
rebuilds identically through A3. Future language changes must retain those gates
and update docs/compiler-profile-inventory.md against the actual source.

Source/input capacity is now 4,194,303 bytes with24-bit source metadata; see
[source capacity](../spec/source-capacity.md) for packet/layout boundaries.

## Blocks and statements

A function body, a branch of `if`, a `case` arm and the body of `fn` are
blocks: statements, then the value the block ends in if it ends in one
(`native-blocks.alc`). The rules are the pinned compiler's:

- A statement is an output call, a binding, a pattern binding, `System.halt`
  or `System.stop`, or a call whose value is dropped. Any other expression as
  a statement is rejected, except that a block's last line may name a variant
  (`ok({})`, `none`).
- `if` and `case` are statements when their value is not used: `else` may be
  left out, and the branches need not end in values or agree in type. As a
  value every branch must end in one and `else` is required.
- `with` and `for` are statements or values too (`alchem-comprehensions.md`).
- `main` is a block of statements. Reaching its end exits 0; `System.halt`
  ends the program wherever it stands, in `main` or in another function.
- A `fn` whose body ends in a statement returns the empty tuple.
- `Enum.each(items, function)` calls the function with each element of a list
  or each entry of a map, in key order, and leaves no value.

Statements are joined in runs of doubling length, so the code of a body of n
statements is copied about n log n times, not n squared; 20,000 output
statements compile in about a second.

## String and collection literals

- A quoted string may hold `#{expression}`: the value of a string, integer or
  boolean expression as text, joined to the text around it; `\#{` is the two
  characters. Any other type is rejected, as upstream rejects it.
- A heredoc is `"""` at the end of a line up to `"""` at the start of a later
  one. Each line loses the closing line's indentation; escapes and
  `#{expression}` apply and quotes are text.
- A string literal is not capped at 128 bytes, and a list or map literal
  takes 4096 elements (it was 128); each element is still copied into the
  list of elements as it is read, which sets that bound.
- `System.halt` with a status outside 0..255 ends the program with
  `exit status must be between 0 and 255` and the active calls, status 2.

- Expressions and blocks nest 200 deep and a chain of one operator takes 4096
  operands (both were 16).

`harness/literals.py` checks these against the pinned compiler's results.

