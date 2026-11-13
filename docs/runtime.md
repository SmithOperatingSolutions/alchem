# Process and fault-tolerance runtime

## Execution and ownership

Every executable has a root process context. `pid[T]` is an unforgeable local capability for a process whose mailbox carries `T`. IDs are unique positive integers within the runtime; use `Process.id` to compare identities. PID and supervisor capabilities cannot be structurally compared or constructed from integers.

`Process.spawn` runs a typed callback on a goroutine with a new context. Generated functions/closures receive that context as a hidden argument; callbacks execute in the invoking process context rather than inheriting the process that created the closure. Every generated statement/function body checks cancellation, and runtime waits select on cancellation. This uses no goroutine-ID discovery or thread-local state.

Mailboxes are bounded FIFO queues with capacity 1–1,000,000. Concurrent senders are ordered by successful enqueue; ordering between racing producers is unspecified. Only the owning context may receive. Sending does not copy: tuples, lists and maps are immutable, so the receiver is handed the same value and neither process can observe the sharing. A message stays reachable while either side holds it; there is no per-process heap. The mailbox buffer grows on demand up to its capacity. Integers, booleans and strings are values; PID/supervisor handles are explicitly shared capabilities. Functions, including functions nested in collections, are not sendable. Closure captures are already immutable and may share read-only storage when used as spawn callbacks. There is no mutable collection assignment in the language.

A process has one mailbox type, fixed by its spawn callback or first `Process.self` call. Later `self` calls must use that same type; the original capacity remains in effect. Root code supplies expected type context, e.g. `parent: pid[string] = Process.self(8)`.

## Processes and messages

| API | Result and behavior |
| --- | --- |
| `Process.self(capacity)` | `pid[T]` from an expected type; establish/retrieve the current mailbox |
| `Process.spawn(callback, capacity)` | `pid[T]`; callback type is `fn[pid[T],integer]` and receives its self PID |
| `Process.id(pid)` | Integer identity |
| `Process.alive(pid)` | False once stopping or terminated |
| `Process.send(pid, value, milliseconds)` | Boolean enqueue success; false on timeout, stopped or dead target |
| `Process.receive(self, milliseconds)` | `tuple[boolean,T]`; false on timeout; the second field is unspecified unless true |
| `Process.await(pid, milliseconds)` | `tuple[boolean,string]`; true plus exit reason after the full owned subtree terminates; awaiting self is rejected |
| `Process.stop(pid)` | Request cancellation; boolean indicates whether a new stop was requested |
| `Process.loop(initial,callback)` | Constant-stack state loop; callback `fn[State,tuple[boolean,State]]` returns continue flag/new state; return final state when false |
| `Process.sleep(milliseconds)` | Cancellable sleep; returns 0; duration must be nonnegative. `Process.sleep(0)` yields to other processes without sleeping, which is the right pause inside a polling loop |
| `Process.crash(reason)` | Raise a recoverable process failure; typed as integer so it can be returned from a worker |
| `Process.report(pid)` | Retained failure location/frames, or termination reason; meaningful after joining |

Wait durations are milliseconds: negative means indefinite, zero polls, positive bounds waiting. Extremely large positive waits clamp to the maximum representable timer duration instead of overflowing. Mailbox capacity is fixed, and send backpressure never grows the queue. Blocked senders wake when space is freed or a participant stops. Successful sends to self can fill its mailbox; an indefinite send to a full self mailbox cannot make progress without a receive, so use deadlines where appropriate. Receive is FIFO, not a selective-receive language form.

A callback returning 0 exits `normal`; other return codes exit as `exit:N`. Stop requests exit `shutdown`. Failures retain their message as reason, except user crashes named `normal`/`shutdown` are reported as `error: normal`/`error: shutdown` so they cannot masquerade as successful exits. Dead PIDs retain identity and report metadata, reject sends, and cannot be reused for a restarted worker. New workers receive new PIDs.

Long-lived workers should use `Process.loop` instead of recursive server calls. The runtime keeps only the current immutable state and checks cancellation at every iteration. Each callback activation returns before the next starts, so message history does not accumulate on the Go stack. A callback may receive, send, match, update immutable state or fail normally. Return `{false,state}` to finish the loop. A function that calls itself in return position also runs as a loop (see the [language specification](language-spec.md)); other recursion uses the stack.

## Monitors and links

| API | Result and behavior |
| --- | --- |
| `Process.monitor(pid)` | New positive reference; one termination notification, including for an already terminated process |
| `Process.demonitor(pid, reference)` | Remove the subscription and flush a queued matching notification; boolean indicates removal/flush |
| `Process.link(pid)` | Register a symmetric link; false for self or an already terminated target |
| `Process.unlink(pid)` | Remove both directions; boolean indicates a prior link |
| `Process.trap_exits(boolean)` | Set exit trapping and return the old setting (default false) |
| `Process.event(milliseconds)` | `tuple[boolean,integer,integer,string]`: available, reference, process ID, reason |

