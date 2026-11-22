# The commands that print documentation

`alchem` (`tools/alchem.alc`, `spec/alchem-testing-gen.md`) has the pinned
command line's commands that describe the language, the library and the
command itself. They are the module `AlchemGuide`, `tools/alchem-guide.alc`:

    alchem help | -h | --help
    alchem version [--json]
    alchem syntax [--all] [--group name] [--json] [topic]
    alchem doc [--all] [--group name] [--search text] [--json] [Module | Module.function]
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

`harness/commands.py` (the gate `commands`) holds four scenes: 88 command
lines that only print, the six agents installed into a project that has
files of theirs already (one of alchem's own that differs, a shared file
with text, one with half a block), the marked block replaced, appended and
refused, and `docs` written, checked and written again. Each scene is a
directory, its command lines run one after another: `alchem`, built by the
compiler under test, gives the status, standard output and standard error
the pinned command gave for each of the 120, and leaves the same files.
`scripts/generate-command-cases.py PINNED` writes what the pinned command
gave (`harness/commands-cases.json.xz`). On Windows the job runs the scenes
with both, `commands.py --against alchem-upstream.exe alchem.exe`, as the
pinned command prints a path with Windows' separators there.

## Not as the pinned command

- `version` is `alchem VERSION SYSTEM/MACHINE`, and the two as JSON. The
  pinned command also names the Go toolchain it builds with; no build of
  this one uses any.
- `doc` reads the library alone. The documentation written in a file
  (`alchem doc file.alc`), in a module of the project in the current
  directory and in a package it imports is not read yet: a name ending in
  `.alc` is refused with status 2, and `--search` finds nothing of the
  project's.
- `alx`, `lsp` and `fmt` are in the list of commands and not in `alchem`
  yet: each says so and ends with status 2.
