# Windows x64

`alchem build -target windows/amd64` is to make a program for Windows that
does what the pinned compiler's `-target windows/amd64` program does. This
file is the design and the state of the port (issues #75, #77).

## One source, three compilers

As for ARM64 (spec/arm64.md), the target is a constant of the build:
`nc_win()` (native-windows.alc) is 0 in the source and 1 in the compiler
`scripts/build-windows.py` makes. It builds two:

- `build/dev/alchem-compiler-windows-cross`: the source with `nc_win()` 1,
  compiled by A2. A Linux program that makes Windows programs.
- `build/dev/alchem-compiler-windows.exe`: the same source compiled by the
  cross compiler. On Windows it must make itself again byte for byte.

The Linux compiler takes the other branch everywhere, so its output stays
byte for byte what it was.

## The code is the Linux code

A Windows program is the x86-64 image the Linux compiler makes, at the
same addresses, with one change: every system call instruction (`syscall`,
0F 05) is `ud2` (0F 0B), which has the same length. Nothing else moves, so
every offset, jump and fixed address of the Linux image holds.

- An emitter writes the second byte of a system call as `nc_sc()`.
- A runtime assembled from `spec/*-x86_64.s` is assembled a second time
  with `syscall` defined as a macro for `ud2`
  (scripts/windows_sites.py); the offsets where the two differ go into
  the generated literal as `nc_os(code, sites)`, which patches them in the
  Windows compiler and returns the code as it is otherwise.

## The PE file

ImageBase is 0x380000, and nothing is relocated (no `DYNAMIC_BASE`):

| RVA | Address | Section | |
| --- | --- | --- | --- |
| 0 | 0x380000 | headers | |
| 0x1000 | 0x381000 | `.wtext`, RX | the Windows layer's code, the import tables |
| 0x10000 | 0x390000 | `.wdata`, RW | its data, the import address table |
| 0x80000 | 0x400000 | `.text`, RX | the image: the ELF header and code of Linux |

The bytes before the image are a constant, `nw_prefix()`
(native-windows-data.alc, made by scripts/generate-windows-runtime.py);
`nw_pe` fills in the three header fields that depend on the image's size.
The image keeps its 128-byte ELF header, so the entry stays at 0x400080,
the words at 0x400420 to 0x400478 and the function table at 0x400480.

## The Windows layer

`spec/windows-x86_64.s`, about 3 KiB of code, and `spec/windows-layer.c`,
which the assembly gives each call first (`layer_call`) and which makes the
calls written in C, or gives the call back for the assembly to make.
scripts/generate-windows-runtime.py compiles the C freestanding (no C
library, no red zone, no SSE; Windows functions are `ms_abi` pointers in
the import address table) and links the two with a linker script that puts
code, read-only data and the import tables in `.wtext` and data, the import
address table and zeroed data in `.wdata`. It writes the import tables
itself, from every `imp_NAME` the two files use (`DLLS` gives the DLL of
those not in KERNEL32).

- **Entry.** The PE entry adds a vectored exception handler, keeps the
  stack Windows started the thread with, builds a Linux initial stack and
  jumps to 0x400080. The arguments come from `GetCommandLineW`, split as
  Go's `os` package splits it on Windows, and the environment from
  `GetEnvironmentStringsW`, both in UTF-8; an empty command line gives
  the program's path as the one argument (`GetModuleFileNameW`), as Go's
  `os.Args` there. 64 KiB of stack lie below that
  block, for the exception records Windows pushes there until the program
  has switched to its own stack.
- **System calls.** `ud2` raises an illegal-instruction exception. The
  handler finds `0F 0B` at RIP, makes the Linux call in RAX with kernel32
  on the Windows stack, and continues after it with the result in RAX,
  RCX the address after the call and R11 the flags, every other register
  kept: the Linux contract. A call it does not make writes
  `E_RUNTIME_WINDOWS: unsupported system call 0x...` to standard error and
  returns -ENOSYS.
- **Memory.** `mmap` of up to 4 GiB is reserved and committed; a larger
  one (the 16 GiB arena, `MAP_NORESERVE`) is only reserved, and the handler
  commits 64 KiB around an address when touching it faults. A buffer the
  kernel reads or writes for a call is committed first, since Windows does
  not fault it in for the kernel as Linux does.
- **Faults.** The SIGSEGV handler `rt_sigaction` installs (`zf_guard`) is
  called as Linux would, with the address in its siginfo and RIP in its
  ucontext; if it moves RIP the program goes on there.

- **Descriptors.** A table of 1024 handles; 0 to 2 are the standard
  handles until a handle is set there, and a new descriptor is the lowest
  free from 3. A failed call gives the Linux errno that stands for the
  Windows error (`errno_map`; any other is EIO), and keeps the Windows
  error (`last_error`).
- **Paths** are UTF-8, given to the `...W` calls in UTF-16; `/dev/null` is
  `NUL`. A directory opens with `FILE_FLAG_BACKUP_SEMANTICS`, and a file
  created without write permission is read-only.

The calls made so far:

- memory and signals: `mmap`, `munmap`, `madvise` (`MADV_DONTNEED` and
  `MADV_FREE` decommit), `rt_sigaction`, `rt_sigprocmask`, `sigaltstack`;
- descriptors: `read`, `write`, `open`, `openat`, `close`, `lseek`,
  `fstat`, `stat`, `lstat`, `newfstatat`;
- the file system: `getcwd`, `chdir`, `mkdir`, `mkdirat`, `rmdir`,
  `unlink`, `unlinkat`, `rename`, `renameat`, `renameat2`;
- time and the process: `clock_gettime`, `nanosleep`, `getrandom`,
  `getpid`, `exit`, `exit_group`, and `ppoll` (no descriptors: a sleep;
  sockets: `WSAPoll`; any other descriptor is taken as ready);
- in C: `pread64` and `pwrite64` (an offset read or write, the position
  kept), `ftruncate`, `fsync`, `fdatasync`, `getdents64`
  (`FileFullDirectoryInfo`), `link`, `symlink`, `chmod` and `fchmodat`
  (read-only or not, as Go's os.Chmod), `memfd_create` (a temporary file
  deleted on close), `mremap` (a new mapping and a copy), `mmap` of a file
  (its bytes read into new memory: the library maps files only privately
  to read), `dup`, `dup2`, `dup3` and `fcntl`, and the `*at` calls on a
  directory descriptor: the path is joined to the directory's
  (`GetFinalPathNameByHandleW`) and the call made as from the working
  directory, the program's registers put back after (`layer_restore`);
- sockets, in C over Winsock: `socket`, `bind`, `listen`, `accept`,
  `accept4`, `connect`, `sendto`, `recvfrom`, `shutdown`, `getsockname`,
  `getpeername`, `setsockopt`, `getsockopt`, and `read`, `write`, `close`,
  `fstat`, `fcntl` and `ioctl` on a socket. Addresses are laid out alike
  but for AF_INET6 (10, 23); options and errors are mapped to Winsock's,
  `SO_REUSEADDR` is not set (Go sets nothing on a Windows listener), and
  a non-blocking connect's `WSAEWOULDBLOCK` is `EINPROGRESS`.

## Processes

- **Starting a program** is a pseudo call (1000104, `sys_spawn`) in place
  of fork and execve: `CreateProcessW` with the command line Go's
  `syscall.EscapeArg` makes of the arguments, the environment block of
  `os/exec` (each name once, its last value, in either case; `SYSTEMROOT`
  kept), the directory, and pipes whose child ends alone are inherited
  (`System.cmd`: output, and errors with it or where the program's go;
  `Port`: input too, errors with the output, to `NUL` or where the
  program's go; and for `alchem.exe`, errors to a file, an end at a
  deadline, or the program's own three handles). `wait4` waits on the process (with `WNOHANG`, not), and
  gives the whole 32-bit exit code in a word, as Go's `ExitCode` has it
  there; `kill` with SIGKILL is `TerminateProcess` (exit code 1, as Go's
  `Process.Kill`), and Windows has no other signal to send. `pipe2` is an
  anonymous pipe of 1 MiB.
- **Finding it** is Go's `exec.LookPath` for Windows (`Sys._wwhich`):
  `PATHEXT`, the working directory first and refused when it is what is
  found (`ErrDot`), `filepath.SplitList`'s quotes, and `executable file
  not found in %PATH%`; `exec.Command`'s rules for a name with a separator
  or an absolute one (`Sys._wcommand`).
- **ppoll** waits on sockets with `WSAPoll` and looks at pipes with
  `PeekNamedPipe`, each millisecond on the high-resolution timer while a
  pipe is waited for, so a `Port` does not hold the one thread up.
- **A copy of the program.** The library forks for one thing: a failing
  process has a copy of the program fail in earnest, its errors on a pipe,
  for the trace. `fork` here returns 0 and the program goes on as the
  copy, with the parent kept: its CONTEXT, the descriptor table (a close
  only leaves the table; what the copy opens is closed after), the stack
  it runs on from just below its pointer up (copied whole: Windows writes
  its exception records on the stack that faults), and every other page of
  the program's memory, made read-only and copied the first time the copy
  writes to it (`copy_fault`, and `commit_range` for what the layer
  writes). Pages the copy commits are decommitted after, as free memory
  must be zero. When the copy exits, the layer puts that back on a stack of
  its own (`copy_resume`: Windows' records of the exception lie on the
  program's) and resumes the parent with `RtlRestoreContext`, its fork
  giving the copy's number, which `wait4` reaps. The memory is the
  program's regions: what `mmap` and the layer map for it, and the block
  of the initial stack (1024 at most).

## The library's view of Windows

What Go's packages do differently on Windows, the library does when
`Sys.windows()` is 1: a primitive the compiler makes a constant
(`nc_win()`), so the Linux and macOS programs have nothing of it but a
branch never taken.

- **Paths.** `library/Path.alc` ends in Go's path/filepath for Windows
  (`_wvlen` volumeNameLen, `_wabs` IsAbs, `_wclean` Clean with
  postClean, `_wjoin` Join, `_wbase`, `_wdir`, `_wext`, `_wrel` Rel with
  parts compared in either case, `_wtype` pathType). The Path functions use
  them there and give back `/` for `\` where the pinned library does
  (`filepath.ToSlash`). `Path.expand`, `absname` and `Sys.abs` make a path
  whole with `GetFullPathNameW` (pseudo call 1000102).
- **Directories.** `File.cwd` is `GetCurrentDirectoryW` with `/` (no
  `PWD`), `System.user_home` is `USERPROFILE`, `System.tmp_dir` is
  `GetTempPathW` without its last `\` (pseudo call 1000103).
- **The environment.** `System.get_env` finds a name in either case
  (ASCII), as `GetEnvironmentVariableW` does: the Windows compiler's
  `na_get_env` is assembled with `WINDOWS` defined
  (scripts/generate-library-runtime.py writes both).
- **Errors.** The layer keeps, for each errno it gives, the Windows error
  behind it; `Sys.errno` and the file runtime's messages are then Windows'
  text for it (pseudo call 1000101: `FormatMessageW` in US English, as
  Go's `syscall.Errno.Error`; `winapi error #N` when Windows has none).
  An errno the library makes itself has Go's invented text, but `ENOENT`
  and `ENOTDIR`, which Go's syscall names for `ERROR_FILE_NOT_FOUND` and
  `ERROR_PATH_NOT_FOUND`. The file runtime of the Windows compiler is
  assembled with `WINDOWS` defined to ask for it
  (scripts/generate-file-read-runtime.py). A socket error names the call
  Go's net makes on Windows (`connectex`, `wsarecv`, `wsasend`,
  `acceptex`, `wsasendto`: `TCP._sysop`).

## alchem.exe

`scripts/build-alchem.py --windows --compiler build/dev/alchem-compiler-windows-cross`
builds the `alchem` command (tools/alchem.alc) with the compiler that makes
Windows programs inside, as a Windows program: its `test`, `run`, `build`,
`check` and `new` work on Windows, and take `-target windows/amd64` (each
`alchem` builds for the system it runs on, as the one for macOS does). There
it names what it builds as the pinned command does (`.exe`), and starts
programs without `/bin/sh` (`wexec`, the layer's spawn): `run` gives the
program its own input, output and errors; a fixture's input is `NUL`, its
errors go to a file and it is ended at its deadline (a timer of the timer
queue calls `TerminateProcess`). CI runs its `test`, `build` and `run` on
Windows.

## Checking

`scripts/run-windows PROGRAM.exe` runs a program under Wine with a seccomp
filter that ends it (SIGSYS) at a system call made from its image. Under
Wine a `syscall` left in the image would make a Linux call and seem to
work; on Windows it would be taken for a Windows one. Any other PE file
runs without the filter.

The reference is the pinned compiler's own windows/amd64 program
(`alchem build -target windows/amd64`), which also runs under Wine. Under
Wine, the Windows compiler builds itself to the same bytes, and of the
upstream examples (scripts/upstream-examples.py) whose reference program
succeeds, 856 of 857 print what it prints. The other is `File.ln`, whose
reference read another example's file in the shared temporary directory.

Wine's error texts are its own (`File not found.`, and none for Winsock's
errors); the reference for them is Windows (CI).

## Still to do

- Local time: Go takes it on Windows from the system's zone
  (`GetDynamicTimeZoneInformation`); the library takes `$TZ` or UTC.
- Stacks: a 1 GiB stack is committed at once. The exception dispatcher
  pushes its record on the faulting stack, so a stack committed as it is
  touched would need room there.
- The gates on Windows. CI (`.github/workflows/native.yml`, job Windows
  x64 on `windows-2025`) runs the Windows compiler the Linux job builds:
  it must make itself again byte for byte, make a program that runs, and
  build every upstream example that prints the same on Linux and Windows
  into a program that prints there what the Linux program prints
  (`scripts/windows-examples.py`: `prepare` on Linux, `check` on Windows,
  or `check --wine` under Wine; `SKIPPED` names the others).
