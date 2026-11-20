# Memory that is given back

A native program took every value from one arena by moving a pointer and
never gave anything back (`alchem-tail-calls.md`): a server's loop, a list
built with `++` or a map updated in a loop ended with status 71 where the
pinned runtime, which has Go's collector, runs for ever. Now a program
collects: memory nothing refers to any more is found and used again, so a
program runs as long as its live data fits.

`spec/memory-x86_64.s` is the collector (assembled into
`implementations/alchem/native-memory-data.alc` by
`scripts/generate-memory-runtime.py`), `native-memory.alc` (prefix `gm_`)
puts it into a program, and `harness/memory_reclaim.py` is its gate.

## What was weighed

- **A collector that moves values** (copying, mark-compact, an arena per
  process copied on send) needs to know, for every word of every frame,
  record and mapped block, whether it is an address. The runtime does not:
  values are untyped words; a value of a type variable's type has no
  description; a function value's captured words have none; the library
  written in Alchem keeps values as integers (`Process.__word`) in blocks it
  maps itself and writes them with `Sys.poke` (about 700 places: process
  records, mailbox cells, timers, sockets, JSON and HTTP scratch); a list's
  tail is an address inside its block, and an element is put before a list
  by writing below its head. One word taken for a number where it was an
  address, or the reverse, corrupts a program silently. It was not chosen.
- **Giving an arena back at a process's end or a loop's turn** needs the
  same knowledge to copy what survives, and reclaims nothing inside a
  process that lives long.
- **Marking without moving**, taking every word that could be an address
  for one: chosen. Nothing moves, so every write the library makes in place
  stays right, an address inside a list keeps its block, and a word wrongly
  taken for an address only keeps something longer. What it needs is where
  every value starts, which the allocation sites now say.

## The heap

The arena is as before: 16 GiB reserved lazily, or the largest half the
system grants down to 4 MiB (`nc_arena_init`). Beside it the collector maps
(lazily, about a seventh of the arena's size; a program whose system does
not grant that runs without collecting, as before):

- **S**, a bit per 8 bytes of arena: set where a value starts;
- **M**, the marks of a collection; **F**, set where a free range starts;
- a summary of S (a bit per word of S), made at each collection, to find the
  start of a large value from an address inside it;
- the mark stack and the table of mapped blocks (below).

A **value** runs from its S bit to the next S bit: allocation is still a
pointer that moves, so values lie side by side. A site that left its value
without a bit (none is known; the places that fill reserved room, below,
do so on purpose) makes it part of the value before it, which lives and
dies with that one: too much is kept, never too little.

**Memory is zero where a value is made**, as the untouched arena was: the
list code relies on it (an unclaimed pair is a count of 0,
`alchem-lists.md`). A free range keeps what died in it, and is made zero
when it is taken as a window (`gm_take`); of a range much larger than what
is asked for only the first part is taken (what is asked, at least 1 MiB),
so that no more is made zero than is about to be used. The sweep therefore
reads and writes no byte of the arena but the two words (next, size) that
head a free range of 128 bytes or more: it goes through S, M and F alone.
(It zeroed all that died: 22% of the time of the pinned `suite/list`
program, whose garbage is lists of megabytes.) When the frontier comes
down, what lies between it and where it was is not zero either: two words
keep the part of the arena above the frontier that was in use (`DLOW` to
`DTOP`), and a fresh window is made zero where it lies in it (`gm_clean`).
The file runtime
no longer leaves a path, or what it read of a file that then failed, behind
the arena's cursor: the path stands on the stack, and what was read is
zeroed (`spec/file-read-x86_64.s`).

## Allocation

Every allocation site was `lea r11,[r12+size]; cmp r11,r13; jbe ok; exit 71;
ok: ...; mov r12,r11`. The exit is now `call [0x400478]`, the **allocation
hook** (`gm_alloc`). In a collecting program R13 is 0, so every allocation
calls it:

- with room in the current window (`r11 <= limit`): the S bit of R12 is
  set; a dozen instructions.
