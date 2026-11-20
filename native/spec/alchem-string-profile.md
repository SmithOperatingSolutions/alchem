# Native string and output profile

The Alchem-written compiler supports a distinct `string` type. Strings share the
immutable length/payload record representation with bytes, but cannot be passed
to byte APIs or implicitly converted. String parameters/returns, bindings,
branches, direct/forward/private/recursive calls and the six-argument ABI use
ordinary type checking. String results use RAX record pointers.

Double-quoted literals have no length cap of their own. Raw non-control bytes
are copied without normalization; valid UTF-8 source therefore preserves its
encoded bytes. The escapes are the pinned language's: `\a`, `\b`, `\f`, `\n`,
`\r`, `\t`, `\v`, `\e` (escape), `\s` (space), `\\`, `\"`, `\#`, three octal
digits up to `\377` and `\xHH`, each one byte, including NUL and invalid UTF-8;
and a Unicode code point as `\uHHHH`, `\UHHHHHHHH` or `\u{H...}` (one to six
digits), written as UTF-8, surrogates and values past U+10FFFF excluded. Raw
control bytes/newlines, unknown or incomplete escapes and unterminated
literals are rejected. Interpolation and heredocs are in
alchem-source-profile.md. Scanning skips complete quoted tokens so
keywords, comments and delimiters inside them do not change program structure.
Decoder traversal is chunked to avoid exhausting the compiler's call-depth bound.

`left <> right` concatenates two strings, evaluates left to right, and returns a
fresh record. It uses the same aligned arena charging as byte concatenation but
no 1 MiB payload cap: like the pinned runtime, a result is limited only by
memory, here the arena (16 GiB reserved lazily; exit71 when it is exhausted). Byte Enum.concat is bounded the same way. It is left associative at addition precedence in this
profile. Empty literals and empty concatenations allocate fresh records too.
`byte_size(string)` returns encoded byte length, not Unicode character count.
`Integer.to_string(integer)` returns a fresh canonical decimal string, including
minimum signed i64. Unsigned division handles its magnitude without signed
negation overflow; exactly align8(length+8) arena bytes are charged. Base overloads
are not supported. `String.length` now counts
grapheme clusters with the exact pinned runtime rules. String.slice, first and
last use the same boundaries. See alchem-grapheme-profile.md for Unicode version
and inherited limitations; byte length is never substituted for grapheme count.
`==` and `!=` compare strings byte for byte (Go string equality); `<`, `<=`, `>`
and `>=` order by unsigned bytes with a proper prefix first (Go string
comparison). Further Go-exact operations:
String.split(s,sep) (strings.Split; an empty separator exits73),
String.replace(s,old,new) (strings.ReplaceAll; an empty old inserts new before
every UTF-8 sequence, invalid bytes singly, and at the end), String.count(s,pat)
(non-overlapping; 0 for an empty pattern), String.valid?(s) (utf8.ValidString),
String.trim(s) (strings.TrimSpace with unicode.IsSpace: ASCII whitespace, U+0085,
U+00A0, U+1680, U+2000-U+200A, U+2028/2029, U+202F, U+205F, U+3000),
String.trim_leading(s)/trim_trailing(s) (TrimLeftFunc/TrimRightFunc) and the bare
contains/starts_with/ends_with names alongside their ? forms. Results are fresh
records; split/replace size their output before writing. harness/string_ops.py
checks290 cases whose Python oracle equals the pinned upstream output.
String.upcase(s)/downcase(s) follow Go strings.ToUpper/ToLower: every rune goes
through the simple unicode.ToUpper/ToLower mapping (spec/case-ranges.json from
Go 1.27.4, Unicode 17.0.0; no multi-character special casing, so "ß" is
unchanged) and each invalid byte becomes U+FFFD. Their runtime
(spec/case-map-x86_64.s, about4.5KB) is the third shared runtime.
String.to_integer(s) / to_integer(s,base) parse like Integer.parse and return the
integer; where the pinned runtime fails the process (not an integer, or a base
outside2..36) the native program exits73. It shares the Integer.parse runtime.
harness/string_case.py checks every mapped rune and range neighbour.
String.reverse(s) reverses grapheme clusters. String.capitalize(s) applies
unicode.ToTitle to the first grapheme and ToLower to the rest.
String.pad_leading/pad_trailing(s,width[,fill]) measure s in graphemes and add
the first width-count runes of the fill repeated (default one space; each invalid
fill byte is one rune written as U+FFFD; an empty fill or a width not above the
count returns s). A fill that cannot fit the arena exits71. The grapheme runtime
is now the fourth shared runtime instead of being inlined at each call, so
String.length/slice/first/last/reverse/capitalize/pad_* may be used any number
of times. Shared runtimes use table slots beyond the program's records and do
not reduce the65535-function limit. harness/string_graphemes.py checks255 cases against the pinned
grapheme oracle; the results equal the pinned upstream output.
No Unicode normalization or implicit numeric conversion
is implied. Those APIs need separate compatibility work and tests.

