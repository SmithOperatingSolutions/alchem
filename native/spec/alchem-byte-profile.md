# Typed immutable bytes in the self-hosted Alchem source compiler

Integer and bytes parameters/returns are distinct types. Bindings
infer type, calls check each argument, returns match declarations and if branches
must agree. Arithmetic, comparisons, indexing/default/count and System.halt require
integers. No casts between byte buffers and general lists, or mutation.

Byte buffers use explicit b[...] literals and the bytes type. General [...]
lists now have full-width storage; see alchem-collections-profile.md. Up to 128 element expressions evaluate
left to right before full-width 0..255 range checks. Invalid values exit72, without
truncation. Valid constant literals may be checked during compilation and emitted
as inline data copied into a fresh record. This preserves allocation semantics;
invalid constants still take the computed/runtime check path. Empty lists are
fresh and charged too.

- Enum.count(bytes) returns length.
- Enum.at(bytes,index,default) normalizes a negative index once, then returns a
  zero-extended byte or the full i64 default outside bounds.
- Enum.concat(bytes,bytes) returns fresh concatenated data, bounded only by the
  arena (16 GiB reserved lazily for programs, exit71 when it is exhausted;
  alchem-tail-calls.md); the former1MiB payload cap is gone.
- Enum.slice(bytes,index,count) returns a fresh bounded copy. Negative count fails
  with 73 before bounds handling; negative index normalizes once. Remaining invalid
  index yields empty. Count clamps to available length without addition overflow.
  Range overloads are not in this profile.

- Enum.reverse(bytes) returns a fresh reversed copy.
- Enum.take(bytes,count) returns a fresh prefix for nonnegative count, suffix for
  negative count, clamped to length. Minimum i64 takes the whole buffer.
- Enum.drop(bytes,count) drops a prefix for nonnegative count, suffix for negative
  count, clamped to length. Minimum i64 drops the whole buffer.
- Enum.sum(bytes) returns the i64 sum of unsigned byte elements; empty returns 0.
  It allocates no record. These overloads do not imply general-list support.

Reverse/take/drop charge a fresh aligned record, even for empty or unchanged
results. Take/drop append the existing slice emitter after safe count/index
normalization. Reverse uses a bounded backwards byte copy. The instruction
reference is enum-byte-runtime-x86_64.s; it is not a build input. The Alchem
runtime emitter constructs the actual instructions without invoking an assembler.

All arguments evaluate eagerly left to right, including an unused index default.
Byte references survive calls/returns/scoped conditional results and remain
immutable through every operation.

Ordinary generated programs reserve an anonymous RW/non-executable arena of 16 GiB lazily
(MAP_NORESERVE), or the largest half of that the system grants down to 4 MiB
(alchem-tail-calls.md), and compiler-entry artifacts 16 GiB down to 1 GiB. R12/R13 are bump/end; records contain u64 length then
payload and charge align8(length+8), including 8 for empty. No reclamation or
rewinding. Invalid computed pack values are checked before capacity/allocation.
Mmap failure, exhaustion or excess concat payload exits 71. These private target
errors have no diagnostics. The bootstrap IR uses its own diagnostic contract;
see ir-v11.md. No executable allocation mapping is created.

The larger fixed entry and function table layout is in alchem-source-profile.md.
The byte/runtime implementation now compiles itself; size/storage/native-entry
work and A1/A2/A3 equality are verified in docs/self-hosting.md. Full production
Alchem compatibility remains outside this bounded profile.
