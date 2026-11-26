#!/usr/bin/env bash
# Builds what the playground page loads into native/playground/web:
# alchem_emu.wasm, the interpreter, and alchem, the Linux x86-64 alchem made
# from this tree by the pinned compiler. The page is then served from there
# as static files, for example:
#
#   python3 -m http.server 8737 --directory native/playground/web
#
# The alchem is built on Linux x86-64 directly, elsewhere in the container
# of scripts/linux-container.sh.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
root="$(cd "$here/.." && pwd)"

(cd "$here/emu" && cargo build --release --offline --lib --target wasm32-unknown-unknown)
cp "$here/emu/target/wasm32-unknown-unknown/release/alchem_emu.wasm" "$here/web/"

compiler=$(python3 "$root/scripts/pinned-compiler.py" linux-x86_64)
if [[ "$(uname -s)/$(uname -m)" == Linux/x86_64 ]]; then
  python3 "$root/scripts/build-alchem.py" --compiler "$compiler" --output "$here/web/alchem"
else
  relative="${compiler#"$root"/}"
  bash "$root/scripts/linux-container.sh" python3 scripts/build-alchem.py --compiler "$relative" --output playground/web/alchem
fi
ls -l "$here/web/alchem_emu.wasm" "$here/web/alchem"
