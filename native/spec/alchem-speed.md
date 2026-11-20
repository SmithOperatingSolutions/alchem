# Speed

What was done so that the pinned tree's benchmark programs
(`benchmarks/alchem`, 16 programs) take about the time the pinned compiler's
programs take, with the same output. `harness/speed.py` holds 15 programs
(3,764 lines of output as the pinned compiler writes them) for everything
here whose behaviour could differ. The table of times is at the end.

## The compiler (`native-speed.alc`, prefix `vs_`)

- **An integer literal is one instruction.** A literal of more than three
  digits was made as the program ran, digit by digit: `xor eax,eax`, then
  `imul rax,10; sub rax,d` for each digit, and a `neg`: thirteen
  multiplications for `1099511627776`, in every place a constant stood.
  `vs_literal` works the 64 bits out from the digits (bytes, lowest first:
  the compiler's dialect has no division) and emits `mov rax,imm32` or
  `mov rax,imm64`.
- **The left operand waits in RCX when the right one is plain**
  (`vs_pair`): a constant or a slot of the frame, which is one instruction
  that touches nothing else. It waited on the stack for every operand
  (`push rax` ... `pop rcx`), a store and a load in the path of every
  operation.
- **Division and remainder by a constant** (`vs_binary`, `vs_divide`). By a
  constant that is neither 0 nor -1 nothing can fail, so the two checks go.
  By one from 2 up to 2**62-1 the quotient is a product (Granlund and
  Montgomery): with `l` the least for which `2**l >= d` and
  `m = 2**(63+l)/d + 1`, `n/d` is the high half of `n*(m-2**64)` plus `n`,
  shifted right `l-1` bits, plus one for a negative `n`. `m` is found by
  long division, a bit at a time. The remainder is `n - (n/d)*d`.
- **A condition that ends in a comparison of two integers jumps on the
  flags** (`vs_test`, for `if` and `cond`): `cmp; jcc; jmp` where there was
  `cmp; setcc; movzx; test; je`. The test stays where it was, because a
  condition joined with `and` or `or` jumps to the end of the condition
  with its value made.
- **`Bitwise.band`, `bor`, `bxor`, `bsl`, `bsr` and `bnot` of integers are
  the operators' code where they are called** (`vs_or`, in front of the
  library's lookup; a piped value included). The operators give what the
  library's functions give for every count, a negative one and one of 64
  or more included. Anything else under the name (another number of
  arguments, another type, `&Bitwise.band/2`) goes the usual way.
- **`floor`, `ceil`, `trunc` and `round` of a float to an integer are in
  line** when the processor's own conversion says the value fits
  (`vs_whole`): `cvttsd2si`, and what is left of the value past its whole
  part, which is exact, moves the result: its sign for `floor` and `ceil`;
  twice it, truncated, for `round`, which is 1 or -1 from a half on. A
  value that does not fit (the conversion gives the least integer) calls
  the float runtime as before, which says what is wrong.

## The float runtime

Text and parsing are Go 1.27's unrounded scaling (`alchem-floats.md`, which
has the comparison with Go: 68 million texts, 12 million parses).

## The library

- **Dates and times** (`library/Date.alc`). The shared layer does Go's
  `time.Date` arithmetic so that a moment out of the 584 thousand million
  years a `Time` has wraps as Go's does: sums and products modulo 2**64
  made of checked steps (a product by doubling, a call per bit), over a
  list of seven fields read with a call each. One `Date.add` took a
  microsecond. Now fields within 2**31 of zero (with days moved within
  2**40 and microseconds within 2**60) are computed in plain arithmetic:
  `yj` is the day number of a year, any month and any day, `yd`, `yn` and
  `yt` the structs of a day number and the microseconds of a day, and
  `Date.add`, `diff`, `compare`, `day_of_week`, `end_of_month`,
  `NaiveDateTime.add` and `diff`, `DateTime.from_unix`, `to_unix`, `add`
  and `compare` go from struct to struct without a list. Anything else
  takes the way that was there, unchanged, and the shared list functions
  (`zm`, `zs`, `ze`, `cv`, `cl`, `cj`) take the plain way themselves for
  such fields, so `shift`, `strftime`, zones and `Time` gain too.
  Text of the usual shape is written into a fresh string eight bytes at a
  time and read from its bytes; any other shape (a one-digit hour, a comma,
  more than six digits of a fraction, a year past 9999, anything invalid)
  goes the way that was there.
