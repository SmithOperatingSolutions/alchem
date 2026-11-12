# Standard library

Every function here is a builtin: no import is needed and the module names are reserved. Collection operations (`map`, `filter`, `reduce`, `List.*`, `Map.*`) are described in the [language specification](language-spec.md) and process operations in [runtime](runtime.md).

Functions here report an expected failure with `result` or an absent value with `option`; match the value with `case`. The one exception is `Server.await`, which returns a flag in a tuple like the process operations it mirrors.

## String

| Function | Result |
| --- | --- |
| `String.length(text)` | `integer`: number of Unicode code points |
| `String.slice(text, start, count)` | `string` of up to `count` code points from zero-based `start`; shorter or empty when the string ends first; negative arguments fail with `slice bounds must be nonnegative` |
| `String.contains(text, part)`, `String.starts_with(text, prefix)`, `String.ends_with(text, suffix)` | `boolean` |
| `String.split(text, separator)` | `list[string]`, including empty pieces; an empty separator fails with `separator must not be empty` |
| `String.join(parts, separator)` | `string` |
| `String.trim(text)` | `string` without leading and trailing whitespace |
| `String.upcase(text)`, `String.downcase(text)` | `string`, by simple per-character Unicode case mapping |
| `String.reverse(text)` | `string` reversed by code point |
| `String.replace(text, old, new)` | `string` with every occurrence replaced |

## Integer and Float

| Function | Result |
| --- | --- |
| `Integer.to_string(n)` | `string` |
| `Integer.parse(text)` | `result[integer,string]`: `ok(value)` for an optionally signed decimal that fits 64 bits, otherwise `error(reason)` with a reason such as `"12a" is not an integer` |
| `Float.to_string(x)` | `string` with a fractional part, such as `1.0`; exponent form above 1e16 and below 1e-5 |
| `Float.parse(text)` | `result[float,string]` |
| `Float.from_integer(n)` | `float` |
| `Float.round(x)`, `Float.floor(x)`, `Float.ceil(x)` | `float`; each also takes a number of decimal places |
| `round(x)`, `trunc(x)`, `ceil(x)`, `floor(x)` | `integer`; round is half away from zero; values outside the integer range fail |

Other numeric functions are one line of [Go interop](interop.md) away: `extern sqrt(x: float): float = "math.Sqrt"`.

## File, System, Time and IO

