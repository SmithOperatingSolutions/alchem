#!/usr/bin/env python3
"""The front end of alchem (tools/alchem-lexer.alc, tools/alchem-parse.alc)
and its formatter (tools/alchem-format.alc) against the pinned compiler's
lexer, parser and formatter (spec/alchem-front-end.md).

harness/front-end-cases.json.xz holds source texts and, for each, the
SHA-256 of what the pinned lexer, parser and formatter give for it as
JSON: the tokens and comments, the tree ParseSyntax gives or its message,
and the text Format gives or its message (scripts/generate-front-end-cases.py
makes the file). The texts are the repository's source files as they were
when the file was made, broken copies of them (a line dropped, the text cut
short, a sign put in, two lines swapped, a few characters taken out), and
copies written otherwise than the formatter writes them (indentation taken
out, or added with spaces at the ends of lines and none after commas, or
blank lines moved and operators spaced). scripts/lexer-dump.alc,
scripts/parser-dump.alc and scripts/format-dump.alc, built by an alchem the
compiler under test builds, must give the same bytes for every text."""
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
        for name in ('lexer-dump', 'parser-dump', 'format-dump'):
            subprocess.run([str(alchem), 'build', '-o', str(base / name), name + '.alc'], cwd=ROOT / 'scripts', check=True, timeout=1800)
        paths = []
        for k, case in enumerate(held):
            path = base / 'texts' / f'{k:05d}.alc'
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(case['text'].encode('utf8', 'surrogateescape'))
            paths.append(path)
        tokens, trees, formats = (lines(base / name, paths) for name in ('lexer-dump', 'parser-dump', 'format-dump'))
        refused = 0
        for path, case in zip(paths, held):
            assert digest(tokens.get(str(path), b''), path) == case['tokens'], ('tokens', case['name'])
            assert digest(trees.get(str(path), b''), path) == case['tree'], ('tree', case['name'])
            assert digest(formats.get(str(path), b''), path) == case['format'], ('format', case['name'])
            refused += case['refused']
    print(f'PASS front_end: {len(held)} texts lexed, parsed and formatted as the pinned compiler lexes, parses and formats them, byte for byte; {refused} of them refused with its message')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
