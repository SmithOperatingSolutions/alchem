# Additional native library APIs

These implementations emit machine instructions from Alchem. Native compilation
and execution invoke no Go/Rust/Python runtime. The pinned upstream registry and
runtime at0b73f880b108 remain read-only references; this is a documented subset,
not a claim that every standard-library API is ported.

| API | Supported behavior |
| --- | --- |
| Enum.map/filter/reduce | Typed named-function iteration over general lists; see alchem-collections-profile.md |
| Enum.join(list[string]) / join(list[string],string) | Exact byte concatenation, optional separator between elements, fresh string; empty input returns empty |
| Integer.to_string(i64) / to_string(i64,base) | Bases2..36, uppercase digits, signed endpoints including minimum i64 |
| Integer.digits(i64) / digits(i64,base) | Base>=2, most significant first; negative input has negative digits; zero gives [0] |
| Integer.parse(string) / parse(string,base) | result[integer,string]: Go ParseInt with base10 or2..36 (optional sign, case-insensitive digits, no prefixes/underscores/spaces, exact signed64 range); error is the strconv.Quote of the input plus " is not an integer", and " in base N" for the two-argument form |
| Integer.undigits(list[integer]) / undigits(list[integer],base) | Base>=2; digits must be0..base-1; checked signed64 multiply/add; empty returns0 |
| String.duplicate(string,count) | Exact bytes repeated count times; zero/empty produce fresh empty strings; count>=0 |
| IO.read_line() | option[string]: next stdin line without its "\n" and then one "\r"; none at end of input; a final unterminated line is returned |
| IO.read_all() | string: the rest of stdin to end of input |
| File.read(string) | result[string,string]: ok(contents) or error(reason) with the pinned os.PathError text ("open PATH: no such file or directory", "read PATH: is a directory", "errno N" past Go's table, "invalid argument" for an embedded NUL) or "file is not valid UTF-8" |
| File.write(string,string) | result[tuple[],string]: os.WriteFile(path,content,0644): create or truncate, write all bytes, close; ok({}) or error with "open/write/close PATH: reason" |
| File.append(string,string) | result[tuple[],string]: like File.write but opened O_APPEND without truncation, creating the file with mode0644 |
| File.remove(string) | result[tuple[],string]: os.Remove: unlink, then rmdir; reports rmdir's error unless it is ENOTDIR, as "remove PATH: reason" |
| IO.write(string) | Main-body statement, exact stdout bytes, no appended newline |
| System.argv() | list[string]: process arguments after the program name, each run of invalid UTF-8 replaced by one U+FFFD (Go strings.ToValidUTF8); fresh copies per call |
| System.get_env(string) / get_env(string,string) | option[string] from the initial environment: the first entry whose text before its first "=" equals the name exactly; empty names never match. The two-argument form returns the value or the default string |
| System.pid() | Current Linux process identifier as a string |
| System.system_time() / os_time() | Linux CLOCK_REALTIME in integer nanoseconds since Unix epoch |
| System.stop(status) | Main-body alias of System.halt, with the same checked0..255 status contract |

Integer.parse error text matches the pinned runtime byte for byte: printable
runes (strconv.IsPrint, Go 1.27.4/Unicode 17.0.0, spec/print-ranges.json) are
kept, `"`/`\\` and \a\b\f\n\r\t\v use short escapes, other ASCII controls and
invalid UTF-8 bytes use lowercase \xHH, and other runes use \uHHHH or \UHHHHHHHH.
Its runtime (spec/integer-parse-x86_64.s, about5KB with the range table) is
emitted once per program, in a function-table slot after the program's records,
when the source mentions Integer.parse. Results and error strings use the
checked arena.

IO.read_line/read_all follow the pinned runtime: text must be valid UTF-8 (Go
utf8.Valid) and a line may hold at most1,048,576 bytes after trimming; either
violation fails at the call (alchem-failures.md). A read that fails is the end
of input for read_line and a failure of read_all; EINTR is retried. read_line reads one
byte per system call, so it never consumes input after its newline and mixes
freely with read_all, other processes and later reads. read_all takes at most the
pinned16,777,216 bytes: more input ends the program at the call with `input exceeds
16777216 bytes`, as the pinned runtime does (the whole input is read first; one that
exhausts the arena exits71).

File.read opens with O_RDONLY|O_CLOEXEC, retries EINTR, reads to end of file and
always closes the descriptor. File.write opens with O_WRONLY|O_CREAT|O_TRUNC|
O_CLOEXEC and mode0644 (an existing file keeps its mode), writes any bytes, retries
EINTR, continues after short writes and reports a failed close. The shared file
runtime (spec/file-read-x86_64.s with Go 1.27.4's errno texts from
spec/errno-messages.json, about4KB) is emitted once per program in the table
slot after the Integer.parse slot. A file of more than the pinned16,777,216 bytes is
error("file exceeds 16777216 bytes"), as there (it is read first; one that exhausts
the arena exits71).

Native entry stubs keep the initial stack pointer in R14 (argc, argv, envp), which
generated code and runtime routines otherwise leave untouched. Environment values
are returned byte for byte, like the pinned runtime; System.put_env and the
environment it changes are described in alchem-system.md.

All arguments evaluate left to right. Invalid bases/digits/negative repetition
counts and undigits arithmetic overflow fail at the call with the pinned
runtime's message (alchem-failures.md; a compiler entry exits with the status
that names the message). Impossible/exhausted
allocations exit71. IO.write retries EINTR, advances on short writes, and exits74
on zero progress/other errors. Clock syscall failure also exits74. These private
native errors have no target diagnostic; the bootstrap IR's diagnostics remain
separate. IO.puts retains its payload-plus-newline behavior and fault checks.

