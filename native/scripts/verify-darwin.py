#!/usr/bin/env python3
"""The gates of the compiler built for macOS (spec/darwin-arm64.md), run on
macOS on ARM64 with that compiler, a Mach-O made on Linux:

  python3 scripts/build-arm64.py --darwin --compiler build/dev/A2 \\
      --output build/dev/alchem-compiler-darwin
  build/dev/alchem-compiler-darwin < <source> > alchem-compiler-macos

usage: verify-darwin.py COMPILER [--skip-corpus] [--shard K/N] [GATE...]

ALCHEM_VERIFY_JOBS gates run at a time (3). With --shard K/N this runs the
K-th of N parts, which runners run side by side: the first part checks the
self-build and the corpus, and the gates are shared out by their time
(SECONDS).

- the compiler compiles its own source to itself, byte for byte;
- every example of scripts/upstream-examples.py prints what the pinned
  compiler, built here, prints;
- the gates of harness/ in GATES (or those named) pass.
"""
from concurrent.futures import ThreadPoolExecutor
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import inspect
import errno
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT / 'build' / sys.platform

# The gates of harness/ that run on macOS. Of the others that take the native
# compiler: those that cap a program's address space to make its arena
# small (RLIMIT_AS, which macOS neither lowers nor enforces), write to
# /dev/full, which macOS has not, or name files with bytes that are no UTF-8
# (APFS refuses them); time_zones (APFS ignores case), network (connecting to
# port 0 is EADDRNOTAVAIL there), tls (it fakes the year with Linux's
# tools), core_tools (it builds Linux tools), test_driver (alchem run reaches
# its standard input through /proc), and modules and gaps, whose programs of
# megabytes take the compiler for macOS past their time (spec/darwin-arm64.md).
GATES = ['atoms', 'binary', 'boolean_library', 'clauses', 'closures', 'commands', 'comprehensions', 'core_modules', 'crypto',
         'described',
         'diskstore', 'front_end', 'equality', 'exceptions', 'facts', 'failures', 'fetch', 'fixtures', 'floats', 'forms', 'gen', 'generics', 'graphemes',
         'inference', 'inspection', 'json_library', 'library', 'lists', 'literals', 'long_bodies', 'lsp', 'macros', 'maps',
         'nil_forms', 'nodes', 'operators', 'options', 'ordering', 'packages', 'parsing', 'patterns', 'pipes', 'processes',
         'programs', 'protocols', 'ranges', 'refusals', 'regex', 'replaced', 'sets', 'sigils', 'speed', 'statements', 'streams', 'string_case',
         'templates', 'testing', 'traces', 'type_words', 'wide']


# What each gate took, in seconds, on a runner of macos-15 running three at a
# time; a gate not named takes about 30. SECONDS['corpus'] is the self-build
# and the corpus.
SECONDS = {'front_end': 2169, 'ordering': 1242, 'core_modules': 1185, 'corpus': 840, 'graphemes': 601,
           'fixtures': 585, 'lists': 581, 'programs': 488, 'type_words': 456, 'boolean_library': 397,
           'replaced': 320, 'nodes': 298, 'library': 284, 'maps': 278, 'fetch': 270, 'lsp': 263, 'string_case': 198,
           'testing': 193, 'binary': 188, 'processes': 166, 'failures': 159, 'commands': 150, 'refusals': 150,
           'regex': 136, 'nil_forms': 129, 'options': 113, 'streams': 108, 'comprehensions': 94, 'json_library': 93,
           'long_bodies': 90, 'described': 83, 'sets': 76, 'macros': 75, 'floats': 69, 'gen': 68, 'crypto': 64,
           'speed': 62, 'clauses': 57, 'sigils': 44, 'protocols': 31, 'exceptions': 27, 'parsing': 25,
           'operators': 23, 'closures': 20, 'diskstore': 20, 'equality': 19, 'templates': 19, 'patterns': 12,
           'generics': 11, 'inference': 9, 'pipes': 8, 'literals': 7, 'ranges': 6, 'forms': 4, 'packages': 4,
           'atoms': 3, 'statements': 3, 'wide': 3, 'inspection': 2, 'facts': 1, 'traces': 1}


def shard(names, k, n):
    """The gates of the k-th of n parts (from 1): each gate, the longest first,
    goes to the part with the least time so far, the first starting with the
    corpus."""
    missing = [name for name in names if name not in SECONDS]
    assert not missing, f'SECONDS has no time for {missing}: the parts of CI are shared out by it'
    load = [SECONDS['corpus']] + [0] * (n - 1)
    parts = [[] for _ in range(n)]
    for name in sorted(names, key=lambda g: (-SECONDS[g], g)):
        i = load.index(min(load))
        parts[i].append(name)
        load[i] += SECONDS[name]
    return [g for g in names if g in parts[k - 1]]