- without: the window is closed (what is left of it becomes a free range),
  a collection runs if as much was allocated since the last as the
  threshold says, and a new window is taken: a free range from the lists
  (48 lists by size; the first range of the smallest class that surely
  fits), else up to 1 MiB of fresh arena past the **frontier** (the
  highest address in use), else, after a collection, status 71. R12 and
  R11 come back moved to the new window. Every site was changed so that it
  holds nothing else derived from R12 when it calls: nine in
  `native-sets.alc` and `native-operators.alc` had copied R12 before the
  check (the assembly variant below found the first of them).

A site that fills memory of a size it does not know beforehand first calls
the **reserve hook** (`call [0x400470]`, R11 the end it asks for): it gets
that much room in a window and R13 set to its end, and then runs as it
always did, checking against R13. When the room is full it calls the
**grow hook** (`call [0x400458]`), which makes the room larger where it is
(a window at the frontier grows with it) or moves the bytes to room twice
as large and says by how much. When it is done it puts R13 back
(`mov r13,[r14-1320]`). These are `IO.read_all`, `IO.read_line`,
`File.read` and `inspect` (its text, with a float's digits in it): a line
or a file of any length is read into room that grows, where it was read
into all of the arena that was left. `String.duplicate` and the padding
functions refuse a result larger than the arena before they count it out
(status 71), as they refused one larger than what was left of it.

A compiler entry (`nc_entry_compiler`, the compiler itself among them)
collects as every program does: its arena is every program's
(`nc_arena_init`), and its input, all of standard input, is read into room
the reserve hook gives and the grow hook makes larger, as `IO.read_all`
reads (`nc_io_prefix`; more than 16 MiB less 1 KiB is refused as before).
The compiler building itself went from 1.47 GB resident to 53 MB, and
compiles a small program in 16 MiB of address space. `gm_off` (a start that
leaves the collector off) remains in the blob, started by no entry.

## Roots: how they are found exactly

A collection starts inside a hook, on the stack of the process that
allocated. Every general register is pushed first, so the registers are
part of that stack. Then every word of these is taken for a possible
address:

1. **The running stack**, from the stack pointer to the top of its mapping.
2. **Every other stack**: the main stack and each stack a process was
   given. `Process.__switch` keeps the stack pointer it leaves where the
   collector reads it: in the word below the top of a process's stack (the
   word at +256 of its record is that top), or for the main process in the
   collector's own word at R14-504. That word of a process's stack is the
   next free stack's top while the stack is free, and of a stack given out
   but never left it is that still: such a word is no address in the
   stack, and then only the stack's top 64 bytes are scanned, where
   `Process._start` puts the function a new process runs.
3. **Every block the library maps**: `Sys.call` is compiled as a call of
   the collector's system-call entry (`call [0x400468]`), which notes
   every anonymous `mmap`, `mremap` and `munmap` in a table. Blocks mapped
   with `MAP_NORESERVE` are the stacks of (2); all others (the block of
   the process library, mailbox cells, the state block, buffers) are
   scanned whole.
4. The 64 bytes below R14 that hold the program's few globals, and the
   library's block of working memory (`Sys.state`, the word that ends
   `argv`), which the coverage routine of a test program may have mapped
   itself.

The image is read-only and holds no address of the arena. Nothing else is
mapped: the arena, the main stack and the collector's own tables are the
only mappings machine code makes.

A word `v` of a stack or register keeps the value `v` lies in, and also the
one `v - 1` and the one `v + 8` lie in: machine code holds the address just
past a string it has read to its end (`String.split` keeps that of its
text), or steps through a block from one word before it. A word inside a
value or a mapped block keeps only the value it lies in.

What this relies on, and the audit behind it:

- **A value is held as its own word** wherever it is held: never shifted,
  negated, xor-ed or as a difference. `Process.__word` and `__any` pass the
  word on; the library's cells hold words.
