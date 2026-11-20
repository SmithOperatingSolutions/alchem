# Compiler-sized source and reproducible native compiler builds

The verified profile supports source<=4194303 bytes, <=65535 functions, <=1024 body tokens,
<=128 list elements, and <=1 GiB total function code (an image beyond 16 MiB is
checked by harness/source_capacity.py). Source cursors use u24;
function lengths/addresses, relative branches and ELF sizes use checked u32 fields
within this profile. The generated entry reserves 1024 bytes; the function table
is one u64 per slot at file 1152 and function code follows it. Entry remains0x400080.

Traversal must bound stack usage: batch declaration/body scanning, balanced name
search and byte slicing, balanced code assembly. Compile each function once and
retain lengths alongside code; address layout must not recompile bodies. Valid
constant-byte lists may validate at compile time and emit an inline constant copy
into a fresh record, preserving immutability and allocation charging. Computed
lists retain eager evaluation and full-width runtime byte checks.

IR V11 adds required arena_bytes (8..17179869184, multiple8) to the existing typed
flow/read profile. Earlier versions retain their exact 4 MiB behavior/bytes. The
source compiler bootstrap uses a documented32 MiB execution arena, with measured
charges under tracing. Ordinary generated programs retained4 MiB then (they now reserve
16 GiB lazily, alchem-tail-calls.md); compiler-entry
artifacts use32 MiB. A larger budget complements the changed storage algorithms;
it is not evidence that raising limits alone scales the implementation.

An explicit public native_compile(source: list[integer]): list[integer] helper
opts a module into compiler-entry IO. A void main/0 remains for upstream syntax
compatibility. The generated process reads bounded stdin, calls native_compile,
rejects empty results with status65/diagnostic, writes nonempty bytes completely
and exits 0. All IO code, headers and instructions must be emitted in Alchem.
No host wrapper patches generated artifacts. Normal modules still enter main.

Completed acceptance: component-sized source/128-element construction, images crossing64KiB,
measured bounded allocation, then compile the actual assembled compiler to A1.
A1 builds A2 and A2 builds A3 with no host tools on PATH. Byte equality and
correctness/rejections pass at all three stages through both seed backends.
Arena charges are measured under tracing. The initial self-build baseline is in
docs/self-hosting-benchmarks.md; it does not establish full Alchem compatibility.

V11 also adds native bytes.slice and source Enum.slice: one fresh bulk copy,
negative-index normalization, nonnegative count clamped without overflow. This
replaces recursive copying inside code bundles. Valid constant byte lists emit
an inline payload copy into a fresh record; dynamic elements retain runtime
checks. The source distribution selects nine shared lexer primitives; native
rebuilds thereafter consume the exact single assembled Alchem file.

The auditable compiler IO instruction template is compiler-entry-x86_64.s. It
is a reference only, not a build input: the Alchem runtime emitter constructs
its bytes (split into bounded literal chunks), replacing the nine-byte call slot
with its own function-table call. Native builds/rebuilds never invoke an assembler.

Source distribution assembly now compacts formatting/comments with a lexical
scanner that preserves quoted content, token boundaries and statement newlines,
including CR-only comment endings. Component sources remain readable. This is
initial assembly only: native A1/A2/A3 rebuild the same compact source unchanged.
The pre-boolean source shrank from 63,989 to 55,008 bytes without changing its ELF.
The expanded readable source is 95,987 bytes; the native input is 63,835 bytes,
leaving 1,955 bytes of lexical headroom. No cursor or runtime input limit changed.

Initial distribution assembly also performs injective identifier compaction,
preserving quoted contents, namespace members, all language keywords and public
main/native_compile/nc_compile names. Native self-builds consume that exact input;
normal user source is not rewritten. Alpha-renaming was checked against the
existing compiler ELF before the library changes. Generated Unicode byte literals
are tracked implementation source; assembled compiler-source.alc stays ignored.

The function table now has256 slots. Address construction uses balanced ranges and
length sums: the256-function boundary exposed and fixed a recursive address-write
limit, without changing the256 active-frame limit. Compiler-entry arenas are32MiB;
a native self-build with Unicode/options exceeded the old16MiB budget. Ordinary
programs remain4MiB and older IR contracts are unchanged. All budgets are measured.

Source/input capacity is now 4,194,303 bytes with24-bit source metadata; see
[source capacity](../spec/source-capacity.md) for packet/layout boundaries.

Structural types use u16 function indices. The table now holds exactly the
used slots, up to65541, without padding; active native frames remain256. See alchem-structural-types.md.

Current compiler entries reserve 16 GiB lazily (1 GiB before the source limit
became 4 MiB; see source-capacity.md for measurements); the earlier64MiB budget was
within30% of exhaustion. Native charge34,536,120 bytes; ordinary programs had4MiB
(16 GiB reserved lazily since alchem-tail-calls.md).
