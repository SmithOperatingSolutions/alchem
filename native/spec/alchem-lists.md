# Lists that do not copy

A list was its length and its elements side by side, so `[x | acc]` copied
the whole list and the `t` of `[h | t]` copied the tail: a loop that built or
walked a list of n elements took about 4n² bytes, none of them given back
(`alchem-tail-calls.md`). Now taking a tail takes nothing, putting an element
before a list takes 16 to 64 bytes and no copy in a loop, and the library's
functions that build a list element by element are linear. Every result is
the pinned compiler's, as before.

## The layout

A list value is one word: the address of a **pair**. A pair is two words, the
number of elements from here to the end of the list and the element; the
next pair holds one element less, and after the last pair stands the count 0
alone.

```
        -16      -8       p        +8       +16      +24            16n
 ...  [ below ][      ][   n   ][ e0    ][  n-1  ][ e1    ] ...  [   0   ]
                         ^ the list            ^ its tail
```

- `[p]` is the length. Element i is the word at `p + 8 + 16*i`.
- The tail is `p + 16`; the list without its first k elements `p + 16*k`,
  for every k up to the length (the address of the closing 0 is the empty
  list that ends this one). Nothing is allocated for any of them.
- `[p - 16]`, the word *below*, says whether the block the list lies in has
  an unclaimed pair there: **0** means it has, and the list may be extended
  downward in place; anything else means it has not.

A **block** is what one allocation holds: the word -2, a word of padding, the
pairs, and the closing 0. A block made for exactly n elements is `24 + 16n`
bytes; `[p - 16]` of its first pair is the -2. A block made with room has
its unclaimed pairs between the -2 and the first pair in use; they are zero
because the arena is zero until it is written, and no pair in use holds a
count of 0 (the count of a pair is at least 1). `[]` is a constant in the
program's code: the three words -2, padding, 0, and the address of the 0;
it takes no memory at run time and is never written.

The invariant every routine keeps: for a list p, the pairs from p up are
never written again, by anyone. The only write into an existing block is
into a pair whose count word is 0 with a list directly above it (and
`Enum.o_turn`, below, which the library uses on a list nobody else has).

## Putting an element before a list

`[x | list]` (`nl_cons` in `spec/collections-x86_64.s`):

- if `[p - 16]` is 0: write `n + 1` there and x beside it, and the new list
  is `p - 16`. The pair is claimed by the write: a second `[y | list]` on
  the same list finds `n + 1` there, not 0, and takes the other way. The
  two instructions that test and write are not separated by a call, and a
  program is one thread (`alchem-processes.md`), so two processes cannot
  both claim a pair;