String.duplicate checks multiplication/arena bounds before copying, including
huge counts and empty input. Join computes the result size before allocation.
Formatting uses bounded stack scratch; integer lists store full signed values.
User allocations stay in the checked RW arena (16 GiB reserved lazily,
alchem-tail-calls.md). No executable heap mapping,
collection reclamation or implicit type conversion is introduced.

File, System, Path and IO functions on files, devices, the environment and
external programs are written in Alchem (alchem-system.md). Further
Unicode/string transformations and remaining library overloads are not
implemented. Grapheme behavior is unchanged; see the pinned
Unicode compatibility limits in alchem-grapheme-profile.md.

harness/integer_parse.py checks796 parse results/error texts against independent
Python ParseInt/Quote oracles (which agree with the pinned upstream compiler on
every case), invalid bases including explicit0, arena exhaustion, a65535-function
program using the runtime and type/arity rejections.
harness/io_input.py runs189 input/read-sequence combinations against a Go
ReadSlice/TrimSuffix/utf8.Valid oracle (matching the pinned upstream build on the
same inputs), the1MiB line boundary, no over-read past a newline, chunked pipes,
arena exhaustion, closed stdin, EINTR/EIO injection and rejections.
harness/system_env.py execs programs with exact argv/envp bytes (duplicate keys,
entries without "=", invalid UTF-8, argc0) and compares44 runs with Go os.Args/
ToValidUTF8/LookupEnv oracles; native output matched the pinned upstream build
on the hand-written cases. It also checks argv arena exhaustion and rejections.
harness/file_read.py also checks7 writes on disk (contents, truncation, modes,
symlinks),9 failing writes against os.WriteFile's reasons (equal to the pinned
upstream output) and write EINTR/EIO and close EIO injection.
harness/file_read.py compares22 paths (missing, directory, unreadable, ENOTDIR,
ELOOP, ENAMETOOLONG, NUL and empty paths, non-UTF-8 names and contents, symlinks,
/dev/null) with an os.Open/ReadAll oracle that equals the pinned upstream output,
plus arena exhaustion, descriptor reuse under a16-descriptor limit, open/read
EINTR and EIO injection and rejections.
harness/library_expansion.py compares numeric and byte outputs with independent
Python calculations, checks real PID/wall-clock results and rejects bad types.
It injects EINTR, short/zero writes and clock failure, plus real closed/full output.
harness/collection_memory.py checks26 exact allocation charges. These run at
A1/A2/A3 alongside the existing byte/string/grapheme and compiler-component gates.
The assembly references and regeneration scripts are development tools only;
ordinary builds read the checked Alchem literals.

