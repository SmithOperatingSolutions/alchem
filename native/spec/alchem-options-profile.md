# Native options and collection lookups

Options compose recursively with scalars, tuples and results. See
alchem-structural-types.md for type inference and the shared representation.

`some(value)` evaluates one operand and allocates a 16-byte aligned record
containing tag1 and its full 64-bit value/pointer. `none` is a null option and
allocates nothing. Some(0), some(false) and some(empty bytes/string) remain distinct
from none. Options cannot be used as booleans, numbers or record-comparison values.
Typed function arguments/returns, private/recursive calls and matching branch
results preserve option payload types. None may inhabit any declared option type
or unify with a concrete option branch. A bare none binding has no inferred payload
type; matching it without a typed context is rejected. There are no implicit scalar
conversions. Nested options retain distinct outer and inner records.

An exhaustive case expression has one `some(name) -> expression` arm and one
`none -> expression` arm, in either order. Branch-local bindings work; the extracted
name is scoped only to the some arm. Both arms are type checked and their result
types must agree (or unify none with a concrete option). Missing/duplicate arms,
unknown payload types and scope leaks are rejected. This supports value expressions,
not general effectful case statements or arbitrary patterns. Parentheses and nesting
follow the existing expression-depth and live-slot bounds.

Byte collection APIs now include:

- Enum.at(bytes,index) and Enum.fetch(bytes,index): option[integer]. Negative
  indices normalize once; absent/extreme indices yield none. Present bytes are
  zero-extended and boxed. The three-argument Enum.at default overload is unchanged.
- List.first(bytes) and List.last(bytes): option[integer], none for empty input.
- List.first(bytes,default) and List.last(bytes,default): integer, returning the
  eager full-width default for empty input. Every argument evaluates left to right.

String.first/string.last return option[string] containing a fresh copy of a
whole pinned-runtime grapheme cluster; empty input yields none. See
alchem-grapheme-profile.md for exact segmentation/provenance and limitations.

Full structural type words replace the original one-byte kind scheme; see
alchem-structural-types.md. The internal ABI returns null or record pointers in RAX.
Normal program allocation remains the checked arena; some charges16, none0,
and option-producing operations additionally charge any operand/result copies.
