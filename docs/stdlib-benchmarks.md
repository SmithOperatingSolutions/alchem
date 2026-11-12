# Standard library benchmarks

The standard library suite measures 193 operations across `Enum`, `Stream`, `Map`, `MapSet`, `List`, `String`, `Regex`, `Integer`, `Float`, `JSON`, the calendar types, `for`, `try`, `with`, processes, `Server`, `Agent` and `Task`. Every case exists three times: in Alchem, in Elixir as the baseline, and in hand-written Go as the ceiling. The whole-program workloads described in [benchmarks](benchmarks.md) are run by the same command.

```sh
go run ./benchmarks/harness                         # everything
go run ./benchmarks/harness -only enum,json         # some programs
go run ./benchmarks/harness -json out.json          # also write the figures as JSON
go run ./benchmarks/harness -compare benchmarks/baseline.json
```

## How it measures

- **Programs.** Each of the eleven programs is `benchmarks/alchem/suite/NAME.alc`, `benchmarks/elixir/suite/NAME.exs` and `benchmarks/go/suite/NAME/main.go`, with the same cases in the same order.
- **Timing.** A program times its own cases with a monotonic clock: two warm-up iterations, then seven timed, reporting the median and the fastest. Startup of the Erlang virtual machine, about 215 ms here, is therefore not part of any figure in the suite.
- **Checks.** Every case returns an integer derived from its result. The harness compares it across the three implementations and reports any difference in the `Result` column, so each timing is also a check that the three programs computed the same thing.
- **Inputs.** Collections are generated inside each program by the same arithmetic. The files (a 1,000,000-line 64 MiB text file, its first 120,000 lines, and JSON documents of 159 bytes, 10 KB and 5 MB) are written by the harness and passed to all three.
- **Elixir.** Baselines are compiled modules run with `elixir`, using only what ships with Elixir: `JSON`, `GenServer`, `Agent`, `Task`. The versions are those pinned in `mise.toml`.
- **Go.** The ceiling is what a Go programmer would write: slices and built-in maps mutated in place, `strings`, `regexp`, `encoding/json`, `time`, goroutines and channels, a mutex for shared state. Where Alchem and Elixir must leave an input untouched, the Go version clones it once.
- **Build figures.** The harness also times `alchem check`, `alchem build`, `go build` and `elixirc` for each program and records binary sizes.

## Detecting regressions

`benchmarks/baseline.json` is the JSON record of the run below. `-compare` runs the suite again and exits with status 3 if a case got slower. Absolute times do not travel between machines, so a case is judged by Alchem's ratio to Elixir and to Go measured in the same run: it regresses when both ratios grew by more than `-threshold` (1.25 by default). A reference under 100 µs in either run is ignored, and a case with no usable reference is skipped. After an intended change in performance, write a new baseline with `-json benchmarks/baseline.json`.

Every case currently reports `same`. The Go programs for the float cases write the shortest text and round on the exact value of the float, as Alchem and Elixir do.

## Recorded results

- Date: 2026-11-11
- OS/architecture: darwin/arm64
- Logical CPUs: 14
- CPU: Apple M3 Max
- Memory: 36 GiB
- macOS: 26.5.2
- Go: go version go1.27.3 darwin/arm64
- Elixir: Elixir 1.20.5 (compiled with Erlang/OTP 29)
- Compiler and runtime: the commit that records these results
- Runs per whole-program workload: 7 (median reported)
- The machine was in ordinary use during the run (load average about 6 on 14 cores), so treat differences under about 10% as noise.

Alchem was faster than Elixir in 142 of the 193 cases and slower in 51. Before the optimisations listed under "What was optimised", the figures were 123 and 70.

### What was optimised

The first run of this suite pointed at the operations below. Each was then changed in the runtime; the ratios are Alchem's time over Elixir's, before and after.

| Operation | Before | After | Change |
| --- | --- | --- | --- |
| `<>` appending to a growing string | 91 | 0.6 | `actor.Concat` extends the string a process last built in place, in a buffer with room to grow, instead of copying it on every step. Bytes are only ever written beyond the end of every string sharing the buffer. |
| `Map.merge`, `MapSet.union` | 33 to 36 | 5.3 | `actor.MapBuilder` changes the nodes it created itself in place, and the smaller map is inserted into the larger. |
| `try` that rescues a failure | 23 to 35 | 2.4 to 3.5 | A `try` whose `rescue` takes every message tells the runtime, which then skips recording the stack of a failure that nothing will report. What remains is Go's own panic and recover, which the Go ceiling pays too. |
| `--` | 22 | 0.4 | Integer and string lists are subtracted by counting in a hash table; other element types no longer reallocate the right-hand side on each hit. |
| `Map.filter`, `Map.reject`, `Map.split_with` | 15 | 2.3 | Built with `MapBuilder`, on top of the faster traversal below. |
| Traversing a map in key order | 7 to 13 | 1.6 to 3.4 | `actor.MapSorted` collects keys with their values in one walk, so there is no lookup per key, and sorts integer keys with a radix sort. |
| `Map.new`, `MapSet.new`, `Enum.frequencies`, `Enum.group_by` | 2 to 7 | 0.4 to 0.9 | Built with `MapBuilder`. |
| `Enum.sort`, `Enum.sort_by` | 2.6 to 3.2 | 0.4 to 1.9 | `slices.SortStableFunc` instead of the reflection-based `sort.SliceStable`, and `slices.Sort` for integers and strings, where equal elements cannot be told apart. |
| `Enum.zip`, `zip_with`, `zip_reduce` of two lists | 3.3 | 0.04 | A library function may now have a variant that takes lists as stored, called when every enumerable argument is a list; these index both lists instead of pulling one through a coroutine. This also removed the cost that dominated `string == and < compare`. |
| `List.delete_at`, `insert_at`, `replace_at`, `update_at` | 1.3 to 3.2 | 0.1 to 0.3 | List variants that make one copy of the storage. |

