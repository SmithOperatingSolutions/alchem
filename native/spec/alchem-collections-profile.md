# Native immutable general collections

The Alchem-written compiler separates byte buffers (`bytes`, `b[0,255]`) from
word lists (`list[T]`, `[value,...]`). Integer lists retain signed64-bit values;
string and nested lists retain full pointers and structural types. Empty `[]`
infers list[unknown] and unifies with typed calls/returns, another branch, defaults
or a typed callback. Mixed incompatible element types reject. There are no casts.
Literals have at most128 elements, evaluated left to right. Runtime-built lists
are bounded by the user arena (16 GiB reserved lazily, alchem-tail-calls.md), rather
than by the literal count.

A list is the address of a count beside its first element, the count of
the rest beside the second and so on to a count of 0 (16 bytes an element in
a block of 24 more; alchem-lists.md): a tail is an address inside its list
and an element is put before a list without copying it. Lists are
immutable and are never packed/truncated as bytes. The existing byte operations
and byte error/resource order remain separately tested. Compiler/runtime sources
and byte demos now use explicit byte syntax. Only the initial pinned Go frontend
adapter translates that spelling to its older byte IR; native rebuilds consume
the saved source unchanged. The migration helper in the harness applies only to
old byte-profile fixtures; general-collection tests have no source rewrite.

## Lists and iteration

- Enum.count/empty? inspect list length.
- Enum.at(list,index) / Enum.fetch(list,index) return option[T]. Negative indices
  add length once; absent/extreme indices return none. Enum.at(list,index,default)
  returns T and requires a compatible eager default. List.first/last have the
  corresponding option/default overloads.
- Enum.concat/reverse and a slice or take from inside a list construct fresh
  lists, preserving element types and input aliases; Enum.drop, and a slice
  or take that ends where the list ends, give the list from that element on
  (alchem-lists.md). Negative slice count exits73; invalid slice
  indices yield empty. Count clamping avoids signed overflow. Take/drop preserve
  the pinned positive/negative-count behavior, including signed endpoints.
- Enum.sum requires integer elements; a sum that leaves 64 bits ends the
  program with `integer overflow`, as the pinned runtime does.
- `&name` captures a declared local module function, including private/forward
  functions. `fn[Arg,...,Return]` stores its full signature. Enum.map calls a
  one-argument callback in order and returns list[Return]. Enum.filter requires
  a boolean callback and preserves matching original elements in order.
  Enum.reduce(list,initial,&name) passes element then accumulator to a two-argument
  callback returning the accumulator type. Empty reduction returns initial.
  Calls are ordinary native machine calls; existing frame/depth guards apply.
- Callbacks can be stored/passed as typed values to these APIs, and may be
  anonymous functions with captured bindings; function values can also be
  called directly. Captures such as `&(&1 + 1)` and references such as
  `&Module.name/1` are also callbacks. See alchem-closures.md.

Map/filter reserve output capacity before invoking callbacks. Filter charges the
input-length capacity even if fewer elements survive (the counts are written
once the callbacks are done). Reduce itself allocates
nothing. Callback allocations remain charged. Errors exit normally through the
native guards; callbacks cannot reclaim or rewind the arena.

## Maps

`map[Key,Value]`, `%{}`, `%{key => value,...}` and Map.new(list[tuple[Key,Value]])
support integer, string or boolean keys with recursively typed values. Empty maps
have unknown key/value holes. Map.put fills or unifies those holes; inconsistent
later keys/values reject. Duplicate keys retain their last value. String keys
compare full byte contents, not pointers, including embedded NUL/invalid UTF-8.

Map.get/fetch provide option lookup; Map.get with a third eager argument returns
the value/default. Map.has_key? returns boolean. Map.put/delete return immutable
maps; original values remain usable. Map.keys/values and Map.entries/to_list
return typed lists. Enum.count/empty? accept maps. Iteration uses the entry list
with map/filter/reduce. Enumeration follows the pinned sorted-key order: signed
integer order, false before true, and lexicographic string byte order. Values
and entries follow their keys.

Records have an eight-byte count plus16 bytes per key/value pair. Lookup is
linear; construction/copy and in-place sorting of the fresh result favor a small
bounded implementation. This is not a hash-map or optimized-map performance
claim. Map literals construct temporary pair/list records; those allocations
remain charged. Map.new reserves capacity for all supplied pairs before
collapsing duplicates. Deleting an absent key still constructs a fresh record.
Further map callbacks/merge/set operations, arbitrary key equality and mutation
remain future work.

The shared60-bit structural encoding, 16 live locals/expression nesting,
65535 functions, 256 active frames and executable/source bounds remain explicit.
Compiler entries and ordinary programs reserve 16 GiB lazily (the largest half of it the
system grants, down to 1 GiB and 4 MiB; alchem-tail-calls.md). See
alchem-structural-types.md and alchem-library-profile.md.
