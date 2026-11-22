# The front end

The native compiler compiles from the source bytes as it reads them and
has no syntax tree: a program it refuses gets one message (issue #100).
The front end is a second reading of a source file, in Alchem, that gives
what the pinned compiler's front end gives: its lexer's tokens and
comments, its parser's tree, and its messages, each with its line and
column. `alchem`'s messages for a refused program (#100) and `alchem fmt`
(#91) are built on it.

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

## The check

`harness/front_end.py` (the gate `front_end`) holds 1,590 texts: the
repository's source files under 60 KB as they were when the file was
made, and five broken copies of each (a line dropped, the text cut short,
a sign put in, two lines swapped, characters taken out). For each it keeps
the SHA-256 of what the pinned lexer and the pinned parser give as JSON
(`scripts/pinned-lexer`, `scripts/pinned-parser`). `scripts/lexer-dump.alc`
and `scripts/parser-dump.alc`, built by `alchem`, must give the same bytes
for every text: 1,196 of the texts are refused, each with the pinned
message at the pinned place. `scripts/generate-front-end-cases.py` makes
the file; `scripts/compare-lexer.py` compares the lexers on any files.

## Not as the pinned front end

- A letter, a digit, an upper case letter and a space beyond ASCII are told
  apart by ranges, not by Unicode's tables.
- A float literal of more than 15 significant digits is written with the
  fewest digits that read as the same float, found by reading candidates
  back; the pinned compiler finds them from the float's bits.
