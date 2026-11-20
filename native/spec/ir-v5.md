# JSON IR version 5 — immutable byte buffers

V5 extends V4 with a `bytes` value type: an immutable, process-lifetime reference
to a static packed buffer. Integer function results remain i64; up to six
parameters may be i64 or bytes, each occupying one argument register/stack slot.
V4 call-depth and active-frame guards apply to all V5 programs. Older versions
reject byte operations/types and retain their previous behavior.

| Operation | Exact fields | Result |
| --- | --- | --- |
| bytes.const | op, dest, values | bytes; values is an array of integer bytes 0..255 |
| bytes.len | op, dest, value | i64 length of the referenced bytes value |
| bytes.get | op, dest, buffer, index, default | i64 byte or default; operands are SSA names |
| if.bytes | op, dest, cond, then, else | bytes; same branch scope rules as V3 |

For get, index/default have type i64. Negative index is normalized once by adding
length; an index still outside [0,length) returns default. Empty buffers always
return default. Default is an already evaluated SSA value, with no lazy effects.
No unchecked memory access, allocation, mutation, pointer arithmetic, equality,
bytes return signatures or conversion from arbitrary integers is exposed.
Each literal is at most 1 MiB; the program's total literal storage (including
8-byte headers, even for unused branches) is at most 4 MiB. Exceeding these
limits is E_UNSUPPORTED; malformed values/types/shapes are E_INVALID_IR.

Representation: one pointer to a u64 little-endian length followed by packed
bytes in the executable's read/execute load segment. The compiler emits literals
in deterministic instruction traversal order after code/runtime diagnostics,
patches RIP-relative LEA references and performs checked native loads. No heap,
host-language runtime, linker or libc is needed. These references are private
ABI values, not external FFI pointers. Physical page permissions remain RX.

The restricted source adapter maps literal list[integer] values containing only
integer literals 0..255 to bytes. Named list[integer] parameters, local aliases,
if values, Enum.count(buffer) and Enum.at(buffer,index,default) are supported.
This is a byte-only subset of list semantics, not general list support. Negative
indices/defaults match the pinned upstream Enum.at overload. No two-argument
option-returning Enum.at, computed list elements, strings or writable lists.
Current executable source programs use [V6](ir-v6.md), retaining these byte
operations/limits with a runtime process-status guard. Library probes can still
emit V5. Source functions are no longer evaluated at compile time to prove status.
