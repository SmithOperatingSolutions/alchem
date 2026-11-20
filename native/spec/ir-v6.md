# JSON IR version 6 — checked process status

V6 retains V5's typed instructions, byte values/ABI, validation and native
call-depth/active-frame limits. It changes only the process-entry contract:
after calling main, the entry stub checks its full i64 result is in 0..255.
Valid results become the process exit status, with no stdout/stderr. An invalid
result writes exactly `E_HALT_STATUS: expected status 0..255\n` to stderr and
exits 70. Normal status 70 remains distinguishable by empty stderr. Both
negative and excessively large positive values are rejected without low-byte
truncation. Helper functions still return arbitrary full i64 values.

The guard is an unsigned compare of RAX to 255 followed by an out-of-range
branch, so negative values fail as well. Failure uses direct Linux write/exit
syscalls; no host runtime or external compiler/linker is introduced. Call/stack
failure remains E_RUNTIME_LIMIT; it occurs before the status check if execution
never returns from main. As before, total instruction count/time is not bounded.

V1–V5 retain their existing low-byte process-return contracts and emitted bytes.
V6 applies the checked-entry rule to every program regardless of whether it
uses byte data, recursion or a literal/dynamic result.

The restricted source adapter now emits V6 for every executable main. Normal
void completion returns zero; final/terminal-branch System.halt results remain
actual native computations. It no longer executes main/helper expressions at
compile time to prove a status, eliminating the 100,000-step/active-proof-depth
limitation. All source paths are still parsed, type checked, lowered and their
IR validated. Runtime guards retain the 256-active-call/1 MiB stack profile.
Explicit library-function probes retain V1–V5 and their low-byte return behavior.

This intentionally extends experimental source behavior: System.halt(-1) and
System.halt(256), formerly compile-time unsupported, now compile and fail at
runtime. Infinite recursive source compiles and hits the native resource guard.
Other unsupported language features remain compile errors; no IO or writable
storage is introduced here. Native diagnostics are profile-specific, not exact
copies of production Alchem's actor/runtime error messages.
