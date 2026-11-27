#!/usr/bin/env bash
# Put the ARM64 assembler (GNU binutils) and QEMU's user-mode emulator in
# build/arm64-tools, from the host's Ubuntu/Debian package archive, without
# installing anything (spec/arm64.md):
#
#   scripts/fetch-arm64-tools.sh
#   build/arm64-tools/bin/aarch64-linux-gnu-as, ...-objcopy, ...-objdump
#   build/arm64-tools/bin/qemu-aarch64-static
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
tools="$root/build/arm64-tools"
# The development container has them installed and no package lists to
# download them with (docker/Dockerfile): those are linked.
lists="$(find /var/lib/apt/lists -maxdepth 1 -type f ! -name lock 2>/dev/null | head -1)"
if [[ -z "$lists" ]] && command -v aarch64-linux-gnu-as >/dev/null && command -v qemu-aarch64-static >/dev/null; then
  rm -rf "$tools.new" && mkdir -p "$tools.new/bin"
  for name in as ld objcopy objdump; do ln -s "$(command -v aarch64-linux-gnu-$name)" "$tools.new/bin/aarch64-linux-gnu-$name"; done
  ln -s "$(command -v qemu-aarch64-static)" "$tools.new/bin/qemu-aarch64-static"
  rm -rf "$tools" && mv "$tools.new" "$tools"
  "$tools/bin/aarch64-linux-gnu-as" --version | head -1
  "$tools/bin/qemu-aarch64-static" --version | head -1
  exit 0
fi
rm -rf "$tools.new" && mkdir -p "$tools.new/debs" "$tools.new/root"
(cd "$tools.new/debs" && apt-get download qemu-user-static binutils-aarch64-linux-gnu)
for deb in "$tools.new"/debs/*.deb; do dpkg-deb -x "$deb" "$tools.new/root"; done
mkdir -p "$tools.new/bin"
libs="$tools/root/usr/lib/$(uname -m)-linux-gnu"
for name in as ld objcopy objdump; do
  printf '#!/bin/sh\nLD_LIBRARY_PATH=%s exec %s "$@"\n' "$libs" "$tools/root/usr/bin/aarch64-linux-gnu-$name" > "$tools.new/bin/aarch64-linux-gnu-$name"
done
ln -s "../root/usr/bin/qemu-aarch64-static" "$tools.new/bin/qemu-aarch64-static"
chmod 755 "$tools.new"/bin/aarch64-linux-gnu-*
rm -rf "$tools" && mv "$tools.new" "$tools"
"$tools/bin/aarch64-linux-gnu-as" --version | head -1
"$tools/bin/qemu-aarch64-static" --version | head -1
