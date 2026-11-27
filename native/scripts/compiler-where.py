#!/usr/bin/env python3
"""Where the compiler ends on a text it neither takes nor refuses.

    compiler-where.py COMPILER FILE... [--built FILE]

The compiler is not traced: on a failure of its own (nearly always a
position that is -1, of something that was not found, written into a
record as a byte) it ends with status 72 and no word. Its source with a
function native_traced makes a compiler that is traced (nc_entry_table),
a quarter larger and a sixth slower, which ends as any program does: with
the reason and the functions that led there. COMPILER (build/dev/A2) builds
that compiler here, in a few seconds, from the source as it is written, so
that the functions have their names; each FILE is given to it, and what it
says is printed with each function's file and line in
implementations/alchem. A text it takes or refuses prints its status alone.

--built keeps the traced compiler, and uses the one that is there: name a
new file after the compiler's source changes.
"""
import argparse
import bisect
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('compiler', type=Path)
    parser.add_argument('files', nargs='+', type=Path)
    parser.add_argument('--built', type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('compiler_reach', ROOT / 'scripts/compiler-reach.py')
    reach = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reach)
    source, starts = reach.assembled(traced=True)
    defs = reach.functions(source.split('\n'), starts)
    firsts = [d[0] for d in defs]

    def placed(match):
        """A line of the assembled source as its file and line there."""
        line = int(match.group(1))
        k = bisect.bisect_right(firsts, line) - 1
        if k < 0:
            return match.group(0)
        first, _, file, at = defs[k]
        return f'{file}:{at + line - first}'

    with tempfile.TemporaryDirectory(prefix='alchem-where-') as top:
        traced = Path(top) / 'traced'
        if args.built and args.built.exists():
            shutil.copyfile(args.built, traced)
        else:
            env = dict(os.environ, ALCHEM_MEMORY=os.environ.get('ALCHEM_MEMORY', '8G'), ALCHEM_SECONDS='600')
            built = subprocess.run([str(ROOT / 'scripts/limited'), str(args.compiler.resolve())], input=source.encode(), capture_output=True, env=env)
            if built.returncode or built.stderr:
                raise SystemExit(f'the compiler did not build the traced one: {built.returncode} {built.stderr.decode(errors="replace")[:300]}')
            traced.write_bytes(built.stdout)
            if args.built:
                args.built.parent.mkdir(parents=True, exist_ok=True)
                args.built.write_bytes(built.stdout)
                args.built.chmod(0o700)
        traced.chmod(0o700)
        for file in args.files:
            done = subprocess.run([str(traced)], input=file.read_bytes(), capture_output=True, env={'PATH': ''}, timeout=3600)
            said = done.stderr.decode(errors='replace')
            if done.returncode in (0, 65):
                print(f'{file}: {"taken" if done.returncode == 0 else "refused"}')
            else:
                print(f'{file}: status {done.returncode}')
                print(re.sub(r'<stdin>:(\d+)', placed, said), end='')
    return 0


if __name__ == '__main__':
    sys.exit(main())
