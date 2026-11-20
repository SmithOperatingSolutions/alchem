# JSON

The `JSON` type and `JSON.decode`, `decode!`, `encode`, `encode!` (with
`pretty:`) and `decode_as`, with the text, the errors and the failures of
the pinned runtime. That runtime uses Go 1.27's `encoding/json`, the
version built on `jsontext`, and the library follows it function by
function (`consumeValue`, `ConsumeString`, `AppendUnquote`,
`ConsumeNumber`, the error wording of `transformSyntacticError`).
`harness/json_library.py` holds 18 programs (some 600 lines of output: the
reference's examples, 76 malformed texts, 150 mutated ones, values of
every kind written and read back, 57 `decode_as` cases) and 20 programs the
pinned compiler rejects. Beyond the gate, 9,600 mutated texts (24 seeds of
`decode`, `encode!`, `pretty:` and a round trip each) gave the pinned
output byte for byte.

## The type

`JSON` is a sum type of the library (`#: struct JSON` in
`library/JSON.alc`, module `AlchemTypes`): `null`, `boolean(value)`,
`integer(value)`, `float(value)`, `string(value)`, `list(items)`,
`object(fields)`. Two changes in `native-records.alc` let it be one: a
variant may have the name of a type word (`integer`, `boolean`, `string`,
`option`, `bytes`, `void`, `byte_size`; keywords stay refused, as
upstream), and `Name.variant` finds a sum type of the library when the
program has no such name and `variant` is one of its variants (so
`JSON.decode` stays a function).

## By the type of a value

`JSON.encode(value)`, `JSON.encode!(value[, options])` and
`JSON.decode_as(text or JSON)` go by a static type that a function written
in Alchem cannot see. `native-json.alc` compiles them as calls of library
functions that take a description of the type: the node tree `inspect`
walks (`native-inspect.alc`, `spec/integer-parse-x86_64.s`), placed in the
code behind the call.

| In the program | What is called |
| --- | --- |
| `JSON.encode!(v)` | `encode!(word, description)` |
| `JSON.encode!(v, options)` | `encode!(word, options, description)` |
| `JSON.encode(v)` | `encode(word, description)` |
| `JSON.decode_as(x)` | `decode_as(x, description)`: an integer, taken as the expected `result[a, string]` |

`decode_as` takes its type from the annotation of the binding it is the
value of (also as the last call of a pipe), or, as the value a function or
typed `fn` ends with, from the declared result. Elsewhere it is rejected,
as upstream (`cannot infer the result type`). A type with a function, a
stream, a regular expression or a map whose keys are tuples is rejected,
as upstream.

For writing values by a description the library alone has four
operations, in any module (`jn_intrinsic`): `M.__word(value)` the word a
value is held in, `M.__kind(value)` where the description of its type
stands, `M.__cast(word)` a word as a value of the type its binding is
annotated with, `M.__show(word, description)` what `inspect` writes.

Description node 34 is an option that a type variable of a generic
struct stands for, written for `decode_as` and in the descriptions a
generic function is handed ("Type variables" below); `inspect` and
`encode` take it as an option. A field declared an
option may be missing from the object; a field of type `a` may not, even
when `a` is an option, and upstream tells the two apart the same way.

## Type variables

Inside a generic function the type may mention the function's type
variables: `JSON.encode!(x)` for `x: a`, `JSON.decode_as(text)` where
`result[list[a], string]` is expected, a generic struct `Nest[a]`, and the
same through a `fn` inside the function, a generic caller (`tuple[b, b]`)
and `&name/N`. The value is written or read as the type the function was
called with. `inspect` and `IO.inspect` go the same way, and
`Gen.check` for the failing value it shows.

A generic function is compiled once, so the description has to reach it at
run time (`native-described.alc`):

- A generic function of the program that needs descriptions is *described*
  (bit 128 of its byte, below). After the comparator of each
  type variable it takes one more hidden argument per variable, its twin:
  the address of the first node of the description of the type the
  variable stands for. The twin of `a` has the name `a` and byte 127, so
  everything that carries comparators carries it: a call, a `fn` in the
  function (it captures every slot), `&name/N`.
- A call gives each twin (`jd_twin` from `nu_comparators`): a description
  behind a jump for a type without variables, the caller's own twin for
  one of its variables, and for a compound type that mentions the caller's
  variables a copy of the description in the arena with the caller's twins
  written into it.
