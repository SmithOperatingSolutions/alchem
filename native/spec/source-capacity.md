# The size of a native source

Native compiler/source-tool entries accept at most 1,073,740,799 bytes (1 GiB
less 1 KiB and one byte: `nc_limit`): a longer input ends with
`E_RUNTIME_INPUT: input exceeds byte limit` and status 65 as it is read, and
no ELF is written. The reader keeps EINTR/short-read behavior and takes
memory as the input comes (`nc_io_prefix`). `nc_compile` checks the same
bound on what it is given, and `nc_compile_all` on the source with the
library functions written in Alchem appended; a program too close to the
limit to hold them is compiled without them, as before. It was 16,776,191
bytes while a position was three bytes (issue #72), and 4,194,303 and
1,048,576 before that.

A source *file* may be as long as a program for the bundlers and `alchem`
(`alchem-modules.md`): `File.read` gives 1,073,741,824 bytes, where the
pinned runtime gives 16,777,216, and a file was held to 16,776,191 bytes
until it did. The pinned compiler refuses a source file past 1,048,576
bytes (`source exceeds 1048576 bytes`) but not a program; a single source
given to `alchem-compiler` directly may be larger than a megabyte because
the compiler's own source has to pass through it; these are deliberate
differences.

Two things keep their own, smaller bound:

- The rewriting of macros, protocols, HTML templates and an `fn` whose
  clauses stand on the lines after it (`native-macros.alc`) keeps a place in
  three bytes. A text of 16 MiB or more that may hold one of them
  (`mx_wanted`: the words `defmacro`, `defprotocol`, `defimpl`, `~h`, `~H`,
  the byte 127, or such an `fn`, anywhere in it) is not compiled. The text a
  rewriting makes may pass 16 MiB.
- A file of tests is under 16 MiB (`tm_prepare`): a longer text is compiled
  as it is, and has no tests.

## What holds a position

A source position is four bytes wherever the compiler keeps one
(`nc_u32`/`nc_long`): in parser packets (a value, a step, an argument packet,
a pattern's packet and the states of the scans start with one, `nc_pos`),
signatures, parameters, list spans (start and stop), string and sigil pieces,
the plans its parts hand each other, the index of an environment's stores and
the function table. A compiled value's flags are the byte after its position:
bit 7 is `nw_mark` (the value's type needed one from its context) and bit 6
`nx_impure`.

Some things keep their length or their bytes, because a compiled program
depends on them:

- A record of an environment is as long as it was. A block is compiled in
  windows from 1024 bytes of environment on (`ev_plain`, `native-scope.alc`),
  and its code depends on that, so no record may grow: one holds where its
  name starts (four bytes) and the name's length (three; it held the name's
  end and a byte nothing read). A record that notes a position
  (`nc_env_note`: the collector's notes, the end of a call that jumps) has
  the position's low three bytes as its type, and stands at the position
  itself when that takes a fourth. The ends a `for` notes (`wf_mark`) are
  three bytes each in a record that stands at the first of them, which tells
  one within 8 MiB of it; one farther away has a record of its own. A piped
  function that waits for its type is kept by how far before the call's `(`
  it stands (`nf_piped_kind`).
- A declared type (a struct, a sum type, an instance of either) is named in a
  type by three bytes, and types are in compiled programs (what a `throw`
  throws, a process's messages). In a source under 16 MiB they are where the
  declaration's name stands, as they were; in a longer one the number of the
  declaration's record (`nd_key`, `nc_wide`: a byte of every table record
  says which). A name not yet resolved (tags 15 and 20) holds the four bytes
  of where it is written.
- A frame's trace word (RBP-136) is 64 bits: in a source under 16 MiB the
  position in its low 24 bits and above them the count of lines past that
  position's own, which a `for` uses (`alchem-traces.md`); in a longer one
  the position in the low 32 and the lines above them. The compiler counts
  with the second form (`nz_past`, `nz_place`) and writes the word the source
  asks for (`nz_low`, `nz_high`); the trace routine is the one assembled from
  `spec/trace-x86_64.s` with its mask and its shift changed (`nz_routine`; on
  ARM64 two instruction words). A position a failure passes to the routine
  is 32 bits whose bits 30 and 31 say how to show it, which is why a source
  ends below 1 GiB. A `try` keeps its lines in eight bytes.
- The end of an interpolation hole is searched with the nesting depth above
  bit 32 of the position (`sg_hole_some`).

So every program under the old limit compiles to the bytes it did: 11,419 of
the 11,421 programs compared, and the other two are compiler entries, whose
one changed byte is the limit of what they read.

Whitespace/comment skipping, body scanning and clause scanning take up to
1,073,741,824 steps.

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

- 16,777,214 functions and 16,777,215 table records (`alchem-modules.md`,
  "Compiler representation"), which a source of 16 MiB did not reach: at
  the compiler's own density that held about 25,000 functions, and
  functions of one line each about 300,000. It was 65,535 and 65,536
  (and 4096 and 8000 before that): a record was named by a number of two
  bytes in the record of its module, at the start of an environment, in
  the context of a function's clauses and in the plans the compiler's parts
  hand each other (the call's target, a struct's or a sum type's number, a
  module in the order of the modules, a function asked about for equality
  or for JSON). Each is three bytes now, and an environment's records
  start at its fourth byte. The table's record went from 27 bytes to 40,
  with four bytes for each position and for its module, so that it need
  not change when positions or numbers grow. None of this is in
  what the compiler makes: every program compiles to the bytes it did, and
  the compiler from the pinned release makes itself. `harness/past_limit.py`
  holds programs whose every function, struct and sum type stands behind
  66,000 others. Seed IR V11 takes 65,535 functions.

  The limit is the same for every system. A position-independent ARM64
  program (macOS, and Linux built so) told an address of the table from a
  number by where a table of 65,541 slots ends, and a slot past that was
  not moved to where the image stands: such a program of 65,540 functions
  ended at its first call (`string_case` on macOS showed it). The
  translation is now given where the program's own table ends
  (`a_block_end`, `xa_block`; `darwin-arm64.md`), so the addresses it
  takes for the table's are those of the table and no more; for a program
  under the old limit that is fewer than before, and the 952 programs
  compared compile for macOS to the bytes they did. The programs of
  `harness/past_limit.py` run on Linux x86-64, on Linux ARM64 built either
  way and on macOS; the first of them is among the programs checked on
  Windows (`scripts/windows-examples.py`).
- A file of tests holds 65,534 declarations: its tests, describe blocks
  and functions are each a record of `native-testing.alc`, whose numbers
  are two bytes in the 48 bytes of its cursor. One with more is refused,
  where it ended the compiler; a program without tests has no such bound.
- A program with a macro, a template or a protocol is read once more by
  `native-macros.alc` before it is compiled. That reading added each
  record to the end of all of them, and each piece of the rewritten text
  to the end of all the pieces, and was three calls inside one another for
  every declaration: 8,000 functions took 4.5 GB, 32,000 the arena, and
  33,000 nested deeper than calls may. The records and the pieces are kept
  in two parts, the later joined to the earlier when it is a quarter of it
  (`mt_kept`, `mt_late`), and the reading is a loop (`mt_index`, whose
  steps say what they add with `mt_next`): 66,000 functions take 12 s and
  123 MB.
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
| Source | 1,073,740,799 bytes, a file or a program; 16,776,191 for a text with a macro, a protocol, a template, a clause-style `fn` or tests | a failure passes its position in 30 bits; the rewriting keeps a place in three bytes (above); the pinned compiler stops at 1,048,576 a file |
| Functions; table records | 16,777,214; 16,777,215 | 24-bit numbers ("Limits that remain"); 65,535 and 65,536 until they were widened |
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

## The alchem command

`alchem check` (the front end of `tools/alchem-parse.alc`,
`alchem-lower.alc`, `alchem-analyze.alc` and `alchem-check.alc`, which
`alchem run`, `build` and `test` go through) and `alchem fmt` grew with the
square of a file where the compiler does not: 16,000 functions, 0.9 MB,
took `alchem check` 199 s and 4.5 GB and the compiler alone 1.3 s. A list
was searched, or copied to add to its end, once for every function:

- the parser added each function to the end of the module's list and
  counted the list for each note and `@doc` (`declarations`), and gave
  each note and `@doc` to its function by going through all of them
  (`documented`). The functions, the notes and the `@doc` texts are now
  gathered last first with a count, turned round once, and given in one
  pass (`noted`);
- the checks before lowering kept the names seen in a list
  (`AlchemLower.merge_from`, `AlchemAnalyze.first_pass`): a map;
- `separate_arities` added each function to the end of its list, and
  `arities_problem` called it again for every function of the program;
- the functions of a module were looked for in a list for every call
  (`resolve_names`, `unit_problem`), and each function's own name in the
  list of all of them (`assembled`): maps;
- `merged_list` and `forms_of` were a call inside the one before for every
  function, each joining its list to the rest: loops (`merged_onto`,
  `forms_onto`) that put each function before the rest, so a module is not
  bounded by how deep calls may nest. `a ++ b` copies `b` as well as `a`;
- the formatter added each function's text to the end of a list
  (`functions_text`).
- the lexer copied the rest of the source to find where a heredoc ends
  (`AlchemLexer.find`), once for every `@doc """`: 16,000 functions with
  one on every fifth took it 8 s, and take 0.4 s.

A field of a tree was read by listing every field of that name
(`AlchemJson.get`) and several were set by passing the object once for
each (`put_all`): the first is now a walk to the field and the second one
pass, which halved the time of the passes that rebuild the tree.

Functions `def fN(n: integer): integer do fN-1(n) + N end` in one module,
under emulation:

| Functions | Bytes | `alchem check` | Was | `alchem fmt --check` |
| --- | --- | --- | --- | --- |
| 4,000 | 244,744 | 2.4 s, 0.3 GB | 14.7 s, 0.4 GB | 0.3 s |
| 16,000 | 1,006,744 | 9.7 s, 1.2 GB | 199 s, 4.5 GB | 1.4 s |
| 32,000 | 2,046,744 | 19.5 s, 2.0 GB | 137 s, 11.7 GB after the first mending | 3.1 s |
| 64,000 | 4,126,744 | 40.2 s, 4.3 GB | the arena used up (status 71) | 6.6 s |

`harness/check_scaling.py` (the gate `check_scaling`) holds 4,000 and
32,000 functions with notes and `@doc` to that: eight times the functions
in less than twenty-four times the processor's time and under 4 GiB, and
the formatter finding nothing to change.

A pass of `AlchemLower.lowered` goes through every statement and
expression of a module and makes each again, an object of some thirty
fields, and there were ten. Six rewrite one kind of statement each
(`unless`, `receive`, the clauses of a `fn`, `cond`, `with`, `check`) and
one the bitwise operators: the module is now read once for which of those
it has (`kinds_of`), and a rewrite runs only when its kind is there or a
rewrite before it ran. An expression that holds no other, a name or a
literal, is left as it is by the walks that would set its five parts to
what they are (`bare?`).

| Functions | `alchem check` | Before these two |
| --- | --- | --- |
| 4,000 | 1.4 s, 0.17 GB | 2.4 s, 0.3 GB |
| 16,000 | 6.1 s, 0.64 GB | 9.7 s, 1.2 GB |
| 64,000 | 25.1 s, 2.6 GB | 40.2 s, 4.3 GB |

What remains is linear: about 0.4 ms and 40 KB a function, a third of it
the lexer and the parser, the rest the passes that still make the tree
again (`qualify`, the names of `assembled`) and the reads of a field,
which pass the fields before it.

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
program as the compiler built from the source as it is, and the same
compiler again from the grown source with one byte more, which was refused
while a position was three bytes.

`harness/source_capacity.py` compiles real late declarations, bindings, calls
and Unicode operations on both sides of 64 KiB and through 256 KiB; a call
chain through five functions spread over sources of 1,048,575, 1,048,577,
2,097,200, 3,200,000, 4,194,305, 8,388,609, 12,582,913 and 16,776,191 bytes,
whose failure trace (a `for`, an `if` value, a `for` with two generators and a
filter, and a column counted past two-byte characters on line 1,677,672) must be the pinned compiler's trace for
the unpadded program with every line moved by the padding before it; a program
of exactly 16,776,191 bytes that runs, and a malformed one that is refused;
a `for` whose generator stands
745 lines past its body (three nested `cond`s of 249 arms; more than a 32-bit
immediate holds above 24 bits of position), at the start of a source and at
the end of one of 16,776,191 bytes. Past the old limit: the same call chain
in sources of 16,776,193, 16,777,217 and 20,971,521 bytes, the `for` at the
end of sources of 16,777,217 and 20,971,521 bytes, programs of 16,776,192
and 25,165,825 bytes that run, and refusal of 1,073,740,800 bytes as they
are read; the compiler under 3 GiB of address space
(the arena is halved until it is granted) and under 512 MiB (exit 71); and a
21.6 MB image whose one function holds more than 16 MiB of code. `harness/modules.py` builds a project
whose imported file is 16,777,217 bytes, with both bundlers, and has both
refuse a file of 1,073,740,800 bytes, imported or the entry; `harness/file_read.py`
reads files of 16,777,217 and 1,073,741,824 bytes and is given the error for one byte more. `harness/compiler_entry.py` reads
binary standard input of 65,535, 65,536, 1,048,575, 1,048,576, 4,194,303,
4,194,304 bytes through a compiler entry and is refused past
1,073,740,799; `harness/input.py` does the same for seed IR V11 at 4,194,303,
4,194,304, 16,776,191 and 16,777,216 and keeps V10 at 1,048,576. `harness/compiler_arena.py` covers budgets up to 16 GiB and their
halving under an address-space limit; `harness/self_host.py` measures the
arena charge of each rebuild against 16 GiB (458 MB seed-built, 601 MB
self-built).