- **No address of the arena lies only in a floating-point register** across
  an allocation (the float runtime holds floats there), **or below the
  stack pointer** (no code uses a red zone: every literal of the compiler
  was disassembled and searched), or in the kernel.
- Code that runs with R12 to R15 as scratch (the hash and TLS runtimes, the
  final trace) does not allocate.
- Every instruction that writes R12 was listed (a census of all byte
  literals and of `spec/*.s`): 99 writes in 90 routines, each an
  allocation of one of the forms above.

**A function value's record held what an earlier call had left on the
stack**: a `fn` copies the slot of every record of its environment, and
the records that stand for no value (the expected type of a call, tag 21;
the marks of where a statement stands, tags 40 to 46) have slots nothing
stores into. The copied word was often an address, which kept a value of
the turn before in use, and that one the turn before it: 20,000 rounds of
fifty function values and a stream kept 107 MB. Such a slot is no longer
copied (`gm_held`); the record's word stays 0.

**The records of processes are values now.** The process library took its
records (a process, 384 bytes; a socket, a task, a timer) from blocks it
mapped and never gave back, so a program that started a million processes
kept a million records. `Process._take` now gives a string of zero bytes
from the arena: a record nothing refers to (its handle is gone, it is in
no list of the block `g`) is collected like any value.

## A collection

1. The window is closed. M is all zero (the sweep leaves it so) but for
   the bits of owned values (below), which are cleared now: nothing is
   owned after a collection.
2. The summary of S is made.
3. Roots are marked: the value an address lies in is found by searching S
   downward from the address (through the summary when the word of S is
   empty); a value whose F bit is set is free and ignored; else its M bit
   is set and it is pushed on the mark stack.
4. The mark stack is emptied: every word of a popped value is treated the
   same way. When the stack is full a value is marked but not pushed, and
   afterwards every marked value is scanned again until none had to be left
   out.
5. Sweep, in address order over S: a marked value loses its mark; a free
   range stays; an unmarked value becomes one, as it is. Neighbouring free
   and dead ranges become one (their inner S and F bits go; a word of S
   inside such a run with no mark is cleared whole). A free range of 128
   bytes or more is put at the end of the list of its size class, so that
   low addresses are used first. A free range that reaches the frontier
   lowers the frontier, and its pages are given back to the system when
   they are 4 MiB or more.
6. The threshold for the next collection is the bytes found live, at least
   8 MiB.

`System.collect_garbage()` runs one (through `Sys.call` with a number the
kernel does not have, 1000001), and `System.memory()` reads the
collector's words: `held` is the arena up to the frontier, `idle` what of
it lies in free ranges, `in_use` the rest, `collections` the collections
that ran.

## What triggers a collection

- 8 MiB, or as much as was live after the last collection if that is more,
  have been allocated since the last one (counted when a window closes; a
  fresh window is at most 1 MiB, so the count is at most that late);
- or no free range and no fresh arena can hold an allocation;
- or `System.collect_garbage()`.

## Testing the collector itself

`scripts/generate-memory-runtime.py --stress` assembles a variant (never
committed) in which a program collects after every 64 KiB and every value
is made 64 bytes further on than its site meant to make it; the next call
of the hook stops the program (an invalid instruction) when those 64 bytes
were written. All gates were run with it: it found the nine sites that
kept R12 across the hook, and the path the file runtime left in free
memory. With it every gate passes but the ones that measure exact charges.

## Maps

A map was its count and its keys and values in one block: a lookup went
through all of it, and `Map.put` and `Map.delete` copied all of it, so a
map built or updated in a loop took time and memory with the square of its
size (50,000 puts: 5.6 s and 20 GB of copies, where the pinned runtime, a
hash trie, takes 12 ms). With memory given back the copies no longer end
the program, but the time stayed.

