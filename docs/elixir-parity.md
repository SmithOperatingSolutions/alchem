# Elixir standard library parity

What Alchem has of Elixir's standard library, what differs because Alchem is statically typed and its macros are templates, and what is still to do. Exact signatures are in the generated [library reference](library-reference.md); behaviour is in [standard library](stdlib.md).

Status: **done** (implemented and covered by a fixture), **partial**, **todo**, or **n/a** (cannot exist in this language as designed).

## Conventions that replace dynamic Elixir

| Elixir | Alchem |
| --- | --- |
| `nil` for "absent" (`Enum.at`, `Enum.find`, `List.first`, `Map.get/2`) | `option[T]`: `some(value)` or `none` |
| `{:ok, value}` / `{:error, reason}` | `result[T,string]` |
| `{:ok, value}` / `:error` (`Map.fetch`, `Base.decode64`) | `option[T]` |
| raising functions and `!` variants | fail the calling process with a message |
| `{:cont, acc}` / `{:halt, acc}` (`Enum.reduce_while`) | `cont(acc)` / `halt(acc)`, of type `step[T]` |
| `{:halt, acc}` vs `{[items], acc}` (`Stream.transform`, `Stream.resource`, `Stream.unfold`) | `none` to stop, `some({items, acc})` to continue |
| truthiness | booleans only; `find_value` takes a function returning `option` |
| any term is comparable and orderable | equality and ordering are checked per type; functions are neither |
| options as keyword lists and atoms (`Enum.sort(list, :desc)`) | pass a function (`Enum.sort(list, &(&1 >= &2))`) |
| protocols (`Enumerable`, `String.Chars`, `Inspect`) | built in: lists, maps, sets, ranges and streams are enumerable; `inspect` works on every type |

## Language forms

| Form | Status | Notes |
| --- | --- | --- |
| `fn x, y -> ... end` | done | parameter and result types are inferred from where the function is passed; parameters may be patterns |
| `&(&1 + 1)`, `& &1.name`, `&String.length(&1)` | done | |
| `&Module.function/arity`, overloads by arity | done | `&area/2` names one arity; `&area` works when there is only one. Functions of one name and different arities are different functions |
| `first..last`, `first..last//step` | done | a range is a lazy `stream[integer]` |
| `x in enumerable` | done | |
| `[head \| tail]` to build a list | done | `[a, b \| rest]` puts elements in front of a list |
| `++`, `--`, `<>`, `**` | done | |
| `&&`, `\|\|`, `!` | done | spellings of `and`, `or`, `not`; operands must be booleans |
| `cond do ... end` | done | usable as a statement or a value |
| `raise`, `defexception`, `throw` | done | `raise("message")`, `raise(%Exception{...})` for an exception declared with `defexception` (a struct with a `message: string` field), and `throw(value)` | `raise Module, keyword` forms, `reraise` with a stack, `exit/1`; runtime failures are messages, not `ArithmeticError` and the like |
| names ending in `?` and `!` | done | |
| `with` | done | without `else`, a non-matching `error` or `none` becomes the result |
| `for` comprehensions | done | generators, filters, pattern skipping, and one of `into:`, `uniq:` or `reduce:`; an empty `reduce:` value needs a type annotation |
| `try`/`rescue`/`catch`/`else`/`after` | done | rescue arms match `e in Exception`, `%Exception{...}` or the message; catch arms take a thrown value of one type; else arms match the body's value | `rescue e ->` binds the message, not an exception; `catch kind, value` |
| sigils | done | `~r`, `~w`, `~s`, `~S`, `~c`, `~D`, `~T`, `~N`, `~U`, and any other letter through a `sigil_x(text, modifiers)` function; lower-case text sigils interpolate. `~c` is a list of code points, since there are no charlists |
| `=~` | done | |
| `#` comments | done | kept by the formatter |
| `unless` | done | statement or value, with an optional `else` |
| atoms | done | `:name`, of type `atom`; any atom fits that type, so use a sum type where the compiler should check the alternatives |
| keyword lists | done | `[name: value]` is a `list[tuple[atom, T]]`; values share one type; not accepted as trailing call arguments |
| heredocs | done | escapes and interpolation as in a string, `~S"""` for literal text, and sigil heredocs | |
| charlists, bitstring syntax | n/a | `~c` gives code points |
| protocols | done | `defprotocol` and `defimpl`, resolved when the program is compiled from the type of the first argument; no dispatch on a type variable, no `@derive`, no `Any` fallback |
| macros, `use` | partial | template macros: `defmacro` with `quote` and `unquote`, `do` blocks, hygiene, and `use` adding functions through `__using__`. A macro substitutes its arguments; it cannot inspect them, compute while compiling, or define types |
| behaviours | n/a | a protocol covers the common use |
| guards with `is_integer/1` and friends | n/a | types are static |
| multi-clause anonymous functions | done | clauses on the lines after `fn`; one argument, so match a tuple for several |
| default arguments (`\\`) | done | trailing parameters; the value is a constant, filled in at each call |
| module attributes as constants (`@name value`) | done | built from literals, operators and earlier constants; visible in the whole module, defined once; not readable from other modules |
| HTML templates | done | `~h` interpolates with escaping into a `Markup` value, as a HEEx template escapes; no component syntax or compile-time HTML validation |

