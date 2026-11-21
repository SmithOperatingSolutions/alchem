#!/usr/bin/env python3
"""The upstream examples on Windows (spec/windows.md).

    windows-examples.py prepare DIR [--compiler build/dev/A2]
    windows-examples.py check DIR COMPILER.exe [--jobs N] [--wine]
    windows-examples.py pinned OUT.exe
    windows-examples.py reference DIR PINNED.exe COMPILER.exe [--wine]

prepare (on Linux) writes each example of scripts/upstream-examples.py that
the native Linux compiler builds and runs to exit 0 into DIR as NNNN.alc,
with what it printed as NNNN.out and its name in names.txt; the examples
whose output is not the same on Windows (SKIPPED) are left out. The
programs of the gates follow, with the status and output frozen in
harness/ (NNNN.code), but those Windows prints otherwise (GATE_SKIPPED). What
Linux prints is what the pinned compiler's windows/amd64 programs print for
all the others, under Wine (scripts/run-windows). WINDOWS_ONLY adds
programs for Windows alone, with what they print there.

check (on Windows) builds each with the Windows compiler, runs it in an
empty directory and compares what it prints; it ends 1 if any differs.
With --wine it runs them under Wine (scripts/run-windows) on Linux.

What Windows prints otherwise (SKIPPED, GATE_SKIPPED) is not passed over:
prepare writes those programs into DIR/reference too, and reference (on
Windows, with the Go toolchain the pinned compiler builds with) builds each
with the pinned compiler as its windows/amd64 program and with the Windows
compiler, runs both in the same directory, and compares their status and
output. pinned (on Linux) builds the pinned compiler as a Windows program."""
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
}


# Programs for Windows alone, with what they print there (the pinned
# compiler's windows/amd64 programs print the same): processes through
# cmd.exe, which every Windows has.
WINDOWS_ONLY = [
    ('windows/System.cmd', 'defmodule T do\n  def main() do\n'
     '    IO.puts(inspect(System.cmd("cmd", ["/c", "echo", "hello there"])))\n'
     '    IO.puts(inspect(System.cmd("cmd", ["/c", "exit 300"])))\n'
     '    IO.puts(inspect(System.cmd("cmd", ["/c", "echo err 1>&2"], [{:stderr_to_stdout, "true"}])))\n'
     '    IO.puts(inspect(System.find_executable("alchem-no-such-program")))\n'
     '  end\nend\n',
     '{"\\"hello there\\"\\r\\n", 0}\n{"", 300}\n{"err \\r\\n", 0}\nnone\n'),
    ('windows/Port', 'defmodule T do\n  def main() do\n'
     '    me: pid[PortEvent] = Process.self(16)\n'
     '    IO.puts(inspect(case Port.open("cmd", ["/c", "echo from port&& echo second"], me) do\n'
     '      ok(_) -> true\n      error(e) -> false\n    end))\n'
     '    assert_receive(me, PortEvent.data(first), 5000)\n    IO.puts(inspect(first))\n'
     '    assert_receive(me, PortEvent.data(second), 5000)\n    IO.puts(inspect(second))\n'
     '    assert_receive(me, PortEvent.exit(status), 5000)\n    IO.puts(inspect(status))\n'
     '    IO.puts(inspect(case Port.open("alchem-no-such-program", Enum.take([""], 0), me) do\n'
     '      ok(_) -> "started"\n      error(e) -> e\n    end))\n'
     '  end\nend\n',
     'true\n"from port"\n"second"\n0\n"exec: \\"alchem-no-such-program\\": executable file not found in %PATH%"\n'),
]


