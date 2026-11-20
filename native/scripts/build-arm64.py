#!/usr/bin/env python3
"""Build the compiler for linux/arm64 (spec/arm64.md): the compiler's source as
the bootstrap assembles it, with nc_arm() 1, compiled by a compiler of this
tree. It runs where that compiler runs and makes ARM64 programs.

    build-arm64.py --compiler build/dev/A2 --output build/dev/alchem-compiler-arm64

With --darwin it makes macOS programs (spec/darwin-arm64.md); --macos PATH
then has that compiler compile its own source to PATH too: the compiler as
a macOS program, which scripts/verify-darwin.py checks on macOS.
"""
import argparse
from pathlib import Path
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
SWITCH = '  def nc_arm(): integer do 0 end\n'


def source(pic=False, darwin=False):
    spec = spec_from_file_location('alchem_bootstrap', ROOT / 'scripts/bootstrap-alchem-compiler.py')
    bootstrap = module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    text = bootstrap.source_text('functions', False)
    if text.count(SWITCH) != 1:
        raise ValueError('the compiler source has no single nc_arm()')
    text = text.replace(SWITCH, '  def nc_arm(): integer do %d end\n' % (3 if darwin else 2 if pic else 1))
    return bootstrap.compact_identifiers(bootstrap.compact_source(text)).encode()


def build(compiler, output, pic=False, darwin=False):
    text = source(pic, darwin)
    made = subprocess.run([str(compiler)], input=text, capture_output=True, env={'PATH': ''}, timeout=1800)
    if made.returncode or made.stderr or made.stdout[:4] not in (b'\x7fELF', b'\xcf\xfa\xed\xfe'):
        raise RuntimeError(f'the compiler did not build: {made.returncode} {made.stderr.decode(errors="replace").strip()}')
    output = Path(output)
    staged = output.with_name('.' + output.name + '.new')
    staged.write_bytes(made.stdout)
    staged.chmod(0o700)
    staged.replace(output)
    return len(text), len(made.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/dev/A2')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/dev/alchem-compiler-arm64')
    parser.add_argument('--pic', action='store_true', help='make position-independent programs')
    parser.add_argument('--darwin', action='store_true', help='make macOS programs (Mach-O, libSystem)')
    parser.add_argument('--macos', type=Path, help='with --darwin: the compiler as a macOS program, made by the one built')
    args = parser.parse_args()
    if args.macos and not args.darwin:
        parser.error('--macos needs --darwin')
    try:
        size, image = build(args.compiler.resolve(), args.output, args.pic, args.darwin)
        print(f'Built {args.output}: {size:,} source bytes -> {image:,} bytes')
        if args.macos:
            size, image = build(args.output.resolve(), args.macos, darwin=True)
            print(f'Built {args.macos}: {size:,} source bytes -> {image:,} bytes (macOS)')
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'E_BUILD: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
