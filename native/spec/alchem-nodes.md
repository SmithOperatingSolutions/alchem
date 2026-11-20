# Nodes

`Node`, `Stream.publish` and the handles of other nodes' processes of the
pinned compiler (`compiler/actor/node/node.go`, `compiler/actor/remote.go`,
`compiler/codec.go`, the "---- Node ----" functions of
`compiler/library.go.txt`, `docs/runtime.md` "Nodes"), in the self-hosted
compiler. All of it is written in Alchem (`library/Node.alc`) on the sockets
of `alchem-network.md`, the processes of `alchem-processes.md` and the
digests of `alchem-crypto.md`; nothing of Go's `net` or `crypto/tls` is under
it, so the TLS 1.3 that upstream gets from Go is done here by the library
(`library/TLS.alc`, `alchem-tls.md`).

`harness/nodes.py` holds 25 programs of one node with the pinned compiler's
status, output and trace frozen in (the 15 examples of `## Node`, the one of
`Stream.publish` and the one of the syntax reference's "nodes"; 8 probes),
20 programs it rejects, 14 pairs of programs run as two nodes, a node
written in Python from `node.go` that compares a native node's answers byte
for byte, and a TLS 1.3 handshake made by Python's `ssl` module (OpenSSL)
with a native node.

## What is built

- **Node**: `start/2,3,4` (`encrypted:`; the cookie of `ALCHEM_COOKIE`),
  `self`, `address`, `connect/1,2` (`reconnect: true`, `reconnect: n`),
  `disconnect`, `list`, `monitor`, `monitor_nodes`, `whereis/2,3`,
  `whereis_global`, `register_global`, `serve`, `call/3,4`, `cast`,
  `stream`. `Stream.publish`. Every result, failure text and trace is the
  pinned one in the cases probed (below).
- **Handles of another node's process** (`pid[t]` from `Node.whereis`, from
  `Node.whereis_global`, or decoded from a message): `Process.send`,
  `send_after`, `id`, `alive` (is its node connected), `monitor`,
  `demonitor`, `link`, `unlink`, and `Server.monitor`. `Process.receive`,
  `await`, `stop`, `report` and the receive assertions fail with `this needs
  a process of this node; a process of another node can only be sent to`.
  `Process.register` and `Node.register_global` of one give `false`.
- **What crosses**: integers, floats, booleans, strings, atoms, lists,
  tuples, maps, sets, structs (generic ones too), sum types (those that
  hold themselves too), `option`, `result`, `Date`, `Time`,
  `NaiveDateTime`, `DateTime`, and process handles, which cross as the
  node's name and the process's number and come home as the process itself.
- **The compiler's checks**: a call that needs a type's form on the wire
  (`Process.register`, `Process.whereis`, `Node.whereis`, `whereis_global`,
  `register_global`, `serve`, `call`, `cast`, `stream`, `Stream.publish`)
  is rejected when the type is not known where the call stands (upstream:
  `cannot infer the result type of Node.whereis here; annotate the binding`)
  or holds something with no form on the wire (`Process.register cannot be
  used with messages of type list[regex]: regex cannot be sent to another
  node`). And the check `alchem-processes.md` listed as missing is made: a
  `pid[...]`, `supervisor[...]`, `server[..., ...]` or `task[...]` whose
  argument holds a function, a stream or a type variable is rejected where
  the program writes it (upstream: `invalid type "pid[fn[integer]]"`,
  `mailbox messages cannot contain functions`), for `pid`, `supervisor` and
  `server` through the fields of declared types, for `task` as far as the
  type is written out, as upstream.

## The wire

The pinned format, byte for byte (`node.go`). A connection starts with one
byte from each end, the dialling end first: `T` when it encrypts, `P` when it
does not. Then, encrypted or not, messages of a four-byte length (most
significant first, at most 64 MiB) and that many bytes.

Without encryption each end sends 32 random bytes and the binding is the
SHA-256 of the dialler's and then the accepter's. With it the binding is the
32 bytes TLS exports under the label `alchem node cookie proof`. Each end
then sends `alchem node 4`, its name and HMAC-SHA-256(cookie, binding, 0, its
role (`dialling` or `accepting`), 0, its name), each as a length and bytes; a
wrong proof closes the connection.

