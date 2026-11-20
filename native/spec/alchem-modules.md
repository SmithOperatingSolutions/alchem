# Modules and imports

The self-hosted compiler reads one source from standard input and opens no
files, which keeps `env -i PATH= alchem-compiler < source` a complete build.
Imports are therefore resolved before compilation by a bundler, and the compiler
accepts a bundle of several modules.

## Source rules (as the pinned language)

- `import "path.alc"` inside a module names another file, relative to the
  importing file. It may appear anywhere among the module's functions.
- An imported module's public functions are called with its name:
  `Math.double(3)`. Unqualified names resolve only inside the calling module, so
  the same function name may exist in several modules.
- A module may call only modules it imports directly; imports are not
  transitive. A module may also qualify calls to itself (`App.f(1)`).
- `defp` functions are private to their module.
- Imported modules cannot define `main`; a program has exactly one.
- Import cycles and duplicate module names are errors. Importing a file twice,
  or along several paths, includes it once.
- No file, the entry or an imported one, may be over 1 MiB (1,048,576 bytes):
  `PATH: read source: source exceeds 1048576 bytes`, as the pinned compiler
  reports it. The limit is per file; a program of several files may be larger.
- Module names cannot be library namespaces: the pinned ReservedModule list
  (IO, List, Map, String, Integer, File, System, Enum, Path, Base, JSON, ...).

## Bundle format

The bundler is itself an Alchem program, `tools/alchem-bundle.alc`, which the
standard build compiles with the self-hosted compiler to
`build/native/alchem-bundle`; `scripts/bundle-alchem.py` is the Python reference
it is checked against, byte for byte. The Alchem bundler compares paths after
lexical cleaning ("." and ".." removed) and does not resolve symbolic links;
errors go to standard error with status 1, a usage error has status 2.

`alchem-bundle ENTRY.alc` writes every module once: the entry first, then every other module after the modules it imports (the order the pinned compiler writes their code in, which the lines of a cover file follow: `alchem-failures.md`). Every file
keeps its lines, so a line number in the bundle's file is the line in the
source: an import line becomes an empty line, and the module's direct imports
follow `do` on the header's own line as `import "module:Name"`. The bundle
starts with a manifest in comment lines, `#alchem-bundle N` and then one line
`# length path` per file in order: the file's length in the bundle and its
absolute path (the working directory joined with the path given, cleaned
without following links). A failing program names its file and line from it
(`spec/alchem-traces.md`). A path with a line break is refused.

```alchem
#alchem-bundle 2
# 96 /work/app.alc
# 71 /work/math.alc
defmodule App do import "module:Math"

  def main() do
    System.halt(Math.double(21))
  end
end
defmodule Math do
  def double(n: integer): integer do
    n * 2
  end
end
```

The compiler accepts `import` only in that position and form; a raw file import
that was not bundled is rejected. An import naming a module that is absent from
the bundle is harmless unless it is called. The bundler reports missing files,
cycles, duplicate module names, imported modules that define main and files
over 1 MiB; packages
(`host/owner/repo@version/...`) are not supported.

## Compiler representation

Table records are 27 bytes: five u24 source positions, argc, flags, eight
bytes (for a function: where its result type is written, the number of its
default arguments and where its guard starts) and the u16 index of the owning
module's header. A further clause of a function has a record of its own with
flags 40, which no lookup finds and which has no code (alchem-clauses.md). Each
module contributes a header record (flags 32) holding its name span, the start
of its import lines and the number of user functions declared before it. A
header occupies a function-table slot but emits no code. Name lookup takes the
owning module; `Module.function` finds the header by name, checks that the
caller is that module or imports it, and rejects another module's `defp`.

Limits: 65,535 user functions across all modules and 65,536 table records in
all, where every module header, struct, sum type, exception and further clause
of a function is a record too: one module may hold 65,535 functions, 64
modules 65,472 between them. A record is named by a 16-bit number in an environment (its function) and
in a record (its module), which is what bounds the table; a call site holds
the 32-bit address of its slot, and the lengths of a program's functions are
kept behind a 32-bit count (`nc_build`). Shared runtimes take slots beyond the
records, so they do not reduce the function limit.

Table building runs sixteen steps per level over four levels, so module and
function counts do not deepen recursion, and no step copies the table: a step
carries a window, the records since the module's header or since the first
clause of the function declared last, which is all that the place of the next
record depends on (`nj_place`: whether it is a further clause, another form or
a new function), and each level joins the records its steps made. What needs
every record is checked once the table is whole (`nc_table_valid`): a module
name is declared once, a struct or sum type once in its module and not under a
library module's name, and two functions of one name in a module take
different numbers of arguments. The outcome is the one the checks had when
they ran as each record was added.

