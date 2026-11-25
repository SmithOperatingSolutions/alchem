#!/usr/bin/env python3
"""Record what the pinned compiler's program prints for each program of
harness/written.json.

    generate-written-cases.py PINNED            record the results again
    generate-written-cases.py PINNED FILE...    add the programs of these files
"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'harness/written.json'


def result(alchem, source):
    """The program's status and what it writes, with no path in it."""
    with tempfile.TemporaryDirectory(prefix='alchem-written-') as top:
        base = Path(top).resolve()
        (base / 'm.alc').write_text(source)
        done = subprocess.run([str(alchem), 'run', 'm.alc'], capture_output=True, text=True, cwd=base, timeout=600)
        return [done.returncode, done.stdout, done.stderr.replace(f'{base}/', '')]


def main(pinned, added):
    held = [case['source'] for case in json.loads(CASES.read_text())] if CASES.exists() else []
    held += [text for text in (Path(path).read_text() for path in added) if text not in held]
    with ThreadPoolExecutor(4) as pool:
        found = list(pool.map(lambda source: result(Path(pinned).resolve(), source), held))
    CASES.write_text(json.dumps([{'source': s, 'result': r} for s, r in zip(held, found)], indent=1, ensure_ascii=False) + '\n')
    print(f'{len(held)} programs')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