| `JSON.encode!` | 1.3 to 2.9 | 0.4 to 0.9 | Strings of printable ASCII that need no escaping are written directly; anything else still goes through `encoding/json`, so the output is unchanged. |
| `MapSet.intersection`, `difference`, `subset?`, `disjoint?`, `equal?` | 3.0 to 3.2 | 1.0 to 1.2 | Results are built with `MapBuilder` from the smaller set, and the three tests count shared elements instead of building a set. |
| `Enum.concat` and `List.delete` on lists, `Enum.flat_map` | 1.5 to 1.8 | 0.1 to 0.5 | List variants that copy the storage once; `flat_map` appends each result directly. |
| `Integer.to_string(n, 16)`, `Integer.digits` | 1.7 to 2.3 | 1.1 to 1.6 | Upper-cased in place, and the digit list allocated once. |

### Candidates for optimisation

What is still slower than Elixir, grouped by cause. The causes come from reading `compiler/library.go.txt` and `compiler/actor/`.

| Operation | Alchem / Elixir | Likely cause |
| --- | --- | --- |
| `left ++ right` with a long right side | 12 | Lists are slices stored head-last, so prepending a chunk copies the entire accumulated list, where a linked list copies only the left operand. The same representation makes appending 9 times faster than Elixir, so this is a trade rather than a defect. |
| `Map.merge`, `MapSet.union` | 5 | Still one insertion per key of the smaller map. Erlang merges two tries structurally in native code; a merge that walks both tries would close most of the rest. |
| `Map.put`, `Map.update`, `Map.delete`, `MapSet.put` one key at a time | 2.2 to 4.2 | Every change copies a path of nodes, each a separately allocated struct and slot slice, and `update` hashes the key twice (`MapGet` then `MapPut`). A loop of single puts cannot use the builder, because every intermediate map is a value the program may keep. |
| `JSON.decode` | 1.6 to 3.7 | `jsonParse` decodes into `any` with `encoding/json` and `UseNumber`, then `jsonRead` converts the whole tree into the `JSON` type. That is two passes and two sets of allocations; a decoder that produces the `JSON` type directly would halve it. |
| `try` that rescues a failure | 2.4 to 3.5 | Go's panic and recover; the Go ceiling is within 1.5 times. |
| Traversing a map in key order | 1.6 to 3.4 | A hash trie has to sort to give the defined key order, where Erlang's small maps are already sorted. |
| Recursion over `[head \| tail]` | 3.1 | Each call counts call depth and matches the list pattern, and there is no tail-call elimination. The default depth limit of 100,000 also means a list of that length cannot be walked recursively at all; the benchmark had to use 5,000 elements. |
| `Enum.sort_by` | 1.9 | Level with the Go ceiling; the sort itself, on an index permutation. |
| `with` | 1.8 | About 22 ns per three-clause chain against 2.5 ns for the Go error returns: each `ok` or `error` is a `result` value held in an interface, so it is heap-allocated. |
| `Server.call` from 8 clients | 1.55 | A single client matches `GenServer.call`; under contention Alchem falls behind. Not investigated further. |
| `Stream.zip` | 1.0 | Level with Elixir, but 86 times the Go ceiling: a stream is pulled through `iter.Pull`, which switches coroutines for every element. |

Things that are not on the list are worth knowing too:

- Sequential work over lists and ranges (`map`, `filter`, `reduce`, `sum`, `chunk_every`, `group_by`, `uniq`), lazy streams, strings, regular expressions, number parsing, most calendar arithmetic and `File.stream!` are 2 to 50 times faster than Elixir.
- Processes are ahead of Elixir on every case: spawning, round trips, fan-in, and by a factor of about 100 when sending a large list, because messages are shared rather than copied.
- `Agent` and a single-client `Server.call` are level with Elixir, at about 0.8 µs per call.
- `Task.async_stream` over CPU-bound work is about 1.25 times slower than Elixir at every concurrency limit, which is the same ratio as the serial loop: the gap is the cost of the recursive function itself, not of the tasks.

### Whole programs

Each program is run from outside and timed as a whole; see [benchmarks](benchmarks.md) for what each does.

#### hello

Start, print one line, exit.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 2.88ms | 2.61ms | 4.3 MiB | 2.5 MiB | n/a | n/a |
| Go | 2.87ms | 2.67ms | 4.2 MiB | 2.3 MiB | n/a | n/a |
| Elixir | 202.18ms | 200.6ms | 92.2 MiB | n/a | n/a | n/a |

#### spawn

100,000 processes alive at once, then released and joined.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 117.37ms | 113.64ms | 327.1 MiB | 2.6 MiB | 1.144µs | 873473 |
| Go | 75.46ms | 73.83ms | 282.6 MiB | 2.3 MiB | 725ns | 1377456 |
| Elixir | 460.35ms | 456.03ms | 383.7 MiB | n/a | 2.581µs | 387342 |

#### echo

200,000 request/reply round trips between two processes.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 60.34ms | 59.91ms | 4.5 MiB | 2.6 MiB | 287ns | 3480490 |
| Go | 47.89ms | 43.07ms | 4.1 MiB | 2.3 MiB | 225ns | 4441829 |
| Elixir | 318.89ms | 315.72ms | 94.5 MiB | n/a | 583ns | 1713631 |

#### compute

Recursive fib(32), then the sum of squares of 1..1,000,000 through a list.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 25.68ms | 21.51ms | 20.3 MiB | 2.5 MiB | n/a | n/a |
| Go | 11.47ms | 11.24ms | 20.1 MiB | 2.3 MiB | n/a | n/a |
| Elixir | 271.8ms | 267.83ms | 217.5 MiB | n/a | n/a | n/a |

#### build

