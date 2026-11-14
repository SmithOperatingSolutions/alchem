# Multi-file modules

An executable starts at one `.alc` entry file or a directory containing `main.alc`. Each file defines one module. The entry module supplies the only `main/0`; imported files contain typed functions and may not define `main`.

```elixir
defmodule Application do
  import "math.alc"
  def main() do
    value = Math.double(3)
    assert(value == 6)
  end
end
```

The example import must declare `defmodule Math` in `math.alc`; filenames do not rename modules. Imports may stand anywhere among a module's declarations, usually after `@moduledoc`, and resolve relative to the importing file, including `../` paths. Imports are not transitive: a file names every module it uses. Imports introduce a module namespace, not unqualified function names. Qualified calls and `&Module.function` references require a direct import; transitively loaded modules are not implicitly visible. Functions in the same module may use unqualified calls/references and forward or recursive calls. Functions declared with `def` are public; `defp` functions are private to their module.

Loading canonicalizes absolute paths, sorts dependency visits, loads shared dependencies once, and rejects missing/invalid files, import cycles, duplicate module names, duplicate functions and imported entry points. Builtin module names `IO`, `List`, `Map`, `String`, `Integer`, `Float`, `File`, `System`, `Time`, `Process`, `Supervisor` and `Server` are reserved, for modules and for type names. The entire reachable graph is type-checked before a Go build or executable publication. Semantic errors identify the defining file; import errors retain the import chain. Unreachable files outside the graph are not compiled.

Each function keeps its source file for runtime errors and frames. The backend emits one temporary Go module with compiler-owned identifiers, preserving namespace separation. Runtime sources are embedded in the compiler and copied into that temporary project: building an Alchem project does not download an Alchem runtime dependency. Output is staged beside its destination and replaced only after successful compilation.

Run `alchem check examples/system`, `alchem build -o system examples/system`, then `./system` (`system.exe` on Windows). The example imports a typed actor worker and uses supervision, immutable messages and orderly shutdown.

## Module contents

After its imports a module may declare, in any order, `require` lines and `extern` functions (see [Go interop](interop.md)), `struct` and `type` declarations, and functions. Types declared in a module are named `Module.Type` from other modules that import it directly. A `defp` function, including every clause of it, can be called and referenced only inside its own module; a qualified call from elsewhere is the compile error `Module.name is private to its module`. All types are public.

## Remote packages

An import may name a file inside a versioned package instead of a relative path:

```elixir
import "github.com/example/mathlib@v1.2.0/lib/math.alc"
```

The text before `@` is the package path, the version is an exact tag, and the rest is the file inside the package. Packages are fetched with the Go module system (`go mod download`), so they come from the configured `GOPROXY`, are verified against the Go checksum database, are cached in the Go module cache, and honour `GOPRIVATE` and related settings for private hosts. A package needs no `go.mod`.

Files inside a package import each other with ordinary relative paths, which may not leave the package directory, and may bind `extern` functions to Go packages inside the package. One program may use only one version of a package; two different versions are the compile error `conflicting versions`. `alchem check` and `alchem build` contact the network only when a program has remote imports or `require` lines whose modules are not already cached.

### Private repositories

Set `ALCHEM_PRIVATE` to comma-separated patterns naming private hosts or owners:

```sh
export ALCHEM_PRIVATE='github.com/owner/*,git.example.com'
```

A matching package is fetched with git from its own host, using the credentials git already has, and nothing about it (its name included) is sent to the public Go proxy or checksum database. The patterns are added to Go's `GOPRIVATE`, which works as well when it is already set. Without either, a private package fails at the checksum lookup, and the error says which pattern to set.

### Documentation and programs of a package

The commands that take a file take a package path too, written as an import writes it:

```sh
alchem doc github.com/example/mathlib@v1.2.0/lib/math.alc
alchem run github.com/example/mathlib@v1.2.0/tools/table.alc -- 12
alchem build github.com/example/mathlib@v1.2.0/tools/table.alc
alchem check github.com/example/mathlib@v1.2.0/lib/math.alc
```

`doc` shows the file's `@moduledoc`, `@doc` and `@typedoc` text. `run`, `build` and `check` treat the file as the entry: its imports stay inside its package, the executable `build` makes goes in the current directory, and no lock file is kept, since the version asked for fixes the content.

Inside a project, `alchem doc Math`, `alchem doc Math.double` and `alchem doc --search text` also cover the project's own `.alc` files and the packages they import, each result naming the file it came from. A package is read from the module cache only, so it appears once a `check`, `build` or `run` has fetched it; looking something up never contacts the network.

### The release a package needs

```elixir
require "alchem" "v0.4.0"
```

In any module, this names the oldest Alchem release the file works with. An older compiler stops with `this file needs Alchem v0.4.0 or newer, and this is v0.3.9: upgrade alchem to build it` at that line. A compiler built from source has no release number and accepts every requirement. The line adds nothing to the build and nothing to the lock file. Releases before v0.3.8 do not know it.

### Library modules that are moving to packages

The library keeps what a package could not build for itself: the language's own types, processes, files, the network, JSON and the like. Modules that need none of that are moving to [alchem-packages](https://github.com/SmithOperatingSolutions/alchem-packages), where they are released on their own schedule:

| Builtin, until v0.4.0 | Package file | Module |
| --- | --- | --- |
| `DiskStore` | `disk_store/disk_store.alc` | `DiskStore`, same functions; the type is `DiskStore.Store` |
| `Crypto.hash_password`, `Crypto.verify_password` | `password/password.alc` | `Password.hash`, `Password.verify` |

A builtin module's name is otherwise reserved, but a program may import a module named `DiskStore`: its calls then reach that module, and a program without one keeps using the builtin. So a program moves by adding the import, and by writing `DiskStore.Store` where it wrote the type `disk_store`.

A module may name its functions `put`, `get`, `has_key`, `length`, `map`, `filter`, `reduce`, `prepend` and `concat`, which bare calls otherwise give to the oldest builtins. Inside such a module a bare call means its own function, and the builtin is written `Map.put`, `Enum.map` and so on.

## Lock file

A program that uses remote packages or `require` gets an `alchem.lock` beside its entry file. It records the content hash of each remote package and the Go checksum lines of every required module, including indirect ones. Commit it.

- A remote package whose fetched content differs from its locked hash fails with `module@version does not match alchem.lock`.
- The locked Go checksums are given to the Go toolchain before it resolves dependencies, so a changed module fails with Go's `checksum mismatch`.
- New entries are added, and entries no longer used are removed, whenever `check` or `build` runs. `check` only knows the Go checksums of a program it has to prepare a Go module for (one with `extern` declarations); otherwise it leaves them as they are.
- `--locked` on `check` or `build` writes nothing and fails if the lock lacks an entry the program needs. Use it in CI.

The lock pins content, not just versions, so it also protects packages from hosts outside the Go checksum database (`GONOSUMDB`, `GOPRIVATE`).