def load(path, name):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def self_build(compiler):
    source = load(ROOT / 'scripts/build-arm64.py', 'build_arm64').source(sys.platform == 'darwin', sys.platform == 'darwin')
    made = subprocess.run([str(compiler)], input=source, capture_output=True, timeout=600)
    assert made.returncode == 0 and made.stdout == compiler.read_bytes(), ('self-build', made.returncode, made.stderr[:200])
    print(f'PASS self-build: {len(source):,} source bytes -> {len(made.stdout):,} bytes, identical')


def corpus(compiler):
    examples = load(ROOT / 'scripts/upstream-examples.py', 'upstream_examples')
    pinned = examples.reference.command(HERE / 'alchem-upstream')

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
            for attempt in range(50):
                try:
                    r = subprocess.run(command, capture_output=True, timeout=120, stdin=subprocess.DEVNULL, cwd=d, env=examples.env)
                    break
                except subprocess.TimeoutExpired:
                    return ['timeout', 0, '', '']
                except OSError as error:
                    # Another thread's fork may still hold the file open for
                    # writing (scripts/upstream-examples.py).
                    if error.errno != errno.ETXTBSY or attempt == 49:
                        raise
                    time.sleep(0.01)
            return ['ran', r.returncode, r.stdout.decode('utf8', 'replace'), r.stderr.decode('utf8', 'replace')]

    cases = [c for c in examples.cases() if '/'.join(c[0].split('/')[:2]) not in examples.DROPPED]
    with ThreadPoolExecutor(8) as pool:
        wanted = list(pool.map(lambda c: run([str(pinned), 'run'], c[1], False), cases))
        got = list(pool.map(lambda c: run([str(compiler)], c[1], True), cases))
    counted = failed = refused = 0
    for (name, _), u, r in zip(cases, wanted, got):
        if u[1] != 0:
            refused += 1  # the pinned compiler refuses it standalone
            continue
        counted += 1
        if r[1] != 0 or r[2] != u[2]:
            failed += 1
            print(f'FAIL {name}: {r[0]} {r[1]} wanted {u[2][:80]!r} got {r[2][:80]!r} {r[3][:120]!r}')
    assert failed == 0, f'{failed} of {counted} examples differ'
    # An example the pinned compiler refuses is not compared: with nothing
    # compared the pinned compiler is at fault.
    assert counted > 800, f'only {counted} examples run; the pinned compiler says of the first: {wanted[0]}'
    print(f'PASS corpus: {counted} examples print what the pinned compiler ({examples.reference.version()}) prints, {refused} it refuses standalone')


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
    module = load(ROOT / 'harness' / f'{name}.py', name)
    import ahead
    passed = ahead.install(compiler, name, module) if sys.platform == 'linux' and name not in ALONE else None
    module.verify(compiler)
    if passed:
        passed()


# Gates with timeouts of their own, too short on a runner of three cores busy
# with two other gates (a node waits two seconds for another's answer): they
# run after the others, one at a time.
ALONE = {'long_bodies', 'nodes'}


def gates(compiler, names, jobs):
    """The gates, each in a process of its own, jobs at a time, then those of ALONE."""
    def run(name):
        start = time.time()
        done = subprocess.run([sys.executable, __file__, str(compiler), '--gate', name], capture_output=True, text=True)
        return name, done.returncode, time.time() - start, (done.stdout + done.stderr).strip()
    failed = []
    for batch, width in [([n for n in names if n not in ALONE], jobs), ([n for n in names if n in ALONE], 1)]:
        with ThreadPoolExecutor(width) as pool:
            for name, status, seconds, said in pool.map(run, batch):
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
    k, n = 1, 1
    if '--shard' in args:
        at = args.index('--shard')
        k, n = map(int, args[at + 1].split('/'))
        assert 1 <= k <= n, args[at + 1]
        del args[at:at + 2]
    jobs = int(os.environ.get('ALCHEM_VERIFY_JOBS', '3'))
    names = [a for a in args if a != '--skip-corpus'] or GATES
    assert all(g in GATES for g in names), [g for g in names if g not in GATES]
    without = os.environ.get('ALCHEM_VERIFY_WITHOUT', '').split(',')
    for name in names:
        if name in without:
            print(f'LEFT OUT {name}: it is not for this system')
    names = shard([name for name in names if name not in without], k, n)
    if k == 1:
        self_build(compiler)
        if not skip:
            corpus(compiler)
    gates(compiler, names, jobs)


if __name__ == '__main__':
    main()
