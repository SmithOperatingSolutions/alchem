#!/usr/bin/env python3
"""The released compiler this tree builds from (pinned-compiler.json).

    pinned-compiler.py [TARGET]

prints the path of the pinned compiler for TARGET (the machine's own by
default: linux-x86_64, linux-arm64, macos-arm64 or windows-x86_64), after
downloading its archive from the release pinned-compiler.json names,
checking the archive's SHA-256 against the one the file holds, and taking
the compiler out of it into build/pinned. An archive already there with the
right sum is not downloaded again.

ALCHEM_PINNED_COMPILER names a compiler to use as it is instead: for a
machine without the network, and for trying a compiler before it is
released. ALCHEM_PINNED_COMPILER_URL is where the releases are, in place of
https://github.com/REPOSITORY/releases/download.

native/README.md says how the pin is moved.
"""
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import platform
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PIN = ROOT / 'pinned-compiler.json'


def release_script():
    spec = spec_from_file_location('release_compilers', ROOT / 'scripts/release-compilers.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def own_target():
    system = {'Linux': 'linux', 'Darwin': 'macos', 'Windows': 'windows'}.get(platform.system(), platform.system().lower())
    machine = {'x86_64': 'x86_64', 'AMD64': 'x86_64', 'aarch64': 'arm64', 'arm64': 'arm64'}.get(platform.machine(), platform.machine())
    return f'{system}-{machine}'


def download(url):
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last = error
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f'could not download {url}: {last}')


def fetch(target=None):
    """The pinned compiler for a target as a program on this machine."""
    given = os.environ.get('ALCHEM_PINNED_COMPILER')
    if given:
        path = Path(given).resolve()
        if not path.is_file():
            raise RuntimeError(f'ALCHEM_PINNED_COMPILER names {given}, which is no file')
        return path
    target = target or own_target()
    release = release_script()
    pin = json.loads(PIN.read_text())
    name = release.archive_name(target)
    if name not in pin['sha256']:
        raise RuntimeError(f'{PIN.name} pins no compiler for {target}')
    directory = ROOT / 'build/pinned' / pin['release']
    directory.mkdir(parents=True, exist_ok=True)
    held = directory / name
    data = held.read_bytes() if held.exists() else b''
    if hashlib.sha256(data).hexdigest() != pin['sha256'][name]:
        base = os.environ.get('ALCHEM_PINNED_COMPILER_URL') or f'https://github.com/{pin["repository"]}/releases/download'
        data = download(f'{base.rstrip("/")}/{pin["release"]}/{name}')
        found = hashlib.sha256(data).hexdigest()
        if found != pin['sha256'][name]:
            raise RuntimeError(f'{name} of {pin["release"]} has the SHA-256 {found}, not the {pin["sha256"][name]} that {PIN.name} pins')
        staged = held.with_name('.' + name + '.new')
        staged.write_bytes(data)
        staged.replace(held)
    program = directory / ('alchem-compiler-' + target + ('.exe' if target.startswith('windows') else ''))
    image = release.unpacked(target, data)
    if not program.exists() or program.read_bytes() != image:
        staged = program.with_name('.' + program.name + '.new')
        staged.write_bytes(image)
        staged.chmod(0o700)
        staged.replace(program)
    return program


def main(arguments):
    if len(arguments) > 1 or (arguments and arguments[0] in ('-h', '--help')):
        print(__doc__)
        return 0 if arguments and arguments[0] in ('-h', '--help') else 2
    try:
        print(fetch(arguments[0] if arguments else None))
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        print(f'E_PINNED: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
