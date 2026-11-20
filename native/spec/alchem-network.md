# The network modules and DiskStore

`TCP`, `UDP`, `HTTP`, `WebSocket` and `DiskStore` of the pinned compiler
(`compiler/library.go.txt`, the sections "TCP" to "WebSocket" and
"DiskStore"; `docs/library-reference.md`), in the self-hosted compiler.
All of it is written in Alchem (`library/TCP.alc`, `UDP.alc`, `HTTP.alc`,
`WebSocket.alc`, `DiskStore.alc`) on raw Linux system calls
(`alchem-system.md`) and the processes of `alchem-processes.md`; nothing of
Go's `net`, `net/http`, `compress` or `crypto` is under it, so what those
packages do for the pinned runtime is done here by the library, and written
to give the same results, texts and bytes on the wire.

`harness/network.py` holds 65 programs with the pinned compiler's status,
output and failure trace frozen in (the 46 examples of the library
reference for TCP, UDP, HTTP and WebSocket; 17 probes; one over IPv6; one
of the name-server client) and 20 it rejects. `harness/diskstore.py` holds
15 (the 13 examples among them) and 7. The 75 function signatures of the
five modules in the pinned registry are all here.

## What is built

`HTTP.json(status, value)` answers with the value as `JSON.encode` writes
it (`alchem-json.md`) under `content-type: application/json`.

- **TCP**: `listen/1,2`, `accept`, `connect/2,3`, `connect_tls/2,3` (see
  TLS), `send`, `recv`, `recv_line`, `close`, `shutdown`, `setopts` (atoms
  and numbers: `active:` true, `:once`, false, a count; `packet:` `:raw`,
  `:line`, 0, 1, 2, 4), `controlling_process`, `address`, `peer`. A socket
  is `socket` (`inspect`: `#socketHandle<>`); `TCP.Event` is
  `data(text)`, `closed`, `error(reason)`.
- **UDP**: `open`, `send`, `recv`, `close`, `address`, `setopts`,
  `controlling_process`; `UDP.Event` is `datagram(from, text)`,
  `error(reason)`.
- **HTTP**: the server (`serve/2,3` with `read_timeout:`, `write_timeout:`,
  `idle_timeout:`, `header_timeout:`, `max_header_bytes:`,
  `max_body_bytes:`, `keep_alive:`, `compress:`; `address`, `stop`,
  `await`, `take_over`, `serve_tls/3,4`), the client (`get/1,2`, `post`,
  `request/4,5` with a time or options `timeout:`, `stream:`, `redirect:`,
  `ca_file:`, `insecure:`; `stream`), and `text`, `chunked`, `read`,
  `header`, `match`, `route`. `HTTP.Request`, `HTTP.Response`,
  `http_server` (`#httpServer<>`).
- **WebSocket**: `upgrade/1,2` (`compress:`, `max_message_bytes:`),
  `connect/2,3,4` (`origin:`, `compress:`, `ca_file:`, `insecure:`, extra
  headers), `send`, `send_binary`, `recv`, `close/1,3`, `setopts`,
  `controlling_process`, `peer`, `compressed?`; `websocket` (`#wsConn<>`),
  `WebSocket.Event`.
- **DiskStore**: `open`, `close`, `put`, `get`, `delete`, `has_key?`,
  `keys`, `size`, `range`, `prefix`, `commit`, `update`, `compact`;
  `disk_store` (`#storeHandle<>`).

## How it runs

**One thread, no blocking call.** Every socket is opened non-blocking. A
call that has to wait (accept, connect, a read that finds nothing, a write
that finds the buffer full) puts its process on a list of descriptor
waiters and gives way (`Process._fdwait`). The scheduler
(`Process._pick`, `library/Process.alc`) polls: when no process is ready
it calls `ppoll` on every waited descriptor, for as long as the nearest
timer allows or for ever when there is none, and makes ready the processes
whose descriptor is; while processes are ready it looks at the descriptors
every sixteenth turn without waiting, so a program that never idles still
serves its sockets. A program with waiters is not deadlocked: `fatal
error: all goroutines are asleep` is written only when nothing waits for a
time or a descriptor. A wait ends at once when its process is asked to
stop and when the socket is closed by another process (`Process._fdshut`);
the pinned runtime looks every 50 milliseconds.

The changes this made to `library/Process.alc`: `_pick` polls as said; the
functions `_poll`, `_pcount`, `_pfill`, `_pmark`, `_fdwait`, `_fdshut`
were added at its end; the structs `pid` and `Process.Exit` are also
wanted by programs that name `TCP`, `UDP`, `HTTP`, `WebSocket` or
`DiskStore`. The words of the processes' block these modules use are
listed at the top of `library/TCP.alc`.