Build a 50,000-element list one prepend at a time, then walk and sum it.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 6.85ms | 6.76ms | 19.0 MiB | 2.5 MiB | n/a | n/a |
| Go | 4.62ms | 4.4ms | 9.3 MiB | 2.3 MiB | n/a | n/a |
| Elixir | 232.99ms | 232.28ms | 95.2 MiB | n/a | n/a | n/a |

#### state

Build a 50,000-entry map one key at a time, sum it in key order, then update 1,000 counters 50,000 times.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 58.72ms | 58ms | 19.2 MiB | 2.6 MiB | n/a | n/a |
| Go | 9.17ms | 9.07ms | 7.0 MiB | 2.4 MiB | n/a | n/a |
| Elixir | 242.4ms | 238.75ms | 113.5 MiB | n/a | n/a | n/a |

#### restart

20,000 supervised crash, restart and round-trip cycles.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 111.56ms | 110.28ms | 11.7 MiB | 2.6 MiB | 5.433µs | 184030 |
| Go | 34.56ms | 34.24ms | 9.6 MiB | 2.3 MiB | 1.584µs | 630954 |
| Elixir | 1.50611s | 1.47565s | 132.2 MiB | n/a | 65.196µs | 15338 |

### Suite

Each program times its own cases: two warm-up iterations, then the median of seven. `Alchem / Elixir` and `Alchem / Go` are how many times longer Alchem took, so below 1 Alchem is faster. `Result` says whether the implementations computed the same value.

#### enum

Enum over lists, ranges and maps.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| enum.map list 1M | 4.38 ms | 8.60 ms | 412 µs | 0.51 | 11 | same |
| enum.filter list 1M | 3.00 ms | 5.40 ms | 1.10 ms | 0.56 | 2.74 | same |
| enum.reduce list 1M | 3.01 ms | 4.97 ms | 2.99 ms | 0.61 | 1.01 | same |
| enum.sum list 1M | 1.45 ms | 2.39 ms | 288 µs | 0.61 | 5.02 | same |
| enum.count predicate list 1M | 902 µs | 4.91 ms | 585 µs | 0.18 | 1.54 | same |
| enum.map range 1M | 4.28 ms | 5.21 ms | 411 µs | 0.82 | 10 | same |
| enum.filter range 1M | 3.21 ms | 5.52 ms | 977 µs | 0.58 | 3.28 | same |
| enum.reduce range 1M | 3.03 ms | 4.15 ms | 2.99 ms | 0.73 | 1.01 | same |
| enum.map map 100k | 3.06 ms | 1.53 ms | 517 µs | 2.00 | 5.92 | same |
| enum.filter map 100k | 2.94 ms | 1.73 ms | 1.15 ms | 1.70 | 2.56 | same |
| enum.reduce map 100k | 2.32 ms | 1.07 ms | 484 µs | 2.16 | 4.79 | same |
| enum.sort integers 1M | 52.34 ms | 57.36 ms | 49.40 ms | 0.91 | 1.06 | same |
| enum.sort strings 200k | 24.85 ms | 54.06 ms | 24.08 ms | 0.46 | 1.03 | same |
| enum.sort_by 200k | 28.17 ms | 15.23 ms | 27.58 ms | 1.85 | 1.02 | same |
| enum.group_by 1M into 1000 | 14.89 ms | 116.9 ms | 7.77 ms | 0.13 | 1.92 | same |
| enum.frequencies strings 200k | 17.91 ms | 55.95 ms | 5.27 ms | 0.32 | 3.40 | same |
| enum.chunk_every 1M by 100 | 5.32 ms | 16.82 ms | 584 µs | 0.32 | 9.11 | same |
| enum.uniq 1M | 60.46 ms | 401.4 ms | 53.73 ms | 0.15 | 1.13 | same |
| enum.zip 1M | 545 µs | 13.70 ms | 399 µs | 0.04 | 1.37 | same |
| enum.unzip 1M | 6.20 ms | 8.10 ms | 1.70 ms | 0.77 | 3.66 | same |
| enum.with_index 1M | 4.93 ms | 9.62 ms | 445 µs | 0.51 | 11 | same |
| enum.flat_map 200k | 2.30 ms | 5.10 ms | 97 µs | 0.45 | 24 | same |
| enum.member? miss 1M | 275 µs | 2.38 ms | 271 µs | 0.12 | 1.01 | same |
| enum.join strings 200k | 1.20 ms | 8.80 ms | 1.50 ms | 0.14 | 0.80 | same |
| enum.map_join integers 200k | 4.46 ms | 20.30 ms | 3.03 ms | 0.22 | 1.47 | same |
| enum.min_max 1M | 7.48 ms | 11.37 ms | 1.11 ms | 0.66 | 6.76 | same |
| enum.reverse 1M | 3.50 ms | 5.42 ms | 389 µs | 0.65 | 9.01 | same |
| enum.slice middle 500k of 1M | 2.45 ms | 5.03 ms | 70 µs | 0.49 | 35 | same |
| enum.at last of 1M | 1.09 ms | 2.52 ms | 0 µs | 0.43 | n/a | same |
| enum.concat 1M + 1M | 539 µs | 4.12 ms | 461 µs | 0.13 | 1.17 | same |

#### stream

