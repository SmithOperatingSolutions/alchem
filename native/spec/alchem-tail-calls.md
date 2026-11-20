# Tail calls and the memory of a program

## A function's call to itself in return position is a loop

As in the pinned compiler (`compiler/codegen.go`, `tailCall`; language-spec,
"Functions"), a function's call to itself that is the whole value it returns
uses no stack and is not one more active call: `loop(n - 1, acc + n)` runs
to any count, where every other call is held to the 100,000 active calls of
`alchem-traces.md`.

The call is a jump exactly where the pinned compiler makes one. Its rule is
on the statements of a function once `unless`, `cond`, `with` and clauses
are rewritten as `if` and `case`:

- **Which statement.** The last expression of the body, of a branch of an
  `if`/`unless` or `cond`, of an arm of a `case`, of the body or an `else`
  arm of a `with`, and of a clause of a function written as clauses, as
  long as each of these forms is itself the last statement of its block;
  the one-line `if c, do: a, else: b` the same. And `return f(...)`
  wherever a `return` may stand.
- **Which expression.** A call by the function's name, with or without its
  module, in parentheses or not, or the last call of a pipeline
  (`n - 1 |> loop(acc)`). Not a call whose value is used further
  (`n * f(n - 1)`, `a or f(x)`, `x = f(n)` then `x`), a call through a
  value (`g = &loop/2`), or a name that a binding hides.
- **Which function.** The same function: the same name, number of
  parameters and, where a name has several forms by parameter types, the
  same form. Default values count as written arguments (`loop(n - 1)` for
  `loop(n, acc \\ 0)` is a jump). Not `main`, not a function without
  parameters, and not a function with a type variable in its signature.
- **Not inside** a `fn`, a `for`, a `try` (body, `rescue`, `catch`, `else`
  or `after`), or an `if`, `case`, `cond` or `with` used as a value: these
  are functions of their own in the pinned compiler. Calls between two
  functions are ordinary calls.

A loop is one active call however long it runs: a function that turns a
million times and then fails shows one line in the trace, at the statement
that failed, and 100,000 calls may still nest below it.

`return` in a `for` or in a `with` used as a value is rejected, as the
pinned compiler rejects it ("return cannot be used inside an if or case
that produces a value"); it was compiled before.

## How it is compiled

`native-tail.alc` (prefix `tl_`). Where a statement's value is the
function's (`nx_value`: the block ends after it, `wf_dropped` says no
statement follows any form around it, and the environment holds no record
of a `fn`, `for`, `try` or form used as a value, `nj_context`; `nj_return`
for `return`; `nc_if_line` for the one-line `if`) and its code ends in a
call of the function itself, the text is looked at: after the parentheses
around the whole of it, it must be a name and one argument list that ends
it, or have `|>` right before that name. Then it is compiled once more with
the end of that call noted in the environment (a record with no name of
type tag 45 and the position), and the call that ends there (`nj_call`, or
`nu_call_finish` for a library function with type variables) is compiled
as a jump: the arguments are evaluated and pushed as for any call, then

```
pop the first six into their registers     (more than six: all are copied to
                                            where this activation's own
                                            arguments lie above its frame,
                                            and the first six loaded)
dec r15                                     the call is no longer active
leave                                       the frame and all it pushed go
mov r11d, entry; jmp [r11]                  the function's table entry
```

Entering again checks the stack, counts the call, stores the parameters,
clears the closure records and the statement position and runs the pattern
match of a function written as clauses, as any entry does, so nothing of
the turn before is live: bindings, records of forms used as values,
`try` handlers and `for` state cannot stand around a call in return
position, and a `fn` made in a turn holds that turn's values in its own
record. All arguments are evaluated before any parameter is replaced.

## The library is no call of the program

