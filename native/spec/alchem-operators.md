# Operators and functions without a module name

These follow the pinned compiler; `harness/operators.py` holds 51 programs with
what it prints for each, failures and traces included, and 12 it rejects.

## Operators

Tightest first; all but `**` group to the left.

| Operators | Operands |
| --- | --- |
| `**` | integers or floats; groups to the right; a negative integer exponent ends the program with `integer power needs a nonnegative exponent` |
| `*` `/` `%` | integers, and for `*` and `/` floats (`alchem-floats.md`); integer `/` and `%` truncate toward zero; a zero divisor ends the program with `division by zero` |
| `+` `-` | integers or floats, never one of each |
| `<>` `++` `--` | `<>` joins strings, `++` joins lists, `--` takes from the left list the first element equal to each element of the right one |
| `==` `!=` `<` `<=` `>` `>=` `in` | `value in list` is whether an element equals the value |
| `and` `&&` | booleans |
| `or` `\|\|` | booleans |

- `+`, `-`, `*`, `**`, unary `-`, `abs`, `/` and `Enum.sum` end the program with `integer
  overflow` when the result leaves 64 bits. The message names the operator's
  position; the trace follows (`alchem-traces.md`).
- `not` and `!` take one boolean operand.
- A `-` that starts a line starts a statement. `%Name` starts a struct and
  `%{` a map; any other `%` is the remainder.
- For `++` and `--` one of the two lists must say what the elements are, and
  the left one takes no type from the right one's elements; for `in` the list
  must say it.
- A compiler entry (`native_compile`) keeps wrapping `+`, `-` and `*`, which
  is what the seed gives the compiler when it builds it, and exits 70 where
  another program would report a failure.

## Functions

Called by name, or as `Kernel.name` when the module defines a function of the
same name (`inspect` is below):

| Function | Result |
| --- | --- |
| `rem(a, b)`, `div(a, b)` | as `%` and `/` |
| `abs(n)` | the absolute value of an integer or a float |
| `min(a, b)`, `max(a, b)` | of two integers, floats, booleans or strings |
| `length(x)` | elements of a list, entries of a map, positions of a tuple |
| `map_size(m)` | entries of a map |
| `hd(list)`, `tl(list)` | the first element and the rest; an empty list ends the program with `the list is empty` |
| `to_string(x)` | a string, integer, float or boolean as text |
| `round(x)`, `trunc(x)`, `ceil(x)`, `floor(x)` | a float as an integer (`alchem-floats.md`) |
| `assert(condition)` | a statement; a false condition ends the program with `assertion failed` |
| `raise(message)` | ends the program with the message, naming the `raise`, and the trace; it stands where a value of any type is expected. `try` and `rescue` are not compiled yet |

## inspect

`inspect(value)` is the value as text in source form and `IO.inspect(value)`
writes that text and a line break and gives the value back:

| Value | Text |
| --- | --- |
| integer, boolean | `-5`, `true` |
| float | `1.5`, `1000.0`, `1.0e16` (`alchem-floats.md`) |
| string | quoted as Go's `strconv.Quote` does: `"a\n\"é\x01"` |
| option, result | `some(1)`, `none`, `ok(1)`, `error("bad")` |
| tuple, list | `{1, "a"}`, `[1, 2]` |
| map | `%{"a" => 1, "k" => 2}`, in key order |
| struct | `%Point{x: 1, y: 2}`; a generic struct without its arguments |
| sum type | `Shape.circle(1)`, `Shape.dot` |
| function | `#Function<>` |

Values carry no type at run time. The compiler writes a description of the
value's type behind the call (a node per type: its length, a tag, and for a
struct or sum type the names) and one routine walks the value by it; a type
that refers to itself points back at its own node. The routine shares the
quoting code of the Integer.parse runtime (`spec/integer-parse-x86_64.s`),
which a program gets when it mentions `inspect`. `harness/inspection.py`
holds the programs and the pinned compiler's output.