A message begins with its kind: 1 a message for a process (its number, the
value), 2 a name looked up (request, name, the type's text) and 3 the answer
(request, found, the number), 4 a monitor asked for (number, reference) and
5 the process's end (reference, number, reason), 6 a published stream asked
after (request, name, the type's text), 7 its next chunk asked for (request,
name, subscription, finished) with answer 3 (request, done, count, the
elements: up to 256 or 64 KiB), 8 the end of a linked process (number,
reason). Integers are Go's signed varints; a float is its eight bytes, most
significant first; a boolean one byte; a string or atom a length and bytes;
a list its count and elements; a tuple or struct its fields; a sum type its
variant's index and fields; `none` 0 and `some` 1 with the value; `ok` 0 and
`error` 1 likewise; a map its count and entries, a set its count and
elements; a handle its node's name and its number. The answer of a served
function is one byte (1 with the value, 0 with the reason), as upstream's
`rpcCodecs` has it.

The type's text is the pinned compiler's (`tuple[atom,list[option[integer]]]`,
`Wire.Order`, `Rich.Box[list[string]]`, `Date`): two nodes find a name only
for the same text.

**Checked against the pinned compiler itself**: the pinned repository's own
two-program tests (`testdata/nodes`, `testdata/cluster`), a message of every
kind of value echoed back, and a program of monitors, links, streams,
served functions and a node that goes away were each run as pinned and
pinned, native and native, pinned server with native client, and native
server with pinned client, encrypted and not: the outputs are the same in
all of them. So were the handshake's failures (cookies that differ, one end
encrypting, two nodes of one name) and a kept connection given up. A native
node and a pinned node are one cluster.

## How it runs

**The form of a type.** A value carries no type at run time and the library
encodes it, so before each of the calls above the compiler writes the form of
the type into the code and stores its address at R14-72
(`implementations/alchem/native-nodes.alc`, `dn_typed`; hooked beside
`ac_typed` in the one line of `native-prelude.alc` that places a library
call): a count, and per type the pinned text and a node per part of the type
(the tags are listed at the top of `native-nodes.alc`; a type that holds
itself points back at its own node). `Node._e` and `Node._d` walk a value by
its node. A function written without parameters (`Stream.publish(:n, fn ->
... end)`) is compiled for its own type first, since the callee gives it
none. The codecs of `Node.serve` and `Node.call` (the argument with the
handle to answer, and the answer) are nodes the library makes at run time
around the two forms.

**A map or set** arrives in any order (upstream sends a hash trie's) and is
sorted by its keys' node, a key that comes twice keeping its last value, so
it is the same value a native program builds.

**Processes.** The node keeps processes that are none of the program's own
(`Process._go`: not counted by `Process.count`, no numbers taken): one
accepts connections, one per connection reads it, one per kept connection
redials. What upstream starts as processes of the program is started so
here, so `Process.count` and the numbers agree: the two of `Node.serve`,
one per call and one for its task, the one that waits for a call's answer,
the one of a cast to another node, the one of a published stream, the
helper of a link or of `Server.monitor` to another node's process.

**A handle of another node's process** is a block like a process's record
with 2 where a process has "not of the program" (offset 320), its number at
40 and at 24 a function value of the node; `Process._send`, `alive`,
`monitor`, `demonitor`, `link` and `unlink` call it there, so
`library/Process.alc` names nothing of `Node` and a program without nodes
holds none of this.

**TLS 1.3** is the library's (`alchem-tls.md`), asked for version 1.3
alone, as upstream sets `MinVersion`. The dialling end verifies nothing of
the certificate it is shown but the signature of the handshake under its
key (upstream sets `InsecureSkipVerify`, and Go checks that signature
still); the accepting end shows a certificate of the node's own (X.509 v3,
Ed25519, the node's name, valid from an hour before for twenty years,
signed by itself). The proof of the cookie is tied to the 32 bytes the
session exports under `alchem node cookie proof`. A node's connection goes
on writing a record when its process is asked to stop. Checked against
Go's `crypto/tls` in both roles (the runs above) and against OpenSSL as a
client (the gate). The compiler gives the library seven operations for
its arithmetic (`Process.__xor`, `__and`, `__or`, `__shl`, `__shr`, and
`__add`, `__mul` without the overflow check; `dn_op`).

