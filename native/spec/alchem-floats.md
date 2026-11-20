# Floats

`float` is the pinned language's 64-bit IEEE type. A float is its IEEE-754
bits in the 64-bit word every value occupies (type tag 24), so lists, tuples,
maps, structs, sum types, options, results and function values hold floats as
they hold integers. `harness/floats.py` holds 170 programs with what the
pinned compiler prints for each (911 lines; 24 end in a failure with its
trace) and 98 it rejects.

## What is built

| Form | Behavior |
| --- | --- |
| `float` in annotations | parameters, results, bindings, fields, type arguments |
| literals | digits on both sides of the point, underscores between the digits before it, an optional exponent `e`, sign, digits: `1.5`, `1_000.25`, `1.0e3`, `2.5e-7`. `1..3` is a range and `1.` and `1.5e` are no floats. A literal too large for 64 bits is rejected; one too small is zero |
| `+` `-` `*` `/` | two floats; `1 + 1.5` is rejected. `/` by `0.0` or `-0.0` ends the program with `division by zero`, naming the operator. Nothing is checked for overflow: results may be `+Inf`, `-Inf` and `NaN` |
| `**` | two floats: Go's `math.Pow` |
| unary `-` | flips the sign, also of zero |
| `==` `!=` `<` `<=` `>` `>=` | IEEE: `NaN` equals and orders nothing, `0.0 == -0.0` |
| `to_string`, `"#{x}"`, `Float.to_string` | the shortest digits that read back as the value, in exponent form when that is strictly shorter or the value is at least 2**53: `1000.0` is `1.0e3`, `1250.0` is `1250.0`; `+Inf`, `-Inf`, `NaN` |
| `inspect`, `IO.inspect` | plain digits from 1 up to 1.0e16, otherwise as `to_string`; `NaN` is `NaN.0`, as the pinned compiler writes it |
| `round` `trunc` `ceil` `floor` | float to integer; `round` takes halves away from zero. A result outside 64 bits, or `NaN`, ends the program with `float out of integer range` |
| `abs` `min` `max` | of floats as of integers; `abs(-0.0)` is `-0.0` and `min(0.0, -0.0)` is `0.0`, as the pinned functions give them |
| `assert_in_delta(a, b, delta)` | ends the program with `assertion failed` and the three values when `a` and `b` are more than `delta` apart |
| `Float.from_integer` | the nearest float |
| `Float.parse`, `String.to_float` | Go's `strconv.ParseFloat`: decimal and hexadecimal (`0x1p-2`) text, underscores as Go allows them, any number of digits, correctly rounded. Infinity, `NaN` and text too large are refused: `error("\"x\" is not a float")`, and `String.to_float` ends the program with that message |
| `Float.round` `Float.floor` `Float.ceil` | one argument: to a whole float (a zero keeps the sign). With decimal places 0..15: rounded on the exact value of the float as the pinned functions do, so `Float.round(1.15, 1)` is `1.1` and `Float.ceil(3.7, 1)` is `3.8`; other places end the program with `precision must be between 0 and 15` |
| `Float.pow` | as `**` |
| `Float.ratio` | `{numerator, denominator}` in lowest terms; `Float.ratio needs a finite float` and `Float.ratio: the fraction does not fit in 64-bit integers` end the program |
| `Float.max_finite`, `Float.min_finite` | the largest and the most negative finite float |
| `Enum.sum(list[float])` | starts from `0.0` |
| patterns | a float literal, also negative, matches by `==` |
| map keys | floats are keys: found by `==` (so `NaN` is never found and each `NaN` put adds an entry), enumerated in ascending order |
| equality of compound values | `==` on floats inside lists, tuples, maps, structs, sum types and through type variables |

An integer literal may now separate its digits with underscores too
(`1_000_000`): one scanner ends both kinds of number.

## Constants

The pinned compiler writes a float literal, and a `+`, `-` or `*` of two such
values (also in parentheses and through a module constant), as a Go constant.
Go folds constants exactly, rounds once per operation, has no negative zero
and no infinity among them. The native compiler does the same while
compiling: `0.0 * -1.5` is `0.0` where the same product of two bindings is
`-0.0`, and `1.0e308 * 10.0` is a compile error where the product of two
bindings is `+Inf`. `-0.0`, a unary minus, `/`, `**` and every call are no
constants (the pinned compiler makes them at run time), so `-0.0 * 1.0` is
`-0.0`.

A constant's code is `mov rax, bits` and nothing else, which is how the
compiler knows one; the literal `-0.0` and `Float.max_finite()` carry a `nop`
behind it.

## How conversion works

The compiler is written without floats (the seed that builds it has none), so
it converts with integers of any size, kept as bytes (`native-floats.alc`):

- A literal is its digits as an integer (at most 800 of them, as Go keeps; a
  dropped digit that is not zero is remembered) and a power of ten: a ratio
  `u/v` of two integers. One of them is doubled until `v <= u < 2v`, 53
  quotient bits (fewer for a subnormal) are divided out one by one, and one
  more bit with what is left decides the rounding, halves to the even
  neighbour. That is the correctly rounded value for every literal.
