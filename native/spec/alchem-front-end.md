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
SHA-256 of what the pinned lexer, parser and formatter give as JSON
(`scripts/pinned-lexer`, `scripts/pinned-parser`, `scripts/pinned-format`).
`scripts/lexer-dump.alc`, `scripts/parser-dump.alc` and
`scripts/format-dump.alc`, built by `alchem`, must give the same bytes for
every text: 1,541 of the texts are refused, each with the pinned message at
the pinned place. The cases also hold what the pinned command's `check`
says of each text as a file of its own; `alchem check` must say the same,
or, where the front end does not reach the reason, the native compiler's
or bundler's own message (`E_COMPILE`, `E_BUNDLE`). It says the same for
1,890 of the 2,005 texts the pinned compiler refuses; the gate holds that
count as the least it may give (`EXPLAINED`). `scripts/generate-front-end-cases.py` makes
the file; `scripts/compare-lexer.py` compares the lexers on any files.

## Not as the pinned front end

- A letter, a digit, an upper case letter and a space beyond ASCII are told
  apart by ranges, not by Unicode's tables.
- A float literal of more than 15 significant digits is written with the
  fewest digits that read as the same float, found by reading candidates
  back; the pinned compiler finds them from the float's bits.
