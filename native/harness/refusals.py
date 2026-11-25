#!/usr/bin/env python3
"""What `alchem check` says of every program the gates know is refused.

The programs are those of REJECTS in the files of harness/. What the pinned
command says of each, its file, line, column and reason, is in
harness/refusals.json.xz by the program's SHA-256, and alchem says the same,
word for word. A program the pinned check accepts and the compiler refuses
(UNSAID: the pinned command then fails to build it and names no place) is
said with the place of the function at least. Nothing is refused with the
one message alone.

    refusals.py --record PINNED   write refusals.json.xz from the pinned command line
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from importlib import import_module
from importlib.util import module_from_spec, spec_from_file_location
import json
import lzma
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'harness/refusals.json.xz'
# How many the pinned check accepts: constants whose arithmetic overflows.
UNSAID = 6


def programs():
    """{the SHA-256 of a refused program: its text}."""
    sys.path.insert(0, str(ROOT / 'harness'))
    found = {}
    for path in sorted((ROOT / 'harness').glob('*.py')):
        if path.stem == 'refusals' or not re.search(r'^REJECTS ?=', path.read_text(), re.M):
            continue
        for item in import_module(path.stem).REJECTS:
            text = item if isinstance(item, str) else item[0] if isinstance(item, (tuple, list)) and item and isinstance(item[0], str) else ''
            if 'defmodule' in text:
                found[hashlib.sha256(text.encode('utf8', 'surrogateescape')).hexdigest()] = text
    return found


def says(command, text, pinned=False):
    """What `command check m.alc` says, the directory left out; '' when it accepts it."""
    with tempfile.TemporaryDirectory(prefix='alchem-refusals-') as top:
        path = Path(top).resolve() / 'm.alc'
        path.write_bytes(text.encode('utf8', 'surrogateescape'))
        env = dict(os.environ) if pinned else {'PATH': '/usr/bin:/bin', 'HOME': top}
        done = subprocess.run([str(command), 'check', str(path)], capture_output=True, env=env, timeout=600)
        return '' if done.returncode == 0 else (done.stdout + done.stderr).decode('utf8', 'replace').strip().replace(str(path), 'm.alc')


def all_of(command, texts, pinned=False):
    with ThreadPoolExecutor(4) as pool:
        return dict(zip(texts, pool.map(lambda text: says(command, text, pinned), texts.values())))


def record(pinned):
    held = all_of(pinned, programs(), True)
    CASES.write_bytes(lzma.compress(json.dumps(held, sort_keys=True).encode(), preset=9))
    print(f'wrote {CASES.name}: {len(held)} programs, {sum(1 for said in held.values() if not said)} the pinned check accepts')


def verify(compiler):
    texts = programs()
    held = json.loads(lzma.decompress(CASES.read_bytes()))
    assert set(held) == set(texts), 'harness/refusals.json.xz is not of these programs: run harness/refusals.py --record'
    spec = spec_from_file_location('build_alchem', ROOT / 'scripts/build-alchem.py')
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix='alchem-refusals-') as top:
        alchem = Path(top) / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))
        seen = all_of(alchem, texts)
    unsaid = 0
    for key, text in texts.items():
        if held[key]:
            assert seen[key] == held[key], (text, seen[key], held[key])
        else:
            unsaid += 1
            assert re.match(r'm\.alc:\d+:\d+: ', seen[key]), (text, seen[key])
    assert unsaid <= UNSAID, unsaid
    print(f'refusals: {len(texts) - unsaid} programs are refused word for word as the pinned command refuses them, and {unsaid} more with a place')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--record':
        record(Path(sys.argv[2]).resolve())
    else:
        verify(Path(sys.argv[1]).resolve())
