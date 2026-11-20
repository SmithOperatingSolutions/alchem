# Sigils, index syntax and what came with them

These follow the pinned compiler; `harness/sigils.py` holds the programs
with what it prints for each, failures and traces included, and the
programs it rejects. The code is `implementations/alchem/native-sigils.alc`.

## Sigils

A sigil is `~`, a letter, text between delimiters and modifier letters
(lower-case letters and `U`). The delimiters are `/ /`, `| |`, `" "`, `' '`,
`( )`, `[ ]`, `{ }` and `< >`. The whole sigil is one token.

- The text has no escapes: `~s(a\nb)` holds a backslash and an `n`. A
  backslash before the closing delimiter gives that delimiter, `~s(a\)b)`.
- A sigil of a lower-case letter holds the value of each `#{expression}`,
  as a string does: a string, an integer, a boolean or an atom. The
  expression may hold the closing delimiter, in a string or between braces.
  One of an upper-case letter keeps `#{` as text.
- A one-line sigil ends on its line. `~X"""` opens a heredoc: the text is the
  lines up to the closing `"""`, each without the closing line's
  indentation. `~s"""` is the heredoc string itself, with its escapes;
  `~S"""` is its text as written.

| Sigil | Value |
| --- | --- |
| `~s(text)`, `~S(text)` | a string; modifiers are ignored |
| `~w(one two)` | the words of the text as `list[string]`, split at white space (what Go's `unicode.IsSpace` names); with a value in it, `String.split` of the string it makes |
| `~c(text)`, `~C(text)` | the code points of the text as `list[integer]`; a byte that starts no character is 65533; `~c` with a value in it is rejected |
| `~D[2024-01-02]` | a `Date` |
| `~T[12:30:00]` | a `Time` |
| `~N[2024-01-02 12:30:00]` | a `NaiveDateTime` |
| `~U[2024-01-02T12:30:00Z]` | a `DateTime` |
| `~r/pattern/flags` | a regular expression (`alchem-regex.md`) |
| `~h"text"`, `~H"text"` | a `Markup`: an HTML template (`alchem-templates.md`) |
| any other letter | `sigil_x(text, modifiers)`, a function of the program taking two strings: the one module that defines it, `def` or `defp`; two modules that define it leave the sigil unknown |

### Dates and times

The four calendar sigils make the structs of those names that the library
declares (`library/Date.alc`, `Time.alc`, `NaiveDateTime.alc`,
`DateTime.alc`, in the appended module `AlchemTypes`), with the pinned
fields in the pinned order: `year, month, day`; `hour, minute, second,
microsecond`; both; and for a DateTime both, then `time_zone` (`"Etc/UTC"`)
and `utc_offset` (0). A program that writes one gets the struct's
declaration without naming it.

The text is checked when the program is compiled, as Go's `time.Parse`
reads the pinned layouts (`2006-01-02`, `15:04:05`, both with `T` or a
space between, and for `~U` then `Z07:00`), white space around it taken off:

- the year has four digits, month and day two; the day exists in its month;
- the hour has one or two digits (0 to 23), minute and second two (0 to 59);
- a fraction of any length may follow the seconds after `.` or `,`; its
  first six digits are the microseconds;
- a `~U` ends in `Z` or in `+hh:mm` / `-hh:mm` with hours up to 24 and
  minutes up to 60, and is the moment in UTC, so `~U[0000-01-01T00:30:00+01:00]`
  is in year -1.

`inspect` writes such a struct back as its sigil, as the pinned runtime
does: `~D[2024-01-02]`, `~T[12:30:00.500000]` (the microseconds when they
are not 0), `~N[2024-01-02 12:30:00]`, `~U[2024-01-02T12:30:00Z]`, and a
DateTime whose zone is not `Etc/UTC` as `#DateTime<2024-01-02 12:30:00+09:00
Asia/Tokyo>`. Numbers are written as Go's `%04d`, `%02d` and `%06d` write
them, whatever a struct built by hand holds. The description of the type
is a node of its own (30 to 33, `spec/integer-parse-x86_64.s`); only the
structs of `AlchemTypes` are written so.

A struct or sum type of the program may not take the name of a library
module (`Date`, `Time`, `URI`, ...), as the pinned compiler has it.

## Index

`value[index]` reads from the value before it, when the bracket stands on
the value's line:

- `list[index]` is the element at a position from 0; an index below 0 or
  past the end ends the program with `list index out of bounds`.
- `map[key]` is the value of a key of the map's key type; a key the map
  does not hold ends the program with `map key not found`.
- `tuple[index]` takes the index as a number written out: decimal digits,
  the same in parentheses or after a minus sign, or a module constant that
  is one.
  (A tuple of sixteen or more fields used to store and read the fields
  past the fifteenth at the wrong place; `elem`, literals and the index
  now agree with patterns, `==` and `inspect`.)

Both failures name the bracket and show the active calls
(`alchem-traces.md`). An index may follow any value, and a field, a call or
another index may follow it: `m["a"][0]`, `s.items[1].name`,
`callbacks[0](x)`, `counts[:blue]`. The list or map is evaluated before
the index. A value of any other type, or one whose type is still open
(`[][0]`), is rejected.

A bracket before `=` starts a binding (`z = l [a] = [5]` is two
statements, as upstream reads it). A bracket before `->` or `when` is the
pattern of the next arm, as the pinned parser reads the body of an arm
(`case xs do [] -> xs [h | _] -> [h] end`), except in the condition of a
`cond` arm and in a guard, where it is an index (`flags[0] -> ...`,
`x when flags[1] -> ...`). The condition or guard is compiled under a mark
in its environment (a record with no name, type 42), which an `if` or
`case` used as a value and a `fn` inside it end.

## Patterns in bindings

A binding's pattern may be a literal or a pinned binding: `1 = x`,
`"a" = s`, `:ok = f()`, `true = (1 == 1)`, `-1 = n`, `^x = y`. A value that
does not match ends the program with `pattern match failed`, and one of
another type is rejected. A string that holds a value (`"a#{1}"`) is no
pattern. A map pattern compares atom keys as the strings they are.

## Module constants

The value of `@name` is checked where it is declared, as the pinned
compiler checks it: literals, lists, tuples and maps of them, operators and
earlier constants. A call, a range, `in`, an index, a pipe, a capture, a
string holding a value and a sigil holding a value are rejected. `@doc` and
`@moduledoc` take one string without values, or `false`. A default value of
a parameter may hold a sigil; the values in it are constants as the rest of
a default is.

## References to library functions

`&Module.name/arity` for a function of the library written in Alchem
(`library/*.alc`) is a function value that calls it: the form its parameter
types fit, among `AlchemModuleN` and `...v2` to `...v9`. It takes its types
from where it stands, like `&String.length/1` for the compiler's own
functions. Without a module, the names the pinned library has are
referable and no others: `abs binary_part byte_size ceil div floor hd
inspect map_size max min rem round tap then tl to_string trunc`
(`&length/1` and `&some/1` are rejected, as upstream rejects them).

Passed to a generic function of the program, such a reference needs every
type variable of its parameter's type settled before it, the result's
too: `id2(1, &Integer.to_string/1)` for `id2(x: a, f: fn[a, b]): b` is
rejected unless the call's own expected type settles `b`. Calls into the
library take it as before.

## Lambdas typed by an earlier lambda

The arguments of a call of a generic function are typed in the order they
are written. A lambda or capture whose parameter types the arguments before
it settle is compiled where it stands, and its result settles variables
for the arguments after it:

```alchem
def by(items: list[a], f: fn[a, b], s: fn[b, b, boolean]): boolean
by(["bb"], fn a -> String.length(a) end, fn a, b -> a >= b end)
```

A lambda whose parameter needs the result of a later one is rejected, as
upstream rejects it.

## Differences from the pinned compiler that remain

- A calendar sigil needs its struct from the library: a compiler built
  without `library/Date.alc` and the others rejects the sigil.
- An index of a tuple written `0x1` or `0_1` is rejected, as every integer
  written in base 16, 8 or 2 or with underscores is: the compiler reads
  decimal digits only (`nc_number`), which this work left alone.
- The text of a sigil without values holds at most 65535 bytes, as a
  string literal does: both are emitted by `nc_literal_emit`, which keeps
  the length in 16 bits.
- Every compile error is `E_COMPILE`; the pinned compiler's message and
  position are not reproduced.