| Function | Result |
| --- | --- |
| `File.read(path)` | `result[string,string]`: `ok(contents)`, or `error(reason)` when the file is missing, unreadable or a directory (the operating system's message), larger than 16 MiB (`file exceeds 16777216 bytes`) or not UTF-8 (`file is not valid UTF-8`) |
| `File.write(path, content)`, `File.append(path, content)` | `result[tuple[],string]`; files are created with mode 0644 and written in place |
| `File.remove(path)` | `result[tuple[],string]` |
| `File.list(directory)` | `result[list[string],string]`: entry names, sorted |
| `File.exists(path)` | `boolean` |
| `System.argv()` | `list[string]`: command-line arguments after the program name |
| `System.env(name)` | `option[string]` |
| `Time.now()` | `integer`: milliseconds since the Unix epoch |
| `Time.monotonic()` | `integer`: microseconds since the program started, never decreasing |
| `IO.puts(text)` | statement; writes the text and a newline to standard output |
| `IO.write(text)` | statement; writes the text without a newline |
| `IO.read_line()` | `option[string]`: `some(line)` without its line ending, or `none` at end of input |
| `IO.read_all()` | `string`: the rest of standard input |

Paths are relative to the working directory of the running program. Unless a table gives the text, the reasons in `result` errors are the operating system's messages and differ between platforms. Input limits and UTF-8 handling for `File.read`, `IO.read_line` and `IO.read_all` are specified under Program input in the [language specification](language-spec.md). File and input operations block the calling process and are not interrupted by cancellation.

`String.reverse`, `String.starts_with`, `String.ends_with`, `String.replace`, the `Float` functions, `File.write`, `File.append`, `File.remove`, `File.list`, `File.exists` and `System.env` can be referenced as function values, for example `map(words, &String.reverse)`. The other functions must be called directly; wrap one in an anonymous function to pass it.

## Enum and Stream

Every function is listed with its signatures, a description and examples in the generated [library reference](library-reference.md), which `alchem doc` prints from the command line, and [Elixir parity](elixir-parity.md) records what is missing and how the typed forms differ from Elixir's.

`Enum` functions accept any enumerable (a list, a map, a set, a range or a stream) and return finished values. A map enumerates as its `{key, value}` entries in ascending key order, and a set in ascending order. They follow Elixir's argument order, including callbacks: `Enum.reduce(items, 0, fn item, acc -> acc + item end)`.

```elixir
orders
|> Enum.filter(& &1.paid)
|> Enum.group_by(& &1.customer, & &1.total)
|> Enum.map(fn {customer, totals} -> "#{customer}: #{Enum.sum(totals)}" end)
```

`Stream` functions take the same enumerables and return a `stream`, which does no work until it is consumed. Because each element flows through the whole pipeline before the next is read, a pipeline over a large or infinite source uses memory for one element (or one chunk) at a time.

```elixir
File.stream!("access.log")
|> Stream.map(&String.trim(&1))
|> Stream.filter(&String.contains?(&1, " 500 "))
|> Stream.chunk_every(1000)
|> Enum.each(fn batch -> store(batch) end)
```

- **Chunking.** `chunk_every(enumerable, count)` yields lists of `count` elements with a shorter last chunk; `chunk_every(enumerable, count, step)` starts a chunk every `step` elements, so chunks overlap when `step < count` and skip elements when it is larger. `chunk_by(enumerable, fun)` starts a new chunk whenever the function's result changes.
- **Lazy input.** `File.stream!(path)` yields lines, each with its line ending, and `File.stream!(path, bytes)` yields chunks of that many bytes, which may end inside a multi-byte character. The file is opened when consumption starts and closed when it ends, including when the consumer stops early or a failure cuts it short. A file that cannot be opened fails at that point, not when the stream is built. `IO.stream()` yields the lines of standard input.
- **Sources.** `Stream.iterate`, `repeatedly`, `cycle`, `unfold`, `from_index`, `interval`, `timer` and `resource` produce streams; the first five can be infinite, and a process consuming one can still be stopped.
- **Steering callbacks.** `Enum.reduce_while` callbacks return `cont(acc)` or `halt(acc)`. `Stream.unfold`, `Stream.transform` and `Stream.resource` callbacks return `none` to stop, or `some({value, next})` / `some({items, next})` to continue.
- **Negative counts.** `take` and `drop` with a negative count work from the end, which needs the whole source and so never finishes on an infinite stream.
- **Ordering and equality.** `sort`, `min`, `max` and their `_by` forms need integers, floats, strings, booleans, or tuples and lists of them. `uniq`, `dedup`, `member?`, `frequencies` and `group_by` need equality or key types as the reference notes. `Enum.sort/2` and `sort_by/3` take a function saying whether its first argument may come before its second.
- **Empty input.** `Enum.min`, `max`, `reduce/2`, `random` and `fetch!` fail on an empty enumerable, as Elixir raises.
- **Random functions.** `Enum.random`, `shuffle` and `take_random` use a source seeded from the `ALCHEM_SEED` environment variable when it is set, which `alchem test --seed` does, so runs can be repeated.

## Other modules

- **Kernel functions** are called without a module: `abs`, `min`, `max`, `div`, `rem`, `round`, `trunc`, `ceil`, `floor`, `hd`, `tl`, `to_string`, `inspect`, `then`, `tap`, `map_size`, `byte_size`. A function of the same name defined in a program takes precedence.
- **`inspect(value)`** renders any value as source would write it, `%Point{x: 1, y: 2}` or `[some(1), none]`; `IO.inspect(value)` prints that and returns the value.
- **`MapSet`** provides sets of integers, strings or booleans.
- **`Regex`** uses RE2 syntax: there are no backreferences or lookaround, and matching takes time linear in the input. Replacement text may use `\\1` for a capture group.
- **`Task`** runs a function in its own process: `Task.async(fn -> work() end)` then `Task.await(task)`. Awaiting a task that failed, or that takes longer than the deadline (5 seconds by default), fails the caller; `Task.yield` reports the same outcomes as `option[result[T,string]]` instead. `Task.async_stream(enumerable, fun)` runs up to one task per processor at a time and yields results in input order. `Task.async` links the task to its caller: a task that fails takes the caller with it, unless the caller traps exits. `Task.start` starts a task that is not linked, and `Task.start_link` one that is. `Task.Supervisor.start_link()` starts a supervisor for tasks: `Task.Supervisor.async` runs a linked task under it and `async_nolink` one whose failure is seen only through `Task.yield` or `Task.await`.
- **`Agent`** holds a state in a process: `Agent.start_link(fn -> initial end)`, then `get`, `update`, `get_and_update` and `cast` with functions that run inside the agent, one at a time. `get`, `update` and `get_and_update` take a timeout in milliseconds as a last argument. `Agent.start_link(fn -> 0 end, [name: :counter])` registers the agent, and each of these functions also takes the name: `Agent.get(:counter, fn(n: integer): integer do n end)`.
- **`JSON`** converts between text and the builtin `JSON` type, whose constructors are `JSON.null`, `JSON.boolean(b)`, `JSON.integer(n)`, `JSON.float(x)`, `JSON.string(s)`, `JSON.list(items)` and `JSON.object(fields)`. Objects are written with their keys in order.
- **`System.cmd(program, arguments)`** runs a program and returns `{output, exit_status}`; **`System.halt(status)`** ends the program at once.
- **`Float.round(x)`** returns a float, as in Elixir; `round(x)` and `trunc(x)` return integers.

## Dates and times

`Date`, `Time`, `NaiveDateTime` and `DateTime` are builtin structs, so their fields can be read and matched: `date.year`, `%Date{month: 12}`. They are written with the `~D`, `~T`, `~N` and `~U` sigils or built with `new`, which returns a `result` and rejects impossible values such as 29 February in a common year.

```elixir
due = Date.add(~D[2026-11-10], 30)
late = Date.after?(Date.utc_today(), due)
stamp = DateTime.to_iso8601(DateTime.utc_now())
```

- **Fields.** `Date` has `year`, `month`, `day`; `Time` has `hour`, `minute`, `second`, `microsecond`; `NaiveDateTime` has all seven; `DateTime` adds `time_zone` and `utc_offset`.
- **Time zones.** A `DateTime` is always in UTC. `DateTime.from_iso8601` accepts text with any offset, converts it to UTC and returns the offset in seconds beside it: `ok({datetime, 7200})`.
- **Arithmetic.** `Date.add` and `Date.diff` count days; the others count seconds. `Time.add` wraps around midnight.
- **Comparing.** `compare` returns -1, 0 or 1 where Elixir returns `:lt`, `:eq` or `:gt`; `before?` and `after?` return booleans. To sort, pass a comparison: `Enum.sort(dates, &(Date.compare(&1, &2) <= 0))`.
- **Text.** `to_iso8601` and `from_iso8601` use ISO 8601; `to_string` writes a space between date and time. Fractions of a second are written only when present.
- **Microseconds** are a plain integer, not Elixir's value-and-precision pair.
- `Time.now()` and `Time.monotonic()` are the earlier clock functions, in milliseconds and microseconds; `Time.utc_now()` is the time of day.

`Calendar.strftime(value, format)` formats any of the four types with `%`-directives (`alchem doc Calendar.strftime` lists them).

A `Duration` is an amount per unit, built with `Duration.months(1)`, `Duration.days(10)` and their siblings and combined with `Duration.add`. `shift(value, duration)` on each of the four types moves it: years and months on the calendar, keeping the day or the last day the new month has.

A `DateTime` may be in any zone of the zone database, which is built into programs that use it, so they behave the same on a system without one. `DateTime.shift_zone(value, "Europe/Paris")` gives the same moment on that zone's wall clock, with `time_zone` and `utc_offset` set; `DateTime.now(zone)` and `DateTime.from_naive(naive, zone)` build one. Comparison, difference, `add` and Unix time work on the moment. Not available: `Duration` arithmetic between two values (`diff` returns seconds or days) and non-Gregorian calendars.

`URI.parse` splits an address into a `URI` struct and `URI.to_string` writes one back. `Version.match?(version, requirement)` tests a requirement such as `"~> 2.1"` or `">= 1.0.0 and < 2.0.0"`. `Logger.debug`, `info`, `warning` and `error` write leveled lines to standard error, filtered by `Logger.configure(level)` or the `ALCHEM_LOG_LEVEL` variable. `OptionParser.parse(arguments, switches)` reads typed command-line switches into a map.

## Server

A server is a process that owns a state and answers typed requests one at a time, in arrival order. It is the request/reply pattern over the process runtime.

```elixir
type Request do
  add(amount: integer)
  read
end

def handle(total: integer, request: Request): tuple[integer, integer] do
  case request do
    Request.add(amount) -> {total + amount, total + amount}
    Request.read -> {total, total}
  end
end

def main() do
  counter = Server.start(0, &handle)
  assert(Server.call(counter, Request.add(5), 1000) == ok(5))
end
```

| Function | Result and behaviour |
| --- | --- |
| `Server.start(state, handler)` | `server[Request,Reply]`; the handler is `fn[State,Request,tuple[State,Reply]]` and returns the next state and the reply |
| `Server.start_supervised(state, handler, max_restarts, window_ms)` | `server[Request,Reply]` that is restarted after a handler failure |
| `Server.restarts(server)` | `integer`: how many times a supervised server has been restarted; 0 otherwise |
| `Server.call(server, request, milliseconds)` | `result[Reply,string]`; `error("timeout")`, `error("server is not running")`, or `error("server stopped: reason")` when the server ends before answering |
| `Server.cast(server, request)` | `boolean`; queues the request without waiting; false when the server has stopped or its queue is full |
| `Server.stop(server)` | `boolean`; requests shutdown |
| `Server.alive(server)` | `boolean` |
| `Server.await(server, milliseconds)` | `tuple[boolean,string]`: whether it terminated, and the exit reason |

Requests and replies must be sendable (no functions). A call that times out is not withdrawn: the server still handles the request and discards the reply. A handler failure stops the server; the caller whose request failed, and later callers, receive an error instead of failing themselves. Timeouts follow the runtime convention: negative waits indefinitely, zero polls. A server queues at most 1024 requests, and callers wait for space within their deadline. A server cannot call itself.

A supervised server runs as the only child of its own one-for-one supervisor. When its handler fails, the caller of that request receives `error("server stopped: reason")`, and the server is started again **with its initial state**; requests queued for the failed instance are lost. Calls made during the restart wait for the replacement within their deadline. After more than `max_restarts` failures within `window_ms` the supervisor gives up and the server stays down: calls return `error("server is not running")` and `Server.alive` is false. `Server.stop` and `Server.await` act on the supervisor. A supervised server started by a supervised worker is part of that worker's tree and stops with it; a server is not a named child of a user `Supervisor`, whose children all share one mailbox type.

Servers are started by the process that calls `Server.start` or `Server.start_supervised` and are stopped with the runtime at exit.

### Timers, names and exits

A handler sees only its server's request type, so what Elixir delivers to `handle_info` arrives here as a request, and there is a request for continued work too:

- `Server.self()` is the running server, annotated with its types: `me: server[Request, integer] = Server.self()`.
- `Server.send_after(server, request, ms)` casts a request later; a handler schedules periodic work for itself with `Server.send_after(Server.self(), Request.tick, 1000)`. `Process.send_after(pid, message, ms)` does the same for a process mailbox, and `Process.cancel_timer(reference)` cancels either.
- `Server.monitor(server, pid, fn reason -> Request.down(reason) end)` queues a request when the process ends. The function runs inside the server.
- `Server.register(server, :name)` names a server and `Server.whereis(:name)` finds it, as `option[server[Request, Reply]]`; names are shared with `Process.register`, and a supervised server keeps its name across restarts.
- `Server.mailbox(server, fn message -> Request.event(message) end)` gives the server a `pid[Message]` that any process, port or socket can send to; each message becomes a request, made inside the server, as `handle_info` receives it in Elixir. The mailbox ends with the server and outlives a supervised server's restarts.
- `Server.continue(request)`, called in a handler, handles a request of the server's own as soon as the current one is answered and before any request already waiting, as `handle_continue` does. Replies to continued requests go nowhere.
- `Process.send_after(:name, message, ms)` sends to whatever is registered under the name when the time comes: a process whose messages are of the message's type, or a server whose requests are, as a cast. When nothing fitting holds the name, the message is dropped.

## Registry and DynamicSupervisor

`Registry.start_link([keys: :unique])` or `[keys: :duplicate]` returns a `registry[Key, Value]`; `Registry.start_link([keys: :duplicate], [partitions: 8])` spreads the keys over partitions with a lock each. A process registers itself under a key with a value; `Registry.lookup` lists the values of living processes, `Registry.entries` the `{process id, value}` pairs, and an entry goes away when its process ends. Put a pid or server in the value to reach the process. `match`, `count_match` and `unregister_match` take a test of the value, `select` a test of key, process id and value, `dispatch` hands a key's entries to a function, `update_value` changes the caller's own value, and `put_meta` and `meta` keep values for the registry as a whole.

`DynamicSupervisor.start_link()` starts a supervisor with no children, which gives up after more than 3 restarts in 5 seconds unless `[max_restarts: n, max_seconds: s]` says otherwise; `max_children: n` limits how many children it runs at once, and `start_child` then returns `error("max_children")`. `start_child(supervisor, worker)` starts a process of any message type and returns its pid; the child is restarted whenever it ends (`:permanent`, the default), when it fails (`:transient`), or never (`:temporary`). `start_server(supervisor, state, handler)` starts a server that restarts itself and stops with the supervisor. `terminate_child`, `which_children`, `count_children`, `restarts`, `stop` and `alive` manage it.
## TCP and HTTP

`TCP` opens connections in passive mode: a process calls `TCP.recv`, `TCP.recv_line` or `TCP.accept` with a wait in milliseconds and gets `error("timeout")` or `error("closed")` when nothing comes. A process waiting without a deadline still stops when it is asked to. A socket belongs to the process that opened it and is closed when that process ends; `TCP.controlling_process(socket, pid)` hands it to another.

`TCP.setopts(socket, [active: :once])` makes a socket active: what arrives is sent to its controlling process, whose messages must be `TCP.Event`, as `TCP.Event.data(text)`, followed by `TCP.Event.closed` or `TCP.Event.error(reason)` at the end. `active: true` sends everything, a number sends that many packets, and `active: false` goes back to passive reads. `packet: :line` cuts the stream into lines and `packet: 4` (or 1 or 2) into packets with a length header, which `TCP.send` adds; `TCP.listen(address, options)` gives the options to every socket it accepts. `UDP.open(address)` opens a datagram socket, read with `UDP.recv` or, made active, as `UDP.Event.datagram(from, text)` messages.

```elixir
ok(listener) = TCP.listen("127.0.0.1:4040")
ok(client) = TCP.accept(listener, -1)
ok(line) = TCP.recv_line(client, 5000)
TCP.send(client, String.upcase(line) <> "\n")
```

`HTTP.serve(address, handler, [idle_timeout: 5000, max_body_bytes: 1000000])` tunes timeouts, keep-alive and sizes; `HTTP.serve_tls(address, handler, [certfile: path, keyfile: path])` serves HTTPS. `HTTP.route(request, routes)` dispatches on `{method, "/users/:id", handler}` routes, answering 404 and 405 itself. `HTTP.chunked(status, headers, stream)` sends a body as it is made, and `HTTP.stream` receives one as a stream of chunks.

`HTTP.serve(address, handler)` answers each request by running the handler, `fn[HTTP.Request, HTTP.Response]`, in a process of its own, so a slow or failing request holds up no other; a handler that fails answers 500. `HTTP.Request` has `method`, `path`, `query`, `headers` (lower-case names) and `body`; `HTTP.Response` has `status`, `headers` and `body`, and `HTTP.text` and `HTTP.json` build common ones. The client functions, `HTTP.get`, `HTTP.post` and `HTTP.request`, return `ok(response)` for a response with any status and `error(reason)` when there was none.

```elixir
def handle(request: HTTP.Request): HTTP.Response do
  case request.path do
    "/health" -> HTTP.text(200, "ok")
    _ -> HTTP.text(404, "not found")
  end
end

def main() do
  ok(server) = HTTP.serve("0.0.0.0:8080", &handle)
  HTTP.await(server, -1)
end
```

## Atoms, keyword lists and ports

`Atom.to_string` and `String.to_atom` convert between an atom and its name. The `Keyword` module works on keyword lists, `[name: value]`: `get`, `fetch`, `put`, `delete`, `merge`, `keys`, `values`, `update`, `pop`, `take`, `drop`, `get_values` and `to_map`.

`Port.open(program, arguments, owner)` runs an external program. Each line it writes arrives in the owner's mailbox as `PortEvent.data(text)`, followed by `PortEvent.exit(status)` when it ends; `Port.command(port, text)` writes to its standard input and `Port.close(port)` closes it. Stopping the owner ends the program.
