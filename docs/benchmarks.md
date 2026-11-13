# Benchmarks

Alchem programs are measured next to equivalent Go and Elixir programs. Sources live in `benchmarks/`: `alchem/*.alc`, `go/*/main.go` and `elixir/*.exs` implement the same seven workloads, and `harness` builds, runs and reports them.

The same harness also runs the standard library suite: 193 operations across the library modules, each written in Alchem, Elixir and Go. Its method, results and the list of operations to optimise are in [standard library benchmarks](stdlib-benchmarks.md).

```sh
go run ./benchmarks/harness            # five runs per program
go run ./benchmarks/harness -runs 7 -timeout 2m
```

The harness runs only those fixed programs, never a shell, checks each program's exact output, and bounds every build and run with a deadline. Elixir is measured when `elixir` is on `PATH` and reported as not measured otherwise. The manual **Benchmarks** workflow installs Elixir on a hosted runner and stores the report as an artifact; the results below come from it.

## What is measured

| Figure | How |
| --- | --- |
| Startup | Median wall time of `hello` |
| Process creation | `spawn`: median wall time for 100,000 live processes, minus startup, per process |
| Round-trip latency and throughput | `echo`: median wall time for 200,000 request/reply round trips, minus startup, per round trip and per second |
| Memory | Peak resident set size of the whole process, from the operating system |
| Computation | `compute`: median wall time for recursive `fib(32)` followed by the sum of squares of 1..1,000,000 through a list |
| List building | `build`: median wall time to grow a 50,000-element list one `prepend` at a time, then walk it by pattern matching and sum it |
| Map state | `state`: median wall time to build a 50,000-entry map one key at a time, sum it in key order, then update 1,000 counters 50,000 times |
| Restart latency | `restart`: median wall time for 20,000 cycles of crashing a supervised worker, waiting for its replacement and completing one round trip with it, minus startup, per cycle |
| Binary size | Size of the built executable (not applicable to Elixir scripts) |

Wall time is measured from outside the process, and each program also times its own phases with a monotonic clock and reports them on standard error as `phase NAME MICROSECONDS`; the harness prints the median of each phase across the runs. Those figures contain no process startup, so the Elixir columns compare directly. `echo` and `restart` also time every single round trip or cycle and report the fastest, the median and the 99th percentile, taken from the run with the median wall time. Peak RSS is unavailable on Windows and reported as `n/a`.

## Map updates

Maps are CHAMP tries: each node keeps its entries and its subtrees in separate arrays, so an update copies the subtree pointers on its path and shares the entries it does not change. Before, each node held one array of 24-byte slots that were either an entry or a subtree, and every level of an update copied all of them. On the development machine (Apple M-series, Go 1.27):

| Measure | Before | After |
| --- | --- | --- |
| `BenchmarkMapPutGrowing` | 1,162 ns, 3,197 B allocated per insert | 770 ns, 1,234 B |
| `BenchmarkMapGet` | 25 ns | 20 ns |
| `state`, whole program, median of 15 | 61.6 ms | 33.6 ms |
| `state`, building the 50,000-entry map | 41.2 ms | 19.2 ms |
| `state`, updating 1,000 counters 50,000 times | 14.4 ms | 7.4 ms |

The profile before the change showed the time going to garbage collection of the copied slots, which is what the separate arrays cut.

## 100,000-process experiment

Memory budget: **512 MiB obtained from the operating system for 100,000 simultaneously live processes**, about 5 KiB per process. On Windows the budget is **1280 MiB**: Go reserves a larger minimum goroutine stack there, and the same test measured 957.8 MiB (9.81 KiB per process) on a Windows ARM64 runner.

