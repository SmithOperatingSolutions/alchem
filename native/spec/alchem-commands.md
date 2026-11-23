# The commands that print documentation

`alchem` (`tools/alchem.alc`, `spec/alchem-testing-gen.md`) has the pinned
command line's commands that describe the language, the library and the
command itself. They are the module `AlchemGuide`, `tools/alchem-guide.alc`:

    alchem help | -h | --help
    alchem version [--json]
    alchem syntax [--all] [--group name] [--json] [topic]
    alchem doc [--all] [--group name] [--search text] [--json] [Module | Module.function | file.alc]
    alchem agent-guide [--json]
    alchem agent-install [--scope project|user] [--dir path] [--force] [--json] <agent> | --list
    alchem docs [--check] [--dir path]
    alchem alx
    alchem fmt [--check] path...

Each prints what the pinned command prints, with its status: the text, the
JSON (two spaces a level, a list nothing was put in as `null`, `<`, `>` and
`&` as `<`, `>` and `&`), the message for a topic, a module, a
function, a group or an agent there is none of, with the names close to it,
and the usage after a flag the command does not take. `alchem` without a
command and with one it does not have print the list of commands and end
with status 2.

## Where the text comes from

`tools/alchem-guide-data.alc` holds the tables: the commands with their
flags and the usage of each, the topics, the modules, the functions, the
examples a group of modules is introduced with, the agents and the file
written for each. `scripts/generate-guide-data.py PINNED` makes it from what
the pinned command line prints, so `alchem` describes the language and the
library the pinned command describes; `--check` fails when the file is not
what would be written. A table is one string: rows divided by U+001E, fields
by U+001F, the items of a field that is a list by U+001D and their parts by
U+001C.

`scripts/build-alchem.py` puts the two modules into `alchem` and writes into
`AlchemGuide` the version (`--version`, `devel` without it) and the system
and machine of the programs the compiler makes.

## The check

`harness/commands.py` (the gate `commands`) holds eight scenes: 88 command
lines that only print, the six agents installed into a project that has
files of theirs already (one of alchem's own that differs, a shared file
with text, one with half a block), the marked block replaced, appended and
refused, and `docs` written, checked and written again. Each scene is a
directory, its command lines run one after another: `alchem`, built by the
compiler under test, gives the status, standard output and standard error
the pinned command gave for each of the 242, and leaves the same files.
`scripts/generate-command-cases.py PINNED` writes what the pinned command
gave (`harness/commands-cases.json.xz`). On Windows the job runs the scenes
of that file with both, `commands.py --against alchem-upstream.exe
alchem.exe`, as the pinned command prints a path with Windows' separators
there. The pinned command finds a package with the Go toolchain, which it is
given; `alchem` is given none.

## doc of a file, of the project and of its packages

`alchem doc file.alc` shows the documentation written in a file: its
module and `@moduledoc`, the types with their `@typedoc`, and the public
functions with their `@doc`, the clauses of one function together as the
pinned command joins them. A name that is not the library's is looked for
among the modules of the project in the current directory (its `.alc`
files, but for directories named with a dot, `node_modules` and `vendor`)
and of the packages those import, read from the package cache; so is a
library module a package can take the place of (`DiskStore`, `WebSocket`,
`Version`, `OptionParser`), and `--search` finds the project's modules and
functions too.

The file is not parsed as the compiler parses it
(`tools/alchem-sources.alc`): strings, comments and sigils are taken out,
the rest is cut into words and signs, and the declarations of the module
are read from those, each body passed over by counting what opens one
(`do`, and `fn` before an arrow) and what closes it (`end`). The functions
of a `defimpl` are named as the pinned command names them, `name$Protocol$N`
with N the number of functions before the implementation.

Checked against the pinned command: the 204 source files of this
repository it documents give the same text and the same JSON (not a gate:
they change); the gate holds 18 of them (`examples/kv`, three fixtures and a
benchmark) in the scene `files`, and in the scene `project` a project with
a sum type, a struct with a default, clauses that begin other forms, a
default value, a private function, a test file, a module named `Version`,
directories that are left out, and a package of three files in the cache.

## alx

`alchem alx` is the shell: it reads inputs, a line or a block at a time,
and runs each with the imports, the definitions and the statements before
it, as the pinned command does. The text of an input decides what it is
(`tools/alchem-alx.alc`):

- it goes on while a block or a bracket is open or a string is not closed
  (`do` that is no key, `fn` not followed by a parenthesis, `end`);
- an `import` and a definition (`def`, `struct`, `type`, ...) are checked
  by building a program with them and kept, and print `:ok`;
- a statement is run in a program of the statements so far, after a line
  that marks where its own output starts. A name bound is shown; a pattern
  is matched from a value kept under a name of the shell's, which is
  shown; any other statement is bound to such a name and shown when the
  program builds that way, and run as it is when it gives no value.

A program is written to a file of the current directory, so that its
imports are found from there, built by the compiler inside `alchem` and run
with no input. What a failing program says is shown without the frames of
the shell's module and with the lines of the input for those of the file.
`h Module.function` prints documentation as `doc` does, `:reset` forgets
what was entered, `:quit`, `exit` and the end of the input leave.

The gate's scene `alx` holds three sessions of 43 inputs: values, bindings
of names and of patterns, a definition and a struct over several lines, an
import, `h`, a division by zero and a `raise`, `:reset` and the three ways
out.

## The flags of build, run, check and new

