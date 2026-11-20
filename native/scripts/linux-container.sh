#!/usr/bin/env bash
# Run a command in the linux/amd64 development container with the repository
# mounted at /work. Builds the image on first use or when mise.toml/Dockerfile
# change. Usage: linux-container.sh [--build-image] [COMMAND...]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
DOCKER="${ALCHEM_DOCKER:-docker}"
PLATFORM="${ALCHEM_CONTAINER_PLATFORM:-linux/amd64}"
if command -v sha256sum >/dev/null 2>&1; then HASH=(sha256sum); else HASH=(shasum -a 256); fi
TAG="$(cat mise.toml docker/Dockerfile | "${HASH[@]}" | cut -c1-12)"
IMAGE="alchem-native-dev:$TAG"

if [[ "${1:-}" == --build-image ]] || ! "$DOCKER" image inspect "$IMAGE" >/dev/null 2>&1; then
  "$DOCKER" build --platform "$PLATFORM" -f docker/Dockerfile -t "$IMAGE" .
fi
if [[ "${1:-}" == --build-image ]]; then exit 0; fi

TTY=()
if [[ -t 0 && -t 1 ]]; then TTY=(-it); fi
# SYS_PTRACE/seccomp: the harness uses strace and ptrace for fault injection and
# arena measurements. Named volumes keep build caches off the bind mount.
exec "$DOCKER" run --rm "${TTY[@]}" --platform "$PLATFORM" \
  --cap-add SYS_PTRACE --security-opt seccomp=unconfined \
  -v "$ROOT:/work" \
  -v alchem-native-cache:/var/cache/alchem-native \
  -v alchem-native-cargo-registry:/root/.cargo/registry \
  "$IMAGE" "${@:-bash}"
