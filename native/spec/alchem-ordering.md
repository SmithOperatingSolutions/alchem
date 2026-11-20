# The order of values

The pinned language orders integers, floats, strings, booleans and atoms, and
lists and tuples of one or more parts built from them (`Orderable` in its
checker). Options, results, maps, structs, sum types, ranges, functions and
the empty tuple have no order. The operators `<`, `<=`, `>` and `>=` take
only integers, floats, strings and atoms; the wider order belongs to the
library: `Enum.sort/1`, `sort/2` with `:asc` or `:desc`, `max`, `min`,
`min_max`, `sort_by`, `max_by`, `min_by`, `min_max_by`, `List.keysort` and
`min`/`max` of two values. A call whose type has no order is rejected
(`Enum.sort needs values with an order ...`); natively, as every compile
error, `E_COMPILE`.

| Type | Order |
| --- | --- |
| integer | by value |
| float | IEEE `<`: a NaN is neither less nor more than anything |
| string, atom | by bytes, a proper prefix first (an atom by its name) |
| boolean | `false` before `true` |
| tuple | part by part: the first part in which one is less decides |
| list | element by element the same way, then the shorter first |

## How it is compiled

The compiler makes the order for the type, as it makes equality
(`alchem-generics.md`). `native-ordering.alc` builds, for a type, a piece of
code that takes two values in RDI and RSI and leaves -1, 0 or 1 in RAX: the
pinned `less(x, y)`, `less(y, x)` pair in one pass. A tuple compares its
parts in turn and stops at the first that is not 0; a list does the same over
the common length and then compares the lengths. Because a NaN gives 0, the
pieces compose exactly as the pinned functions do.

A generic function is compiled once and takes one hidden argument per type
variable, its comparator. The comparator now answers both questions: it is
called with 0 in RDX for equality (1 or 0 in AL) and with 1 for the order (-1,
0 or 1 in RAX). The constants stay as they were: 0 compares and orders words
(integers, booleans), 1 strings and atoms, 12 floats. For a list or a tuple
the comparator of an ordered variable is code holding both pieces behind a
test of RDX: placed at the call behind a jump when the type mentions no type
variable, so nothing is allocated per call, and a function value holding the
caller's comparators when it does (the question is its third parameter). Only a
variable that needs the order gets such a comparator; every other variable
keeps the equality-only one, and struct and sum type equality functions take
those in registers or, past six, in an array, as before.

Which variables need the order is said in the library's source: in a
function of the library written in Alchem (`library/*.alc`) a type variable
whose name starts with `ord` is ordered. A call of such a function must give
the variable a type with an order, or one of the caller's own ordered
variables, else the call does not compile (and a name with several forms
tries its next form). Inside such a function `<`, `<=`, `>` and `>=` on
values of an ordered variable, or of a list or tuple built from them, are the
three-way comparison tested against 0: `x < y` is `less(x, y)`, `x <= y` is
`not less(y, x)`. A program's own functions get none of this: there `<` on a
type variable, a tuple, a list or a boolean is rejected, as the pinned
compiler rejects it, whatever the variable is called.

## The library

Each ordered function is one generic entry over a list or a stream of `ord`
in `library/Enum.alc`,
`library/List.alc` and `library/Kernel.alc`; the forms per element type are
gone. `min` and `max` of two integers, booleans, strings or floats are still
the compiler's own code, and fall back to the library entry for atoms, lists
and tuples.

Sorting is the pinned runtime's own algorithm, because its result shows
whenever the comparison is no order: a sorter function that is not one, and
floats with NaN. `Enum.o_stable(list, less)` and `Enum.o_unstable(list, less)`
are compiler forms, for the library alone, that copy the list's elements
side by side into the result's block, sort them there and spread them into
its pairs (`alchem-lists.md`, which also has `Enum.o_room` and
`Enum.o_turn`), with Go 1.27.4's `stable_func` (insertion sort over blocks of
20, then SymMerge: `slices.SortStableFunc`, `sort.SliceStable`) and
`pdqsort_func` (`sort.Slice`), asking the function value for the same pairs
in the same order. The routines are `spec/sort-runtime.c`, kept as the
assembly gcc made of it (`spec/sort-stable-x86_64.s`, 1,250 bytes, and
`spec/sort-unstable-x86_64.s`, 2,770 bytes) and as checked byte literals in
`native-sort-data.alc` (`scripts/generate-sort-runtime.py`); a routine is
placed in the one library function that uses it. They use no frame of their
own and keep RBP and R12 to R15, so a failure in the function they call is
traced as before. A sort takes one copy of the list, where the merge sort
written in Alchem took a list per pass and the stable sort written in Alchem
exhausted the arena near 2,000 elements.