`build`, `run`, `check` and `new` read their flags as the pinned command
reads them, from the usage it prints for each (`AlchemGuide.parsed`): `-h`
prints the usage and ends with status 0; a flag the command does not take, a
flag without its value, a value that is not a whole number or a duration
where one is due, and `-trace=maybe` print the pinned command's message and
the usage and end with status 2. `-target` is `GOOS/GOARCH` or refused as
there, and then must be what the compiler makes. A file that is not there is
reported as the pinned command reports it, as JSON under `-json`, and a file
with no `main` at all as `missing main/0`, by `run` as by `build`. The
gate's scene `flags` holds 44 such command lines, none of which builds a
program, and the project `new` writes.

`-o` and `-locked` do what they say. `-json`, `-race`, `-trace`, `-timeout`,
`-shutdown-timeout` and `-max-call-depth` are read and change nothing: a
program the compiler does not take is reported with its one message.

## A program the compiler refuses

The compiler refuses a program by making no image, with one message for
every reason. `build`, `run` and `check` first read the program as the
pinned compiler reads it (`AlchemCheck.load`, `tools/alchem-check.alc`):
the entry and the files it imports, in the pinned compiler's order, each
parsed as its `ParseModule` parses one and checked as it is then
(`tools/alchem-lower.alc`: constants, arities, clauses), then checked as
one program as the pinned loader checks it (an import missing, a private
function, the arity of another module's function, `main` in an imported
module, a protocol declared twice), and through the first of the pinned
checker's passes (a function without a return type, a name no function may
have, `main`'s form). What it finds is said as the pinned command says it,
place and message:

    /home/me/app/lib/lib.alc:4:3: unsupported syntax: expected ) "", found identifier "end"
    /home/me/app/main.alc:2:3: import "lib/lib.alc": /home/me/app/lib/lib.alc: read source: open /home/me/app/lib/lib.alc: no such file or directory

`check` does so for a program the compiler takes too, since it takes some
the pinned compiler refuses. A bundler's refusal is explained the same way.
The checks after these (names, arities of calls, types) are not here yet.

Where the front end finds nothing, `alchem` asks the compiler which
function it could not make
(`nc_explain`, in `implementations/alchem/native-compiler.alc`): the program
is compiled as before up to its functions, and those are compiled again one
by one, halves first, as `nc_build` compiles them, until one makes no code.
Its name, `Module.name/arity`, is found among the files of the bundle, and
`build`, `run`, `check` and `alx` say where it is:

    lib/lib.alc:4:3: E_COMPILE: the native compiler does not take something in Lib.twice/1

In `alx` a statement is the input itself (`something in this input`), and a
definition is named without the shell's module. A function of the library
is named as one; a refusal in no one function (the table of the program,
the code shared by its functions, its entry) keeps the one message. This
says where to look, not what is wrong: what is wrong is the front end's
part (issue #100). The bootstrap keeps the name `nc_explain` when it
renames the compiler's functions, as it keeps `nc_compile`.

## fmt

`alchem fmt PATH...` formats the `.alc` files named and those under the
directories named, leaving out `.git` and `artifacts` and following no
link, as the pinned command's `formatPaths` does: the files sorted, every
one formatted before any is written, so that one the parser refuses leaves
all of them as they were (`file:line:column: message`), and each file that
changes named and written in place, by way of a file beside it with its
mode. With `--check` nothing is written and a change is a failure,
`formatting changes required`. The text is `AlchemFormat.format`
(`tools/alchem-format.alc`), the pinned formatter function for function on
the tree of the front end (`spec/alchem-front-end.md`). The scene `fmt` of
the gate runs it over files formatted and not, a broken one, a file that
declares no module and directories with `.git` and `artifacts`.

## Not as the pinned command

- `version` is `alchem VERSION SYSTEM/MACHINE`, and the two as JSON. The
  pinned command also names the Go toolchain it builds with; no build of
  this one uses any.
- `doc` reads a file's declarations without checking the rest of it: a
  file the pinned compiler refuses is documented as far as its declarations
  go, where the pinned command prints the compiler's message, and a project
  file the pinned command leaves out because it does not compile is listed.
  A file that declares no module is refused in this command's own words.
- `build`, `run`, `check` and `alx` give the pinned message for a mistake
  in a program's syntax, constants, arities and clauses, for a file it
  cannot import, and for a mistake in a function's body as far as the
  checker's walk follows it (spec/alchem-front-end.md: an undefined name, a
  call of the wrong arity, a type: `** line 1: undefined function nope`).
  Where the walk stops before the mistake, they say where the refused
  function is, not what is wrong in it.
  `alx` reads no input with the front end. It decides what a statement
  binds from its text: a statement that binds after other statements in
  one input is run and not shown, and a comment alone runs nothing.
- `lsp` is the pinned command's language server
  (`tools/alchem-lsp.alc`, after `lsp/server.go` of the pinned tree), over
  standard input and output: initialize, shutdown and exit; a document
  opened, changed, saved and closed, each followed by its diagnostics;
  hover, definition, completion, formatting and the document's symbols.
  Its replies are the pinned server's byte for byte (`harness/lsp.py`: the
  pinned server's own tests and more, as recorded sessions). Not as the
  pinned server: a document's diagnostics are what the front end finds
  in it and in what it imports, with the open documents in place of
  their files (`spec/alchem-front-end.md`); the program is not compiled,
  so one only the compiler refuses has no diagnostic. And the modules a
  document imports are offered for completion in the order it imports
  them, where the pinned server offers them in no order.
