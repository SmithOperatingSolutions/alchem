#!/usr/bin/env python3
"""Build the compiler for windows/amd64 (spec/windows.md).

The compiler's source as the bootstrap assembles it, with nc_win() 1,
compiled by a compiler of this tree, is a Linux program that makes Windows
programs (the cross compiler). The same source compiled by the cross
compiler is the Windows compiler, alchem-compiler-windows.exe, which must
make itself again byte for byte.

    build-windows.py --compiler build/dev/A2 --output build/dev/alchem-compiler-windows.exe
                     [--source PATH]

--source also writes the source it compiled, which the Windows compiler is
given on Windows to make itself again.
"""
import argparse
from pathlib import Path
import subprocess
import sys
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
SWITCH = '  def nc_win(): integer do 0 end\n'


def source():
    spec = spec_from_file_location('alchem_bootstrap', ROOT / 'scripts/bootstrap-alchem-compiler.py')
    bootstrap = module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    text = bootstrap.source_text('functions', False)
    if text.count(SWITCH) != 1:
        raise ValueError('the compiler source has no single nc_win()')
    text = text.replace(SWITCH, '  def nc_win(): integer do 1 end\n')
    return bootstrap.compact_identifiers(bootstrap.compact_source(text)).encode()


def compile_with(compiler, text, magic):
    made = subprocess.run([str(compiler)], input=text, capture_output=True, env={'PATH': ''}, timeout=600)
    if made.returncode or made.stderr or made.stdout[:len(magic)] != magic:
        raise RuntimeError(f'the compiler did not build: {made.returncode} {made.stderr.decode(errors="replace").strip()}')
    return made.stdout


def write(path, data):
    path = Path(path)
    staged = path.with_name('.' + path.name + '.new')
    staged.unlink(missing_ok=True)
    staged.write_bytes(data)
    staged.chmod(0o700)
    staged.replace(path)


def build(compiler, cross, output, keep=None):
    text = source()
    if keep:
        write(keep, text)
    write(cross, compile_with(compiler, text, b'\x7fELF'))
    write(output, compile_with(cross, text, b'MZ'))
    return len(text), Path(output).stat().st_size


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/dev/A2')
    parser.add_argument('--cross', type=Path, default=ROOT / 'build/dev/alchem-compiler-windows-cross')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/dev/alchem-compiler-windows.exe')
    parser.add_argument('--source', type=Path)
    args = parser.parse_args()
    try:
        size, image = build(args.compiler.resolve(), args.cross, args.output, args.source)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'E_BUILD: {error}', file=sys.stderr)
        return 1
    print(f'Built {args.output}: {size:,} source bytes -> {image:,} bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
