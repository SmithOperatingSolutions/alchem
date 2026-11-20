# Linux ARM64 (AArch64)

`alchem build -target linux/arm64` is to make the same program for ARM64 that
the pinned compiler's `-target linux/arm64` makes. This file is the design and
the state of the port.

## One source, two compilers

The compiler's source holds both targets. `nc_arm()` (native-arm64.alc) is 0
in the source and 1 in the ARM64 compiler, which `scripts/build-arm64.py`
makes from the same source with that one function changed. The target is a
constant of the build, not passed through the compiler's functions. The
x86-64 compiler takes the other branch everywhere, so its output stays byte
for byte what it was: every step of the port is checked so, on the corpus of
upstream examples, examples/ and tools/.

## Translation, function by function

The compiler's emitters, and the passes that read the code they made
(`nc_peak` sizing frames, `zf_patch` turning a library routine's exit into a
failure, the peepholes of native-speed.alc), stay those of x86-64. The ARM64
compiler builds every function's x86-64 code as the x86-64 compiler does and
then translates it (native-x86arm.alc, `xa_bundle`), before the image is laid
out, so the function table, the trace tables and every address are those of
the ARM64 code:

- `xd` decodes an x86-64 instruction by a table of opcodes (`xd_t1`,
  `xd_t2`) into a record of its operands; `xa_insn` gives its ARM64 code.
- Pass 1 (`xa_scan`) walks a function's instructions in order, by halves so
  that its cost stays n log n, and notes for each the size of its
  translation, where its flags came from and whether flags are read after
  it. Pass 2 (`xa_emit`) translates each with every branch target known; a
  translation that does not come out at its measured size fails the
  function, and so the program.
