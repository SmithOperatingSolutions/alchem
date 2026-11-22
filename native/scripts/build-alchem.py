#!/usr/bin/env python3
"""Build `alchem`: the test, run, build, check and new commands
(tools/alchem.alc) with the bundler (tools/alchem-bundle.alc) and the
compiler itself in one program, which compiles by calling the compiler
rather than by running it, and the commands that print documentation
(tools/alchem-guide.alc, spec/alchem-commands.md). --version is the version
`alchem version` prints.

    build-alchem.py --compiler build/dev/A2 --output build/dev/alchem

With --darwin the compiler inside makes macOS programs (spec/darwin-arm64.md):
built by the compiler for macOS that runs on macOS, `alchem` is a macOS
program whose test, run and build commands work there. With --windows it
makes Windows programs (spec/windows.md): built by the Windows cross
compiler (build-windows.py), `alchem.exe` is a Windows program whose
commands work there.

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
import re
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


def compiler_module(darwin=False, windows=False):
    """The compiler as the module AlchemCompiler, with no entry and no main."""
    bootstrap = _load('alchem_bootstrap', ROOT / 'scripts/bootstrap-alchem-compiler.py')
    text = bootstrap.source_text('functions', False)
    if windows:
        switch = '  def nc_win(): integer do 0 end\n'
        if text.count(switch) != 1:
            raise ValueError('the compiler source has no single nc_win()')
        text = text.replace(switch, '  def nc_win(): integer do 1 end\n')
    if darwin:
        switch = '  def nc_arm(): integer do 0 end\n'
        if text.count(switch) != 1:
            raise ValueError('the compiler source has no single nc_arm()')
        text = text.replace(switch, '  def nc_arm(): integer do 3 end\n')
    text = bootstrap.compact_identifiers(bootstrap.compact_source(text))
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


def guide_module(version, platform):
    """tools/alchem-guide.alc saying the version it is and the system and
    machine its programs are for."""
    text = (ROOT / 'tools/alchem-guide.alc').read_text()
    for name, value in (('version', version), ('platform', platform)):
        line = '  def %s(): string do "%s" end\n' % (name, {'version': 'devel', 'platform': 'linux/amd64'}[name])
        if text.count(line) != 1:
            raise ValueError(f'tools/alchem-guide.alc has no single {name}()')
        if not re.fullmatch(r'[A-Za-z0-9._+/-]+', value):
            raise ValueError(f'{name} {value!r} is not one a string holds as it is')
        text = text.replace(line, '  def %s(): string do "%s" end\n' % (name, value))
    return text


def platform_of(compiler, darwin=False, windows=False):
    """The system and machine of the programs a compiler makes, as the
    pinned command names them."""
    if windows:
        return 'windows/amd64'
    if darwin:
        return 'darwin/arm64'
    probe = subprocess.run([str(compiler)], input=b'defmodule M do\n  def main() do\n    System.halt(0)\n  end\nend\n', capture_output=True, env={'PATH': ''}, timeout=120)
    image = probe.stdout
    if image[:4] == b'\xcf\xfa\xed\xfe':
        return 'darwin/arm64'
    if image[:2] == b'MZ':
        return 'windows/amd64'
    if image[:4] == b'\x7fELF' and image[18:20] == b'\xb7\x00':
        return 'linux/arm64'
    if image[:4] == b'\x7fELF' and image[18:20] == b'\x3e\x00':
        return 'linux/amd64'
    raise RuntimeError(f'{compiler} made no program of a known kind')


def program(darwin=False, windows=False, version='devel', platform='linux/amd64'):
    """The bundle of the three modules, with the paths it names those of the repository."""
    bundle = _load('alchem_bundle', ROOT / 'scripts/bundle-alchem.py')
    with tempfile.TemporaryDirectory(prefix='alchem-program-') as directory:
        work = Path(directory)
        (work / 'alchem.alc').write_text((ROOT / 'tools/alchem.alc').read_text())
        (work / 'alchem-bundle.alc').write_text(bundler_module())
        (work / 'alchem-compiler.alc').write_text(compiler_module(darwin, windows))
        (work / 'alchem-guide.alc').write_text(guide_module(version, platform))
        (work / 'alchem-guide-data.alc').write_text((ROOT / 'tools/alchem-guide-data.alc').read_text())
        (work / 'alchem-sources.alc').write_text((ROOT / 'tools/alchem-sources.alc').read_text())
        before = os.getcwd()
        os.chdir(work)
        try:
            # The compiler's module is one file of more than 1 MiB.
            text = bundle.bundle(Path('alchem.alc'), limit=None)
            here = os.getcwd()
        finally:
            os.chdir(before)
        names = {here + '/alchem.alc': 'tools/alchem.alc', here + '/alchem-bundle.alc': 'tools/alchem-bundle.alc',
                 here + '/alchem-compiler.alc': 'implementations/alchem/native-*.alc',
                 here + '/alchem-guide.alc': 'tools/alchem-guide.alc', here + '/alchem-guide-data.alc': 'tools/alchem-guide-data.alc',
                 here + '/alchem-sources.alc': 'tools/alchem-sources.alc'}
    head, _, body = text.partition(b'\n')
    count = int(head.split()[1])
    lines = body.split(b'\n', count)
    for index in range(count):
        size, path = lines[index][2:].split(b' ', 1)
        lines[index] = b'# ' + size + b' ' + names[path.decode()].encode()
    return head + b'\n' + b'\n'.join(lines)


def build(compiler, output, darwin=False, windows=False, version='devel'):
    source = program(darwin, windows, version, platform_of(compiler, darwin, windows))
    made = subprocess.run([str(compiler)], input=source, capture_output=True, env={'PATH': ''}, timeout=600)
    if made.returncode or made.stderr or made.stdout[:4] not in (b'\x7fELF', b'\xcf\xfa\xed\xfe') and made.stdout[:2] != b'MZ':
        raise RuntimeError(f'the compiler did not build alchem: {made.returncode} {made.stderr.decode(errors="replace").strip()}')
    if windows and made.stdout[:2] != b'MZ':
        # A compiler for another system would make an alchem that takes
        # itself for Windows' and is not: --compiler must be the cross compiler.
        raise RuntimeError(f'--windows needs a compiler that makes Windows programs: {compiler} made none')
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
    parser.add_argument('--darwin', action='store_true', help='the compiler inside makes macOS programs')
    parser.add_argument('--windows', action='store_true', help='the compiler inside makes Windows programs (build with the Windows cross compiler)')
    parser.add_argument('--version', default='devel', help='the version `alchem version` prints')
    args = parser.parse_args()
    try:
        source, image = build(args.compiler.resolve(), args.output, args.darwin, args.windows, args.version)
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f'E_BUILD: {error}', file=sys.stderr)
        return 1
    print(f'Built {args.output}: {source:,} source bytes -> {image:,} bytes')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
