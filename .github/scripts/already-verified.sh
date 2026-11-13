#!/usr/bin/env bash
# Prints "true" when the commit is the squash merge of a pull request whose
# head had exactly the same tree and passed this workflow, and "false"
# otherwise. Such a commit has already been checked file for file, so CI on
# main has nothing new to find. Anything unexpected prints "false", so the
# checks run.
#
# usage: already-verified.sh <owner/repo> <commit sha>   (needs gh and GH_TOKEN)
set -uo pipefail
repo=$1
sha=$2

tree=$(gh api "repos/$repo/git/commits/$sha" --jq .tree.sha) || { echo false; exit 0; }
heads=$(gh api "repos/$repo/commits/$sha/pulls" --jq '.[] | select(.merged_at != null) | .head.sha') || { echo false; exit 0; }
for head in $heads; do
  head_tree=$(gh api "repos/$repo/git/commits/$head" --jq .tree.sha) || continue
  if [[ -z "$tree" || "$head_tree" != "$tree" ]]; then
    continue
  fi
  passed=$(gh api "repos/$repo/actions/workflows/ci.yml/runs?head_sha=$head&event=pull_request&status=success&per_page=1" --jq .total_count) || continue
  if [[ "$passed" =~ ^[1-9][0-9]*$ ]]; then
    echo true
    exit 0
  fi
done
echo false