- `Enum.sort/1`, `sort/2` with a direction, `sort_by` and `List.keysort`
  sort stably by `less`; `:desc` turns `less` round, so equal elements keep
  their order in both directions. Keys are made once, in order, before
  anything is compared, and a wrong direction fails before any key is made.
- `Enum.sort/2` and `sort_by/3` with a sorter ask it as the pinned comparison
  does: `sorter(y, x)` first, and `sorter(x, y)` only when that was true.
- `max`, `min`, `min_max` and the `_by` forms keep the first least element;
  the `_by` forms call the key function for both elements at every
  comparison, the new element first.
- `List.sort` (integers, floats and strings only) is `sort.Slice` by
  "greater" over the list as the pinned runtime holds it, the last element
  first; with NaN it leaves what pdqsort leaves.

## Enumerables

Every ordered function takes a list, a map (its `{key, value}` pairs), a
set, a range or a stream, as upstream. The forms that take a list (`sort`,
`sort_by`, `min_max`, `min_max_by`) are given the others as the list of
their elements (`alchem-sets-streams.md`), which is when the pinned function
too reads everything before it compares or calls a key function. `max`,
`min`, `max_by`, `min_by` and their forms with a sorter or a fallback are
written over a stream and read it as the pinned runtime does: one element,
then the comparison with the best so far, so that what a stream writes while
it is read and what the key or sorter function writes come out in upstream's
order. `List.sort` and `List.keysort` take a list and nothing else.

## Map keys

The map and set routines order and compare keys that are tuples with the
same comparator: `nq_static` gives a tuple of key types the two-question
code whether or not a variable asked for its order, `od_keyed` places it
where a map of a known key type is used, and `map_key` in
`spec/collections-x86_64.s` calls it with 0 in RDX to find a key (so a NaN
inside a key equals nothing) and with 1 to sort. A tuple key has no bound
on its size or nesting.

## Failures

A failure inside the library (`empty error`, a wrong direction) is named
where the program called the library, and the library's own calls are not
shown (`alchem-system.md`: the call notes its position in its frame, and the
trace routine skips the library's frames):

```
<stdin>:6:6: empty error
  at M.main (<stdin>:5)
```

A reference such as `&Enum.max/1` notes the position of its `&` the same
way, which is what upstream names when the function it refers to fails.

## Checked against the pinned compiler

`harness/ordering.py`: 1,500 programs and more, each with the pinned
compiler's status, output and trace (`scripts/generate-ordering-cases.py`
makes them): 24 element types by hand and 150 drawn at random to depth 3,
through every ordered function and option; lists, maps, sets, ranges and
streams, with what a stream and the function write as one is read and the
other called; tuple keys of 45 parts; a regex where an order is needed; empty
input and wrong directions; duplicates and stability; lists longer than the
blocks of the stable sort; NaN, infinities and both zeros in every position;
the order in which key and sorter functions are called; references
(`&Enum.sort/1`, `&max/2`) and pipes; failures inside key functions; three
million calls with a compound order; and the programs the
pinned compiler rejects: types without an order through every function,
`<` on compound values and booleans, and the order of a type variable in a
program's own generic function. The two sort routines were also run against
Go 1.27.4's `slices.SortStableFunc` and `sort.Slice` on 400 lists of up to
5,000 floats with NaN: the same words in the same places.

## Differences that remain

- The ordered functions allocate in the arena, which is never reclaimed: a
  sort takes a copy of the list and a function value or two, `max` and `min`
  an iterator and a record each time a better element is found. A long loop of such calls
  takes memory in proportion (360 bytes for a call of `max` on four integers, 3.6 GB for
  ten million of them in the 16 GiB an ordinary program reserves, `alchem-tail-calls.md`)
  where the pinned runtime collects its garbage.
- A library module is told by its name, which starts with `Alchem`, so a
  program's own module named that way would be taken for one; the pinned
  language reserves no such name.
