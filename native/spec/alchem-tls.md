# TLS

`TCP.connect_tls/2,3`, `https://` addresses of the HTTP client, `wss://`
addresses of `WebSocket.connect`, `HTTP.serve_tls/3,4` and the encrypted
connections of nodes, in the self-hosted compiler. The pinned runtime gets
all of this from Go's `crypto/tls` and `crypto/x509` with their defaults
(`compiler/library.go.txt`: `tcpConnectTLSWith`, `httpTrusting`,
`httpServeTLSWith`, `wsConnect`; `compiler/actor/node/node.go`). Nothing of
Go is under a native program, so the protocol, the certificates and the
arithmetic are done by the library: `library/TLS.alc`, written in Alchem,
on the sockets of `alchem-network.md`, the digests of `alchem-crypto.md`
and one more piece of machine code, `spec/tls-x86_64.s`.

`harness/tls.py` (with `harness/tls_data.py`) holds 159 known answers, 81
servers of Python's `ssl` module (OpenSSL) dialled by a native client, 5
requests through the tunnel of a proxy, 140 observations of native servers
by Python's `ssl`, curl, `openssl s_client` and a native client, 5
programs and 8 rejected. Every expectation of what a
program writes is what the same program built by the pinned compiler
writes; where `build/dev/alchem-upstream` is at hand the gate builds the
pinned programs again and compares them, clients and servers.

## What is built

- **Versions**: TLS 1.3 (RFC 8446) and TLS 1.2 (RFC 5246), as a client and
  as a server. Nothing older: Go's default minimum is 1.2 and upstream sets
  none. Nodes speak 1.3 alone, as upstream sets `MinVersion` for them.
- **Cipher suites**, Go's default list in Go's order (AES first where the
  processor has AES, else ChaCha20 first): TLS 1.3
  `TLS_AES_128_GCM_SHA256`, `TLS_AES_256_GCM_SHA384`,
  `TLS_CHACHA20_POLY1305_SHA256`; TLS 1.2 `ECDHE-ECDSA` and `ECDHE-RSA` with
  `AES128-GCM-SHA256`, `AES256-GCM-SHA384`, `CHACHA20-POLY1305`,
  `AES128-SHA` and `AES256-SHA` (CBC with HMAC-SHA1). The suites Go has
  switched off by default (RSA key exchange, 3DES, RC4, CBC-SHA256) are not
  built.
- **Key exchange**: X25519, P-256, P-384, P-521. A client sends an X25519
  share and answers a HelloRetryRequest for any of the other three; a
  server asks for another share with one.
- **Signatures**, in a handshake and in certificates: RSA PKCS #1 v1.5 and
  RSA-PSS with SHA-256, SHA-384, SHA-512 (moduli up to 8192 bits), ECDSA
  on P-256, P-384, P-521, Ed25519; with SHA-1 in a TLS 1.2 handshake, as
  Go still offers, and never in a certificate chain, as Go refuses.
- **Certificates** (X.509, RFC 5280) as `crypto/x509` verifies them: the
  chain is built from what the server sends up to a root of `ca_file:` or
  of the system (`SSL_CERT_FILE`, else the first readable of
  `/etc/ssl/certs/ca-certificates.crt`, `/etc/pki/tls/certs/ca-bundle.crt`,
  `/etc/ssl/ca-bundle.pem`, `/etc/pki/tls/cacert.pem`,
  `/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem`, `/etc/ssl/cert.pem`;
  and every file of the directories of `SSL_CERT_DIR`, else of
  `/etc/ssl/certs` and `/etc/pki/tls/certs`, but for links to files beside
  them; read once per program); candidates in Go's order (by key
  identifier), at most 100 signatures looked at; validity at the time of
  the handshake; the name (`server_name:`, else the host of the address)
  against the DNS names and addresses of the alternative names, a `*` for
  one whole first label, never the common name; basic constraints, path
  lengths, key usage of issuers, extended key usage down the chain,
  critical extensions nobody knows, name constraints for DNS names and
  addresses. `insecure: "true"` verifies nothing, and the certificates
  are still read.
