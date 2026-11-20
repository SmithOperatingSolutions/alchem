# Upstream frontend boundary — pinned inspection and probe

Inspected production Alchem read-only at commit
[`0b73f880b108fe5548f79896a91a59a0aa571fda`](https://github.com/SmithOperatingSolutions/alchem/tree/0b73f880b108fe5548f79896a91a59a0aa571fda).
The native repository's adapter pins that revision with Go module checksums.
No production files, branch refs, workflows, or settings were changed.

| Upstream package/API | Role | Native adapter use |
| --- | --- | --- |
| `compiler/lexer` | Tokenization | Called indirectly by the syntax parser. |
| `compiler/syntax.ParseModule` | Single-file AST parsing with clause merging, without type checking | Parse a restricted executable or library probe. |
| `compiler/syntax.Analyze` | Type/semantic analysis and implicit-return normalization | Run with Library=true for function probes, false for real main. |
| `compiler/ast.Program`, `Function`, `Expr` | AST with source positions and assigned expression types | Inspect only the supported pure integer subset. |
| `compiler/syntax.Parse` | Checked single-file executable parsing | Not used: it enforces source main and handles a broader executable contract. |
| `compiler.Build*` | Project loading, extern binding, Go generation/build | Not used: it invokes Go's compiler backend. |

These package boundaries are exported; no production code needs to be copied or
edited to run the probe. The source module declares Go 1.27. The native Go
backend itself remains a separate Go 1.23 module; Rust is independent too.

The source language requires public executable main to have no parameters and
return void. Program mode preserves that contract and emits V6: normal completion
returns zero; a final/terminal-branch System.halt supplies the computed native
result. The process stub checks its full i64 value is 0..255. Invalid results
write the native-profile E_HALT_STATUS diagnostic and exit 70. The native error
message is not an exact copy of production Alchem's actor/runtime diagnostics.

The compiler never evaluates source main/helpers to prove status. This removes
the former 100,000-step/active-proof-depth limitation; all source paths still
undergo parsing, semantic checking, lowering and IR validation. Native resource
limits remain 256 active calls and 1 MiB charged frames, with E_RUNTIME_LIMIT
on failure. There is no runtime instruction/time budget.

Supported source: integer locals/aliases, wrapping +,-,*, direct integer/byte helpers
with up to six integer/byte parameters, signed comparisons, boolean locals/not,
if values and terminal if statements. Byte data is the restricted immutable
list[integer] literal subset (0..255) with aliases/conditionals, Enum.count and
three-argument Enum.at. Empty lists require an expected type. Branch locals
remain private, both paths are validated, and only the selected path executes.
Unsupported features include general lists/strings and list tails,
mutable storage, input/file IO, imports/macros, defaults/destructuring, indirect/external
calls, division, arbitrary early returns and nonterminal statement-if.

Explicit library probes retain V1–V5 and low-byte integer return behavior;
executable-main lowering uses V6, V7 for literal IO.puts, or V8 for concatenation/byte helper returns. The Rust source driver invokes
only its prebuilt frontend, validates the IR and emits ELF directly. It does not
invoke production Build, Go, Cargo, rustc or an external linker during source
compilation. Empty-PATH/sibling discovery, deterministic output, permissions,
output preservation and source-overwrite protection remain checked.

The Alchem-written component implements a bounded ASCII token scanner, checked
i64 decimal conversion and arithmetic parser/evaluator. All 354 expression oracle
programs now use ordinary source main, including previously expensive evaluator
and deep-boundary cases. This replaces no production frontend code. It emits no
AST/machine code, reads no files and does not make the compiler self-hosted.
See spec/lexer.md, spec/integer-literals.md and spec/expressions.md for its profile.

Copied-source native/reference comparisons cover invoices, recursive/byte helpers
and frontend smoke/value cases. The pinned upstream build is only a read-only
comparison experiment; it is never in the native compilation path. Production
Alchem source, refs, workflows and settings remain unchanged.

Literal one-argument IO.puts lowers directly to static UTF-8 byte data plus LF
and native complete writes. Output works in helpers/branches and preserves
values across syscalls. General strings/interpolation/device overloads and file
IO remain rejected. V7 specifies short writes, EINTR, default signal behavior
and E_RUNTIME_IO/exit 74; production error messages are not duplicated.

V8 adds program-mode Enum.concat(left,right) over byte lists and list[integer]
helper returns. Calls/branches/returns are typed; source main stays void and IR
main i64. Native construction uses fresh process-lifetime records in a separate
4 MiB RW arena, preserving input bytes and references across calls. Pure library
probes retain their earlier profiles; general lists remain outside the supported subset. This does not change production Alchem.

V9 program mode adds computed integer byte-list elements, preserving left-to-right
operand evaluation before full-width byte validation and allocation. All elements
must then fit 0..255; failure is native E_RUNTIME_BYTE/exit 72. Computed packs are
capped at 4096 operands; valid literal lists retain static lowering. The byte-only
subset is intentionally narrower than production Alchem's general integer lists.
The new Alchem encoder fragment and ordinary computed lists match pinned upstream
comparisons on valid supported inputs; no invalid general-list parity is claimed.
