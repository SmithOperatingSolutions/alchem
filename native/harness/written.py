#!/usr/bin/env python3
"""Written programs give what the pinned compiler's give.

harness/written.json holds programs the native compiler once refused or got
wrong, found by random search and reduced, with the status and the output of
the pinned compiler's program (scripts/generate-written-cases.py). Each must be
the same here.
"""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(compiler):
    made = load('written_cases', ROOT / 'scripts/generate-written-cases.py')
    builder = load('build_alchem', ROOT / 'scripts/build-alchem.py')
    cases = json.loads(made.CASES.read_text())
    assert len(cases) >= 234, len(cases)
    with tempfile.TemporaryDirectory(prefix='alchem-written-') as top:
        alchem = Path(top) / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))
        with ThreadPoolExecutor(4) as pool:
            found = list(pool.map(lambda case: made.result(alchem, case['source']), cases))
    wrong = [(case, given) for case, given in zip(cases, found) if given != case['result']]
    assert not wrong, (len(wrong), wrong[:3])
    print(f'written: {len(cases)} programs give what the pinned compiler gives')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
