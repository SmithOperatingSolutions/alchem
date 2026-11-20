# try, exceptions and throw

`try do body rescue arms catch arms else arms after block end`, `raise` of an
exception, `defexception` and `throw` follow the pinned compiler.
`harness/exceptions.py` holds the programs with what it prints for each,
traces included, and the programs it rejects. The code is
`implementations/alchem/native-try.alc`; the part that runs when a program
fails is the start of `spec/trace-x86_64.s`.

## The forms

- A `try` needs a `rescue`, a `catch` or an `after`. The sections come in the
  order rescue, catch, else, after, each at most once, and `rescue`, `catch`
  and `else` need at least one arm.
- **rescue** arms match a failure: a string literal, a name or `_` (with an
  optional guard) matches the message of any failure; `%Name{field: pattern}`
  matches an exception of that type; the first arm may be `name in Name`,
  which binds the exception. An arm that matches nothing passes the failure
  on. Every failure has a message: that of `raise(message)`, the `message`
  field of an exception, or the reason of a runtime failure (`integer
  overflow`, `division by zero`, `pattern match failed`, `call depth
  exceeded`, `assertion failed`, `no case branch matched`, a library
  function's `raise`, and the others of `alchem-traces.md`).
- **catch** arms match a value given to `throw`. All take one type: the type
  the body throws (the `throw` calls written in the body, also inside a `fn`,
  but not inside a nested `try` that has catch arms; two different types are
  rejected), else the type of the arm's literal or struct pattern. The first
  arm may be `name: type`, which states it. A thrown value of another type
  passes on, as does a failure; a throw passes through rescue arms. One that
  nothing catches ends the program with `uncaught throw`, naming the `throw`,
  and no calls.
- **else** arms match the body's value when nothing was raised or thrown. The
  body must then end in a value. A failure in an else arm is not rescued by
  the same `try`; a value no arm matches fails with `no else clause of this
  try matched`, naming the `try`.
- **after** runs on every way out, after any arm, and its value is dropped; a
  failure or a throw that passes goes on once it is over, and one raised
  inside it takes its place. `System.halt` does not run it.
- `defexception Name do message: string ... end` declares a struct with a
  `message: string` field and no type parameters; it is a struct in every
  other respect (literals, defaults, patterns, `inspect`, `==`, imports as
  `Module.Name`).
- `raise(%Name{...})` and `raise(name)` for a binding of an exception type
  raise the value; any other argument must be a string. `raise` and `throw`
  stand for a value of any type.
- As a value the body (with `else`, every else arm) and every rescue and
  catch arm end in a value of one type. As a statement whose value is
  dropped they end in statements. `return` may not stand inside a `try`.
- Inside the body and the arms of a `try` a line that starts with `rescue`,
  `catch` or `after` (not followed by `=` or `:`) ends the block, as in the
  pinned parser; elsewhere, and in an after block, they are ordinary names.

Call depth is counted as the pinned runtime counts it: a rescue or catch
stage that takes the failure goes back to the depth of its `try`, an after
block that runs while a failure passes runs at the depth of what failed.

## How it is compiled

A `try` is code in the frame of its function, like `if` and `case`. It keeps
two slots: the failure record its handler was entered with, and the value of
its body. While the body runs, a handler record is on the stack (the record
before it, the handler's address, RBP and R15) and the word at R14-16 points
at it. Every failure enters the routine of `spec/trace-x86_64.s`; with a
handler it does not print but pushes a failure record where it stands (what
failed, the message as a string, a raised or thrown value and its type, the
try's frame as it was) and jumps to the handler with RBP of the try and RSP
at the record. The handler therefore runs below everything that failed.
Nothing is unwound until an arm takes the failure: then the stack pointer goes
back to the handler record's. An arm that does not match, a type that does
not fit and an after block that is over hand the failure record to the
routine again, which looks for the next handler; when there is none it puts
every frame it passed back as it was and prints the failure where it first
happened. A try with an after block has a second handler record around the
first, whose handler is the after block.

A thrown or raised value carries its type as a string of the compiler's type
bytes, which a catch arm or an exception arm compares with its own.

The reasons the routine knows by number are strings now, so that a rescue
arm takes one as its message without copying.

## Traces

The pinned compiler makes a `try` a function called on the spot, its handler
a deferred function, each arm one more function and the after block another
deferred function; Go runs deferred functions on top of the stack that
failed. A trace of a failure raised in an arm, a guard or an after block
therefore shows the arm, the handler, then every call of the failure being
handled, then the try and its function. The native trace shows the same
lines:

- the try is a closure record on the stack (the line of its statement under
  it), a body with else arms one more, an arm that runs another;
- a handler stands on the line the pinned compiler's generated code has for
  it, counted from the after block, the arms before it and the line of the
  `try` (`ty_arm`, `ty_build`): the lines of an arm's test, of the arm while
  its body runs and of the handler when it passes the failure on;
- the failure record is itself a closure record of the try's frame (an odd
  address): the routine then shows the calls that failed, from the record's
  RBP up to the try's frame, and goes on with that frame as the record kept
  it.

With else arms the function stands, while the try runs and for the rest of
that statement, on the line the generated code ends on, four lines after the
last else arm.

## Differences that remain

- **The line of the try after a handled failure.** When an arm of the
  handler has finished and the after block then fails, the pinned program
  shows the try's closure on the line of whatever block Go's compiler laid
  out last in that function (it is where a recovered function resumes). That
  is a property of Go's block layout, not of the Alchem source. `ty_stub`
  follows it for a body that ends in a plain statement, an `if` with `else`,
  a `cond` and a `case`, as far as the cases probed go (twenty probes, two
  miss: an `if` whose else branch ends in another `if`/`else`, and an `if`
  both of whose branches raise). Only that one line of such a trace differs.
- **A `try` that does not start its statement's line.** The lines of a
  handler are counted from the line the `try` stands on; the pinned
  compiler counts from the line its statement starts on. They differ for
  `x =` on one line and `try do` on the next, and only for the first arm's
  guard and for a handler without arms before it passes a failure on.
- **`_ in Name`** is rejected. The pinned compiler accepts it and then fails
  to build the program (`declared and not used` from its Go compiler).
- **Failures of the native library runtimes** are failures like any other
  now (`alchem-failures.md`): `String.to_integer("zz")`, a negative count
  to `Enum.slice`, a base out of range and the rest are rescued by their
  message and traced at the call.
- **Compiler entries.** A program with a `native_compile` entry has no trace
  routine and cannot use `try` or `throw`.