- otherwise: a new block of `2n + 4` pairs (`16(2n + 4) + 24` bytes), as the
  pinned runtime's `listPrepend` takes `cap = 2n + 4`: the new pair on top
  of a copy of the n pairs (the copy is of the words as they are: the counts
  of a list's pairs do not depend on what stands before them), and `n + 3`
  unclaimed pairs below.

So of the lists that share a block only the one that starts at the lowest
pair in use can grow in place, and it can do so once; a list others share
from below, a tail, the result of `Enum.drop`, a list made at its exact
size, and `[]` are copied when an element is put before them, once, and the
copy then grows in place. `[a, b, c | list]` puts c, then b, then a.
n elements put before `[]` one at a time fill blocks of 4, 12, 28, ...,
`2^(k+3) - 4` pairs: at most 64 bytes an element in all, 32 when the last
block is just full.

This is what the pinned runtime does (`compiler/codegen.go`: a list is a Go
slice with its head last and a claim counter; `listPrepend` extends in place
when it wins the claim and copies with `2n + 4` otherwise; a tail is a
reslice), and it costs what it costs there: putting an element before a
list that is shared from below copies it, in both.

## What was weighed

- **A view**: a list as a small record (count, address of the elements,
  owner) over a shared block. A tail is then a new record of two or three
  words: 16 to 24 bytes for every step of a walk by `[h | t]`, and nothing
  is ever given back, so walking ten million elements would keep 240 MB of
  records. Putting an element in front needs the block's lowest used slot
  kept somewhere both views can see, and every reader loads the address of
  the elements before it reads one.
- **Cells** (an element and the address of the next cell): tail and prepend
  are trivial, but the length and element i are a walk, and `Enum.at`,
  `length`, `list[i]`, the sort, `for`, the stream iterator and every
  routine that reads a list by index would change their cost or their
  shape.
- **Counted pairs**, chosen: the count of what remains stands beside each
  element. A tail is an address and takes nothing; the length is still
  `[p]`, element i is still one load, and the code that reads a list changes
  only its step from 8 to 16. The count of a pair does not depend on what
  stands before it, so a list is extended downward without touching what is
  there, and a copy is a copy of words. The price is 16 bytes an element
  where there were 8, and a builder that knows its length only at the end
  writes the counts in a second pass. Appending in place is not possible
  (the counts of all pairs would change): a list is built from its end, or
  written at once.
- **0 for an unclaimed pair** against a marker written into the room: a
  marker has to be written into every unclaimed pair when the block is
  made, which touches all of a block of which half may never be used
  (512 MB resident for ten million prepends against 408 MB), and 0 costs
  nothing. A word that is not 0 where room should be (the arena is only
  ever moved forward, so this does not happen) would make the list copy,
  never overwrite.

## Reading a list: the idioms

Machine code, a list in RSI:

```
mov (%rsi),%rcx          # the length
mov 8(%rsi),%rax         # the first element (when rcx > 0)
add $16,%rsi             # the tail: walk until the count is 0, or rcx times
shl $4,%rdx ; mov 8(%rsi,%rdx),%rax   # element rdx (rdx < rcx)
```

Library code over raw words, a list at address `p`:
`Sys.peek(p)` is the length, `Sys.peek(p + 8 + 16 * i)` element i,
`p + 16` the tail and `Sys.peek(p) == 0` the end. (No library code reads a
list this way today: `Sys.addr` is only taken of strings, and
`Process.__word`/`Process.__any` pass a list on as a word.)

A walker driven by a type description reads a list node as: count at `[v]`,
elements at `[v + 8]`, `[v + 24]`, ..., `[v + 8 + 16*(count-1)]`.

## Making a list

A list is made only by these, and code that makes one by hand must do the
same: reserve `24 + 16n` bytes at R12 (exit 71 past R13), write -2 at the
start, the count `n - i` and element i into pair i at `start + 16 + 16*i`,
and 0 after the last pair; the list is `start + 16` (`arena_list` in
`spec/collections-x86_64.s`, `list_arena` in `spec/library-x86_64.s`; pairs
may be written in any order before the list is given to anyone). A builder
that learns its length m at the end (`Enum.filter`, `for ... uniq: true`,
`--`) reserves for the most it can need, writes the elements into the first
m pairs, then the counts m..1 and the 0; the pairs behind it stay unused.
The word 16 below the first pair must not be 0 unless the pair below is
really free.

## What each operation takes

| Operation | Bytes |
| --- | --- |
| `[]` | 0 |
| `[a, ..., z]`, `Enum.map`, `Enum.reverse`, `for` (its result), `Enum.sort` and the other sorts, `Map.keys/values/to_list`, `String.split`, `Integer.digits`, `System.argv`, a stream or range read into a list | `24 + 16n` for the n elements of the result |
| `Enum.filter`, `for ... uniq: true`, `a -- b` | `24 + 16n` for the n elements of the input |
| `a ++ b`, `Enum.concat(a, b)` | `24 + 16(m + n)`: both are copied |
| `[h \| t]` and `[a, b \| t]` as patterns, `tl`, `hd`, `length`, `Enum.at`, `list[i]`, `Enum.reduce`, `Enum.sum`, `in`, `==`, comparison, `inspect` | 0 (`Enum.at/2` and `Enum.fetch` box their option: 16) |
| `Enum.drop`, and `Enum.slice`/`Enum.take` of a part that ends where the list ends | 0: the result is the address of its first pair |
| `Enum.take`, `Enum.slice` of another part | `24 + 16n` for the n elements taken |
| `[x \| list]` | 0 when the pair below is unclaimed, else `16(2n + 4) + 24` |
| `first..last` as a list | `48 + 16n`: the block, then first, last and step |

The sorts sort the elements side by side at the start of the result's own
block and then spread them into its pairs from the last one down
(`od_builtin`), so a sort takes the result and nothing more.

A range that was read as a list is that list with `first`, `last` and
`step` in the three words after the closing 0 (`p + 16n + 8`, `+16`,
`+24`); an unread range is still the four words `0, first, last, step`, so
the fields are at `p + 16*[p] + 8` on in both.

## The library's builders

Two forms for the library alone (`od_room`, `od_turn` in
`native-ordering.alc`; a program cannot call a name that starts with `o_`):

- `Enum.o_room(n)`: an empty list on top of a block with n unclaimed pairs,
  so that the next n elements put before it are written in place.
- `Enum.o_turn(list)`: the list with its elements in the opposite order,
  written where they lie (the counts stay as they are). Only for a list the
  calling function built itself and has given to nobody: the functions below
  build from `[]` or `Enum.o_room`, by `[x | acc]` alone, and no function
  the program passed sees the list.

A builder puts each element before the ones it has and turns the list round
at the end; one that knows how long its list gets takes the room at once
and makes exactly one block. Several walk their list by `[x | rest]` with
what they carry in parameters (a call of a library function to itself is a
jump, `alchem-tail-calls.md`) where they made a tuple per element for
`Enum.reduce`. Functions the program passes are called for the same
elements in the same order as before, and a failure inside one is traced
as before. Rewritten this way:

- `Enum`: `flat_map` (now `concat` of `map`), `concat/1`, `intersperse`,
  `map_intersperse`, `dedup`, `dedup_by`, `uniq`, `uniq_by`, `with_index/1`
  and both `with_index/2`, `zip` (and through it `zip_reduce`), `zip_with`
  (no longer through a list of tuples), `split_with`, `chunk_every/3` (and `/2`, `/4`), `chunk_by`, `scan/2`,
  `scan/3`, `map_reduce`, `flat_map_reduce`, `map_every`, `take_every`,
  `drop_every`, `group_by/2,3` (each group is turned at the end),
  `chunk_while`, `reduce_while` (walks by `[x | rest]`; it sliced one
  element out per step), `shuffle` (a number of a sequence per element and
  one sort; it took an element out of the list per step).
- `List`: `duplicate`, `flatten`, `range`, `zip/2`, `zip/1`.
- `String`: `graphemes` (one walk: a grapheme is the first of a window of
  the bytes it starts, taken again from a window twice as long when fewer
  than four bytes, the room of the character that decides where it ends,
  follow it there; it sliced the text from its start for every grapheme),
  `codepoints` (one walk with `Sys.rune`), `jaro_distance`.
- `String.splitter/2` with several patterns (its pieces; the text is still
  split again for every piece), `Stream.chunk_every`, `Stream.chunk_by`,
  `Stream.uniq_by` (the chunk being filled and the keys seen are held last
  first), `Path.join`,
  `Keyword.validate`, `OptionParser.parse`/`parse_head`/`split`,
  `File.ls` (`Sys.names`), and `[x] ++ rest` written as `[x | rest]` in
  `Supervisor`, `DynamicSupervisor`, `Process` and `Kernel.prepend`.

## What changed, by routine

- `spec/collections-x86_64.s` (`native-collection-data.alc`): `arena_list`
  (new), `nl_pack`, `nl_at`, `nl_concat`, `nl_slice`, `nl_reverse`, `nl_sum`,
  `nl_map`, `nl_reduce`, `nl_cons` (new), `nm_entries`, `nm_new`.
- `spec/library-x86_64.s` (`native-library-data.alc`): `list_arena` (for
  `word_arena`), `na_digits`, `na_undigits`, `na_join`, `na_filter`,
  `na_argv`, `na_split`.
- `spec/integer-parse-x86_64.s` (`native-parse-data.alc`, the `inspect`
  walker): `ins_seq` (with `ins_pairs`, `ins_step`), `ins_list`, `ins_range`.
- `native-patterns.alc`: `np_tail` (four bytes: `add rax,16`).
- `native-comprehensions.alc`: `wc_cons` (`[... | rest]` is `nl_cons`; it
  was a list of the heads and `++`), `wf_loop`, `wf_listed`, `wf_uniq_emit`.
- `native-collections.alc`: `nl_empty` (new), `nl_list`, `nl_each`.
- `native-operators.alc`: `nk_range_emit`, `nk_range_field`,
  `nk_subtract_emit`, `nk_member`.
- `native-sets.alc`: `nn_range_stream`, `nn_list_stream`, `nn_iterator` (the
  iterator's record keeps the pair it stands at), `nn_all`, `nn_pairs`,
  `nn_set_type`.
- `native-equality.alc`: `nq_list`, `nq_code` (ranges).
  `native-ordering.alc`: `od_list`, `od_builtin`, `od_room`, `od_turn`.
  `native-sigils.alc`: `sg_index_list`. `native-floats.alc`: `ne_summed`.
  `native-records.alc`: `nd_resolve` (map keys, below).

Strings, bytes, tuples, maps, sets, structs, options and function values
are laid out as they were; a map or a set is still its count and its pairs
side by side, and `Map.new`, `MapSet.new` and a map literal read their list
of entries through the new layout. The compiler's own source uses `bytes`
alone, whose routines share nothing with these but `Enum.count` and
`Enum.empty?` (the word at the address, for both).

## The measured charges

`harness/collection_memory.py` holds exact byte counts; the ones that hold a
list changed, each by what the table above says: `[]` 8 to 0, `[1000]` 16 to
40, `[1000,2000]` 24 to 56, `Enum.concat([1000],[2000])` 56 to 136 (40 + 40
+ 56), `Enum.reverse` 48 to 112, `Enum.slice([1000,2000],0,1)` 40 to 96,
`Enum.map`/`filter` 48 to 112, `Enum.reduce` 24 to 56, a map made from one
entry 64 to 88 (its list of one tuple is 40 where it was 16; the map itself
is unchanged) and with it `Map.get`, `Map.keys`, `Map.to_list`,
`Map.delete`, `Integer.digits(123)` 32 to 72, `Integer.undigits([])` 8 to 0,
`Enum.join` of two strings 88 to 120. New cases there: a slice and a drop
that end where the list ends take nothing, `[1000 | [2000]]` and
`[1000, 3000 | [2000]]` take 160 (the list of one, 40, and one block of
`2*1 + 4` pairs, 120), `[1000 | []]` 88. The other measured-charge gates
(`arena_limits.py`, `options.py`, `string_library.py`,
`boolean_library.py`, `native_memory.py`) hold no list and are unchanged.

`harness/lists.py` measures the linear charges: 100,000 elements put before
`[]` take 4,193,576 bytes (15 blocks; the bound is 64 an element), 131,068
the same, 200,000 take 8,387,840; walking them by `[h | t]`,
`[h, _, _ | t]`, `tl`, `Enum.drop` or a slice of the end takes nothing more;
`Enum.with_index` and `Enum.zip` of 100,000 take 40 an element (the pair
and a tuple), `Enum.dedup` and `Enum.scan` 16, `Enum.flat_map` to lists of
two 104, `Enum.chunk_every` by four 26, `String.graphemes` 57 a byte.

## Gates

`harness/lists.py`: 17 programs written by hand with the pinned compiler's
output and traces (two prepends onto one list, onto tails and tails of
tails, lists in closures, maps, structs and tuples, sent between processes,
in `for` and `reduce`, across the lengths at which a block is full, onto
what every maker of lists gives, the library's builders, failures inside
them), 18 programs the pinned compiler rejects (among them a list as a map
key and a program that calls `Enum.o_room` or `Enum.o_turn`), 300 random
programs of ten
scenarios each (`harness/list-cases.json.xz`, made by
`scripts/generate-list-cases.py`: a scenario makes about thirty lists from
one another and prints all of them at its end, so a write into a neighbour
shows), and the charges above. A further 1,200 programs of the generator
(12,000 scenarios) agree with the pinned compiler; with the test for an
unclaimed pair broken on purpose (any pair that is not the block's first
taken as free), 40 of 40 differ.

## Measured against the pinned compiler

Peak resident memory and time of one run through `scripts/limited` (6 GB,
120 s), by `scripts/benchmark-lists.py`; "before" is the compiler of commit
3f875b9. 7 MB is what an empty program shows. "killed" is the 6 GB ceiling.
The times are of single runs on a machine that was busy: differences of a
few hundredths of a second say nothing.

| Program | Elements | Pinned | Before | Now |
| --- | --- | --- | --- | --- |
| `Enum.dedup` | 10,000 | 7 MB, 0.01 s | 96 MB, 0.08 s | 7 MB, 0.02 s |
| `Enum.dedup` | 100,000 | 8 MB, 0.03 s | killed | 7 MB, 0.03 s |
| `Enum.dedup` | 1,000,000 | 45 MB, 0.06 s | killed | 46 MB, 0.06 s |
| `Enum.chunk_every` | 10,000 | 7 MB, 0.02 s | 43 MB, 0.04 s | 7 MB, 0.03 s |
| `Enum.chunk_every` | 100,000 | 8 MB, 0.02 s | 4,242 MB, 1.54 s | 7 MB, 0.03 s |
| `Enum.chunk_every` | 1,000,000 | 59 MB, 0.10 s | killed | 51 MB, 0.09 s |
| `Enum.zip` | 10,000 | 7 MB, 0.04 s | 382 MB, 0.17 s | 7 MB, 0.05 s |
| `Enum.zip` | 100,000 | 7 MB, 0.06 s | killed | 7 MB, 0.07 s |
| `Enum.zip` | 1,000,000 | 36 MB, 0.07 s | killed | 61 MB, 0.06 s |
| `Enum.with_index` | 10,000 | 7 MB, 0.05 s | 382 MB, 0.20 s | 7 MB, 0.04 s |
| `Enum.with_index` | 100,000 | 10 MB, 0.04 s | killed | 7 MB, 0.06 s |
| `Enum.with_index` | 1,000,000 | 75 MB, 0.10 s | killed | 61 MB, 0.08 s |
| `Enum.scan` | 10,000 | 7 MB, 0.07 s | 382 MB, 0.17 s | 7 MB, 0.05 s |
| `Enum.scan` | 100,000 | 8 MB, 0.05 s | killed | 7 MB, 0.04 s |
| `Enum.scan` | 1,000,000 | 40 MB, 0.10 s | killed | 38 MB, 0.08 s |
| `Enum.flat_map` | 10,000 | 7 MB, 0.06 s | 763 MB, 0.35 s | 7 MB, 0.05 s |
| `Enum.flat_map` | 100,000 | 9 MB, 0.05 s | killed | 12 MB, 0.05 s |
| `Enum.flat_map` | 1,000,000 | 55 MB, 0.13 s | killed | 122 MB, 0.10 s |
| `Enum.intersperse` | 10,000 | 7 MB, 0.04 s | 763 MB, 0.32 s | 7 MB, 0.04 s |
| `Enum.intersperse` | 100,000 | 10 MB, 0.05 s | killed | 7 MB, 0.05 s |
| `Enum.intersperse` | 1,000,000 | 65 MB, 0.09 s | killed | 53 MB, 0.06 s |
| `Enum.take_every` | 10,000 | 7 MB, 0.02 s | 96 MB, 0.07 s | 7 MB, 0.02 s |
| `Enum.take_every` | 100,000 | 7 MB, 0.03 s | killed | 7 MB, 0.02 s |
| `Enum.take_every` | 1,000,000 | 35 MB, 0.07 s | killed | 30 MB, 0.06 s |
| `Enum.zip_with` | 10,000 | 7 MB, 0.02 s | 382 MB, 0.16 s | 7 MB, 0.04 s |
| `Enum.zip_with` | 100,000 | 7 MB, 0.04 s | killed | 7 MB, 0.03 s |
| `Enum.zip_with` | 1,000,000 | 33 MB, 0.06 s | killed | 38 MB, 0.07 s |
| `Enum.chunk_by` | 10,000 | 7 MB, 0.03 s | 213 MB, 0.11 s | 7 MB, 0.02 s |
| `Enum.chunk_by` | 100,000 | 8 MB, 0.04 s | killed | 9 MB, 0.04 s |
| `Enum.chunk_by` | 1,000,000 | 72 MB, 0.10 s | killed | 87 MB, 0.08 s |
| `Enum.map_every` | 10,000 | 7 MB, 0.03 s | 382 MB, 0.18 s | 7 MB, 0.01 s |
| `Enum.map_every` | 100,000 | 8 MB, 0.03 s | killed | 7 MB, 0.02 s |
| `Enum.map_every` | 1,000,000 | 42 MB, 0.05 s | killed | 38 MB, 0.09 s |
| `Enum.drop_every` | 10,000 | 7 MB, 0.06 s | 96 MB, 0.06 s | 7 MB, 0.04 s |
| `Enum.drop_every` | 100,000 | 7 MB, 0.05 s | killed | 7 MB, 0.03 s |
| `Enum.drop_every` | 1,000,000 | 36 MB, 0.08 s | killed | 30 MB, 0.05 s |
| `Enum.split_with` | 10,000 | 7 MB, 0.03 s | 191 MB, 0.08 s | 7 MB, 0.05 s |
| `Enum.split_with` | 100,000 | 7 MB, 0.03 s | killed | 7 MB, 0.02 s |
| `Enum.split_with` | 1,000,000 | 34 MB, 0.07 s | killed | 38 MB, 0.06 s |
| `Enum.map_reduce` | 10,000 | 7 MB, 0.05 s | 382 MB, 0.19 s | 7 MB, 0.02 s |
| `Enum.map_reduce` | 100,000 | 7 MB, 0.06 s | killed | 7 MB, 0.05 s |
| `Enum.map_reduce` | 1,000,000 | 37 MB, 0.05 s | killed | 61 MB, 0.08 s |
| `Enum.concat/1` | 10,000 | 7 MB, 0.04 s | 170 MB, 0.10 s | 7 MB, 0.02 s |
| `Enum.concat/1` | 100,000 | 10 MB, 0.05 s | killed | 7 MB, 0.06 s |
| `Enum.concat/1` | 1,000,000 | 75 MB, 0.14 s | killed | 66 MB, 0.08 s |
| `Enum.group_by` | 10,000 | 7 MB, 0.03 s | 96 MB, 0.05 s | 7 MB, 0.03 s |
| `Enum.group_by` | 100,000 | 7 MB, 0.05 s | killed | 13 MB, 0.03 s |
| `Enum.group_by` | 1,000,000 | 37 MB, 0.09 s | killed | 123 MB, 0.11 s |
| `Enum.chunk_while` | 10,000 | 7 MB, 0.03 s | 43 MB, 0.05 s | 7 MB, 0.01 s |
| `Enum.chunk_while` | 100,000 | 7 MB, 0.05 s | 4,246 MB, 1.52 s | 9 MB, 0.06 s |
| `Enum.chunk_while` | 1,000,000 | 34 MB, 0.11 s | killed | 87 MB, 0.08 s |
| `Enum.reduce_while` | 10,000 | 7 MB, 0.03 s | 7 MB, 0.01 s | 7 MB, 0.03 s |
| `Enum.reduce_while` | 100,000 | 7 MB, 0.03 s | 7 MB, 0.05 s | 7 MB, 0.03 s |
| `Enum.reduce_while` | 1,000,000 | 33 MB, 0.04 s | 53 MB, 0.07 s | 46 MB, 0.05 s |
| `List.duplicate` | 10,000 | 7 MB, 0.02 s | 382 MB, 0.17 s | 7 MB, 0.03 s |
| `List.duplicate` | 100,000 | 7 MB, 0.04 s | killed | 7 MB, 0.02 s |
| `List.duplicate` | 1,000,000 | 10 MB, 0.03 s | killed | 15 MB, 0.04 s |
| `List.flatten` | 10,000 | 7 MB, 0.03 s | 170 MB, 0.08 s | 7 MB, 0.03 s |
| `List.flatten` | 100,000 | 10 MB, 0.03 s | killed | 7 MB, 0.04 s |
| `List.flatten` | 1,000,000 | 77 MB, 0.12 s | killed | 66 MB, 0.06 s |
| `String.graphemes` | 10,000 | 7 MB, 0.04 s | 382 MB, 0.44 s | 7 MB, 0.01 s |
| `String.graphemes` | 100,000 | 8 MB, 0.04 s | killed | 7 MB, 0.05 s |
| `String.graphemes` | 1,000,000 | 47 MB, 0.13 s | killed | 54 MB, 0.11 s |
| `String.codepoints` | 10,000 | 7 MB, 0.08 s | 382 MB, 2.54 s | 7 MB, 0.07 s |
| `String.codepoints` | 100,000 | 8 MB, 0.05 s | killed | 7 MB, 0.05 s |
| `String.codepoints` | 1,000,000 | 45 MB, 0.09 s | killed | 31 MB, 0.07 s |
| `[n \| acc]` in a loop, then summed by `[h \| t]` | 20,000 | 7 MB, 0.03 s | 3,052 MB, 1.20 s | 7 MB, 0.03 s |
| `[n \| acc]` in a loop, then summed by `[h \| t]` | 100,000 | 7 MB, 0.03 s | killed | 7 MB, 0.04 s |
| `[n \| acc]` in a loop, then summed by `[h \| t]` | 1,000,000 | 18 MB, 0.06 s | killed | 31 MB, 0.05 s |
| `[n \| acc]` in a loop, then summed by `[h \| t]` | 10,000,000 | 207 MB, 0.20 s | killed | 408 MB, 0.27 s |
| `Enum.reverse` | 1,000,000 | 41 MB, 0.06 s | 23 MB, 0.04 s | 38 MB, 0.04 s |
| `Enum.map` | 1,000,000 | 42 MB, 0.06 s | 23 MB, 0.04 s | 38 MB, 0.05 s |
| `acc ++ [x]` in a loop | 10,000 | 8 MB, 0.10 s | 382 MB, 0.17 s | 763 MB, 0.28 s |
| `acc ++ [x]` in a loop | 20,000 | 9 MB, 0.28 s | 1,526 MB, 0.57 s | 3,053 MB, 1.03 s |
| `Enum.sort` | 1,000,000 | 50 MB, 0.13 s | killed | 46 MB, 0.49 s |
| `for` over a list, with a filter | 1,000,000 | 37 MB, 0.06 s | 19 MB, 0.03 s | 30 MB, 0.04 s |
| a mailbox of messages, sent and received | 1,000,000 | 18 MB, 0.08 s | 53 MB, 0.14 s | 53 MB, 0.13 s |

## Also changed on the way

- A map type whose key cannot be one (`map[list[integer], integer]`,
  `map[option[integer], string]`, `map[tuple[], integer]`, a struct, and a
  type variable in a program's own function or struct: `map[k, v]`) is
  rejected where it is written, as the pinned compiler rejects it ("map keys
  must be integers, floats, strings, booleans, atoms or tuples of them",
  `invalid type "map[k,v]"`); it was accepted in an annotation, a parameter
  and a field (`nn_set_type`, which did this for sets, and `nd_resolve`).
  The library still writes maps of a type variable.
- `Enum.split/2` with a negative count, `Enum.count_until/2` and
  `Enum.slice/2` with a range did not compile in a program that also called
  `Enum.max` or `Enum.min` (`Enum.max([1, 2])` and `Enum.split(list, 2)` in
  one program): they wrote `max(a, b)` and `min(a, b)`, and in such a
  program the library's own `Enum.max/2` and `Enum.min/2` stand in the same
  appended module, so the names meant those. They compare with `if` now
  (`harness/lists.py` has the programs).

## Differences from the pinned compiler that remain

- **A list cannot be a map key** in either compiler, so no program holds one.
- **`acc ++ [x]` in a loop is quadratic in both**, in time; here it also
  keeps what it copied: `16n²/2` bytes for n elements (764 MB at 10,000,
  3 GB at 20,000) where the pinned runtime's collector frees each copy
  (8 MB). It was `8n²/2` before. The left operand of `++` has to be copied:
  its pairs hold the counts of the list they are in. Nothing is given back
  because the arena is never reclaimed (`alchem-tail-calls.md` has why a
  collector cannot be had as things are); a program that appends in a loop
  should prepend and reverse, as the library now does.
- **16 bytes an element** where the pinned runtime's slice has 8 for an
  integer (16 for a string): a list of a million integers is 16 MB against
  8 MB. Blocks left behind when a list outgrows them are kept: putting n
  elements before a list one at a time keeps up to 64 bytes an element
  (408 MB resident for ten million, the pinned runtime 207 MB).
- **`Enum.sort` of a million integers takes 0.5 s against 0.2 s**: the sort
  is the pinned runtime's own algorithm (`alchem-ordering.md`) and asks a
  function value for every comparison, as before this change.
- **`Enum.group_by` and `Enum.frequencies` make a map per element**
  (`Map.put` copies the map, `alchem-collections-profile.md`): 123 MB for a
  million elements in four groups against 37 MB. The lists of the groups
  are linear now.
- **Functions of the library that rebuild their list at every step by
  design** are as they were, quadratic in the number of steps:
  `Keyword.merge/3`, `Registry.register` and `OptionParser`'s switches
  filter the whole list for a key at each step, `List.myers_difference`
  keeps a row per edit distance, `Enum.uniq`/`uniq_by` and `Stream.uniq`
  look a key up in a list (linear memory, quadratic time in the number of
  distinct keys), and `String.splitter/2` with a list of patterns splits
  the rest of the text again for every piece. What each of them needs is
  another structure (a map from the key, a search from an address in the
  text), not another list.