Events have a separate control queue so runtime notifications never masquerade as typed user messages. Monitor references are positive. Link events have reference 0. Multiple notifications caused by one exit may appear in either order; correlate by reference/ID. A monitor does not kill its observer. An untrapped abnormal linked exit cancels the other process and propagates through links; normal/shutdown exits do not. Trapped links deliver notifications for all exit reasons. Linking an already terminated target applies the same notification/failure rules immediately.

Exit bookkeeping removes monitors/links in both directions. Notifications are not dropped because a data mailbox is full. Dead contexts release queued data and their own event subscriptions. Process metadata held by a user PID remains available for joins/reports until the handle is collected.

## Supervision

`supervisor[T]` manages children sharing message type `T`. A child specification is `tuple[string,string,fn[pid[T],integer]]`: stable child name, restart policy, and callback. Names are nonempty and unique; the list is nonempty. Child callbacks and closures follow the same immutable capture rules as ordinary processes.

```elixir
specs = [{"worker","permanent",&Workers.run}]
group = Supervisor.start("one_for_one",3,1000,specs,8)
worker = Supervisor.child(group,"worker")
```

| API | Result and behavior |
| --- | --- |
| `Supervisor.start(strategy,maxRestarts,windowMS,specs,capacity)` | `supervisor[T]`, owned by the creating process |
| `Supervisor.start_link(...)` | Same arguments, additionally link the manager's exit to its creator |
| `Supervisor.child(group,name)` | Current/last `pid[T]` for the named child; unknown names are errors |
| `Supervisor.children(group)` | `list[tuple[string,integer]]` in declaration order, with current/last child IDs |
| `Supervisor.restarts(group)` | Number of restart cycles started |
| `Supervisor.alive(group)` | Whether the manager is running |
| `Supervisor.stop(group,milliseconds)` | Request shutdown and wait; false if the wait expires; shutdown continues |
| `Supervisor.await(group,milliseconds)` | `tuple[boolean,string]` for manager completion |

Policies:

- `permanent`: restart after any child exit, including normal and explicit child stop.
- `transient`: restart after abnormal exits only.
- `temporary`: never restart; retain the last dead PID for inspection.

Strategies:

- `one_for_one`: replace the failing child only.
- `one_for_all`: stop all children and restart eligible non-temporary children.
- `rest_for_one`: stop the failed child and all later declarations, then restart eligible non-temporary children.

Affected children and their owned subtrees are fully joined before replacements start. Temporary children stopped as part of a group strategy are not restarted. A supervisor can stay alive after all temporary/transient children finish normally. Fetch `Supervisor.child` again to obtain replacement PIDs; handles returned earlier remain tied to the previous process. A returned PID may already have exited if its callback fails immediately, so monitor or join it normally.

Restart intensity counts restart cycles, not individual child starts, over a rolling window of 1–86,400,000 ms. A zero limit allows no restart. When another restart would exceed the limit, the manager exits `restart_intensity`, stops all children and joins the tree. Simultaneous detected exits are processed in declaration order. Stopping a supervisor suppresses restarts and reports `shutdown` after cleanup.

Supervisors are owned scopes: when their creating process ends, their entire trees stop. A worker may create a linked supervisor to form a nested supervision tree; exhaustion then propagates through its creator, allowing an outer supervisor to replace that subtree. Ordinary unlinked spawned processes are not automatically children of their spawning actor; they remain registered with the root runtime and can be linked explicitly.

## Shutdown, diagnostics and physical limits

The root runtime cancels and joins every registered process when `main` finishes or fails. The default total shutdown budget is two seconds, configurable at build time. A deadline failure reports an error and exits nonzero. Stopped workers wake from send/receive/sleep/join/event waits; pure generated computation checks cancellation at statement/function boundaries. Nested supervisors join descendants before the owning process signals completion. Runtime tests exercise this under the race detector and repeated lifecycle runs.

Call depth is counted per process and reset for every spawned or restarted process; exceeding the build's limit is an ordinary failure with reason `call depth exceeded`. Cancellation is observed on entry to every function and closure, before each statement of `main`, and inside every blocking or repeating runtime operation (`receive`, `send`, `await`, `sleep`, `event`, `loop`, supervisor waits). A stopped process therefore runs at most the remaining straight-line statements of its current function before it exits. A function's call to itself in return position is a jump that checks for cancellation and adds no depth. Functions that call no other function have no entry check and no call-depth accounting: they cannot recurse, block or repeat, so they finish within their own statements. Collection operations such as `map` over a large list run to completion once started unless the callback itself reaches a cancellation point. `Supervisor.child` takes no lock and returns either the previous PID or a fully started replacement, so polling it does not delay a restart. A failure captures its call stack cheaply and resolves source frames only when they are printed or requested through `Process.report`. Runtime frames report the Alchem line of the statement being executed; generated wrappers never appear as frames. If the shutdown deadline passes, the root reports `<runtime>: shutdown deadline exceeded`, exits 2 and does not wait further for supervisors it owns.

