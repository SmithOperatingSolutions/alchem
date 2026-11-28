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
- No file, the entry or an imported one, may be longer than a program may
  be, 16,776,191 bytes (`nc_limit`, `source-capacity.md`):
  `PATH: read source: source exceeds 16776191 bytes`. The pinned compiler
  reads no file over 1 MiB (`source exceeds 1048576 bytes`), though it
  builds a program of several such files: this is a deliberate difference,
  in the bundlers, `alchem check`, `alchem fmt` and the parser of
  `tools/alchem-parse.alc`.
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
longer than a program may be; packages
(`host/owner/repo@version/...`) are not supported.

## Compiler representation

Table records are 40 bytes: five u32 source positions, argc, flags, ten
bytes (for a function: the u32 of where its result type is written, the
number of its default arguments, the u32 of where its guard starts and the
high byte of argc), the u32 index of the owning module's header and four
bytes of zero. The record has room for positions and numbers of four bytes,
though a position is still at most 24 bits and a record's number three
bytes where the compiler's parts hand it on (`source-capacity.md`). The
first record also keeps two things of the whole table where a header has
no use for them: how the program is compiled (byte 20: 1 untraced, 2 and 3
counting coverage) and the call a default value is compiled for (the u32
at 27). A further clause of a function has a record of its own with
flags 40, which no lookup finds and which has no code (alchem-clauses.md). Each
module contributes a header record (flags 32) holding its name span, the start
of its import lines and the number of user functions declared before it. A
header occupies a function-table slot but emits no code. Name lookup takes the
owning module; `Module.function` finds the header by name, checks that the
caller is that module or imports it, and rejects another module's `defp`.

Limits: 16,777,214 user functions across all modules and 16,777,215 table
records in all (`source-capacity.md`), where every module header, struct, sum type, exception and
further clause of a function is a record too. A record is named by a number
of three bytes in an environment (its function) and in a record (its
module), which is what bounds the table (two bytes, and 65,535 functions,
until `source-capacity.md`, "Limits that remain"); a call site holds
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
functions across 64 modules (65536 and 65537 table records, both of which run). Project outcomes were confirmed against the pinned
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

A package is read from alchem's package cache, else from the Go module
cache, where Go may have put it. alchem's cache is `ALCHEM_CACHE`, else
`alchem` in the user's cache directory (`$XDG_CACHE_HOME` or `~/.cache` on
Linux, `~/Library/Caches` on macOS, `%LocalAppData%` on Windows): a package is
`packages/host/owner/repo@v1.2.0/files`, beside `h1`, its hash. The Go module
cache is `GOMODCACHE`, else `pkg/mod` under the first `GOPATH` entry, else
`~/go/pkg/mod`, with the hash in the cache's `.ziphash`. Paths and versions
are written with every upper-case letter as `!` and its lower-case form.

The bundlers read the caches and do not download: a package in neither is
`fetch ...: not in the package cache`. `alchem` then fetches it
(`tools/alchem-fetch.alc`) and bundles again, as the pinned compiler's
`go mod download` does, without Go:

- **Proxies.** `GOPROXY` (default `https://proxy.golang.org,direct`) is read
  as Go reads it, from the environment, else from the file `go env -w`
  writes (`$GOENV`, else `go/env` in the user's configuration directory). A
  proxy is asked for `@v/VERSION.info` and then `.zip`, over HTTPS, HTTP or
  from files (`file://`). A proxy that lacks the version (404, 410) passes to
  the next after `,`; one that fails in any way passes to the next after
  `|`. `off` refuses: `module lookup disabled by GOPROXY=off`.
- **Private packages.** A path that `GONOPROXY` (default `GOPRIVATE` with
  `ALCHEM_PRIVATE`) matches, or a `direct` entry reached, is fetched with git
  from its own repository, as the go command fetches it in direct mode, and
  nothing about it is asked of a proxy. The repository is the path's first
  three elements on github.com and bitbucket.org, the path up to an element
  ending in `.git`, or what the host announces at `https://PATH?go-get=1`
  (`<meta name="go-import" content="prefix git address">`). git (with
  `GIT_TERMINAL_PROMPT=0`, so that it asks for nothing) lists the
  repository's references, fetches the version's tag (`dir/vX.Y.Z` for a
  module in a directory), and `git archive` gives its files (with
  `core.autocrlf=input` and `core.eol=lf`). The module's directory is found
  from the go.mod files as `codeRepo.findDir` finds it, `/vN` directories
  included. Its files are kept as `zip.Create` keeps them: files of nested
  modules, of vendored packages (by the root go.mod's `go` version),
  symbolic links and `.hg_archival.txt` are left out, and the repository's
  `LICENSE` is added to a module in a directory without one. The hashes are
  the ones go mod download gives (`harness/fetch.py` holds three).
- **The archive.** As `zip.CheckZip` checks a proxy's: every file's name
  begins with `path@version/` and is a file path (`module.CheckFilePath`);
  go.mod is only at the top and in lower case; no two names differ only in
  case; each file's CRC is right; the files come to at most 500 MB. The hash is Go's: `h1:` and the
  base64 SHA-256 of one line per file, in the order of their names, of the
  file's hex SHA-256, two spaces and its name.
- **The checksum database.** Unless `GONOSUMDB` (default `GOPRIVATE` with
  `ALCHEM_PRIVATE`) matches the path or `GOSUMDB` is `off`, the database
  `GOSUMDB` names (`sum.golang.org` and its key by default; a verifier key
  and an address otherwise) is asked for the package's record. The record's
  tree is a note signed with the database's Ed25519 key, and the record is
  proved to be in that tree from the database's tiles (RFC 6962 hashes,
  tiles of height 8). A hash that differs from the record's is the pinned
  compiler's `checksum mismatch` with its `SECURITY ERROR`. As Go does, the
  latest tree a database showed is kept (`sumdb/NAME/latest` in alchem's
  cache, a signed note, replaced by a larger one), and each tree is checked
  against it: the smaller tree's hash, computed from the larger tree's
  tiles, which are checked against the larger tree's hash, must be the
  smaller tree's. A tree that is not on the latest one's timeline is the
  database showing different trees to different people: `SECURITY ERROR`,
  `go.sum database server misbehavior detected!`, with both notes.
- **The cache.** The files and the hash are written to a directory of their
  own and renamed into place, so a build at the same time sees the whole
  package or none of it; a package that fails a check is not kept.
- A failure that looks like a private package asked of the public proxy or
  database gets the pinned compiler's hint to set `ALCHEM_PRIVATE`.

The project's lock is checked after the package is loaded, as the pinned
compiler checks it: a recorded hash that differs is `... does not match
alchem.lock`.

The compiler skips what a package's files carry besides code: `@moduledoc`,
`@doc` and other attributes with their string or heredoc value, and
`require "name" "version"` lines. `extern` functions bind Go code and are not
supported.

`harness/packages.py` checks a program over a package in a module cache and
in alchem's cache: the bundle from both bundlers, the lock file, `--locked`, a
program run from a package and seven errors. `harness/fetch.py` checks the
fetching, offline, against a module proxy and a checksum database it serves
itself. The same files were run through the pinned compiler
with a local module proxy: the output, the failure trace into the package
file, the lock file and every error agree.

