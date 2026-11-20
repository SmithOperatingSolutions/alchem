# Failures of the library's machine code, zero values and coverage

What the programs of the pinned tree needed beyond the earlier profiles.
`harness/failures.py` holds the programs with what the pinned compiler
prints for each; the code is `implementations/alchem/native-failures.alc`
(`zf_`), with small calls of it from the files named below.

## Library functions with machine code of their own fail as the others do

A routine of `spec/library-x86_64.s`, `spec/collections-x86_64.s` or
`spec/failures-x86_64.s` that cannot go on used to leave the program with
status 73 (or 70). It now ends in twelve bytes with a status that names its
message, `mov edi,status; mov eax,60; syscall`, and where the compiler puts
such a routine into a traced program (`zf_wrap`, called where the `String`,
`Integer`, `Enum` and `IO` calls of the compiler's own are made) each of
these exits becomes a jump to code after the routine that fails at the call,
with the pinned runtime's message, through the trace routine: a `try`
rescues it, `assert_raise` sees it, and an uncaught one prints the place
and the calls. A compiler entry (no trace routine) keeps the exits.

The call's code holds its arguments' code before the routine, and that can
hold data: a byte literal, or the bytes a program writes as machine code
(the compiler's own data is such code). Twelve such bytes that read as an
exit are data, not an exit: data in the code stands behind a jump over it
that spells its length twice (`nc_literal_emit`, `nc_text_emit`,
`sg_static`), and an exit found inside it is passed over. Before this,
`Enum.concat(x, b[1,191,87,0,0,0,184,60,0,0,0,15,5,2])` gave
`0,1,233,91,0,0,0,144,...`: the literal itself was rewritten.

| Status | Message | Raised by |
| --- | --- | --- |
| 80 | `slice needs a nonnegative amount` | `Enum.slice(list, start, count)` |
| 81 | `duplicate needs a nonnegative count and a result under 1 GiB` | `String.duplicate` |
| 82 | `base must be between 2 and 36` | `Integer.to_string/2`, `Integer.parse/2`, `String.to_integer/2` |
| 83 | `base must be at least 2` | `Integer.digits/2`, `Integer.undigits/2` |
| 84 | `digit out of range for the base` | `Integer.undigits` |
| 85 | `integer overflow` | `Integer.undigits` |
| 86 | `separator must not be empty` | `String.split/2` |
| 87 | `slice bounds must be nonnegative` | `String.slice/3` |
| 88 | `input line exceeds 1048576 bytes` | `IO.read_line` |
| 89 | `input is not valid UTF-8` | `IO.read_line`, `IO.read_all` |
| 90 | `cannot read standard input` | `IO.read_all` |
| 91 | the string RSI points at | `String.to_integer` (`"zz" is not an integer`) |
| 96 | `panic: strings: Repeat output length overflow` | `String.duplicate` whose length leaves 64 bits |
| 97 | the string RSI points at, as a panic | `String.slice` of plain bytes whose `start+count` overflows |
| 98 | `panic: strings: negative Repeat count` | `String.pad_leading`, `pad_trailing`: a width whose difference from the length wraps |
| 99 | `panic: runtime error: makeslice: len out of range` | the same, for a fill past 2^48 bytes |

`String.to_integer` calls the parse runtime as `Integer.parse` does and
fails with the error it gives; the base is checked before the call.

Statuses 96 to 99 are panics of the pinned runtime (Go's own): it writes
`<runtime>: panic: ...` and no calls, and a `rescue` gets `panic: ...` as
the message. The trace routine does the same for position `0x7FFFFFFE`
(`spec/trace-x86_64.s`, twelve instructions at `tr_print`). The library
written in Alchem raises one with `Sys.panic(text)` (`zf_panic_call`):
`binary_part` and `Enum.reverse_slice` when a start and a count add up past
64 bits, with Go's `slice bounds out of range [:N]`.

`IO.read_line` takes a read that fails as the end of input, and both
readers take a closed standard input as an empty one (the pinned runtime
opens `/dev/null` in its place): a directory as standard input gives
`none` from `read_line` and `cannot read standard input` from `read_all`.

Also, as upstream:

- `Kernel.name(...)` fails at `Kernel`, not at the name (`nk_from`), and
  `Kernel.elem`, `Kernel.put_elem`, `Kernel.byte_size`, `Kernel.some` and
  the other names that are no functions of the library are the names alone
  (`nk_else`).
- `&String.to_integer/1`, `&hd/1`, `&div/2` and the other references to
  functions the compiler has code of its own for fail at the `&`, in a
  closure on its line (`nf_library_text` compiles them from a text of its
  own, and now gives the table the place: `nj_from`).
- `String.splitter` with an empty pattern fails where it is called.
- At the ends of the integers the library no longer overflows where the
  pinned runtime does not: `List.delete_at`, `Enum.take_every` and
  `drop_every` with the greatest integer, `Enum.with_index` from an offset
  that wraps around, `binary_part` with the least count.
- A field of a struct or a range after a call of the compiler's own:
  `hd(points).x`, `Enum.at(ranges, 0, 1..1).first`, `elem(pair, 1).step`,
  `(1..3).step` (`zf_fields`, `nk_range_dot`).

## Ranges

- `first..last//step` written where a `stream[integer]` is expected (an
  annotated binding, an argument, a function's result) fails with `range
  step cannot be zero`, at the dots, when the step is 0; as a `Range` a step
  of 0 still means 1 or -1. A range record has a fifth word: where its dots
  stand when a step was written and was 0, else 0 (`nn_range_emit`,
  `nk_range`); the making of the stream reads it (`zf_stepped`).
- `Range.size`, `Range.disjoint?`, `Range.split` and `Range.shift` follow
  the pinned runtime's arithmetic, which wraps around in 64 bits
  (`Range.size(0..9223372036854775807)` is the least integer), and
  `disjoint?` walks the smaller range and compares bounds only past 65536
  integers, as there: it was a membership test per integer over lists and
  did not finish for a million.

## The value beside `false` of a receive that ran out of time: nil

`Process.receive` gives `{false, zero}`, the zero being Go's zero value of
the message type: 0, `false`, an empty string, list or map, a struct or a
tuple of zeros, the range `0..0//0`, and for an option, a result and a sum
type, which are interfaces in the pinned runtime, a nil that is none of
their constructors. The compiler makes the zero where the call stands for a
type that holds a struct, a sum type or a range (`zf_received`, `zf_zero`);
the library makes the others from the type's bytes (`Process._zero`).

| Type | The nil |
| --- | --- |
| a sum type | a value of variant -1 |
| `result[a, b]` | a record of discriminant -1 (1 is `ok`, 0 `error`) and no value |
| `option[a]` | the address 0x400000, the first byte of the image, which no value has (`none` is 0, `some(x)` points at a record) |

Everything that reads one of the three follows the pinned runtime
(`harness/nil_forms.py`: 260 programs read a nil every way a program can):

- **`inspect`** and `IO.inspect` write `nil`, also inside lists, tuples,
  maps and structs (`ins_option`, `ins_result`, `ins_sum` in
  `spec/integer-parse-x86_64.s`).
- **`==` and `!=`**: a nil equals itself and nothing else, also through type
  variables, `in`, `--`, `Enum.uniq`, `Enum.dedup` and the other functions
  that compare (`nq_option`, `nq_result`, `nq_sum`). An option compares the
  two words when either is `none` or the nil, before any value is read.
- **Patterns**: `some(p)` matches a word above 0x400000 (`np_emit_node`),
  `none` the word 0, `ok(p)` and `error(p)` their discriminant, a variant
  its number: the nil matches none of them, and a name or `_` matches it.
  So a `for` passes over it, `pattern = nil` fails with `pattern match
  failed`, and a `with` clause hands it to the else arms, or without else
  gives it on as it is.
- **`case` and clauses that match every value** fail on a nil with `no case
  branch matched`, naming the `case` (the first clause's name for a function
  written as clauses), as a closure where the pinned compiler has one. The
  failure follows the last arm when the type of what is matched may hold a
  nil (an option, a result, a sum type, a struct, a type variable, and
  tuples and lists of them: `zf_nil`, `zf_unmatched`, `zf_clauses`) and no
  arm takes everything. Every `case` over an option or a result now goes
  through the pattern matcher (`np_case`); the two forms that compiled
  directly (`no_case_parts`, `nr_case`), whose second arm was entered
  without a test, are gone.
- **The library** asks of an option a function gave it only whether it is
  `some`, as the pinned runtime's Go does: inside library modules `none`
  matches the nil too (`zf_none`), so `Enum.find_value`, `Enum.chunk_while`,
  `Map.get_and_update` and the `Stream` functions take a nil for `none`,
  and `Enum.find_value` gives `none` when its function gave nothing else.
- **`JSON.encode`** writes `null` for each of the three (`JSON.enc`).
- Sent on to another process, kept in a task or an agent, put in a struct
  or a list, it stays what it is.
- **A pid** that is the zero of its type (a field of the struct or a part
  of the tuple a receive left) is no process: `Process.send`, `receive`,
  `await`, `stop`, `alive`, `id`, `monitor`, `demonitor`, `link`, `unlink`
  and `report` fail with `invalid or foreign PID`, `send_after` with
  `invalid PID`, and `register` gives `false` (`library/Process.alc`); they
  read the zero as an address before.

`none = value` as a statement is a pattern when the value is an option and a
binding of the name `none` otherwise, as upstream has both (`nx_plain`); a
pattern `none` over any type but an option is a name, also among the else
arms of a `with` (`np_word`). A `with` clause whose pattern is made of
names, tuples, structs and `none` is rejected when it has a `none`: the
pinned compiler takes such a pattern for one that matches everything and
then finds its case does not (`zf_bare`). `[head | tail]` with a tail of
open type (`[a | [none]]`, `[[1] | [[]]]`) takes the tail's type from the
elements before the bar (`wc_cons`).

## Calls that are no statements, and calls that give no value

`harness/nil_forms.py` holds 520 more programs, most of which the pinned
compiler rejects.

- **`Kernel.` is followed by a function's name and its `(`**, with no blank
  between (`zf_kernel`): `Kernel.not(x)`, `Kernel.!(x)`, `Kernel.-(1)`,
  `Kernel.x`, `Kernel.[1]`, `Kernel.if x do ... end` and `Kernel. abs(1)`
  are rejected. `Kernel.name(...)` is the builtin whatever the module
  defines; where the name is no builtin a function of the program is not
  reached through it (`nk_else`).
- **`elem(...)` and `put_elem(...)` are no calls**: the pinned compiler makes
  them an index and a tuple, which no statement may be, alone, after
  `Kernel.`, in brackets or at the end of a pipeline, in a function's body
  and in the bodies of `if`, `case`, `for`, `try` and `fn` (`zf_formed`,
  which makes the statement a value that is no call: `nx_value`). A
  **variant of a sum type by its name** (`Shape.dot`, `Shape.circle(1)`,
  `P.Shape.dot`) may be the last statement of a block only.
  `Process.self(n)` as a statement has no type to take and is rejected.
- **A call that gives no value** may only be a statement: `refute`,
  `flunk`, `on_exit`, `assert_raise`, `Agent.update`, `File.rm!`,
  `File.write!`, `Gen.check`, `IO.puts(:stderr, text)`, `Logger.debug`,
  `info`, `warning`, `error`, `log`, `configure` and `metadata(list)`,
  `System.collect_garbage` and `System.put_env` are written in Alchem and
  gave `{}` (`zf_void`, `zf_voided`: in a program their value has no type,
  as that of `Enum.each` and `Stream.run` had none already; the library's
  own calls keep the `{}`).
- **`for ..., do: IO.write(text)`**, the one-line form with a call that
  gives no value, is a body run for its effect as the block form is
  (`wf_line`); `do: IO.puts(text)` and `do: assert(...)` are rejected, as
  upstream rejects them (they are statements, no calls).
- **`Process.self` with another message type than the process has** fails
  without calls, as the pinned runtime raises it without a trace: the place
  is passed with bit 30 set (`Stream.__fail`, `spec/trace-x86_64.s`).

## `System.monotonic_time` and `Time.monotonic`

Both count from the start of the program, as the pinned runtime does: at
the first call the start is worked out from the time the process started
(`/proc/self/stat`, in hundredths of a second) and never put later than the
processor time used.

## Assertions with templates

The text of an assertion shows `~h"..."` (also a heredoc) as
`Markup.template("name", [pieces], [Markup.of(value), ...])`, as the pinned
compiler prints what it analysed (`zf_markup`). A list of two or more items
longer than 98 bytes is written over several lines by the pinned formatter
and the assertion is then shown without its text: the length is now that of
the text as shown, not of its escaped form (`zf_shown`).

## Coverage

A test program (one the rewriting gave a `main`) counts how often each
statement of the modules under test runs and, when `ALCHEM_COVER_FILE`
names a file, writes `file<tab>line<tab>times` for each when its tests are
over, as the pinned runner does under `alchem test --cover`: the same
lines, in the same order, each with the same number.
`harness/test_driver.py` holds the pinned runner's file for nine test
files (clauses, guards, `cond`, `with`, `try`, comprehensions, lambdas,
captures, macros, protocols, processes, assertions, and the pinned tree's
`examples/testing` and `examples/kv`) and compares them line for line;
`alchem` (`tools/alchem.alc`) prints the report from the files
(`alchem-testing-gen.md`).

- The statements counted are those of every module of the program but the
  first (the test file) and the library, outside `test` and `setup` blocks
  (`zf_cover`, at `nx_step`). As the pinned compiler has them: a function
  written as clauses or with patterns as parameters is one more statement
  where it stands; a `cond` is none itself, each arm's test is one on the
  arm's line (an arm that is just `true` has none) and what follows the
  last arm is one where the `cond` stands; an `if`, `unless`, `case` or
  `with` used as a value is one more where it stands; a capture and a
  library function by its arity are one where the `&` stands; a `fn` whose
  parameters are patterns is one more where its parameters stand.
- **`with`** is nested cases in the pinned compiler, each a statement where
  the `with` stands: every clause after the first is counted there when it
  is reached, and so is what a value that does not match its clause meets
  (the else arms, or without else the giving on of the value), before the
  else arms' own statements, which are compiled and counted once per clause
  (`zf_counted` in `wc_clause` and `wc_matched`).
- **`for`**: the expression of the one-line form is a statement; a body run
  for its effects (the `for` is a statement, or its body ends in a call
  without a value) ends in a `{}` of the pinned compiler's own on the line
  of its last statement, which is counted (`zf_unit`); the arms of
  `reduce:` are a statement where the `for` stands, counted each time
  round.
- **`try`**: the body and every arm of a `try` that is a statement end in
  such a `{}` too. The pinned compiler lists the statements of the after
  block first, then those of the catch arms, the rescue arms, the body and
  the else arms; the code has the body, the rescue arms, the catch arms,
  the else arms, the block. A mark before them that never runs (five calls
  of the routine jumped over, whose words hold 4 and 3 in their high four
  bits and how many calls each of the five parts holds: `zf_tried`) lets
  `Testing._cordered` put the list in the pinned order.
- **`assert`** in a module under test is one statement: the statements its
  rewriting makes inside (`case T.__as(...)`, `if not (...)`, `flunk(...)`)
  are not counted (`zf_asserting`; whether a `flunk("assertion failed` is
  the rewriting's own is read from the moved records, `zf_placed`).
- **The modules** are listed in the order the pinned compiler writes their
  code in: every module after those it imports. The bundlers write a bundle
  that way (the entry first, then the others in that order:
  `scripts/bundle-alchem.py`, `tools/alchem-bundle.alc`), and the code
  follows the bundle.
- A counted statement starts with a call of the routine of
  `spec/cover-x86_64.s` (table slot functions+8) and its position in 32
  bits behind the call. Each call has a count of its own (a `with`'s else
  arms are code once per clause, and each copy is listed with its own
  number): the 32-bit word, in 64 MiB mapped shared at the first call and
  kept in word 80 of the library's block of working memory, at four times
  the distance from where the call returns to the routine. The compiler
  finds the calls in the finished code (`zf_points`) and puts after the
  routine where the code starts and, for each call, where it stands and its
  word; `Testing._covered` turns each into its count, its file and its line
  with the trace routine's tables (`Testing._centries`, `Testing._cplace`,
  the rules of `tr_place`) and writes the file with mode 0600.
- Byte 15 of the first table record is 2 in such a program (`zf_covered`).
  `Sys.cover()` gives the library the routine's address, 0 elsewhere.
- No flag is involved: every test program with a module under test counts,
  and writes only when the variable is set.

## Differences that remain

- **`Bitwise.bsl(x, least)` and `bsr(x, least)`**, the count the least
  integer: the pinned runtime ends in a fatal error of Go's own (its two
  shifts call each other without end), with a dump of its goroutines; here
  the program fails with `integer overflow`.
- **The programs of the pinned tree that still differ**: `stdlib.alc` and `text_numbers.alc` use `extern`; of the
  benchmarks only the timings differ, and eight of the suite are stopped
  by the 40 seconds and 4 GB the tree is run under (memory is not given
  back and some library functions are slow: `alchem-tail-calls.md`).
