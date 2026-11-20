#!/usr/bin/env python3
"""The gates of the compiler built for macOS (spec/darwin-arm64.md), run on
macOS on ARM64 with that compiler, a Mach-O made on Linux:

  python3 scripts/build-arm64.py --darwin --compiler build/dev/A2 \\
      --output build/dev/alchem-compiler-darwin
  build/dev/alchem-compiler-darwin < <source> > alchem-compiler-macos

usage: verify-darwin.py COMPILER [--skip-corpus] [GATE...]

ALCHEM_VERIFY_JOBS gates run at a time (3).

- the compiler compiles its own source to itself, byte for byte;
- every example of scripts/upstream-examples.py prints what the pinned
  compiler, built here, prints;
- the gates of harness/ in GATES (or those named) pass.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import inspect
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'build/darwin'

# The gates of harness/ that run on macOS. Of the others that take the native
# compiler: those that cap a program's address space to make its arena
# small (RLIMIT_AS, which macOS neither lowers nor enforces), write to
# /dev/full, which macOS has not, or name files with bytes that are no UTF-8
# (APFS refuses them); time_zones (APFS ignores case), network (connecting to
# port 0 is EADDRNOTAVAIL there), tls (it fakes the year with Linux's
# tools), core_tools (it builds Linux tools), test_driver (alchem run reaches
# its standard input through /proc), and modules and gaps, whose programs of
# megabytes take the compiler for macOS past their time (spec/darwin-arm64.md).
GATES = ['atoms', 'boolean_library', 'clauses', 'closures', 'comprehensions', 'core_modules', 'crypto', 'described',
         'diskstore', 'equality', 'exceptions', 'failures', 'floats', 'forms', 'gen', 'generics', 'graphemes',
         'inference', 'inspection', 'json_library', 'library', 'lists', 'literals', 'long_bodies', 'macros', 'maps',
         'nil_forms', 'nodes', 'operators', 'options', 'ordering', 'packages', 'parsing', 'patterns', 'pipes', 'processes',
         'protocols', 'ranges', 'regex', 'sets', 'sigils', 'speed', 'statements', 'streams', 'string_case',
         'templates', 'testing', 'traces', 'type_words', 'wide']


def load(path, name):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def self_build(compiler):
    source = load(ROOT / 'scripts/build-arm64.py', 'build_arm64').source(True, True)
    made = subprocess.run([str(compiler)], input=source, capture_output=True, timeout=600)
    assert made.returncode == 0 and made.stdout == compiler.read_bytes(), ('self-build', made.returncode, made.stderr[:200])
    print(f'PASS self-build: {len(source):,} source bytes -> {len(made.stdout):,} bytes, identical')


def corpus(compiler):
    examples = load(ROOT / 'scripts/upstream-examples.py', 'upstream_examples')
    pinned = HERE / 'alchem-upstream'
    if not pinned.exists():
        HERE.mkdir(parents=True, exist_ok=True)
        subprocess.run(['go', 'build', '-o', str(pinned), './cmd/alchem'], cwd=examples.U, env=examples.env, check=True)

    def run(command, source, stdin):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            program = Path(d) / 'p'
            if stdin:
                made = subprocess.run(command, input=source.encode(), capture_output=True, timeout=120)
                if made.returncode:
                    return ['reject', made.returncode, '', made.stderr.decode('utf8', 'replace')]
                program.write_bytes(made.stdout)
                program.chmod(0o700)
                command = [str(program)]
            else:
                (Path(d) / 'p.alc').write_text(source)
                command = command + [d + '/p.alc']
            try:
                r = subprocess.run(command, capture_output=True, timeout=120, stdin=subprocess.DEVNULL, cwd=d, env=examples.env)
            except subprocess.TimeoutExpired:
                return ['timeout', 0, '', '']
            return ['ran', r.returncode, r.stdout.decode('utf8', 'replace'), r.stderr.decode('utf8', 'replace')]

    cases = [c for c in examples.cases() if '/'.join(c[0].split('/')[:2]) not in examples.DROPPED]
    with ThreadPoolExecutor(8) as pool:
        wanted = list(pool.map(lambda c: run([str(pinned), 'run'], c[1], False), cases))
        got = list(pool.map(lambda c: run([str(compiler)], c[1], True), cases))
    counted = failed = 0
    for (name, _), u, r in zip(cases, wanted, got):
        if u[1] != 0:
            continue  # the pinned compiler refuses it standalone
        counted += 1
        if r[1] != 0 or r[2] != u[2]:
            failed += 1
            print(f'FAIL {name}: {r[0]} {r[1]} wanted {u[2][:80]!r} got {r[2][:80]!r} {r[3][:120]!r}')
    assert failed == 0, f'{failed} of {counted} examples differ'
    print(f'PASS corpus: {counted} examples print what the pinned compiler prints')


def gate(compiler, name):
    """One gate of harness/, in this process."""
    # macOS keeps the signature it checked for a file, and kills a program
    # written over one that ran: what a gate writes is a new file, with the
    # mode the old one had.
    write = Path.write_bytes

    def fresh(path, data):
        try:
            mode = path.stat().st_mode
            path.unlink()
        except FileNotFoundError:
            mode = None
        made = write(path, data)
        if mode is not None:
            path.chmod(mode & 0o7777)
        return made
    Path.write_bytes = fresh
    # The temporary directory by its real path (/var is a link on macOS):
    # a program gives paths relative to its working directory as getcwd has it.
    tempfile.tempdir = os.path.realpath(tempfile.gettempdir())
    sys.path.insert(0, str(ROOT / 'harness'))
    load(ROOT / 'harness' / f'{name}.py', name).verify(compiler)


def gates(compiler, names, jobs):
    """The gates, each in a process of its own, jobs at a time."""
    def run(name):
        start = time.time()
        done = subprocess.run([sys.executable, __file__, str(compiler), '--gate', name], capture_output=True, text=True)
        return name, done.returncode, time.time() - start, (done.stdout + done.stderr).strip()
    failed = []
    with ThreadPoolExecutor(jobs) as pool:
        for name, status, seconds, said in pool.map(run, names):
            if status:
                failed.append(name)
                print(f'FAIL {name} ({seconds:.0f} s)\n{said[-3000:]}', flush=True)
            else:
                print(f'PASS {name} ({seconds:.0f} s)', flush=True)
    assert not failed, f'gates failed: {" ".join(failed)}'


def main():
    args = sys.argv[1:]
    compiler = Path(args.pop(0)).resolve()
    if args[:1] == ['--gate']:
        gate(compiler, args[1])
        return
    skip = '--skip-corpus' in args
    jobs = int(os.environ.get('ALCHEM_VERIFY_JOBS', '3'))
    names = [a for a in args if a != '--skip-corpus'] or GATES
    assert all(n in GATES for n in names), [n for n in names if n not in GATES]
    self_build(compiler)
    if not skip:
        corpus(compiler)
    gates(compiler, names, jobs)


if __name__ == '__main__':
    main()