- In the function a type variable is described by node 35: five bytes
  of zero and the 64-bit address of the first node of another
  description (the address stands 8 bytes from the node's start, so that
  the word a walker takes a node's length from is never negative). The
  code at `inspect` or the JSON call copies the description to the arena
  and writes each twin into its node 35 (`jd_placed`); a type that is one
  variable alone is its twin as it stands. The copy is a value like any
  other (`alchem-memory.md`): it is made through the allocation hook and
  held by the slot or the stack that takes it, and a twin written into it
  is the start of another such value or stands in the image. Each twin is
  written a second time behind the description, in a word of its own: a
  node may stand at any byte, and the collector reads a value word by
  word.
- The walkers follow node 35 and count a node 20 inside it from where it
  points: `ins` in `spec/integer-parse-x86_64.s` (which also takes a list
  of `{atom, value}` tuples behind a node 35 as a keyword list, and node 34
  as an option), `enc` and `fit` in `library/JSON.alc` (`encv`, `fitv`).
- A struct field whose declared type is a type variable may not be missing
  from the object even when the variable stands for an option: such a
  field is node 35 inside a generic function and node 34 in a description
  without variables, and twins are made as for `decode_as`, with node 34
  and with counts and the lengths of names in one byte, as the JSON
  library reads them. A type that needs more (a tuple, a struct or a sum
  type of 255 parts or more, a name of 255 bytes or more) has no such
  description: its twin is the one `inspect` takes, inside node 36, which
  `inspect` looks through and by which `encode` and `decode_as` give
  `a type of 255 or more parts cannot be written as JSON` (`read from
  JSON`) when the program runs.

Which functions are described is settled before code is kept
(`jd_settle`, only when a function of the program mentions `inspect`,
`JSON` or `Gen`): a generic function of the program that does not compile
as the table stands is marked, until a round marks none. A mark is seen by
the functions tried after it in the same round, the rounds go through the
records in turn from the last and from the first, and after the first
round a function is tried again only when its text holds the name of a
function whose marks changed (a chain of 200 generic functions written in
any order is settled in half a second). A function that needs no description keeps its code and its calling
convention, and so does the library, which gets only the comparator.

The pinned compiler rejects a call that gives a type variable read from
JSON a type that cannot be read (`twice reads b from JSON, and
fn[integer,integer] cannot be read`), following the variable through the
generic functions that pass it on. The native compiler finds the same set
(`jd_refused`): bits 0 to 5 of the function's byte say which of a function's first six
type variables it reads, found by compiling the function once more per
variable with that variable poisoned (a `decode_as` of it, or a call that
passes it to a variable the callee reads, then does not compile), to a
fixpoint; for a variable past the sixth the callee is compiled so where a
call gives it such a type.

`&JSON.encode!/1`, `&JSON.encode!/2`, `&JSON.encode/1` and
`&JSON.decode_as/1` are function values that call the library with the
description of their parameter's type, or of the type their result is
expected to hold (`jd_referred`); inside a generic function the type may
again mention its variables. `&inspect/1` and `&IO.inspect/1` there
capture the twins.

What is known of a function is one byte (`jd_byte`): bit 128 described,
bits 0 to 5 the variables read, bit 6 that one past the sixth is read. It
stands in the finished table's name index, which holds a record's number
in four bytes of which three are read (`nc_cursor`): the fourth byte of
entry *id* is the byte of record *id*, whatever record that entry names.
A table record itself has no byte free (byte 24 is the high byte of the
number of parameters).

`harness/described.py` holds the programs.

## Reading text

The parser keeps its own stack (mapped memory, given back at the end) and
runs a thousand steps to a level of calls, so neither a text of megabytes
nor 10,000 levels of nesting costs call depth. An array becomes a list in
one copy; an object of up to 64 members is put in order where it stands
and copied once, a larger one goes through `Map.new`. A string without
escapes is copied as it stands.

Go's decoder reads its text in pieces of 64 bytes, then 128, 256 and so
on, and names an invalid character or escape by the bytes read so far: a
two-byte character that a piece ends in is reported as its first byte
(`'\xc3'`), an escape as the part of it that was read. The library does
the same (`lim`), since the messages are part of what a program sees.

Numbers: an integer when the text has no fraction or exponent and fits 64
bits, else the nearest float; a number too large for a float is an
infinity, as the pinned runtime leaves it (`JSON.float(+Inf)`), which
`encode!` then writes as `+Inf`, and for which `pretty: true` gives the
empty text Go's `Indent` leaves.

## The library file

`library/JSON.alc` has an entry for every function (138), each with the
functions it needs (`scripts/check-library-needs.py` finds none missing),
so a program gets what it calls and what that calls: one that only decodes
gets the reader of text and nothing of the writer or of `decode_as`.

## Differences that remain

- A description that mentions type variables is copied to the arena each
  time the call or the `inspect` it stands at runs (its length rounded up
  to 8 bytes, and a word for each type variable in it); the collector gives it back when nothing holds it. One
  without variables, or of one variable alone, costs nothing.
- Where four compilations for "is this variable past the sixth read"
  stand inside one another (generic functions of more than six type
  variables that pass such a variable on to one another in a chain that
  long, and a call that gives the first a type that cannot be read), the
  next is taken to read and the call is rejected; the pinned compiler
  follows any chain. What is being asked is kept in the 12 bytes the
  record of zeros behind the table has before its flags.
- A function with more than 65,000 type variables gets no description of
  one past that: a description names a type it has seen by a 16-bit
  number (`ni_seen`), and a type variable's twin by such a number too.
- A generic function that calls itself with a larger type (`pong([x], n)`)
  is compiled and runs; the pinned compiler's Go build stops with
  `instantiation cycle`. That holds for any such function, with or without
  JSON: the native compiler makes one body for every type and has nothing
  to instantiate.
- Every value comes from the program's arena, which is never given back. A
  text of 42 KB (a thousand objects of two members, one of them a list of
  four) costs 336 KB as a value; writing a value costs its text and 48
  bytes for each float.
- `decode_as` of a set of tuples orders them by counting, which is
  quadratic in their number.
- A float key (`map[float, v]`) is read with the library's `Float.parse`,
  which takes the decimal forms and `inf`/`nan`; Go's `ParseFloat` also
  takes hexadecimal floats (`0x1p-2`).
