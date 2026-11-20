# with and for

Both forms follow the pinned compiler; `harness/comprehensions.py` holds the
programs with what it prints for each, failures and traces included, and the
programs it rejects. The code is `implementations/alchem/native-comprehensions.alc`.

## with

`with pattern <- expression, ... do body else pattern -> body ... end` is the
pinned compiler's nest of cases: each clause's value is matched against its
pattern and the next clause follows; later clauses and the body see the names
bound so far. A pattern that matches every value by its form (a name, `_`,
`%{}`, a tuple or struct of such) only binds.

A value that does not match its clause ends the `with`:

- **With `else`** it is matched against the else arms. The clauses may be of
  different types, so the arms are compiled once for each clause that can
  fail: an arm whose pattern does not fit that clause's type is passed over,
  and so is every arm after the clause's own pattern and the arms before it
  match every value. A clause no arm fits is rejected, as is an arm that an
  earlier one makes unreachable. The arms need not match every value: one
  that none matches ends the program with `no case branch matched`, naming
  the `with`.
- **Without `else`** the value is the result when it has the type of the
  body. An `error(reason)` passes to another `result` with the same reason
  type (a value that is `ok(...)` and still did not match ends the program
  with `no with clause matched`, naming the clause's expression), and an
  option that does not match gives `none` of another option. Any other type
  is rejected when the `with` is a value.

A `with` is a statement or a value, like `case`. As a statement the value
that does not match is dropped and nothing is asked of its type. As a value
inside an expression it is a closure in a trace, as `if` and `case` are, and
the failure `no with clause matched` runs in one more.

The body's type is found bottom up, so where the pinned compiler takes the
type of the whole `with` from its context (`ok(a + b)` says nothing of the
reason type), the value is marked as needing a type: an annotated binding, a
parameter or a function result gives it, and a binding without annotation is
rejected as upstream rejects it.

## for

`for pattern <- enumerable, filter, ... do body end`, the one-line form
`for ..., do: expression` and its form in parentheses `for(..., do: expression)`.

- A generator's enumerable is a list, a range (the list of its integers) or a
  map (its entries as `{key, value}` in key order). Several generators nest,
  the later ones seeing the earlier bindings and being evaluated again for
  each element around them. An element its pattern does not match is passed
  over. A filter is a boolean expression; the first item is a generator.
- The value is the list of the body's values. A body that ends in output,
  `assert` or a call that gives nothing gives `{}` for each element.
- One option may stand among the items. `into: collectable` appends to a
  list, adds `{key, value}` tuples to a map (a later one replaces an earlier
  one of its key) or appends strings to a string; an empty `[]` or `%{}`
  takes its type from the values. `uniq: true` drops a value equal to an
  earlier one (`uniq: false` does nothing). `reduce: initial` takes a block
  of `accumulator -> body` arms, a case over the accumulator that must match
  every value and whose value is the next accumulator; the last one is the
  result. An initial value of open type, such as an empty `%{}` or `[]`,
  takes its type from the annotation of the binding the `for` is the value
  of; otherwise from what the arms give, or from the result type of the
  enclosing function, and the value then needs a context that gives a type
  (a parameter, a function result), so a binding without annotation is
  rejected as upstream rejects it.
- Where its value is dropped a `for` is run for its effects: its body need
  not end in a value and no list is made. That is a `for` followed by
  another statement, one that ends `main`, and one
  that ends the body of such a `for` or a block of an `if`, `unless`,
  `case`, `cond` or `with` statement whose own value is dropped. A `for`
  that ends any other block is that block's value when its body has one.

### How it is compiled

A `for` is a loop in the enclosing function's frame, so its body uses that
function's bindings directly. Each generator keeps its list and its index in
two frame slots. The body's values are pushed on the machine stack and
counted; when the loops are over one list of that length is allocated and
filled from the stack, so a `for` allocates its result once whatever its
generators and filters pass. `uniq:` then copies the list once, comparing
with the code `==` uses; `into:` a map builds the entries of the target and
the new ones into one map; `reduce:` keeps the accumulator in a slot and
makes no list.

`[first, second | rest]` as an expression (the listed elements before those
of another list) was missing and is compiled here too, since a `reduce:` arm
is where it is most often written.

### Traces

The pinned compiler makes a `for` a function of its own, each generator a
function called with every element and the body one more, and a trace shows
them as closures standing on lines of the generated code: the `for` two
lines after the line its statement stood on, each generator two lines and
one per name its pattern binds after the one before, a filter one line on,
the generator around the body on the line after the body's last statement,
and the function itself, while the `for` runs and for the rest of that
statement, two lines for each generator and two more after that. Those lines
need not exist in the source. The native program keeps a record for each of
these closures in frame slots (the stack holds the body's values) and a
frame's line may be a position with a count of lines past it, above the
position's 22 bits in the frame's 64-bit word (`spec/trace-x86_64.s`).

The line after the body follows the code the pinned compiler makes of the
body's last statement: the next line; for an `if` the line after its last
branch and one more; for a `cond` a line for each arm; for a `case` or
`with` the line after its first; for a `for` the line its function stands on
afterwards, and one more.

An `if`, `case`, `cond` or `with` used as a value is likewise shown where
the form itself stands, not where its statement starts, and so is the rest
of that statement.

## Differences that remain

- **Sets.** `into: MapSet.new()` and a generator over a set or a stream are
  rejected: the native profile has no set or stream type to iterate or
  build.
- **Arms that are never compiled.** The else arms of a `with` are compiled
  against the type of each clause that can fail; arms no clause reaches (all
  of them, when every clause only binds) are checked for their form only: a
  pattern, an optional guard, an arrow and a body with balanced brackets and
  blocks. The compiler types as it parses and has no parser that reads a
  body without the types of its bindings, so a syntax error inside such a
  body is not reported.
- **The type of a `with` without `else` whose body's type is open.** The
  pinned compiler decides from the expected type whether a value that does
  not match passes as it is or as the error of another result. Here the body
  is typed first: when the clause's type fits the body's open type the value
  passes as it is, even where the context then turns out to want another
  result type (which is rejected here and accepted upstream). It needs a
  body that is only `error(...)` or `none` together with a clause whose own
  ok type differs from what the context wants.
- **A call later in the statement of a multi-line form.** A frame holds one
  line. When a `for`, or an `if`/`case`/`with` value, is an argument of a
  call or is piped into one, the frame goes back to the statement's line
  once it is over, which is where the pinned compiler shows that call; a
  second call later in the same statement is then shown there too, where the
  pinned compiler shows it on the line the form left. Showing both would
  need every call to remember the line of its own opening parenthesis, which
  the call code (`nc_call_function`) does not do.
- **The line after a body whose last statement spans lines.** For a body
  that ends in an expression holding a `fn`, or an `if`/`case` value, that
  starts on a later line than the statement, the pinned compiler's generated
  code ends on that later line; here the statement's own line is used. Only
  the line of the generator's closure in a trace differs.
