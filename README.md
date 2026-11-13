# Alchem

**An experimental Elixir-inspired language compiled to native executables through Go.**

Alchem explores expressive functional syntax, message-passing concurrency and OTP-inspired supervision while leveraging Go's compiler and goroutine runtime. It is not Elixir or a BEAM implementation.

**Status:** Experimental working compiler. Supports typed functions and closures, collections, immutable bindings, arithmetic/booleans, conditionals and guarded pattern matching, list operations and maps, pipes, output, assertions, multi-file modules, typed processes with bounded mailboxes, supervision trees, pin patterns, `List`/`Map`/`String` operations, integer conversion, a clock, and formatting/diagnostic tooling. See [benchmarks](docs/benchmarks.md) for measurements against Go.

## Install

On macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/SmithOperatingSolutions/alchem/main/install.sh | sh
```

On Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/SmithOperatingSolutions/alchem/main/install.ps1 | iex
```

The scripts install the latest release, after checking it against the release's checksums, into `~/.local/bin` or `%LOCALAPPDATA%\Programs\alchem`; `ALCHEM_VERSION` and `ALCHEM_INSTALL_DIR` choose another release or place.

With Homebrew, this repository is a tap:

```bash
brew tap smithoperatingsolutions/alchem https://github.com/SmithOperatingSolutions/alchem
brew install alchem
```

With Scoop:

```powershell
scoop install https://raw.githubusercontent.com/SmithOperatingSolutions/alchem/main/bucket/alchem.json
```

