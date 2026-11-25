# Files, directories, the environment and external programs

`File`, `System`, `Path.expand/absname/wildcard`, the `IO` functions on
devices and files, written in Alchem (`library/File.alc`, `System.alc`,
`Path.alc`, `IO.alc`, `Sys.alc`) on a handful of primitives the compiler
emits as raw Linux x86-64 system calls. The pinned runtime does this work
with Go's `os`, `os/exec`, `bufio` and `path/filepath`; the library follows
those call by call, so results, error texts (`open x: no such file or
directory`, `enoent`, `rename a b: file exists`, `unlinkat ./d/e/x:
permission denied`, `fork/exec ./f: exec format error`) and the position of
a file's descriptor after a buffered read are the pinned ones.
`harness/system.py` runs 76 programs with the pinned compiler's status,
output and failure trace frozen in, each in an empty directory of its own.

## The primitives: `Sys`

`Sys.name(...)` is compiled by `native-system.alc` only inside the appended
library modules and, in a bundle the build has marked
(`scripts/bundle-alchem.py`, `marked`), the modules whose names start with
`Alchem`: `alchem`'s own (`tools/`) and the gates' probes. `alchem` marks no
program, so in a program `Sys` is an ordinary name whatever its modules are
called, and the pinned library has no such module. All arguments
and results are integers except where said.

| Primitive | What it does |
| --- | --- |
| `Sys.call(number, a, b, c, d, e, f)` | The system call `number` with up to six arguments; the kernel's result as it is (a negative error number on failure) |
| `Sys.addr(string)` | The address of the string's first byte |
| `Sys.text(address, count)` | A fresh string of `count` bytes from memory (exit 71 when the arena is full) |
| `Sys.len(address)` | The number of bytes before the first zero byte |
| `Sys.peek(address)`, `Sys.byte(address)` | The 8 bytes, or the one byte, at an address |
| `Sys.poke(address, value)` | Stores 8 bytes; gives the value |
| `Sys.copy(to, from, count)` | Copies bytes upward; gives the address after the last written |
| `Sys.find(address, count, byte)` | The index of the first such byte, or -1 |
| `Sys.same(a, b, count)` | 1 when the two runs of bytes are equal |
| `Sys.stack()` | The initial stack pointer (R14): argc, argv, 0, envp, 0 |
| `Sys.top()`, `Sys.limit()` | Where the free part of the arena starts and ends (R12, R13) |
| `Sys.errno(number)` | Go's text for an error number, from the file runtime (`spec/file-read-x86_64.s`, entry 4); on Windows Windows' text for the error behind it (`spec/windows.md`) |
| `Sys.windows()` | 1 in a program for Windows, else 0: a constant of the compiler (`nc_win()`, `spec/windows.md`) |

`library/Sys.alc` holds what the library shares, written on these: system
calls on paths (a path with a zero byte is `invalid argument`, as Go has
it), `os.Remove`, `os.MkdirAll`, `os.RemoveAll`, `os.ReadDir`, the walk of
`File.cp_r`, the buffer of an open file, standard input, the environment,
`exec.LookPath` and starting a program. Its functions are not part of the
pinned library; a program cannot call them.

### The state block

The word that ends `argv` (always zero at start, and read by nothing: the
arguments are counted by `argc`) holds, once the library needs it, the
address of four mapped pages: 0 the environment (0: the initial one), 8
its length, 16 its room, 24 where the monotonic clock started, 32
collections counted, 40 and 48 bytes of standard input read ahead, 56/64/72
the pad (a mapped buffer that grows and is reused: files, command output
and lines are gathered there and copied to the arena once), 512 small
results, 496 the table of the CRC-32 (`Sys.crc`), 1024 a stat record, 4096 a buffer of 12288 bytes.

### The environment

`System.put_env` needs an environment that can change. At its first use
(put_env, or a command started) the initial `envp` is copied into mapped
memory as Go's `syscall.copyenv` keeps it: an entry whose name an earlier
entry has, or that is empty, is left out. put_env replaces the entry of
the name or appends one (`could not set NAME: setenv: invalid argument`
for an empty name, a name with `=`, or a zero byte). The compiler's own
`System.get_env` reads the copy once it exists (`spec/library-x86_64.s`),
and commands are started with it, after `exec`'s own removal of repeated
names when `env:` or `cd:` adds entries (`PWD` for `cd:`).

## What is written

- **File**: `exists?`, `exists`, `dir?`, `regular?`, `rm`, `rmdir`, `rm!`,
  `rm_rf`, `mkdir`, `mkdir_p`, `rename`, `ls`, `list`, `ls!`, `stat`,
  `lstat`, `ln`, `ln_s`, `chmod`, `touch`, `cwd`, `cwd!`, `cp`, `cp_r`,
  `read!`, `read_binary`, `read_binary!`, `write!`, `write/3`, `open/2`,
  `open/3`, `close`, `stream!/1`, `stream!/2`. (`read`, `write/2`, `append`
  and `remove` are machine code, as before.)
- **System**: `cmd/2`, `cmd/3` (`cd:`, `env:`, `stderr_to_stdout:`),
  `find_executable`, `put_env`, `env`, `user_home`, `tmp_dir`, `tmp_dir!`,
  `cwd!`, `monotonic_time/0,1`, `system_time/1`, `os_time/1`,
  `convert_time_unit`, `memory`, `collect_garbage`.
