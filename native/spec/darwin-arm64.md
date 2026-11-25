# macOS on ARM64

`nc_arm()` is 3 in the compiler that makes macOS programs:
`scripts/build-arm64.py --darwin` makes it from the same source as the Linux
ARM64 compiler, which it builds on (spec/arm64.md). It is 2 in a compiler
that makes position-independent Linux ARM64 programs (`--pic`), which is how
the position independence below is checked on Linux. The x86-64 compiler and
the Linux ARM64 compiler (`nc_arm()` 1) take the other branch everywhere: their
programs are byte for byte what they were.

## Position independence

macOS loads an ARM64 program above 4 GiB, wherever it chooses, and refuses
one that is not position-independent. The translated code keeps the layout of
spec/arm64.md (the entry at 0x400080, its words at 0x400420 to 0x400478, the
table of functions at 0x400480): only where an address of that layout is
made does the code change.

- The entry's words and the table hold addresses, so they are read from a
  copy of them that is written: a segment `a_pic_data()` (1 GiB) past the
  image's start, which the code may not reach. Its first word, 16 bytes
  before X26, is how many words it has; the entry relocates each by where
  the image was loaded (`a_relocate`), before anything else.
- X26 holds the address of the copy's first word for the life of the
  program. Nothing else uses X25 to X27, and libSystem keeps them.
- The translator (native-x86arm.alc) makes an address of the words or the
  table from X26 (`a_image`, `xa_add_image`): an absolute memory operand
  (`call [0x400478]`, `cmp [0x400480+rdx*8], rbx`), and a 32-bit immediate
  among those addresses (`mov r11d, slot` before `call [r11]`, a function
  value), which is then written as 64 bits. Every other immediate is a number.
- The runtimes of their own table entry are translated with PIC defined
  (scripts/x86-to-arm64.py, `in_block`), and their sizes do not change.

The image's code has no other absolute address: everything else was
RIP-relative already. Two things read one out of data:

- a float's node in what inspect describes names the float runtime's table
  entry (`ins_float`, spec/integer-parse-x86_64.s), which is read through
  the copy;
- a comparator (equality, ordering, the collector's `mk_ask`) is a function's
  code where it stands below 4 GiB, else a function value whose first word
  is the code. A position-independent program's code stands above 4 GiB, so
  there code is what stands less than 1 GiB and the head below X26
  (`nq_call`); dyld and the kernel keep that gigabyte for the image.

## The executable

`a_macho_image` (native-macho.alc) writes Mach-O: a page of load commands, the
image 128 bytes into the next page so that every offset of it is the one of
the Linux layout, then `__DATA` (the words dyld binds, then the copy) and
`__LINKEDIT` (the chained fixups and the code signature). dyld loads it
(`LC_MAIN`), and binds `_exit`, `_mmap`, `_write`, `_read`, `_close`,
`_munmap`, `_mprotect` and `___error` of libSystem into the words before the
copy (`a_got`).

macOS kills an ARM64 program that is not signed, so the compiler signs it
ad hoc, as the linker does: a CodeDirectory of the SHA-256 of each 4 KiB page
(`m_signature`). The compiler's source has no division and no bitwise
operators (the seed has none), so SHA-256 works on 4-byte words with tables
of xor, and and the shifts of a byte (`sh_tables`). That is slow: the compiler
builds itself in 26 seconds on an M3 Max, where the position-independent
Linux build of it, unsigned, takes 13.

The entry is called as `main` is, with argv in X1 and envp in X2, and dyld's
frames lie between the stack pointer and argv, where the program keeps words
of its own below its initial stack pointer. So the entry copies argc, argv
and envp below the stack pointer, with two zero words after them, and that
copy's argc is the initial stack pointer the program reads (X14,
`a_darwin_args`).

## Calls to the system

There is no stable system-call interface on macOS. The routine every
translated system call goes through (`x86_syscall`, the word at 0x400420) is,
with DARWIN defined, calls of libSystem's functions through the words dyld
binds (scripts/x86-to-arm64.py, `DARWIN_ROUTINE`). The collector holds it
(DARWIN_ROUTINE defined, native-memory-data-darwin.alc); the other runtimes
go to it through the word at 0x400420, as translated functions do. It keeps
every register x86-64 keeps, the vector registers too, finds the call in a
table (`DARWIN_CALLS`: the number, the function, how it converts) and gives
-ENOSYS for any other. What differs is converted both ways:

- errno: a function's -1 is `-errno` in Linux's numbers;
- open's flags, `AT_FDCWD` and the `*at` flags; fcntl's `F_DUPFD_CLOEXEC`
  and status flags; a variadic argument (open's mode, fcntl's) goes on the
  stack, as Apple's calling convention has it;
- stat records, and directory records (`getdents64` is
  `__getdirentries64`);
- the clocks, `getrandom` (`getentropy`, 256 bytes at a time), `ppoll`
  (`poll`), `pipe2` (`pipe` and fcntl), `mremap` (a new mapping and a copy),
  `madvise` (the pages it frees are mapped anew, so that they come back zero
  as Linux gives them),
  `memfd_create` (a file of `mkstemp` unlinked at once);
- signals' numbers (kill, wait4's status, sigaction's record);
- sockets: the families, addresses (a length byte, then the family), the
  options of SOL_SOCKET, TCP and IPV6_V6ONLY, the flags of send and recv;
  every socket gets SO_NOSIGPIPE, as Linux's sends ask with MSG_NOSIGNAL.

The words dyld binds are those of `DARWIN_IMPORTS`, which the collector's
module gives the Mach-O writer (`gd_import_count`, `gd_import_data`). The
entry's own calls (the arena, the stack, exit) call libSystem directly
(`a_libc`).

A runtime asks for AES and PMULL by cpuid, which reads ID_AA64ISAR0_EL1 on
Linux; macOS lets no program read it, and every Mac on ARM64 has both.

The handler of SIGSEGV is installed by sigaction through the routine
(`zf_guard_darwin`): libSystem calls it and returns from it, the fault's
address is at 24 of the information, and the program counter at 272 of the
registers the context points to at 48.

## State

Every program of examples/ runs on macOS as its Linux ARM64 build does, the
corpus of scripts/upstream-examples.py (878 examples) passes on macOS with
the compiler built for macOS, and that compiler compiles its own source on
macOS to itself, byte for byte. scripts/verify-darwin.py checks that on
macOS, with the gates of harness/ that run there; the native workflow's
macOS job runs it in four parts side by side (`--shard`), with the compiler the x86-64 job makes
(`build-arm64.py --darwin --macos`).

Coverage works as on Linux: a position-independent program's coverage
routine holds, in place of the trace runtime's table entry and where the
code starts, where the trace runtime and the routine stand from the start
of the code (`zf_cover_pic`), and Testing._covered reads them so when the
routine stands above 4 GiB.

Not done:

- signing is slow: SHA-256 in the compiler's source works on bytes through
  tables, without bitwise operators, which the seed has none of (about 2 s a
  megabyte); with the translation of large programs to ARM64, a program of
  tens of megabytes takes minutes to compile, which keeps the gates modules
  and gaps from running on macOS in their time;
- `alchem run` gives the program its own standard input through /proc,
  which macOS has not: there the program has none (test_driver);
- the gates that cap a program's address space to make its arena small
  (RLIMIT_AS, which macOS neither lowers nor enforces), that trace it with
  Linux's ptrace, or that need /dev/full or Linux's file system and kernel,
  do not run on macOS (scripts/verify-darwin.py names them).
