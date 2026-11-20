# JSON IR version 4 — bounded recursive calls

V4 retains V3's types, structured conditionals and integer call ABI, and allows
recursive call graphs. V1/V2/V3 retain their previous validation/emission rules.
The function/parameter/branch/frame validation limits remain unchanged.

Each V4 executable initializes two private runtime counters. Every function,
including main, checks at entry that active function count is at most 256 and
charged active frame storage at most 1 MiB. A function charges its rounded frame
plus 16 bytes for saved RBP/return address; normal return restores both counters.
There is no tail-call elimination. Counters apply to the actually executed path,
not the entire static graph.

Exceeding either limit writes exactly
`E_RUNTIME_LIMIT: native call/stack budget exceeded\n` to stderr and exits 70,
without executing the function body or allocating its frame. The diagnostic
uses direct Linux write/exit syscalls; no host-language runtime or linker is
introduced. Normal main exit 70 remains distinguishable by empty stderr.

R14 tracks active charged bytes and R15 active function count. The process stub
initializes them; generated functions reserve them and restore their entry
counter values on normal return. This is a private native-profile ABI, not an
externally callable System V interface. The existing integer argument registers,
RBP/frame alignment and RAX return rules are retained.

The byte budget is a compiler-profile limit, not a query of the host stack limit;
the host must provide enough stack for the permitted charge and entry/error path.
It does not limit total call count or execution time: a terminating program may
make many shallow calls. Compiler validation limits remain separate.

Explicit library probes can emit V4 for recursive graphs. Current executable
source programs emit [V6](ir-v6.md), with checked process status and no compile-
time status proof. The earlier 100,000-step source proof policy is superseded;
raw V4 IR still retains this page's resource and low-byte return contracts.
