#!/usr/bin/env python3
"""The compiler takes a text or refuses it: it does not end any other way.

Two parts, both of scripts/fuzz-compiler.py, which says what is asked of the
compiler and needs no other compiler to say it:

- the texts of harness/fuzz-cases.json, each of which once ended the
  compiler with status 72 (a search found it; the line before each says what
  it is), are taken or refused;
- a search of 2,000 changed programs and 250 made ones with a seed that
  stays: the same cases every time, so a failure here is one of the
  compiler's and is there the next time.

A longer search with a new seed runs every night
(.github/workflows/search.yml)."""
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'harness/fuzz-cases.json'
SEED = 'gate'
COUNT = 2250


def verify(compiler):
    spec = importlib.util.spec_from_file_location('fuzz_compiler', ROOT / 'scripts/fuzz-compiler.py')
    fuzz = importlib.util.module_from_spec(spec)
    sys.modules['fuzz_compiler'] = fuzz
    spec.loader.exec_module(fuzz)
    kept = json.loads(CASES.read_text())
    for case in kept:
        wrong, _ = fuzz.compiled(str(compiler), case['text'].encode('latin-1'), 120, 2 << 30)
        assert wrong is None, (case['what'], wrong)
    said = []
    failed = fuzz.search(Path(compiler), COUNT, SEED, min(4, os.cpu_count() or 1), {'changed', 'made'}, 120, 2 << 30, say=said.append)
    assert failed == 0, '\n'.join(said)
    print(f'PASS fuzz: {len(kept)} texts that ended the compiler are taken or refused; {COUNT} cases of the seed "{SEED}", changed programs and made ones that print what they say')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