`System.cwd!()` and `File.cwd!()` follow `os.Getwd` (alchem-system.md).

## Library functions written in Alchem

Most of the library does not need machine code of its own. `library/NAME.alc`
holds functions of library module NAME written in Alchem, each behind a line
`#: name/arity` (and `needs other/arity` for the functions of the file it
calls). `scripts/generate-prelude.py` turns them into
`native-prelude-data.alc`, and the compiler appends to a program the functions
it mentions, as modules named `Alchem`, the library module and the number of
parameters (`AlchemEnum2` holds `Enum.find/2`), since one name may take
several numbers of arguments. A library call the compiler has no code of its
own for is looked up there by its name and its number of arguments, a piped
value included. A compiler entry gets none.

A name may also have several forms for one number of arguments, for other
types (`#: sort/1 form 2`, module `AlchemEnum1v2`, up to form 16): the call takes the first
form its arguments fit. A type variable whose name starts with `ord` has an
order as well as an equality (`alchem-ordering.md`), so a function that
needs the order of its elements is one generic entry.

`harness/library.py` holds probes and the pinned library reference's own
examples with the pinned compiler's output (over 300 programs) and checks the
generated file against its source. So far 407 functions across
`library/Enum.alc`, `List.alc`, `Map.alc`, `String.alc`, `Kernel.alc`,
`Integer.alc`, `Path.alc`, `Range.alc`, `Base.alc`, `Bitwise.alc`, `URI.alc`
and `Version.alc`; Enum and List also take maps,
through forms of their own. For Map the map routines take the key type of a
type variable from its comparator at run time, so generic functions over
maps compile. Names may end in `!`.

Differences that remain:

- The byte-level String functions that are still written over
  `String.split` and `String.slice` are quadratic in the length
  (`next_codepoint`, `next_grapheme`, `splitter` with several patterns);
  `graphemes` and `codepoints` walk the text once. A list built element by
  element is no longer copied at each step, and the functions that rebuild
  their list at every step by design are named in `alchem-lists.md`.
  Sorting sorts one copy in place (`alchem-ordering.md`).
- A failure inside a library function is named where the program called
  the function and the library's own calls are left out of the trace, as
  the pinned runtime has it (`alchem-sets-streams.md`). Where a library
  function does not `raise` the pinned message, the message is that of the
  code that failed there (often `pattern match failed`).
- `step[a]` is a sum type the library declares (`library/Kernel.alc`); its
  variants are written `cont(x)` and `halt(x)`, as values and as patterns,
  and `inspect` writes them so.
- A name takes at most sixteen forms per number of arguments.
- The library text is held in the compiler's source as base64 byte
  literals (`b"..."`), packed by byte pairs (127 codes; `ny_expand_range`
  unpacks an entry when a program needs it): 733 KB of packed text in
  1.04 MB of source, where decimal `b[...]` took 2.23 MB. See
  "How the library is held and chosen" below.
- A program at the source or function limit is compiled a second time
  without the library (`nc_compile_with`).
- A struct a library file declares is an entry `#: struct Name`. All of
  them live in one appended module, `AlchemTypes`, where a type name is
  looked up that the using module does not declare, so library functions of
  any parameter count and the program itself can name it (`%URI{...}`).
  `URI.merge`, `URI.append_path`, `URI.append_query` and `Version.compare`
  of two versions are still to be written.
- `library/Regex.alc` (`alchem-regex.md`) reaches bytes through the
  compiler (`rx_ab`) and holds a component of the compiler (`#include`); a
  form of `String` that takes a regex is appended only to a program that
  holds one.
- The String, Base and URI functions reach bytes by comparing against 256
  one-byte strings, which costs memory: `Base.encode64` takes about 28 KB of
  text in the arena, which gives nothing back.

## Ordering
## How the library is held and chosen

