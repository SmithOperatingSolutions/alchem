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
TAG="$(cat "$REPOSITORY/mise.toml" docker/Dockerfile docker/enter.sh | "${HASH[@]}" | cut -c1-12)"
IMAGE="alchem-native-dev:$TAG-${PLATFORM##*/}"

if [[ "${1:-}" == --build-image ]] || ! "$DOCKER" image inspect "$IMAGE" >/dev/null 2>&1; then
  # The image needs only the toolchain file and the entrypoint: they are the
  # whole context.
  CONTEXT="$(mktemp -d)"
  trap 'rm -rf "$CONTEXT"' EXIT
  cp "$REPOSITORY/mise.toml" docker/enter.sh "$CONTEXT/"
  "$DOCKER" build --platform "$PLATFORM" -f docker/Dockerfile -t "$IMAGE" "$CONTEXT"
  rm -rf "$CONTEXT"; trap - EXIT
fi
if [[ "${1:-}" == --build-image ]]; then exit 0; fi

TTY=()
if [[ -t 0 && -t 1 ]]; then TTY=(-it); fi
# The container ends with the client that runs it. A client that is killed
# (by scripts/bounded.py, which kills its whole process group, or by any
# signal) leaves its container running; a watcher in a process group of its
# own kills the container once the client is gone.
NAME="alchem-native-$$-$RANDOM"
CLIENT=$$
set -m
( trap '' HUP INT TERM
  while kill -0 "$CLIENT" 2>/dev/null; do sleep 2; done
  "$DOCKER" kill "$NAME" >/dev/null 2>&1 || true ) </dev/null >/dev/null 2>&1 &
set +m
# The command runs as the user who runs this script (docker/enter.sh).
# SYS_PTRACE/seccomp: the harness uses strace and ptrace for fault injection and
# arena measurements. Named volumes keep build caches off the bind mount.
exec "$DOCKER" run --rm --name "$NAME" "${TTY[@]}" --platform "$PLATFORM" \
  ${ALCHEM_CONTAINER_MEMORY:+--memory "$ALCHEM_CONTAINER_MEMORY" --memory-swap "$ALCHEM_CONTAINER_MEMORY"} \
  -e ALCHEM_UID="$(id -u)" -e ALCHEM_GID="$(id -g)" \
  --cap-add SYS_PTRACE --security-opt seccomp=unconfined \
  -v "$REPOSITORY:/work" \
  -v "alchem-native-cache-${PLATFORM##*/}:/var/cache/alchem-native" \
  -v alchem-native-cargo-registry:/opt/cargo/registry \
  "$IMAGE" "${@:-bash}"
