#!/usr/bin/env bash
# The native workflow's inputs, and whether they have passed it already.
#
#   native-verified.sh key
#       Prints the key of the checked-out commit's inputs to the native
#       workflow: a SHA-256 of the git object of each path below. Two commits
#       with the same key give the native jobs the same files.
#   native-verified.sh run <owner/repo> <key>   (needs gh and GH_TOKEN)
#       Prints the address of a successful native workflow run of this
#       repository (not of a fork) that recorded the key, or nothing. Anything
#       unexpected prints nothing, so the checks run.
#
# The paths: native/, the workflow and its scripts, the toolchain file
# (mise.toml at the root), and what the native jobs read outside native/ (the
# Windows job's examples/testing, and the files harness/commands.py `tree`
# reads).
set -uo pipefail

PATHS=(
  native
  .github/workflows/native.yml
  .github/scripts
  mise.toml
  examples
  tests/fixtures
  benchmarks/alchem/suite/processes.alc
)

case "${1:-}" in
  key)
    set -e
    for path in "${PATHS[@]}"; do
      printf '%s %s\n' "$(git rev-parse "HEAD:$path")" "$path"
    done | sha256sum | cut -d' ' -f1
    ;;
  run)
    repo=$2
    key=$3
    runs=$(gh api "repos/$repo/actions/artifacts?name=native-verified-$key&per_page=100" \
      --jq '.artifacts[] | select(.expired == false and .workflow_run.head_repository_id == .workflow_run.repository_id) | .workflow_run.id') || exit 0
    for id in $runs; do
      found=$(gh api "repos/$repo/actions/runs/$id" \
        --jq 'select(.conclusion == "success" and .path == ".github/workflows/native.yml") | .html_url') || continue
      if [[ "$found" == https://* ]]; then
        echo "$found"
        exit 0
      fi
    done
    ;;
  *)
    sed -n '2,15p' "$0" >&2
    exit 2
    ;;
esac
