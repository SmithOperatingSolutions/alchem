#!/usr/bin/env python3
"""Random programs give what the pinned compiler's give.

harness/programs.json.xz holds cases made by scripts/generate-program-cases.py
from the signatures of the library and the forms of the language, with what
the pinned compiler's program prints for each. Every case prints the same
here, but those listed as refused: programs the pinned compiler takes and the
native one does not, yet. None of these may print anything else, and a
refusal that is mended is struck from the list (the count below), so the list
only gets shorter.
"""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
import json
import lzma
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'harness/programs.json.xz'
# The most cases that may be refused.
REFUSED = 20


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(compiler):
    made = load('program_cases', ROOT / 'scripts/generate-program-cases.py')
    builder = load('build_alchem', ROOT / 'scripts/build-alchem.py')
    held = json.loads(lzma.decompress(CASES.read_bytes()))
    refused = set(held['refused'])
    assert len(refused) <= REFUSED, (len(refused), REFUSED)
    with tempfile.TemporaryDirectory(prefix='alchem-programs-') as top:
        alchem = Path(top) / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))

        def program(item):
            cases, wanted = item
            return made.differing(alchem, [c for c in cases if c[0] not in refused], wanted)
        with ThreadPoolExecutor(4) as pool:
            found = [d for part in pool.map(program, held['programs']) for d in part]
        assert not found, (len(found), found[:3])
        known = [(c, wanted) for cases, wanted in held['programs'] for c in cases if c[0] in refused]
        with ThreadPoolExecutor(4) as pool:
            still = [d for part in pool.map(lambda k: made.differing(alchem, [k[0]], k[1]), known) for d in part]
        assert all('E_COMPILE' in (d[3] or '') for d in still), still
    total = sum(len(cases) for cases, _ in held['programs'])
    print(f'programs: {total - len(refused)} random programs give what the pinned compiler gives; {len(still)} of the {len(refused)} known refusals remain')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
