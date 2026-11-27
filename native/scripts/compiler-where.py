#!/usr/bin/env python3
"""Where the compiler ends on a text it neither takes nor refuses.

    compiler-where.py COMPILER FILE... [--built FILE]

The compiler ends with status 72 and no word when it makes a byte of a
number that is none: nearly always a position that is -1, of something that
was not found, written into a record. Here its source is compiled as the
module of a test (scripts/compiler-reach.py does the same to count what
runs), with the three functions that write a number into bytes (nc_u16,
nc_u24, nc_u32) refusing one that does not fit: the test then fails where
the number was written, with the functions that led there, and that is
printed for each FILE. A text the compiler takes or refuses prints
nothing but its name.

COMPILER (build/dev/A2) builds the test, which takes three minutes and
some GiB (ALCHEM_REACH_BUILD_MEMORY, 12G); --built keeps it, and uses the
one that is there: name a new file after the compiler's source changes.
The lines are those of the assembled source, the functions those of
implementations/alchem.
"""
import argparse
import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CHECKED = '''  def nc_checked16(v: integer): bytes do
    if v < 0 do nc_unfit(v) else if v > 65535 do nc_unfit(v) else nc_u16(v) end end
  end
  def nc_checked24(v: integer): bytes do
    if v < 0 do nc_unfit(v) else if v > 16777215 do nc_unfit(v) else nc_u24(v) end end
  end
  def nc_checked32(v: integer): bytes do
    if v < -2147483648 do nc_unfit(v) else if v > 4294967295 do nc_unfit(v) else nc_u32(v) end end
  end
  def nc_unfit(v: integer): bytes do
    raise("no bytes of " <> Integer.to_string(v))
  end
'''


def checked(source):
    """The source with every call of the three functions checked, but those
    they make of each other."""
    head, body = source.split('\n', 1)
    inside = re.compile(r'(  def nc_u(?:16|24|32)\(.*?\n  end\n)', re.S)
    parts = inside.split(body)
    for k in range(0, len(parts), 2):
        for bits in ('16', '24', '32'):
            parts[k] = re.sub(r'(?<![A-Za-z0-9_])nc_u%s\(' % bits, 'nc_checked%s(' % bits, parts[k])
    return head + '\n' + CHECKED + ''.join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('compiler', type=Path)
    parser.add_argument('files', nargs='+', type=Path)
    parser.add_argument('--built', type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('compiler_reach', ROOT / 'scripts/compiler-reach.py')
    reach = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reach)
    with tempfile.TemporaryDirectory(prefix='alchem-where-') as top:
        work = Path(top)
        test = work / 'where'
        if args.built and args.built.exists():
            shutil.copyfile(args.built, test)
        else:
            source, _ = reach.assembled()
            env = dict(os.environ, ALCHEM_MEMORY=os.environ.get('ALCHEM_REACH_BUILD_MEMORY', '12G'), ALCHEM_SECONDS='3600')
            built = subprocess.run([str(ROOT / 'scripts/limited'), str(args.compiler.resolve())], input=reach.bundle(checked(source)), capture_output=True, env=env)
            if built.returncode or built.stderr:
                raise SystemExit(f'the compiler did not build the test: {built.returncode} {built.stderr.decode(errors="replace")[:300]}')
            test.write_bytes(built.stdout)
            if args.built:
                args.built.parent.mkdir(parents=True, exist_ok=True)
                args.built.write_bytes(built.stdout)
        test.chmod(0o700)
        for k, file in enumerate(args.files):
            place = work / f'text{k}'
            place.mkdir()
            shutil.copyfile(file, place / 'text.alc')
            done = subprocess.run([str(test)], cwd=work, capture_output=True, env=dict(os.environ, REACH_PROGRAMS=str(place), ALCHEM_TEST_TIMEOUT='3600000'))
            print(f'{file}: {"taken or refused" if done.returncode == 0 else f"status {done.returncode}"}')
            if done.returncode:
                lines = [line for line in done.stdout.decode(errors='replace').splitlines() if 'compiler.alc' in line and 'nc_checked' not in line and 'nc_unfit (' not in line]
                print('\n'.join(lines[:12]) if lines else '  (nothing said: not a number written into bytes)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
