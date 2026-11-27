#!/usr/bin/env bash
# The gates on Linux ARM64, in a container: on a Mac with Apple silicon, the
# quick way to run them. The container runs at the machine's own speed, where
# macOS checks every new program for a sixth of a second before its first run
# and the gates run thousands. CI runs them on macOS, Windows and x86-64.
#
#   scripts/verify-arm64.sh [GATE...]
#
# The compiler is made from this tree's source by the pinned release, as
# everywhere; the gates are those of verify-darwin.py, but for the ones that
# trace a process by x86-64 registers.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-}" != --inside ]]; then
  # A ceiling for all of it, as scripts/limited has one for each program.
  ALCHEM_CONTAINER_MEMORY="${ALCHEM_CONTAINER_MEMORY:-12g}" ALCHEM_CONTAINER_PLATFORM=linux/arm64 exec bash scripts/linux-container.sh bash scripts/verify-arm64.sh --inside "$@"
fi
shift
test -d .cache/gomod || (cd adapters/alchem && go mod download)
python3 - <<'PY'
import os, subprocess, sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def script(name):
    spec = spec_from_file_location(name.replace('-', '_'), f'scripts/{name}.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


text = script('build-arm64').source()
compiler = script('pinned-compiler').fetch('linux-arm64')
work = Path('build/dev')
work.mkdir(parents=True, exist_ok=True)
made = []
for stage in (1, 2, 3):
    run = subprocess.run([str(compiler)], input=text, capture_output=True)
    if run.returncode or run.stderr:
        sys.exit(f'stage {stage}: {run.returncode} {run.stderr.decode(errors="replace")}')
    compiler = (work / f'alchem-compiler-linux-arm64.{stage}').resolve()
    compiler.unlink(missing_ok=True)
    compiler.write_bytes(run.stdout)
    compiler.chmod(0o755)
    made.append(run.stdout)
if made[1] != made[2]:
    sys.exit('the compiler does not make itself')
os.replace(compiler, work / 'alchem-compiler-linux-arm64')
PY
# The container runs this as the repository's owner, not as root
# (docker/enter.sh): a file without write permission is one to it.
exec env ALCHEM_VERIFY_JOBS="${ALCHEM_VERIFY_JOBS:-7}" ALCHEM_VERIFY_WITHOUT=boolean_library,lists,options python3 scripts/verify-darwin.py build/dev/alchem-compiler-linux-arm64 "$@"
