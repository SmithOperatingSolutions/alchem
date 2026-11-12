# Developer commands and build options

Flags precede entry paths. `alchem <command> --help` describes that command.

```sh
alchem check examples/system
alchem check --json examples/system
alchem fmt --check examples/system
alchem fmt examples/system
alchem build -o system examples/system
alchem build --target windows/arm64 -o system.exe examples/system
alchem build --timeout 60s --shutdown-timeout 5s --trace=false examples/system
alchem build --race -o system-race examples/system
alchem test --timeout 10s tests/fixtures
```

## Help built into the command

The compiler documents itself from the same tables it compiles with, so help cannot describe something the installed compiler lacks:

```sh
alchem agent-guide                 # overview: commands, syntax topics, library modules
alchem syntax                      # list syntax topics
alchem syntax with                 # rules and a working example for one construct
alchem doc                         # list library modules
alchem doc Enum                    # a module's functions, one line each
alchem doc Enum.chunk_every        # signatures and examples
alchem doc --search chunk          # search functions, modules and topics
alchem doc lib/cart.alc            # the @moduledoc and @doc text of a file
```

`--json` gives structured output for each, `syntax --all` prints every topic and `doc --all Module` every function in full. Every example these commands print is compiled and run by the test suite (`testrunner/docs_test.go`), and a library function without a description and an example fails it.

`alchem agent-install <agent>` writes a short instruction file that tells a coding agent what Alchem is and to run `alchem agent-guide`; the file holds no reference material, so it does not go stale. Agents: `claude`, `cursor`, `windsurf`, `cline`, `copilot` and `agents` (`AGENTS.md`); `--list` shows the path each uses. `--scope user` installs for every project where the agent supports it, `--dir` chooses the directory, and `--force` replaces a file that has been edited. `AGENTS.md` and the Copilot instructions belong to the project, so only a marked block inside them is written and refreshed.

`alchem docs` writes the generated reference files: [library reference](library-reference.md), [syntax reference](syntax-reference.md), [command reference](cli-reference.md) and [agent guide](agent-guide.md). `alchem docs --check` exits 1 and names the files that are out of date; the test suite runs it, so adding a library function, a syntax topic or a command option without regenerating fails CI.

Where the documentation lives:

| What | Where | Enforced by |
| --- | --- | --- |
| Library function descriptions and examples | `doc(...)` in `compiler/syntax/docs_*.go`, beside the signature table | every function must have one; every example runs |
| Library module descriptions and grouping | `module(...)` in `compiler/syntax/docs.go` | every function's module must be listed |
| Syntax topics | `topic(...)` in `compiler/syntax/topics.go` | every example runs |
| Commands and options | `guide.Commands` and the flags in `cmd/alchem/main.go` | options are read from the flags themselves |

## Creating and running a project

`alchem new my_app` creates `my_app/` with `main.alc`, a library module in `lib/my_app.alc` whose documentation examples are doctests, a test in `test/my_app_test.alc`, a `.gitignore` and a README. `alchem run main.alc -- arguments` builds the program into a temporary directory and runs it, passing input, output and the exit status through; it takes the build options except `-o`.

```sh
alchem new my_app
cd my_app
alchem run main.alc -- Ada
alchem test test
```

## The interactive shell

`alchem alx`, the Alchem Language Executor, reads Alchem a line or a block at a time and prints what each input printed and then its value. A line that leaves a `do`, `fn`, bracket or string open continues on the next. `def`, `struct`, `type`, `defexception` and `import` lines are kept as definitions for the inputs after them; `h Enum.map` shows documentation, `:reset` forgets everything and `:quit` or ctrl-D leaves.

```text
alx(1)> x = 10
10
alx(2)> def double(n: integer): integer do
...(2)>   n * 2
...(2)> end
:ok
alx(3)> Enum.map([1, x], fn n -> double(n) end)
[2, 20]
```

Alchem is compiled, so each input is compiled and run as a program together with the definitions and statements accepted before it, which takes a few tenths of a second. Earlier statements run again each time, but only the new input's output is shown; their effects on files, the network or processes repeat. An input that fails to compile or fails while running is reported and forgotten.

## Editors

`alchem lsp` is a language server over standard input and output. It checks a file as it is edited, including unsaved changes and the files it imports, and offers hover documentation for library and project functions, completion after `Module.`, go to definition across imported files, document symbols, and formatting with `alchem fmt`'s rules.

Neovim:

```lua
vim.filetype.add({ extension = { alc = "alchem" } })
vim.api.nvim_create_autocmd("FileType", {
  pattern = "alchem",
  callback = function()
    vim.lsp.start({ name = "alchem", cmd = { "alchem", "lsp" }, root_dir = vim.fs.root(0, { ".git" }) })
  end,
})
```

Helix, in `languages.toml`:

```toml
[[language]]
name = "alchem"
scope = "source.alchem"
file-types = ["alc"]
language-servers = ["alchem"]

[language-server.alchem]
command = "alchem"
args = ["lsp"]
```

Other editors start it the same way: the command is `alchem lsp` and the files are `*.alc`.

## Checking, formatting and building

`check` resolves imports and checks every reachable function without running source or invoking the Go compiler. Positioned compile errors include the defining file, one-based line/column and a message. `--json` on build/check writes a structured diagnostic object to stderr (`file`, `line`, `column`, `message`); non-source errors may have no position. Syntax/import chains and semantic errors remain available as human-readable errors without that flag.

