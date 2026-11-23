#!/usr/bin/env python3
"""The archives of a release of the compiler, and the check of one.

    release-compilers.py build --compiler build/dev/A2 --output build/release
    release-compilers.py check TARGET build/release

build makes, from a compiler of this tree that has made itself (A1 == A2),
the compiler for each target it builds itself on, each as a program of that
target:

    linux-x86_64     the compiler given
    linux-arm64      scripts/build-arm64.py's compiler, made by itself
    macos-arm64      scripts/build-arm64.py --darwin --macos
    windows-x86_64   scripts/build-windows.py

and writes each into an archive of its own, alchem-compiler-TARGET.tar
(.zip for Windows), with SHA256SUMS beside them. The archives hold the one
file alchem-compiler (alchem-compiler.exe), as it is and with nothing of
when or where they were made: an archive's bytes depend on its compiler
alone, not on the library that would pack it, so the same source gives the
same sums on any machine.

check, run on the target, takes the compiler out of its archive after
checking the archive's sum, and has it compile its own source: it must make
itself again, byte for byte.
"""
import argparse
import hashlib
import io
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ('linux-x86_64', 'linux-arm64', 'macos-arm64', 'windows-x86_64')
# e_machine of the ELF programs: x86-64 and AArch64.
MACHINE = {'linux-x86_64': b'\x3e\x00', 'linux-arm64': b'\xb7\x00'}
MAGIC = {'linux-x86_64': b'\x7fELF', 'linux-arm64': b'\x7fELF', 'macos-arm64': b'\xcf\xfa\xed\xfe', 'windows-x86_64': b'MZ'}


def script(name):
    spec = spec_from_file_location(name.replace('-', '_'), ROOT / 'scripts' / (name + '.py'))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source(target):
    """The compiler's source as the compiler for a target is made from it."""
    if target == 'linux-x86_64':
        return script('bootstrap-alchem-compiler').source_text('functions').encode()
    if target == 'windows-x86_64':
        return script('build-windows').source()
    return script('build-arm64').source(darwin=target == 'macos-arm64')


def member(target):
    return 'alchem-compiler.exe' if target.startswith('windows') else 'alchem-compiler'


def archive_name(target):
    return f'alchem-compiler-{target}' + ('.zip' if target.startswith('windows') else '.tar')


def archive(target, image):
    """The archive of one compiler: its bytes depend on the compiler only."""
    held = io.BytesIO()
    if target.startswith('windows'):
        with zipfile.ZipFile(held, 'w', zipfile.ZIP_STORED) as out:
            entry = zipfile.ZipInfo(member(target), (1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_STORED
            entry.create_system = 3
            entry.external_attr = 0o755 << 16
            out.writestr(entry, image)
        return held.getvalue()
    with tarfile.open(fileobj=held, mode='w', format=tarfile.USTAR_FORMAT) as out:
        entry = tarfile.TarInfo(member(target))
        entry.size, entry.mode, entry.mtime = len(image), 0o755, 0
        out.addfile(entry, io.BytesIO(image))
    return held.getvalue()


def unpacked(target, data):
    held = io.BytesIO(data)
    if target.startswith('windows'):
        with zipfile.ZipFile(held) as packed:
            return packed.read(member(target))
    with tarfile.open(fileobj=held, mode='r:') as packed:
        return packed.extractfile(member(target)).read()


def sums(directory):
    """SHA256SUMS as {archive: sum}."""
    found = {}
    for line in (directory / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split()
        found[name] = digest
    return found


def build(compiler, output):
    output.mkdir(parents=True, exist_ok=True)
    arm, windows = script('build-arm64'), script('build-windows')
    with tempfile.TemporaryDirectory(prefix='alchem-release-') as work:
        work = Path(work)
        arm.build(compiler, work / 'arm-cross')
        arm.build(work / 'arm-cross', work / 'linux-arm64')
        arm.build(compiler, work / 'darwin-cross', darwin=True)
        arm.build(work / 'darwin-cross', work / 'macos-arm64', darwin=True)
        windows.build(compiler, work / 'windows-cross', work / 'windows-x86_64')
        images = {'linux-x86_64': compiler.read_bytes()}
        for target in TARGETS[1:]:
            images[target] = (work / target).read_bytes()
    lines = []
    for target in TARGETS:
        image = images[target]
        if not image.startswith(MAGIC[target]) or (target in MACHINE and image[18:20] != MACHINE[target]):
            raise RuntimeError(f'the compiler made for {target} is no program of {target}')
        data = archive(target, image)
        (output / archive_name(target)).write_bytes(data)
        lines.append(f'{hashlib.sha256(data).hexdigest()}  {archive_name(target)}\n')
        print(f'{archive_name(target)}: {len(image):,} bytes of compiler, {len(data):,} packed')
    (output / 'SHA256SUMS').write_text(''.join(lines))


def check(target, directory):
    data = (directory / archive_name(target)).read_bytes()
    if hashlib.sha256(data).hexdigest() != sums(directory).get(archive_name(target)):
        raise RuntimeError(f'{archive_name(target)} is not what SHA256SUMS names')
    if archive(target, unpacked(target, data)) != data:
        raise RuntimeError(f'{archive_name(target)} is not the archive its compiler makes')
    image = unpacked(target, data)
    text = source(target)
    with tempfile.TemporaryDirectory(prefix='alchem-release-') as work:
        program = Path(work) / member(target)
        program.write_bytes(image)
        program.chmod(0o700)
        made = subprocess.run([str(program)], input=text, capture_output=True, timeout=1800)
    if made.returncode or made.stderr:
        raise RuntimeError(f'the compiler did not build: {made.returncode} {made.stderr.decode(errors="replace").strip()}')
    if made.stdout != image:
        raise RuntimeError(f'the compiler for {target} made {len(made.stdout):,} bytes that are not its own {len(image):,}')
    print(f'{archive_name(target)}: the compiler makes itself again, {len(text):,} source bytes -> {len(image):,} bytes')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    building = commands.add_parser('build')
    building.add_argument('--compiler', type=Path, default=ROOT / 'build/dev/A2')
    building.add_argument('--output', type=Path, default=ROOT / 'build/release')
    checking = commands.add_parser('check')
    checking.add_argument('target', choices=TARGETS)
    checking.add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'build':
            build(args.compiler.resolve(), args.output)
        else:
            check(args.target, args.directory.resolve())
    except (OSError, ValueError, RuntimeError, KeyError, subprocess.TimeoutExpired) as error:
        print(f'E_RELEASE: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
