# Patterns

The self-hosted compiler matches patterns as the pinned language does: in
`case` arms, in bindings, and in the parameters of named functions and of
`fn p -> ... end`.

## Forms

- `_` matches anything; a name matches anything and binds it; `^name` matches
  the value of an existing binding (any type `==` can compare).
- Integer and string literals, `true` and `false` match themselves.
- `{p, q}` matches a tuple; `%Name{field: p}` a struct, fields not listed being
  ignored; `Name.variant(p, q)` and `Module.Name.variant(p)` a sum variant;
  `some(p)`, `none`, `ok(p)` and `error(p)` options and results.
- `[]`, `[p, q]`, `[head | tail]` and `[p, q | tail]` match lists. A tail that is
  named or matched further is the list from that element on: nothing is copied.
- `%{key => p}` matches a map holding every listed key with a matching value;
  `%{}` matches any map.
- Patterns nest to any depth, and a name may be bound once per pattern.

## Where they stand

- `case value do pattern -> body ... end` works for a value of any type. An arm
  may have a guard, `pattern when condition -> body`. The arms must match every
  value: integers, strings and maps need a catch-all, while booleans, options,
  results, sum types, lists and their combinations are complete when every
  shape is covered, for example `{true, n}` and `{false, n}`. An arm that no
  value can reach is rejected, as is a case whose only cover is guarded.
- `pattern = value` binds the names of a pattern that need not match every
  value; a value that does not match stops the program with status 2 and, on
  standard error, `file:line:column: pattern match failed` and the active
  calls (`spec/alchem-traces.md`).
- A parameter of a named function may be a pattern, `def f({a, b}: tuple[integer, integer])`.
  The clauses of a function together must match every value
  (`spec/alchem-clauses.md`). A parameter of `fn {a, b} -> ... end`
  may be any pattern and fails like a binding when it does not match.

## How it is compiled

A pattern is parsed against the type it matches into a small tree: anything,
a name's slot, or a constructor with its sub-patterns, the number of
constructors its type has (none for integers, strings and maps), and how its
value is tested and its parts found. Matching code takes the value in RAX and
leaves 1 or 0 in AL: a constructor tests its tag, keeps the value on the stack
and matches each part in turn, skipping the rest at the first failure. Literals
and pins compare with the code `==` uses. A list's tail and a map's value are
found at run time; a tail is the address of the list's second pair
(`np_tail`, `alchem-lists.md`) and takes no memory.

Exhaustiveness and unreachable arms use the usual matrix test on those trees: a
row of patterns is useful when it can match a value no earlier row matches,
found by specializing on each constructor when the earlier rows name all of a
type's constructors and by dropping the column otherwise.

The cases with one arm per constructor of an option, result or sum type keep
their direct code; every other case goes through the matcher.

## Native limits

- Annotated lambdas take plain names, as upstream requires.

`harness/patterns.py` checks these against the pinned upstream outcomes.