Source failures are recovered at process boundaries, not converted to executable-wide `os.Exit` inside a worker. The root prints its source failure and Alchem frames (including imported and anonymous functions) and exits 2; worker failures are available through monitors, joins and `Process.report`. `--trace=false` suppresses automatic root frames, while explicit reports retain failure information.

A process blocked in `IO.read_line` or `IO.read_all` is waiting on the operating system and does not observe cancellation until the read returns; at shutdown such a process can run into the shutdown deadline. Goroutines still share an address space. This runtime does not provide BEAM-equivalent isolation, distributed PIDs, forced interruption of an operating-system write, recovery from fatal Go stack/memory failures, or hard real-time deadlines. Cancellation is cooperative at the implemented boundaries. These are explicit operating limits; no failure-injection test can turn fatal Go runtime failures into recoverable actor exceptions.

## Nodes

A program becomes a node with `Node.start(name, address, cookie)` and connects to another with `Node.connect(address)`. The connection is a TCP stream of length-prefixed messages inside TLS 1.3, so what crosses cannot be read or altered on the way: not the messages, not the names processes are looked up by, not the nodes' own names.

Nodes hold no certificates that an authority has signed; each makes its own key when it starts, and nothing checks it. What admits a node is the cookie, a secret every node of a cluster shares. Each end proves it knows the cookie with a keyed hash over a value that both derive from the TLS session they have just set up, together with its role and its name; the cookie itself is never sent. Because the proof is tied to the session, someone placed between two nodes, who would hold a separate session with each, cannot pass one node's proof to the other, and the nodes refuse to connect. A node that gets a wrong proof closes the connection without answering.

The cookie is the whole of the protection. Someone who can place themselves between two nodes obtains a proof they can test guesses against at leisure, so a cookie must be long and random, not a word. Keep it out of source control: `Node.start(name, address)` reads it from the `ALCHEM_COOKIE` environment variable.

Encryption can be turned off with `Node.start(name, address, cookie, [encrypted: false])`, for nodes on a network you trust, such as one machine or a private cluster, where the handshake and the encryption are cost without benefit. The setting is fixed when the node starts and is not negotiated: before anything else, each end sends one unencrypted byte saying whether it encrypts, and two nodes connect only if the settings match, so a node that encrypts never falls back to plain text. A mismatch is reported on both sides. Without encryption, messages, names and the nodes' own names can be read and changed by anyone on the network. The cookie is still checked and never sent: each end contributes a random value and both proofs cover the two, so a recorded proof cannot be replayed, but someone between two nodes can relay the proofs, and anyone who sees them can test guesses of the cookie against them. Turning encryption off does not make the program smaller.

The node code, with its networking and encryption, is linked only into programs that use nodes. Such a program is about 4.8 MB larger than one that does not.

A process is reached from another node by name: `Process.register(pid, :name)` on its node, and `Node.whereis(node, :name)` on the other, which returns a handle of the annotated type if the name is registered there for that same type. `Process.send` to such a handle encodes the message, writes it to the connection and returns; it reports false once the connection has closed. The receiving node builds the value again and puts it in the mailbox, waiting up to five seconds for room before dropping it. Values are immutable, so a copy cannot be told from the original.

The functions that encode and decode a message type are generated by the compiler from the type. Integers, floats, booleans, strings, atoms, lists, tuples, maps, sets, structs, sum types, `option`, `result` and the date and time types cross. A process handle crosses as the name of its node and its number, and the node that sends it makes the process reachable; a handle that returns to its own node is the local process again. Functions, streams, regular expressions, ports, tasks, agents and servers do not cross, which the compiler reports where a process is registered or looked up.

A handle to a process of another node supports `Process.send`, `Process.id`, `Process.alive`, which reports whether its node is connected, and `Process.monitor` with `Process.demonitor`. A monitor asks the other node to report the process's exit, which arrives as an event with the reference, the process's number and its exit reason, exactly as for a local process; a process that has already ended is reported at once, one the other node does not know as `noproc`, and one whose node is lost first as `noconnection`. `Process.receive`, `link` and `await` need a process of this node. `Node.monitor(node)` asks for one event, read with `Process.event`, when the connection to a node ends; its reason is `nodedown` and the node's name.

A stream does not cross in a message, because it is code rather than data. Instead `Stream.publish(:name, fn -> stream end)` offers one to other nodes, and `Node.stream(node, :name)` returns a stream that pulls from it. The publishing node builds the stream once for each reader, in a process of its own, and advances it only when a reader asks for the next chunk of up to 256 elements or 64 KiB. So an endless stream, or one larger than memory, can be read from another node, and a reader that stops early causes no further work. Reading fails if the other node stops answering.

Not provided: starting a process on another node, links between nodes, names known to every node, certificates signed by an authority, and automatic reconnection.

