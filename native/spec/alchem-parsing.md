# Forms the pinned parser reads that the compiler took otherwise

`harness/parsing.py` holds 26 programs with the pinned compiler's output and
17 it rejects for the forms below.

- **A `(` on a new line** starts a statement: `y = x` and then `(x + 1) |>
  IO.inspect()` are two statements, and `y = f` followed by `(3)` is the
  unknown binding `f`, not a call (`nc_name_other`; a call's parenthesis
  stands on the line of its name).
- **A `[` on a new line** after a line that ends in a binding called `b`
  starts a statement. `b[` is a byte literal only where the bracket stands
  against the `b` and no binding called `b` holds a list, a map or a tuple,
  which `b[0]` reads (`nl_bytes`). (The pinned language has no byte
  literals; the compiler's own source is written with them.)
- **`fn -> value end` after a binding** is the function's value: `fn ->`
  is no arm of a `case` (`nx_ends`). Bound without a type, `m = fn -> 1
  end`, it is rejected like any `fn` nothing gives a type.
- **`fn` with clauses** on the lines after it, each `pattern -> body` with
  an optional guard, is `fn name -> case name do ... end end`, the `case`
  standing where `fn` stands, as the pinned compiler lowers it
  (`mx_clauses`, in the rewriting of `alchem-macros.md`).
- **`hd([])`**, the head of a list whose elements have no type yet, takes
  its type from where it stands: an annotated binding, an argument, the
  right operand of an operator, the other branch of an `if` or another arm
  of a `case` (`nk_kernel`, `nw_held`). Alone (`y = hd([])`,
  `IO.inspect(hd([]))`, the left operand) it is rejected, as upstream.
- **Variants and fields** may have any name but the words the pinned
  language keeps (`true false def defmodule do end else if return and or
  not assert case when fn import extern require defp in cond raise with
  for unless defprotocol defimpl defmacro`): `integer`, `string`,
  `boolean`, `float`, `option`, `list`, `map`, `length` are names like
  others (`nv_member`), in declarations, constructors, patterns, literals
  and `value.field`.
- **`( call )` as a statement** is the call: `(f(1))`, `(IO.puts("x"))`,
  `(a |> f())`. Any other value in parentheses is no statement, and an
  `if` in parentheses whose branches leave no value is rejected
  (`nx_callish`, `nx_wrapped`, `nc_parenthesized`).
- A string without its closing quote in a function body, and a variant
  that its type does not have in a `case`, are compile errors (they ended
  the compiler with status 72).
- So are twenty more texts a search found (`scripts/fuzz-compiler.py`,
  `harness/fuzz-cases.json`), each of which wrote a position that was -1
  into a record and ended the compiler with status 72: `case` or `cond`
  with no block before an `end`, an `if` without `do` in a list or an arm,
  a string without its closing quote in a call, after `rescue`, among a
  function's parameters or as the name of a `defimpl`'s function, `@`
  before a string, a range with no last value or one no integer holds, a
  map pattern whose key is no expression or whose `=>` is another
  operator, `fn(...): Name do` with a result type that is none, a
  variant's or a struct's field of a type that is none, and a bundle whose
  manifest gives a length of more digits than an integer has.

## Differences from the pinned compiler that remain

- A function that returns a `fn` returning another `fn`, written without
  types (`fn x -> fn y -> ... end end` under an annotation), is still
  rejected: the inner function is typed before the outer one's result type
  reaches it (`alchem-closures.md`).
- `b[1, 2]` in a program that is not the compiler is a byte literal here
  and a syntax error in the pinned language.

## Undeclared type variables in a declaration

A field of a struct, or of a variant of a sum type, whose type mentions a
type variable that the declaration does not list as a parameter is rejected,
as the pinned compiler rejects it (`unknown type "b"`). `nd_closed` in
`native-records.alc` checks each declaration once when the table is built.
