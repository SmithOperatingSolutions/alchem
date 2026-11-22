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

`harness/commands.py` (the gate `commands`) holds seven scenes: 88 command
lines that only print, the six agents installed into a project that has
files of theirs already (one of alchem's own that differs, a shared file
with text, one with half a block), the marked block replaced, appended and
refused, and `docs` written, checked and written again. Each scene is a
directory, its command lines run one after another: `alchem`, built by the
compiler under test, gives the status, standard output and standard error
the pinned command gave for each of the 201, and leaves the same files.
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

## Not as the pinned command

- `version` is `alchem VERSION SYSTEM/MACHINE`, and the two as JSON. The
  pinned command also names the Go toolchain it builds with; no build of
  this one uses any.
- `doc` reads a file's declarations without checking the rest of it: a
  file the pinned compiler refuses is documented as far as its declarations
  go, where the pinned command prints the compiler's message, and a project
  file the pinned command leaves out because it does not compile is listed.
  A file that declares no module is refused in this command's own words.
- `doc host/owner/repo@v1.2.3/lib/name.alc`, a package's file named as an
  import names it, is not fetched.
- `alx`, `lsp` and `fmt` are in the list of commands and not in `alchem`
  yet: each says so and ends with status 2.