- `TestHundredThousandProcessesWithinMemoryBudget` (`compiler/actor/scale_test.go`) spawns 100,000 processes that all block in `receive`, measures the runtime's memory growth, then releases and joins every one. It fails above the budget. Measured on Linux AMD64: 370.1 MiB, 3.79 KiB per process.
- The compiled `spawn.alc` program below peaked at 472.8 MiB resident for the whole executable on the hosted runner (397.1 MiB on the development container). That figure includes everything the program allocates, not only the runtime, and leaves little margin under 512 MiB.
- The test is skipped under `-short` and under the race detector, whose instrumentation changes memory use; CI runs it uninstrumented in its own step.

## Recorded results

Recorded by the Benchmarks workflow on a GitHub-hosted runner at commit `09d477c`. Shared virtual hardware makes these indicative, not authoritative; rerun the harness or the workflow to compare.

## Environment

- Date: 2026-11-10
- OS/architecture: linux/amd64
- Logical CPUs: 2
- CPU: AMD EPYC 9V74 80-Core Processor
- Memory: 8122100 kB
- Go: go version go1.23.12 linux/amd64
- Elixir: Elixir 1.18.6 (compiled with Erlang/OTP 27)
- Runs per program: 7 (median reported)

### hello

Start, print one line, exit.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 1.14ms | 1.12ms | 2.6 MiB | 2.2 MiB | n/a | n/a |
| Go | 1.14ms | 1.06ms | 2.7 MiB | 2.0 MiB | n/a | n/a |
| Elixir | 299.27ms | 290.89ms | 73.9 MiB | n/a | n/a | n/a |

### spawn

100,000 processes alive at once, then released and joined.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 768.81ms | 738.96ms | 472.8 MiB | 2.3 MiB | 7.676µs | 130265 |
| Go | 278.14ms | 272.2ms | 270.2 MiB | 2.0 MiB | 2.77µs | 360999 |
| Elixir | 1.14324s | 1.00302s | 356.6 MiB | n/a | 8.439µs | 118488 |

### echo

200,000 request/reply round trips between two processes.

| Implementation | Median wall | Fastest | Peak RSS | Binary size | Per operation | Operations/s |
| --- | --- | --- | --- | --- | --- | --- |
| Alchem | 213.78ms | 210.07ms | 7.1 MiB | 2.3 MiB | 1.063µs | 940579 |
| Go | 47.81ms | 47.1ms | 3.8 MiB | 2.0 MiB | 233ns | 4285253 |
| Elixir | 407.98ms | 403.37ms | 77.2 MiB | n/a | 543ns | 1839734 |

## Hosted runner after round 5

The Benchmarks workflow was run again at commit `067f942`, after five of the six rounds below. The runner was a different machine from the first recording (AMD EPYC 7763, 2 logical CPUs, Go 1.23.12, Elixir 1.18.6 on OTP 27, medians of 7 runs), so compare the three implementations within this table rather than against the table above.

| Workload | Alchem | Go | Elixir |
| --- | --- | --- | --- |
| `hello` wall time | 1.5 ms | 1.4 ms | 381.8 ms |
| `spawn` wall time | 461.5 ms | 312.1 ms | 1818.4 ms |
| `spawn` peak RSS | 309.6 MiB | 270.3 MiB | 357.2 MiB |
| `echo` wall time | 104.2 ms | 61.0 ms | 539.0 ms |
| `echo` per round trip, startup subtracted | 513 ns | 298 ns | 785 ns |
| `compute` wall time | 68.2 ms | 24.7 ms | 559.9 ms |
| `compute` peak RSS | 17.6 MiB | 17.3 MiB | 202.1 MiB |

In this run Alchem was ahead of Elixir on every workload, including per round trip and memory for 100,000 processes, which it had trailed on in the first recording. Elixir's own figures were slower here than on the first runner, so part of that change is the machine. Against Go on the same runner, Alchem was about 1.5 times per process, 1.7 times per round trip and 2.8 times on `compute`; round 6 was not yet included.

## Current hosted-runner results

The Benchmarks workflow at commit `3f075a7` (v0.3.0), on a GitHub-hosted runner (AMD EPYC 9V74, 4 logical CPUs, Go 1.27.4, Elixir 1.20.5 on OTP 29, medians of 7 runs). This is the reference comparison. The runner is a different machine from the recordings below, so compare the three implementations within this section rather than across sections.

