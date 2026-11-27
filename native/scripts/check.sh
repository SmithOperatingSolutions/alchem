#!/usr/bin/env bash
# What a pull request's x86-64 and Derived files jobs check
# (.github/workflows/native.yml), with the same settings: run in the
# linux/amd64 container (mise run linux:check), from any host, it gives the
# answer CI gives. See docs/testing.md.
#
#   scripts/check.sh [GATE...]     the gates named, or all of them
#
# 1. The pinned Go command, the reference the gates compare against.
# 2. The fixpoint (A1 = A2) from the pinned release and the gates, four at a
#    time with 14 GiB each, as CI runs them.
# 3. The seed makes the compiler the pinned release makes, byte for byte.
# 4. Every derived file is what its generator makes.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)-$(uname -m)" != Linux-x86_64 ]]; then
  echo 'check.sh runs on Linux x86-64: use mise run linux:check' >&2
  exit 2
fi
# Emulated x86-64 (Rosetta or QEMU, as in the container on Apple silicon)
# gives no ptrace, ignores strace's fault injection, fails under an
# address-space limit and prints some floats otherwise: a third of the gates
# fail there whatever the change. Its answer is not CI's.
if grep -qiE 'rosetta|qemu' /proc/self/maps || grep -q VirtualApple /proc/cpuinfo; then
  if [[ "${ALCHEM_CHECK_EMULATED:-}" != 1 ]]; then
    echo 'check.sh: this x86-64 is emulated, where many gates fail whatever the change (docs/testing.md).' >&2
    echo 'Run it on a Linux x86-64 machine, or set ALCHEM_CHECK_EMULATED=1 to run it anyway.' >&2
    exit 2
  fi
  echo 'check.sh: emulated x86-64: failures of ptrace, strace and memory gates are expected here' >&2
fi
step() { echo "== $*"; }

step dependencies
mise run fetch
mise run fetch:seed
# QEMU and an ARM64 assembler, for the ARM64 gates (build/arm64-tools).
bash scripts/fetch-arm64-tools.sh

step 'the pinned Go command'
python3 -c "import importlib.util as u; s = u.spec_from_file_location('upstream', 'scripts/upstream-examples.py'); m = u.module_from_spec(s); s.loader.exec_module(m); m.build_upstream()"
test -x build/dev/alchem-upstream.bin

step 'fixpoint and gates'
ALCHEM_VERIFY_MEMORY=14G python3 scripts/verify-quick.py --jobs 4 "$@"

step 'the seed gives the compiler the pinned release gives'
ALCHEM_VERIFY_LIMITED=1 python3 scripts/verify-quick.py --build-only
cp build/dev/A2 build/dev/A2-pinned
ALCHEM_VERIFY_LIMITED=1 python3 scripts/verify-quick.py --seed --build-only
cmp build/dev/A2 build/dev/A2-pinned

step 'derived files'
python3 scripts/verify-derived.py

step 'all passed'