# The programs of the gates (harness/*.py, RUNS: program, status, output,
# errors) whose output on Windows is not what was frozen on Linux, as the
# pinned compiler's windows/amd64 programs print it too, by the start of
# the SHA-1 of the program: Windows' texts for errors (connectex, File not
# found., Invalid function., winapi error #N under Wine), and programs that
# run Unix programs (sh, cat, sort, true).
GATE_SKIPPED = {
    '74cab8ea13a9dc90': 'diskstore: reading a directory is Invalid function.',
    '8a682017d7e54e99': 'network: connectex, wsasendto, bind texts',
    '3f099a2ec14c19d1': 'network: connectex texts',
    'f7f9e01e4bba7af5': 'network: bind text',
    'a228f4f023154423': 'network: connectex texts',
    '12f31b3e08f968ed': 'network: wsasend text',
    '6dfc963e00010c6f': 'network: connectex, open texts, a reset read',
    '17b06680c1383be9': 'network: connectex texts',
    'c73676a8ef191eae': 'nodes: connectex texts',
    '9930ad7067555640': 'processes: runs sh',
    '5bc42070a9b52aec': 'processes: runs sort',
    '3dc7ee2df1372fb7': 'processes: runs sh',
    'e5b8b7905852c2b3': 'processes: runs cat',
    '198bb5fcd83a9dab': 'processes: runs cat',
    '700cda0a9b6edf51': 'processes: runs cat',
    '76c2f246990f4c5e': 'processes: runs sh and true',
    '73394fb268f5d365': 'processes: runs sh and cat; Windows exec texts',
    '4a81a1ee499b93b7': 'streams: Path not found.',
    'ab02f2126653ce3f': 'streams: Path not found.',
    '701e8cffd0b1edf7': 'streams: Path not found.',
    '9f29bbbc4aa73180': 'streams: Path not found.',
    '89358ba4d72c650c': 'tls: connectex texts',
    'f228da4432c4b763': 'tls: connectex, File not found. texts',
    'e82096a75dc06a41': 'tls: connectex texts',
}


