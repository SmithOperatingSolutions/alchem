#!/usr/bin/env python3
"""Compare tools/alchem-lexer.alc with the pinned compiler's lexer on source
files: the tokens and comments of each, written as JSON, must be the same
bytes, and so must the message for a file the lexer refuses. Not a gate.

    compare-lexer.py ALCHEM FILE...

ALCHEM is the alchem that builds the native side (scripts/lexer-dump.alc);
the pinned side is scripts/pinned-lexer, built with the Go module cache
(GOMODCACHE, as the container sets it)."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main(arguments):
    if len(arguments) < 2:
        raise SystemExit(__doc__)
    alchem, files = Path(arguments[0]).resolve(), [str(Path(f).resolve()) for f in arguments[1:]]
    with tempfile.TemporaryDirectory() as d:
        pinned, native = Path(d) / 'pinned', Path(d) / 'native'
        subprocess.run(['go', 'build', '-o', str(pinned), '.'], cwd=ROOT / 'scripts/pinned-lexer', check=True,
                       env=dict(os.environ, GOFLAGS='-mod=mod', GOPROXY='off'))
        subprocess.run([str(alchem), 'build', '-o', str(native), 'lexer-dump.alc'], cwd=ROOT / 'scripts', check=True)
        def dump(program):
            out = subprocess.run([str(program)] + files, capture_output=True, text=True, check=True).stdout
            return {json.loads(line)[0]: line for line in out.splitlines() if line.startswith('[')}
        theirs, ours = dump(pinned), dump(native)
    differ = [f for f in files if theirs.get(f) != ours.get(f)]
    refused = sum(1 for line in theirs.values() if json.loads(line)[1] == 'error')
    for f in differ[:10]:
        print('differs:', f)
    print(f'{len(files) - len(differ)} of {len(files)} files lex as the pinned lexer lexes them ({refused} refused by it)')
    return 1 if differ else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