**Sockets** follow Go's `net`: `SO_REUSEADDR` on listeners, `TCP_NODELAY`
and keep-alive probes every 15 seconds on connections, the address that
stands for every address (`:0`, `0.0.0.0:0`, an empty host) bound for IPv6
and IPv4 at once and shown as `[::]:port`, addresses written as Go writes
them (IPv6 compressed, an IPv4 peer of such a socket as `127.0.0.1:port`,
zones by interface name). Reads go through what Go's 4096-byte buffered
reader would hold, so `TCP.recv(s, 0, ms)` gives what one read brought, a
length gives exactly that many bytes, a read that runs out of time keeps
what it has for the next, and a wait of 0 gives `timeout` unless the bytes
are already held, all as upstream. The texts of failures are Go's: `dial
tcp 127.0.0.1:1: connect: connection refused`, `listen tcp: address x:
missing port in address`, `lookup tcp/x: unknown port`, `write tcp a->b:
write: broken pipe`, `read udp ...`.

**Names.** A host is taken, in this order: as an address Go reads
(`127.0.0.1`, `::1%lo`), as one the C library reads (`127.1`,
`0x7f.0.0.1`, `010.0.0.1`), from `/etc/hosts`, and then from the name
servers of `/etc/resolv.conf` (`nameserver`, `search`/`domain`, `options
ndots: timeout: attempts:`), asked for A and AAAA records over UDP and
again over TCP when an answer is cut short. That is the order of the C
library's `getaddrinfo`, which the pinned runtime calls, on a system set
up with `hosts: files dns`. Several addresses are tried in turn, those the
machine has a way to first and IPv6 before IPv4 among them; a listener
takes the first IPv4 address. Ports may be names of `/etc/services`.

**HTTP server.** One process accepts; each connection has a process that
reads requests and writes answers; each request runs the handler in a
process of the program (counted by `Process.count`, stopped when the
client goes away or the server stops), as upstream. The bytes are those of
Go's server: the status line and its texts, the handler's headers in the
order of their canonical names and then `Date`, `Content-Length`, a
sniffed `Content-Type`, `Connection` and `Transfer-Encoding`; a body of up
to 2048 bytes with its length and a longer one in chunks of 2048;
`HEAD`, 204 and 304 without a body; HTTP/1.0 with and without keep-alive;
`Expect: 100-continue`; chunked request bodies; pipelined requests; the
refusals (`400 Bad Request: missing required Host header`, 413, 417, 431,
501, 505) with their exact bytes; gzip on request when `compress:` is set,
by Go's rules for which bodies; a failing handler as 500; `take_over` and
`WebSocket.upgrade` leaving the connection, with what the client sent
after the request, to the handler. `HTTP.Request.headers` are Go's: lower
case, sorted, `host` put back, `cache-control: no-cache` added for
`Pragma: no-cache`.

**HTTP client.** The request is the one Go's transport writes (`Host`,
`User-Agent: Go-http-client/1.1`, `Content-Length`, the caller's headers
sorted, `Accept-Encoding: gzip`, `Authorization: Basic` from the
address's user). The answer's body is read by its length, its chunks or to
the end of the connection, gzip is undone when it was asked for (and
`content-encoding` and `content-length` leave the headers then), 1xx
answers are passed over, redirects are followed as Go's client follows
them (301, 302, 303 become GET without the body and its content headers;
307 and 308 repeat; `Referer`; credentials dropped when the host changes;
`stopped after 10 redirects`), `HTTP_PROXY` and `NO_PROXY` are honoured
for `http://` addresses and `HTTPS_PROXY` for `https://` ones, and the failures have Go's texts (`Get
"http://127.0.0.1:1/": dial tcp 127.0.0.1:1: connect: connection refused`,
`parse "...": invalid port ":x" after host`, `unexpected EOF`, `net/http:
HTTP/1.x transport connection broken: malformed HTTP status code "abc"`).

**WebSocket.** A process reads frames from the connection's start,
answers pings and the closing handshake, and queues up to sixteen events;
`recv` and an active socket take them from there. Masking, fragments,
control frames between them, the close codes and every protocol failure
are answered with the pinned runtime's bytes (`harness/network.py` sends
27 hand-made frame sequences to a server). permessage-deflate is
negotiated and spoken as upstream (each message on its own).

**Compression and hashes** are in `library/HTTP.alc` and
`library/WebSocket.alc`: inflate (RFC 1951, every block type), deflate,
gzip (RFC 1952) with CRC-32. The language has
no bit operations in library code, so exclusive or is a table of 65,536
bytes built once (`HTTP._k`), and shifts are multiplications and
divisions. The SHA-1 of the handshake is `Crypto.hash(:sha1, ...)`, the
machine code of `alchem-crypto.md`.

**DiskStore** keeps the pinned file format byte for byte (the magic line,
records of length, CRC-32 and changes with varint lengths), replays a log
up to its first torn or spoiled record and cuts it there, writes and
`fsync`s before a call returns, rewrites the file beside itself and
renames it over (`compact`, and by itself when the file is more than
twice what it holds plus a megabyte), gives the same store for a path
opened twice, and holds every other writer off while `update` runs its
function. Keys are kept in order in a mapped array, values in the arena.

## The compiler

`implementations/alchem/native-network.alc` (component `sk_`) names the
four handle types the pinned compiler writes in lowercase and what
`inspect` writes for them; `ac_typeword` and `ac_shown`
(`native-processes.alc`) ask it. One line of `nv_typed`
(`native-records.alc`) lets `TCP.Event.data(x)` name a sum type of the
library that is written with its module. Nothing else changed.

## Differences from upstream that remain

- **TLS** is built (`alchem-tls.md`): `TCP.connect_tls`, `https://` and
  `wss://` addresses, `HTTP.serve_tls`, with `ca_file:`, `insecure:` and
  `server_name:`. What remains different from Go's `crypto/tls` (no
  session tickets, no hybrid key exchange, `http/1.1` alone offered) is
  listed there.