`fmt` accepts multiple files/directories, recursively finds `.alc` files, and skips `.git`/`artifacts`. It parses all input before writing any file, so a syntax error leaves the batch untouched. Each file is replaced through a same-directory temporary file with its existing permissions. Symlinks/nonregular files are rejected. `--check` reports out-of-date files, writes nothing and exits 1. Canonical formatting is deterministic and idempotent across the implemented grammar, with two-space indentation. Operators get parentheses only where precedence needs them (`a - (b - c)`, `(a + b) * c`), and a `case`, `rescue` or `fn` arm that is one short expression stays on the line of its pattern. Formatting never changes what a program means: its syntax tree is the same before and after. Call and index targets are never wrapped: statements have no terminator, so an added leading parenthesis would attach to the preceding statement. Pipes and imports are retained. Formatting does not require imports to exist or type-check. Comments and documentation attributes are kept.

Build options:

| Option | Default/meaning |
| --- | --- |
| `-o path` | Explicit executable path; otherwise derive from the resolved entry basename (so `build .` uses the directory name) and append `.exe` for a Windows target; entries with no usable name require `-o` |
| `--target GOOS/GOARCH` | Explicit target; otherwise use inherited Go target settings or the native platform |
| `--timeout duration` | Two-minute total build context, propagated across import loading and toolchain execution |
| `--shutdown-timeout duration` | Two seconds for runtime tree cleanup; minimum 1 ms |
| `--max-call-depth n` | 100,000 nested Alchem calls per process; accepts 1 to 1,000,000. Exceeding it is a recoverable `call depth exceeded` failure |
| `--trace=true/false` | Include automatic Alchem runtime frames by default |
| `--race` | Ask the Go toolchain to instrument the generated executable; requires a supported race target and native/C toolchain |
| `--json` | Structured compile diagnostics on stderr |

Builds use an isolated, embedded-runtime Go module with workspace discovery and VCS stamping disabled. Target overrides are passed explicitly; unsupported targets/toolchain combinations fail without replacing an existing executable. Success publishes a staged binary next to the destination. Ctrl-C cancels the build context. Cross-compiled executables are compilation evidence until run on an appropriate host.

Source limits: each `.alc` file may be at most 1 MiB, grammar nesting (expressions, patterns, types and blocks) at most 256 levels, and a single operator or postfix chain at most 1024 operations. One import graph may contain at most 1024 modules. Exceeding a limit is a compile diagnostic for `check`, `fmt` and `build` alike.

`test --timeout` configures each fixture's execution deadline (default 30 seconds); its context also cancels builds and execution on interruption. Stream bounds, exact stdout/stderr checks and explicit exit-code metadata are retained. Fixture deadline and the compiled program's shutdown deadline are separate budgets.

Library entry points are `Check`/`CheckContext`, `Format`, `BuildWithOptions`/`BuildWithOptionsContext` and the existing `Build`, `BuildTo`, `BuildToContext` wrappers. `BuildOptions` provides `Output`, `GOOS`, `GOARCH`, `Timeout`, `ShutdownTimeout`, `NoTrace`, `Race` and `MaxCallDepth`. Zero timeout fields select defaults; negative deadlines are rejected. `Describe(error)` exposes positioned diagnostics, preserving imported-source information. `testrunner.RunContext` and `RunWithTimeout` expose fixture deadlines programmatically.

## The Go toolchain

Builds, tests, `run`, `alx`, and `check` of a program with `extern` run a `go` command, found in this order:

1. `ALCHEM_GO`, the path of a go executable.
2. `go` on `PATH`, when it is Go 1.27 or newer. An older one is skipped, and `alchem version` says so; one whose version cannot be read is used as it is.
3. The Go release alchem downloaded before, in `<user cache>/alchem/toolchains/<release>` (`ALCHEM_CACHE` replaces `<user cache>/alchem`).
4. Otherwise the pinned release (`compiler.GoRelease`) is downloaded from `https://go.dev/dl/` (`ALCHEM_GO_MIRROR` replaces it), checked against the SHA-256 recorded in the compiler, and unpacked there. A notice goes to standard error. Set `ALCHEM_GO_DOWNLOAD=off` to fail with an explanation instead.

A downloaded release runs with its own `GOROOT` and `GOTOOLCHAIN=local`, so settings left by another Go installation do not mix two releases. `alchem version` prints the compiler version and which go builds use; `--json` adds the pinned release. `go run ./tools/gorelease go1.N.M` pins a new release, reading its checksums from go.dev.

Compiled programs are self-contained native executables: running one needs neither Go nor Alchem.

## Go declarations and the lock file

`alchem check` verifies every `extern` against the Go declaration it names. For a program with `extern` declarations this runs the Go toolchain (`go list`) to read the packages' type information, compiling them into the build cache on first use; programs without `extern` are checked without Go. Mismatches are ordinary diagnostics at the `extern` line and appear in `--json` output.

`check` and `build` accept `--locked`, which fails instead of updating `alchem.lock`; see [modules](modules.md).

## Tests

`alchem test path...` runs `*_test.alc` files with `--seed`, `--only`, `--trace`, `--max-failures`, `--timeout`, `--cover` and `--cover-min`; see [testing Alchem programs](unit-testing.md). A directory that holds no test files is run as output fixtures.
