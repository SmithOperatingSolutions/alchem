#!/usr/bin/env python3
"""The upstream examples on Windows (spec/windows.md).

    windows-examples.py prepare DIR [--compiler build/dev/A2]
    windows-examples.py check DIR COMPILER.exe [--jobs N] [--wine]

prepare (on Linux) writes each example of scripts/upstream-examples.py that
the native Linux compiler builds and runs to exit 0 into DIR as NNNN.alc,
with what it printed as NNNN.out and its name in names.txt; the examples
whose output is not the same on Windows (SKIPPED) are left out. What
Linux prints is what the pinned compiler's windows/amd64 programs print for
all the others, under Wine (scripts/run-windows).

check (on Windows) builds each with the Windows compiler, runs it in an
empty directory and compares what it prints; it ends 1 if any differs.
With --wine it runs them under Wine (scripts/run-windows) on Linux."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]

# Examples whose output on Windows is not Linux's.
SKIPPED = {
    # They run Unix programs (echo, cat, sleep), which Windows does not have
    # as programs; the pinned compiler's Windows programs fail too.
    'lib/System/System.cmd/1', 'lib/Port/Port.close/1', 'lib/Port/Port.command/1', 'lib/Port/Port.info/1',
    'lib/Port/Port.kill/1', 'lib/Port/Port.monitor/1', 'lib/Port/Port.open/1', 'lib/Port/Port.os_pid/1',
    # Under Wine a symbolic link Windows makes does not resolve, for the
    # pinned compiler's program too.
    'lib/File/File.ln_s/1',
    # Named time zones: Windows has no zone files, and the pinned program
    # carries Go's own database (time/tzdata), which these do not yet
    # (spec/windows.md).
    'lib/DateTime/DateTime.from_naive/1', 'lib/DateTime/DateTime.now/1', 'lib/DateTime/DateTime.shift/1',
    'lib/DateTime/DateTime.shift_zone/1', 'lib/DateTime/DateTime.shift_zone!/1',
    # A copy of the program fails in earnest (fork), still to do
    # (spec/windows.md).
    'lib/Process/Process.report/1',
}


def load_examples():
    import importlib.util
    spec = importlib.util.spec_from_file_location('upstream_examples', ROOT / 'scripts/upstream-examples.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(out, compiler):
    examples = load_examples()
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    cases = [(n, s) for n, s in examples.cases() if not n.startswith('syntax/extern') and n not in SKIPPED]
    with ThreadPoolExecutor(os.cpu_count() or 4) as pool:
        results = list(pool.map(lambda c: examples.native(c[1], str(compiler)), cases))
    names = []
    for (name, source), result in zip(cases, results):
        if result[0] != 'ran' or result[1] != 0:
            continue
        number = f'{len(names):04}'
        (out / (number + '.alc')).write_text(source)
        (out / (number + '.out')).write_text(result[2])
        names.append(name)
    (out / 'names.txt').write_text(''.join(n + '\n' for n in names))
    print(f'{len(names)} examples in {out}')


def check_one(directory, compiler, number, name, runner):
    source = (directory / (number + '.alc')).read_bytes()
    want = (directory / (number + '.out')).read_bytes()
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        built = subprocess.run([*runner, compiler], input=source, capture_output=True, timeout=300)
        if built.returncode:
            return name, f'did not build: {built.stderr.decode(errors="replace")[:300]}'
        program = d / 'p.exe'
        program.write_bytes(built.stdout)
        run = d / 'run'
        run.mkdir()
        try:
            got = subprocess.run([*runner, str(program)], capture_output=True, timeout=60, cwd=run, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            return name, 'timed out'
        if got.returncode != 0 or got.stdout != want:
            return name, (f'exit {got.returncode}\n  want {want[:300]!r}\n  got  {got.stdout[:300]!r}\n'
                          f'  stderr {got.stderr.decode(errors="replace")[:300]!r}')
    return name, None


def check(directory, compiler, jobs, runner):
    directory = Path(directory)
    compiler = str(Path(compiler).resolve())
    names = (directory / 'names.txt').read_text().split('\n')[:-1]
    with ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(lambda i: check_one(directory, compiler, f'{i:04}', names[i], runner), range(len(names))))
    failed = [(n, why) for n, why in results if why]
    for name, why in failed:
        print(f'FAIL {name}: {why}')
    print(f'{len(names) - len(failed)} of {len(names)} examples print on Windows what they print on Linux')
    return 1 if failed else 0


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == 'prepare':
        compiler = ROOT / 'build/dev/A2'
        if '--compiler' in args:
            compiler = Path(args[args.index('--compiler') + 1])
        prepare(args[1], compiler.resolve())
        return 0
    if len(args) >= 3 and args[0] == 'check':
        jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 4
        runner = [str(ROOT / 'scripts/run-windows')] if '--wine' in args else []
        return check(args[1], args[2], jobs, runner)
    sys.exit(__doc__)


if __name__ == '__main__':
    raise SystemExit(main())
