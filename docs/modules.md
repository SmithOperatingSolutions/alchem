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

## Lock file

A program that uses remote packages or `require` gets an `alchem.lock` beside its entry file. It records the content hash of each remote package and the Go checksum lines of every required module, including indirect ones. Commit it.

- A remote package whose fetched content differs from its locked hash fails with `module@version does not match alchem.lock`.
- The locked Go checksums are given to the Go toolchain before it resolves dependencies, so a changed module fails with Go's `checksum mismatch`.
- New entries are added, and entries no longer used are removed, whenever `check` or `build` runs. `check` only knows the Go checksums of a program it has to prepare a Go module for (one with `extern` declarations); otherwise it leaves them as they are.
- `--locked` on `check` or `build` writes nothing and fails if the lock lacks an entry the program needs. Use it in CI.

The lock pins content, not just versions, so it also protects packages from hosts outside the Go checksum database (`GONOSUMDB`, `GOPRIVATE`).