`scripts/generate-prelude.py` writes `native-prelude-data.alc` with no
function per entry. The entries of one appended module (`AlchemEnum2`,
`AlchemEnum1v2`, `AlchemTypes`) are one packed byte string, `ny_dN()`, held
in parts of 4000 bytes when it is longer (the seed-built compiler reads a
function body sixteen tokens to a nested call and is allowed 1024 calls);
`ny_data(group)` returns the string of a module by its number. One index,
`ny_index()`, holds everything else; its layout and the rules are at the top
of the generator. 1,006 entries are 214 functions and 685,991 bytes of
source (they were 1,889 functions and 837,724 bytes); the compiler's
assembled source fell from 1,310,166 bytes and 3,491 functions to
1,239,267 bytes and 1,862 functions.

Which entries a program gets is decided in one reading of its text
(`ny_pick`), with the hints of `sg_hints` and `nn_hinted` appended as
before. The compiler keeps a byte per entry and per flag. At each byte of
the text the index gives the texts that start with it (a bucket per first
byte, a handful of texts each), and a text that stands there is a trigger.
Only code is read: a comment is passed over, and of a string or heredoc
only what stands in its `#{ }` (`ny_pick_text`, `ny_pick_holes`), so
`"HTTP.serve: not started"` appends nothing and `"#{Enum.count(x)}"`
appends `Enum.count`. A sigil is read whole, as before: the text of one
may be code (a template). The reading is still one pass; where it has got
to travels in the last three bytes of the state, since a string may end
past the stretch a call was given. For the 875 programs of the examples
corpus the images are byte for byte what they were, but for three whose
strings held a trigger ("bad input" appended `input`; `"started"`), which
are smaller. `harness/gaps.py` compares the image of a program whose
comment and string name library functions with the same program without
the names.

- `Module.name`, for a function of a library file: the module as a whole
  word (as `nc_word` reads one, so also at the end of a longer word), a
  dot after any blanks and comments, and a
  name the module's sorted name list holds (a binary search). It marks the
  entries of that name, whatever their number of parameters and form; the
  entries whose header says `exact` only when the call has their number of
  arguments (`nh_given`, asked only while such an entry is unmarked).
- a bare name as a whole word, for a function of `library/Kernel.alc`.
- a text anywhere, for a struct: the file's module name, the struct's name
  (the part after a dot) and the texts after `also` in its header (`~D[`).
- a word that sets a flag: the name of a module, or `native_compile`, which
  marks a compiler entry (it gets no library).

A marked entry marks the entries it needs, and those theirs (`ny_mark`;
`needs` names a function by its number of parameters and brings every form
of it), and a function of another module that names a struct's type marks
the struct. `Sys`, the library's own module, has no trigger: its functions
come through what needs them. An entry is appended when it is marked, or one
of its `extras` flags is set, and all of its `homes` flags are set:

- `extras`: a `Sys` function that needs only `Sys` functions and that more
  than three functions of one module reach comes with the word of that
  module (not `IO`); a `Regex` entry other than `compile`, `compile!` and
  `rx_compile` comes with the word `Regex`.
- `homes`: a form of `IO` that names a struct of another file wants that
  file's module named too (`IO.puts` of a file needs `File`); a `Regex`
  entry, and an entry of another module that needs one, wants the word
  `Regex`.

The appended entries are then written module by module in the order of the
index; a module is written when it has one and, where it has a guard, a
module that reaches it is named. These are the rules the generator had when
it tested mentions one by one (`ny_seen`) and gave every entry the mentions
of all that reach it; the set of entries appended is the same for every
program. That was checked by compiling 15,743 programs with the compiler
before and after, every image the same byte for byte: every example of the
pinned references, the module-shaped programs of the gates, and generated
mentions (for each library name the call with nought to four arguments,
piped, referenced, with blanks about the dot, and near misses; each struct
text and module word alone and inside a longer word; and 4,000 programs of
two to four of these together).

What an entry costs the compiler's source is its packed text, 17 bytes of
index, its name once in its module's list when no other entry has it, and
two bytes in the list of each entry that names it under `needs` (equal lists
are held once). No entry costs a function, so a helper shared by many
entries can be an entry of its own.

Compile time no longer grows with the size of the library times the size of
the program: see "Time" in `source-capacity.md`.

The functions with machine code of their own that need a shared runtime
(`na_shared`: Integer.parse, the file functions, the String case and
grapheme functions) were likewise found by one reading of the source per
function, fourteen in all; `na_seen` now finds them in one reading.