`IO.puts(string)` and `IO.write(string)` are statements in any function body and
at the start of any if/else branch or case arm, before the body's, branch's or
arm's value; helpers run them in evaluation order, untaken branches do not. It writes all payload bytes to stdout followed by exactly one newline,
including for an empty string. Bound values survive its syscall clobbers. Both
payload and newline retry EINTR; positive short writes advance the cursor; zero
progress or other syscall errors exit 74 without a target diagnostic. OS signal
semantics remain in effect. IO.puts is not an expression. The pinned language
rejects void-returning functions ("returns void, which is not a valid type"), so
effectful helpers return a value; device overloads/gets/inspect are not implemented.
`IO.warn(string)` is a statement in the same places and writes the text and one
newline to standard error; a failed write there is ignored, as the pinned
runtime does, so it never changes the exit status. Main must still end in
System.halt or terminal halt branches. Compiler-entry stdin/stdout is unchanged.

Compiler metadata uses full structural words and separate flags; see
alchem-structural-types.md. A native_compile entry must be a public bytes-to-bytes
function, so a string signature cannot accidentally select compiler IO.

harness/string_library.py checks deterministic compilation and exact output,
UTF-8 text, all 256 hexadecimal byte escapes, typed calls/live values, lexical
rejections, /dev/full/closed output, and injected interrupted/short/zero writes.
The complete suite runs it against all three self-built compiler stages through
the two seeds' byte-equality gate. No assembler participates in native compilation;
puts-x86_64.s and integer-to-string-x86_64.s are auditable instruction references only.

IO.write, String.duplicate and Integer base formatting are specified in
alchem-library-profile.md. General void helpers and IO.gets remain future work.

## String literals

A string or atom written in a program is not made when it is evaluated.
Its length and bytes lie in the program's image behind a jump, in the code
that mentions it, and its value is their address (`nc_text_emit`): a loop
that names "abc" a million times allocates nothing for it, where it copied
the literal into the arena each time. The pieces of an interpolated string
and of a heredoc, `~s` and `~w` texts, the keys of keyword lists and atoms
are placed the same way. The image is mapped read and execute only, so a
write to a literal would end the program; nothing writes to a string it was
given: the string routines and the library build new strings, `Sys.poke`
is used on blocks the library allocated itself, and a string is extended
in place only where it ends at the arena's cursor, which an address in the
image never does. Byte literals `b[...]` and the empty map are made as
before.

The gates that measure charges hold the new figures: every literal in a
measured expression costs 8 bytes and its length rounded up less
(`harness/options.py`, `string_library.py`, `boolean_library.py`,
`collection_memory.py`, `lists.py`), and the programs of
`harness/source_capacity.py` that need an image past 1 MiB and past 16 MiB
have more statements, since each `IO.puts("7")` is 128 bytes of code where
it was about 173.

## String.normalize

`String.normalize(text, form)` with `:nfc`, `:nfd`, `:nfkc` or `:nfkd` is
written in Alchem at the end of `library/String.alc`, generated by
`scripts/generate-normalization.py` from the pinned runtime's own tables
(`normDecompositions` and `normCombining` in `compiler/library.go.txt`,
Unicode 17.0.0), and follows `strNormalize` step by step: text that is
ASCII without a carriage return is returned as it is; each code point is
decomposed (Hangul by arithmetic, the rest by table, fully, with the
compatibility decompositions for the two `k` forms), the marks between
starters are put in the order of their combining classes, and for the two
`c` forms starters take the marks that compose with them. A byte that is
no UTF-8 becomes U+FFFD, as Go ranges over a string. The tables are text
of 64 printable characters in pieces a `case` picks, searched by halves
where they lie: nothing is allocated to read them.
