#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
# The whole run has a memory ceiling: a compile may reserve 16 GiB and the
# gates run side by side, so a runaway is killed here and not by the kernel
# at the machine's expense.
if [[ "${ALCHEM_VERIFY_LIMITED:-}" != 1 ]]; then
  export ALCHEM_VERIFY_LIMITED=1
  ALCHEM_MEMORY="${ALCHEM_VERIFY_MEMORY:-36G}" ALCHEM_SECONDS="${ALCHEM_VERIFY_SECONDS:-3600}" exec scripts/limited bash "$0" "$@"
fi
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo "Requires Linux x86-64 for native executable tests" >&2
  exit 2
fi
export GOTOOLCHAIN=local
export GOPROXY=off
export GOSUMDB=off
export GOWORK=off
WITH_RUST=false
WITH_SOURCE=false
case "${1:-}" in
  "") ;;
  --with-rust) WITH_RUST=true ;;
  --with-source) WITH_RUST=true; WITH_SOURCE=true ;;
  *) echo "Usage: $0 [--with-rust|--with-source]" >&2; exit 2 ;;
esac
if (( $# > 1 )); then echo "Usage: $0 [--with-rust|--with-source]" >&2; exit 2; fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
# Checks that do not depend on each other run side by side: bg starts one,
# join waits for all started since the last join, prints each one's output in
# the order they were started and stops at the first that failed.
JOBS=()
bg() {
  local out="$TMP/job.${#JOBS[@]}.$RANDOM"
  "$@" >"$out" 2>&1 &
  JOBS+=("$!:$out:$*")
}
join() {
  local failed=0 job pid out rest
  for job in "${JOBS[@]}"; do
    pid="${job%%:*}"; rest="${job#*:}"; out="${rest%%:*}"
    if ! wait "$pid"; then failed=1; echo "FAILED: ${rest#*:}"; fi
    cat "$out"
  done
  JOBS=()
  return "$failed"
}
build_go() { (cd implementations/go && go test ./... && go build -trimpath -o "$TMP/alchem-native-go" .); }
bg python3 -m unittest discover -s harness -p 'test_*.py' -v
bg build_go
if "$WITH_RUST"; then
  export CARGO_TARGET_DIR="$TMP/rust-target"
  cargo test --locked --offline --manifest-path implementations/rust/Cargo.toml
  cargo build --locked --offline --manifest-path implementations/rust/Cargo.toml
fi
join
bg python3 harness/run.py --compiler "$TMP/alchem-native-go"

if "$WITH_RUST"; then
  bg python3 harness/run.py --compiler "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/differential.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/flow_differential.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/recursion_differential.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/runtime_limits.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/bytes_differential.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/bytes_limits.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/status_differential.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/output.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/construction_differential.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/arena_limits.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/packing_differential.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/input.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/packing_limits.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/compiler_arena.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/slicing.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/function_capacity.py "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  join
  echo "Go native backend acceptance passed"
  echo "Go/Rust native backend comparison passed"
else
  join
  echo "Go native backend acceptance passed"
fi

if "$WITH_SOURCE"; then
  FRONTEND_GO="${ALCHEM_FRONTEND_GO:-go}"
  (cd adapters/alchem && "$FRONTEND_GO" test -mod=readonly ./... && "$FRONTEND_GO" build -mod=readonly -trimpath -o "$TMP/alchem-source-probe" .)
  bg python3 harness/source_probe.py "$TMP/alchem-source-probe" "$TMP/alchem-native-go" "$CARGO_TARGET_DIR/debug/alchem-native-rust"
  bg python3 harness/source_programs.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/lexer.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/integers.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/expressions.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/encoder.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/arithmetic_compiler.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/alchem_compiler.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/alchem_byte_compiler.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/compiler_scaling.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/compiler_entry.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  bg python3 harness/self_host.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/alchem-native-go"
  # The published build is independent of the gates above; the two after it need it.
  python3 scripts/build-self-hosted.py --frontend "$TMP/alchem-source-probe" --backend "$CARGO_TARGET_DIR/debug/alchem-native-rust" --output-directory "$TMP/self-hosted"
  bg python3 harness/core_modules.py "$TMP/self-hosted/alchem-compiler"
  bg python3 harness/core_tools.py "$TMP/self-hosted/alchem-compiler"
  bg python3 harness/grown_compiler.py "$TMP/alchem-source-probe" "$CARGO_TARGET_DIR/debug/alchem-native-rust" "$TMP/self-hosted/alchem-compiler"
  bg python3 harness/arm64.py "$TMP/self-hosted/alchem-compiler"
  bg python3 harness/x86_to_arm64.py 150 "$TMP/self-hosted/alchem-compiler"
  bg python3 harness/arm64_floats.py "$TMP/self-hosted/alchem-compiler"
  join
  echo "Pinned Alchem frontend probes and executable programs passed"
fi
