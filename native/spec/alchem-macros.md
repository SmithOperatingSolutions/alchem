# Macros, and how a program is rewritten before it is compiled

`defmacro`, `quote`, `unquote`, `use` and `__using__` follow the pinned
compiler (`compiler/syntax/macros.go`): a macro is a template, and a call is
replaced by a copy of it with the arguments put in. `harness/macros.py`
holds 61 programs with what the pinned compiler prints for each, traces
included, and 41 it rejects. The code is
`implementations/alchem/native-macros.alc`.

## The rewriting

The compiler reads positions in one text and has no tree to rewrite, so
macros are expanded as text before anything else looks at the program
(`mx_prepare`, called by `nc_compile`). The same pass takes out protocols
(`alchem-protocols.md`), HTML templates (`alchem-templates.md`) and the `fn`
whose clauses stand on the lines after it (`alchem-parsing.md`). A program
that holds none of these is compiled as it was given, byte for byte.

The receive assertions are rewritten first (`ac_receives`,
`alchem-processes.md`; `nc_rewritten` is called with what that leaves). That
rewriting keeps every line and names its failures in its own text, so the
tables this one keeps are those of the text it was given, and a receive
assertion in a template or in a block given to a macro is named as the
pinned compiler names it: at the call, or where the block wrote it. The
library is chosen from the rewritten text (`ny_prelude`), so a function
that only a template or a function added by `use` mentions is there.

1. **Index** (`mt_index`). One walk over the tokens at the depth of a
   module's declarations notes every module, function, macro, `use`,
   protocol and `defimpl`, and what is left as it is: a type's declaration
   and a function's parameters (a default value is a constant, which the
   pinned compiler does not expand either), and the value of a module
   constant.
2. **Pieces** (`mx_edits`, `mx_walk`). The rewritten text is a list of
   pieces of 13 bytes: bytes of the program standing where they stood;
   bytes standing for one place (a template's own text stands where the
   macro was called); up to five bytes of the compiler's own; and the
   pieces of an HTML template's values. A piece may also name a place whose
   file it is shown in.
3. **Text and tables** (`mx_made`). The pieces give the text, and one moved
   record per run of pieces says where the run starts in the rewritten text
   and where it stands in the program as written. The source the compiler
   then sees is the rewritten text, the library, and a tail: the moved
   records and the newline, file and continuation tables of the program as
   written (`mx_tail`, `mx_part`). `nz_blob` hands them to the failure
   routine, which turns a position of the rewritten text back before it
   names it (`alchem-traces.md`).

## What is expanded

- `defmacro name(a, b) do quote do ... end end`, with a last parameter
  `do: block` for a `do ... end` block. A macro is called by its name in its
  module and as `Module.name(...)` from any other, wherever a call may
  stand in a function: statements, values, arguments, the code of
  `"#{...}"`, guards, the arguments of another macro.
- A call that is a whole statement is replaced by the template's
  statements. One used as a value is replaced by the template in
  parentheses, so a template of several statements there is rejected, as
  the pinned compiler rejects it.
- `unquote(name)` is the argument, written again each time it is unquoted;
  in parentheses unless it is one token, one bracket, a name with its call,
  or stands alone between brackets, commas or the ends of a statement. The
  block is its statements where `unquote(block)` is a statement and the
  block in parentheses anywhere else.
- A value piped into a macro, `value |> square()`, is its first argument:
  the value is everything `|>` takes on its left, by the pinned parser's
  precedence.
- A name the template binds takes a suffix of its own in each expansion
  (byte 127 and four characters made from the place of the call), so it
  neither captures nor is captured. A function of the macro's own module
  called from the template is written `Module.function` when the macro is
  used from another module, and so is `&function/arity`.
- The template may call macros: of its own module, then of the module
  using it. Expansion stops 64 calls deep.
- `use Module, name: value` adds the functions of `Module`'s `__using__`
  template to the module, each `unquote(name)` being the value given.
- Rejected, as the pinned compiler rejects them: the wrong number of
  arguments; a block given to a macro without a block parameter, or none
  to one that has it; `unquote` of what is no parameter, or of more than a
  name; a macro and a function of one name; a macro defined twice; `use`
  of a module the program does not have, of one without `__using__`, with
  an option missing or one too many, or adding a function the module
  defines; a macro that keeps expanding; `unquote` where a pattern stands
  (before the `=` of a binding, as the pattern of a receive assertion).

A function's call to itself in return position is a jump in expanded code
as anywhere (`alchem-tail-calls.md`): the rule reads the rewritten text, in
which a function added by `use` and the statements of a template are
ordinary code.

## Where a failure is named

As in the pinned compiler: the template's own code stands at the call (the
`T` of `Tools.square(...)`), on the call's line; an argument and a block
stand where they were written; an argument that is a whole statement of the
template is that statement, at the call, around its own places (the
expansion writes it in parentheses for this). A function that `use` adds is
shown with the lines of the template and the file of the module using it,
which is what the pinned compiler shows.

## Names the compiler makes

Byte 127 continues a name (`is_identifier_continue`), and only the
rewriting writes it: the suffix of a template's bindings, the names of the
functions of a `defimpl`, the parameter of a `fn` with clauses. A program
whose own names hold the byte is rejected (`mx_tainted`).

## Differences from the pinned compiler that remain

- The names a template binds are found in its text: what stands before `=`
  and `<-`, the patterns before `->` (not the conditions of a `cond`), the
  parameters of `fn`. The pinned compiler takes them from its tree. They
  agree on every form the gate holds; a pattern written across several
  lines outside brackets is read from the line its `->` stands on.
- Whether a call is a statement or a value is read from the tokens around
  it. A one-line template is the same text either way; a template of
  several statements needs the call to be a whole statement, which it is
  wherever the pinned compiler takes it as one.
- A template of several lines put into the `#{...}` of a one-line sigil is
  rejected: the code of a sigil's value ends on its line
  (`alchem-sigils.md`).
- A value piped into a macro inside a template, where that value holds
  another macro call or `unquote`, is rejected: the value's pieces are
  already written when the pipe is met, and only the program's own text is
  cut back.
- A program may hold 64 nested expansions and, rewritten, 4,194,303 bytes.
- Every compile error is `E_COMPILE`.