A map is now the address of a **node**. A **leaf** is what a map always
was: the count and the keys and values side by side in the order of the
keys. A **branch** has bit 62 set in its first word beside the count of
all entries below it; then the number of its children and, for each, a key
no entry of that child is below, and the child. A map of up to 32 entries
is one leaf, served by the code that always served it
(`spec/collections-x86_64.s`), byte for byte and with the same charges. A
larger one, whatever its keys are, is served by the collector's blob (`gm_map_get`, `gm_map_put`,
`gm_map_delete`, `gm_map_entries`, `gm_map_new`, `gm_map_flat` in
`spec/memory-x86_64.s`, called through `0x400428` to `0x400450`):

- a key is found by a search by halves in each node on the way down
  (integer keys in a loop of their own, without a call per comparison);
- `Map.put` and `Map.delete` copy the nodes on the way to the entry, at
  most 32 pairs each, and share the rest with the map they were given; a
  node that would hold 33 pairs becomes two halves; a branch left with one
  child is that child, and a map left with 32 entries or fewer is one leaf
  again;
- a leaf of more than 32 entries (one made at once: `Map.new` of keys that
  come in order, a map read from JSON or from another node) is valid and is
  made a tree of leaves of 24 the first time something is put into or
  deleted from it;
- `Map.new` of more than 32 pairs whose keys do not come in order, or are
  floats or tuples, puts them one by one, into a map that is its own
  (below).

**Keys that are or hold a NaN.** A float that is a NaN, and a tuple that
holds one, equals nothing, itself included (`Float.pow(-8.0, 0.5)` makes
one): it is never found, every put of one adds an entry, deleting one
changes nothing, and it has no place in an order. Maps with float or tuple
keys were therefore kept as one block of any size and searched from its
start. Now such keys stand after all others, in a leaf and in a tree, in
the order they were put: the keys before them are in order and are
searched by halves, a key that holds a NaN is not looked for at all
(`mk_nan`: it is not equal to itself) and is put last. A search compares
by the order alone when the last key of a node holds no NaN (then none
does); else every key it meets is asked first (`mk_cmp`). The compiler's
own code for up to 32 entries leaves a NaN where it was put and lets it
stop the keys put after it, so a leaf it made is put right before its
first put here (`mk_canon`). The pinned runtime keeps a map by hashes
seeded per run and sorts with an order a NaN has no place in, so the
order of a map with such keys differs there from run to run; counts and
lookups are the same (`keys` in the gate). A put of a key that is there
writes the key too (`-0.0` over `0.0`), as the pinned `putNode` does.

What reads a map's words was changed to go through the tree or to ask for
one leaf of it first (`gm_map_flat`, `Sys.flat` in the library): `inspect`
(`ins_tree`), `==` (`nq_map`, which now compares the entries pairwise in
key order instead of searching the second map for every key of the first),
map patterns (`np_emit_map`), `Enum.count` (the count without bit 62), and
the JSON and node encoders. `Map.keys`, `values`, `to_list`, `for` over a
map and everything built on them walk the tree in order. A `MapSet` is a
map and gained the same.

## Owned values

A value is never changed once it is made, with two exceptions that no
program can observe. They are what made a fold over a map and a loop that
appends to a string take time with the square of their length: every turn
copied what the turn before had made and nothing else could reach.

**The mechanism** (`spec/memory-x86_64.s`, "Owned values"). M, the marks,
is all zero between collections; there a bit says that the value that
starts at it is *owned*: it was made by an owned operation, has room, and
was given to nobody but the operation's result.

- `gm_map_oput` (owned `Map.put`): a node on the way to the entry that is
  owned is changed where it is; one that is not is copied into a node
  with room for 32 pairs and that one is owned. A full node gives its
  upper half to a new one. No garbage but at a split.
- `gm_str_append` (owned `<>`): an owned string is `[room][length][bytes]`,
  its address that of its length as of any string, the value starting a
  word before. With room the right string's bytes are written behind the
  left's and the length grows; else both go into a new string with twice
  the room (at least 64 bytes), as the pinned `actor.Concat` does.
- `gm_map_done`, `gm_str_done`: the bits go (of a map: of the owned nodes,
  which are those the fold touched). The value is as any other from then on.
