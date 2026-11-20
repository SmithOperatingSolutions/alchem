# JSON IR version 9 — checked packing of computed bytes

V9 retains V8 storage/ABI/typed returns and adds bytes.pack with exact fields
op, dest, args. args is a required array of prior i64 SSA names; result is bytes.
There may be at most 4096 arguments (E_UNSUPPORTED above that bound). This keeps
inline validation/store code bounded; larger buffers can use concatenation.
Missing/null arrays, undefined values and bytes/bool operands are E_INVALID_IR.
V1–V8 retain their contracts/emitted bytes and reject the new opcode.

The operation first validates every value, in argument order, is 0..255 using
full-width checks. Any invalid value attempts exactly
`E_RUNTIME_BYTE: expected byte value 0..255\n` on stderr and exits 72. No modulo
truncation, partial record or allocation occurs on this failure. The byte check
precedes the capacity check, even if the arena is full. Operands already exist
as evaluated SSA values; this does not short-circuit earlier instructions.

On success, allocate a fresh immutable u64-length/packed-byte record from V8's
4 MiB RW arena, charged align8(count+8); empty packs also charge 8. Allocation
failure/exhaustion remains E_RUNTIME_ALLOC/exit 71. No reclamation or mutation
is added. Packed values/aliases can cross returns/branches and concatenate or
write through existing operations. Static literal budgets stay independent.

Source program mode adds computed list[integer] elements in this byte-only
subset: evaluate elements left to right into i64 values, then pack/check them.
All elements are evaluated before the byte validation phase. Nonliteral or
out-of-byte-range literal lists select V9, capped at 4096 elements. Already-valid
literal byte lists retain their previous static lowering and larger literal
limit. This intentionally changes former unsupported cases such as [x], [40+2],
[-1], [256]: computed valid lists now run; invalid byte values fail at runtime.
List tails, boolean/general lists and pure library-probe construction remain
unsupported. Binary source output, input/file IO and an ELF writer are separate
work; this profile exposes no arbitrary pointers or memory mutation.