Whole programs, timed from outside:

| Workload | Alchem | Go | Elixir | Alchem / Go |
| --- | --- | --- | --- | --- |
| `hello` | 1.41 ms | 1.31 ms | 264.0 ms | 1.1 |
| `spawn` | 346.5 ms | 202.6 ms | 693.4 ms | 1.7 |
| `echo` | 102.1 ms | 66.5 ms | 447.5 ms | 1.5 |
| `compute` | 29.9 ms | 20.0 ms | 430.9 ms | 1.5 |
| `build` | 12.3 ms | 5.5 ms | 332.6 ms | 2.3 |
| `state` | 43.4 ms | 11.4 ms | 334.5 ms | 3.8 |
| `restart` | 144.4 ms | 37.4 ms | 2054.9 ms | 3.9 |

Each workload also times its own phases, so the virtual machine's startup no longer has to be subtracted from Elixir's figures:

| Phase | Alchem | Go | Elixir |
| --- | --- | --- | --- |
| `spawn`: start 100,000 processes | 220.1 ms | 167.0 ms | 184.6 ms |
| `spawn`: release and join them | 101.6 ms | 13.4 ms | 212.1 ms |
| `echo`: 200,000 round trips | 92.0 ms | 59.3 ms | 84.2 ms |
| `compute`: fib(32) | 17.7 ms | 10.2 ms | 19.0 ms |
| `compute`: squares of 1..1,000,000 | 9.4 ms | 7.2 ms | 79.2 ms |
| `build`: grow | 0.71 ms | 0.85 ms | 1.59 ms |
| `build`: walk | 9.09 ms | 2.94 ms | 1.22 ms |
| `state`: build | 27.3 ms | 3.1 ms | 17.0 ms |
| `state`: sum | 3.3 ms | 6.1 ms | 25.6 ms |
| `state`: update | 10.9 ms | 0.5 ms | 6.2 ms |
| `restart`: 20,000 cycles | 141.8 ms | 35.5 ms | 1705.6 ms |

Latency distributions (fastest, median, 99th percentile): a round trip takes 350, 391 and 1302 ns in Alchem, 230, 250 and 611 ns in Go, and 340, 370 and 872 ns in Elixir; a crash-and-restart cycle 4, 5 and 22 µs, 1, 1 and 8 µs, and 3, 77 and 307 µs.

Peak memory: 100,000 processes take 325.5 MiB in Alchem, 278.3 MiB in Go and 362.2 MiB in Elixir; `state` takes 12.8, 7.6 and 91.1 MiB; an idle program 4.1, 4.4 and 71.5 MiB.

Reading these:

- Alchem is within 1.5 to 1.7 times Go on processes, messaging and computation, and starts as fast.
- Against Elixir, Alchem is faster as a whole program on every workload, and ahead or close phase by phase except where noted here. Round trips are about 9% slower than Elixir's (92 against 84 ms), and starting processes about 19% slower (220 against 185 ms), though Alchem releases and joins them in half the time.
- Walking a list and building and updating a map are where Elixir is still clearly ahead inside the program: `build`'s walk (9.1 against 1.2 ms), `state`'s build (27 against 17 ms) and update (11 against 6 ms). Summing the map in key order is faster in Alchem.
- `restart` is a full supervisor against Go's hand-written recover-and-respawn loop; Elixir's median restart is 15 times Alchem's.

### After v0.3.0: tail calls and folds that own their map

Two changes address the phases where Elixir was ahead above. They were measured on the development machine (Apple M-series, 14 logical CPUs, Go 1.27, Elixir on the same machine, medians of 5 runs), so compare within this table; the hosted-runner tables above predate them.