- `gm_map_own`, `gm_map_owned`: a map's first node made owned, and asked
  for, for the library (below).
- A collection clears M before it marks. Nothing is owned after one; the
  next owned operation copies once more. A bit left on a value nothing
  refers to (a fold ended by a raise) is gone before its memory is used
  again, since memory is only used again after a collection.
- A program that does not collect owns nothing: its owned operations are
  the plain ones.

They are reached through `Sys.call`'s entry (`call [0x400468]`) with
numbers the kernel does not have, 1000002 to 1000007, so the table of
entries did not grow.

**Where the compiler asks for them** (`native-memory.alc`, "Owned
accumulators"). The rule is the pinned compiler's for maps (`fold.go`,
`ownedFold`) and what its `actor.Concat` does for strings, by other means:
that runtime extends the string a process built last, which it can tell
from any other because its strings are an address and a length held apart;
a native string is its length and bytes in one block, so here the compiler
has to know that nothing else holds the string.

- *The accumulator of a fold*: the second parameter of the `fn` that is
  the last argument of `Enum.reduce` (two or three arguments, piped or
  not; `Enum` the library's: a program with a module `Enum` has no folds),
  both parameters plain names; and the name of the first arm of
  `for ... reduce: ... do acc -> ... end`.
- *A string parameter handed on*: a parameter of a function (written
  without clauses) whose body holds `name <> ...` at the start of an
  argument.
- *The owned read.* Where a statement is the fn's or arm's result (the
  block ends in it, its value is not dropped, and no `fn`, `for`, `try` or
  form used as a value was entered since) and is `acc <> rest`,
  `Map.put(acc, ...)`, `Map.update(acc, ...)`, `Map.put_new(acc, ...)`,
  `MapSet.put(acc, ...)` or `acc` alone, it is compiled once more with
  that read of `acc` noted. For a function's call to itself in return
  position the argument `acc <> rest` at the parameter's own place is
  noted the same way (not for a piped call, whose arguments are one
  further on).
  `acc <> rest`: all that follows the `<>` is made first, reading `acc`
  as it was, then appended once. In the call of a function to itself the
  append waits until every argument is made and stands before the jump,
  so `loop(n - 1, acc <> x, byte_size(acc))` passes the size before the
  append, as it must.
  `Map.put(acc, k, v)` is the owned put. For `Map.update`, `Map.put_new`
  and `MapSet.put` the map is made the fold's own (`gm_map_own`) and the
  library's function, which ends in `Map.o_keep`, puts into it where it
  is when it is owned and as a plain put when not; `Map.o_keep` and
  `Map.o_put` (an owned put into a map the library made itself:
  `Enum.uniq`) are the library's alone.
- *Every other read gives the value away*: it is followed by the release
  (`gm_str_done`, `gm_map_done`), unless it only looks: `acc == x`,
  `acc != x`, `byte_size(acc)`, `String.length(acc)`, `Map.get(acc, ...)`,
  `Map.fetch`, `Map.fetch!`, `Map.has_key?`, `map_size(acc)`,
  `MapSet.member?`, `MapSet.size` (each only where the program has no
  function or module of that name). A `fn` whose text names the
  accumulator releases it where the fn is made, since the fn keeps it.
  What `Enum.reduce` and the `for` give is released: the fold is over.

So a value is owned only while it is the accumulator on its way from one
turn to the next. Whoever else gets it (a list, a function value, a
process, the caller) gets it released, and an owned operation on a
released value copies it first. `harness/memory_reclaim.py` (`appending`,
`folds`) holds the loops in which an earlier value is still held: kept in
a list, read behind the append, captured by a `fn`, appended to itself,
started from twice, ended by a raise.

`Map.new` of pairs out of order, `Enum.uniq`, `Enum.group_by`,
`Enum.frequencies`, `Map.merge`, `MapSet.new`, `MapSet.union` and every
other function of the library written as such a fold change their map
where it is.

## Frames

A frame's slots are roots for as long as the frame stands. Two things
kept values there after their last read, and in a function that calls
itself they add up, a frame per call:

- *a binding that is over*. In a function that calls itself by name
  (noted at its entry, `gm_params`), behind a statement that has no block
  of its own, the slot of every binding the statement names and nothing
  behind it names again is set to 0 (`gm_cleared`): bindings of the
  function and its parameters, or inside a `fn`, `for` or form used as a
  value those made there. Only where the function ends within 1,500 bytes
  of the statement, so that looking for the names costs little.
- *what earlier calls left on the stack*. A frame is not cleared when it
  is made: the slots a function has not stored into yet hold whatever lay
  there, often addresses of the values the calls before had (measured:
  with the bindings cleared alone the program below kept all of its 121
  MB). A function that calls itself other than by a jump (a loop keeps
  one frame) sets its sixteen slots to 0 at its entry (nine instructions,
  `gm_frame`) when its code makes values or calls anything but itself and
  the shared routines it fails through; a body that only computes and
  calls itself (`fib`) leaves nothing new behind and is entered as before.

20,000 calls deep, each with a list of 100 tuples it no longer needs:
121 MB resident before, 13 MB now (`frames` in the gate). The cost,
measured as the least of six runs in turn: `fib(38)` 0.452 s and 0.451 s
(it is entered as before); the compiler compiling itself 6.45 s without
the cleared frames and 6.51 s with them (0.8%; the compiler does not
collect, so for it they are all cost). `harness/system_env.py` exhausted
a 4 MiB arena with 200 copies of the arguments that only the frames of a
function's calls to itself still held; it holds them in a list now.

## What changed, measured

Processor seconds of the program (least of three runs, each compiler's
program in turn on a busy machine), before this work, after it, and the
pinned program's (all its threads):

| Program | Before | Now | Pinned |
| --- | --- | --- | --- |
| 200,000 one-byte appends by a function's call to itself and 200,000 by `Enum.reduce` | 7.24 | 0.01 | 0.01 |
| 100,000 appends by `for ... reduce:` | 0.70 | 0.00 | 0.00 |
| a million `Map.put` in `Enum.reduce` | 1.48 | 0.34 | 0.61 |
| a million `Map.put` by a function's call to itself | 1.68 | 1.19 | 2.33 |
| five million `Map.update` over 1,000 keys in `Enum.reduce` | 1.03 | 0.48 | 0.14 |
| 20,000 float keys and 20,000 tuple keys put one by one | killed at 2 GB | 0.03 | (does not build: `Map.keys` of tuple keys) |
| 20,000 calls deep with a dead list each: resident | 155 MB | 16 MB | 19 MB |
| `suite/map_set`, its medians summed | 4.14 | 0.73 | 0.46 |
| `suite/string`: `<>` append 1 byte 20k times, median | 0.1246 | 0.0002 | 0.0002 |

`Map.update` is three searches of a tree where the pinned runtime makes
two of a hash trie; `map.get` and `has_key?` of 100,000 integer keys
remain four to five times the pinned medians for the same reason (a
search by halves through three nodes against five bits of a hash a
level). The list `acc ++ [x]` in a loop copies in both: 20,000 turns take
0.25 s here and 0.34 s there.

## Loops of the library

A function's call to itself in return position is a jump
(`alchem-tail-calls.md`), but it was not when the call was written with
the module's name and the function belongs to the library
(`Process._drop(g, x, a)` inside `Process._drop`): such a call has the
store of where it stands between its arguments and the call, and the
shape that is looked for did not allow for it. Every loop of the process
library (and of the modules built like it: Task, Server, Supervisor, TCP,
HTTP, Node, JSON, TLS) therefore went one call deeper per turn, 176 bytes
of stack each: a task that ended walked the list of its parent's links
that deep, so 10,000 tasks alive at once touched 9 GB of stacks and the
program was killed. `tl_unplaced` takes the store out before the shape is
compared; 26 functions of a program with tasks loop now.

## Differences from the pinned runtime that remain

- **A binding keeps its value until its function returns, outside a
  function that calls itself.** Bindings are cleared, and frames made
  zero, only in a function that calls itself by name ("Frames"): there
  frames stand one on the other. Two functions that call each other in
  turn, each holding a large value it no longer needs, still keep all of
  them: which functions reach themselves through others is not known where
  a function is compiled (one pass, a function at a time), and clearing in
  every function costs every call (nine stores at an entry: 31% on
  `fib(38)` when it was tried there, 3% on the compiler's own build when
  loops had it too). Inside such a function a binding last named in a
  statement with a block of its own (the condition of an `if`), or more
  than 1,500 bytes before the function's end, or of a function written as
  clauses, is not cleared; the frame's slots are still zero at its entry.
- **Values are not moved**, so memory between values that live long is
  only used again for values that fit there (free ranges under 128 bytes
  wait until a neighbour dies), and the arena cannot be given back below
  the highest value in use.
- **A word that looks like an address keeps a value.** An integer, the
  bits of a float or eight bytes of a string that happen to be the address
  of something keep it in use until they change. Addresses are 47-bit
  numbers near 0x7000_0000_0000; nothing in the gates met one by accident.
- **`acc <> piece` copies where the compiler cannot see that nothing else
  holds the string.** The pinned runtime extends in place whatever string
  a process built last; here the append is owned in the shapes of "Owned
  values" and copies in the others: a parameter of a function written as
  clauses (`def build(0, acc)`, `def build(n, acc)`: the clauses are one
  case over hidden parameters, and the names differ from clause to
  clause); `f(n - 1) <> piece`, where the string comes back from the call
  (it would have to be released wherever else the function returns); a
  string inside a tuple accumulator (`{acc <> x, n}`: the tuple is made
  anew each turn and what else reads its parts is not followed); a
  binding rebound in a row of statements (`s = s <> a` then `s = s <> b`:
  each is one copy, there is no loop); an `Enum.reduce` given a named
  function or a `fn(...): type do`; `Enum.reduce_while`, `List.foldl` and
  the like. They are correct and take time with the square of the length,
  as all appends did.
- **A map in a fold is changed in place only through `Enum.reduce` with a
  `fn x, acc -> ... end` and `for ... reduce:`.** The pinned compiler also
  takes a named function (`&put/2`) and a typed `fn`; here those copy the
  nodes on the way to the entry, as every put outside a fold does (a
  million puts by a function that calls itself: 1.0 s of processor time
  here, 2.3 to 2.9 s for the pinned program over its threads, 0.9 s by
  the clock).
- **Every word of a live value is read at a collection, and memory is
  made zero before it is used again**: there is no note that a value
  holds no addresses. Both are what the pinned `suite/list` cases with
  lists of megabytes still pay (28% and 23% of that program): Go neither
  scans nor clears a slice of integers. The note needs the element type
  at the places that make a list (twenty routines, which share their code
  for all types and get no type), and a value found free of addresses at
  one collection cannot be assumed so at the next: a list is filled after
  it is made, and the library writes addresses into strings of zeros
  (`Process._take`). The loop that reads is six instructions a word; only
  reading less would help.
- **Collections stop the program.** There is one thread; a collection
  takes the time to scan what is live and to sweep.

## The pinned benchmark programs

The 16 programs of the pinned tree's `benchmarks/alchem` (15 that measure
and `hello`), each run by the pinned compiler and natively one after the
other on a machine busy with other work (wall seconds for the whole
program, the pinned figure with its compilation of about half a second;
then, for the suites, the sum of the medians each case prints). "Native
before" is what the compiler of 9e1af1b did under a 40 second and 4 GB
ceiling; only `restart` was timed with it (8.1 s):

