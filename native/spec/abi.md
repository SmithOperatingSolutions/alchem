# ABI — version 1 process baseline

The current backend emits a standalone Linux x86-64 executable. Its entrypoint
is a process entrypoint, not a System V callable function. The only observable
result is the low eight bits of the `ret` operand as process exit status.
There are no parameters, calls, return-to-caller sequence, runtime, or external
symbols. Do not invoke this entrypoint as a library function.

The executable starts at virtual address `0x401000`. Code reserves a stack area
by subtracting a multiple of 16 bytes from RSP. Each SSA value occupies an
8-byte slot at an offset from this adjusted RSP. No assumptions about argument
registers or initial stack contents are used. RAX and RBX are scratch registers;
the backend does not preserve callee-saved registers because it never returns
to a caller. The stack allocation is capped at 1 MiB; this is not stack probing
or a guarantee against host stack limits.

`ret` loads its i64 operand into RDI, sets RAX to Linux syscall number 60
(`exit`), and issues `syscall`. The process terminates without restoring the
stack. This emits no stdout/stderr. Shared fixtures exercise zero, positive,
negative, and overflowing arithmetic results and check process exit status.

Any future externally callable function ABI must specify System V AMD64 integer
argument registers (RDI, RSI, RDX, RCX, R8, R9), RAX return values, stack alignment
at calls, register preservation, and stack-passed arguments with executable
interop tests. Those conventions are not implemented or verified by this
process-only milestone. Branches, calls, and runtime support remain future work.

## Version 2 direct integer calls

A separate process-entry stub starts at 0x401000 with the Linux entry stack,
calls parameterless main, moves its RAX result to RDI and issues exit syscall 60.
Each function receives up to six i64 arguments in RDI, RSI, RDX, RCX, R8 and R9,
and returns i64 in RAX. Arguments are copied into stack slots on entry.

Functions push RBP, set RBP to RSP, and reserve a multiple of 16 bytes for all
SSA values. Slots are addressed relative to that fixed RSP. Before every call,
RSP is 16-byte aligned; the return address makes callee-entry RSP 8 modulo 16.
Epilogues use leave/ret. RBP is preserved; RBX and R12–R15 are untouched. Arithmetic
uses caller-saved RAX/RCX, and every live SSA value stays in a stack slot across
calls. Outgoing argument registers are loaded only after all argument
expressions have been lowered to slots.

Calls use signed relative 32-bit displacements, patched after deterministic
function layout. This is the integer-register subset of System V AMD64; there
are no external symbols, stack-passed arguments, floating-point ABI, varargs or
interop guarantee beyond the tested internal convention. V1 emission is unchanged.


## Version 3 conditionals

V3 retains the V2 integer call ABI. Boolean locals occupy 8-byte slots containing
exactly 0 or 1. Comparisons use signed CMP/SETcc and zero-extension; not toggles
the normalized bit. Conditional jumps select one branch, load its yield into
RAX, and converge on one destination store. All branch-local slots are reserved
in the function frame up front. Calls inside branches use the same aligned
frame and preserved-value rules as other calls. No phi moves, loops or arbitrary
control-flow edges are part of this structured milestone.

## Version 4 bounded recursive calls

V4 retains V3's frame/argument/result conventions and reserves R14/R15 as
process-private counters, initialized by the entry stub. R14 tracks rounded
active frame bytes plus 16 bytes per call; R15 tracks active function count.
Each entry checks the 1 MiB/256-call limits before allocating its frame; normal
return subtracts its charge and decrements depth. Limit failure uses direct
Linux write/exit syscalls, emits the specified diagnostic and exits 70.

These counters are shared across generated calls rather than preserved as
ordinary callee-saved registers. V4 is a private ABI without external-call
interop. See [the V4 contract](ir-v4.md) for resource/host-stack assumptions.

## Version 5 immutable byte parameters