- **A server's files** (`certfile:`, `keyfile:`): certificates in PEM, the
  key as PKCS #8, PKCS #1 or SEC 1, for RSA, P-256, P-384, P-521 and
  Ed25519; checked against the certificate as `tls.X509KeyPair` checks.
- **In a connection**: records of up to 16384 bytes; `close_notify` when a
  socket is closed, and a clean end read as `closed`; KeyUpdate received
  and answered, and sent after 2**23 records (that many were never sent
  in a test); session tickets received and
  passed over; a renegotiation refused (a server's request with `no
  renegotiation`, a client's new hello with `unexpected message`, as Go); a
  certificate asked of a client answered with none; ALPN `http/1.1`
  offered by the HTTP client alone; SNI for names, not for addresses; the
  extended master secret; the downgrade marks of RFC 8446 in both
  directions; at most 16 records in a row that bring nothing.
- **The failures a program sees** have Go's texts, compared with the
  pinned compiler case by case (the gate's CLIENTS and FILES):
  `tls: failed to verify certificate: x509: certificate signed by unknown
  authority` (with Go's hint `(possibly because of "..." while trying to
  verify candidate authority certificate "...")`), `certificate has expired
  or is not yet valid: current time ... is after ...`, `certificate is
  valid for a, b, not c`, `cannot validate certificate for 127.0.0.1
  because it doesn't contain any IP SANs`, `certificate relies on legacy
  Common Name field, use SANs instead`, `certificate specifies an
  incompatible key usage`, `unhandled critical extension`, `too many
  intermediates for path length constraint`, `a root or intermediate
  certificate is not authorized to sign for this name: DNS name "x" is not
  permitted by any constraint`, `remote error: tls: handshake failure` and
  the other alerts by Go's names, `tls: first record does not look like a
  TLS handshake`, `http: server gave HTTP response to HTTPS client`, `tls:
  either ServerName or InsecureSkipVerify must be specified in the
  tls.Config`, `timeout`, `closed`, `open x: no such file or directory`,
  `no certificates in x`, and the eleven texts of `tls.X509KeyPair`. A
  server answers plain HTTP on its port with Go's `400 Bad Request` and
  `Client sent an HTTP request to an HTTPS server.`

## How it runs

**A socket that speaks TLS** is the socket of `alchem-network.md` with
four more words (`library/TCP.alc`: the block is 208 bytes): what TLS
keeps for it and three function values that read, write and close through
it. `TCP._read` and `TCP._write` call them when they are set and the
system otherwise (`TCP._rawread`, `TCP._rawwrite`), so everything above
(`recv`, `recv_line`, packets, active sockets, the HTTP client and server,
WebSockets) works on such a socket unchanged, and a program without
`connect_tls`, an HTTP client, `WebSocket.connect` or `serve_tls` holds
none of `TLS.alc`. `HTTP.serve` likewise calls a function value the server
of `serve_tls` leaves (`hs + 112`) before a connection's first request.
`TCP.shutdown` of such a socket gives `not a connected socket`, as
upstream's does.

One process at a time writes a record (a lock in what TLS keeps); the
reading side is the socket's own lock. A read that runs out of time keeps
what came of a record for the next read.

**The machine code** (`spec/tls-x86_64.s`, 4,788 bytes;
`scripts/generate-tls-runtime.py` writes
`implementations/alchem/native-tls-data.alc`) is emitted once, in
function-table slot `functions+7`, for a program that holds `Sys.tls`,
which is to say one that got a function of `TLS.alc`. `Sys.tls(block)` is a
library-only primitive like `Sys.hash` (`native-system.alc`, operation 16).
The block's first word says what to do: Montgomery arithmetic on numbers
of 1 to 128 limbs of 64 bits (set up a modulus, multiply, add, subtract,
raise to a power, swap two numbers on a bit, reduce, compare, to and from
bytes); AES-128 and AES-256 in GCM and in CBC; ChaCha20-Poly1305. AES has
two forms chosen when a key is set up: AES-NI with PCLMULQDQ where CPUID
says the processor has them (and SSSE3), else software that looks nothing
up in a table (SubBytes as the inversion x^254 and the affine map on
sixteen bytes at once with SSE2; GHASH by 128 masked shifts). The header
of the file lists every operation.

**The curves** P-256, P-384 and P-521 are one piece of Alchem over that
arithmetic (Jacobian coordinates, a = -3, a Montgomery ladder whose two
points are swapped by the runtime on each bit; the scalar is first
lengthened by the group order to one length). X25519 is RFC 7748's ladder
over the same arithmetic. Ed25519 is TweetNaCl's, in Alchem (16 limbs of 16
bits). RSA raises to the private exponent in one piece, without the
Chinese remainder theorem, and checks its signature before it gives it.

**Time**, on one core of an i7-1360P: a handshake costs a client about
3 ms of processor time and a server 2 to 7 ms (the pinned client: 4.6 ms);
an ECDSA P-256 verification 1 ms, an RSA-2048 one 0.2 ms, an RSA-2048
signature 4 ms and an RSA-4096 one 33 ms, an X25519 0.4 ms, a P-256 key
0.5 to 1 ms, an Ed25519 signature or verification 15 to 30 ms; the 120
roots of this system are read in 24 ms, once. AES-GCM seals 1.3 GB/s with
AES-NI and 11 MB/s in software, ChaCha20-Poly1305 545 MB/s, AES-CBC 1.2 to
8 GB/s (software 9 to 14 MB/s).

## The compiler

`native-system.alc`: `Sys.tls` (operation 16), the runtime's slot
(`nh_shared`, `nh_slot`), and `nh_library`, for one line of
`native-compiler.alc`: inside the library the word `TLS` never means a
module of the program. The pinned library has no module `TLS`, so a
program may have one (`defmodule TLS`), which the library's own calls must
not find. `scripts/bootstrap-alchem-compiler.py`: the component
`native-tls-data.alc`. `library/Process.alc`, `library/TCP.alc`: the
struct lines name `TLS`; and a process's stack, when the system does not
grant 256 MiB, is an eighth of the last size asked for and not a half
(`alchem-processes.md`): under a limit on the address space a program with
a dozen processes otherwise ran out, which the larger programs of the
HTTP client and `WebSocket.connect` (they now hold `TLS.alc`) met first.

## Security

What is verified is what Go verifies with its defaults; nothing is
weakened for a test, and the gate's certificates that must fail do fail
with Go's reasons. Beyond that, honestly:

- **Constant time, by construction**: the runtime's large-number
  operations (their time depends on the sizes alone; powers by a fixed
  window of 4 bits with every table entry read under a mask), both forms
  of AES, GHASH, ChaCha20, Poly1305, the comparison of tags. So the
  ladders of X25519 and of the three curves take the same steps for every
  scalar, and RSA's private power for every exponent of a length.
- **Not constant time**: everything in Alchem around those operations.
  The ladders read the scalar's bits and the swaps' arguments in ordinary
  code (no branch on a bit, but nothing proves the compiler's code free of
  one); ECDSA signing reduces and inverts its nonce through the constant
  time operations but draws it by rejection; Ed25519 (TweetNaCl in Alchem)
  branches and indexes on secret bits, as `alchem-nodes.md` said; the
  PSS and PKCS #1 paddings are built in Alchem; RSA is not blinded.
  **TLS 1.2 with AES-CBC**: the padding and the HMAC of a record are
  checked in Alchem in a way meant to take the same steps whatever the
  padding says (255 bytes looked at, one HMAC over the text and one more
  digest over what is left, one failure for both), which is the shape of
  Go's defence against Lucky 13 and not a proof of it. The CBC suites are
  chosen only when the other end has none of the others.
- **Secrets stay in memory.** Nothing is reclaimed
  (`alchem-processes.md`) and nothing is wiped: keys, the working memory
  of the curves, round keys. The runtime clears its own stack frames for
  the ciphers and the powers.
- **Randomness** is `getrandom`, each time.
- **Not checked, as Go does not**: revocation (CRL, OCSP), certificate
  transparency.
- **Speculative execution**: no hardening.

## Differences from Go that remain

- **No session tickets and no resumption.** A client offers none and
  passes over the tickets a server sends; a server sends none. Every
  connection is a full handshake. Resumption needs a store of sessions on
  both sides and the PSK binders of RFC 8446; a server that sent tickets
  it then refused would be dishonest to its clients. (`openssl s_client`
  shows a second session block with Go's server and not here.)
- **No hybrid key exchange.** Go's first key share is X25519MLKEM768;
  ML-KEM (and ML-DSA signatures) are lattice arithmetic of their own
  (FIPS 203, 204), not built. Every server that takes Go's X25519MLKEM768
  share also takes X25519.
- **HTTP/2.** Go's HTTP client offers `h2` and `http/1.1` and speaks
  HTTP/2 to a server that chooses it; the native client offers
  `http/1.1` alone and so speaks HTTP/1.1 to every server
  (`alchem-network.md`: no HTTP/2).
- **The ClientHello's bytes** are not Go's (no `status_request`, signed
  certificate timestamps, PSK modes, ML-KEM share; a different order): a server that fingerprints its clients sees another
  client.
- **Certificate policies** (`policiesValid`: explicit policy, policy
  mappings, inhibit-any-policy) are read past and not evaluated; Go
  rejects a chain whose authorities require an explicit policy that the
  chain does not carry. **Name constraints** are applied to DNS names and
  addresses; those on e-mail addresses and URIs are not, since a server's
  certificate is matched by neither.
- **A certificate that cannot be read** is `x509: malformed certificate`
  whatever is wrong with it; Go names the part (`x509: malformed
  validity`, `x509: invalid subject alternative names`, ...). And the
  reader is laxer than Go's in what it never uses: it does not refuse a
  negative serial number, malformed strings in a name, or what is wrong
  inside the extensions it passes over.
- **A private key that cannot be read**: the words after `tls: failed to
  parse private key: ` are those of `encoding/asn1` for a wrong tag or
  length at the five places PKCS #8 has them (which covers an encrypted
  key and bytes that are no key); a key that is PKCS #8 outside and
  malformed inside gets `x509: failed to parse RSA private key embedded in
  PKCS#8` (or `EC`, or `x509: invalid Ed25519 private key`) without Go's
  reason after it.
- **Alerts sent.** Where a handshake fails here the other end is sent the
  alert Go sends in the cases looked up (`bad certificate`, `protocol
  version`, `handshake failure`, `illegal parameter`, `decode error`,
  `decrypt error`, `unexpected message`, `bad record MAC`, `record
  overflow`, `no renegotiation`); in the rarer refusals of a malformed
  message the alert may be another of these than Go's. What a server
  thinks of a failed handshake no program sees (upstream discards the
  server's log).
- **Ed25519 is slow** (15 to 30 ms a signature or verification, Go: 0.05
  ms): it is the one curve still done with TweetNaCl's arithmetic in
  Alchem. It is correct (RFC 8032's vectors, OpenSSL and Go as peers).
- **RSA signs without the Chinese remainder theorem**: 4 ms for 2048 bits
  where Go takes 1 ms.
- **One thread** (`alchem-processes.md`): a handshake's arithmetic is not
  interrupted, so a server's other connections wait the 2 to 7 ms it
  takes, or 33 ms with an RSA-4096 key.
- **Memory** (nothing is reclaimed): a connection costs a client about
  130 KB of the arena, most of it the certificates read and the handshake's
  messages, and each record sent or received its own bytes once more.
- **Go's switches** (`GODEBUG=tlsrsakex=1`, `tls10server=1`,
  `x509negativeserial=1`, ...) do not exist.
