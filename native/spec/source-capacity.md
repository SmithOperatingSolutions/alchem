# Sixteen-MiB native source input

Native compiler/source-tool entries accept at most 16,776,191 bytes (16 MiB
less 1 KiB and one byte: `nc_limit`), reserving one extra input byte to reject
overflow before calling the compiler: a longer input ends with `E_RUNTIME_INPUT: input exceeds byte limit`
and status 65, and no ELF is written. The reader keeps EINTR/short-read
behavior. `nc_compile` checks the same bound on what it is given, and
`nc_compile_all` on the source with the library functions written in Alchem
appended; a program too close to the limit to hold them is compiled without
them, as before.

The pinned compiler refuses a source file past 1,048,576 bytes (`source
exceeds 1048576 bytes`) but not a program: five files of a megabyte each build
and run. The bundlers and `alchem` refused such a file as it does; they now
read a file as long as a program may be (`alchem-modules.md`), and
the compiler takes what a program of many files adds up to. A single source
given to `alchem-compiler` directly may be larger than a megabyte because the
compiler's own source has to pass through it; this is a deliberate
difference. Issue #19 is to go past 16 MiB with four-byte positions.

## What holds a position

Source positions are unsigned 24-bit fields (`nc_u24`/`nc_cursor`) in parser
packets, signatures, parameter/local names, list spans, string decoder cursors,
scoped bindings and the function table, and a position takes all 24 bits. A
compiled value's flags are the byte after its position: bit 7 is `nw_mark`
(the value's type needed one from its context) and bit 6 `nx_impure`. Until
they had that byte they were bits 23 and 22 of the position, which held the
source to 4 MiB. 16,777,215 stands for no position (`mx_none`), so
the limit leaves 1 KiB below it for the positions just past the end that
scans produce.

Integers that carry more than a position are not stored in three bytes:

- A frame's trace word (RBP-136) is 64 bits: the position in its low 24 bits
  and above them the count of lines past that position's own, which a `for`
  uses (`alchem-traces.md`). It was 32 bits with the position in the low 20,
  then 64 with it in the low 22. A `try` keeps such words in 32 bits, which
  hold 255 lines past a position (`ty_past`, `ty_record`).
  The count is no longer bounded by the word: a value that does not fit a
  sign-extended 32-bit immediate is stored in two halves (`nz_set`, `wf_word`).
- The end of an interpolation hole is searched with the nesting depth above
  bit 24 of the position (`sg_hole_some`).

Whitespace/comment skipping, body scanning and clause scanning take up to
16,777,216 steps, enough for a source that is all short comment lines or all
tokens.

## What holds a code size

A source of 4 MiB compiles to more code than one of 1 MiB did, past what three
bytes hold, so every code length is now 32 bits:

- the length of each function in a bundle (`nc_build`, the shared runtimes of
  `na_shared_bundle` and `ne_shared`, read by `nc_addresses`/`nc_length_sum`).
  The failure-trace tables are one such entry and hold four bytes for every
  newline and every UTF-8 continuation byte of the source: up to 16 MiB.
- the split of a two-part code packet (`wc_both`), the length kept behind the
  left operand of `++`/`--`, and the offset from a closure record back to its
  lambda (`nf_code`, a 32-bit displacement).
- the image size in the ELF header (four bytes; it was three).

Total function code may be 1 GiB (it was 15 MiB, so that an image stayed within
16 MiB). Table addresses are 32-bit and calls go through the table; branches
inside a function are 32-bit relative.

## Memory

The compiler never frees: the arena is the bound. Compiler entries reserve
16 GiB lazily (MAP_NORESERVE; it was 1 GiB), or the largest half of that the
system grants down to 1 GiB, and exit 71 when it is used up. Seed IR V11 accepts
`arena_bytes` up to 17,179,869,184 and the bootstrap asks for that; a budget
past 1 GiB is reserved the same way, with the same halving (`ir-v11.md`).
Ordinary generated programs keep their 4 MiB arena.

Measured peak resident memory, which is the arena charge plus a few MiB:

| Source | Bytes | Compiler | Peak | Time |
| --- | --- | --- | --- | --- |
| The compiler's own source | 851,625 | seed-built A0 | 445 MB | 4.7 s |
| The compiler's own source | 851,625 | self-built A2 | 584 MB | 5.1 s |
| The compiler's source grown with data functions | 4,194,303 | seed-built A0 | 1,004 MB | 9.2 s |
| The same | 4,194,303 | self-built A1 | 1,235 MB | 10.1 s |
| 434 functions of arithmetic and strings | 1,048,575 | A2 | 874 MB | 7.1 s |
| 1,727 such functions (a 23.8 MB image) | 4,194,303 | A2 | 3,650 MB | 44 s |
| Comment lines around five functions | 4,194,303 | A2 | 226 MB | 10.6 s |
| One function of 125,000 statements (21.6 MB image) | 1,625,128 | A2 | 3,175 MB | 13.3 s |
| The compiler's source grown with data functions | 16,776,191 | seed-built A0 | 5,090 MB | 27 s |
| The same | 16,776,191 | self-built A2 | 6,280 MB | 26 s |
| The late-trace program padded with comment lines | 16,776,191 | A2 | 2,170 MB | 8.8 s |

So 1 GiB was already nearly used at the old source limit (874 MB for a dense
1 MiB program) and is exceeded by the compiler's own source once that passes
about 1.5 MB; 16 GiB leaves room for a source at the limit that is one
function (about 8 GB by the last row).

## Building the compiler from the seed

The seed frontend is the pinned parser, which reads at most 1,048,576 bytes
(measured after the adapter has translated the byte spelling). The compiler's
assembled source is 851,625 bytes and will pass that.
`scripts/bootstrap-alchem-compiler.py` therefore lowers a longer source in
parts (`frontend_ir`): each part is the whole module with the bodies of the
functions outside it replaced by a constant of their type, so every call is
still checked against the real signature, and each function's IR is taken from
the part that holds its body. `harness/compiler_entry.py` checks that the IR
made in three parts equals the IR of the whole source, byte for byte. A single
function must still fit the parser beside the signatures of all the others.

Seed IR V11 reads up to 16,777,216 bytes (`bytes.read`; versions before it keep
1,048,576), and both backends emit the same code for it.

## Limits that remain

- 65,535 functions and 65,536 table records (`alchem-modules.md`, "Compiler
  representation"; seed IR V11 takes 65,535 functions too, earlier versions
  256). It was 4096 and 8000. The compiler's own source has 1,862
  functions in 1,239,267 bytes (it had 3,491 before the library stopped
  costing a function per entry), and a library function written in Alchem no
  longer adds one (`alchem-library-profile.md`), so the source limit comes
  first only for dense functions: at the compiler's own density 16,776,191
  bytes hold about 25,000 functions, and a program of one-line functions
  reaches 65,535 at about 3.6 MB (the pinned compiler takes more).
  A program of 65,535 functions has 64 bytes of source for each on average.
- A `for` body's statements were compiled with the code so far copied for
  each (12.6 GB at 5,000); they are joined in runs of doubling length now, as
  a function body's are (`wf_more`; "Costs that grow faster than the
  program" below).
- A compile reads the whole source a fixed number of times whatever the
  library holds: once to choose the library functions (`ny_pick`), once for
  the functions that need a shared runtime (`na_seen`), and then the
  readings other components make for themselves: the sigil hints
  (`sg_hints`), the stream hints (`nn_hinted`), `inspect` and the float
  parsers (`ni_mentions`, `ne_quoting`), float literals, and two for the
  failure-trace tables (`nz_marks`, the largest part of what is left). It
  read it once for every mention any library entry could be appended for.
  See "Time" below.

## Fixed limits

The pinned compiler bounds a program by its source (1 MiB), by the nesting
of its parser (256 levels) and by the operators one expression may chain
(1024). The native compiler had a number of smaller bounds of its own: scans
that gave up after a count of tokens, counts kept in a byte, depths. Each
was looked for with programs at and past it (`scripts/generate-gaps-cases.py`,
`limits()`: 2, 10 and 100 times the old figure where a program of that size
still fits the pinned compiler's megabyte) and those the pinned compiler
accepts were removed where a byte did not hold them.

Removed, or now where the pinned compiler has them:

| What | Was | Now |
| --- | --- | --- |
| Tokens of one call written as a statement (`IO.inspect({45 parts} == {45 parts})`) | 200 (`np_skip_name`) | the source |
| Tokens of one argument, list element or map entry | 1024 (`nc_span`) | the source |
| Tokens of a bracketed value or pattern, a guard, a default value, a `when`, a `with` clause | 200, 512, 1024, 4096 or 100,000 by place | the source |
| Elements of a list or map literal | 4096 | the source |
| Characters of a name | 64 | the source (5,000 run) |
| Characters of a comment line | 1008 | the source |
| Nesting of parentheses, lists, tuples, maps, calls and `some(`, each inside the last | 200 of the compiler's own levels | 126, as upstream (two parser levels each) |
| Nesting of `if`, `case` and `cond` | 200 | 251, as upstream (`not`: 253) |
| Nesting of a type (`list[list[...]]`) | 32 | 125 as it is written, as upstream (130 held) |
| Operators chained at one level (`a + b + ...`, `<>`, `and`, `++`) and pipes in a chain | 4096, and a chain that long took the machine's memory | 1024, as upstream |
| Variants of a sum type | 126 (the tag was compared as a signed byte: 128 and up matched the wrong arm) | 250 |
| Fields of a struct | 31 | 250 |
| Elements matched by a tuple pattern | 127 (the same signed byte) | 250 |
| Lines of a heredoc | about 20,000 (one call a line; status 72) | the source |
| An error inside nested `if`/`case`/`cond` | twice the work at each level, a statement form being tried again as a value (20 levels took the machine's memory) | tried again once, not inside another such try and not past 32 levels (`nx_again`); 20 levels: 0.05 s |
| A body nested deeper than the parser allows | compiled to the bottom, then refused | refused by the scan that finds the function's end (`nc_body_chunk`) |

`np_close`, which finds a closing bracket, walks its tokens by halves: a
call of ten thousand tokens costs the seed-built compiler no depth of
calls (its 1024 would not hold one a token).

Removed in a later round (the numbers are sizes that were run against the
pinned compiler; `scripts/generate-gaps-cases.py` holds the programs):

| What | Was | Now |
| --- | --- | --- |
| Bindings alive in one function, with the values a `case`, pipe, `for`, `with`, `try` or pattern holds meanwhile | 250 | the source. A slot is no longer a byte anywhere: a record of the environment has the slot of its place among the records (`nc_lookup` counts), and patterns, captures, comparators and the plans of `case`, `for`, `with` and `try` hold slots in three bytes. A slot from the 255th on is addressed behind an eight-byte instruction that does nothing and holds its distance from RBP, which is how `nc_peak` sizes the frame without mistaking other code for one; a frame past 16 KiB is checked whole against the stack limit (`nc_guard`). 5,000 bindings: 2.1 s, 1.4 GB |
| Generators of one `for`; clauses of one `with` | about 60; about 125 | the source (1,026 each ran; see the costs below) |
| Parameters of a function | 200 | 65,534 (the count is the record's byte and the byte that was spare before its owner, `nc_argc`); defaults past 255 are counted where they are needed (`nj_defaulted`) |
| Arguments of a call; parts of a tuple; parameters of a function type or of a lambda | 249; 250; 250 | the source. An argument packet with 255 arguments or more, or a type list that two bytes do not hold, has its count in three bytes and the length in four behind a count byte of 255 (`nc_arg_packet`); arguments and tuple parts are compiled one after another and joined in runs of doubling length (`nc_arg_more`, `nr_more`). 5,000 arguments: 2.0 s; a tuple of 5,000: 0.1 s |
| Variants of a sum type; fields of a struct; type parameters of a struct or sum type | 250; 250; 120 | the source (5,000 variants: 0.4 s; 5,000 fields: 0.8 s; 2,000 type parameters ran). Declarations are walked once where they were walked once for every index (`nv_seek`, `nd_seek`, `nd_located`) |
| A structural type | 255 bytes | the memory. A type behind its length (a cell: `nt_cell`) has one length byte below 255, else the byte 255 and four bytes; the count of a tuple, a function type or an instance of a generic type is one byte below 255, else 255 and three bytes (`nt_counter`). Value packets, environment records, argument packets and type lists hold cells. The library reads the same bytes for the message types of processes (`Process._tcount`) |
| Digits of an integer or float literal, with leading zeros | under 900; 800 kept | the source (100,000 zeros before a 7). A float keeps 800 significant digits, as Go does |
| Elements of a list or map literal; a string | the source, with memory growing with the square (a list of 50,000 exhausted 6 GB; a string of 100,000 bytes took 660 MB) | linear: spans and chunks are joined in runs of doubling length (`nc_list_more`, `ns_run_more`). A list of 150,000 integers: 2.7 s, 1.3 GB; a string of 1,000,000 bytes: 1.4 s, 460 MB |
| Entries of a map literal | from the 4,097th on an entry was compiled as the one 4,096 before it (the index shared a number with a flag, `nm_pair`): `map_size` of 5,000 entries gave 4,096 | every entry |
| Arms of a `case` or `cond`; clauses of a function; `#{}` in a string; statements in a `for` or `try` body | about 2,000 (5,000 exhausted 6 GB: each was compiled inside the one before it and its code copied once for each) | linear, see below |

What remains fixed, with the reason:

| Limit | Number | Why |
| --- | --- | --- |
| Source | 16,776,191 bytes | positions are 24 bits (above; #19); the pinned compiler stops at 1,048,576 a file |
| Functions; table records | 65,535; 65,536 | 16-bit ids (below) |
| Parameters of one function | 65,534 | two bytes of the table record (the pinned compiler takes what its megabyte holds, about 140,000 one-letter parameters) |
| The description of a type for `inspect`, the JSON library and node messages | 64 KiB a node: a struct of about 3,000 fields, a sum type of about 4,000 variants | a node's length is 16 bits in the format the inspect routine (`spec/integer-parse-x86_64.s`), `library/JSON.alc` and the node codec read. Counts and name lengths in it are one byte, or 255 and four bytes (`ni_count`, `ins_count`), which `inspect` reads; JSON and node messages read one byte, so a type with 255 fields, variants or tuple parts or more has no JSON or wire form (it is refused at compilation: `ni_held`, `ni_small`) |
| The name of a function in a failure trace; of a type variable | 254 bytes; 255 | one length byte in the trace tables (`nz_named`) and in a type (tag 16) |
| Forms of one library function | 16 | `ny_forms` tries module names ...v2 to ...v16 |
| Elements of a byte literal `b[...]` | 128 | the compiler's own dialect only |
| Characters of a base64 byte literal `b"..."` | 4,096 | the compiler's own dialect only; the closing quote is found in steps of 64 characters, and a seed-built compiler fails past about 768 |
| Calls nested at run time | 100,000 | as upstream |

## Costs that grow faster than the program

The compiler never frees, so a cost that grows with the square of a count
ends as memory. What was made linear, and how:

- The arms of a `case` (`native-arms.alc`, `pa_`), of a `cond` (`pk_`) and
  the clauses of a function (`pc_`) are compiled one after another, each
  arm's code apart with the length of its closing jump left out, and put
  together once all are known (`pa_assemble`), in runs of doubling length.
  That no arm is unreachable and that every value is matched is decided at
  the end: for arms that differ by their constructors alone (literals,
  variants, `true`/`false`, names) by sorting their keys (`pa_repeats`), for
  others by the matrix test as before (`pa_replay`). An arm that waits for
  the type of the arms after it, or gives them a type to expect, is left to
  the older `np_arms`/`nk_cond_arms` from that arm on. A case over a sum
  type is `np_case`'s too (it was `nv_case`'s). 50,000 literal arms: 3.4 s,
  1.7 GB (the pinned compiler needs 92 s for 20,000); 20,000 clauses: 1.9 s,
  1.0 GB; 20,000 `cond` arms: 1.3 s (the pinned compiler runs out of its two
  minutes).
- The function table kept every clause of a function in its window while
  the function was declared; a further clause is now left out of the window
  once the clauses before it declare every parameter's type
  (`nc_table_kept`).
- A string's `#{}` values are joined by code that stands in one row
  (`ns_part_more`): 20,000 of them compile in 1.5 s (the pinned compiler's
  Go build gives up there).
- A `for` or `try` body's statements are joined in doubling runs
  (`wf_more`): 20,000 statements in each of the two, 5.5 s and 1.5 GB.

- The statements of a block are compiled in windows of the environment
  (`native-scope.alc`, `ev_`). An environment is one byte string and a
  binding made a longer one, so a block of n bindings copied n
  environments of up to n records several times and every search read
  them all. A block whose environment has passed 1,024 bytes
  (`ev_plain`, about ninety bindings) after eight statements keeps its
  records in two indexed stores and a short list instead: the last 512
  statements' records in the second store and the list, the last 16 in
  the list. A store holds the records, the entries of those found by name
  in sorted runs (a new run is joined with the runs before it that are not
  twice as long, so there are few) and the entries of those without a
  name. Each statement is compiled in an environment of its own: the
  records whose name stands anywhere in its text (read as bytes, so a
  name in a string, a sigil or a heredoc counts), those without a name
  that say where a statement stands or what type is expected, and one
  record of type 47 for every run of records left out, which stands for
  their slots (`nc_env_gap`; `nc_lookup`, `nc_env_count`, `nc_env_skip`
  and the three other places that count slots add its number). A
  statement's text is read by tokens to the first word of the next
  statement or to what closes the block (`ev_extent`). A statement that
  does not compile so, or ends after that, is compiled once more in the
  whole environment behind a record of type 48; blocks inside such a
  compilation use no windows, so a failure costs one more compilation and
  not one at every level of nesting. A smaller block is compiled exactly
  as before.
- An expression in an environment longer than 1,024 bytes is compiled in
  a window too (`ev_expression`, from `nc_expression`): its text ends at
  a comma or a `do` outside brackets unless it starts with a word whose
  form has them, and it is compiled again in the whole environment when
  it fails or ends later.
- A function value copies into its record only the records of its
  environment that are not left out (`nf_carried`, `gm_held`): inside a
  window that is what the statement names. 10,000 lambdas after one
  binding compile in 3 s and 0.7 GB (2,000 exhausted 3 GB: each record
  held every binding before it, and the code that fills a record grew
  with them).
- The lines of a heredoc with `#{}` are steps like those of a quoted
  string (`ns_heredoc_step`), joined in runs of doubling length: 10,000
  lines, 0.7 s and 0.4 GB (the pinned compiler: 59 s, 1.8 GB).
- The parts of a tuple pattern or of a variant's pattern are parsed each
  in the first one's environment behind a record for the slots bound
  before it and joined in runs (`np_children`); that no name is bound
  twice is seen at the end by sorting. The types of a tuple's parts are
  cut by halves (`np_cells`). 2,000 parts: 0.17 s and 170 MB (690 MB).
- `fn[...]` that is a type is passed at once by the scan that finds a
  function's end (`nc_body_chunk`): 2,000 function types nested in each
  other are refused in 0.05 s (6 s and 1.1 GB, each `fn` read to its
  closing bracket).

Measured on a machine busy with other work (bindings `x1 = x0 + 1`):

| Bindings in one function | Native | Pinned compiler |
| --- | --- | --- |
| 5,000 | 0.8 s, 160 MB (was 3.6 s, 1.4 GB) | |
| 10,000 | 1.7 s, 340 MB (was: exhausted 3 GB) | 6.6 s, 257 MB |
| 30,000 | 3.0 s, 890 MB | 43 s, 687 MB |

Of the 890 MB about 770 MB is what 30,000 statements of that kind cost
without any binding (the code of the runs, copied once a doubling, and
the trace tables); the stores and windows are the rest.

`alchem check` (the front end of `tools/alchem-parse.alc` and
`tools/alchem-check.alc`, which `alchem run`, `build` and `test` go through)
grows with the square of a file where the compiler does not. Functions
`def fN(n: integer): integer do n + N end` in one module, under emulation:

| Functions | Bytes | `alchem check` | The compiler alone |
| --- | --- | --- | --- |
| 2,000 | 107,865 | 4.3 s, 0.16 GB | 0.2 s |
| 4,000 | 217,865 | 14.7 s, 0.42 GB | 0.3 s |
| 8,000 | 437,865 | 51.9 s, 1.3 GB | 0.6 s |
| 16,000 | 889,866 | 199 s, 4.5 GB | 1.3 s |

A file may now be as long as a program (`alchem-modules.md`), but one of
dense code past about a megabyte is beyond what `alchem check` does in the
memory it has; the compiler given the same text directly takes it.

What still grows with the square, with what the pinned compiler takes
(each measured through its wrapper, 4 GB and 120 s):

| What | Native runs | Pinned compiler runs | Why |
| --- | --- | --- | --- |
| Clauses of a `with` | 1,000 in 2.0 GB | 2,000 (22 s), not 3,000 | each clause is compiled around the code of those after it, which is copied about twelve times a level (`wc_clause`, `wc_matched`, `np_join`): the jump past a clause's miss needs the length of what follows. A layout without that length (the clauses one after another, a miss leaving through a return) with the result type folded from the last clause back is what remains to be built |
| `else` arms of a `with` | 500 in 1.2 GB | 1,000 (13 s), not 3,000 | the same nesting in `wc_arms`, with the matrix of the arms so far copied for each |
| Generators of a `for` | 500 in 0.7 GB | fewer than 1,000 (its Go build gives up) | each generator's loop is compiled around the next |
| Parts of a tuple pattern | 8,000 in 2.3 GB | 40,000 (28 s) | the parsing is linear now; the code that matches the parts (`np_emit_node`) and the exhaustiveness test still read the tree from its start for each part |
| Elements of a list pattern | 1,000 in 0.4 GB | 10,000 (12 s) | `[a, b, c]` is a tree of pairs nested in each other (`np_items`), copied at each level |
| Type variables of one generic function | 300 in 0.7 GB | 40,000 (5 s) | substitutions are lists searched from the first and the list of names is cut once a variable (`nu_comparators`, `nu_arguments`, `nu_apply`) |
| Arguments of one call | 5,000 in 0.9 GB | 40,000 (3 s) | the types of a call's arguments are found by index, each from the first |
| Arms over a sum type whose variants have fields | 1,000 in 7 s | 1,000 (86 s), not 3,000 | each arm walks the declaration to its variant; within what the pinned compiler takes |

## Time

Measured on the development machine while other work was running on it, so
each figure is the least of three runs; CPU time agrees with it to a few
percent. "Before" is the compiler at 504a0a1, "now" the one after the
function table got its name index, the library its single index and
`nc_word`, `nc_start` and `nc_half` their short paths (a word that cannot
match by its first byte is not read as a token; one blank between two tokens
is stepped over; a half of millions is taken in larger steps). The padded
programs are comment lines of 71 bytes before a module of two functions;
the function programs are `def fN(x: integer): integer do fM(x + 1) end` in
chains of fifty.

| Source | Bytes | Before | Now |
| --- | --- | --- | --- |
| Comment lines around a module that prints a string | 3,300,000 | 5.8 s, 151 MB | 1.4 s, 151 MB |
| The same around `Enum.map`, `Enum.sum`, `String.split`, `String.pad_leading`, `inspect` | 3,300,000 | 9.7 s, 154 MB | 1.4 s, 154 MB |
| The compiler's source as it was (3,491 functions) | 1,310,166 | 9.0 s, 875 MB | 3.8 s, 762 MB |
| The compiler's source as it is (1,862 functions) | 1,239,267 | | 3.0 s, 603 MB |
| 4,000 functions of one line | 208,949 | 5.8 s, 325 MB | 0.65 s, 139 MB |
| 8,000 such functions | 420,069 | refused (limit 4096) | 1.2 s, 282 MB |
| 16,000 such functions | 854,187 | refused | 2.4 s, 576 MB |
| 60,000 such functions | 3,263,627 | refused | 10.7 s, 2,217 MB |
| 65,535 such functions | 3,566,720 | refused | 12.6 s, 2,918 MB |

The programs of 60,000 and 65,535 functions run (exit status 42). Before the
library had its `ny_seen` (at 1374085) the two padded programs took 12.0 s
and 37.9 s. With only the limits raised and the table still copied and
searched whole, the compiler of 1374085 took 15.8 s and 1,090 MB for 8,000
functions and 83 s and 3,927 MB for 16,000.

Of the 1.4 s for the padded source that uses the library, sampled: 45% is
the two readings for the failure-trace tables (`nz_marks`), 17% the sigil
readings of `sg_hints`, about 14% further readings for single words
(`ny_has`: the stream hints of `nn_hinted` among them), 4% the choice of
library functions (`ny_pick`), 4% the mentions that `na_mentions` still
reads one at a time (`ne_quoting`), and the rest the comment lines
themselves, read once by the table builder.

## Checks

`harness/grown_compiler.py` grows the compiler's own source with data
functions to 16,776,191 bytes (past the 4096 that the
table and seed IR V11 once held), builds it from the seed
through the frontend in parts, and requires A1 == A2, the same image for a
program as the compiler built from the source as it is, and refusal of the
grown source with one byte more.

`harness/source_capacity.py` compiles real late declarations, bindings, calls
and Unicode operations on both sides of 64 KiB and through 256 KiB; a call
chain through five functions spread over sources of 1,048,575, 1,048,577,
2,097,200, 3,200,000, 4,194,305, 8,388,609, 12,582,913 and 16,776,191 bytes,
whose failure trace (a `for`, an `if` value, a `for` with two generators and a
filter, and a column counted past two-byte characters on line 1,677,672) must be the pinned compiler's trace for
the unpadded program with every line moved by the padding before it; a program
of exactly 16,776,191 bytes that runs; refusal of one byte and of 4096 bytes
more, and of a malformed source at the limit; a `for` whose generator stands
745 lines past its body (three nested `cond`s of 249 arms; more than a 32-bit
immediate holds above 24 bits of position), at the start of a source and at
the end of one of 16,776,191 bytes; the compiler under 3 GiB of address space
(the arena is halved until it is granted) and under 512 MiB (exit 71); and a
21.6 MB image whose one function holds more than 16 MiB of code. `harness/compiler_entry.py` reads
binary standard input of 65,535, 65,536, 1,048,575, 1,048,576, 4,194,303,
4,194,304 and 16,776,191 bytes through a compiler entry and is refused at
16,776,192; `harness/input.py` does the same for seed IR V11 at 4,194,303,
4,194,304, 16,776,191 and 16,777,216 and keeps V10 at 1,048,576. `harness/compiler_arena.py` covers budgets up to 16 GiB and their
halving under an address-space limit; `harness/self_host.py` measures the
arena charge of each rebuild against 16 GiB (458 MB seed-built, 601 MB
self-built).
