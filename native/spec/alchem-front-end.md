# The front end

The native compiler compiles from the source bytes as it reads them and
has no syntax tree: a program it refuses gets one message (issue #100).
The front end is a second reading of a source file, in Alchem, that gives
what the pinned compiler's front end gives: its lexer's tokens and
comments, its parser's tree, and its messages, each with its line and
column, and its formatter. `alchem`'s messages for a refused program
(#100) and `alchem fmt` (#91) are built on it.

## The lexer: `tools/alchem-lexer.alc`

`AlchemLexer.scan(text)` gives the tokens (kind, text, line, column) and
the comments (text, line, column) the pinned lexer gives
(`compiler/lexer`), or its message, `line:column: message`.

## The parser: `tools/alchem-parse.alc`

`AlchemParse.parse(text)` gives the tree the pinned compiler's
`syntax.ParseSyntax` gives, the parse it makes for its formatter, or its
message. The tree is `AlchemJson` values (`tools/alchem-json.alc`) with the
fields of the pinned `ast` types in their order, so that the tree written
as JSON is the pinned one byte for byte, `null` where Go writes a nil
slice. Type names are checked as the pinned `ast.ValidType` checks them
(`tools/alchem-types.alc`, the module `AlchemTypeNames`: a module named
`AlchemTypes` is refused, issue #102).

The parser is the pinned one function for function. The pinned parser
changes its state in place and puts parts of it back when a function
returns; here the state (`P`: the tokens left, the comments left, the
settings of arms, captures and `try`) is given to each function and given
back with what it read, and a look ahead (`assignment_start?`,
`arm_start?`) is a state thrown away.

## The formatter: `tools/alchem-format.alc`

`AlchemFormat.format(text)` gives the text the pinned compiler's
`compiler.Format` gives, or the parser's message: the pinned formatter
function for function, on the tree `AlchemParse.parse` gives. A string is
quoted as Go's `strconv.Quote` quotes it (`AlchemLexer.go_quote`): a rune
`strconv.IsPrint` says is not printable is an escape, by the ranges of
`tools/alchem-print-data.alc`, which `scripts/pinned-print` writes from the
pinned Go toolchain's tables. A float is written as `ast.FormatFloat`
writes it, from the shortest digits the tree holds.

## What is said of a refused program: `tools/alchem-check.alc`

`AlchemCheck.load(entry, directory)` reads a program as the pinned
compiler's `loadProjectAs` does: the entry (`main.alc` of a directory), then
the files it imports in sorted order, depth first, each read once, an
import cycle, a missing file, a duplicate or reserved module name and an
import path that is not relative said as the pinned compiler says them,
each with the place of the import that led to it. Each file is parsed as
`ParseModule` parses it (`AlchemParse.parse_module`, without the comments
the formatter keeps) and checked as `ParseModule` then checks it
(`AlchemLower.problem`, `tools/alchem-lower.alc`: `resolveConstants`, and
the parts of `lower` that refuse, `separateArities` and `mergeClauses`). A
package's file (`host/owner/repo@v1.2.3/...`) is not followed.

Once every file is read, `AlchemCheck.merged` checks the program as one, as
`loadProjectAs` then does: a protocol declared twice, `main` in an imported
module, a call of a module the file does not import (after `Qualify`
names a module's own types under it) or of another module's private
function, and the arity of a call of another module's function
(`ResolveArities`). A program with macros, a `use`, a `require` or a
`doctest` is not followed past its files, since the steps those take
(`ExpandMacros`, `documented`) are not here. Paths are kept with `/` and
shown with the system's separators, as Go's `filepath` shows them.

## The module as the checker reads it: `tools/alchem-lower.alc`

`AlchemLower.lower_module(text)` gives the tree the pinned compiler's
`syntax.ParseModule` gives, or its message: the module parse (no comments,
no heredoc text, no sigil delimiter, as the pinned parser keeps those only
for the formatter), each constant replaced by its value, and `lower`:
`separateArities` naming each arity of an overloaded name and its calls,
`mergeClauses` making the clauses of a function one function of a `case`
on `arg$1`, `arg$2` … form by form, the rewrites of `unless`, receives,
`fn` clauses, `cond`, `with`, `check all` and bitwise operators, and
`Qualify` naming a module's own types and variants under it. A lowered
receive shows its pattern as the formatter writes it. `Statements`, which
shares its array with `main`'s body in Go and so holds what Go's memory
layout leaves there, and the fields kept for the literal-only parser API
are left out; the checker reads `Functions`.

## The program as the loader gives it: `AlchemCheck.program`

`AlchemCheck.program(entry, directory, analyzing)` gives the program the
pinned compiler's loader gives its checker, as JSON: each module lowered
(`lower_module`), its functions named in the program (`Module.name`, or
`main`) with their module, local name and file, the calls of each body
named as the loader names them (`Kernel.name` the builtin, a function of the
module its name in the program), the calls of another module's function of
more than one arity named by the one they fit (`ResolveArities`), and the
types, protocols and modules the program takes over. Before that, the one
check `ExpandMacros` makes of a program without macros: only a macro takes
a `do ... end` block. A program with macros, a `use`, a `require` or a
`doctest` is not followed to its end. `scripts/loaded-dump.alc` writes it,
and `scripts/pinned-loaded.py` builds the pinned loader to write the same:
the pinned module copied from the module cache with only an exported entry
to the loader added and a test before the checker, so that it stops where
the checker would begin.

## The checker: `tools/alchem-analyze.alc`

`AlchemAnalyze.problem` follows the pinned compiler's checker
(`syntax.Analyze`) on the program as the loader leaves it: each function as
`mergeClauses` makes it (one for each form, named `name`, `name/2` or
`name#2`, with the form's return type), named `Module.name` or `main`. It
is followed in pieces, each finding what the pinned one finds in its order;
where it reaches a check that is not here yet it finds nothing, so that
what it finds is always the pinned compiler's first problem. Now: the pass
over every function before any body (a function defined twice, a name no
function may have, `main`'s form, a return type that is not a type, such
as none at all) and a module with both tests and `main`. A program with an
`extern` function is refused before it (below).

The bodies of functions are walked by `tools/alchem-typing.alc`
(`AlchemTyping`), which follows `syntax.Analyze` after that pass: the
program's types declared and checked, a test that takes a context with no
setup block to give one, and then each function in order, its type
variables, return type and parameters, and its body statement by
statement and expression by expression as `checker.block` and
`checker.expr` type them, with the patterns, the exhaustiveness of a case,
calls of library functions (with their overloads and constraints), the
oldest builtins, the program's own functions, constructors, structs and
functions written in place. The tables the pinned checker types library
calls with (`syntax.Libraries`, `Overloads`, `SimpleBuiltins`,
`BuiltinTypes`) are `tools/alchem-check-data.alc`, which
`scripts/generate-check-data.py` writes from the pinned module
(`scripts/pinned-checkdata`). The calls of `Process`, `Server` and
`Supervisor`, `for` (with `uniq:`, `into:` and `reduce:`), a `with` clause
that does not match, `put_elem`, a function of several forms called, the
constraints of library functions that read JSON or send between nodes,
`try` with its `rescue`, `catch`, `else` and `after`, a builtin struct's
defaults, a `with` and its `else`, and the sigils are followed too: `~s`,
`~w`, `~c`, `~h`, those the program defines, `~r` (whose pattern the
native `Regex` must compile) and the calendar's `~D`, `~T`, `~N` and `~U`,
whose text is read as Go's `time.Parse` reads the layouts of `ParseClock`.

Before the bodies come the program's protocols (`checker.protocols`: each
`defimpl` against what its protocol declares, and each implementation
whole), and a call through a protocol is the call of the function that
implements it for the type of its first argument (`dispatch`). In a test
file the setup blocks are typed first (`checker.contexts`): `setup_all`,
then the setup blocks from the outermost `describe` inwards, each given
the context in effect where it stands and giving the type of its last
expression to the setup blocks and tests beneath it.

The pinned checker comes back to a branch whose type another settles
(`checker.undetermined`): an `if`, a `case` arm or the body of a `try`
that fails to infer a type while the type of its context is still open,
and a function written in place whose every path raises. It asks the
context after the failure, and a constructor that shows only part of its
type (`none`, `ok(1)`) leaves that part as a hint for the other branches
of the value it ends a branch of (`recordHint`). Here a failure carries
out of each block whether the block's type was open then, its value type
and the hint (`mark`, `remark`), and the branch is walked again from
there once the others have settled it. A `catch` arm that names no type
takes the type of the values its `try` throws (`thrownTypes`), which the
walk keeps for each `throw` it types; a failure carries those typed
before it out too, since the pinned checker reads them from the tree
after a body that failed.

The walk stops, and says nothing, at what it does not follow: a program
that defines a retiring library module of its own, a `catch` arm that names no type in a `try` whose body is
come back to with a `throw` among the arguments of a call tried against
several forms, and a program where several implementations of a protocol
each lack a function (the pinned checker names one of them, in no
order). `scripts/typing-dump.alc` prints where the walk ends for each
file it is given.

## The check

`harness/front_end.py` (the gate `front_end`) holds 3,004 texts: the
repository's source files under 60 KB as they were when the file was
made; five broken copies of each (a line dropped, the text cut short, a
sign put in, two lines swapped, characters taken out); three copies
written otherwise than the formatter writes them (indentation taken out,
or added with spaces at the ends of lines and none after commas, or blank
lines moved and operators spaced); and up to four copies with a comment
put before one line, of those the pinned formatter takes, where comments
are kept in lists and between clauses (#40, #42). For each it keeps the
SHA-256 of what the pinned lexer, parser, formatter and module parse give
as JSON (`scripts/pinned-lexer`, `scripts/pinned-parser`,
`scripts/pinned-format`, `scripts/pinned-module`). `scripts/lexer-dump.alc`,
`scripts/parser-dump.alc`, `scripts/format-dump.alc` and
`scripts/module-dump.alc`, built by `alchem`, must give the same bytes for
every text: 1,541 of the texts are refused, each with the pinned message at
the pinned place. Each text loaded as a program of its own gives the
program the pinned loader gives, byte for byte, for all but the 8 the
loader is not followed to its end for. The cases also hold what the pinned command's `check`
says of each text as a file of its own; `alchem check` must say the same,
or, where the front end does not reach the reason, the native compiler's
or bundler's own message (`E_COMPILE`, `E_BUNDLE`). It says the same for
all 2,005 texts the pinned compiler refuses; the gate holds that count as
the least it may give (`EXPLAINED`). `scripts/generate-front-end-cases.py` makes
the file; `scripts/compare-lexer.py` compares the lexers on any files.

`harness/front-end-probes.json` holds 428 programs written for what the
walk follows that the repository's files reach seldom: `try` and its
arms, the calendar sigils in the forms `time.Parse` takes and refuses,
the other sigils, branches that settle each other's types and the hints
between them, functions that only raise, a builtin struct's defaults,
`with` and its `else`, setup blocks and their contexts, and protocols;
most with a mistake after the construct, which only following the
construct reaches, and without it. `scripts/generate-front-end-probes.py`
writes them with what the pinned `check` says of each. `alchem check`
must say the same or give its own message; it says the same for 427,
which the gate holds as the least (`PROBED`). The other is
`~N[2026-01-05  13:04:05]`, with two spaces: the pinned compiler takes
it because Go's `time.Parse` takes any run of spaces for one, and the
native compiler, as Elixir, takes exactly one space or a `T`.

## Not as the pinned front end

- `extern` is out of the language (it bound a name to a Go function or
  type, and a program is not built with Go). The pinned compiler still
  takes it; of a program that has one `check`, `build`, `run` and `test`
  say so at the first of them, once the files are read and their syntax
  is right, with the library function to use where there is one
  (`AlchemCheck.extern_problem`; `docs/interop.md` has the list):
  `main.alc:2:10: extern is no longer in the language: sqrt was bound to
  the Go function "math.Sqrt", and a program is not built with Go; use
  Float.pow(value, 0.5)`. The `front_end` gate takes that for a text
  with an `extern`, whatever the pinned compiler says of it.
- A letter, a digit, an upper case letter and a space beyond ASCII are told
  apart by ranges, not by Unicode's tables.
- A float literal of more than 15 significant digits is written with the
  fewest digits that read as the same float, found by reading candidates
  back; the pinned compiler finds them from the float's bits.