Lazy Stream pipelines against eager ones, and File.stream!.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| stream map filter sum 1M | 1.68 ms | 9.60 ms | 579 µs | 0.18 | 2.90 | same |
| eager map filter sum 1M | 8.10 ms | 28.03 ms | 578 µs | 0.29 | 14 | same |
| stream map filter take 1,000 of 1M | 13 µs | 23 µs | 1 µs | 0.57 | 13 | same |
| eager map filter take 1,000 of 1M | 7.18 ms | 23.40 ms | 1 µs | 0.31 | 7179 | same |
| stream chunk_every 100 then sum 1M | 6.60 ms | 10.75 ms | 293 µs | 0.61 | 23 | same |
| eager chunk_every 100 then sum 1M | 7.17 ms | 19.92 ms | 294 µs | 0.36 | 24 | same |
| stream range map filter sum 1M | 2.05 ms | 10.53 ms | 572 µs | 0.19 | 3.58 | same |
| stream.iterate take 1M | 6.14 ms | 14.58 ms | 4.15 ms | 0.42 | 1.48 | same |
| stream.unfold 1M | 2.72 ms | 6.06 ms | 555 µs | 0.45 | 4.89 | same |
| stream.with_index 1M | 1.75 ms | 10.50 ms | 307 µs | 0.17 | 5.71 | same |
| stream.flat_map 200k | 933 µs | 5.95 ms | 165 µs | 0.16 | 5.65 | same |
| stream.scan 1M | 5.07 ms | 15.87 ms | 3.05 ms | 0.32 | 1.66 | same |
| stream.zip 1M | 47.60 ms | 47.55 ms | 560 µs | 1.00 | 85 | same |
| file.stream! count lines 1M (64 MiB) | 28.33 ms | 29.77 ms | 25.73 ms | 0.95 | 1.10 | same |
| file.stream! parse and sum a column 1M | 117.7 ms | 526.2 ms | 46.52 ms | 0.22 | 2.53 | same |
| file.stream! word frequencies 1M | 303.5 ms | 1.63 s | 85.74 ms | 0.19 | 3.54 | same |
| file.stream! filter then chunk_every 1,000 | 51.53 ms | 554.9 ms | 47.23 ms | 0.09 | 1.09 | same |
| file.stream! 64 KiB chunks (64 MiB) | 6.83 ms | 5.26 ms | 3.40 ms | 1.30 | 2.01 | same |
| file.stream! sum a column 120k (8 MiB) | 14.02 ms | 62.51 ms | 5.26 ms | 0.22 | 2.67 | same |
| file.read! split sum a column 120k (8 MiB) | 17.17 ms | 39.13 ms | 4.95 ms | 0.44 | 3.47 | same |

#### map_set

Map and MapSet.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| map.put build integer keys 1k | 242 µs | 61 µs | 36 µs | 3.97 | 6.72 | same |
| map.put build integer keys 100k | 54.70 ms | 16.89 ms | 2.91 ms | 3.24 | 19 | same |
| map.put build integer keys 1M | 923.5 ms | 404.9 ms | 43.26 ms | 2.28 | 21 | same |
| map.put build string keys 100k | 77.27 ms | 26.96 ms | 6.13 ms | 2.87 | 13 | same |
| map.new from 100k pairs | 8.02 ms | 10.39 ms | 918 µs | 0.77 | 8.74 | same |
| map.get hit integer keys 100k | 2.98 ms | 5.10 ms | 864 µs | 0.58 | 3.45 | same |
| map.get miss integer keys 100k | 2.21 ms | 2.38 ms | 1.64 ms | 0.93 | 1.35 | same |
| map.fetch! string keys 100k | 8.93 ms | 11.72 ms | 3.68 ms | 0.76 | 2.43 | same |
| map.has_key? 100k | 2.40 ms | 2.88 ms | 1.60 ms | 0.83 | 1.50 | same |
| map.update 1M counters over 1000 keys | 385.2 ms | 91.67 ms | 5.03 ms | 4.20 | 77 | same |
| map.update existing 100k keys | 85.46 ms | 24.99 ms | 1.04 ms | 3.42 | 82 | same |
| map.merge 100k with 100k | 9.64 ms | 1.84 ms | 3.46 ms | 5.23 | 2.78 | same |
| map.delete 100k keys | 71.51 ms | 15.82 ms | 2.33 ms | 4.52 | 31 | same |
| map.to_list 100k | 3.35 ms | 1.02 ms | 487 µs | 3.27 | 6.89 | same |
| map.keys 100k | 2.27 ms | 1.37 ms | 474 µs | 1.66 | 4.80 | same |
| map.values 100k | 2.18 ms | 1.40 ms | 472 µs | 1.56 | 4.62 | same |
| map.filter 100k | 13.00 ms | 5.68 ms | 2.24 ms | 2.29 | 5.79 | same |
| mapset.new from 1M integers | 50.37 ms | 133.1 ms | 14.65 ms | 0.38 | 3.44 | same |
| mapset.put 100k | 59.39 ms | 20.74 ms | 2.75 ms | 2.86 | 22 | same |
| mapset.member? 200k | 4.25 ms | 5.47 ms | 2.28 ms | 0.78 | 1.87 | same |
| mapset.union 100k with 100k | 11.10 ms | 2.01 ms | 4.06 ms | 5.52 | 2.73 | same |
| mapset.intersection 100k with 100k | 6.06 ms | 5.34 ms | 3.81 ms | 1.14 | 1.59 | same |
| mapset.difference 100k with 100k | 8.04 ms | 7.80 ms | 5.17 ms | 1.03 | 1.55 | same |

#### list