| Program | Pinned | Native before | Native now | Medians: pinned | now |
| --- | --- | --- | --- | --- | --- |
| hello | 0.46 | under 40 | 0.03 | | |
| build | 0.77 | under 40 | 0.05 | | |
| compute | 0.81 | under 40 | 0.11 | | |
| echo | 1.08 | under 40 | 0.37 | | |
| spawn | 1.11 | under 40 | 1.13 | | |
| restart | 1.15 | 8.1 | 6.57 | | |
| state | 0.77 | killed (memory) | 0.10 | | |
| suite/control | 3.01 | under 40 | 2.91 | 0.206 | 0.206 |
| suite/numbers | 3.27 | under 40 | 45.25 | 0.261 | 4.648 |
| suite/processes | 8.69 | under 40 | 11.02 | 0.853 | 1.146 |
| suite/list | 2.13 | killed (memory) | 2.85 | 0.167 | 0.309 |
| suite/string | 3.30 | over 40 | 32.60 | 0.283 | 3.546 |
| suite/otp | 25.05 | killed (memory) | 35.11 | 2.775 | 3.868 |
| suite/calendar | 6.42 | over 40 | 274.91 | 0.542 | 30.039 |
| suite/enum | 5.54 | over 40 | 26.18 | 0.500 | 2.794 |
| suite/map_set | 7.21 | killed (memory) | 37.33 | 0.690 | 4.159 |

