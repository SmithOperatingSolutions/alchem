# Protocols

`defprotocol` and `defimpl` follow the pinned compiler: a protocol declares
functions, an implementation supplies them for one type, and a call
`Protocol.function(value, ...)` is resolved when the program is compiled,
from the type of its first argument. There is no dispatch while the program
runs. `harness/protocols.py` holds 18 programs with the pinned compiler's
output and 27 it rejects. The code is
`implementations/alchem/native-protocols.alc`.

## How it is compiled

The rewriting of `alchem-macros.md` takes a protocol's declaration out and
turns each function of a `defimpl` into a function of its module:

```alchem
defimpl Describe, for: list[a] do      def describe$Describe$4(items: list[a]): string do
  def describe(items): string do   ->    "a list of #{length(items)}"
    "a list of #{length(items)}"       end
  end
end
```

The name is the function, the protocol and the number of functions the
module defined before the `defimpl`, joined by byte 127, which no program
can write; a trace shows it with `$`, the name the pinned compiler gives the
function. The type is written on the first parameter. Being a function of
its module, the implementation reaches the module's private functions,
types and constants, and takes the hidden arguments of a generic function
when its type holds type variables (`alchem-generics.md`).

A call of a module the program does not have, `Name.function(...)`, is a
protocol's when some function is named `function`, 127, `Name`, 127, ...
(`mp_or`, from `nc_name_other`). The arguments are typed once; the first
must have a type of its own (not `none`, `[]` or a function still to be
typed). The implementations are tried in the pinned compiler's order: the
modules each after those it imports, the entry last (`mp_order`, from the
bundle's import lines), and within a module in the order of the text. The
first whose type the argument's type fits is called (`nu_unify`, so
`list[a]` takes any list and a type variable takes anything); the other
arguments are then checked against that one alone.

- A protocol is known by its name in every module, without an import.
- A call of the protocol's function from its own implementation for the
  same type is a call of the function to itself: in return position it is a
  jump, as in the pinned compiler (`alchem-tail-calls.md`).
- `&Protocol.function/2` is written `&Protocol.function(&1, &2)` (up to 9).
- A value piped into a protocol's function is its first argument.

## What is rejected, as the pinned compiler rejects it

A protocol without functions, one whose function takes no value, a name
that is not one capitalized word, a protocol declared twice (in any
modules); a `defimpl` of an unknown protocol, without functions, with a
function the protocol does not declare, with another number of parameters
or another result type, lacking a function, for a type the protocol is
already implemented for, or with a first parameter typed otherwise; a call
for a type without an implementation, on a value whose type is a type
variable of the calling function, without arguments, or with arguments the
chosen implementation does not take; `function(...)` without the protocol's
name.

The pinned compiler does not build an implementation whose function has a
pattern for a parameter, a guard, several clauses or no result type (it
fails on the name it made); these are rejected too.

## Differences from the pinned compiler that remain

- The number in an implementation's name counts the `def` and `defp` of the
  module before the `defimpl`, as the pinned parser counts its functions;
  what else that parser reads as a function (the tests of a test block) is
  not read by this compiler at all.
- The type of a `defimpl`, a first parameter's own type and the result
  types are compared as written, token by token (`list[ integer ]` is
  `list[integer]`).
- Every compile error is `E_COMPILE`.
