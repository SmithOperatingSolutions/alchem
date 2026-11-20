# Function values and closures

The self-hosted compiler supports anonymous functions that capture enclosing
bindings, and calls through function values, as the pinned language does.

## Forms

- `fn(x: integer, y: string): integer do body end` states its own types.
- `fn x, y -> body end` takes its parameter types from where it is used, and
  its result type from there too when the place gives one, else from its
  body. The places are those where the pinned compiler types a value against
  an expected type (see "Where a lambda takes its types" below).
- A capture is the short form of such a lambda: `&(&1 + &2)`, or without
  parentheses when it starts with a call, `&String.length(&1)`,
  `&Module.function(&1)`, `&helper(&1) + 1` or `&value.(&1)`. `&1` to `&6` are
  its parameters and their number is the highest one used. It needs the same
  typed context as `fn x -> ... end`.
- `&name` and `&name/arity` refer to a named function of the same module;
  `&Module.name` and `&Module.name/arity` to a public function of the module
  itself or one it imports directly. The arity must be the function's.
- `&String.length/1`, `&Enum.sum/1`, `&byte_size/1`, `&System.pid/0`: a library
  function or builtin by arity is the capture `&String.length(&1)`, with the
  same need for a typed context whose parameter count is the arity, and is
  rejected inside another capture.
- A function value is called as `f(1)` or `f.(1)`. Its type is
  `fn[argument, ..., result]`. A call that returns a function value may be
  called at once, `adder(10)(5)` or `adder(10).(5)`, when the parenthesis is on
  the same line.
- A body may hold bindings and IO.puts/IO.write statements before its value,
  and may itself contain lambdas.
- Lambdas capture the bindings around them. Bindings never change, so a capture
  is a copy made when the function value is created; the value may outlive the
  function that created it.
- A parameter that has the name of an enclosing binding is rejected, as upstream
  does ("closure parameter shadows an existing binding").
- As upstream: a capture cannot contain another capture, even inside a nested
  `fn`; `&N` is not visible inside a `fn` nested in the capture; a capture needs
  at least `&1`; and its parameter count must be the one expected.

## Where a lambda takes its types

The pinned compiler types every expression against the type its place
expects. The native compiler types most values from the inside out and lets
a part still unknown (`none`, `[]`) meet its type later, which a lambda
cannot do: its body needs its parameters' types. So a function type that is
expected is carried to the lambda in the environment, as records with no
name of type 21:

- at the position of an expression, what is expected of it (`nf_expecting`,
  `nw_expect`): the value of an annotated binding, each argument once the
  callee's parameter types are known, the elements of a list, the parts of a
  tuple, the values of a map, the fields of a struct literal or update, what
  stands in parentheses;
- at position 0, what the body being compiled is to give (`nf_ambient`): the
  result type of a function whose result holds a function type
  (`nf_bodied`), and the branches of an `if`, `unless`, `case` or `cond`
  that stands where a type is expected. A `fn` starts its body with a
  record of type 41 and its own result type, which counts the same way.

Only a type that holds a function type gets a record: every other value has
its type without one. A list, tuple or map literal gives its parts the
parts of the type expected of it (`nf_part`).

- **Result type.** `fn _ -> none end` where `fn[option[string],
  option[string]]` is expected has that result type: the body is held to it
  (`nf_seal`), and `return`, a nested lambda or a call that ends the body
  take it as their own expected type. A result type with a part still
  unknown (a generic call whose result variable is not settled yet) is not
  expected; the body gives it. A body that needed a type from its context
  and has none expected (`fn x -> [none, some(x)] end` as an argument of
  `Enum.map` bound without a type) is rejected, as the pinned compiler
  does; so are two branches ending such a body that each lack a part of
  their type (`if x > 0 do ok(x) else error("e") end`: each is a return of
  its own there, where in a binding the two settle each other).
- **Nested lambdas** take the result type of the lambda they end:
  `f: fn[integer, fn[integer, integer]] = fn x -> fn y -> x + y end end`.
- **Elements after the first.** With no type expected, the later elements
  of a list and values of a map are expected to have the type of the first
  (`[fn(a: integer): integer do a + 1 end, fn y -> y * 2 end]`), and the
  later branches of an `if`, `case` or `cond` the type of the first
  (`nf_led`). A first branch that is itself a lambda with no type waits for
  the others, as the pinned compiler holds such a branch back: it is
  compiled once with lambdas standing for values of unknown type, only to
  find where it ends (`nf_hinting`, type 30), then again expecting what the
  other branches gave (`nf_settling`). A list does not wait: its first
  element must have its type, as upstream has it.
- **Arguments that hold a lambda.** An argument that does not compile and
  holds `fn` or `&` (a list of lambdas, an `if` between two, a lambda in
  parentheses) is set aside as a lambda argument is (`nf_late`), and
  compiled when the parameter's type is known (`nf_valued`). A generic
  parameter that is a bare type variable takes no lambda, also when the
  call's expected type settles the variable (`nu_unshaped`).
- **Pipes.** `fn x -> x + 1 end |> apply(1)`, `[fn ...] |> each(1)` and an
  `if` or `case` piped the same way: a left side that does not compile and
  is a lambda, `&(...)`, a bracketed value or a block form waits as the
  call's first argument (`nf_pipe_late`).
