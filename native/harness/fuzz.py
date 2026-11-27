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
(.github/workflows/search.yml).

A third part is what says where the compiler ends when a search finds such
a text (scripts/compiler-where.py): a compiler entry is not traced, and one
whose source has a function native_traced is. A small entry that makes a
byte of a number that is none ends with status 72 and no word, and with
native_traced says where; the compiler built so makes of a program what the
compiler makes of it."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

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
    entry = 'defmodule C do\n  def native_compile(source: bytes): bytes do\n    b[Enum.count(source) + 253]\n  end\n%s  def main() do\n    System.halt(0)\n  end\nend\n'
    with tempfile.TemporaryDirectory(prefix='alchem-fuzz-entry-') as top:
        def made(text, name):
            built = subprocess.run([str(compiler)], input=text.encode(), capture_output=True, env={'PATH': ''}, timeout=600)
            assert (built.returncode, built.stderr) == (0, b''), (name, built.returncode, built.stderr[:200])
            path = Path(top) / name
            path.write_bytes(built.stdout)
            path.chmod(0o700)
            return path
        def given(program, data):
            done = subprocess.run([str(program)], input=data, capture_output=True, env={'PATH': ''}, timeout=600)
            return done.returncode, done.stdout, done.stderr
        plain, traced = made(entry % '', 'plain'), made(entry % '  def native_traced(): integer do 1 end\n', 'traced')
        assert given(plain, b'ab') == (0, b'\xff', b'') == given(traced, b'ab')
        assert given(plain, b'abc') == (72, b'', b'')
        assert given(traced, b'abc') == (2, b'', b'<stdin>:3:7: byte must be between 0 and 255\n  at C.native_compile (<stdin>:3)\n'), given(traced, b'abc')
        spec = importlib.util.spec_from_file_location('compiler_reach', ROOT / 'scripts/compiler-reach.py')
        reach = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reach)
        whole = made(reach.assembled(traced=True)[0], 'compiler')
        program = (ROOT / 'examples/invoice-functions.alc').read_bytes()
        assert given(whole, program) == given(compiler, program) and given(whole, program)[0] == 0
        assert given(whole, b'defmodule M do\n  def main() do\n    x = \n  end\nend\n')[0] == 65
    said = []
    failed = fuzz.search(Path(compiler), COUNT, SEED, min(4, os.cpu_count() or 1), {'changed', 'made'}, 120, 2 << 30, say=said.append)
    assert failed == 0, '\n'.join(said)
    print(f'PASS fuzz: {len(kept)} texts that ended the compiler are taken or refused; a compiler entry with native_traced says where it ends, and the compiler built so compiles alike; {COUNT} cases of the seed "{SEED}", changed programs and made ones that print what they say')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
