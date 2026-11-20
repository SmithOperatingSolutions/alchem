# Structs and sum types

The self-hosted compiler supports the pinned language's named types: structs
and sum types, declared in a module and used from it or from a module that
imports it directly.

## Structs

```alchem
struct Account do
  owner: string
  balance: integer = 0
end
```

- `%Account{owner: "ada", balance: 10}` builds a value. Fields may come in any
  order; a field that is left out takes its default, and one without a default
  must be given. Unknown and repeated fields are rejected.
- `value.field` reads a field, also after a call, a literal, `elem(...)`, a
  parenthesized expression or a capture placeholder: `deposit(a, 1).balance`,
  `&(&1.owner)`.
- `%Account{value | balance: 5}` copies value with the given fields replaced;
  value must be an Account.
- A default is an expression compiled where the literal stands, without the
  bindings around it.

## Sum types

```alchem
type Shape do
  circle(radius: integer)
  rect(width: integer, height: integer)
  empty
end
```

- `Shape.circle(2)` and `Shape.empty` build values; a variant takes exactly its
  fields, up to six.
- `case value do Shape.circle(r) -> ... Shape.rect(w, h) -> ... Shape.empty -> ... end`
  binds the fields to names (`_` binds nothing); struct and variant patterns
  nest and stand in bindings and parameters too (alchem-patterns.md). The arms must cover every
  variant, or end in a catch-all `_ -> ...` or `name -> ...`, which binds the
  whole value. An arm for a variant already matched, or any arm after a
  catch-all, is rejected as unreachable. All arms have one type.
- A sum type may refer to itself: `node(left: Tree, value: integer, right: Tree)`.

Structs and sum types may take type parameters, `struct Pair[a, b]` and
`type Tree[t]`; see alchem-generics.md.

## Names and imports

Types are nominal: two declarations with the same fields are different types,
and each is named by its module, as in upstream's messages (`App.Account`).
Inside its module a type is written `Name`; from a module that imports it
directly, `Module.Name`: `%Geo.Size{width: 3}`, `x: Geo.Shape`,
`Geo.Shape.rect(2, 5)` and the pattern `Geo.Shape.rect(w, h)`. A module's own
type and an imported type may share a name. Type and variant names follow the
pinned rules: a type is one capitalized word, a variant is not capitalized.

## Representation

A named type is tag 13 (struct) or 14 (sum type) followed by the source position
of its declared name, so identity is the declaration. An annotation is parsed
without knowing its module and names the declaration by where it was written
(tag 15); it is resolved against the function table wherever a signature,
binding, lambda or field is used. Each declaration takes one table record
(flag 64 or 128) and no code. Fields and variants are read from the declaration
when needed.

A struct value is laid out like a tuple: the field count, then one word per
field. A sum value is the field count plus one, the variant's index, then its
fields. Both come from the checked arena (exit71 when exhausted). A literal
allocates its record first and stores each field as it is evaluated, in the
order written, then the defaults. A case keeps its subject in a frame slot
under an environment record with no name, tests the variant index arm by arm
and copies the named fields into slots.

## Native limits beyond the pinned language

- A struct has at most 32 fields and a sum type 127 variants.
- A declaration that is never used is only checked for its outline.

## Equality

`==` and `!=` compare lists, tuples, options, results, maps, structs and sum
types by structure, as the pinned language does; function values, and anything
holding one, cannot be compared, and ordering (`<`, `<=`, `>`, `>=`) stays with
integers and strings. Maps are equal when they hold the same keys with equal
values, whatever order they were built in.

The comparison is code made for the type, not a walk over tagged data: values
carry no type at run time. Each piece takes the two values in RDI and RSI and
leaves 1 or 0 in AL; tuples chain their fields and skip the rest at the first
difference, lists and maps loop, and a struct or sum type is compared by a
function in its declaration's table slot, so a type that refers to itself
compares by recursion. That function returns at once for the same record and
stops with status 70 when 7 MiB of stack are in use, far beyond the 256 frames
of user functions. `harness/equality.py` checks 240 random typed pairs against
a structural oracle, and structs, sum types and maps against upstream.

`harness/records.py` checks structs and sum types, local and imported, with
rejections and invalid declarations; every outcome equals the pinned upstream
compiler's.
