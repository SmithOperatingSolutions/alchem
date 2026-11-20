# Sets, streams and lazy ranges

`set[T]` and `stream[T]` are types of their own in the self-hosted compiler,
with the pinned compiler's rules; `MapSet` and `Stream` are written in Alchem
(`library/MapSet.alc`, `library/Stream.alc`) over a few operations the
compiler gives the library alone. `harness/sets.py` and `harness/streams.py`
hold the programs with what the pinned compiler prints for each, failures and
traces included, and the programs it rejects. The compiler code is
`implementations/alchem/native-sets.alc`.

## Sets

- `set[T]` (type tag 25 and the element) is written in annotations, struct
  fields and signatures. `T` is a key type: an integer, float, string,
  boolean, atom, or a tuple of one or more of them. A set of anything else,
  and in a program a set of a type variable, is rejected, as upstream does.
- A set is a map from its elements to `true`, so the map routines keep it in
  ascending order and `==` compares it as a map. `inspect` writes
  `MapSet.new([1, 2])`, elements ascending.
- A set is an enumerable: every `Enum` and `Stream` function, the library
  functions of other modules that take an enumerable (`Map.new`,
  `List.foldl`, `Integer.undigits`, `Path.join`, ...), `x in set` (a lookup),
  `for x <- set`, `into: MapSet.new()` and `Enum.into(items, MapSet.new())`.
- All sixteen `MapSet` functions. `MapSet.new()` takes its type from an
  annotation or a parameter, and is rejected where nothing gives one.

Tuples as keys came with this for maps as well: `%{{1, 2} => "a"}`,
`Enum.group_by(xs, fn x -> {a(x), b(x)} end)`, `Enum.frequencies` of tuples.
The map routines (`spec/collections-x86_64.s`) compare and order such keys
with the comparator the compiler makes for the key type
(`alchem-ordering.md`): they get twice its address in R8 (as scalar key
types have 0, 2 and 24) and call it with 0 in RDX to ask whether two keys
are equal and with 1 for their order. The comparator a generic function
holds for a tuple type is the same thing, so library functions written once
for any key
type order tuples too. A map the library makes is checked to have a key
type (`Map.new([{[1], 2}])` through a set or stream is rejected like the
list was).

## Streams

- `stream[T]` (type tag 26 and the element) is a lazy sequence. `inspect`
  writes `#Function<>`; streams do not compare.
- At run time a stream is a function value from a *context* to an
  *iterator*. An iterator is a function value of no parameters that gives
  `some(element)` or `none`; it is not called again after `none`. The
  `some` it gave may be written over once its element was read, which is
  how `Stream.map` and most others pass elements on without allocating:
  state is kept in `some` records that are written over. A context is
  `some(function)`: what to do when the stream is read no further. Only
  `Stream.resource` adds to it (its `after` function); whoever starts a
  stream ends the context when it stops reading, whether the stream ended
  or not.
- Every `Stream` function of the pinned library except `Stream.publish`
  (below), with the pinned behaviour in the cases probed:
  negative counts of `take` and `drop`, `nth` 0, the partial last chunk of
  `chunk_every` with any step, the failures (`nth must be a nonnegative
  integer`, `chunk_every needs a positive count and step` where the stream
  is made; `cannot cycle over an empty enumerable` and `sleep duration must
  be nonnegative` when it is read, naming where it was made),
  `Stream.resource` starting at the first element and running `after` once,
  at the end or when the reader stops.
- `String.splitter` gives a stream.
- Where a library function takes an enumerable, a list, map, set, range or
  stream is given. A call is tried, in order: with the arguments as they
  are; with lists, maps, sets and ranges made streams where a form takes a
  stream; for `Enum.name` with a stream or range among the arguments, as
  the list of `Stream.name` when Stream has that name; for `Enum`, the
  compiler's own list code with the first argument made a list; then with
  the first argument, and at last every one, made the list a form takes.
- `Enum` reads a stream only as far as it needs, and calls its function for
  each element as the stream gives it, as upstream does: `take`,
  `take_while`, `find`, `find_index`, `find_value`, `any?`, `all?`, `at`,
  `fetch`, `fetch!`, `member?`, `empty?`, `count_until`, `reduce_while`,
  `slice/3`, `zip`, `zip_with`, `zip_reduce` stop early; `map`, `filter`,
  `reject`, `each`, `reduce`, `flat_map`, `scan`, `with_index`, `count`,
  `sum`, `sum_by`, `product_by`, `frequencies_by`, `group_by`,
  `split_with`, `map_reduce`, `flat_map_reduce`, `map_intersperse`,
  `map_join` (of strings and integers), `into/3`, the chunk, dedup and uniq
  functions and `MapSet.new/2` interleave.
- `for x <- stream` and `x in stream` read the stream as it gives.
- `Enum.each` and `Stream.run` leave no value, for every enumerable.

## Ranges