- **Calls that end a block.** A call that is a block's whole last statement
  and does not compile is compiled again with the block's expected type as
  the call's own (`nf_tail`): `def f(): list[integer] do Enum.filter([],
  fn y -> y > 1 end) end`. `Enum.map`, `Enum.filter` and `Enum.reduce`
  over a list take what is expected of the call: filter the type of an
  empty list, map the callback's result type, reduce the accumulator's.
  `Enum.f([], ...)` and `List.f([], ...)` are accepted where the call has
  an expected type and rejected elsewhere, as upstream.

- **Forms.** Of a function with several forms, a lambda fits those whose
  function type has as many parameters as the lambda is written with
  (`nf_arities`): `twice(fn x, y -> x + y end, 3)` takes the form whose
  parameter is `fn[integer, integer, integer]`.
- **Generic structs.** A literal of a generic struct where an instance is
  expected (an annotation, the function's result) takes the instance's type
  arguments for its fields (`nf_goal`), so a lambda in a field whose type
  names a parameter has its types: `def kind(w: fn[p, string]): Kind[p] do
  %Kind{write: fn props -> w.(props) end} end`.

## Calling a value

`value.(arguments)` calls any value that is a function: `(fn(a: integer):
integer do a + 1 end).(1)`, `elem(pair, 0).(3)`, `hd(list).(4)`,
`handlers["a"].(5)`, `Map.fetch!(handlers, "a").(4)`. After a call's `)` a
`(` on the same line calls too: `hd(list)(4)`. As upstream: not after
`end` (`fn ... end.(1)`, `if ... end.(1)`); a field's call
`value.field.(1)` only after a name or names joined by dots (`v.run.(1)`,
`box.op.run.(1)`, not `(v).run.(1)`, `mk().run.(1)` or `list[0].run.(1)`);
and a pipe's target is the call alone (`x |> elem(0).(3)` is rejected).

## Annotated bindings

`name: type = value` binds name with the declared type. The value must be
compatible with it (`x: option[integer] = none`, `l: list[integer] = []`), and a
lambda or capture as the value takes its types from a `fn[...]` annotation.

## Pipes

`left |> name(args)` calls name with left as its first argument, for every kind
of call: functions of the module and of imported modules, function values
(`x |> f()` and `x |> f.()`), library functions including those with optional
arguments (`255 |> Integer.to_string(16)`), builtins such as `elem` and
`byte_size`, and constructors. Lambdas and captures among the other arguments
take their types as usual.

- A pipe binds looser than `+`, `-` and `<>` and tighter than comparisons:
  `1 + 2 |> inc()` pipes 3, and `2 |> inc() == 3` compares the piped result.
- The target must be a call: `x |> inc`, `x |> inc() + 1` and `x |> adder(1)()`
  are rejected, as upstream does.
- left is evaluated before the other arguments. A pipeline may continue on the
  following lines, each starting with `|>`.
- `text |> IO.puts()`, `IO.write()` or `IO.warn()` ends a pipeline as a
  statement, wherever those statements are allowed. It has no value, so it
  cannot be bound, passed or returned.

The piped value waits in a frame slot under an environment record with no
name, which starts and ends at the target's `(`; the argument list that opens
there takes it as its first argument. The target is also compiled without the
record: a call that compiles to the same code did not take the value and is
rejected, which covers calls that read no arguments. Pipes inside arguments
nest seven deep (the expression nesting limit); a chain is not nesting.
`harness/pipes.py` checks these against the pinned upstream outcomes.

## Native limits beyond the pinned language

- Parameters and captured bindings together use the live slots of a function
  (250), and every enclosing binding is captured.
- What a body is to give (a function's or a `fn`'s result type that holds a
  function type) is found by the lambda wherever it stands in the body, not
  only where the body ends. The value of a binding without annotation and
  an argument are shut off from it; an operand, a condition or the subject
  of a `case` is not, so `if (fn x -> x end).(1) > 0 do ...` inside a
  function that returns `fn[integer, integer]` compiles where upstream
  rejects it. Telling the end of a body from the rest needs the statement's
  extent before it is compiled.
- `--x` is rejected as upstream rejects it; `- -x` is the same there.
- Pattern parameters and multi-clause `fn` are not implemented. A lambda body
  that ends in an output statement has no value natively.

## Representation

A function value is a pointer to a record whose first word is the code address,
followed by its captured values. A caller evaluates arguments left to right,
loads them into the usual argument registers, puts the record in R10 and calls
through its first word. A lambda's entry copies each capture from the record
into the frame slots after its parameters, so its body compiles like any other
function body. A function-table slot already has the record's shape with no
captures, so `&name` is the slot's address and allocates nothing; named
functions ignore R10. Enum.map, Enum.filter and Enum.reduce call callbacks the
same way.

Lambda code is emitted inside its enclosing function behind a jump, then a
record of 8+8n bytes is allocated from the checked arena (exit71 when exhausted)
and filled. Lambdas have the same entry as functions: the stack limit and the count
of active calls.
The body scanner that finds a function's closing `end` counts an unannotated
`fn` as a block opener; `fn(` (annotated, closed by its `do`) and `fn[` (a type)
are not.

An argument list is parsed before its callee's parameter types are applied, so
a lambda or capture argument is first recorded as deferred: its source position
and its offset in the argument code. Once the callee's types are known, each
deferred argument is compiled and its code placed at that offset, last argument
first, which keeps evaluation left to right. Callees that give no types reject
deferred arguments. A capture's parameters are environment records that start
at its `&` and have the placeholder index as length, so no name matches them;
`&N` reads record N-1. A library function by arity is compiled from the text of
its capture, `&String.length(&1)`, built from the name in the source; that text
names nothing of the enclosing function, so it captures nothing. A function value called at once waits on the stack while
its arguments are evaluated and is popped into R10 for the call.

`harness/closures.py` checks annotated and inferred lambdas, captures and
references, lambdas in every argument position with evaluation order, calls of
call results, annotated bindings, arena and frame limits and
rejections. `harness/modules.py` checks references and captures of imported
functions. Each program's outcome equals the pinned upstream `alchem run`.
