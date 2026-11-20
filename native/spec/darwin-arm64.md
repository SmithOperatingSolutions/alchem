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
RIP-relative already.

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

The entry is called as `main` is, with argv in X1: the initial stack pointer
the program reads (X14) is the word before it, argc.

## Calls to the system

There is no stable system-call interface on macOS. The routine every
translated system call goes through (`x86_syscall`, the word at 0x400420) is,
with DARWIN defined, calls of libSystem's functions through the words dyld
binds (scripts/x86-to-arm64.py, `DARWIN_SYSCALL`): it keeps every register
x86-64 keeps, the vector registers too, converts what differs (`mmap`'s
flags), and gives `-errno` where a function gives -1. The entry's own calls
(the arena, the stack, exit) call libSystem directly (`a_libc`). The
collector for macOS is native-memory-data-darwin.alc.

So far `read`, `write`, `close`, `mmap`, `munmap`, `mprotect` and `exit` are
calls; any other call gives -ENOSYS (-38).

## State

Every program of examples/ runs on macOS as its Linux ARM64 build does, and
the compiler built for macOS compiles its own source on macOS to itself, byte
for byte. Not yet done:

- the rest of the system calls (files, time, processes, sockets, signals),
  with macOS's numbers for errors, flags and structures;
- the handler of SIGSEGV (`zf_guard_arm`), which installs itself with Linux's
  `rt_sigaction`;
- coverage (`zf_shared`) and inspected function values (native-inspect.alc),
  which keep a slot's address in 32 bits;
- the corpus and the gates on macOS, and a job for them on `macos-15`.
