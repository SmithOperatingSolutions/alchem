#!/usr/bin/env python3
"""Regenerate harness/front-end-cases.json.xz for the front_end gate
(harness/front_end.py). Not used by normal builds.

    generate-front-end-cases.py PINNED FILE...

The texts are the files given, five broken copies of each, made with a
fixed seed, three copies written otherwise than the formatter writes
them, and up to four copies with a comment put before a line that the
pinned formatter takes; for each, the SHA-256 of what the pinned lexer, parser and formatter
(scripts/pinned-lexer, scripts/pinned-parser, scripts/pinned-format,
scripts/pinned-module: the tree ParseModule lowers, built
with the Go module cache) give for it is written, and what `check` of the
pinned command line PINNED (build/dev/alchem-upstream.bin) says of it as
a file of its own, and with --json: front_end.checked."""
from pathlib import Path
import json
import lzma
import os
import hashlib
import random
import re
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


def unformatted(text):
    """Three copies of a text written otherwise than the formatter writes it."""
    lines = text.split('\n')
    return ['\n'.join(line.lstrip(' ') for line in lines),
            '\n'.join(('      ' + line + '   ' if line.strip() else line) for line in lines).replace(', ', ','),
            '\n'.join(re.sub(r' (\|>|<>|\+\+|==|=|->) ', r'  \1  ', line) + ('\n' if k % 5 == 0 else '') for k, line in enumerate(lines) if line.strip())]


def main(arguments):
    if len(arguments) < 2:
        raise SystemExit(__doc__)
    pinned, arguments = Path(arguments[0]).resolve(), arguments[1:]
    rng = random.Random(7)
    named, sources = [], []
    for name in arguments:
        text = Path(name).read_bytes().decode('utf8', 'surrogateescape')
        if not text or len(text) > 60000:
            continue
        shown = os.path.relpath(name, ROOT)
        sources.append((shown, text))
        named.append((shown, text))
        named += [(f'{shown} (broken {k + 1})', b) for k, b in enumerate(broken(text, rng))]
        named += [(f'{shown} (unformatted {k + 1})', u) for k, u in enumerate(unformatted(text))]
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        for tool in ('pinned-lexer', 'pinned-parser', 'pinned-format', 'pinned-module'):
            subprocess.run(['go', 'build', '-o', str(base / tool), '.'], cwd=ROOT / 'scripts' / tool, check=True, env=dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off'))

        def written(texts, folder):
            paths = []
            for k, text in enumerate(texts):
                path = base / folder / f'{k:05d}.alc'
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(text.encode('utf8', 'surrogateescape'))
                paths.append(path)
            return paths

        # Four copies of each source with a comment put before one of its
        # lines, at that line's indentation, of those the pinned formatter
        # takes: where it keeps comments (#40, #42).
        candidates = []
        for shown, text in sources:
            lines = text.split('\n')
            for i in range(1, len(lines) - 1, max(1, (len(lines) - 2) // 24)):
                pad = len(lines[i]) - len(lines[i].lstrip(' '))
                candidates.append((shown, '\n'.join(lines[:i] + [' ' * pad + '# a comment here'] + lines[i:])))
        tried_paths = written([text for _, text in candidates], 'candidates')
        tried = front_end.lines(base / 'pinned-format', tried_paths)
        taken = {}
        for path, (shown, text) in zip(tried_paths, candidates):
            if json.loads(tried[str(path)].decode('utf8', 'replace'))[1] != 'error':
                taken.setdefault(shown, []).append(text)
        for shown, _ in sources:
            found = taken.get(shown, [])
            for k, text in enumerate(found[::max(1, len(found) // 4)][:4]):
                named.append((f'{shown} (commented {k + 1})', text))
        paths = written([text for _, text in named], 'texts')
        subprocess.run([sys.executable, str(ROOT / 'scripts/pinned-loaded.py'), str(base / 'pinned-loaded')], check=True, env=dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off'))
        loads = front_end.loaded(base / 'pinned-loaded', [text for _, text in named], True)
        skipped = hashlib.sha256(b'["x.alc","skipped"]\n').hexdigest()
        checks = front_end.checked(pinned, [text for _, text in named], True)
        described = front_end.checked(pinned, [text for _, text in named], True, ('--json',))
        tokens, trees, formats, modules = (front_end.lines(base / tool, paths) for tool in ('pinned-lexer', 'pinned-parser', 'pinned-format', 'pinned-module'))
        held = []
        for path, (shown, text), check, description, load in zip(paths, named, checks, described, loads):
            tree = trees[str(path)]
            held.append({'name': shown, 'text': text, 'tokens': front_end.digest(tokens[str(path)], path), 'tree': front_end.digest(tree, path),
                         'format': front_end.digest(formats[str(path)], path),
                         'module': front_end.digest(modules[str(path)], path),
                         'check': check, 'described': description, 'loaded': load, 'skipped': skipped,
                         'refused': 1 if json.loads(tree.decode('utf8', 'replace'))[1] == 'error' else 0})
    front_end.CASES.write_bytes(lzma.compress(json.dumps(held).encode('utf8', 'surrogateescape'), preset=9))
    print(f'wrote {front_end.CASES.relative_to(ROOT)}: {len(held)} texts, {sum(c["refused"] for c in held)} refused, {front_end.CASES.stat().st_size} bytes')


if __name__ == '__main__':
    main(sys.argv[1:])