Positional List operations, ++ and --.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| list.at 2,000 reads of 10k | 10.59 ms | 12.18 ms | 3 µs | 0.87 | 3528 | same |
| list.replace_at 1,000 of 10k | 4.05 ms | 32.74 ms | 18 µs | 0.12 | 225 | same |
| list.update_at 1,000 of 10k | 3.99 ms | 32.60 ms | 25 µs | 0.12 | 160 | same |
| list.insert_at 1,000 into 10k | 4.89 ms | 35.19 ms | 553 µs | 0.14 | 8.85 | same |
| list.delete_at 1,000 of 10k | 4.44 ms | 14.50 ms | 503 µs | 0.31 | 8.82 | same |
| list.delete value 1,000 of 10k | 5.81 ms | 30.68 ms | 1.70 ms | 0.19 | 3.42 | same |
| list.last 1,000 times of 100k | 1 µs | 156.2 ms | 0 µs | 0.00 | n/a | same |
| list.length 1,000 times of 100k | 1 µs | 84.42 ms | 0 µs | 0.00 | n/a | same |
| list ++ append 1k to growing list 200 times | 8.97 ms | 81.29 ms | 581 µs | 0.11 | 15 | same |
| list ++ prepend 1k to growing list 200 times | 8.72 ms | 734 µs | 9.50 ms | 12 | 0.92 | same |
| list -- 1,000 from 10k | 108 µs | 296 µs | 1.70 ms | 0.36 | 0.06 | same |
| list.flatten 1,000 lists of 100 | 297 µs | 1.00 ms | 57 µs | 0.30 | 5.21 | same |
| list prepend build 1M | 2.56 ms | 4.20 ms | 2.43 ms | 0.61 | 1.06 | same |
| list head/tail recursive walk 5k, 20 times | 600 µs | 197 µs | 26 µs | 3.05 | 23 | same |
| list.foldr 100k | 803 µs | 728 µs | 347 µs | 1.10 | 2.31 | same |
| list.duplicate 1M | 401 µs | 2.94 ms | 265 µs | 0.14 | 1.51 | same |
| list in (membership) 1,000 misses of 10k | 2.73 ms | 11.82 ms | 2.73 ms | 0.23 | 1.00 | same |

#### string

String and Regex.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| string <> append 1 byte 20k times | 111 µs | 148 µs | 46 µs | 0.75 | 2.41 | same |
| string interpolation 200k | 8.54 ms | 38.36 ms | 8.36 ms | 0.22 | 1.02 | same |
| string.split on space 1.4 MB | 2.05 ms | 4.70 ms | 2.07 ms | 0.44 | 0.99 | same |
| string.split whitespace 1.4 MB | 1.58 ms | 4.43 ms | 1.52 ms | 0.36 | 1.04 | same |
| string.replace 1.4 MB | 3.23 ms | 4.28 ms | 3.22 ms | 0.75 | 1.00 | same |
| string.contains? 200k words | 1.07 ms | 42.36 ms | 1.27 ms | 0.03 | 0.84 | same |
| string.starts_with? 200k words | 148 µs | 4.86 ms | 187 µs | 0.03 | 0.79 | same |
| string.upcase ASCII 1.4 MB | 1.95 ms | 24.98 ms | 2.05 ms | 0.08 | 0.95 | same |
| string.downcase ASCII 1.4 MB | 1.25 ms | 27.48 ms | 1.26 ms | 0.05 | 0.98 | same |
| string.upcase non-ASCII 310 KB | 1.21 ms | 2.53 ms | 1.20 ms | 0.48 | 1.00 | same |
| string.trim 200k words | 921 µs | 22.61 ms | 825 µs | 0.04 | 1.12 | same |
| string.length ASCII 1.4 MB | 372 µs | 285 µs | 374 µs | 1.31 | 0.99 | same |
| string.length non-ASCII 310 KB | 184 µs | 4.91 ms | 186 µs | 0.04 | 0.99 | same |
| string.slice 100k from the middle of 1,000 characters | 26.66 ms | 42.20 ms | 26.38 ms | 0.63 | 1.01 | same |
| string.graphemes non-ASCII 310 KB | 3.40 ms | 9.76 ms | 1.91 ms | 0.35 | 1.79 | same |
| string.codepoints non-ASCII 310 KB | 3.35 ms | 2.57 ms | 1.86 ms | 1.30 | 1.80 | same |
| string.reverse ASCII 1.4 MB | 4.99 ms | 35.96 ms | 4.90 ms | 0.14 | 1.02 | same |
| string.pad_leading 200k words | 11.26 ms | 39.58 ms | 4.86 ms | 0.28 | 2.32 | same |
| string == and < compare 200k words | 997 µs | 5.26 ms | 822 µs | 0.19 | 1.21 | same |
| regex.match? 100k lines | 8.08 ms | 48.31 ms | 7.98 ms | 0.17 | 1.01 | same |
| regex.run with captures 100k lines | 30.26 ms | 49.94 ms | 27.30 ms | 0.61 | 1.11 | same |
| regex.named_captures 100k lines | 35.67 ms | 71.17 ms | 27.02 ms | 0.50 | 1.32 | same |
| regex.scan 10k lines | 15.81 ms | 39.17 ms | 11.23 ms | 0.40 | 1.41 | same |
| regex.replace 10k lines | 12.22 ms | 43.35 ms | 11.84 ms | 0.28 | 1.03 | same |
| regex.split 10k lines | 13.98 ms | 41.91 ms | 13.53 ms | 0.33 | 1.03 | same |

#### numbers