"Killed" is the 4 GB ceiling of `scripts/limited`: four of the seven that
did not finish in 40 seconds were ended for memory, not time. What changed
them: memory given back (state, list, otp, map_set), the loops of the
process library (otp: 10,000 tasks at once), maps as trees (state: 50,000
puts in 20 ms where they took 5.6 s; enum's `group_by` and `frequencies`;
map_set), and `Enum.uniq` over a map of what it has seen for elements with
an order (a million integers; it went through the list of those kept for
every element).

What is still slow, by the cases the suites print (pinned and native
medians of one quiet run, microseconds), and why it was not closed here:

- **calendar**, every case 20 to 300 times the pinned figure (`date.add`
  1M: 43,000 and 1,140,000; `date sort` 100k: 91,000 and 5,900,000;
  `naive_date_time.add` 1M: 38,000 and 2,700,000). The date library is
  written in Alchem over structs and does its arithmetic through general
  library calls; no single cause was found in the time there was. Sampled (`ptrace`, a sample a millisecond; `perf` is not
  permitted here, `perf_event_paranoid` 4), `Date.add` spends 46% in one
  function of 981 bytes and 10% in another: the library does Go's
  `time.Date` arithmetic in closed form, but over a list of seven fields
  read with a call each and through checked helper calls for every
  operation, about a microsecond a date. Closing it means rewriting the
  date library's inner layer over plain integers, which was not done.