## A program's module in place of a library module

The pinned language lets a program have a module named `DiskStore`,
`WebSocket`, `Version` or `OptionParser` (`RetiringModule`): a package now
provides each, and a program that imports the package, or has a module of
the name, uses that module and not the library's (issue #129).

- The name is taken as a module's (`nc_retiring_module`); every other
  library module's name is refused, as before.
- The library is chosen from the program's text with such a name
  unreadable wherever it stands (`ny_masked`), when a line of the program
  declares the module: none of the library's functions or types of that
  name is appended.
- The module's types are its own under any name, and the type of the
  module's own name is written by that name alone in every module
  (`%Version{}`), as the library's type was (`nd_library`).
- A type named after a library module anywhere else is refused by the
  front end with the pinned message, `type name Registry is reserved for
  the builtin Registry functions`, at its place.

The modules the library is appended as (`AlchemEnum2`, `AlchemTypes` and
the rest, as this file writes them) are named in a program's image with the
byte 127 in place of the `e` of `Alchem`: neither front end takes that byte
in a source file, so no module of a program is one of them, and a program's
module named `AlchemTypes` is its own (issue #102, `nc_ours`).

`harness/replaced.py` holds sixteen programs with what the pinned command gives.

## Ordering and sets (state after the float-forms merge)

The ordered functions (`Enum.sort`, `max`, `min`, `min_max`, the `_by`
forms, `List.sort`, `List.keysort`, `min`, `max`) are one generic entry
each: the compiler makes the order for the type the call gives, as it makes
equality, and rejects the types the pinned language does not order
(`alchem-ordering.md`). Tuples of any size, lists and any nesting of them
sort as the pinned runtime sorts them, NaN included; the earlier forms per
element type, which compared a nested tuple or list as a word
(`Enum.sort([{1, {2, 3}}, {1, {1, 3}}])` gave the input order), are gone.

Helper functions the library files share are public and so callable from a
program, which upstream would reject (`Date.cm` and the like). The ordering
helpers are not: a function of the library whose name starts with `o_` can
be called from the library alone, as one whose name starts with an
underscore.

## The functions kept without a module, and put_elem

The pinned language keeps `prepend`, `concat`, `map`, `filter`, `reduce`,
`put`, `get` and `has_key` from before its modules (`library/Kernel.alc`).
As upstream has them:

- `reduce(list, start, f)` gives `f` the accumulator first and the element
  second, the reverse of `Enum.reduce`. It was passed on as it stood and
  folded with the arguments the wrong way round, silently:
  `reduce([1, 2, 3], 0, fn(acc: integer, n: integer): integer do acc * 10 + n end)`
  gave 60 for 123.
- `map`, `filter` and `reduce` take a function that has its types (a named
  one, `&name`, or `fn(x: type): type do`): `fn x -> ... end` and a capture
  are rejected there (`ny_untyped`), since upstream types the function
  before the list.
- an empty list as the first argument takes its type from the argument
  after it: `prepend([], 1)`, `concat([], [7, 8])`, `map([], &f)`,
  `reduce([], 5, &g)` (`nu_legacy`).
- `put_elem(tuple, index, value)` is the tuple with the element at the
  literal index replaced, of the value's type (`nr_put_elem`).

These words, the keywords and `length` name no binding or parameter, as
upstream (`nc_unbindable`: assert, length, when, prepend, concat, map,
filter, reduce, put, get, has_key, fn, import, extern, require, in, cond,
raise, with, for, unless, defprotocol, defimpl, defmacro). The words of
types and `byte_size` do: `bytes = "a"`, `string = 1`, `option`, `integer`,
`boolean`, `void` were refused before and are bindings like any other.

A call written as a statement and a parenthesized value on the next line
are two statements (`Process.sleep(150)` then `(n * n)`): only a `(` on
the call's own line calls its result (`nx_calls`).

Two entries of one library module may not define one name: `Enum`'s
`product_by` for streams was form 3 beside the list form of `sum_by/2
form 3`, so a program that named `Enum.sum_by` and anything of streams
(`Enum.count` alone) did not compile. It is form 5 now.
