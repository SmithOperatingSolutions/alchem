# Processes

`Process`, `Task`, `Task.Supervisor`, `Agent`, `Server`, `Supervisor`,
`DynamicSupervisor`, `Registry`, `Port` and the receive assertions of the
pinned compiler (`compiler/actor/*.go`, `docs/runtime.md`), in the
self-hosted compiler. `harness/processes.py` holds 117 programs with the
pinned compiler's status, output and failure trace frozen in, and 22 it
rejects. The pinned references' examples for these modules all agree: the
two of `processes` in the syntax reference and the 103 of `Process`,
`Task`, `Task.Supervisor`, `Agent`, `Server`, `Supervisor`,
`DynamicSupervisor`, `Registry` and `Port` in the library reference, with
the four receive assertions of `Testing`.

A native program is one thread with no library under it. Its processes are
coroutines of that thread: each has a stack of its own, and one runs until
it waits. Everything about them is written in Alchem (`library/Process.alc`,
`Task.alc`, `Agent.alc`, `Server.alc`, `Supervisor.alc`,
`DynamicSupervisor.alc`, `Registry.alc`, `Port.alc`), a port of the pinned
runtime function by function, over the system calls of `alchem-system.md`
and five operations the compiler gives the library
(`implementations/alchem/native-processes.alc`, reference in
`spec/processes-x86_64.s`). A program that mentions none of these modules
holds none of this.

## What is built

- **Process**: `self`, `spawn`, `send`, `receive`, `await`, `stop`, `alive`,
  `id`, `count`, `sleep`, `crash`, `report`, `loop`, `monitor`, `demonitor`,
  `link`, `unlink`, `trap_exits`, `event`, `register`, `unregister`,
  `whereis`, `send_after` (to a process or a name), `cancel_timer`. Mailboxes
  are bounded and first in, first out; a full one makes the sender wait its
  milliseconds. Exit reasons are the pinned ones: `normal`, `exit:N`,
  `shutdown`, the message of a failure (`error: normal` and `error:
  shutdown` for a failure so named), `uncaught throw`, `linked: reason`.
- **Types**: `pid[t]`, `task[a]`, `agent[s]`, `server[q, r]`,
  `supervisor[t]`, `registry[k, v]`, `dynamic_supervisor`, `port`,
  `PortEvent` and `Port.Info`. `inspect` writes `#PID<>`, `#Task<>`,
  `#Agent<>`, `#Server<>`, `#Supervisor<>`, `#Registry<>`,
  `#DynamicSupervisor<>` and `#portHandle<>`; none of them compares.
- **Task**: `async`, `start`, `start_link`, `await/1,2`, `await_many/1,2`,
  `yield`, `shutdown`, `async_stream/2,3` (results in input order, at most
  the given number of tasks at a time, the rest stopped when the stream is
  read no further). **Task.Supervisor**: `start_link/0,1`, `async`,
  `async_nolink`, `start_child`, `children`, `terminate_child`.
- **Agent**: `start/1,2`, `start_link/1,2` (with `name:`), `get`, `update`,
  `get_and_update`, `cast` (each also by name), `stop`, `whereis`.
- **Server**: `start`, `start_supervised`, `call`, `cast`, `stop`, `alive`,
  `await`, `restarts`, `self`, `continue`, `register`, `whereis`,
  `send_after`, `monitor`, `mailbox`.
- **Supervisor**: `start`, `start_link`, `child`, `children`, `restarts`,
  `alive`, `stop`, `await`, `server`; the three strategies, the three
  policies, restart intensity over a window. **DynamicSupervisor**:
  `start_link/0,1`, `start_child/2,3`, `start_server`, `terminate_child`,
  `which_children`, `count_children`, `restarts`, `stop`, `alive`.
