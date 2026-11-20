# JSON IR version 8 — immutable runtime byte construction

V8 retains V7 operations, checked entry status, output and native call/frame
limits. It adds bytes.concat with exact fields op, dest, lhs, rhs. Both operands
are bytes SSA values; the result is a fresh bytes value containing lhs then rhs.
A helper may declare return_type bytes or i64; calls have that declared type.
Main must still return i64 and take no parameters. Boolean function returns and
arbitrary pointer conversions remain unsupported. All branch/call/return types
are checked, including unused code. V1–V7 retain their contracts and bytes.

At V8 process entry a Linux mmap reserves exactly 4 MiB of anonymous RW memory,
separate from the RX executable/static literals. Every concatenation, including
empty+empty, allocates a fresh record: u64 length followed by packed bytes,
charged as align8(length+8). A result may contain at most 1 MiB of payload.
There is no reclamation; all references live until process exit. Inputs remain
unchanged and results can cross calls/returns/conditional merges. Static literal
limits (1 MiB each / 4 MiB total including headers) remain independent.

Mapping failure, oversize result or exhausted arena attempts to write exactly
`E_RUNTIME_ALLOC: byte allocation failed or limit exceeded\n` to stderr and
exits 71 before copying beyond a bound. These are runtime limits, not compile-time
constant folding/rejections. Limits charge allocations on actually executed
paths, including discarded results; unused branches allocate nothing. No GC,
libc, Go/Rust runtime or external compiler/linker is introduced.

The private ABI reserves R12 as the bump cursor and R13 as arena end, in addition
to R14/R15 call/frame counters. Entry initializes R12/R13 once; functions share
allocation state instead of restoring the bump cursor at returns. Temporary
copy registers are caller-saved; references/other SSA values remain in stack
slots. Concatenation checks length/capacity, writes its header, clears DF and
copies inputs with native byte moves. No IR mutation or pointer arithmetic is
exposed; byte writes still mean stdout/stderr output, not memory mutation.

Source program mode supports two-argument Enum.concat over the restricted
immutable byte-list subset and list[integer] helper return types. These select
V8, including functions returning static literals without concatenation. Main
remains void; general/computed-element lists, mutable buffers, byte conversion
from arbitrary integers, list-of-lists concat, strings and input/file IO remain
unsupported. Pure library-probe mode does not add V8 construction/byte returns;
use program mode so its checked process-entry contract is explicit.