The pinned compiler has the library in Go, where its loops and searches
are not calls of the program. So a function of the library written in
Alchem (`library/*.alc`) jumps the same way and may have type variables
(its comparators are passed again after the arguments), and neither it nor
a `fn` in it is an active call: both are entered and left without `R15`
being touched (`tl_enter`, `tl_leave`, `tl_fn_enter`, `tl_fn_leave`; the
jump leaves out its `dec r15`). A program therefore nests as deep through
`Enum.flat_map`, `zip_with` or `reduce_while` as in the pinned runtime
(49,999 turns of a function that calls itself from a `fn` it passes, where
40,000 were too many when the library's own function and `fn` counted), and a search of the regex matcher, which goes a
call down per step, is held to the stack alone (1 GiB reserved, exit 70):
`(?:ab)*c` matches 8 MB of `ab` (it stopped at 60 KB with `call depth
exceeded`) and would exhaust the stack near 9 MB.

## The memory of a program

Every value comes from the arena, which is never given back
(`alchem-collections-profile.md`). It was 4 MiB. An ordinary program now
reserves 16 GiB lazily (`nc_arena_init`: `mmap` with `MAP_NORESERVE`, one
page more than the arena), or the largest half of that the system grants
down to 4 MiB, and exits 71 when no 4 MiB are granted: reserved pages cost
nothing until they are written, so a program takes what it allocates and no
more. The page after the arena starts with the size reserved, which
`System.memory` reads: `in_use` is what has been taken (with the library's
block of 16,384 bytes), `held` the pages that takes (with that page), `idle`
the rest of `held`. A program that takes all of its arena exits 71, as
before. The processes of a program share the one arena.

What a gate measures is unchanged: the bytes charged (`R12` less the
arena's start, `harness/native_memory.py`), whatever was reserved. A gate
that needs an exhausted arena runs the program in an address space where the
reservation halves down to its 4 MiB floor (`floor_arena`: the image and
7 MiB), so the exact boundaries of the 4 MiB arena are still tested, and
`harness/collection_memory.py` measures the same program at both sizes.

File and input sizes are now the pinned runtime's instead of the arena's:
`File.read` of more than 16,777,216 bytes is
`error("file exceeds 16777216 bytes")` and `IO.read_all` of more input ends
the program with `input exceeds 16777216 bytes` at the call (both read the
whole of it first).

### Measured against the pinned compiler

Peak resident memory and time, pinned and native, through `scripts/limited`:

| Program | Turns | Pinned | Native |
| --- | --- | --- | --- |
| `loop(n - 1, acc + n)` | 10,000,000 | 7 MB, 0.12 s | 7 MB, 0.12 s (4 MiB arena and 2 MiB stack suffice) |
| the same | 100,000 / 1,000,000 | 7 MB | 7 MB |
| a turn formats a string (`"item " <> Integer.to_string(n) <> ...`, `String.pad_leading`) | 100,000 | 7 MB, 0.05 s | 18 MB, 0.07 s |
| the same | 1,000,000 | 8 MB, 0.33 s | 186 MB, 0.47 s |
| the same | 10,000,000 | 9 MB, 2.5 s | 1.9 GB, 4.2 s |
| a turn calls `Enum.max` on a list of four | 100,000 | 7 MB | 37 MB |
| the same | 1,000,000 | 8 MB, 0.16 s | 369 MB, 0.22 s |
| the same | 10,000,000 | 9 MB, 0.9 s | 3.6 GB, 1.9 s |
| `Enum.sort` of 20,000 with a function | | 7 MB | 7 MB |
| `Regex.scan` with 16,000 matches | | 7 MB | 7 MB |
| a list of 20,000 built by `[n \| acc]` in a loop, then summed by `[h \| t]` | | 7 MB, 0.04 s | 7 MB, 0.03 s (3.1 GB, 1.1 s while a list was copied: `alchem-lists.md`) |

All of these stopped with status 71 or `call depth exceeded` before.

## Differences from the pinned compiler that remain

- **Nothing is reclaimed** was true when this was written; memory is given back now (`alchem-memory.md`), and what follows in this entry is how it was. The pinned runtime collects garbage; here a
  program holds all it ever allocated, about 190 bytes for a turn that
  formats a string and 360 for a call of `Enum.max` in the table above, up
  to the 16 GiB reserved (or the machine's memory, where the system then
  ends the program instead of status 71). A collector needs what the
  runtime does not have: values are untyped words, so a precise one needs,
  for every frame slot and every record, the type the compiler knows (the
  descriptions it writes for `inspect` cover values, not frames, and a
  value of a type variable's type has none), and a conservative one must
  scan every stack (each process has its own) and the arena for words that
  look like addresses, and cannot move anything. Resetting the arena at
  each turn of a loop whose new arguments are all scalars or older than the
  turn (a comparison per argument) would make the loops of the table run in
  constant memory, but is unsound as things are: processes share the arena,
  so another process may allocate between a turn's start and its end, and
  the library's stream cells are written in place (`Stream.__put`), so an
  older record may come to point at a younger one. It needs an arena per
  process and a write barrier in those cells first.
- **Lists no longer copy** (`alchem-lists.md`): a tail is an address
  inside its list and an element put before a list is written into the
  list's block, so the loop of the last row of the table takes 7 MB and
  0.03 s for 20,000 elements and 408 MB for ten million (the pinned runtime
  207 MB). What remains of this difference is there: 16 bytes an element,
  blocks a list outgrew are kept, and `acc ++ [x]` in a loop keeps every
  copy it makes.
- **Deep traces through closures.** Where calls nest too deep through a
  `for`, a `try` or a `fn`, the pinned runtime shows fewer than 61 lines
  (50 through a `for`, 35 through a `rescue` arm: its Go frames count
  against its limit); here 61 are shown. The first lines agree.

## Fixed on the way

- `Stream.iterate` gave every element in the one cell it keeps its state
  in, which the next stage writes its result into: `Stream.map` over it
  ran its function over its own results (`[2, 6, 14, 30, 62]` for
  `[2, 4, 6, 8, 10]`). Each element is now a cell of its own
  (`harness/streams.py`).
- The scans that look for the end of a block, a pipe or the bar of a list
  (`wc_scan_step`, `wc_arm_arrow`, `nk_arm_step`, `nk_pipe_step`,
  `nk_end_step`) took every `fn` for the opening of a block, also
  `fn(x: integer): integer do ... end`, whose `do` opens it, and the type
  `fn[integer, integer]`: `[fn(x: integer): integer do x end | rest]` did
  not compile. They now ask `nf_untyped`, as `nc_body_chunk` does.

`harness/tail_calls.py` holds 71 programs with the pinned compiler's status,
output and trace, and 4 it rejects.
