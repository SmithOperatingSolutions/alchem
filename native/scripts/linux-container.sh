#!/usr/bin/env bash
# Run a command in the linux/amd64 development container with the repository
# mounted at /work, in /work/native. Builds the image on first use or when the
# repository's mise.toml or docker/Dockerfile change.
# Usage: linux-container.sh [--build-image] [COMMAND...]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DOCKER="${ALCHEM_DOCKER:-docker}"
PLATFORM="${ALCHEM_CONTAINER_PLATFORM:-linux/amd64}"
if command -v sha256sum >/dev/null 2>&1; then HASH=(sha256sum); else HASH=(shasum -a 256); fi
REPOSITORY="$(cd "$ROOT/.." && pwd)"
TAG="$(cat "$REPOSITORY/mise.toml" docker/Dockerfile | "${HASH[@]}" | cut -c1-12)"
IMAGE="alchem-native-dev:$TAG-${PLATFORM##*/}"

if [[ "${1:-}" == --build-image ]] || ! "$DOCKER" image inspect "$IMAGE" >/dev/null 2>&1; then
  # The image needs only the toolchain file: it is the whole context.
  CONTEXT="$(mktemp -d)"
  trap 'rm -rf "$CONTEXT"' EXIT
  cp "$REPOSITORY/mise.toml" "$CONTEXT/"
  "$DOCKER" build --platform "$PLATFORM" -f docker/Dockerfile -t "$IMAGE" "$CONTEXT"
  rm -rf "$CONTEXT"; trap - EXIT
fi
if [[ "${1:-}" == --build-image ]]; then exit 0; fi

TTY=()
if [[ -t 0 && -t 1 ]]; then TTY=(-it); fi
# SYS_PTRACE/seccomp: the harness uses strace and ptrace for fault injection and
# arena measurements. Named volumes keep build caches off the bind mount.
exec "$DOCKER" run --rm "${TTY[@]}" --platform "$PLATFORM" \
  ${ALCHEM_CONTAINER_MEMORY:+--memory "$ALCHEM_CONTAINER_MEMORY" --memory-swap "$ALCHEM_CONTAINER_MEMORY"} \
  --cap-add SYS_PTRACE --security-opt seccomp=unconfined \
  -v "$REPOSITORY:/work" \
  -v "alchem-native-cache-${PLATFORM##*/}:/var/cache/alchem-native" \
  -v alchem-native-cargo-registry:/root/.cargo/registry \
  "$IMAGE" "${@:-bash}"