- **Registry**: all seventeen functions.
- **Port**: `open/3,4` (`mode:`, `stderr:`, `packet:`), `command`, `close`,
  `kill`, `os_pid`, `info`, `monitor`. The program is started as Go's
  `exec.Command` starts it (the errors are Go's: `exec: "name": executable
  file not found in $PATH`, `fork/exec path: reason`), interrupted when its
  owner or the process that reads it ends, and killed half a second later
  if it has not gone.
- **Receive assertions**: `assert_receive`, `refute_receive`,
  `assert_received` and `refute_received`, with a guard, a wait and a
  message of one's own; a failure shows the pattern, the pinned names and
  the mailbox as the pinned compiler shows them.
- **The program's end**: when `main` returns or fails every other process
  is asked to stop and awaited (their `after` blocks run) before the status
  or the failure is given. A main process stopped by a linked failure
  writes that failure, the trace of the process that failed included, and
  ends with status 2. `System.stop(status)` stops the main process in that
  way; `System.halt` leaves at once.

## How it runs

**The scheduler** (`Process._sched`, `_pick`, `_wait`). One process runs.
It gives way only where the pinned runtime blocks: `receive`, a `send` to a
full mailbox, `sleep`, `await`, `event`, a call of a task, agent or server,
a supervisor's wait, a port's read, and at its end. The processes ready to
run wait in a queue and are taken in the order they became ready; one
readied by a message or a stop goes to the back. A wait with a time is kept
in a list; before a process is picked, the processes whose time has come
are made ready, those of the earliest time first and no others in that
turn, so that what an earlier timer sets off runs before a later one even
when the program finds both late. With nothing ready the thread sleeps
(`nanosleep`) until the earliest time. With nothing ready and nothing timed
the program ends as the pinned one does when every goroutine is asleep.

**Call depth.** A process counts its own calls (R15 is kept and taken by
the switch) and starts its function as upstream does, one call deep; the
library's functions are no calls of the program (`alchem-tail-calls.md`),
so the function of an agent, a server's handler and a supervisor's child
nest as deep as upstream lets them, and a process that calls itself in
return position for every message runs for any number of them (a million
in the gate).

**A process** is a record of 384 bytes (`library/Process.alc` lists it) in
blocks mapped for the purpose, never given back: a handle may outlive its
process and still answer `Process.id`, `await` and `report`. Its stack is a
mapping of 256 MiB reserved lazily, or an eighth of that, and of that again,
down to 256 KiB when the system does not grant it (an eighth and not a half,
so that under a limit on the address space the stacks to come find room
too: with halves a dozen processes used up 3 GiB), reused once the process
is over. A switch
(`Process.__switch`) keeps and takes five words: the stack pointer, the
frame, the count of active calls (R15), the innermost handler of a `try`
(the word at R14-16) and the stack limit (R14-8). The arena (R12, R13) is
the program's and is not switched: a message is the word of its value, and
the receiver gets the same value, as upstream.

**The end of a process.** A process's function runs under `try ... rescue
... after` in the library (`Process._run`): the rescue arm's guard notes the
message of a failure and declines, so the failure passes on with everything
that failed still on the stack; the after block then ends the process. For
a failure it first has the trace written: the program forks, the copy
points standard error at a pipe and lets the failure pass on, which writes
the place, the reason and the calls exactly as for a program that failed
(`spec/trace-x86_64.s`, untouched), and the process keeps the text: it is
what `Process.report` gives and what a main process stopped through a link
writes. A request to stop is a `throw` of `Process.Exit`, raised where the
stopped process next looks (`Process._check`: every function of these
modules, every wait): rescue arms let it pass, `after` blocks run, nothing
of the program catches it.

**The main process** runs under a handler of the entry code
(`ac_entry`): `Process._close` runs when `main` returns and when it fails,
after which a failure of its own passes on to be written as always. The
main process looks before each of its statements whether it was asked to
stop (`ac_statement`: one compare of the word at R14-56 per statement of
`main`, in programs with processes).

**Types the program only annotates.** `Process.self(8)` takes its message
type from the annotation, `Process.whereis` finds a name only for the type
it was registered with, `Server.continue` and `Process.send_after` to a
name check the request's type, and a `receive` that ran out of time gives
the type's zero value. For the calls listed in `ac_hooks` the compiler
stores, just before the call, the address of the type as a string of its
bytes at R14-48 (0 when the type is not settled there); the library
compares such strings and builds zero values from them (`Process._zero`).

**Two things of function values came with this**, since examples of these
modules need them: several parameters of a `fn` may be `_` (`fn key, _, _ ->
... end`), and a `fn` whose every way out raises has the result `tuple[]`,
as upstream (`Task.start(fn -> raise("x") end)`).

**Typing.** The process types are structs of the library whose names the
compiler takes in lowercase (`ac_typeword`), with a field of function type
so that `==` is refused. The pinned compiler types the state a server, an
agent, a loop or a supervised server starts from by the function given with
it, so `Server.start([], handler)` is accepted; for functions of these
modules a call whose result came out whole is taken although an argument
needed a type a later one gave (`ac_settled`). `Task.Supervisor.name` is
looked up as `Supervisor.name` (`ac_module`).

**Receive assertions** are rewritten in the program's text before it is
compiled (`ac_receives`), as the pinned compiler rewrites its tree: on the
line the statement starts on,
`pattern = Process.assert_receive(pid, wait, fn m -> case m do pattern when guard -> true _ -> false end end, fn m -> inspect(m) end, "pattern", [pins], message, columns)`,
followed by as many line ends as the statement held, so every line keeps
its number. A statement is taken as one when the word starts its line.

**`needs`.** `scripts/check-library-needs.py library/Process.alc ...` reports
an entry of these files that calls a library function its `needs` does not
name; it changes nothing.

## Words the program and the library share

| Where | What |
| --- | --- |
| R14-48 | the type of the call that follows (`ac_hooks`), 0 for none |
| R14-56 | set once the main process was asked to stop |
| `Sys.state() + 96` | the block the processes hang from (`library/Process.alc`) |

## Where a run-to-block scheduler decides

Upstream's goroutines run on several processors, so these are not fixed
there; native programs always give the first outcome named.

- Processes started or woken one after another run in that order, each
  until it waits. `spawn(a); spawn(b)` followed by a wait runs all of `a`
  up to its first wait before `b`; upstream's order varies from run to run.
- A process that sends does not give way: the receiver runs when the
  sender next waits. A sender freed by a `receive` runs after the receiver
  waits again.
- A process asked to stop has ended by the time the one that asked has
  waited once (`Process.count()` after stopping tasks counts them out;
  upstream may still count them).
- `Server.call` with a wait of 0 may be answered: the server runs before
  the caller's time is looked at.

## Differences that remain

- **Memory.** (As it was; values and the records of processes are given back now, `alchem-memory.md`.) Nothing is reclaimed: every value of every process, messages
  included, comes from the program's one arena (16 GiB reserved, paid for
  as it is touched, `alchem-tail-calls.md`). A call of a server whose
  handler returns a tuple of two integers takes 40 bytes of it and a
  received integer 24, so the arena holds some 430 million such calls or
  715 million receives, and a long-lived program grows by that much;
  upstream collects. Process records, mailbox cells and stacks are outside
  the arena and are reused. An arena per process, given back when the
  process ends or reset on each turn of its loop, would need every value
  that passes between processes copied: messages (by a routine the compiler
  would make per message type, as it makes equality), and also the function
  values this library itself passes (an agent's operations, the functions of
  timers, a task's result, a server's state on restart), whose captured
  values have no type at run time. The switch itself would only keep two
  more words (R12, R13).
- **One thread.** A system call that blocks holds every process up:
  `IO.read_line` and `IO.read_all` waiting for input (`IO.read`, `IO.gets`
  and the library's other reads of standard input give way to the other
  processes until there is something to read: `alchem-nodes.md`), `System.cmd`, a
  `Port.command` to a program that does not read (once the pipe holds 64
  KiB), a file on a slow device. A process that computes without waiting
  holds the others up for as long, timers included, and the two seconds the
  pinned runtime gives the others to stop at the program's end are not
  counted (`<runtime>: shutdown deadline exceeded` is never written):
  preempting a process needs a signal handler that switches stacks, which
  this runtime does not have.
- **A port's output is polled**: the process that reads it looks every
  millisecond while nothing has come (`ppoll` with no wait), so an idle
  port wakes the program a thousand times a second and a line arrives up
  to a millisecond late.
- **A process that stops itself.** After `Process.stop` of itself, or a
  link to a process that already failed, upstream ends the process at the
  next function it enters and the main process before its next statement.
  Natively the main process ends before its next statement too; any other
  process at its next call into these modules.
- **`System.stop` in a process other than the main one**: upstream lets
  that process go on until the program has ended around it; natively it
  waits there.
- **Failures without calls.** `process mailbox type already fixed` is
  written with the calls that led to it; upstream writes only its first
  line. `restart_intensity`, `only the mailbox owner may receive` and the
  others agree.
- **Deadlock.** When every process waits for ever the program writes
  `fatal error: all goroutines are asleep - deadlock!` and ends with status
  2, as upstream; Go's dump of its goroutines does not follow.
- **The value beside `false`** of a `receive` that ran out of time is the
  type's zero value for integers, booleans, floats, strings, atoms, lists,
  maps, sets, tuples, structs and ranges, and for a sum type a value that
  is shown as `nil` and equal only to itself, as upstream (the compiler
  makes it where the type has a declaration: `alchem-failures.md`); `none`
  for an option and `error` of the zero for a result, where upstream
  writes `nil`.
- **Types that are not checked.** A name given by `Supervisor.server` is
  found by `Server.whereis` for any request and reply type, and the
  functions that take an agent's name do not compare the state's type: the
  types of a function argument are not settled where the call is made, and
  the library has no way to build a `server[q, r]` type from its parts.
  (Whether a message type may be sent at all is checked where the type is
  written: `alchem-nodes.md`.)
- **Registries** give their entries in the order they were made; upstream
  in the order of a Go map, which varies. `partitions:` is kept and has no
  effect.
- **Receive assertions**: the pattern is shown as written, where upstream
  writes it out from its tree (the same text unless the spacing is
  unusual). `--receive-timeout` does not exist natively; the wait is 100
  milliseconds unless the statement gives one.
- **Not built**: `Task.async_stream/2` runs 16 tasks at a time, not one
  per processor. (`Node`, `Stream.publish` and the handles of other nodes'
  processes are in `alchem-nodes.md`.)