| Phase | Before | After | Elixir | Go |
| --- | --- | --- | --- | --- |
| `build`: walk | 3.46 ms | 0.09 ms | 0.77 ms | 1.4 ms |
| `state`: build | 19.2 ms | 4.8 ms | 11.9 ms | 1.4 ms |
| `state`: update | 7.6 ms | 1.45 ms | 3.9 ms | 0.3 ms |

- **Walk.** `count(rest, seen + 1)` is a call to itself in return position, which now runs as a loop instead of 50,000 nested calls. Go's baseline recurses, so it is slower here.
- **Build and update.** A profile showed the map code itself at under 4% of the time: the rest was the garbage collector, started every few hundred microseconds because each put copies a path of nodes while the live heap is a few MiB. A `reduce` whose function cannot let an older version of the map be seen now updates one map in place (see [architecture](architecture.md)); the allocation for the 50,000 updates fell from 28.6 MiB to 0.09 MiB. Puts outside such a fold are unchanged.

## Hosted runner at `ee4096d`

The Benchmarks workflow at commit `ee4096d`, on a GitHub-hosted runner (AMD EPYC 7763, 2 logical CPUs, Go 1.23.12, Elixir 1.18.6 on OTP 27, medians of 7 runs), before the workloads timed their own phases.

Elixir starts a virtual machine in about 383 ms, which dominates its short runs, so its column is shown both whole and with that startup subtracted. Alchem and Go start in about 1.5 ms and are shown whole.

| Workload | Alchem | Go | Elixir | Elixir less startup | Alchem / Go |
| --- | --- | --- | --- | --- | --- |
| `hello` | 1.48 ms | 1.44 ms | 383.3 ms | n/a | 1.0 |
| `spawn` | 487.3 ms | 324.7 ms | 1508.8 ms | 1125.5 ms | 1.5 |
| `echo` | 105.3 ms | 62.2 ms | 545.8 ms | 162.6 ms | 1.7 |
| `compute` | 40.2 ms | 24.6 ms | 561.7 ms | 178.5 ms | 1.6 |
| `build` | 16.0 ms | 11.0 ms | 430.8 ms | 47.5 ms | 1.5 |
| `state` | 120.6 ms | 17.1 ms | 461.0 ms | 77.8 ms | 7.1 |
| `restart` | 164.6 ms | 39.0 ms | 3058.9 ms | 2675.7 ms | 4.2 |

Per operation, startup subtracted: a process costs 4.86 µs in Alchem, 3.23 µs in Go and 11.26 µs in Elixir; a round trip 519 ns, 303 ns and 812 ns; a crash-and-restart cycle 8.2 µs, 1.9 µs and 133.8 µs.

Peak memory: 100,000 processes take 309 MiB in Alchem, 270 MiB in Go and 358 MiB in Elixir; `state` takes 11.5 MiB, 5.2 MiB and 95.1 MiB; an idle program 2.6 MiB, 2.7 MiB and 73.4 MiB.

Reading these:

- Alchem is within 1.5 to 1.7 times Go on processes, messaging, computation and list building.
- `state` is the outlier against Go because Go mutates one map in place while Alchem keeps every version. Against Elixir, whose maps are also persistent, Alchem is faster as a whole program but about 1.5 times slower once Elixir's startup is subtracted (119 ms against 78 ms). The map is the clearest remaining place to improve.
- `restart` against Go is a full supervisor against a hand-written recover-and-respawn loop. Elixir's baseline used to poll `Supervisor.which_children`, a synchronous call to the supervisor, to find each replacement; each new worker now announces itself to the measuring process instead, so the figure reflects the restart.
- Alchem beats Elixir on every workload as a whole program, and on every workload except `state` with startup removed.

## Restart latency

How the restart path was improved, measured on the development container (4 logical CPUs, Intel Xeon 2.10GHz, Go 1.24.7, medians of 9 runs). The current hosted-runner results above have the three-way figures.

| Stage | Alchem per cycle | Go per cycle |
| --- | --- | --- |
| First measurement | 76.0 µs | 2.2 µs |
| Child lookup without the runtime lock | about 46 µs | |
| Polling loop yields with `Process.sleep(0)` | 15.6 µs | 2.5 µs |
| Stack frames resolved only when read | 9.9 µs | 2.3 µs |