V5 retains V4 counters, frame alignment and argument-register ordering. A bytes
parameter occupies one register/8-byte stack slot, holding a private reference
to a process-lifetime RX literal: little-endian u64 length then packed u8 data.
Calls accept mixed i64/bytes parameters in their declared order, up to six total;
all function results are still i64. RAX/RCX/RDX are scratch registers for checked
indexing; buffer references live in stack slots across calls. RIP-relative LEA
fixups refer to literal data after function code/runtime diagnostics. The compiler
never exposes pointer arithmetic, arbitrary pointer construction or mutation.
See [IR v5](ir-v5.md) for indexing and static storage budgets.

## Version 6 checked process entry

V6 retains the V5 function ABI and byte representation. After main returns to
the process stub, an unsigned RAX comparison rejects values above 255 (including
all negative signed values) before moving the result into RDI for exit. This
guard applies only to the process stub; generated helpers retain full i64 returns.
Failure emits E_HALT_STATUS and exits 70 using direct write/exit syscalls. Native
resource failure remains a separate E_RUNTIME_LIMIT handler. See [V6](ir-v6.md).

## Version 7 byte output

V7 retains V6 entry/function conventions and emits inline write loops for
bytes.write. RAX/RCX/RDX/RSI/RDI/R8/R11 are scratch; arguments/live values remain
in stack slots and RBP/R14/R15 are preserved. R8 retains total byte count while
RSI/RDX track progress; successful completion returns the count to the SSA slot.
Write errors use a separate E_RUNTIME_IO handler/exit 74. See [V7](ir-v7.md).

## Version 8 byte results and arena state

Helpers may return i64 or bytes in RAX; main still returns i64. Byte results use
the same one-word pointer/header representation as byte parameters. The process
stub mmaps a separate 4 MiB RW arena, initializes R12 (next allocation) and R13
(end), and reserves both throughout generated functions. R14/R15 keep their
existing call/frame roles. Normal returns do not rewind R12: references remain
valid until process exit and discarded allocations remain charged. Concat uses
caller-saved scratch registers, clears DF, and copies into fresh aligned records;
SSA slots preserve live references/arguments. Allocation failure/limits emit
E_RUNTIME_ALLOC and exit 71. See [V8](ir-v8.md) for exact charging/limits. This
extends the private ABI, not an external System V FFI guarantee.

## Version 9 checked packing

V9 retains V8 typed results and R12–R15 state. Each bytes.pack first checks full
RAX operands against 255 using unsigned branches, then allocates an aligned fresh
record. RDX holds its address while validated values are reloaded from SSA slots
and stored as bytes. The result pointer returns in RAX; live arguments/references
remain in stack slots. Byte failure uses E_RUNTIME_BYTE/exit 72, separately from
arena failure/exit 71. See [V9](ir-v9.md) for the operand cap and evaluation order.

## V10 bounded stdin

V10 bytes.read reserves align8(limit+9) bytes including one lookahead byte
(limit at most 1 MiB; 4 MiB in V11, which builds the compiler),
accumulates short reads and retries EINTR on fd 0. R9 holds the record pointer,
R8 the byte count, RSI the cursor and RDX the remaining capacity. R12/R13 and
R14/R15 retain their arena/resource roles; SSA slots survive syscalls. It returns
the header pointer in RAX at EOF; failures use 65/74. See [V10](ir-v10.md).

## V11 compiler resources and slicing

V11 supplies an explicit aligned arena_bytes budget of up to 16 GiB; older profiles
retain 4 MiB. A budget past 1 GiB is reserved with MAP_NORESERVE, R13 holding the size
while it is halved down to 1 GiB until the system grants it.
Its call guard allows 1024 nested calls and 4 MiB of stack (256 and 1 MiB before it).
Native bytes.slice allocates one fresh copy with overflow-safe signed index/count
normalization. See ir-v11.md. The independent Alchem-written compiler emits its
own private integer/byte and compiler IO ABI, described in alchem-source-profile.md.
Its compiler entries read up to 4,194,303 bytes of source and reserve 16 GiB lazily
(source-capacity.md); ordinary generated programs reserve 16 GiB lazily too, down to
4 MiB where the system grants no more (alchem-tail-calls.md).