A range is `first`, `last` and `step` behind a count of 0; it no longer holds
its integers. Where a list is needed the list is built then (behind it the
three fields again, so the result is still a range value). Otherwise a
range is read as a stream: `Enum.sum(1..10000000)`,
`Enum.reduce(1..3000000, ...)`, `for x <- 1..1000000` and
`Enum.count_until(1..1000000, 5)` allocate nothing per element, and
`Enum.take(1..1000000000, 3)` reads three. A range is no longer a
`list[integer]` to a function of the program or to `++`, as upstream has
it. A range *written* where a `stream[integer]` is expected is that stream:
the value of an annotated binding, the result of a function declared to
return one, an argument, a piped value; a binding that holds a range is
not, as upstream has it.

## What the library is written with

Only a module of the library (one whose name begins with `Alchem`) may call a
library function whose name begins with an underscore:

| | |
| --- | --- |
| `MapSet.__set(map)`, `MapSet.__map(set)` | the map as a set; the set as a map to `true` |
| `Stream.__make(fn c -> iterator end)` | the function of a context as a stream |
| `Stream.__start(stream, c)` | its iterator under context `c` |
| `Stream.__run(stream, fn it -> ... end)` | the function's value for the iterator, under a context of its own that is ended after it |
| `Stream.__list(stream)` | the list of its elements |
| `Stream.__iter(list)`, `Stream.__all(iterator)` | the iterator over a list; the list of what an iterator still gives |
| `Stream.__until(iterator, f)` | the first `some(x)` for which `f(x)`, or `none`: the loop of every function that passes elements over |
| `Stream.__put(some, value)`, `Stream.__get(some)`, `Stream.__pull(some)` | write a `some` over (the result is the same record, typed by the value); read it; call the iterator it holds |
| `Stream.__then(first, value)` | the value, after first |
| `Stream.__sleep(milliseconds)` | `nanosleep` |
| `Stream.__where()`, `Stream.__fail(place, message)` | where the program called this library function; end the program naming that place |
| `Stream.__of(stream)` | the stream (a library function: its argument is made a stream) |

A library name takes up to sixteen forms per number of arguments (modules
`...v2` to `...v16`).

## Failures inside the library

A trace leaves the library's functions out and names a failure inside one
where the program called it (`alchem-system.md`: the call notes its
position in the frame at RBP-152 and `spec/trace-x86_64.s` skips frames of
modules named `Alchem...`). Two things are added here for streams, which
fail when they are read, not where they are made, while upstream names
where they were made (`cannot cycle over an empty enumerable`, `sleep
duration must be nonnegative`, `could not stream PATH`, `Stream.into:
closed`): `Stream.__where()` reads the position the caller of a library
function noted, and `Stream.__fail(place, message)` passes it to the trace
routine with bit 31 set, which the routine takes as the place to name
whoever fails.

## Files and standard input

`File.stream!(path)` and `File.stream!(path, size)` (`library/File.alc`),
`IO.stream()` (`library/IO.alc`) and `Stream.into/2,3` are streams as
upstream has them: the file is opened when the first element is asked for
(a missing file fails then, naming the `File.stream!`), `IO.stream` reads
one line each time one is asked for, and `Stream.into` writes each element
to the file as it passes.

## Differences that remain

- `Stream.publish` and `Node.stream` are not written: they are for other
  nodes, which the native runtime does not have. `Task.async_stream` is
  (`alchem-processes.md`).
- `File.stream!` reads the whole file into the arena when its first element
  is asked for, not a line at a time.
- Memory is not reclaimed (the arena of every native program, 16 GiB reserved
  lazily, `alchem-tail-calls.md`). A
  stream stage that makes a value per element costs that value: the tuples
  of `zip` and `with_index`, the lists of the chunk functions and of
  `flat_map`, what the functions of `unfold`, `resource` and `transform`
  return. `Stream.uniq` keeps the keys seen in a list that is copied when
  it grows. `Stream.cycle` over anything but a list starts its source again
  each round (an iterator of 40 to 48 bytes). Reading, mapping, filtering,
  taking, dropping, scanning and folding allocate nothing per element.
- `Enum.map_join` with a function that gives a boolean, atom or float reads
  a stream to its end before it calls its function. The output differs from
  upstream's only when the stream's own functions and that function both
  write. (`Enum.max_by`, `min_by` and `min` and `max` with functions compare
  as they read, and `sort_by` and `min_max_by` read everything first, as
  upstream does: `alchem-ordering.md`.)
- A failure that ends the reading of a stream does not run the `after` of a
  `Stream.resource`, whether it ends the program or a `try` takes it; nor
  does a `return` from inside `for x <- stream`. `Stream.zip` of a list of
  resources that stops early ends them first to last, upstream last to
  first.
- Whether a range is "written" is told from the code of the value (it ends
  in the making of a range), so `if c do r else 1..3 end` with a range
  binding `r` is taken as one where a stream is expected.