Or download the archive for your platform from [Releases](https://github.com/SmithOperatingSolutions/alchem/releases), unpack it, and put `alchem` on your `PATH`. With Go installed you can instead run `go install github.com/SmithOperatingSolutions/alchem/cmd/alchem@latest`.

Alchem compiles through Go, but you do not need to install Go: when no `go` command is on `PATH`, the first build downloads the pinned Go release into the user cache, checks its SHA-256 and uses it from then on. `alchem version` shows which Go builds use; see [toolchain](docs/tooling.md#the-go-toolchain).

## Hello World

```elixir
defmodule Hello do
  def main() do
    IO.puts("Hello from Alchem!")
  end
end
```

Run `alchem build examples/hello.alc` (from a checkout, `go run ./cmd/alchem build examples/hello.alc`), then execute `./hello` (Windows: `hello.exe`). Run fixtures with `go run ./cmd/alchem test tests/fixtures`.

## Expressions and functions

```elixir
defmodule Example do
  def double(value: integer): integer do
    return value * 2
  end
  def main() do
    count = double(2 + 3)
    ready = count > 0 and not false
    if ready do
      assert(count == 10)
      IO.puts("ready")
    end
  end
end
```

Arithmetic uses checked signed 64-bit integers. Overflow and division by zero fail at runtime. Go toolchain builds have a two-minute default deadline; library callers can use `compiler.BuildToContext` for custom cancellation. See the language specification for precedence, scopes, explicit return types and limitations.

## Collections and patterns

```elixir
defmodule Data do
  def total(xs: list[integer]): integer do
    case xs do
      [] -> return 0
      [head | tail] -> return head + total(tail)
    end
  end
  def main() do
    {label,items} = {"ready",[1,2,3]}
    assert(items |> total() == 6)
    assert(items[0] == 1)
    label |> IO.puts()
  end
end
```

Build the example with `go run ./cmd/alchem build examples/collections.alc`, then run `./collections`. Lists are homogeneous; tuples have fixed typed positions. Equality compares nested collections structurally. Known runtime failures report Alchem source locations, for example `program.alc:12:8: list index out of bounds`.

## Collection operations and maps

`map`, `filter` and `reduce` accept typed function references such as `&double`. `prepend`, `concat` and map `put` return new values without mutating their inputs. Maps use `%{"key" => value}` and `map[K,V]` types; `case` arms can add `when` guards.

Try `go run ./cmd/alchem build examples/operations.alc`, then run `./operations`. The example combines a map/filter/reduce pipeline with an immutable map update and guarded matching. See the specification for callback signatures, map lookup behavior and allocation costs.

## Inline callbacks

```elixir
factor = 3
values = [1,2] |> map(fn(n: integer): integer do
  return n*factor
end)
assert(values == [3,6])
```

Anonymous functions capture existing immutable bindings and can be returned or stored as values. Try `go run ./cmd/alchem build examples/closures.alc`, then run `./closures`.

## Map snapshots

`Map.keys`, `Map.values` and `Map.entries` return lists sorted by key, so maps can feed existing collection pipelines reproducibly. `Map.delete` returns a new map and preserves the original.

Try `go run ./cmd/alchem build examples/map_traversal.alc`, then run `./map_traversal`.

## Clauses, types and generics

```elixir
defmodule Bank do
  struct Account do
    owner: string
    balance: integer
  end

  type Command do
    deposit(amount: integer)
    withdraw(amount: integer)
  end

  def run(account: Account, Command.deposit(amount): Command): result[Account, string] do
    ok(%Account{account | balance: account.balance + amount})
  end
  def run(account, Command.withdraw(amount)) when amount > account.balance do
    error("insufficient funds")
  end
  def run(account, Command.withdraw(amount)) do
    ok(%Account{account | balance: account.balance - amount})
  end

  def main() do
    account = %Account{owner: "ada", balance: 10}
    case run(account, Command.withdraw(50)) do
      ok(updated) -> IO.puts("balance #{updated.balance}")
      error(reason) -> IO.puts("#{account.owner}: #{reason}")
    end
  end
end
```

The last expression of a body is its value. Functions can be written as pattern-matching clauses with guards, checked for exhaustiveness. Structs, sum types, `option`/`result`, floats, string interpolation and generic functions and types (`def fold(xs: list[a], acc: b, f: fn[b, a, b]): b`) are covered in the [language specification](docs/language-spec.md).

## Go interop and standard library

```elixir
require "github.com/google/uuid" "v1.6.0"
extern new_id(): string = "github.com/google/uuid.NewString"
extern read_file(path: string): result[string, string] = "os.ReadFile"
```

`extern` binds an Alchem function to a Go function from the standard library, a required module or a Go package inside the project; see [Go interop](docs/interop.md). Strings, numbers, files, environment, time and the typed request/reply `Server` are in the [standard library](docs/stdlib.md). Modules can keep functions private with `defp` and import versioned remote packages; see [modules](docs/modules.md).

## Enum, Stream and tests

```elixir
File.stream!("access.log")
|> Stream.map(&String.trim(&1))
|> Stream.reject(&(&1 == ""))
|> Stream.chunk_every(1000)
|> Enum.each(fn batch -> IO.puts("#{Enum.count(batch)} lines") end)

totals = orders |> Enum.group_by(& &1.customer, & &1.total) |> Enum.map(fn {name, amounts} -> {name, Enum.sum(amounts)} end)
```

`Enum` works on lists, maps, sets, ranges and streams; `Stream` is lazy, so the file above is read a thousand lines at a time. Anonymous functions and `&` captures take their types from where they are used. The library also has `Map`, `MapSet`, `String`, `Regex`, `Task`, `Agent`, `JSON` and more: see the [standard library](docs/stdlib.md), the generated [reference](docs/library-reference.md) and the [Elixir parity](docs/elixir-parity.md) notes.

The language also has `try`/`rescue`, `with`, `for` comprehensions, sigils such as `~r/\d+/` and `~D[2026-01-05]`, dates and times, and `#` comments.

Tests are `test "..." do ... end` blocks in `*_test.alc` files, with nested `describe`, `setup` blocks that pass a typed context, tags, doctests, repeatable seeds and line coverage: `alchem test --cover examples/testing`. See [testing Alchem programs](docs/unit-testing.md).

## Built-in documentation

The compiler documents itself: `alchem syntax <topic>` explains a construct with a working example, `alchem doc <Module>` and `alchem doc <Module.function>` show library functions with examples, and `alchem doc file.alc` prints a file's own `@moduledoc` and `@doc` text. `alchem agent-guide` is the overview for coding agents, and `alchem agent-install <agent>` installs a short instruction file pointing an agent at it. The reference pages under `docs/` ([library](docs/library-reference.md), [syntax](docs/syntax-reference.md), [commands](docs/cli-reference.md)) are written by `alchem docs` from the same source, and every example in them is run by the tests. See [developer tooling](docs/tooling.md).

## Multi-file supervised programs

`examples/system` imports a typed echo worker, sends immutable messages through a bounded mailbox, and shuts down its supervisor tree:

```sh
go run ./cmd/alchem check examples/system
go run ./cmd/alchem fmt --check examples/system
go run ./cmd/alchem build -o system examples/system
./system
```

See [modules](docs/modules.md), [processes and fault tolerance](docs/runtime.md), and [developer tooling](docs/tooling.md) for complete APIs and explicit ownership/lifecycle contracts. The CLI supports output/target selection, build/shutdown deadlines, structured diagnostics, tracing, and race-enabled builds. Go goroutines share an address space; cancellation is cooperative and does not imply BEAM isolation.

## Architecture

`.alc` source → lexer → parser → AST → semantic analysis → Go code generation → Go compiler → native executable.

The compiler (`compiler`) and process runtime (`compiler/actor`) are separate packages; the runtime source is embedded and copied into each generated build. Native builds use the Go toolchain, and CI cross-compiles six targets with CGO disabled.

## Roadmap

All six original milestones are complete:

1. **M1: Hello World:** Go CLI, lexer, parser, semantic checks, codegen, build, end-to-end tests.
2. **M2: Language:** modules, functions, immutable bindings, pipes, pattern matching, collections and diagnostics.
3. **M3: Concurrency:** goroutine-backed processes, process IDs, independent mailboxes, spawn/send/receive, ownership semantics.
4. **M4: Fault tolerance:** actors, supervision, monitors, links, restart policies and graceful shutdown.
5. **M5: Cross-platform:** Windows, Linux and macOS on AMD64 and ARM64, each built and run natively in CI.
6. **M6: Benchmarks:** process creation, throughput, memory, startup, binary size and restart latency compared with equivalent Go and Elixir programs.

Since then: constant-time `prepend`, maps with logarithmic updates, string operations, a clock and program input (arguments, standard input and reading files). Planned next: richer output and faster map updates. See the [roadmap](docs/roadmap.md) for the list and [benchmarks](docs/benchmarks.md) for current measurements.

## Platform validation

CI runs native tests and a CLI smoke test on Linux, Windows and macOS, plus cross-builds for AMD64/ARM64 across all three operating systems. Cross-built artifacts are compilation evidence; native runtime coverage is limited to the runner architectures shown in job logs. See [testing](docs/testing.md) for the matrix, Go versions and current limitations.

## Engineering rules

Define behavior and acceptance criteria; write failing tests first; implement the smallest change; run unit, integration and regression tests; review correctness, security and performance before committing. Document limitations and avoid claiming BEAM-equivalent isolation: Go goroutines share an address space and cannot recover from all fatal runtime failures.

See [architecture](docs/architecture.md), [language specification](docs/language-spec.md), and [roadmap](docs/roadmap.md).

## License

Alchem is licensed under the [Apache License, Version 2.0](LICENSE). It is inspired by Elixir but is not affiliated with it; see [provenance](docs/provenance.md).

See [contributing](CONTRIBUTING.md) to help, and [security](SECURITY.md) to report a vulnerability.