Integer and Float parsing, formatting and arithmetic.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| integer.to_string 200k | 2.85 ms | 3.97 ms | 2.87 ms | 0.72 | 0.99 | same |
| integer.to_string base 16 200k | 5.96 ms | 3.79 ms | 10.40 ms | 1.58 | 0.57 | same |
| integer.parse 200k | 4.58 ms | 19.65 ms | 1.17 ms | 0.23 | 3.90 | same |
| string.to_integer 200k | 3.19 ms | 2.59 ms | 1.16 ms | 1.23 | 2.74 | same |
| string.to_integer base 16 200k | 4.17 ms | 4.68 ms | 3.75 ms | 0.89 | 1.11 | same |
| float.to_string 200k | 9.97 ms | 7.37 ms | 22.15 ms | 1.35 | 0.45 | same |
| float.parse 200k | 6.50 ms | 19.64 ms | 4.89 ms | 0.33 | 1.33 | same |
| string.to_float 200k | 5.29 ms | 10.87 ms | 4.87 ms | 0.49 | 1.09 | same |
| float.round 2 places 200k | 645 µs | 9.50 ms | 134 µs | 0.07 | 4.81 | same |
| float.floor and ceil 200k | 1.26 ms | 9.10 ms | 179 µs | 0.14 | 7.04 | same |
| round and trunc 1M | 3.64 ms | 11.82 ms | 569 µs | 0.31 | 6.40 | same |
| float arithmetic 1M | 1.39 ms | 7.72 ms | 592 µs | 0.18 | 2.35 | same |
| integer arithmetic 5M | 18.14 ms | 30.04 ms | 17.69 ms | 0.60 | 1.03 | same |
| integer.digits and undigits 200k | 14.46 ms | 13.48 ms | 2.21 ms | 1.07 | 6.53 | same |
| integer.gcd 1M | 40.32 ms | 63.13 ms | 37.46 ms | 0.64 | 1.08 | same |
| integer.pow 1M | 6.61 ms | 15.27 ms | 4.35 ms | 0.43 | 1.52 | same |
| bitwise mix 1M | 2.27 ms | 3.88 ms | 1.35 ms | 0.59 | 1.68 | same |

#### json

JSON decode and encode.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| json.decode 159 B, 10,000 times | 36.89 ms | 23.16 ms | 20.68 ms | 1.59 | 1.78 | same |
| json.decode 10 KB, 200 times | 40.97 ms | 11.63 ms | 25.96 ms | 3.52 | 1.58 | same |
| json.decode 5 MB | 96.54 ms | 38.60 ms | 65.96 ms | 2.50 | 1.46 | same |
| json.encode 159 B, 10,000 times | 6.95 ms | 8.66 ms | 12.66 ms | 0.80 | 0.55 | same |
| json.encode 10 KB, 200 times | 8.66 ms | 9.81 ms | 7.46 ms | 0.88 | 1.16 | same |
| json.encode 5 MB | 20.85 ms | 51.22 ms | 19.56 ms | 0.41 | 1.07 | same |

#### calendar

Date, NaiveDateTime and DateTime.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| date.add 1M | 41.16 ms | 37.71 ms | 21.75 ms | 1.09 | 1.89 | same |
| date.new! 1M | 23.25 ms | 214.6 ms | 11.68 ms | 0.11 | 1.99 | same |
| date.diff 100k | 2.18 ms | 5.11 ms | 597 µs | 0.43 | 3.66 | same |
| date.day_of_week 100k | 1.17 ms | 4.43 ms | 270 µs | 0.26 | 4.35 | same |
| date.end_of_month 100k | 1.30 ms | 3.32 ms | 2.34 ms | 0.39 | 0.55 | same |
| date.to_iso8601 100k | 11.52 ms | 10.41 ms | 4.79 ms | 1.11 | 2.41 | same |
| date.from_iso8601 100k | 6.97 ms | 24.01 ms | 5.23 ms | 0.29 | 1.33 | same |
| date sort 100k | 81.82 ms | 72.51 ms | 10.53 ms | 1.13 | 7.77 | same |
| naive_date_time.add 1M | 35.06 ms | 143.4 ms | 5.16 ms | 0.24 | 6.79 | same |
| naive_date_time.diff 100k | 2.41 ms | 12.09 ms | 594 µs | 0.20 | 4.06 | same |
| naive_date_time.to_iso8601 100k | 24.89 ms | 18.97 ms | 7.74 ms | 1.31 | 3.22 | same |
| naive_date_time.from_iso8601 100k | 12.01 ms | 27.41 ms | 8.06 ms | 0.44 | 1.49 | same |
| date_time.from_unix! 1M | 51.71 ms | 75.87 ms | 2.72 ms | 0.68 | 19 | same |
| date_time.to_unix 100k | 1.11 ms | 6.69 ms | 54 µs | 0.17 | 21 | same |
| date_time.add 100k | 4.35 ms | 19.30 ms | 734 µs | 0.23 | 5.93 | same |
| date_time.compare 100k | 4.84 ms | 14.22 ms | 196 µs | 0.34 | 25 | same |
| date_time.to_iso8601 100k | 26.82 ms | 22.95 ms | 2.42 ms | 1.17 | 11 | same |
| date_time.from_iso8601 with offset 100k | 10.23 ms | 33.46 ms | 4.80 ms | 0.31 | 2.13 | same |

#### control

For, try/rescue, with, case and cond.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| for filter and map list 1M | 1.36 ms | 4.87 ms | 1.22 ms | 0.28 | 1.11 | same |
| enum filter and map list 1M | 4.28 ms | 8.26 ms | 1.14 ms | 0.52 | 3.76 | same |
| for range 1M | 3.27 ms | 5.53 ms | 449 µs | 0.59 | 7.28 | same |
| for two generators 1,000 x 1,000 with filter | 3.46 ms | 4.31 ms | 1.02 ms | 0.80 | 3.39 | same |
| enum flat_map 1,000 x 1,000 with filter | 5.21 ms | 7.23 ms | 1.03 ms | 0.72 | 5.07 | same |
| for pattern generator 1M | 1.83 ms | 4.41 ms | 1.34 ms | 0.41 | 1.36 | same |
| for map entries 100k | 2.43 ms | 1.53 ms | 1.07 ms | 1.58 | 2.26 | same |
| loop without try 1M | 2.44 ms | 4.15 ms | 639 µs | 0.59 | 3.83 | same |
| try with no failure 1M | 8.42 ms | 4.70 ms | 4.29 ms | 1.79 | 1.96 | same |
| try rescue raise 100k | 19.56 ms | 8.67 ms | 13.29 ms | 2.26 | 1.47 | same |
| try rescue division by zero 100k | 19.28 ms | 5.54 ms | 15.03 ms | 3.48 | 1.28 | same |
| with three clauses 1M | 21.93 ms | 11.84 ms | 2.47 ms | 1.85 | 8.87 | same |
| case over sum type 1M | 3.00 ms | 5.17 ms | 903 µs | 0.58 | 3.32 | same |
| cond 1M | 1.91 ms | 5.14 ms | 1.07 ms | 0.37 | 1.78 | same |
| recursive fib(27) | 1.36 ms | 1.37 ms | 568 µs | 1.00 | 2.39 | same |