The Go baseline is a hand-written supervisor: a goroutine that recovers a panic and starts a replacement, published through an atomic pointer. It has no restart policy, intensity limit, exit reason, link or monitor, so some gap is expected. The first figure, however, was mostly not restart work at all:

- A client polling `Supervisor.child` for the replacement took the runtime lock on every poll and starved the supervisor that needed the same lock to start the replacement. The lookup now reads an atomically published PID.
- The Alchem program had no way to yield between polls, so the polling process held a processor and every hand-off needed an operating-system thread wake-up. `Process.sleep(0)` now yields, as the Go baseline's loop does.
- Every failure resolved its call stack into source frames, including for workers whose report nobody reads. Frames are now resolved on demand.

A cycle is now about 4.3 times the Go baseline. What remains is the supervisor's own work: recording the exit, applying policy and restart intensity, and spawning through the full process lifecycle.

## Map updates

Maps were Go maps copied in full on every `put`, so keeping growing state in a map was quadratic, the same cliff `prepend` had. They are now persistent hash tries (see [architecture](architecture.md)). The `state` workload, added to expose this, on the development container:

| Implementation | `state` wall time |
| --- | --- |
| Alchem, copy on every update | 52.8 s |
| Alchem, persistent map | 157.5 ms |
| Go, mutable map updated in place | 13.3 ms |

The Go baseline mutates one map in place, which Alchem's immutable values cannot do, so the remaining factor of about 12 is the cost of keeping every earlier version valid: each update allocates new nodes along one path. Elixir, whose maps are also persistent, is the closer comparison; see the hosted-runner table above.

## Optimization rounds

Seven rounds of runtime and code-generation work followed the recording above. They were measured on the development container (4 logical CPUs, Intel Xeon 2.10GHz, Go 1.24.7, medians of 7 runs), so compare them with each other and with the Go column, not with the hosted-runner table. Elixir has not been re-measured since.

| Workload | Before | After round 1 | After round 2 | After round 3 | After rounds 4-5 | Go |
| --- | --- | --- | --- | --- | --- | --- |
| `spawn` wall time | 958.5 ms | 651.5 ms | 494.5 ms | 453.9 ms | 394.5 ms | 299.6 ms |
| `spawn` peak RSS | 397.1 MiB | 353.4 MiB | 338.9 MiB | 307.6 MiB | 306.4 MiB | 270.1 MiB |
| `echo` wall time | 343.0 ms | 191.9 ms | 178.8 ms | 116.6 ms | 127.1 ms | 86.2 ms |
| `echo` per round trip | 1.71 µs | 0.95 µs | 0.89 µs | 0.58 µs | 0.63 µs | 0.42 µs |
| `compute` wall time | n/a | n/a | n/a | 78.5 ms | 56.8 ms | 22.8 ms |
| 100,000-process budget test | 370.1 MiB | 341.5 MiB | 328.7 MiB | 304.3 MiB | 300.3 MiB | n/a |

Round 6, measured in a later 15-run session with Go re-measured alongside:

| Workload | After rounds 4-5 | After round 6 | Go |
| --- | --- | --- | --- |
| `spawn` wall time | 394.5 ms | 364.8 ms | 267.3 ms |
| `echo` wall time | 127.1 ms | 113.8 ms | 80.0 ms |
| `compute` wall time | 56.8 ms | 43.5 ms | 22.3 ms |

In the first table, the last two columns come from one 15-run session; the machine was busier than for the earlier columns, which is why Go and `echo` read slightly slower there. `compute` was added with round 4, so its first figure is the state after round 3.

Runtime micro-benchmarks (`go test -run '^$' -bench . -benchmem ./compiler/actor`):

