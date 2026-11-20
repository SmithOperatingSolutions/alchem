# Failure traces

A program that cannot go on ends as the pinned runtime ends it: status 2 and,
on standard error, the place and the reason, then one line per active call.

```
/work/lib/util.alc:3:5: pattern match failed
  at Util.unwrap (/work/lib/util.alc:3)
  at App.deep (/work/app.alc:7)
  at App.main (/work/app.alc:26)
```

The reasons are the pinned runtime's: `pattern match failed`, for a value that
does not match the pattern of a binding or of a `fn` parameter, naming the
pattern; `call depth exceeded`, when calls nest more than 100000 deep below
`main`, naming the function entered (a function's call to itself in return
position is a loop and no call, and the library's functions written in
Alchem are none either: `alchem-tail-calls.md`); `exit status must be between 0 and 255`,
naming the `System.halt`; and those of `alchem-operators.md`: `integer
overflow`, `division by zero`, `integer power needs a nonnegative exponent`,
`assertion failed`, `the list is empty` and `no cond clause matched`; those
of `alchem-comprehensions.md`: `no case branch matched` and `no with clause
matched`; those of `alchem-sigils.md`: `list index out of bounds` and `map
key not found`, naming the bracket; and the message of a `raise(message)`,
naming the `raise`. The column counts characters from 1.

## What a trace shows

- Each call is `Module.function (file:line)`, the line being that of the
  statement the call is running. A `fn` is shown as its enclosing function
  with ` <closure>`.
- The functions of the library written in Alchem are not shown, and a
  failure inside one is named where the program called it
  (`alchem-sets-streams.md`).
- An `if`, `case`, `cond` or `with` used as a value inside an expression is a
  closure in the pinned compiler, and is shown as one: the statement being
  run inside it, then the line the form itself stands on, which the rest of
  that statement is then shown on too (a call the form is an argument of, or
  is piped into, stays on the statement's line). One that is the whole
  statement is not.
- A `for` is a closure, each of its generators another and its body one
  more, on lines of the pinned compiler's generated code
  (`alchem-comprehensions.md`).
- At most 63 calls are shown, innermost first. A call that went too deep is
  not shown itself, and 61 of the calls around it are.
- A reference `&name/arity` adds no line of its own.

Deep traces of the pinned runtime depend on what its Go compiler inlined; the
counts above are what it shows for plain recursion.

## File names

The compiler reads one source and opens no files. A bundle made by
`alchem-bundle` starts with the manifest described in `alchem-modules.md`,
from which positions become files and lines. Source given directly is named
`<stdin>`.

## How it works

Every frame holds, below its sixteen slots, the position of the statement it
is running (RBP-136) and its closure records (RBP-144): 0 for a function, 1
for a `fn`, or the address of a record pushed on the stack by an `if` or
`case` used as a value, holding the outer chain and the statement around it.
Each statement starts by storing its position; R15 counts active calls.

The routine is `spec/trace-x86_64.s`, kept as checked byte literals in
`native-trace-data.alc` and emitted once per program as an extra function-
table entry (`native-trace.alc`), followed by its tables: the position of
every newline, the files, one name per function-table slot, and the position
of every byte that continues a character. It walks the frames by their saved
RBP and names each from its return address. A failing place passes the
position and the reason: its number in the routine's table of messages, or
from 4096 up the address of a string holding the message. A frame's word is
64 bits: the position is its low 22 bits (a source is below 4 MiB) and the
bits above them count lines past that position's own.

A failure inside a `try` goes to its handler instead of ending the program
(`alchem-try.md`): the routine first looks at the handler word at R14-16, and
a trace may then hold the calls of a failure that is being handled, between
the handler and the frame of its `try`. A throw that nothing catches is
reason 9, `uncaught throw`, shown without calls. The reasons by number are
strings, which a rescue arm takes as the message.

A program that was rewritten before it was compiled (macros, protocols,
HTML templates: `alchem-macros.md`) names places in the rewritten text. Its
tables are those of the program as written, and a fifth table, the moved
records, turns a position back before `tr_place` reads it: sixteen bytes per
run of the rewritten text, where the run starts there, the place it stands
for in the program as written, a place whose file is named instead (all
ones for none) and a number of columns. The place is the run's first byte
and the rest follow it; with bit 31 it is the one place the whole run
stands for (a template's own text stands at the macro's call); with bit 30
it is an anchor, and the run is shown on the anchor's line at its column
plus the fourth word and, without bit 31, plus the offset into the run
(the code of a value in an HTML template, `alchem-templates.md`). The words
before the tables number ten: the fifth pair is the offset and count of the
moved records, 0 for a program compiled as it was written.

The compiler itself is not traced: a program with a `native_compile` entry
stores no positions and carries no tables.

`harness/traces.py` checks ten runs across two bundled files against what the
pinned compiler prints for the same files.
