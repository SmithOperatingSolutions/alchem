# Alchem Native

## Commits and pull requests

- No AI attribution anywhere: no `Co-Authored-By` trailers, no "Generated with"
  lines, no tool or model credits in commit messages, PR titles/descriptions or
  comments.
- Add `[skip ci]` to commit subjects. Do not trigger or dispatch GitHub Actions;
  all workflows are manual-only and verification is local.
- Do not merge PRs or modify production Alchem without an explicit request.

## Environment

Toolchains are pinned in `mise.toml` (`mise install`). Generated executables are
Linux x86-64 ELF, so on any other host run builds and checks through the
container tasks (`mise run linux:verify`, `mise run linux:build`,
`mise run linux:shell`). See `docs/HANDOFF.md` for the resume point and
`docs/progress.md` for recorded verification results.

## Finish the work

- Do not be lazy. When a difference from the pinned upstream compiler, a
  failing case or a limit turns up, fix it in the same piece of work. Do not
  defer it, list it as a "native limit", or hand it back as a follow-up.
- Do not stop at the first version that passes. Probe the change against
  upstream, find what else the same cause breaks, and close that too.
- Leave something undone only when it cannot be done here, and then say
  exactly why (the concrete technical reason), not that it is large or out
  of scope.
- Do not ask whether to continue with work that was already requested.
