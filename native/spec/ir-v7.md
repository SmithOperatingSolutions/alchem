# JSON IR version 7 — native byte output

V7 retains V6's checked status, byte types, validation and native resource limits.
It adds `bytes.write`, with exact fields op, dest, value, stream. value names a
bytes SSA value; stream is exactly stdout or stderr. The result is an i64 count
of bytes written after the complete buffer is sent. Empty buffers return zero
without calling write. Values live across output operations remain preserved.
All operands/streams are validated, including instructions in untaken branches.
V1–V6 reject this opcode and retain their previous executable bytes/contracts.

Generated code calls Linux write directly, advances pointer/remaining count on
short successful writes and retries EINTR. Zero progress or another syscall error
attempts to write `E_RUNTIME_IO: output write failed\n` to stderr and exits 74.
Previously written output is not rolled back. Error reporting can itself fail if
stderr is unavailable; exit 74 still occurs. Linux's default signal disposition
still applies (for example SIGPIPE). There is no nonblocking/EAGAIN retry policy,
implicit formatting, newline or NUL termination at the IR level.

RAX/RCX/RDX/RSI/RDI/R8/R11 are scratch registers; SSA slots, RBP and R14/R15
counters retain their existing rules. No heap, external compiler/linker, libc or
Go/Rust runtime is introduced. Static byte budgets remain 1 MiB per literal /
4 MiB total including headers. This introduces output only, not mutable storage,
input, arbitrary file descriptors, file creation or an Alchem-written ELF writer.

Source lowering supports one-argument IO.puts with a literal string. UTF-8 text
is encoded as bytes with exactly one appended LF, then emitted as bytes.const
and bytes.write(stdout). Embedded LF is retained, so a trailing LF gets another.
Empty literal text prints one LF. Output may occur before later statements and
inside branches/helpers; only executed branches write. Main still completes
normally or uses its final System.halt. Programs using output select V7; other
executable source retains V6. Unsupported string bindings/interpolation and
device/file overloads remain compile errors. General string values are not added.
