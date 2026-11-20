# IR V10 — bounded runtime stdin

V10 preserves V1–V9 and adds `{"op":"bytes.read","dest":"input","limit":128}`.
The limit is a required JSON integer in 0..1048576 (0..4194304 in V11). The result is immutable bytes.
Only V10 accepts this operation. Existing byte operations and typed returns remain
available. Reading consumes fd 0 until EOF, retrying EINTR and accumulating short
reads. It reserves align8(limit+1+8) bytes in the V8 arena before reading, including
one lookahead byte. The actual length is recorded at EOF. Each invocation charges
its reservation, even for empty input; no reclamation. Exact-limit input succeeds;
an extra byte fails immediately with `E_RUNTIME_INPUT: input exceeds byte limit`
and LF, exit 65. No successful truncated result is returned. Negative read results
other than EINTR attempt `E_RUNTIME_IO: input read failed` plus LF, exit 74. EAGAIN
is an error. Allocation failure follows V8 (71). fd 0 remains open; subsequent reads
after EOF return empty fresh records. Input may contain all byte values.

Read clobbers RAX, RCX, RDX, RSI, RDI, R8, R9, R11. SSA slots and arena/call-budget
registers survive. Input has no timeout; an unclosed pipe can block awaiting EOF.

The arithmetic compiler bootstrap assembles tracked Alchem components and adds
an explicit native entry bridge: read up to 128 bytes, call the typed Alchem
`compile_expression(list[integer]) -> list[integer]`, write a nonempty result to
stdout and exit 0. Empty results mean source rejection: diagnostic
`E_COMPILE: invalid expression or result outside 0..255` plus LF on stderr, exit 65,
no stdout. This sentinel is specific to this compiler (valid images are nonempty),
not a general byte pipeline convention. Normal source/main/library modes keep
their existing contracts. The bridge contains no source parser, evaluator or ELF
writer. Those run inside the Alchem-written executable for every runtime input.