#### processes

Spawn, send and receive.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| process spawn and await 100k, one at a time | 51.20 ms | 70.38 ms | 23.80 ms | 0.73 | 2.15 | same |
| process spawn 100k alive at once, release, await | 80.97 ms | 188.8 ms | 45.21 ms | 0.43 | 1.79 | same |
| process ping-pong 500k round trips | 143.2 ms | 212.0 ms | 97.98 ms | 0.68 | 1.46 | same |
| process fan-in 8 senders, 1M messages | 136.6 ms | 1.26 s | 55.57 ms | 0.11 | 2.46 | same |
| process ring 1,000 processes, 1,000 laps | 162.9 ms | 220.9 ms | 114.3 ms | 0.74 | 1.43 | same |
| process send a 10k-element list, 10k round trips | 2.96 ms | 364.3 ms | 1.98 ms | 0.01 | 1.49 | same |
| process mailbox fill 500k then drain | 11.61 ms | 74.97 ms | 9.69 ms | 0.15 | 1.20 | same |

#### otp

Server, Agent and Task.

| Case | Alchem | Elixir | Go | Alchem / Elixir | Alchem / Go | Result |
| --- | --- | --- | --- | --- | --- | --- |
| server.call 200k | 149.1 ms | 169.0 ms | 39.31 ms | 0.88 | 3.79 | same |
| server.call 8 clients, 25k calls each | 313.2 ms | 183.6 ms | 74.16 ms | 1.71 | 4.22 | same |
| server.cast 200k then one call | 16.95 ms | 18.72 ms | 6.03 ms | 0.91 | 2.81 | same |
| agent.get 200k | 146.2 ms | 181.2 ms | 538 µs | 0.81 | 272 | same |
| agent.update 200k then get | 142.4 ms | 180.2 ms | 490 µs | 0.79 | 291 | same |
| agent.get_and_update 200k | 145.3 ms | 175.0 ms | 498 µs | 0.83 | 292 | same |
| task.async and await 100k, one at a time | 85.90 ms | 159.9 ms | 24.73 ms | 0.54 | 3.47 | same |
| task.async 10k at once, await_many | 19.56 ms | 52.62 ms | 3.57 ms | 0.37 | 5.47 | same |
| task.async_stream 100k trivial items | 70.83 ms | 251.1 ms | 45.30 ms | 0.28 | 1.56 | same |
| serial 1,000 x fib(22) | 153.3 ms | 118.1 ms | 51.09 ms | 1.30 | 3.00 | same |
| task.async_stream 1,000 x fib(22), limit 1 | 169.2 ms | 121.4 ms | 59.66 ms | 1.39 | 2.84 | same |
| task.async_stream 1,000 x fib(22), limit 2 | 81.67 ms | 64.00 ms | 26.99 ms | 1.28 | 3.03 | same |
| task.async_stream 1,000 x fib(22), limit 4 | 44.65 ms | 32.62 ms | 14.66 ms | 1.37 | 3.05 | same |
| task.async_stream 1,000 x fib(22), limit 8 | 22.86 ms | 22.54 ms | 7.45 ms | 1.01 | 3.07 | same |
| task.async_stream 1,000 x fib(22), limit 14 | 20.24 ms | 16.26 ms | 4.78 ms | 1.24 | 4.24 | same |

### Every case slower than Elixir

The 51 cases, of 193, where Alchem took longer than Elixir (cases under 100 µs in Alchem are left out), slowest first.

