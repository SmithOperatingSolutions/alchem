# Contributing

Thank you for helping with Alchem. Issues and pull requests are welcome.

## Before you start

For a bug, open an issue with the program, the command, what you expected and what happened, and the output of `alchem version`. For a larger change, such as new syntax or a new library module, open an issue first so the design can be agreed before the work.

[docs/architecture.md](docs/architecture.md) explains how the compiler is put together, and [docs/roadmap.md](docs/roadmap.md) lists what is planned.

## Development

You need Go 1.27 or newer.

```bash
go test ./...
```

```bash
go vet ./... && gofmt -l .
```

```bash
go run ./cmd/alchem docs --check
```

```bash
go run ./cmd/alchem test tests/fixtures
```

CI also runs the suite under the race detector on Linux, macOS and Windows, cross-compiles six targets, and requires the coverage measured by `go run ./tools/coverage` to stay above its minimum. Run `go test -race ./...` before a change to the runtime in `compiler/actor`.

## Pull requests

- Each change comes with tests: a Go test, or an Alchem fixture in `tests/fixtures` for language and library behaviour.
- Library functions carry a description and examples (`alx>` lines), and the tests run the examples. After changing them, run `go run ./cmd/alchem docs` to regenerate the reference pages.
- Write documentation and examples in your own words. `go run ./tools/provenance -elixir <checkout>` checks that nothing is copied from Elixir's documentation; see [docs/provenance.md](docs/provenance.md).
- Keep one topic per pull request, and describe what changed and why.

## License

By contributing, you agree that your contributions are licensed under the [Apache License, Version 2.0](LICENSE), as the rest of the project is.
