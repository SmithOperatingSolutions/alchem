# IR V11 — explicit arena budget and native byte slicing

V11 retains the V10 typed flow/call/read/byte operations and adds a required
program field arena_bytes: a JSON integer, multiple of 8, in 8..17179869184. The
native mmap and end-pointer guard use exactly that budget up to 1 GiB, with the
encoding they always had. A larger budget is reserved lazily (MAP_NORESERVE) and,
when the system refuses it, halved until it is granted or would fall below 1 GiB
(E_RUNTIME_ALLOC, 71); R13 holds the size during the attempts. Earlier versions
reject this field and retain the exact fixed 4 MiB behavior/encoding. The compiler
bootstrap uses 16 GiB; ordinary Enum.slice source programs default to4MiB.

New instruction:

```json
{"op":"bytes.slice","dest":"part","buffer":"bytes_name","index":"i64_name","count":"i64_name"}
```

Result is fresh immutable bytes. Buffer must be bytes; index/count must be i64.
Count<0 attempts E_RUNTIME_SLICE: expected nonnegative count plus LF and exits 73,
before index/bounds handling. Negative index adds input length once. A remaining
negative or index>=length yields empty bytes. Nonnegative count clamps to the
available length using subtraction/comparison, avoiding start+count overflow.
Each result, even empty, charges align8(result_length+8); allocation failure
retains E_RUNTIME_ALLOC/71. Original data/aliases are unchanged. Copy uses native
rep movsb with clear direction flag and never creates an executable mapping.

JSON keys/casing/decoded duplicates and operand fields remain strict. Missing,
null, wrong-type, out-of-scope or incorrectly typed values are rejected. Versions
before 11 reject the slice opcode. Source Enum.slice(bytes,index,count) selects
V11; range overloads/general lists/pure library construction are unsupported.

The Alchem-written backend independently emits the same slice semantics, with
its private raw error73 rather than bootstrap diagnostics. Source compiler entry
has a 16 GiB lazily reserved execution profile; ordinary generated programs still use4MiB.
See compiler-scaling.md for source distribution and native rebuild contracts.

V11 bootstrap programs now permit65535 functions (it was4096); V1–V10 retain256. This source
capacity extension preserves earlier valid encodings and active-call limits.
The source adapter selects the larger cap only when emitting V11. Shared tests
check256/257 for V10 and65535/65536 for V11, execution, backend equality and preserving
existing output/mode on rejection. The native self-hosted compiler independently
supports65535 functions. Explicit bytes/b[...] syntax is a seed spelling adapter;
V11 byte IR and general-collection native representations remain distinct.

A V11 bytes.concat result is bounded only by the arena up to a payload of 1 GiB
(its payload check, which is also the most code the native compiler emits); V8 to V10 keep the1MiB payload limit of ir-v8.md. The
seed-built compiler can therefore emit images beyond1MiB, like the self-built one.

V11 programs may nest 1024 calls and use 4 MiB of charged stack; V1–V10 keep
256 calls and 1 MiB. The compiler's own source needs it: compiling its most
deeply nested functions takes about sixteen calls per level of nesting, below
the halving over its functions. Both backends emit the same guard.

A V11 bytes.read limit may be 0..16777216 (V10 keeps 0..1048576): the compiler
reads sources of up to 16,776,191 bytes, and a V11 program may hold 16 MiB of
byte constants (`bytes.const`, each still at most 1 MiB; earlier versions keep
4 MiB): the compiler's source grown to that size is mostly such data. The emitted code is that of V10 with the
larger immediates, the same in both backends. The seed frontend itself parses
at most 1 MiB at a time; source-capacity.md says how a longer compiler source
reaches the backends.