def gate_runs():
    """(name, program, status, output) of every gate program frozen as
    (program, status, output, errors) that Windows prints alike."""
    import hashlib
    import importlib.util
    sys.path.insert(0, str(ROOT / 'harness'))
    found = []
    for path in sorted((ROOT / 'harness').glob('*.py')):
        text = path.read_text()
        if '\nRUNS=' not in text and '\nRUNS =' not in text:
            continue
        spec = importlib.util.spec_from_file_location('gate_' + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for i, run in enumerate(getattr(module, 'RUNS', None) or []):
            if len(run) != 4 or not isinstance(run[0], str) or not isinstance(run[1], int):
                continue
            if hashlib.sha1(run[0].encode()).hexdigest()[:16] in GATE_SKIPPED:
                continue
            found.append((f'gate/{path.stem}/{i}', run[0], run[1], run[2]))
    return found


def skipped_gate_runs():
    """(name, program) of the gate programs GATE_SKIPPED names."""
    import hashlib
    import importlib.util
    sys.path.insert(0, str(ROOT / 'harness'))
    found = []
    for path in sorted((ROOT / 'harness').glob('*.py')):
        text = path.read_text()
        if '\nRUNS=' not in text and '\nRUNS =' not in text:
            continue
        spec = importlib.util.spec_from_file_location('gate_' + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for i, run in enumerate(getattr(module, 'RUNS', None) or []):
            if len(run) == 4 and isinstance(run[0], str) and hashlib.sha1(run[0].encode()).hexdigest()[:16] in GATE_SKIPPED:
                found.append((f'gate/{path.stem}/{i}', run[0]))
    assert len(found) == len(GATE_SKIPPED), 'a program of GATE_SKIPPED is gone: take it out'
    return found


def pinned(out):
    """The pinned compiler built from the module cache as a Windows program."""
    examples = load_examples()
    env = dict(examples.env, GOOS='windows', GOARCH='amd64')
    subprocess.run(['go', 'build', '-o', str(Path(out).resolve()), './cmd/alchem'], cwd=examples.U, env=env, check=True)
    print(f'built {out}')


def normal(text, where):
    """Output with what differs from run to run as N: ports, the directory."""
    import re
    text = text.replace(str(where).encode(), b'DIR').replace(str(where).replace('\\', '/').encode(), b'DIR')
    return re.sub(rb'(127\.0\.0\.1|\[::1\]|localhost):\d+', rb'\1:N', text)


# Of those, what is a matter of timing on Windows, not of the program: the
# sh of Git for Windows writes printf 'one\ntwo' to a pipe in two writes,
# which the pinned runtime's blocking read finds apart and a read when the
# pipe is ready finds together.
REFERENCE_TIMING = {'3dc7ee2df1372fb7': 'processes: the parts a pipe is read in'}


def reference(directory, pinned_compiler, compiler, runner):
    import hashlib
    directory = Path(directory)
    names = (directory / 'reference' / 'names.txt').read_text().split('\n')[:-1]
    failed = []
    timed = 0
    for i, name in enumerate(names):
        if hashlib.sha1((directory / 'reference' / f'{i:04}.alc').read_bytes()).hexdigest()[:16] in REFERENCE_TIMING:
            timed += 1
            continue
        source = directory / 'reference' / f'{i:04}.alc'
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / 'p.alc').write_bytes(source.read_bytes())
            # Under Wine the pinned compiler is the Linux one (it has a Go
            # toolchain there), which builds windows/amd64 programs as well.
            made = subprocess.run([*([] if runner and not str(pinned_compiler).endswith('.exe') else runner), str(pinned_compiler), 'build', '-target', 'windows/amd64', '-o', str(d / 'pinned.exe'), str(d / 'p.alc')],
                                  capture_output=True, timeout=600)
            ours = subprocess.run([*runner, str(compiler)], input=source.read_bytes(), capture_output=True, timeout=300)
            if made.returncode or ours.returncode:
                failed.append((name, f'did not build: {made.stderr[:200]!r} {ours.stderr[:200]!r}'))
                continue
            (d / 'native.exe').write_bytes(ours.stdout)
            got = []
            for program in ('pinned.exe', 'native.exe'):
                run = d / 'run'
                if run.exists():
                    shutil.rmtree(run)
                run.mkdir()
                (run / 'tmp').mkdir()
                env = dict(os.environ, TMP=str(run / 'tmp'), TEMP=str(run / 'tmp'))
                try:
                    r = subprocess.run([*runner, str(d / program)], capture_output=True, timeout=120, cwd=run, stdin=subprocess.DEVNULL, env=env)
                    got.append((r.returncode, normal(r.stdout, run).replace(str(d / 'p.alc').encode(), b'<stdin>')))
                except subprocess.TimeoutExpired:
                    got.append(('timed out', b''))
            if got[0] != got[1]:
                import difflib
                lines = difflib.unified_diff(got[0][1].decode(errors='replace').split('\n'),
                                             got[1][1].decode(errors='replace').split('\n'),
                                             'pinned', 'native', lineterm='', n=0)
                diff = '\n'.join('    ' + line[:240] for line in list(lines)[:40])
                failed.append((name, f'status pinned {got[0][0]}, native {got[1][0]}\n{diff}'))
    for name, why in failed:
        print(f'FAIL {name}: {why}')
    print(f'{len(names) - timed - len(failed)} of {len(names) - timed} print what the pinned compiler\'s Windows programs print'
          f' ({timed} a matter of timing, REFERENCE_TIMING)')
    return 1 if failed else 0


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
    for name, source, status, printed in gate_runs():
        number = f'{len(names):04}'
        (out / (number + '.alc')).write_text(source)
        (out / (number + '.out')).write_bytes(printed)
        (out / (number + '.code')).write_text(str(status))
        names.append(name)
    for name, source, printed in WINDOWS_ONLY:
        number = f'{len(names):04}'
        (out / (number + '.alc')).write_text(source)
        (out / (number + '.out')).write_text(printed)
        names.append(name)
    (out / 'names.txt').write_text(''.join(n + '\n' for n in names))
    # What Windows prints otherwise, for reference.
    others = [(n, s) for n, s in examples.cases() if n in SKIPPED] + skipped_gate_runs()
    against = out / 'reference'
    against.mkdir()
    for i, (name, source) in enumerate(others):
        (against / f'{i:04}.alc').write_text(source)
    (against / 'names.txt').write_text(''.join(n + '\n' for n, _ in others))
    print(f'{len(names)} programs in {out}, {len(others)} to compare with the pinned compiler\'s')


def check_one(directory, compiler, number, name, runner):
    source = (directory / (number + '.alc')).read_bytes()
    want = (directory / (number + '.out')).read_bytes()
    coded = directory / (number + '.code')
    status = int(coded.read_text()) if coded.exists() else 0
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        # A temporary directory of its own: gate programs name files there.
        (d / 'tmp').mkdir()
        # Under Wine as a path of its drive Z:, which it takes there.
        tmp = ('Z:' + str(d / 'tmp').replace('/', '\\')) if runner else str(d / 'tmp')
        env = dict(os.environ, TMP=tmp, TEMP=tmp)
        built = subprocess.run([*runner, compiler], input=source, capture_output=True, timeout=300)
        if built.returncode:
            return name, f'did not build: {built.stderr.decode(errors="replace")[:300]}'
        program = d / 'p.exe'
        program.write_bytes(built.stdout)
        run = d / 'run'
        run.mkdir()
        try:
            got = subprocess.run([*runner, str(program)], capture_output=True, timeout=120, cwd=run, stdin=subprocess.DEVNULL, env=env)
        except subprocess.TimeoutExpired:
            return name, 'timed out'
        if got.returncode != status or got.stdout != want:
            return name, (f'exit {got.returncode}\n  want {want[:300]!r}\n  got  {got.stdout[:300]!r}\n'
                          f'  stderr {got.stderr.decode(errors="replace")[:300]!r}')
    return name, None


def check(directory, compiler, jobs, runner):
    directory = Path(directory)
    compiler = str(Path(compiler).resolve())
    names = (directory / 'names.txt').read_text().split('\n')[:-1]
    # Wine takes no TMP of a program's own: there the programs that name
    # files in the temporary directory (DiskStore's) run one at a time.
    alone = [i for i in range(len(names)) if runner and names[i].startswith('gate/diskstore/')]
    together = [i for i in range(len(names)) if i not in alone]
    with ThreadPoolExecutor(jobs) as pool:
        results = list(pool.map(lambda i: check_one(directory, compiler, f'{i:04}', names[i], runner), together))
    results += [check_one(directory, compiler, f'{i:04}', names[i], runner) for i in alone]
    failed = [(n, why) for n, why in results if why]
    for name, why in failed:
        print(f'FAIL {name}: {why}')
    print(f'{len(names) - len(failed)} of {len(names)} programs print on Windows what they print on Linux')
    return 1 if failed else 0


def main():
    args = sys.argv[1:]
    if len(args) >= 2 and args[0] == 'prepare':
        compiler = ROOT / 'build/dev/A2'
        if '--compiler' in args:
            compiler = Path(args[args.index('--compiler') + 1])
        prepare(args[1], compiler.resolve())
        return 0
    if len(args) == 2 and args[0] == 'pinned':
        pinned(args[1])
        return 0
    if len(args) >= 4 and args[0] == 'reference':
        runner = [str(ROOT / 'scripts/run-windows')] if '--wine' in args else []
        return reference(args[1], Path(args[2]).resolve(), Path(args[3]).resolve(), runner)
    if len(args) >= 3 and args[0] == 'check':
        jobs = int(args[args.index('--jobs') + 1]) if '--jobs' in args else 4
        runner = [str(ROOT / 'scripts/run-windows')] if '--wine' in args else []
        return check(args[1], args[2], jobs, runner)
    sys.exit(__doc__)


if __name__ == '__main__':
    raise SystemExit(main())