- **Path**: `expand`, `absname` (`os.Getwd`: `$PWD` when it names the
  working directory, else getcwd), `wildcard` (`filepath.Glob` and `Match`
  with classes, ranges, escapes and runes).
- **IO**: `puts(:stdio | :stderr, text)`, `puts(file, text)`,
  `write(file, text)`, `read(:line | :eof | count)`, `read(:stdio, how)`,
  `read(file, :line | :eof | count)`, `binread(count)`,
  `binread(file, count)`, `gets`, `stream`.

A command is started with fork, the child's descriptors arranged as Go
arranges them (standard input from `/dev/null`, a pipe for the output, an
error pipe closed on exec that reports why the program could not start),
and execve; its output is read to the end, then it is waited for. A status
ended by a signal is -1.

A file opened with `File.open` is the pinned type `file` (`inspect` gives
`#fileHandle<>`); `File.stat` gives `%File.Stat{...}`. For these the
compiler lets the appended module `AlchemTypes`, and only it, declare a
struct with a dotted or a lowercase name (`struct File.Stat`, `struct
file`), finds `Module.Name` there when the program has no such module, and
reads the type word `file`. A file's buffer is filled exactly as
`bufio.Reader` fills its 4096 bytes, so a write after a read lands where it
lands upstream.

`IO.puts(file, text)` and `IO.write(file, text)` give a result where the
value is used; as the statement that ends a `fn` or a `for` body they are
run for their effect and the body gives `{}`, as upstream has it for every
call whose name also has a form without a value.

## Also changed in the compiler

- `0x1F`, `0o17`, `0b101` (with `_` between digits) are integers; the
  pinned range and spelling rules hold (`File.chmod(path, 0o600)`).
- A failure inside a library function written in Alchem is traced as the
  pinned runtime traces it: at the call that entered the library, and
  without the library's own calls. Every such call stores its position in
  its frame (RBP-132) and `spec/trace-x86_64.s` skips frames of modules
  named `Alchem...`. This holds for every library module, not only these.
  A reference to a library function (`&Enum.max/1`) stores the position of
  its `&` in the frame of the function value it makes.
- `File.` and `System.` calls the compiler has no code for fall back to
  the library, as `Enum` does; `IO.puts`/`IO.write` with more than one
  argument are library calls.
- `scripts/generate-prelude.py` (the rules below are now held in one index
  and applied in one reading of the program, `alchem-library-profile.md`,
  "How the library is held and chosen"): an
  entry marked `exact` (`#: puts/2 exact`) is appended only for a call with
  its number of arguments, so `IO.puts(text)` does not bring
  `IO.puts(device, text)` along; a function that takes a library type of
  another module needs that module mentioned; a struct comes with the
  functions of other modules that name it.
- `IO.read_line` and `IO.read_all` take first the bytes the library read
  ahead of a character that turned out to be none.

## Differences from upstream that remain

- **Port** is not written. `Port.open(program, arguments, owner)` delivers
  the program's output as messages to a process (`pid[PortEvent]`), and
  every other Port function is about such a port; the native compiler has
  no processes, mailboxes or `receive` to deliver to. The pieces a port
  needs below that (pipes, fork, exec, wait, kill through `Sys.call`) are
  here.
- `File.stream!` gives a stream (`alchem-sets-streams.md`) that opens the
  file when its first element is asked for, as upstream, and then reads all
  of it into the arena at once; upstream reads a line or a piece at a time,
  so a file past the arena fails here. `IO.stream` reads a line each time
  one is asked for.
- Every value comes from the arena (16 GiB reserved lazily,
  `alchem-tail-calls.md`), which is never given back: a file or a
  command's output larger than what is left ends the program with status
  71 (upstream: 16 MiB for `File.read_binary`, no limit for the rest). Working buffers are mapped memory outside the
  arena.
- `System.monotonic_time` counts from its first call: the entry stub does
  not record when the program started. `System.memory` reports the arena
  (in_use: what is taken of it, with the state block; held: the pages that
  takes; idle: the rest of held), `stacks: 0` and the calls of
  `collect_garbage` as collections; the pinned figures are the Go
  runtime's.
- `System.convert_time_unit` fails with `integer overflow` where the
  product does not fit; Go's multiplication wraps silently.
- `System.cmd` takes its arguments as a list, not any enumerable.
- Standard input is read a byte at a time, as `IO.read_line` already was,
  so nothing is taken that was not asked for; upstream buffers 64 KiB,
  which a program started later by `System.cmd` does not see there and
  does see here. Text that is not UTF-8 ends `IO.read_line`/`read_all`
  with status 73 (their existing behaviour) where upstream fails with
  `input is not valid UTF-8`.
- The library's functions that upstream types as having no value
  (`File.write!`, `System.put_env`, `IO.puts(:stderr, text)`) give `{}`,
  so a binding of one is accepted where upstream rejects it.
- Recursion in the library is bounded by the 100000 calls a program may
  nest, since the compiler does not turn calls in tail position into
  loops: a directory tree or a pattern nested that deep, or a line of
  standard input of a hundred million bytes, ends with `call depth
  exceeded`.