| Case | Alchem | Elixir | Go | Alchem / Elixir |
| --- | --- | --- | --- | --- |
| list ++ prepend 1k to growing list 200 times | 8.72 ms | 734 µs | 9.50 ms | 12 |
| mapset.union 100k with 100k | 11.10 ms | 2.01 ms | 4.06 ms | 5.52 |
| map.merge 100k with 100k | 9.64 ms | 1.84 ms | 3.46 ms | 5.23 |
| map.delete 100k keys | 71.51 ms | 15.82 ms | 2.33 ms | 4.52 |
| map.update 1M counters over 1000 keys | 385.2 ms | 91.67 ms | 5.03 ms | 4.20 |
| map.put build integer keys 1k | 242 µs | 61 µs | 36 µs | 3.97 |
| json.decode 10 KB, 200 times | 40.97 ms | 11.63 ms | 25.96 ms | 3.52 |
| try rescue division by zero 100k | 19.28 ms | 5.54 ms | 15.03 ms | 3.48 |
| map.update existing 100k keys | 85.46 ms | 24.99 ms | 1.04 ms | 3.42 |
| map.to_list 100k | 3.35 ms | 1.02 ms | 487 µs | 3.27 |
| map.put build integer keys 100k | 54.70 ms | 16.89 ms | 2.91 ms | 3.24 |
| list head/tail recursive walk 5k, 20 times | 600 µs | 197 µs | 26 µs | 3.05 |
| map.put build string keys 100k | 77.27 ms | 26.96 ms | 6.13 ms | 2.87 |
| mapset.put 100k | 59.39 ms | 20.74 ms | 2.75 ms | 2.86 |
| json.decode 5 MB | 96.54 ms | 38.60 ms | 65.96 ms | 2.50 |
| map.filter 100k | 13.00 ms | 5.68 ms | 2.24 ms | 2.29 |
| map.put build integer keys 1M | 923.5 ms | 404.9 ms | 43.26 ms | 2.28 |
| try rescue raise 100k | 19.56 ms | 8.67 ms | 13.29 ms | 2.26 |
| enum.reduce map 100k | 2.32 ms | 1.07 ms | 484 µs | 2.16 |
| enum.map map 100k | 3.06 ms | 1.53 ms | 517 µs | 2.00 |
| with three clauses 1M | 21.93 ms | 11.84 ms | 2.47 ms | 1.85 |
| enum.sort_by 200k | 28.17 ms | 15.23 ms | 27.58 ms | 1.85 |
| try with no failure 1M | 8.42 ms | 4.70 ms | 4.29 ms | 1.79 |
| server.call 8 clients, 25k calls each | 313.2 ms | 183.6 ms | 74.16 ms | 1.71 |
| enum.filter map 100k | 2.94 ms | 1.73 ms | 1.15 ms | 1.70 |
| map.keys 100k | 2.27 ms | 1.37 ms | 474 µs | 1.66 |
| json.decode 159 B, 10,000 times | 36.89 ms | 23.16 ms | 20.68 ms | 1.59 |
| for map entries 100k | 2.43 ms | 1.53 ms | 1.07 ms | 1.58 |
| integer.to_string base 16 200k | 5.96 ms | 3.79 ms | 10.40 ms | 1.58 |
| map.values 100k | 2.18 ms | 1.40 ms | 472 µs | 1.56 |
| task.async_stream 1,000 x fib(22), limit 1 | 169.2 ms | 121.4 ms | 59.66 ms | 1.39 |
| task.async_stream 1,000 x fib(22), limit 4 | 44.65 ms | 32.62 ms | 14.66 ms | 1.37 |
| float.to_string 200k | 9.97 ms | 7.37 ms | 22.15 ms | 1.35 |
| naive_date_time.to_iso8601 100k | 24.89 ms | 18.97 ms | 7.74 ms | 1.31 |
| string.length ASCII 1.4 MB | 372 µs | 285 µs | 374 µs | 1.31 |
| string.codepoints non-ASCII 310 KB | 3.35 ms | 2.57 ms | 1.86 ms | 1.30 |
| serial 1,000 x fib(22) | 153.3 ms | 118.1 ms | 51.09 ms | 1.30 |
| file.stream! 64 KiB chunks (64 MiB) | 6.83 ms | 5.26 ms | 3.40 ms | 1.30 |
| task.async_stream 1,000 x fib(22), limit 2 | 81.67 ms | 64.00 ms | 26.99 ms | 1.28 |
| task.async_stream 1,000 x fib(22), limit 14 | 20.24 ms | 16.26 ms | 4.78 ms | 1.24 |
| string.to_integer 200k | 3.19 ms | 2.59 ms | 1.16 ms | 1.23 |
| date_time.to_iso8601 100k | 26.82 ms | 22.95 ms | 2.42 ms | 1.17 |
| mapset.intersection 100k with 100k | 6.06 ms | 5.34 ms | 3.81 ms | 1.14 |
| date sort 100k | 81.82 ms | 72.51 ms | 10.53 ms | 1.13 |
| date.to_iso8601 100k | 11.52 ms | 10.41 ms | 4.79 ms | 1.11 |
| list.foldr 100k | 803 µs | 728 µs | 347 µs | 1.10 |
| date.add 1M | 41.16 ms | 37.71 ms | 21.75 ms | 1.09 |
| integer.digits and undigits 200k | 14.46 ms | 13.48 ms | 2.21 ms | 1.07 |
| mapset.difference 100k with 100k | 8.04 ms | 7.80 ms | 5.17 ms | 1.03 |
| task.async_stream 1,000 x fib(22), limit 8 | 22.86 ms | 22.54 ms | 7.45 ms | 1.01 |
| stream.zip 1M | 47.60 ms | 47.55 ms | 560 µs | 1.00 |

### Compile time and binary size

`alchem check` analyses without building. `alchem build` includes the Go build of the generated program, with the Go build cache warm. Elixir is `elixirc` on the same program, including starting the virtual machine.

| Program | alchem check | alchem build | Alchem binary | go build | Go binary | elixirc |
| --- | --- | --- | --- | --- | --- | --- |
| enum | 6 ms | 316 ms | 2.8 MiB | 194 ms | 2.4 MiB | 270 ms |
| stream | 20 ms | 297 ms | 2.8 MiB | 197 ms | 2.4 MiB | 265 ms |
| map_set | 6 ms | 291 ms | 2.7 MiB | 193 ms | 2.4 MiB | 267 ms |
| list | 5 ms | 268 ms | 2.7 MiB | 194 ms | 2.4 MiB | 263 ms |
| string | 5 ms | 289 ms | 3.1 MiB | 201 ms | 2.8 MiB | 270 ms |
| numbers | 6 ms | 280 ms | 2.8 MiB | 197 ms | 2.4 MiB | 266 ms |
| json | 6 ms | 297 ms | 4.0 MiB | 214 ms | 3.7 MiB | 259 ms |
| calendar | 6 ms | 293 ms | 2.8 MiB | 191 ms | 2.4 MiB | 270 ms |
| control | 5 ms | 281 ms | 2.7 MiB | 192 ms | 2.4 MiB | 268 ms |
| processes | 6 ms | 273 ms | 2.7 MiB | 194 ms | 2.4 MiB | 259 ms |
| otp | 6 ms | 284 ms | 2.8 MiB | 199 ms | 2.4 MiB | 270 ms |

With an empty Go build cache, `alchem build` of `hello.alc` took 1.71s: the Go standard library and the embedded runtime are compiled once and then cached.

`hello` builds to 2.5 MiB, so the library a program uses adds 0.2 to 0.6 MiB, and 1.5 MiB for `JSON`, which brings in `encoding/json`. Check and build times vary from run to run by a factor of two for the same program, so the differences between programs here are noise.
