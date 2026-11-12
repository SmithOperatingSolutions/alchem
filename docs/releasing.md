# Releasing

Releases are GitHub releases built by `.github/workflows/release.yml`.

## Cutting a release

1. Make sure `main` is green.
2. Tag the commit and push the tag:

   ```bash
   git tag -a v0.1.0 -m "Alchem v0.1.0"
   git push origin v0.1.0
   ```

3. The workflow builds `alchem` for linux, darwin and windows on amd64 and arm64 with `-X main.version=<tag>`, packs each with the README and LICENSE into `alchem_<tag>_<os>_<arch>.tar.gz` (`.zip` on Windows), and writes `checksums.txt`.
4. It runs the Linux binary with no Go on `PATH`, so the binary downloads the pinned Go release and builds `examples/hello.alc`, and checks the result.
5. It publishes the release with generated notes. A tag with a hyphen (`v0.2.0-rc.1`) becomes a prerelease.

Running the workflow by hand (`workflow_dispatch`) does steps 3 and 4 and uploads the archives as a workflow artifact without publishing anything.

## Versions

Versions follow semantic versioning with a `v` prefix. Before 1.0, a minor version may change the language or the library incompatibly; a patch version does not.

## The pinned Go release

Each compiler records the Go release it downloads when no `go` command is installed (`compiler.GoRelease`) and the SHA-256 of that release's archives. To move to a newer Go:

```bash
go run ./tools/gorelease go1.27.5
```

The tool reads the checksums from go.dev and rewrites `compiler/toolchain.go`. Commit the result with the tests; the next release carries it.
