#!/usr/bin/env python3
"""Build `alchem`: the test, run, build, check and new commands
(tools/alchem.alc) with the bundler (tools/alchem-bundle.alc) and the
compiler itself in one program, which compiles by calling the compiler
rather than by running it.

    build-alchem.py --compiler build/dev/A2 --output build/dev/alchem

The program is three modules: tools/alchem.alc; the bundler without its
main, as an imported module may not define one; and AlchemCompiler, the
compiler's source as the bootstrap assembles it (implementations/alchem,
scripts/bootstrap-alchem-compiler.py) without its native_compile entry and
its main. They are bundled as scripts/bundle-alchem.py bundles a program and
compiled by the compiler given, so the compiler inside `alchem` is the one
that built it, from the same source. A compiler entry is never traced and
its arithmetic is never checked; inside `alchem` the compiler's code is an
ordinary module, so everything it relies on holds in a traced program too.
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
BUNDLER_MAIN = '  def main() do\n    System.halt(emit(run(System.argv())))\n  end\nend\n'


def _load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compiler_module():
    """The compiler as the module AlchemCompiler, with no entry and no main."""
    bootstrap = _load('alchem_bootstrap', ROOT / 'scripts/bootstrap-alchem-compiler.py')
    text = bootstrap.source_text('functions', True)
    head, rest = text.split('\n', 1)
    if head != 'defmodule NativeSourceCompiler do':
        raise ValueError('the compiler source is not one NativeSourceCompiler module')
    lines = rest.split('\n')
    kept = [line for line in lines if not line.startswith('def native_compile(') and not line.startswith('def main()')]
    if len(lines) - len(kept) != 2:
        raise ValueError('the compiler source has no single native_compile entry and main')
    return 'defmodule AlchemCompiler do\n' + '\n'.join(kept)


def bundler_module():
    """tools/alchem-bundle.alc without its main."""
    text = (ROOT / 'tools/alchem-bundle.alc').read_text()
    if not text.endswith(BUNDLER_MAIN):
        raise ValueError('tools/alchem-bundle.alc does not end in its main')
    return text[:-len(BUNDLER_MAIN)] + 'end\n'


def program():
    """The bundle of the three modules, with the paths it names those of the repository."""
    bundle = _load('alchem_bundle', ROOT / 'scripts/bundle-alchem.py')
    with tempfile.TemporaryDirectory(prefix='alchem-program-') as directory:
        work = Path(directory)
        (work / 'alchem.alc').write_text((ROOT / 'tools/alchem.alc').read_text())
        (work / 'alchem-bundle.alc').write_text(bundler_module())
        (work / 'alchem-compiler.alc').write_text(compiler_module())
        before = os.getcwd()
        os.chdir(work)
        try:
            # The compiler's module is one file of more than 1 MiB.
            text = bundle.bundle(Path('alchem.alc'), limit=None)
            here = os.getcwd()
        finally:
            os.chdir(before)
        names = {here + '/alchem.alc': 'tools/alchem.alc', here + '/alchem-bundle.alc': 'tools/alchem-bundle.alc',
                 here + '/alchem-compiler.alc': 'implementations/alchem/native-*.alc'}
    head, _, body = text.partition(b'\n')
    count = int(head.split()[1])
    lines = body.split(b'\n', count)
    for index in range(count):
        size, path = lines[index][2:].split(b' ', 1)
        lines[index] = b'# ' + size + b' ' + names[path.decode()].encode()
    return head + b'\n' + b'\n'.join(lines)


def build(compiler, output):
    source = program()
    made = subprocess.run([str(compiler)], input=source, capture_output=True, env={'PATH': ''}, timeout=600)
    if made.returncode or made.stderr or made.stdout[:4] != b'\x7fELF':
        raise RuntimeError(f'the compiler did not build alchem: {made.returncode} {made.stderr.decode(errors="replace").strip()}')
    output = Path(output)
    staged = output.with_name('.' + output.name + '.new')
    staged.write_bytes(made.stdout)
    staged.chmod(0o700)
    staged.replace(output)
    return len(source), len(made.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--compiler', type=Path, default=ROOT / 'build/dev/A2')
    parser.add_argument('--output', type=Path, default=ROOT / 'build/dev/alchem')
    args = parser.parse_args()
    try:
        source, image = build(args.compiler.resolve(), args.output)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'E_BUILD: {error}', file=sys.stderr)
        return 1
    print(f'Built {args.output}: {source:,} source bytes -> {image:,} bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