- **numbers**: `float.to_string` 200k (11,000 and 320,000), `float.parse`
  and `String.to_float` (7,000 and 1,130,000), `bitwise mix` 1M (2,400 and
  880,000). The float runtime converts exactly with integers of 1152 and
  4096 bits for every value (`spec/float-x86_64.s`), where Go takes a fast
  path for the common ones: not touched. The `Bitwise` functions went bit
  by bit through division; they are now the inline operators
  (`library/Bitwise.alc`), checked against the pinned runtime for every
  pair of eleven values and fifteen shift counts.
- **string**: `<>` in a loop (above); `String.split` on whitespace (2,300
  and 640,000), `String.slice` (41,000 and 245,000), the regular
  expressions (4,000 to 60,000 and 170,000 to 780,000: a matcher written
  in Alchem against Go's compiled one).
- **restart**: 315 microseconds a restart where the pinned runtime takes 9;
  the same before this work (8.1 s).
- Allocation was measured again on a quieter machine and costs about what
  it did: 100 million tuples of two words take 0.9 to 1.5 s with the hook
  and collections (9 MB resident) against 0.8 s and 0.65 s of page faults
  without (2.3 GB resident; the pinned runtime about 0.5 s), and 20
  million `Integer.to_string` 0.42 to 0.47 s against 0.51 to 0.64 s. The
  slower `numbers` and `control` cases of the table above were the
  machine's load at the time, not the hook (an earlier version of this
  note said 25 nanoseconds a value; that was wrong).