- **`String.split/1`** walks the text once (Go's `strings.Fields`); it
  replaced each of 24 white space characters by a space, one pass each.
- **`String.split/2` and `String.replace/3`** (`spec/library-x86_64.s`)
  compared the whole separator at every byte with `repe cmpsb`, and
  `replace` appended each byte that did not match with a call and a
  `rep movsb` of one byte. They compare in full only where the first byte
  matches, append what lies between two matches at once, and copy short
  pieces with a plain loop.
- **`String.slice`, `at`, `first`, `last` and `reverse`**
  (`spec/graphemes-x86_64.s`): an ASCII byte other than a carriage return,
  before another ASCII byte or at the end, is a cluster by itself and is
  no longer given to the cluster routine.
- **Regular expressions** (`library/Regex.alc`). The search tried the
  program at every character by halving the text (the library was written
  under the compiler dialect's rule of no loops; a function's call to
  itself in return position is a loop in the library now). It goes through
  the text once and, for a program that starts with a byte, from one place
  that holds that byte to the next (`Sys.find`), with the second byte
  looked at too when there is one. Backing off a run (`tr`) and running
  one (`re`) are loops, a class reads both ends of a range with one load
  (`ic`), and a run of a class looks an ASCII byte up without decoding it
  (`rc`). The whole match is no longer run again for its groups (`rx_sp`
  is told where the match stops).
- **`Enum.sort/1` of integers and of strings** uses the pinned runtime's
  unstable sort (`Enum.o_unstable`), which asks about half as often as the
  stable one: values of these types that are equal are the same value, so
  the result is the one the stable sort gives. Every other type keeps the
  stable sort (two floats that are equal, 0.0 and -0.0, are not the same).
- **`Enum.frequencies`, `Enum.uniq` of integers and of strings and
  `Enum.group_by` with integers for keys** count, tell apart and group
  through a table in mapped memory (`h_new` and the functions after it at
  the end of `library/Enum.alc`) and make the map once, from the keys in
  order, where they put into a map once per element. The keys of
  `group_by` are worked out before the table is made, so nothing of the
  program runs while it stands.
- **`MapSet.new` of integers and of strings** sorts the different elements
  and hands them over in order; **`Map.merge` and `MapSet.union`** of maps
  with integer or string keys go through both sides' entries once, in
  order, unless the second is less than an eighth of the first.
- **The links of a process** (`library/Process.alc`, `_pair`, `_lcut`,
  `_lhas`): a link is two cells that know each other and their place, so
  it is taken out in one step. A process with ten thousand linked tasks
  walked its list for every task that was linked and again for every one
  that ended.
- **`List.duplicate`** puts eight elements at a time.

## What is still slower, and why

Measured as the table says; "times" is native over pinned.

- **`restart`** (about fifteen times). A process that fails has its trace
  written before it ends, because `Process.report` may ask for it later:
  the program forks, and the copy fails in earnest into a pipe
  (`Process._trace`, `alchem-processes.md`). `strace -c` of the 20,000
  restarts: 2.5 s in `fork` (127 microseconds each: the program has 16 GiB
  of arena and a gigabyte of stack per process reserved), 2.1 s in `wait4`,
  23 `write` and 12 `read` per failure for the trace's pieces, of 7.2 s in
  all. The pinned runtime recovers a panic in the same thread. Without the
  fork the trace has to be written into memory by the trace routine itself
  and control has to come back from it; that routine
  (`spec/trace-x86_64.s`) ends the program by design and was not mine to
  change in this work. A copy that shares memory (`vfork`) is no way out:
  it returns through the frames the program still needs.
- **Maps that are put into one element at a time** (`map.put` in a loop,
  `Map.update`, `Map.new` of pairs out of order, `MapSet.put`: four to
  sixteen times). Every `Map.put` copies the nodes on the way to the entry
  (`alchem-memory.md`); the pinned runtime writes into the map a fold owns.
  The routines are in the collector's blob (`spec/memory-x86_64.s`), which
  another piece of work had in hand. `Map.new` is the compiler's own call,
  so the library cannot hand it sorted pairs as it does for `MapSet.new`.
- **`acc <> piece` in a loop** copies the string every time
  (`alchem-memory.md`); also another piece of work.
- **`list -- list`** (nineteen times for 1,000 from 10,000) looks through
  the left list for every element of the right one, in machine code
  (ten million steps in 5 ms); the pinned runtime counts through a map.
- **`List.replace_at`, `update_at`, `insert_at`** copy the list, as the
  pinned runtime does, into pairs of 16 bytes an element where Go's slice
  has 8: three to four times.
- **Regular expressions with groups** (`Regex.run`, `named_captures`: four
  to five times). The matcher is a backtracker written in Alchem that
  goes down a call per instruction and returns two positions; the groups
  are read by running the match again per group. Go compiles the pattern
  to a one-pass or bit-state machine.
- **A call of a function value per element** (`Enum.reduce` and
  `Enum.count` over a range or a list with a small `fn`, `float
  arithmetic`, `cond`: two to five times where the pinned figure is a
  nanosecond or two an element). Go's compiler puts the small function
  into the loop; here each element is a call through the function value
  with a frame of its own (stack check, sixteen slots, the statement's
  place stored for a trace), about 6 ns.
- **`task.async_stream` with a limit above one** takes the same processor
  time as the pinned program but more time on the clock: there is one
  thread (`alchem-processes.md`).
- **Date and time fields beyond 2**31** (an hour of 2,562,047,788 or more,
  microseconds beyond 2**40) fail with `integer overflow` in several
  functions where Go normalises field by field: the exact way forms the
  microseconds of the day in one product. That was so before this work
  and is unchanged; `harness/speed.py` holds 630 probes of far fields that
  do agree.
