#!/usr/bin/env python3
"""The front end of alchem (tools/alchem-lexer.alc, tools/alchem-parse.alc)
against the pinned compiler's lexer and parser (spec/alchem-front-end.md).

harness/front-end-cases.json.xz holds source texts and, for each, the
SHA-256 of what the pinned lexer and the pinned parser give for it as
JSON: the tokens and comments, and the tree ParseSyntax gives or its
message (scripts/generate-front-end-cases.py makes the file). The texts
are the repository's source files as they were when the file was made,
and broken copies of them: a line dropped, the text cut short, a sign
put in, two lines swapped, a few characters taken out. scripts/lexer-dump.alc
and scripts/parser-dump.alc, built by an alchem the compiler under test
builds, must give the same bytes for every text."""
from pathlib import Path
import hashlib
import json
import lzma
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).resolve().parent / 'front-end-cases.json.xz'


def cases():
    return json.loads(lzma.decompress(CASES.read_bytes()))


def lines(program, paths):
    """What a dump gives for each file, by the file's name."""
    out = subprocess.run([str(program)] + [str(p) for p in paths], capture_output=True, timeout=1800, check=True).stdout
    found = {}
    for line in out.split(b'\n'):
        if line.startswith(b'["'):
            found[json.loads(line.decode('utf8', 'replace'))[0]] = line
    return found


def digest(line, path):
    """The SHA-256 of a dump's line with the file's name taken out."""
    return hashlib.sha256(line.replace(json.dumps(str(path)).encode(), b'"FILE"', 1)).hexdigest()


def verify(compiler):
    held = cases()
    spec = spec_from_file_location('build_alchem', ROOT / 'scripts/build-alchem.py')
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix='alchem-front-end-') as top:
        base = Path(top)
        alchem = base / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))
        for name in ('lexer-dump', 'parser-dump'):
            subprocess.run([str(alchem), 'build', '-o', str(base / name), name + '.alc'], cwd=ROOT / 'scripts', check=True, timeout=1800)
        paths = []
        for k, case in enumerate(held):
            path = base / 'texts' / f'{k:05d}.alc'
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(case['text'].encode('utf8', 'surrogateescape'))
            paths.append(path)
        tokens, trees = lines(base / 'lexer-dump', paths), lines(base / 'parser-dump', paths)
        refused = 0
        for path, case in zip(paths, held):
            assert digest(tokens.get(str(path), b''), path) == case['tokens'], ('tokens', case['name'])
            assert digest(trees.get(str(path), b''), path) == case['tree'], ('tree', case['name'])
            refused += case['refused']
    print(f'PASS front_end: {len(held)} texts lexed and parsed as the pinned compiler lexes and parses them, byte for byte; {refused} of them refused with its message')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
