#!/usr/bin/env python3
"""The programs of harness/written.json, each built by the Linux x86-64
alchem and run, both on the interpreter (emu-run): every one must give the
pinned compiler's status and output, as the written gate holds them.

    check.py ALCHEM [COUNT]

ALCHEM is the Linux x86-64 alchem (build.sh makes it, as web/alchem); with
COUNT only the first COUNT programs. emu-run is built first.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EMU = HERE / 'emu/target/release/emu-run'


def bounded(command, cwd):
    """A command under the memory and time caps of scripts/bounded.py."""
    return subprocess.run([sys.executable, str(ROOT / 'scripts/bounded.py'), '--memory', '3G', '--seconds', '300', *command],
                          capture_output=True, text=True, errors='replace', cwd=cwd, stdin=subprocess.DEVNULL)


def one(alchem, case):
    with tempfile.TemporaryDirectory(prefix='alchem-playground-') as d:
        (Path(d) / 'm.alc').write_text(case['source'])
        built = bounded([str(EMU), '--file', 'm.alc=/work/m.alc', '--out', f'/work/m={d}/m', str(alchem), 'build', '-o', 'm', 'm.alc'], d)
        if not (Path(d) / 'm').exists():
            got = [built.returncode, built.stdout, built.stderr.replace('/work/', '')]
            return None if got == case['result'] else ('build', got)
        os.chmod(Path(d) / 'm', 0o755)
        ran = bounded([str(EMU), str(Path(d) / 'm')], d)
        got = [ran.returncode, ran.stdout, ran.stderr.replace('/work/', '')]
        return None if got == case['result'] else ('run', got)


def main(alchem, count=None):
    subprocess.run(['cargo', 'build', '--release', '--offline'], cwd=HERE / 'emu', check=True)
    cases = json.loads((ROOT / 'harness/written.json').read_text())[:count]
    with ThreadPoolExecutor(3) as pool:
        found = list(pool.map(lambda case: one(Path(alchem).resolve(), case), cases))
    bad = [(k, f) for k, f in enumerate(found) if f]
    for k, (stage, got) in bad[:20]:
        print(f'--- program {k}, at its {stage}: {got!r:.400}\n    wanted {cases[k]["result"]!r:.400}')
    print(f'{len(cases) - len(bad)} of {len(cases)} programs built and run on the interpreter give what the pinned compiler\'s give')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None))
