# Regular expressions

`~r/pattern/flags`, `text =~ regex`, the `Regex` module and the `String`
functions that take a regex, as the pinned compiler has them: it compiles a
pattern with Go's `regexp` package (RE2 syntax, the first match a
backtracking search would find). `harness/regex.py` holds programs with the
pinned compiler's output: programs written out and 468 generated patterns,
each tried on a subject through every function; the same generators were run
against Go's `regexp` on some 5,000 more patterns while this was written.

| Form | Value |
| --- | --- |
| `~r/a+b/`, any sigil delimiter | a `regex`; an invalid pattern is rejected when the program is compiled |
| modifiers `i m s U` | the pattern after `(?imsU)`, in the order written; `u` changes nothing; `x` takes white space and `#` comments out of the text (outside classes and escapes); any other letter is rejected |
| `~r/^#{name}$/i` | `Regex.compile!` of the flags and the string, as it runs (`x` then changes nothing, as upstream) |
| `text =~ regex` | `String.match?(text, regex)`; binds like the comparisons |
| `Regex.compile(string)` | `result[regex, string]`, the error being Go's text (`error parsing regexp: missing closing ): \`a(\``) |
| `Regex.compile!(string)` | the regex, or the program ends with that text |
| `Regex.match?`, `run`, `scan`, `split`, `source`, `named_captures` | as upstream: `run` and `scan` give the whole match and then each group, `""` for a group that took no part |
| `Regex.replace(regex, text, replacement)` | the replacement a string (`\1` and Go's `$1`, `${1}`, `$name`, `$$`), a function of the match, or one declared to take `list[string]`, of the match and its groups |
| `String.match?(text, regex)`, `String.split(text, regex)`, `String.split(text, regex, [parts: n])`, `[trim: true]`, `String.replace(text, regex, replacement)` | the `Regex` functions; `split/2` and `replace/3` take a regex only written as a `~r`, a name or `Regex.compile!(...)` (in parentheses or not), as upstream |

The type is written `regex`. A regex is not compared, not a map key, not
put into a string; `inspect` writes `#Regexp<>`.

## How it is built

- **`implementations/alchem/native-regex.alc`** is Go's `regexp/syntax`
  in the compiler's dialect: `rx_compile` parses a pattern (the same
  errors with the same text, found in the same order), simplifies it and
  compiles it to a program. The compiler runs it on a `~r` without values
  and puts the program in the executable's code, where the value points:
  such a literal costs nothing as the program runs. `library/Regex.alc`
  takes the same text (`#include`, `scripts/generate-prelude.py`, with its
  names shortened) for `Regex.compile`.
- A class is its ranges in order, as Go's `cleanClass` leaves them: under
  `(?i)` with all its characters fold to (`unicode.SimpleFold`), `\p{...}`
  from the tables, a negation as what is left out. The tables are
  `spec/regex-tables.json` (`scripts/generate-regex-tables.go`, from the
  pinned Go's Unicode 17), packed into `native-regex-data.alc`
  (`scripts/generate-regex-data.py`, 10 KB): the names of `\p{...}` (the
  general categories, their unions and aliases, the scripts, `Any`,
  `ASCII`, `Assigned`, `LC`; any case, with or without `_ -` and spaces),
  the fold pairs and groups, every code point's category and the scripts.
- **The program** is a string of instructions: a character, one of a pair
  of ASCII letters, a class (ranges, found by halving), any character,
  split (two orders), jump, save a position, the six assertions, match,
  and `x*` for one instruction `x` (greedy and lazy), which runs without
  nesting a call per character. Jumps are relative.
- **`library/Regex.alc`** runs it by going down into it, a call per
  instruction; a call that fails is a path given up, so the match found is
  the one Go finds. A call returns two of the match's positions in one
  number, and the others are read by running the same path again with
  other positions asked for, so matching allocates nothing: `match?` on a
  literal `~r` uses no memory at all.
- **Loops that match the empty string.** Go's matchers drop a path that
  comes back to an instruction without having moved, which decides what
  `(a*)*`, `(a?)+` or `(a|b*)*` capture. The compiler puts a mark
  (instruction 18) wherever two paths meet inside a loop whose body can be
  empty, and the matcher carries the marks passed since the last character
  as bits of a number (a list from the 63rd on): a path that meets a set
  mark ends there.
- **The compiler** (`native-sigils.alc`): type 29 (`regex`), the `~r` sigil,
  `=~` (`sg_match`; the two characters are one token), `inspect` (node 29
  of `spec/integer-parse-x86_64.s`), and four names only the library may
  call (`sg_rx`, inside `Alchem*` modules alone, as `Sys.*` and the `__`
  names are): `rx_ab(value)`, a string or regex as its bytes;
  `rx_as(bytes)` and `rx_ar(bytes)`, bytes as a string and as a regex (the
  three share one layout, so they cost no code); `rx_tb()`, the tables.
  The library's `bytes` are the byte lists the compiler itself is written
  with, read with `Enum.at`.
- What matches is appended to every program that holds a regex (a `~r`,
  the word `regex` or `Regex`), and the forms of `String` that take one
  only to such a program; the component that compiles one only to
  programs that call `Regex.compile`, `Regex.compile!` or write a `~r`
  with values. A failure inside the library is traced at the program's
  call, a `~r` with values and `=~` included (`nh_placed`).

## Differences from the pinned compiler that remain

- **Time.** A backtracking search takes time exponential in the text for
  a pattern like `(a|a)*b`, where Go's takes time in proportion to it:
  Go remembers the (instruction, position) pairs it has tried, and a
  program here has no memory it can change to remember them in. Ordinary
  patterns are not affected.
- **Depth.** The matcher goes a call down per instruction. Those are no
  calls of the program (the library is entered without counting,
  `alchem-tail-calls.md`), so the 100,000 active calls do not hold it, but
  the stack does: about 230 bytes for each turn of a loop, so `(?:ab)*c`
  matches 8 MB of `ab` and a text past 9 MB exhausts the 1 GiB stack
  (exit 70). `x*`, `x+` and their lazy forms for a single character, class
  or `.` (`\w+`, `.*`, `[^"]*`) are not nested, nor is the search for
  where a match starts.
- **Memory.** A program gives no memory back
  (`alchem-tail-calls.md`). Matching uses none, but results do:
  300 to 500 bytes per match of `scan`, `split` and `replace` (a list
  grows by being copied); 16,000 matches of a `scan`, which did not fit
  the 4 MiB a program had, take 7 MB. `Regex.compile` as the program runs takes
  1 to 3 KB per character of the pattern, 220 KB for `\pL`, and over 1 MiB
  for `(?i)` with a large Unicode class; a `~r` without values takes
  nothing.
- **Limits of a pattern.** Go refuses a tree more than 1000 high and a
  program of more than 3,355,443 instructions, but looks at the size only
  once the nodes it has made times the repeat counts it has seen pass that
  number; here the size is always looked at. A pattern of some thousand
  characters inside `{1000}` that Go still compiles is refused. Go's limit
  of 33 million class ranges in one pattern is not kept (no pattern that
  fits a program reaches it). A `~r` whose program would pass 8 MB is
  rejected.
- A name of `\p{...}` is known by a 32-bit hash of its canonical form
  (no two of the 257 names share one): one in four billion misspelt
  names would be taken for a table.
- Go's parser also factors common prefixes of alternatives and merges
  single characters of an alternation into a class; this compiles each
  branch as written. The matches are the same (the generated patterns
  include alternations inside loops that match the empty string).
- Every compile error is `E_COMPILE`.