- A constant sum, difference or product is formed exactly from the two
  mantissas and exponents and rounded by the same step.

At run time text is made and read by the float runtime
(`spec/float-x86_64.s`, 18.5 KB, kept as checked byte literals in
`native-float-data.alc` by `scripts/generate-float-runtime.py`). It is emitted
once per program, in the table slot after the trace routine's, when the source
has the letters `loat` or a point between two digits; a false positive only
adds the runtime. EAX selects the operation.

- Text: Go 1.27's `shortFloat` (`internal/strconv/uscale.go`, unrounded
  scaling): the two ends of the values that read back as the float are
  scaled by a power of ten with one or two 64-bit products each, and the
  shortest digits between them are taken, the float's own scaled value
  rounded when there is no shorter. The powers are Go's `pow10Tab`, 696
  entries of 128 bits (`fl_pow10`, 11 KB of the runtime). The digits and
  the exponent are then laid out by the rules above. The digit generation
  on integers of 1152 bits that stood here before gave the same text for
  every value tried (below) and took 1.6 microseconds a float; this takes
  about 50 nanoseconds.
- Parsing: Go's `readFloat` byte for byte (signs, `0x`, underscores, the
  exponent capped as Go caps it), keeping the first 19 digits as one word,
  then Go's `parseFloat64`: the word scaled by the power of ten and rounded
  once. When digits were dropped the result stands if the word plus one
  gives the same float, as in Go's `atof64`; otherwise the text is read
  again, up to 800 digits, and the value is formed exactly: the same ratio
  and bit-by-bit division as the compiler's, on integers of 4096 bits.
  Hexadecimal text is rounded from its 64 mantissa bits and a sticky bit.
- Rounding at decimal places: the product with the power of ten and its exact
  error (Dekker's product, in place of Go's fused multiply-add: the same
  value), and for products of 2**52 or more the pinned function's exact
  path: a 128-bit product, then the ratio division.
- `**` and `Float.pow`: Go's `math.Pow`, `frexp` and `ldexp`, with its amd64
  `Exp` and `Log` routines instruction for instruction. `Exp` uses fused
  multiply-add when the processor and the system have it (CPUID and XGETBV,
  as Go decides), since the two paths differ in the last bit.
- `inspect` reaches the runtime through the description of the value's type:
  a float's node (tag 24) holds the address of the runtime's table entry, and
  the inspect routine jumps there to append the text.

Arithmetic and comparisons are SSE2 instructions emitted in place. Map
routines take key type 24 and a type variable's comparator 12 for floats.

## Checked against the pinned compiler

- Runtime, linked into a test driver and compared with Go 1.27.4 running the
  pinned functions: 235,784 texts (`to_string` and `inspect` of powers of two
  and ten and their neighbours, subnormals, ties, random bits), 62,972
  parses, 542,160 roundings, whole-number conversions and ratios, 125,184
  powers on the fused path and again on the plain one (`GODEBUG=cpu.fma=off`).
  One difference: `floor`, `ceil` and `trunc` leave a signalling NaN as it
  is where Go quiets it; no operation of the language makes one.
- Through both compilers, program by program: 18,160 literals, each through
  interpolation and `inspect`; 200 programs of constant expressions (1,850
  expressions; both compilers reject the same 68 programs for overflow);
  2,400 lines of expressions over bindings; 6,000 lines of the functions
  above; and the programs of the gate.

- The conversion by unrounded scaling, linked into a test driver
  (the runtime's bytes called from C) and compared with Go 1.27.4's
  `strconv`: the text of 67,944,045 floats (60 million random bit patterns
  weighted towards subnormals, mantissas at both ends, whole numbers and
  short decimals; every power of two with the 40 floats on each side of it;
  every power of ten from 1e-330 to 1e310 with 200 neighbours on each side;
  the first three million subnormals; four million small whole numbers and
  fractions) read back by Go as the same float and held the digits and
  exponent of `FormatFloat(x, 'e', -1, 64)`, and 11,944,045 of them gave
  byte for byte the text of the exact runtime that stood here before.
  12,000,000 texts parsed as `ParseFloat` parses them: shortest and
  17-to-20-digit forms of random floats, random digits and exponents,
  halfway points between neighbouring floats written out to 800 digits and
  the same with one late digit moved, 19 and 20 digit mantissas, powers of
  two written exactly, and the forms Go refuses. `harness/speed.py` holds
  367 lines of both through the compilers.

## Differences that remain

- `Gen.float`, `JSON` and `Markup.of` take or give floats in the pinned
  language; those modules are not compiled at all.
- A float literal may have 400 digits before the point, 1000 after it and
  400 in its exponent; the pinned compiler sets no bound. The scanners call
  themselves once per byte within a fixed count, as for names and integers.
- Found here and not particular to floats: a map literal with the same
  literal key twice is accepted (the pinned compiler rejects it), tuples are
  no map keys, and `0x`, `0o` and `0b` integers are not read.