| Benchmark | Before | After round 2 | After round 3 |
| --- | --- | --- | --- |
| Cancellation check per statement | 15 ns | 1 ns | 1 ns |
| Spawn and join | 1711 ns, 14 allocations | 1129 ns, 6 allocations | 1146 ns, 4-5 allocations |
| Request/reply round trip | 1410 ns, 10 allocations | 820 ns, 2 allocations | 564 ns, 0 allocations |
| Send and receive a map of lists | 1112 ns, 18 allocations | 854 ns, 11 allocations | 50 ns, 0 allocations |

- **Round 1** made the per-statement cancellation check an atomic load instead of a trip through the runtime lock, created monitor/link/ownership tables and the event channel on first use, skipped supervisor wakeups when no supervisor exists, stopped allocating a channel on every receive, and sent messages without lists or maps by assignment.
- **Round 2** finished processes in one critical section, created the sender wakeup channel only when a sender parks, gave uncontended sends a lock-free path, read a joined process's exit reason without the lock, and compiled `==`/`!=` on integers, booleans and strings to Go's operator instead of the reflective comparison.

- **Round 3** stopped copying messages (values are immutable, so sharing is unobservable), replaced the channel mailbox with a ring buffer that grows on demand, and gave each process one wake channel so a receive without a deadline is a plain channel wait rather than a multi-way select. Stop and done channels are now created only for waits that need them.

- **Round 4** replaced the global process table with an intrusive list, allocated a process and its mailbox together, and kept the call-depth limit on the process record.
- **Round 5** targeted pure computation: the call-depth decrement moved from a deferred call to the return path, the checked `+`, `-` and `*` gained inlinable fast paths, and function bodies check for cancellation once on entry instead of before every statement (see [runtime](runtime.md) for the exact cancellation points). A controlled comparison of 30 runs each put the entry-only check about 10% ahead on `compute`.

- **Round 6** stayed on computation. The Go compiler was not inlining the checked `+` and `-` because their failure path was being expanded into them; that path is now kept out of line. `map`, `filter` and `reduce` over a named function compile to a loop that calls the function directly. Functions that call nothing else carry no depth tracking, since they cannot recurse, block or repeat. Equality on tuples, flat lists and flat maps uses typed comparisons, leaving reflection only for collections nested in collections.

- **Round 7** changed the list representation. Lists were Go slices with the head first, so every `prepend` copied the whole list and building a list element by element was quadratic. They now store the head last behind a small claim counter (see [architecture](architecture.md)), which makes `prepend` amortized constant time while keeping tails, `take` and `drop` free of copying. The `build` workload, added to expose this, went from 3036 ms to 15.5 ms (Go, using `append`: 6.2 ms). The other workloads were unchanged within noise.

After seven rounds a process costs about 1.4 times a bare goroutine with a channel (was 3.6), a round trip about 1.4 times (was 4.4), the compute workload about 1.95 times Go (was about 3.4 when first measured), and list building about 2.5 times Go (was about 500 times). Ratios move by a tenth or so between sessions on shared hardware. What remains is mostly the cost of guarantees: recursive calls track depth, every arithmetic operation is overflow-checked, and every process carries an identity and lifecycle. The Go column moves a little between runs on shared hardware; each round was measured against a fresh Go run.

## Reading the hosted-runner results

- Startup and binary size match plain Go: an Alchem executable is a Go executable with a small embedded runtime. Elixir pays about 300 ms and 74 MiB to start the virtual machine.
- Creating and joining a process costs about 2.8 times a bare goroutine with a channel. An Alchem process also carries an identity, mailbox, link/monitor tables and lifecycle bookkeeping under one runtime lock. Per process it is slightly cheaper in time than Elixir here, but uses more memory (473 MiB against 357 MiB for 100,000).
- A round trip costs about 4.5 times the Go baseline and about twice Elixir's once startup is subtracted. Each send deep-copies its message, and every statement checks for cancellation.
- Per-operation figures subtract each implementation's own startup time, so whole-program wall time favours Alchem over Elixir more than the per-operation figures do.