A finished table carries a name index after its records: one record of zeros
(a read one record past the end still gives zeros), the number of every
record as a u32 in the order of name bytes, then module, then record number
(`nc_order`; built by a merge sort, `nc_sorted`), and up to 26 bytes that make
the size one more than a multiple of 27, which is how `nc_records` and
`nc_indexed` tell it from records alone. `nj_scan` (a function by name and
module from a record on), `nc_find`, `nd_find` and `ny_module` search it in
logarithmic time; on records alone (the window) they scan as before. Of
several functions of one name `nc_find` still returns the one the old scan
came to first (`nc_find_among`). A library type with a dotted or lowercase
name (`File.Stat`, `file`: `alchem-system.md`) is indexed under its whole
name and found as before by `nh_find`; a step of the table building keeps the
record of the module's header beside the window, which is what says whether
such a name may be declared there (`nh_declare`).

Measured with the self-built compiler (functions `def fN(x: integer): integer
do fM(x + 1) end` in chains of fifty; `source-capacity.md`, "Time", has the
method and more rows). The middle column from 8,000 functions on is the
compiler of 1374085 with only its limits raised: it copied the table for
each declaration and searched all of it for each declaration and each call.

| Functions | Source bytes | Table copied and searched whole | Now |
| --- | --- | --- | --- |
| 4,000 | 208,949 | 5.8 s, 325 MB | 0.65 s, 139 MB |
| 8,000 | 420,069 | 15.8 s, 1,090 MB | 1.2 s, 282 MB |
| 16,000 | 854,187 | 83 s, 3,927 MB | 2.4 s, 576 MB |
| 60,000 | 3,263,627 | not run: the rows above put it past the 12 GB the measurements were allowed | 10.7 s, 2,217 MB |
| 65,535 | 3,566,720 | | 12.6 s, 2,918 MB |

What is left grows with the number of functions and not its square: about
0.18 ms and 37 KB of arena for each small function (the compiler never
frees, and every word it tests a token against is a byte string made for
the test).

`harness/modules.py` checks bundled projects, the visibility rules, bundler
errors, invalid bundles, a 200-module call chain, 300 modules and 65472/65473
functions across 64 modules (65536 and 65537 table records). Project outcomes were confirmed against the pinned
upstream `alchem run` on the unbundled files.

Imported structs and sum types are written `Module.Name` (see
alchem-records.md), and `&Module.function` references work (alchem-closures.md).
Not yet supported: package imports.

## Packages

A package is a tagged repository of `.alc` files, imported as the pinned
compiler writes it: `import "host/owner/repo@v1.2.0/lib/math.alc"` names the
repository, an exact tag and a file inside it. The bundlers follow the pinned
compiler's rules:

- The import must have that shape, with no `..` or `//` in the file part:
  `remote imports are written "module/path@v1.2.3/file.alc"`.
- A program uses one version of a package: `conflicting versions of ...`.
- Files of a package import each other with relative paths, which cannot
  leave the package: `import "..." leaves the package`.
- Imports of a file are followed in the order of their text.
- `alchem.lock` beside the entry file records `package path version hash`
  for each package, sorted, under the pinned compiler's header, and keeps the
  `module` lines it finds. A hash that differs from the recorded one is an
  error. `--locked` writes nothing and fails when an entry is missing.
- An entry written as a package file, `alchem-bundle
  host/owner/repo@v1.2.0/tools/dev.alc`, runs a program the package carries;
  it keeps no lock file.

A package is read from the Go module cache, where `go mod download
host/owner/repo@v1.2.0` puts it: `GOMODCACHE`, else `pkg/mod` under the first
`GOPATH` entry, else `~/go/pkg/mod`, in the directory
`host/owner/repo@v1.2.0` with every upper-case letter written as `!` and its
lower-case form. The hash is the cache's `.ziphash` for that version. The
bundlers do not download: fetching verifies the archive against Go's checksum
database over TLS, which a program built by this compiler cannot do, so a
missing package is the error `fetch ...: not in the module cache ...; run go
mod download ...`.

The compiler skips what a package's files carry besides code: `@moduledoc`,
`@doc` and other attributes with their string or heredoc value, and
`require "name" "version"` lines. `extern` functions bind Go code and are not
supported.

`harness/packages.py` checks a program over a package in a module cache: the
bundle from both bundlers, the lock file, `--locked`, a program run from a
package and seven errors. The same files were run through the pinned compiler
with a local module proxy: the output, the failure trace into the package
file, the lock file and every error agree.