- Data in code is marked where it is made. An instruction whose RIP-relative
  operand names data follows the marker `0F 0B 'D'`, the data's length and
  how far before what it points at the data starts (`xa_mark`,
  `xa_mark_back`); the translation copies those bytes. Every emitter that
  places data in code marks it in the ARM64 compiler (text and byte
  literals, failure messages, type descriptions, the empty list, throws).
  Fragments assembled from spec/*-x86_64.s with data among their code are
  assembled once more with the markers placed by the assembler
  (scripts/generate-marked-fragments.py: `na_pad`, `zf_slice_check`).
- ARM64 code among x86-64 code follows `0F 0B 'A'` and its length and is
  copied (`xa_raw`): the runtimes that are a table entry of their own.

## The machine the code assumes

ARM64 code keeps the frame and memory layout of the x86-64 code, so an
instruction translates to a short ARM64 sequence and every offset the
compiler computes (slots at RBP-8n, RBP-136 for the trace word, R14-8 for the
stack limit, the entry's words at 0x400420 to 0x400478, the function table at
0x400480) stays the same. Each x86-64 register has an ARM64 register:

| x86-64 | ARM64 | | x86-64 | ARM64 |
| --- | --- | --- | --- | --- |
| RAX | X0 | | R8 | X8 |
| RCX | X1 | | R9 | X9 |
| RDX | X2 | | R10 | X10 |
| RBX | X3 | | R11 | X11 |
| RSP | X28 | | R12 | X12 |
| RBP | X29 | | R13 | X13 |
| RSI | X4 | | R14 | X14 |
| RDI | X5 | | R15 | X15 |

XMM registers are D0 to D15 (Q for 128-bit moves). X16 and X17 hold
addresses and constants inside one translated instruction, X19 to X24
values; X30 is the link register.

- The stack is X28, not SP: ARM64 Linux faults on an access through an SP
  that is not 16-byte aligned, and x86-64 code pushes 8 bytes at a time. SP
  stays below the words the program keeps under R14 (the collector's 1536
  bytes and the entry's), for signal frames.
- A call leaves its return address on that stack as x86-64's does (the
  failure trace reads it at RBP+8): `adr x30, back; str x30, [x28, #-8]!;
  b target`; `ret` is `ldr x30, [x28], #8; br x30`.
- Flags: an instruction whose flags are read uses ARM64's flag-setting form.
  After a subtraction x86-64's carry is a borrow and ARM64's its inverse, so
  each reader is translated by where its flags came from (`xa_cc`: a
  subtraction, an addition or logic, a floating-point comparison). Byte and
  word arithmetic whose flags are read is done in the top of a W register.
  Overflow of a multiplication is computed (`smulh`) and set as V and C.
- `inc` and `dec` keep x86-64's carry: ARM's C is read before them
  (`mrs`) and put back into the flags they set (`bfi`, `msr nzcv`), in the
  sense it had; whether flags are read looks past them for a reader of the
  carry. A shift by CL leaves the flags as they were when CL is 0, and
  sets C (the last bit out) together with Z and N otherwise. `rep movs`
  and `rep stos` count RCX down without touching the flags.
- Whether flags are read follows an unconditional jump to its label; loop,
  loope, loopne and jrcxz count RCX down without the flags and are taken
  as reading them (a carry chain runs through `adc ... loop`). A label is
  one where the carry is live only when a reader of it is found within
  sixteen steps (a function of thousands of literals, each jumped over,
  would otherwise make every label one and pass 1 quadratic).
- A routine may leave its caller flags (the float runtime's `bn_cmp`):
  `ret` counts as reading them all, so what sets them last computes them,
  they leave in a subtraction's sense (C turned over at `ret` after an
  addition) and a call comes back with that sense. The compiler's own code
  reads no flags across a call.
- A label where the carry is read before it is set again (a loop whose
  body ends in `adc` or `sbb`, entered after logic or an addition) is
  reached with the carry in one sense, a subtraction's, on every path: a
  jump to it and the instruction before it turn ARM's C over when it is an
  addition's (`mrs`, `eor`, `msr`). Both translations do this; the
  compiler's finds such targets as their jumps are met and scans the
  function once more when one of them is a loop's head.
- A system call goes through one routine (`x86_syscall`, scripts/x86-to-arm64.py)
  that moves x86-64's arguments to ARM64's, maps the call's number and keeps
  the registers x86-64 keeps. The collector holds it; the word at 0x400420
  is its address, which translated functions call through.
- Conversions from double to integer give x86-64's lowest integer for NaN
  and values out of range, where ARM64 saturates; `cpuid` reports FMA and AVX
  so that the float runtime takes its fused path, and AES-NI, PCLMULQDQ and
  SSSE3 where the processor has AES and PMULL (ID_AA64ISAR0_EL1, which
  Linux lets a program read), so that TLS takes the processor's AES as on
  x86-64 and its software AES elsewhere.
- SSE's 128-bit integer operations, `pshufb`, AES-NI and `pclmulqdq` (the
  TLS runtime) are NEON's on V registers: `aese`/`aesd` with a zero key
  then the round key added, as x86-64 adds it last; `tbl` for `pshufb`
  with each index masked so that 128 and up give 0; `pmull` for
  `pclmulqdq`.
- The image starts at 0x400000 with an ELF header for machine 183. The
  entry's start (arena, stack, the collector's start) is written for ARM64
  (`a_entry`); what follows it is translated.

## Runtimes

The runtimes keep one source, spec/*-x86_64.s. scripts/x86-to-arm64.py
translates that assembly to ARM64 assembly under the same machine model, and
GNU as for AArch64 assembles it: the collector (scripts/generate-memory-runtime.py,
native-memory-data-arm64.alc) and every runtime of its own table entry
(scripts/generate-arm64-runtimes.py, native-runtimes-arm64.alc: the failure
trace, floats, crypto, TLS, integer parsing, File.read, case mapping,
graphemes). An operand the translator does not know (a label in an
address, an address of 32-bit registers anywhere but `lea`) stops the
generation rather than becoming something else.

harness/x86_to_arm64.py runs random sequences of instructions natively and
translated under QEMU and requires the same registers, memory and
branches: every kind through scripts/x86-to-arm64.py, and, given the
compiler, the kinds the compiler emits through its own translation
(`xa_function`, built as a program's entry from the compiler's source):
carry chains in loops, inc and dec between a comparison and its reader,
shifts by CL, the vector and AES instructions among them.

`scripts/fetch-arm64-tools.sh` puts the assembler and QEMU's user-mode
emulator in build/arm64-tools without installing anything; `scripts/run-arm64`
runs a program with it. Gates that use ptrace or strace cannot run under
QEMU and need ARM64 hardware.

## Checking

harness/arm64.py checks the ARM64 encoders against GNU as and runs programs
compiled for ARM64 under QEMU against their x86-64 builds: the same status,
standard output and standard error. The corpus (871 upstream examples and
examples/) is run the same way, and harness/tls.py passes with a compiler
that builds for ARM64 and runs under QEMU: its known answers (large numbers,
AES-GCM on both paths, ChaCha20-Poly1305, AES-CBC, the curves, RSA), the
servers of OpenSSL it dials and the observations of its servers by OpenSSL,
curl and Python.

The translation decodes an instruction in full (`xd`, a record of words)
where it emits one; what reads ahead for whether the flags are read uses
a lean decoding (`xq`: length, op, sub, opcode as one integer, no record),
the same as xd's at every offset of a 400 KB program. A program of 1 MB of
x86-64 code compiles for ARM64 in 5 s and 32 MB (2 s for x86-64).

## The handler of SIGSEGV

Where a program makes a zero that the pinned runtime has as a nil pointer
(`zf_guard`), x86-64 code installs a handler that sends a fault below
address 4096 to Go's panic by rewriting RIP in the saved context. ARM64
calls a handler with its arguments in X0 to X2 and returns by X30, and keeps
the program counter at 440 of the context, so the ARM64 compiler emits that
part as ARM64 code among the translated (`zf_guard_arm`): the handler, the
restorer, the failure that calls Sys.panic as a translated call does, and
rt_sigaction, which keeps RBX and R8 (X3, X8).

## Coverage

A statement counted for `--cover` calls a routine with its position as the
word behind the call, which the routine returns past, and has the count of
its own by how far before the routine the call returns
(spec/cover-x86_64.s). On ARM64 the call is ARM64 code among the
translated whose return address is that word (`zf_cover_call`), the
routine is its translation (`cv_blob_arm`, with the length at 4 as on
x86-64), and the list of calls the report reads (Testing._centries) is made
from where they stand in the ARM64 code once it is translated
(`zf_cover_arm_points`), so that the library reads it unchanged.
harness/failures.py passes for ARM64 builds under QEMU, its coverage
reports among them.

## Compiler entries

A program whose entry is `native_compile(source: bytes): bytes` reads all
of standard input, gives it to that function and writes what it returns
(spec/compiler-io-x86_64.s). Translated, that code outgrows the 1024 bytes
of the entry, so the ARM64 compiler makes it a function of its own after
the shared runtimes (`nc_io_function`), its messages marked as data, and
the entry calls it. The compiler is such a program: built for ARM64 it
compiles its own source under QEMU to the x86-64 compiler, byte for byte
(harness/arm64.py).

## State

Every program of the corpus that compiles (885 of the 889 upstream
examples and examples/; the other 4 are of several files, which the bare
compiler refuses on both) runs under QEMU as its x86-64 build does, and the
pinned compiler's own ARM64 builds of the corpus print what its x86-64
builds print (Logger's time of day aside).

## Floats

The pinned compiler's ARM64 programs are Go's, and Go's compiler for ARM64
fuses: an addition or subtraction of floats with a product (or a negated
product) as an operand is one rounding (FMADDD, FMSUBD, FNMSUBD, FNMADDD of
ARM64.rules, which ask nothing of how often the product is used). The ARM64
compiler does the same (native-floats.alc, "fused multiply-add"):

- where the product is an operand as written, in parentheses or negated: a
  product's value is flagged and ends in its multiplication, which the sum
  takes off (`ne_fused`); a difference takes Go's rules in their order;
- through a name bound to a product: its factors are kept in two slots
  beside it (`nx_binding`, `ne_read`);
- not where Go's compiler folds: an operation on two floats it knows at
  compile time (literals, names bound to them, operations on them; bit 8
  of a value's flags, a hidden record after such a name) is a constant to
  it, no product (so `inf - inf` stays NaN where inf = 1.0e308 * 10.0);
- through a call Go's compiler inlines: a function of one clause whose body
  is assignments and a last expression of names, numbers, + - * / and
  parentheses with * at its top returns with its factors still in RCX and
  XMM1, which the call takes (`ne_called`, `ne_inlined`).

The runtime is Go's ARM64 one where it differs: math.Log is log.go as Go
compiles it for ARM64 (read from the pinned toolchain's code), math.Exp is
exp_arm64.s, and math.Pow's squaring fuses `x1 *= x1; x1 += x1`
(spec/float-x86_64.s, `.ifdef ARM`). harness/arm64_floats.py runs 500
results of 34 forms against the pinned compiler's ARM64 and x86-64 programs
(where those differ in 42 of them).

What is not the same: in a sum of two products Go fuses one of them, and
which follows the order its CSE pass gives the sum's operands: by the
equivalence class of each, which depends on every value of the function
the sum ends up in after inlining (a sum alone in its function keeps the
order as written and fuses the right product; among others the one made
first, mostly the left). That is a property of the whole function as Go's
compiler sees it, and the same source function inlined into two callers
can fuse differently in each; the ARM64 compiler fuses the left one.

An invalid operation (0/0, inf - inf) gives each processor's default NaN:
negative on x86-64, positive on ARM64, as Go's own programs do on the two.