- **Compressed bytes.** gzip bodies and compressed WebSocket messages are
  valid and read by any inflater, but are not the bytes Go's
  `compress/flate` writes: the encoder here is one block of the fixed
  codes over a hash-chain match finder. Those bytes are not the pinned
  compiler's own either, they are the Go release's it was built with. It
  shows in the `content-length` of a gzip answer a client asked for by
  itself, and on the wire.
- **The client keeps no connections.** Each request opens one and closes
  it; Go's transport keeps idle connections and writes `Unsolicited
  response received on idle HTTP channel` to standard error when a server
  says more than it should. No HTTP/2. A proxy is a plain `http://` one:
  `HTTP_PROXY` for `http://` addresses and `HTTPS_PROXY` for `https://`
  ones, which are tunnelled through it with `CONNECT` as Go tunnels them
  (`harness/tls.py`); a proxy that is itself reached by `https://` or
  `socks5://` fails with `proxy: the scheme ... is not built`. IPv6 ranges
  in `NO_PROXY` are not matched.
- **A response read in pieces that is gzip** (`stream: "true"`) is read
  whole at the first piece and then given in pieces of 32 KiB; upstream
  inflates as it reads. The pieces of other streamed bodies are cut where
  the reads fall, as upstream's are, which is not always at the same
  bytes.
- **Names**: `/etc/nsswitch.conf` and `/etc/gai.conf` are not read (the
  order is hosts, then DNS; no mDNS or systemd modules), no EDNS, no
  internationalised names, `rotate` and the other options are ignored, and
  the order of several addresses is the reachable ones first with IPv6
  before IPv4, not all of RFC 6724. A connection tries its addresses one
  after another; Go races the two families 300 milliseconds apart.
- **The scheduler decides.** Handlers run one at a time, each until it
  waits; a handler that computes without waiting, `System.cmd` and
  reading standard input hold every connection up (`alchem-processes.md`,
  "One thread"). Where upstream decides by chance, native programs always
  give one outcome: a WebSocket closed from this end whose peer did not
  answer gives `closed(1006, "")` to the next `recv` before `closed`
  (upstream gives either). A socket made passive is passive when
  `setopts` returns once the sending process has run; upstream takes up
  to 50 milliseconds.
- **Memory.** Nothing is reclaimed (`alchem-processes.md`): a request
  answered takes about 7 KB of the arena on the server's side and 9 KB on
  the client's, an echoed WebSocket message about 1 KB, a line read from
  a socket under 200 bytes, so a server of the default 16 GiB arena
  answers some two million small requests. The blocks of sockets (208
  bytes), requests (152) and WebSockets (184) are not given back either.
  A value replaced in a DiskStore stays in the arena.
- **`DiskStore.update` whose function writes to the store** waits for
  itself in both; upstream then hangs for ever, a native program with
  nothing else to wait for ends with `fatal error: all goroutines are
  asleep - deadlock!` and status 2.
- **HTTP server details not built**: an informational status (100 to 199)
  from a handler is written as a last answer without a body, not as an
  interim one; `Transfer-Encoding: identity` set by a handler is dropped
  like any other; a `Content-Length` a handler writes with a sign is
  taken as none; the kinds of body the sniffer knows are Go's commonest
  (HTML, XML, PDF, PostScript, the image, audio, video, font and archive
  signatures, text, binary) without EOT fonts.
- **Listeners** ask for a backlog of 4096, which the kernel cuts to its
  own limit; Go reads the limit from `/proc`.
- **A function value that only gives `none`** (`fn _ -> none end`) is not
  typed by the parameter it is passed for, here or anywhere
  (`DiskStore.update(store, key, fn _ -> none end)` is rejected); write
  its types out.