Inside a generic function a value whose type mentions a type variable is
inspected as the type the function was called with: the function takes
the description of each variable's type as a hidden argument, and the
description of the value points at it (node 35; `alchem-json.md`, "Type
variables"). String interpolation of such a value is rejected, as upstream
(`interpolation requires a string, integer, float, boolean or atom`).

## cond

`cond do condition -> body ... end` runs the body of the first condition that
holds. As a value every body ends in one and their types agree; as a statement
they need not. When no condition holds the program ends with `no cond clause
matched`, naming the `cond`.

A block ends where the next arm starts. For `cond` that is an expression
followed by `->`, found by its tokens: brackets and `do`/`fn` ... `end` nest;
at the outer level the expression ends where an operand follows an operand,
and at a line break unless an operator stands beside it.

## unless and the one-line if

`unless condition do ... else ... end` is an `if` on the opposite condition.
`if condition, do: value, else: value` (and `unless`) is the one-line form:
each part is one expression or an output or halt statement, and without
`else:` it is a statement. A `do` followed by `:` opens no block.

`concat filter map reduce get has_key put prepend tap then` without a module
name are written in Alchem (`library/Kernel.alc`, see
alchem-library-profile.md). `harness/forms.py` holds the programs.

## Module constants

`@name value` at the start of a line of a module declares a constant, and
`@name` anywhere in that module stands for the value: each use compiles the
declaration's expression where it stands, with no bindings in reach, so a
constant may use literals, operators and other constants. The value runs to
the end of its expression, across lines inside brackets or beside an
operator. `@doc`, `@moduledoc` and other attributes are skipped the same way.

## Atoms and keyword lists

`:name` is an atom, of type `atom`. At run time it is the string of its name
and only the type differs, so atoms compare, order and serve as map keys as
strings do, `to_string` gives the name and `inspect` writes `:name`. A
pattern may be an atom. In a list literal `name: value` is the tuple
`{:name, value}`, and `inspect` writes a list of such tuples back in that
form. `harness/atoms.py` holds the programs. Quoted atoms (`:"two words"`)
and a trailing `key: value` among a call's arguments are not compiled yet.

## Ranges

`first..last` is a range, of type `Range`, and `first..last//step` sets its
step; without one, or with step 0, it counts up or down toward `last`. `..`
binds as `<>` does. A range is first, last and step and holds no integers:
it is an enumerable, read as a stream or made a list where a library
function needs one (`spec/alchem-sets-streams.md`), so `Enum`, `Stream`,
`in` and `for` take it, and a huge one costs nothing until it is read.
`range.first`, `range.last` and `range.step` read the three, `==` compares
them and `inspect` writes the range back. `library/Range.alc` holds the
Range functions and `harness/ranges.py` the programs.

## Bitwise operators

`a &&& b`, `a ||| b`, `a ^^^ b`, `a <<< n`, `a >>> n` and `~~~a` take
integers and give one; they stand for `Bitwise.band`, `bor`, `bxor`, `bsl`,
`bsr` and `bnot`, as the pinned parser rewrites them, and a failed
assertion writes them as those calls. `|||` and `^^^` bind as `or` does,
`&&&` as `and`, the shifts as `|>` (tighter than a comparison, looser than
`<>` and `+`), each to the left; `~~~` takes the value after it as a minus
does. So `1 ||| 2 == 3` is `1 ||| (2 == 3)` and is rejected, and
`1 <<< 2 + 1` is 8. They stand wherever an expression does: guards,
module constants and default values, `for` filters, pipes, interpolation.

A shift by a negative count is the opposite shift by its size. Left by 64
or more gives 0; right keeps the sign, and by 64 or more shifts by 63.
The code is in line (`nk_bits`): the processor's and, or and exclusive or
(`dn_emit`, which the library's `Process.__and` and the like share), and
a few instructions for a shift. Each sign three times is one token
(`nk_tripled`), so `|||` is not `||` and `<<<` no comparison; a line that
ends or starts with one continues the expression.

One difference remains: a shift by the least integer, -9223372036854775808,
whose size is itself. Upstream's `bitShiftLeft` and `bitShiftRight` call
each other without end there and the program dies of its stack; the native
operator shifts by 64 or more the opposite way, and `Bitwise.bsl` written
in Alchem fails on the negation.

`harness/gaps.py` holds the programs.

## Not yet

`min`/`max` of lists and tuples.
