# Native structural types

The Alchem-written compiler supports recursively composed `option[T]`,
`tuple[T1,T2,...]` and `result[Value,Error]` alongside integer, byte buffer,
string, boolean, general list/map and typed callback types. Declarations, six-argument calls, return checking,
local inference and conditional merges all preserve the full structural type.
There are no implicit conversions between scalar or container types.

Tuple literals use `{value,other}` with zero to six fields, evaluated left to right.
`elem(tuple,index)` requires a nonnegative literal index within that tuple's
arity; its static result type is the corresponding field's type. Tuple records
are immutable, with one eight-byte arity header and eight bytes per field.
Integers retain all 64 bits; strings and nested values retain their pointers.
The empty tuple `{}` has type `tuple[]` and supports unit success results.
Tuple destructuring, dynamic indices and tuple update APIs are outside this step.

`ok(value)` and `error(reason)` each evaluate one operand and allocate a 16-byte
record: an eight-byte discriminant (one for ok, zero for error) and the full
value/pointer. Both constructors return non-null records. Result cases require
exactly one `ok(name) -> expression` and one `error(name) -> expression`, in
either order. Both arms are checked, their result types must unify, and bound
names remain local to their arm. Cases are expressions, not effectful statements.

Examples:

```alchem
def parse_answer(): result[tuple[integer,string],string] do
  ok({42,"answer"})
end

def main() do
  System.halt(case parse_answer() do
    ok(value) -> elem(value,0)
    error(reason) -> byte_size(reason)
  end)
end
```

`some` now accepts nested values, including another option, a tuple or a result.
`none` represents option[unknown]; a one-sided result constructor has an unknown
opposite type. Recursive unification fills these holes from declarations, function
arguments or the other conditional branch. An unknown type is never valid source
annotation syntax. Matching an unknown payload is rejected, so a bare `case none`
or a one-sided result without context cannot supply an arbitrary extracted type.
Typed function returns supply that context to callers.
`none`, `some`, `ok`, `error` and `elem` may name bindings and parameters, as in
the pinned language; a binding named `none` or `some` hides that constructor in
its scope, while case patterns keep their meaning.

## Representation and bounds

Types are collision-free prefix encodings in byte strings, not hashes or
truncated tags. Scalar tags are integer0, bytes1, string2 and boolean3, one byte
each. Option4 and list7 are followed by one child; result6 and map8 by two;
tuple5 has a count byte followed by its child encodings. Unknown9 is internal
inference only. Function10 has a parameter count byte and then parameter/return
encodings. An empty byte string is no type and marks every failure. General list/map storage and typed
callback iteration are implemented; see alchem-collections-profile.md.
A type may have any length (255 bytes was the limit: a longer type's cell has
its length in four bytes behind a byte of 255, and a count of 255 or more is 255
and three bytes; `nt_cell`, `nt_counter`); 130 levels of nesting are accepted, for annotations
and for inferred types alike. Formerly (the first limit was one 60-bit word, which a
function type over a tuple of collections exceeded). For example
result[tuple[tuple[list[string], map[string, string]], string], string] takes
12 bytes, and a tuple of five tuples of six tuples of six strings 252. The
nesting bound exists because the compiler recurses once per level. Tuples have zero to
six fields. Oversized annotations or constructor types reject at compilation.
The existing 16 live locals, expression depth16, 256 active frames, 4MiB user
arena and executable-size limits still apply.

Compiler packets use a u24 source cursor, the type's length byte and the type.
Environment records, argument packets and type lists hold each type after its
length byte, so records vary in size and are walked in slot order. The function table holds the position of each
result annotation instead of a type, so its records keep their 27 bytes.
Function records are27 bytes: five u24 source positions, argc, flags, eight
bytes (the position of the result annotation, the number of defaults and the
position of the guard) and the u16 index of the owning module header. Flags are
main1, public helper0, private helper16, module header32 or further clause40;
see alchem-modules.md and alchem-clauses.md.
Argument packets store six full type words. Environments have a u16 function
index followed by15-byte name/slot/type records. The function table at file
offset1152 has one slot per table record (65536 at most, 65535 of them functions; alchem-modules.md) and the shared runtimes; code follows it. The source limit is 4,194,303 bytes: a position needs 22 of its 24 bits, and bits 22 and 23 of a value's position are the flags of source-capacity.md.
Native compiler entry requires a public one-argument byte-to-byte signature.
No new bootstrap IR version or host language runtime is needed.

`harness/structural_types.py` verifies nested values, signed endpoints, mixed
six-argument calls, both result orders, inference, immutable tuple reuse, scope/
type/arity errors and checked arena exhaustion. `harness/type_words.py` verifies
full-width transport and arithmetic against Python. Both run at A1, A2 and A3;
the existing integer suite also checks the65535/65536-function boundary.
