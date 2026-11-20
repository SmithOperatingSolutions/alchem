#!/usr/bin/env bash
# Build the experimental source compiler and its pinned frontend once.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if (( $# > 1 )); then echo "Usage: $0 [OUTPUT_DIRECTORY]" >&2; exit 2; fi
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo "Requires Linux x86-64" >&2; exit 2
fi
export GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off GOWORK=off
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/implementations/rust/target}"
FRONTEND_GO="${ALCHEM_FRONTEND_GO:-go}"
DESTINATION="${1:-$ROOT/build/native}"
mkdir -p "$DESTINATION"
DESTINATION="$(cd "$DESTINATION" && pwd)"
STAGE="$(mktemp -d "$DESTINATION/.alchem-native-build-XXXXXX")"
trap 'rm -rf "$STAGE"' EXIT
(cd adapters/alchem && "$FRONTEND_GO" build -mod=readonly -trimpath -o "$STAGE/alchem-source-probe" .)
cargo build --release --locked --offline --manifest-path implementations/rust/Cargo.toml --bin alchem-native-rust
cp "$CARGO_TARGET_DIR/release/alchem-native-rust" "$STAGE/alchem-native"
chmod 700 "$STAGE/alchem-native" "$STAGE/alchem-source-probe"
mv "$STAGE/alchem-source-probe" "$DESTINATION/alchem-source-probe"
mv "$STAGE/alchem-native" "$DESTINATION/alchem-native"
python3 scripts/build-self-hosted.py --frontend "$DESTINATION/alchem-source-probe" --backend "$DESTINATION/alchem-native" --output-directory "$DESTINATION"
python3 scripts/build-core-modules.py --compiler "$DESTINATION/alchem-compiler" --output-directory "$DESTINATION/core" --arithmetic-output "$DESTINATION/alchem-arithmetic"
# The import bundler is an ordinary Alchem program built by the published compiler.
env -i PATH= "$DESTINATION/alchem-compiler" < tools/alchem-bundle.alc > "$STAGE/alchem-bundle"
chmod 700 "$STAGE/alchem-bundle"
mv "$STAGE/alchem-bundle" "$DESTINATION/alchem-bundle"
# alchem is the test, run, build, check and new commands with the bundler and the
# compiler in one program (spec/alchem-testing-gen.md), built by the published compiler.
python3 scripts/build-alchem.py --compiler "$DESTINATION/alchem-compiler" --output "$DESTINATION/alchem"
echo "Built self-hosted compiler/core tools and native bootstrap tools in $DESTINATION"
