# Releasing

Releases are GitHub releases built by `.github/workflows/release.yml`.

## Cutting a release

1. Make sure `main` is green. After a squash merge whose tree is the one the pull request's checks passed on, CI on `main` reports that at once instead of running again (the "Already verified" job), so the commit can be tagged straight away.
2. Tag the commit and push the tag:

   ```bash
   git tag -a v0.1.0 -m "Alchem v0.1.0"
   git push origin v0.1.0
   ```

3. The workflow builds the `alchem` written in Alchem (`native/`) from the released compiler `native/pinned-compiler.json` names, with neither Go nor Rust, for linux on amd64 and arm64, darwin on arm64 and windows on amd64, each saying the tag as its version.
4. It signs the macOS and the Windows binary where the signing secrets are set (below).
5. It runs each binary, as signed, on a machine of its own target with no Go there: it must say its version and target, build and run a program, refuse a wrong one with the place and the reason, and serve an editor's session (`.github/scripts/lsp-session.py`).
6. It packs each with the README and LICENSE into `alchem_<tag>_<os>_<arch>.tar.gz` (`.zip` on Windows) and writes `checksums.txt`.
7. It installs from those archives with `install.sh` on Linux (amd64 and arm64) and macOS and with `install.ps1` on Windows, served from the machine itself; what is installed must say the tag and build and run a program.
8. It publishes the release with generated notes. A tag with a hyphen (`v0.2.0-rc.1`) becomes a prerelease.
9. It attaches the Homebrew formula and Scoop manifest for the release (`alchem.rb`, `alchem.json`), made by `tools/packaging` from `checksums.txt`.
10. The release does not start the Packaging workflow by itself, since it is published with the workflow's own token: the pull request that moves the tap and the bucket (below) runs it, and it installs the release through the install scripts, the tap and the bucket.

Running the workflow by hand (`workflow_dispatch`) does steps 3 to 7 and uploads the archives as a workflow artifact without publishing anything. With no signing secrets it signs with certificates it makes for the run, so that steps 5 and 7 run the binaries as a release signs them. With its `unsigned` input set it signs nothing, which is what a tag does while no signing secret is set (`gh workflow run release.yml -f unsigned=true`).

The Go `alchem` (`cmd/alchem`) is not released any more. It stays in the repository as the reference the checks of `native/` compare against. The releases up to v0.3.11 are of it, for six targets; there is no native release for macOS on Intel, and none for Windows on ARM64 until the native compiler has that target, where the x64 program is installed and runs.

## After a release

The tap and the bucket are `Formula/alchem.rb` and `bucket/alchem.json` in this repository, so they move to a new release by pull request:

```bash
go run ./tools/packaging -version v0.4.1
```

The tool downloads the release's `checksums.txt` and rewrites both files. The Packaging workflow checks the pull request by installing from them. Scoop can also find a newer release on its own through the manifest's `checkver` and `autoupdate`.

## Signing

The release workflow signs the binaries when its secrets are set, and skips signing otherwise.

| Secret | What it holds |
| --- | --- |
| `APPLE_DEVELOPER_ID_P12` | A Developer ID Application certificate and key, exported from Keychain as `.p12` and base64-encoded |
| `APPLE_DEVELOPER_ID_P12_PASSWORD` | The password of that `.p12` |
| `APPLE_NOTARY_API_KEY_JSON` | An App Store Connect API key for notarization, in the JSON form `rcodesign encode-app-store-connect-api-key` writes |
| `WINDOWS_SIGNING_PFX` | A code-signing certificate and key as `.pfx`, base64-encoded |
| `WINDOWS_SIGNING_PFX_PASSWORD` | The password of that `.pfx` |

macOS binaries are signed with the hardened runtime and notarized with [rcodesign](https://github.com/indygreg/apple-platform-rs), which runs on the Linux release runner; a bare binary cannot be stapled, so Gatekeeper checks its notarization online on first run. Windows binaries are signed and timestamped with `osslsigncode`. These steps have not yet run with real certificates; the first signed release should be checked on a Mac (`codesign -dv --verbose=4 alchem`, `spctl -a -t install alchem`) and on Windows (`Get-AuthenticodeSignature alchem.exe`).

## Versions

Versions follow semantic versioning with a `v` prefix. Before 1.0, a minor version may change the language or the library incompatibly; a patch version does not.

## The pinned Go release

Each compiler records the Go release it downloads when no `go` command is installed (`compiler.GoRelease`) and the SHA-256 of that release's archives. To move to a newer Go:

```bash
go run ./tools/gorelease go1.27.5
```

The tool reads the checksums from go.dev and rewrites `compiler/toolchain.go`. Commit the result with the tests; the next release carries it.