**Standard input.** The pinned repository's cluster server waits with
`IO.read(:eof)` while its node serves. One thread cannot block in `read`
and serve, so in a program with processes the library's reads of standard
input (`IO.read`, `IO.gets`, `IO.binread`, `IO.stream`) now wait for the
descriptor as sockets are waited for (`Sys.ready`, through a function value
`Process._boot` leaves at g + 1032), and `IO.read(:eof)` reads to the end
that way. `IO.read_line()` and `IO.read_all()` called directly are the
compiler's own code and still block the thread (`alchem-processes.md`, "One
thread").

## Changes outside `library/Node.alc` and `native-nodes.alc`

- `native-prelude.alc`: `dn_typed(...)` around `ac_typed(...)` in `ny_call`'s
  last line. `native-processes.alc`: `ac_op`, `ac_intrinsic` and `ac_emit`
  pass the seven new operations to `dn_op`/`dn_emit`. `native-records.alc`:
  `nd_resolve_instance` passes its result through `dn_checked` (the mailbox
  check). `scripts/bootstrap-alchem-compiler.py`: the component.
- `library/Process.alc`: the struct lines name `Node` and `Stream.publish`;
  `_boot` leaves the function of `Sys.ready`; `_send`, `alive`, `monitor`,
  `demonitor`, `link`, `unlink` go to a handle's function; `receive`,
  `await`, `stop`, `report` and the receive assertions refuse one;
  `register` keeps the form and refuses one; `whereis` compares the type's
  text when both sides have one; `_far`, `_home`, `_reach` at the end.
- `library/Server.alc`: `monitor` of another node's process (`_watch`).
  `library/Stream.alc`: `publish` at the end. `library/TCP.alc`,
  `library/Task.alc`: the struct lines. `library/Sys.alc`: `ready`, `busy`,
  `rest` at the end and `ready` before the reads of `load`, `fill`, `next`,
  `bin`. `library/IO.alc`: `read/1` as said above.
- Words taken: R14-72 (the forms of the call that follows), g + 1024 (the
  node's block), g + 1032 (the function that waits for a descriptor). No
  type tag and no inspect node were added; the wire's node tags are private
  to `native-nodes.alc` and `Node.alc`.

## Differences from upstream that remain

- **The node's key is Ed25519**, where Go's nodes make ECDSA P-256 keys:
  each kind of node verifies the other's signature (the dialling end
  checks the CertificateVerify under the certificate's key now, of
  whatever kind: `tls: invalid signature by the server certificate: ...`,
  as Go). An Ed25519 signature costs 15 ms here (`alchem-tls.md`).
- **No hybrid key exchange and no session tickets** (`alchem-tls.md`): two
  pinned nodes agree on X25519MLKEM768 between themselves, a native node
  and any other on X25519. The suite is Go's choice: AES-128-GCM where
  the processor has AES, else ChaCha20-Poly1305.
- **Texts of a failed TLS handshake** are Go's for what was probed (`EOF`,
  `tls: first record does not look like a TLS handshake`, `tls: oversized
  record received with length N`, `remote error: tls: handshake failure`
  and the other alerts by name, `tls: client offered only unsupported
  versions: [303 302 301]`).
- **Ranges** have a type of their own natively and do not cross: a call
  whose message type holds one is rejected (upstream has no range type to
  annotate; a range there is a list or a stream).
- **A struct no code uses** is not looked into: `struct S do p: pid[fn[integer]] end`
  alone compiles, where upstream reports the invalid type. The same holds
  for any other invalid field type of an unused struct whose first part is
  a library handle (`pid[nosuch]`).
- **`pid[tuple[integer, pid[regex]]]` registered** is rejected here; the
  pinned compiler panics (`no wire form for regex`).
- **Order where upstream's is chance**: `Node.whereis_global` asks the
  connected nodes in the order they connected, newest first (upstream: a Go
  map's order); a map's entries go out in key order (upstream: a hash
  trie's). The receiving node builds the same value either way.
- **Memory** (`alchem-processes.md`: nothing is reclaimed). A message
  received costs its value in the arena and its bytes once more; a handle
  decoded from a message costs a block of 384 bytes that is given back only
  for the handle a served call answers through; a process named in a
  message that goes out is remembered for good (32 bytes; upstream's table
  of reachable processes also only grows), except the one that waits for a
  call's answer, which is forgotten when the call returns.
- **One thread.** A process that computes without waiting holds the node's
  reader and its timers up, as it holds every process up; upstream's ten
  seconds for a write and five for a full mailbox are counted from when the
  node's process gets to run.
