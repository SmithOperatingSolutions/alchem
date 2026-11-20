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

ImageBase is 0x3C0000, and nothing is relocated (no `DYNAMIC_BASE`):

| RVA | Address | Section | |
| --- | --- | --- | --- |
| 0 | 0x3C0000 | headers | |
| 0x1000 | 0x3C1000 | `.wtext`, RX | the Windows layer's code, the import tables |
| 0x10000 | 0x3D0000 | `.wdata`, RW | its data, the import address table |
| 0x40000 | 0x400000 | `.text`, RX | the image: the ELF header and code of Linux |

The bytes before the image are a constant, `nw_prefix()`
(native-windows-data.alc, made by scripts/generate-windows-runtime.py);
`nw_pe` fills in the three header fields that depend on the image's size.
The image keeps its 128-byte ELF header, so the entry stays at 0x400080,
the words at 0x400420 to 0x400478 and the function table at 0x400480.

## The Windows layer

`spec/windows-x86_64.s`, about 3 KiB of code.

- **Entry.** The PE entry adds a vectored exception handler, keeps the
  stack Windows started the thread with, builds a Linux initial stack and
  jumps to 0x400080. The arguments come from `GetCommandLineW`, split as
  Go's `os` package splits it on Windows, and the environment from
  `GetEnvironmentStringsW`, both in UTF-8. 64 KiB of stack lie below that
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
  with descriptors, each is taken as ready).

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
succeeds, 784 of 857 print what it prints. The others need:

- sockets: `socket` and the calls after it (38 examples);
- processes: `fork`, `pipe2` (`System.cmd`, `Port`);
- `pwrite64`, `getdents64` (`File.ls`), `mremap`, `fchmodat`, `link`,
  `symlink`, `utimensat`, `memfd_create`;
- the library's view of Windows, which Go's packages give the pinned
  programs: the working directory and `Path.expand` with forward slashes
  (`Z:/tmp/...`), `C:\x` absolute and `/x` volume-relative in
  `Path.type`, `System.user_home` from `USERPROFILE`, and Windows' texts
  for errors (`open nope: File not found.` under Wine, from
  `FormatMessage`, where Linux gives `no such file or directory`).

The last needs the library to know it runs on Windows. One way, as
`System.collect_garbage` already does (spec/alchem-memory.md), is a system
call number Linux does not have, which the Windows layer answers; error
texts then come from `FormatMessageW` for the kept Windows error, as Go's
`syscall.Errno.Error` gets them.

## Still to do

- The calls and the library's view above, against the pinned compiler's
  windows/amd64 programs. Wine's error texts are its own; the reference
  for those is Windows (CI).
- An empty command line: Go then takes the executable's path as the one
  argument.
- Stacks: a 1 GiB stack is committed at once. The exception dispatcher
  pushes its record on the faulting stack, so a stack committed as it is
  touched would need room there.
- `alchem build -target windows/amd64` in tools/alchem.alc.
- The gates on Windows. CI (`.github/workflows/native.yml`, job Windows
  x64 on `windows-2025`) runs the Windows compiler the Linux job builds:
  it must make itself again byte for byte, and make a program that runs.
