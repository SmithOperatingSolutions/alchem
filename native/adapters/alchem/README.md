# Pinned Alchem frontend adapter

This experimental adapter uses the upstream parser and semantic analyzer pinned
to `0b73f880b108fe5548f79896a91a59a0aa571fda`, with the pseudo-version/checksums
in go.mod/go.sum. It never modifies upstream source or invokes upstream Go
codegen. It needs Go 1.27+ to build; the native Go reference remains Go 1.23+.

`--program` lowers public parameterless void main and supported integer/byte-returning helpers
to V6 (V7 for literal IO.puts; V8 for concatenation/byte returns; V9 for computed byte lists). A normal main completes with zero; a final/terminal-branch System.halt
produces the actual computed native result. The process stub checks the full
value is 0..255. Invalid status writes `E_HALT_STATUS: expected status 0..255\n`
and exits 70. No source function is interpreted to prove its result at compile
time; expensive evaluator mains no longer need library-mode workarounds.

Supported source includes wrapping +, -, *, integer locals/aliases, direct
integer helpers with up to six named integer/byte-list parameters, signed
comparisons, boolean locals/not, typed if values and terminal if statements.
Branch locals remain private and both paths are lowered/validated. Conditional
nesting is limited to16, functions to256 (V11 permits512), native active calls to256 and charged
active frames to 1 MiB. There is no total runtime instruction/time budget.

Byte data is a deliberately restricted immutable list[integer] subset: literal
elements 0..255, named list parameters, aliases/conditional values, Enum.count
and three-argument Enum.at with negative indices/defaults. Empty lists need an
expected type. Literal storage is capped at 1 MiB each / 4 MiB including headers.
List tails, general lists, strings and mutation remain unsupported. Byte-list helper returns and two-argument
Enum.concat select V8 in program mode. Imports, defaults, destructuring, general IO, macros,
indirect/external calls, division, arbitrary early returns, nonterminal
statement-if, unless, and/or and loop syntax are also outside this profile.

`--function NAME` is the explicit parameterless integer library probe interface.
Its result remains the low byte of process status. Library lowering retains V1
arithmetic, V2 direct calls, V3 conditionals, V4 recursion and V5 byte profiles;
acyclic V2/V3 probes retain depth 64. Executable programs use V6–V9 with checked status.

The adapter emits deterministic JSON on stdout. Parse/type errors use E_SOURCE,
unsupported features E_UNSUPPORTED, arguments E_INVALID_ARGUMENT and file errors
E_IO. Rejected source emits no IR. Runtime status/resource failures happen only
when executing successful native output, not while compiling source.

```sh
(cd adapters/alchem && go mod download && go build -mod=readonly -o /tmp/alchem-source-probe .)
/tmp/alchem-source-probe --input examples/invoice.alc --program > /tmp/invoice.json
```

Build both prebuilt tools with `bash scripts/build-native.sh`; see
[the quickstart](../../docs/quickstart.md). Complete verification is
`bash scripts/verify-local.sh --with-source`, offline after dependency setup.
It runs both backends, 18 library probes, 73 executable-main programs, 13 native
runtime-error cases, 5 source rejections and the Alchem-written lexer/integer/
expression oracles. All 354 expression probes now use source main.
Set ALCHEM_FRONTEND_GO and GOPATH for a separate frontend toolchain/cache.

V7 supports one-argument IO.puts with a literal string in program mode. It emits
the literal's UTF-8 bytes plus one LF using complete native writes; helpers and
branches may print before later statements. String bindings/interpolation and
device/file overloads remain unsupported. No general string values or input are
added. Syscall output failure attempts E_RUNTIME_IO on stderr and exits 74;
partial output is not rolled back, and Linux signal behavior remains in effect.

V8 allocates a separate anonymous 4 MiB RW arena at process entry. Concatenation
returns fresh immutable byte data (at most 1 MiB payload), charging align8(length+8)
with process lifetime and no reclamation. Static literals stay RX and keep their
separate limits. Inputs, references and byte return values remain valid across
calls. Mapping/size/exhaustion failures attempt E_RUNTIME_ALLOC and exit 71.
Pure --function probes do not add runtime construction; use program mode.

V9 supports computed list[integer] elements in program mode: evaluate elements
left to right, then validate each full i64 is 0..255 and pack a fresh immutable
record. Invalid values (including formerly unsupported [-1]/[256]) fail natively
with E_RUNTIME_BYTE/exit 72, not modulo truncation. Computed packs have at most
4096 elements; already-valid literal byte lists retain static lowering/limits.
Byte validation precedes the arena-capacity check after operand evaluation.

The native profile now spells byte buffers bytes/b[...]. The initial seed adapter
translates those tokens to its existing list[integer] byte subset, preserving
strings/comments. Native self-rebuilds consume the saved source without rewriting.
This adapter does not lower native general lists, maps or callbacks; they are
implemented by the Alchem compiler. V11 permits512 functions for the larger seed;
older IR profiles keep256 and active calls remain256. The native profile reserves
bytes as a type name. Production Alchem is unchanged.
