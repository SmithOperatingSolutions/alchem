# Type variables

The self-hosted compiler supports the pinned language's generics: a lowercase
type name that is not a built-in type is a type variable.

## Generic functions

`def first_or(items: list[t], fallback: t): t` is generic in `t`; each call picks
its types by matching the parameter types against the arguments, and the result
type follows. Inside the function a value of type `t` can be passed, stored,
returned and compared with `==` and `!=`, but not used in arithmetic or ordering
(the library's own functions order the values of a variable they name `ord...`:
`alchem-ordering.md`).

- A lambda or capture among the arguments takes its parameter types from the
  variables the other arguments settle, whatever its position.
- `&name`, `&name/arity` and `&Module.name` for a generic function are function
  values for the types the use site expects: `f: fn[string, string] = &id/1`.
  Without an expected function type the reference is rejected.

## Generic structs and sum types

`struct Pair[a, b] do left: a ... end` and `type Tree[t] do leaf ... end` take type
parameters. A type is written with its arguments, `Pair[integer, string]`,
`Tree[t]`. A literal or constructor settles the parameters from its values;
one it leaves open (`Tree.leaf`) is settled where the value meets a type.
Field reads, updates and patterns use the fields' types with the arguments in
place.

## How it is compiled

Every value is one word whatever its type, so a generic function is compiled
once and no code is made per choice of types. A type variable is tag 16 with
its name; a generic instance is tag 18 (struct) or 19 (sum type) with its
declaration's position, the number of arguments and the arguments. Matching a
declared type against a given one builds a substitution, which gives the
result type and the instance's field types.

Equality is the one operation that needs to know a type (with the order, for
the library: `alchem-ordering.md`). A generic function
therefore takes one hidden argument per type variable after its parameters: a
comparator, which is 0 for values compared as words, 1 for strings, 12 for
floats, or a function value taking two values (and 0 in RDX) and leaving 1 or 0. A call passes the
comparator of each type it settles: a constant, the caller's own comparator
when the type is one of its variables, the equality function of a struct or
sum type, or for a list, tuple or other compound type the address of code
placed at the call behind a jump. A comparator below 4 GiB is such an address
and is called directly; nothing is allocated. Only a compound type that itself
mentions one of the caller's type variables needs a function value holding the
caller's comparators, and that is a record from the arena. The equality
function of a generic struct or sum type takes the comparators of its type
arguments in RDX, RCX, R8, R9, R10 and RAX; a type with more than six
parameters takes in RDX the address of an array of them on the caller's stack.
A generic function whose parameters and comparators number more than six
takes those past the sixth on the stack.

A generic function of the program that inspects a value of a type
variable's type, or writes or reads it as JSON, takes after its
comparators one more hidden argument per type variable: the address of
the description of the variable's type (its twin, named as the variable
and byte 127). `alchem-json.md`, "Type variables", has how the twins are
made and which functions take them; a function that needs none, and every
function of the library, keeps the convention above. A twin is not a
comparator: it is passed as it is when a function is compiled with the
equality of a variable withheld (`native-needs.alc`).

## Where a value takes its type

The pinned compiler types an expression against the type its context expects,
arguments from left to right. The native compiler follows the same rules, so
it rejects what the pinned compiler cannot type:

- `none`, `[]`, `%{}`, `ok(1)`, a variant of a generic type, or a call of a
  generic function whose result is still open, bound without an annotation.
- The first element of a list, the left operand of `==`, an arithmetic
  operator or `<>`, and the first argument of a library function, when they
  need a type from their context. Later elements, right operands and later
  arguments take the type the first one settled.
- A lambda in a generic call whose parameter types only a later argument or
  the result settles, unless the call is the whole value of an annotated
  binding or an argument with a known type.
- `&name` of a generic function where the expected function type is itself
  generic.
- A struct or variant pattern as a lambda parameter.
- An argument for a parameter the pinned library writes `enum[...]` (the
  enumerable of `Enum`, `Stream`, `Map.new`, `MapSet.new` and others: 175
  functions, `native-enumerable-data.alc`, made from the pinned
  registrations by `scripts/generate-enumerable-params.py`) that needs a
  type from its context and is not the literal `[]`: the pinned checker
  gives such a parameter's argument no expected type (`library()` in
  `library.go`). So `Enum.reverse(Enum.reverse([]))`, `Map.new([{"a", []}])`,
  `Enum.reverse([none])` and `Enum.reverse([]) |> Enum.reverse()` are
  rejected even where the result has a type, while `Enum.reverse([])` and
  `[] |> Enum.reverse()` are not (`native-enumerable.alc`). The library
  written in Alchem is not held to it.

## Function types as type arguments

A function or a stream has no equality, so a type that holds one has no
comparator (`assert_raise("...", fn -> Stream.map(...) end)` gives a
library function a stream for its type variable). A
generic function that is given such a type for a variable takes the
comparator of words for it (`nu_comparators`), which it never calls (a
function of the program that would is rejected, below): `Enum.each(callbacks, ...)`,
`Map.get(handlers, name)`, `Enum.zip(fs, xs)`.

The pinned compiler rejects a function type where equality is needed. For
the library that is a table (`eq:` in its registrations), which
`nu_equal` holds by name: `Enum`/`Stream` `dedup`, `member?`, `uniq` (every
variable), `chunk_by`, `dedup_by`, `uniq_by` (the last: the key the
function gives), `List` `myers_difference`, `delete`, `starts_with?`,
`ends_with?` (every variable), the `List.key...` functions (the first: the
key) and `Map.equal?` (the second: the value). A call that gives such a
variable a type holding a function is rejected (`nu_refused`).

A function of the program whose result type names a type variable that no
parameter has is rejected, as upstream (`type variable t does not appear in
a parameter`); the library's own may (`MapSet.new(): set[a]`).

## Which variables need equality

For a generic function of the program the pinned compiler works out which
variables need equality from the bodies (a fixpoint over every use, before
any code is made: `analyze.go`), and rejects a use that gives such a
variable a type without equality: `same(f, f)` for
`def same(a: t, b: t): boolean do a == b end` with function arguments, and
the same through any chain of generic functions that hand the type on.

The native compiler makes each function's code once and keeps no fact about
a function but its signature, so it asks where it matters
(`native-needs.alc`): at a call that gives a variable of a function of the
program a type without equality (`nq_comparable`: it holds a function or a
stream, also inside a struct), the callee is compiled once more with a
record in its environment (type 46 and the variable's name) under which
that variable has no comparator (`nu_vars`). Every comparison of a type
that mentions the variable (`==`, `!=`, `in`, `--`, a pinned binding,
`uniq: true`, a library function that compares) then fails to compile; if
the function compiles as it is and not so, it needs the variable's equality
and the call is rejected. Inside such a compilation a call that gives a
type mentioning the variable to another function's variable asks the same
of that function (for a library function, its `eq:` table), which is the
fixpoint's step; the record lists the functions and variables being asked
about, so a cycle adds nothing. A use in a function that is never called
is rejected too, as upstream.

`harness/generics.py` checks these against the pinned upstream outcomes.
