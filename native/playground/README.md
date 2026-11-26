# Alchem in the browser: the playground

A page where Alchem programs are written, compiled and run with no server
running them (#137). It takes the first of the two ways the issue names: an
x86-64 interpreter in the browser runs the Linux `alchem` as it is, which
builds the program, and then runs the program it built.

- `emu/` is the interpreter, in Rust with no dependencies. It builds to
  WebAssembly (`wasm32-unknown-unknown`) for the page, and to `emu-run` for
  checking it on any machine against the real programs.
  - `cpu.rs` interprets the x86-64 instructions of the compiler and its
    runtimes: the integer set, the string instructions, SSE2 scalar
    doubles and bitwise operations, SSE4.1 rounding, the VEX fused
    multiply-adds of the float runtime, and AES-NI for TLS. An instruction
    outside this set stops the program with its bytes and address.
  - `mem.rs` is memory in 64 KiB pages, made when first touched, so the
    16 GiB arena a program reserves costs only what it uses.
  - `linux.rs` is the Linux system calls over a file system held in memory:
    files, directories, the standard streams, mmap, time (the machine's own,
    so that a sleep passes at once) and random bytes. There are no other
    processes and no network: fork, exec, pipes and sockets fail with
    ENOSYS, as on a kernel without them. A program's own processes are green
    threads, so they work.
- `web/` is the page. `worker.js` runs the interpreter in a Web Worker, which
  keeps the page free while a program runs and sends its output as it
  comes.
- `build.sh` makes what the page loads: `alchem_emu.wasm` (240 KB) and the
  Linux x86-64 `alchem` (8.2 MB) of this tree, built by the pinned compiler.

## Trying it

```sh
native/playground/build.sh
python3 -m http.server 8737 --directory native/playground/web
```

then open http://localhost:8737.

`emu-run` runs a program outside a browser:

```sh
cd native/playground/emu && cargo build --release
target/release/emu-run --file hello.alc=/work/hello.alc --out /work/hello=hello alchem build -o hello hello.alc
target/release/emu-run --stats hello Ada
```

## Checking it

`check.py` builds each program of the `written` gate (240 of them) with the
Linux `alchem` on the interpreter, runs what it built there too, and
compares both with the pinned compiler's status and output. All 240 match.

```sh
native/playground/check.py native/playground/web/alchem
```

## What it costs

Measured on an M3 Max. The interpreter runs about 80 million instructions a
second natively (`emu-run`) and about 53 million in Chrome's WebAssembly,
after a first run that is slower while the browser compiles the module.

| The page's example | Instructions to build it | Build in the page | Its run |
| --- | --- | --- | --- |
| Hello | 28 million | 0.5 s | under 10 ms |
| Results and with | 37 million | 0.7 s | under 10 ms |
| Structs and pipes | 117 million | 2.2 s | under 10 ms |
| Processes (with `Task.async_stream`) | 1.1 billion | 24 s | under 10 ms |

The page downloads 8.5 MB before its first run (the 8.2 MB `alchem` and the
240 KB interpreter). The programs themselves run at once; the time goes to
compiling them, which pulls in the library functions a program uses, and
the processes example pulls in many.

## Still to do

- Speed: the interpreter decodes each instruction every time it runs it.
  Reading an instruction's bytes at once instead of one by one did not
  change the rate, so where the time goes is still to be measured; a cache
  of decoded instructions by address, or a translation of each function to
  WebAssembly, are the next things to try.
- A smaller download: the page could compress `alchem`, or load a compiler
  without the commands a playground does not use (`lsp`, `fmt`, `alx`).
- A backend for WebAssembly (the second way the issue names) would make
  `alchem build --target wasm` a target of its own; this prototype shows a
  playground does not need it.