## Modules

| Module | Status | Have | Missing |
| --- | --- | --- | --- |
| Enum | done | 70 functions in 87 arities, on lists, maps, sets, ranges and streams, `into/3`, `slide`, `zip/1`, `zip_with/2`, `chunk_every/4`, `sort` and `sort_by` with `:asc`/`:desc`, `min`/`max`/`min_by`/`max_by` with a sorter, `with_index` with a function, `slice/2` with a range | |
| Stream | done | all lazy functions, including `chunk_every`, `chunk_by`, `resource`, `transform`, `unfold`, `iterate`, `cycle`, `interval`, `timer`, `zip/1`, `into` a file opened with `File.open` | |
| File (lazy) | done | `File.stream!(path)` by line and `File.stream!(path, bytes)` by chunk; `IO.stream()` for standard input | modes and encodings |
| Range | done | as syntax, `Range` structs with `first`, `last` and `step`, `Range.new`, `size`, `disjoint?`, `shift`, `split`, `to_list`, and slicing with `Enum.slice` and `String.slice` | |
| List | partial | `first`, `last`, `flatten/1`, `foldl`, `foldr`, `delete`, `delete_at`, `duplicate`, `insert_at`, `replace_at`, `update_at`, `pop_at`, `starts_with?`, `ends_with?`, plus the earlier `reverse`, `take`, `drop`, `contains`, `sort`, `range`, `zip`, `myers_difference`, `zip/1` | keyword-list functions (`keyfind` and so on) are n/a |
| Map | done | `get`, `get_lazy`, `fetch`, `fetch!`, `has_key?`, `put`, `put_new`, `put_new_lazy`, `drop`, `take`, `new`, `from_keys`, `to_list`, `filter`, `reject`, `split`, `split_with`, `update`, `update!`, `replace`, `replace!`, `pop`, `merge/2,3`, `intersect`, `equal?`, `keys`, `values`, `delete`, `get_and_update`, `pop_lazy`, `replace_lazy` | `from_struct` is n/a: a map has one value type |
| MapSet | done | every function; the type is `set[T]`, elements and map keys of any type of integers, floats, strings, booleans, atoms and tuples of them | lists and structs as keys |
| Keyword | partial | `get/2,3`, `fetch`, `fetch!`, `get_values`, `has_key?`, `put`, `put_new`, `delete`, `keys`, `values`, `merge/2`, `take`, `drop`, `update/4`, `pop/2`, `to_map`, `validate`, `split`, `merge/3`, `get_lazy`, `pop_lazy`, `put_new_lazy` | |
| Tuple | n/a | | tuples are fixed-shape; use `tuple[0]` and patterns |
| String | partial | `length`, `slice/3`, `at`, `first`, `last`, `capitalize`, `upcase`, `downcase`, `reverse`, `codepoints`, `graphemes`, `contains?`, `starts_with?` and `ends_with?` with a pattern or a list of them, `duplicate`, `pad_leading`, `pad_trailing`, `split/1,2`, `split_at`, `join`, `trim` and its leading/trailing forms, `replace` and its prefix/suffix/leading/trailing forms, `to_integer/1,2`, `to_float`, `valid?`, `printable?`, `count`, `next_codepoint`, `match?`, grapheme clusters for `length`, `slice`, `at`, `reverse` and `graphemes`, `next_grapheme`, `normalize`, `jaro_distance`, `myers_difference`, `splitter`, case modes `:ascii`, `:greek` and `:turkic`, and regular expressions in `replace` and `split`, `slice/2` with a range | |
| Integer | done | `to_string/1,2`, `parse/1,2`, `digits`, `undigits`, `pow`, `gcd`, `extended_gcd`, `mod`, `floor_div`, `ceil_div`, `is_even`, `is_odd` | |
| Float | partial | `round/1,2`, `floor/1,2`, `ceil/1,2`, `pow`, `parse`, `to_string`, `from_integer`, `ratio`, `min_finite`, `max_finite` | `:math` functions come through `extern` |
| Kernel | partial | `abs`, `min`, `max`, `div`, `rem`, `round`, `trunc`, `ceil`, `floor`, `hd`, `tl`, `length`, `map_size`, `byte_size`, `to_string`, `inspect`, `then`, `tap`, `raise`, `elem` and `put_elem` with a literal index, `binary_part` | `send`/`spawn`/`self` are `Process.*`; `apply` and `function_exported?` are n/a without dynamic calls |
| Function | partial | `identity` | `capture`, `info` are n/a |
| Bitwise | done | `band`, `bor`, `bxor`, `bnot`, `bsl`, `bsr`, the operators `&&&`, `|||`, `^^^`, `<<<`, `>>>` and `~~~` | |
| Base | done | 16, 32 and 64, URL-safe 64, with `decode` and `decode!`, `hex_encode32`/`hex_decode32`, `case:` and `padding:` options | |
| Path | partial | `join/1,2`, `basename/1,2`, `dirname`, `extname`, `rootname/1,2`, `expand`, `absname`, `split`, `relative_to`, `wildcard`, `type`, `safe_relative` | |
| File | partial | `read`, `read!`, `write`, `write!`, `append`, `exists?`, `dir?`, `regular?`, `rm`, `rm!`, `rm_rf`, `rmdir`, `ls`, `ls!`, `mkdir`, `mkdir_p`, `cp`, `rename`, `touch`, `cwd`, `cwd!`, `stream!`, `open` with modes and file handles, `close`, `stat`, `lstat`, `cp_r`, `ln`, `ln_s`, `chmod`, `write/3` with `:append` and `:exclusive` | |
| IO | partial | `puts` (also to `:stdio` or `:stderr`), `write`, `inspect`, `warn`, `gets`, `read_line`, `read_all`, `stream`, `read` and `binread` from standard input or a file, `write` and `puts` to a file, and `IO.ANSI` | |
| System | partial | `argv`, `get_env/1,2`, `put_env`, `cwd!`, `user_home`, `tmp_dir`, `find_executable`, `cmd/2`, `halt`, `pid`, `cmd/3` with `cd:`, `env:` and `stderr_to_stdout:`, `monotonic_time`, `system_time` and `os_time` with units, `convert_time_unit`, `stop` | |
| Regex | partial | `compile`, `compile!`, `match?`, `run`, `scan`, `replace`, `split`, `source`, `named_captures`, the `~r` sigil with `i`, `m`, `s`, `u`, `x` and `U` | syntax is RE2, so no backreferences or lookaround |
| Task | done | `async` (linked to the caller), `start`, `start_link`, `await/1,2`, `await_many/1,2`, `yield`, `shutdown`, `async_stream/2,3`, and `Task.Supervisor` with `start_link`, `async`, `async_nolink`, `start_child`, `children` and `terminate_child` | |
| Agent | done | `start_link` and `start`, with `name:`, `get`, `update` and `get_and_update` with an optional timeout, `cast`, `stop`, `whereis`; the functions that take an agent also take its name | |
| GenServer | done | the typed `Server` module: call, cast, supervised restart, `Server.self`, `Server.send_after` for timed work, `Server.monitor` turning another process's exit into a request, `Server.mailbox` for any other messages (`handle_info`), `Server.continue` (`handle_continue`), and names with `Server.register` and `Server.whereis` | |
| Supervisor, Process | done | the typed runtime, `Process.send_after` to a pid or a name and `cancel_timer`, `Process.register` and `whereis` | |
| DynamicSupervisor | done | `start_link` with `max_restarts:`, `max_seconds:` and `max_children:`, `start_child` with `:permanent`, `:transient` or `:temporary`, `start_server`, `terminate_child`, `which_children` (process ids), `count_children` (a number) | |
| Registry | done | `start_link` with `keys: :unique` or `:duplicate` and `partitions:`, `register`, `unregister`, `unregister_match`, `lookup` (values), `entries` (`{process id, value}`, what Elixir's `lookup` returns), `match`, `count_match`, `values`, `dispatch`, `select` (with a function for the match specification), `update_value`, `keys`, `count`, `put_meta` and `meta`; entries go away when their process ends | |
| JSON | done | `encode!`, `decode`, `decode!` over the builtin `JSON` type, `encode`/`encode!` of any value, structs included, and `pretty: true` | |
| ExUnit | done | `test`, nested `describe`, `setup`, `setup_all`, typed context, `@tag`, `@describetag` and `@moduletag` with names and values, `timeout:` and `skip:`, `--tag` and `--exclude` by name or `name:value`, property testing with `check all` and the `Gen` generators (StreamData's), with shrinking, doctests, `assert`, `refute`, `assert_raise`, `assert_in_delta`, `flunk`, `assert_receive`, `refute_receive`, `assert_received`, `refute_received` with patterns, `capture_io`, `on_exit`, `--seed`, `--only`, `--trace`, `--max-failures`, `--cover` | |
| Date, Time, NaiveDateTime, DateTime | partial | construction, ISO 8601 in and out, sigils, `add`, `diff`, `compare`, `before?`, `after?`, conversions, `shift`, time zones for `DateTime` (`shift_zone`, `now`, `from_naive`), and the `Date` calendar queries, `compare` returning `:lt`, `:eq` or `:gt`, `truncate`, `add` and `diff` with units, `Date.range`, week functions with `starting_on`, `week_of_year`; values print as `~D[...]` and its kin | |
| Calendar, Duration | done | `Calendar.strftime`; `Duration` built per unit (`Duration.months(1)`), `add`, `subtract`, `negate`, `multiply`, ISO 8601 in and out; `shift` on all four types, `Duration.new!` from keywords | non-Gregorian calendars |
| URI | done | `parse`, `new`, `to_string` over the `URI` struct; `encode`, `decode`, the `www_form` pair, `encode_query`, `decode_query`, `merge`, `append_path`, `append_query` | |
| Version | partial | `parse` to a tuple, `compare`, `match?` with `==`, `!=`, `>`, `>=`, `<`, `<=`, `~>`, `and`, `or`, the `Version` struct with `parse!` and `to_string`, `Version.Requirement` with `parse_requirement`, `match?` with `allow_pre:` | |
| OptionParser | partial | `parse/2,3` with typed switches (`boolean`, `string`, `integer`, `float`, `count`), `--no-` forms and one-letter aliases; values are returned as text, Elixir's `parse` and `parse_head` with `strict:`, `switches:` and `aliases:` and the types `:keep` and `:count`, `to_argv`, `split` | |
| Logger | partial | `debug`, `info`, `warning`, `error` to standard error; `configure(level)`, `level()`, `ALCHEM_LOG_LEVEL`, per-process `metadata`, `format:` and `metadata:` configuration, handlers with `add_handler` and `remove_handler`, lazy messages, `log` | |
| Port | partial | `open`, `command`, `close`, `os_pid`; output arrives a line at a time as `PortEvent.data`, then `PortEvent.exit`, `mode: :binary`, `packet:`, `stderr:`, `Port.info`, `Port.monitor` | |
| Node | partial | `start`, `connect`, `list`, `disconnect`, `monitor`, `self`, and `whereis` with `Process.register`; messages are copied between nodes, with encoders generated per type, over TLS 1.3 with a shared cookie, which `encrypted: false` turns off, `Node.serve`, `Node.call` and `Node.cast` (remote calls), `register_global`/`whereis_global`, `connect` with `reconnect: true`, and links to processes of other nodes | a function cannot be sent to run on another node; serve it there and call it |
| `:gen_tcp` and `:gen_udp` as `TCP` and `UDP` | done | `listen` and `connect` with options, `accept`, `send`, `recv`, `recv_line`, `setopts` with `active:` (`true`, `:once`, `false` or a count; data arrives as `TCP.Event` messages) and `packet:` (`:raw`, `:line`, or a 1, 2 or 4 byte length header), `shutdown`, `close`, `controlling_process`, `address`, `peer`; `UDP.open`, `send`, `recv`, `setopts` with `active:` (`UDP.Event` messages); a socket closes when its owning process ends | |
| HTTP, beyond the standard library | done | `HTTP.get`, `post`, `request` (with a timeout or options: `ca_file:`, `insecure:`, `stream:`) and `stream`, `HTTP.serve` running each request in its own process, with timeouts, keep-alive and size limits, `HTTP.serve_tls`, `HTTP.chunked` responses and `HTTP.read`, `HTTP.match` and `HTTP.route` for path patterns, over the `HTTP.Request` and `HTTP.Response` structs | |
| StringIO, Application, Config | n/a | | |
| Access, Atom, Code, Macro, Module, Protocol, Record, Exception | n/a | | |

## Next

The numbered list this section used to hold is done. What remains is in the "Missing" column above; the larger pieces are the `Version` and `Duration` conveniences.

The library runtime is not a separate cached Go package, and does not need to be: it is tree-shaken per program, and measured builds take 0.24 s with no library, 0.25 s with `Enum` and 0.33 s with five modules.

## What cannot be done

- **Macros that compute.** An Elixir macro is code that runs inside the compiler. Alchem compiles ahead of time through Go and has nothing to run such code in, so its macros are templates: they substitute their arguments into quoted code. That covers control-flow forms, wrappers and `use`; it does not cover a macro that inspects its arguments or generates code from data. Those would need macros compiled to helper programs that the compiler runs, which is not built.
- **Hex packages.** A Hex package is Elixir or Erlang source or bytecode for the BEAM. Alchem programs do not run on the BEAM and cannot load it. Alchem modules are imported from a repository with `import "host/owner/repo@version/file.alc"`, and Go packages are called through `extern`.

An earlier version of these notes also listed distribution here. It is built: see Node above.

## Deliberate differences

- `Float.to_string`, interpolation and `Float.round`, `floor` and `ceil` with a precision give Elixir's results, checked against Elixir on 6,000 generated values.
- A default argument is a constant filled in where the function is called, not a second function with fewer parameters.
- `URI.decode` and `URI.decode_www_form` return a `result` instead of raising.
- Between nodes a process is found by a registered name and a message type, and a send returns once the message is written. There is no transparent remote spawn.
- `DateTime.to_string` in a zone other than UTC writes the offset, the abbreviation and the zone name, as Elixir does; the zone database is Go's, built into the program.
- `DateTime.from_naive` in a gap or an overlap of a zone's clock picks one time instead of returning the ambiguity.
- `OptionParser.parse` returns every value as text, because a map has one value type.
- `Task.async_stream` yields the values themselves, not `{:ok, value}`: its tasks are linked to the caller, so a failure ends the caller and every value that arrives is a success.
- `DynamicSupervisor` has no `extra_arguments`: a child is a function, which captures what it needs.
- `TCP.Event` and `UDP.Event` messages carry the data but not the socket, which Elixir's `{:tcp, socket, data}` includes: give each socket its own receiving process, or a `Server.mailbox` whose conversion tags it. There is no `binary:` option, since text is always a binary.
- `Registry.lookup` returns the values; `Registry.entries` returns `{process id, value}` pairs as Elixir's `lookup` does, since a pid's type depends on its messages.
