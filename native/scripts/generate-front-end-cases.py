#!/usr/bin/env python3
"""Regenerate harness/front-end-cases.json.xz for the front_end gate
(harness/front_end.py). Not used by normal builds.

    generate-front-end-cases.py FILE...

The texts are the files given and five broken copies of each, made with a
fixed seed; for each, the SHA-256 of what the pinned lexer and parser
(scripts/pinned-lexer, scripts/pinned-parser, built with the Go module
cache) give for it is written."""
from pathlib import Path
import json
import lzma
import os
import random
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
import front_end

SIGNS = ['(', ')', '[', ']', '{', '}', 'do', 'end', ',', '=', '->', '"', '%', '@', '|', '#{', '~r/', '\\\\', ':', '!', '.']


def broken(text, rng):
    """Five broken copies of a text."""
    lines = text.split('\n')
    out = []
    for kind in range(5):
        if kind == 0 and len(lines) > 3:
            i = rng.randrange(1, len(lines) - 1)
            out.append('\n'.join(lines[:i] + lines[i + 1:]))
        elif kind == 1:
            out.append(text[:rng.randrange(len(text))])
        elif kind == 2:
            i = rng.randrange(len(text))
            out.append(text[:i] + rng.choice(SIGNS) + text[i:])
        elif kind == 3 and len(lines) > 3:
            i, j = rng.randrange(1, len(lines) - 1), rng.randrange(1, len(lines) - 1)
            swapped = lines[:]
            swapped[i], swapped[j] = swapped[j], swapped[i]
            out.append('\n'.join(swapped))
        else:
            i = rng.randrange(len(text))
            out.append(text[:i] + text[min(len(text), i + rng.randrange(1, 12)):])
    return out


def main(arguments):
    if not arguments:
        raise SystemExit(__doc__)
    rng = random.Random(7)
    named = []
    for name in arguments:
        text = Path(name).read_bytes().decode('utf8', 'surrogateescape')
        if not text or len(text) > 60000:
            continue
        shown = os.path.relpath(name, ROOT)
        named.append((shown, text))
        named += [(f'{shown} (broken {k + 1})', b) for k, b in enumerate(broken(text, rng))]
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        for tool in ('pinned-lexer', 'pinned-parser'):
            subprocess.run(['go', 'build', '-o', str(base / tool), '.'], cwd=ROOT / 'scripts' / tool, check=True, env=dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off'))
        paths = []
        for k, (_, text) in enumerate(named):
            path = base / 'texts' / f'{k:05d}.alc'
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(text.encode('utf8', 'surrogateescape'))
            paths.append(path)
        tokens, trees = front_end.lines(base / 'pinned-lexer', paths), front_end.lines(base / 'pinned-parser', paths)
        held = []
        for path, (shown, text) in zip(paths, named):
            tree = trees[str(path)]
            held.append({'name': shown, 'text': text, 'tokens': front_end.digest(tokens[str(path)], path), 'tree': front_end.digest(tree, path),
                         'refused': 1 if json.loads(tree.decode('utf8', 'replace'))[1] == 'error' else 0})
    front_end.CASES.write_bytes(lzma.compress(json.dumps(held).encode('utf8', 'surrogateescape'), preset=9))
    print(f'wrote {front_end.CASES.relative_to(ROOT)}: {len(held)} texts, {sum(c["refused"] for c in held)} refused, {front_end.CASES.stat().st_size} bytes')


if __name__ == '__main__':
    main(sys.argv[1:])
