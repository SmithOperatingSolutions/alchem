#!/usr/bin/env python3
"""The upstream examples on Windows (spec/windows.md).

    windows-examples.py prepare DIR [--compiler build/dev/A2]
    windows-examples.py check DIR COMPILER.exe [--jobs N] [--wine] [--only PREFIX --repeat N]
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
With --wine it runs them under Wine (scripts/run-windows) on Linux. With
--only PREFIX --repeat N it runs the programs whose name starts with PREFIX
N times each: those whose processes could fall otherwise in time.

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
    'c9f23f8f91d42206': 'system 68: a wildcard that ends in a backslash, which parts directories on Windows',
    'e685b07ea56d3832': 'system 0: Windows\' file, path and exec texts, Unix programs and places',
    '7fff6bf2872953ce': 'system 1: Windows\' file, path and exec texts, Unix programs and places',
    'e50e781459c7b456': 'system 2: Windows\' file, path and exec texts, Unix programs and places',
    'b2f56d6288f6d300': 'system 3: Windows\' file, path and exec texts, Unix programs and places',
    '5d25e3ff912d8eae': 'system 4: Windows\' file, path and exec texts, Unix programs and places',
    'c2ef14a3ff10cc3f': 'system 5: Windows\' file, path and exec texts, Unix programs and places',
    'c06ae20b49152443': 'system 6: Windows\' file, path and exec texts, Unix programs and places',
    'c902ad61c7b24206': 'system 7: Windows\' file, path and exec texts, Unix programs and places',
    '15c570da24157304': 'system 8: Windows\' file, path and exec texts, Unix programs and places',
    'e3de30801d6de652': 'system 9: Windows\' file, path and exec texts, Unix programs and places',
    'b68af474d11c1c0d': 'system 11: Windows\' file, path and exec texts, Unix programs and places',
    'aebb25567d8fd85d': 'system 13: Windows\' file, path and exec texts, Unix programs and places',
    '582f3e05f855f38e': 'system 14: Windows\' file, path and exec texts, Unix programs and places',
    'f18a2b8e5faeb1a0': 'system 22: Windows\' file, path and exec texts, Unix programs and places',
    'c21bbb301b41a5af': 'system 23: Windows\' file, path and exec texts, Unix programs and places',
    'cb8874a56a397e8d': 'system 25: Windows\' file, path and exec texts, Unix programs and places',
    'd6d629382df5a1b7': 'system 26: Windows\' file, path and exec texts, Unix programs and places',
    'a571331452eb5094': 'system 27: Windows\' file, path and exec texts, Unix programs and places',
    '2d342574f5bd86fd': 'system 28: Windows\' file, path and exec texts, Unix programs and places',
    '66074ae468056dc5': 'system 34: Windows\' file, path and exec texts, Unix programs and places',
    '8498500e6208ee9f': 'system 35: Windows\' file, path and exec texts, Unix programs and places',
    '9d1490fc421cb8e5': 'system 62: Windows\' file, path and exec texts, Unix programs and places',
    '41a56090adb4d965': 'system 63: Windows\' file, path and exec texts, Unix programs and places',
    'ed7b66b29b636760': 'system 73: Windows\' file, path and exec texts, Unix programs and places',
    '6b50980b9deac432': 'system 74: Windows\' file, path and exec texts, Unix programs and places',
    '00ce1ee88daf4559': 'time_zones 4: Windows\' file, path and exec texts, Unix programs and places',
}


# Programs compared with the pinned compiler's on Windows alone (reference):
# what the Windows layer and the library's view of Windows were found, by
# reading, to do otherwise than Go there. (name, program, environment).
REFERENCE_PROGRAMS = [
    # A failing process's trace is written by a copy of the program into a
    # pipe the program reads once the copy has ended: one longer than the pipe.
    ('windows/a trace longer than its pipe', 'defmodule T do\n  def main() do\n'
     '    w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do raise(String.duplicate("x", 2000000)) end, 1)\n'
     '    {ended, why} = Process.await(w, 20000)\n'
     '    IO.puts(inspect({ended, byte_size(why)}))\n'
     '    IO.puts(inspect(byte_size(Process.report(w)) > 2000000))\n'
     '  end\nend\n', {}),
    # Copies made at many depths of the stack, and what the program holds
    # after each: the copy's pages are put back, none of the program's lost.
    ('windows/failing processes at many depths', 'defmodule T do\n'
     '  def deep(n: integer): integer do\n    if n == 0 do raise("at the bottom") else 1 + deep(n - 1) end\n  end\n'
     '  def fill(n: integer, kept: list[integer]): list[integer] do\n    if n == 0 do kept else fill(n - 1, [n * 7 | kept]) end\n  end\n'
     '  def rounds(i: integer, bad: integer): integer do\n    if i > 300 do bad else\n'
     '      w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do deep(i * 37) end, 1)\n'
     '      {ended, why} = Process.await(w, 20000)\n'
     '      fine = ended and why == "at the bottom" and String.contains?(Process.report(w), ": at the bottom\\n  at T.deep")\n'
     '      rounds(i + 1, if fine do bad else bad + 1 end)\n    end\n  end\n'
     '  def main() do\n    kept = fill(200000, [])\n    before = Enum.sum(kept)\n'
     '    IO.puts(inspect(rounds(0, 0)))\n'
     '    IO.puts(inspect({Enum.sum(kept) == before, Enum.sum(fill(200000, [])) == before}))\n'
     '  end\nend\n', {}),
    # More mappings in a program's life than the layer's table of them has
    # room for, then a copy, then mappings again.
    ('windows/more mappings than the table holds', 'defmodule T do\n'
     '  def churn(n: integer, total: integer): integer do\n'
     '    if n == 0 do total else churn(n - 1, total + length(Enum.uniq([n, n, 1, 2, 1]))) end\n  end\n'
     '  def main() do\n    IO.puts(inspect(churn(3000, 0)))\n'
     '    kept = Enum.to_list(1..100000)\n'
     '    w: pid[integer] = Process.spawn(fn(self: pid[integer]): integer do raise("after the table") end, 1)\n'
     '    IO.puts(inspect(Process.await(w, 20000)))\n    IO.puts(Process.report(w))\n'
     '    IO.puts(inspect({churn(3000, 0), Enum.sum(kept)}))\n'
     '  end\nend\n', {}),
    # os.Setenv on Windows sets the variable whatever case it has.
    ('windows/put_env in another case', 'defmodule T do\n  def main() do\n'
     '    IO.puts(inspect(System.get_env("ALCHEMCASE")))\n'
     '    System.put_env("ALCHEMCASE", "two")\n'
     '    IO.puts(inspect({System.get_env("alchemcase"), System.get_env("AlchemCase")}))\n'
     '    IO.puts(inspect(System.cmd("cmd", ["/c", "echo %ALCHEMCASE%"])))\n'
     '  end\nend\n', {'AlchemCase': 'one'}),
    # os.Stat follows a link, os.Lstat does not; a link to a directory, its
    # target written from the link's directory, is a directory's.
    ('windows/links', 'defmodule T do\n'
     '  def kind(r: result[File.Stat, string]): string do\n    case r do\n'
     '      ok(s) -> inspect({s.size, s.type})\n      error(e) -> e\n    end\n  end\n'
     '  def main() do\n    File.write("t.txt", "hello")\n    File.mkdir_p("d/sub")\n    File.write("d/sub/f.txt", "x")\n'
     '    IO.puts(inspect(File.ln_s("t.txt", "l.txt")))\n'
     '    IO.puts(kind(File.stat("l.txt")))\n    IO.puts(kind(File.lstat("l.txt")))\n'
     '    IO.puts(inspect(File.read("l.txt")))\n'
     '    IO.puts(inspect(File.ln_s("sub", "d/link")))\n'
     '    IO.puts(inspect({File.dir?("d/link"), File.ls("d/link"), File.read("d/link/f.txt")}))\n'
     '  end\nend\n', {}),
    # exec.LookPath with no extensions to try takes the file as it is named.
    ('windows/a program found without extensions', 'defmodule T do\n  def main() do\n'
     '    File.write("tool", "")\n    File.write("other.exe", "")\n'
     '    IO.puts(inspect({System.find_executable(Path.expand("tool")) == some(Path.expand("tool")), System.find_executable(Path.expand("other"))  == none}))\n'
     '  end\nend\n', {'PATHEXT': ';'}),
    # An environment of more than a million characters, given to a program.
    ('windows/a large environment', 'defmodule T do\n'
     '  def set(n: integer): integer do\n'
     '    if n == 0 do 0 else\n      System.put_env("ALCHEM_LARGE_#{n}", String.duplicate("v", 30000))\n      set(n - 1)\n    end\n  end\n'
     '  def main() do\n    set(40)\n'
     '    IO.puts(inspect(System.cmd("cmd", ["/c", "echo ok"])))\n'
     '  end\nend\n', {}),
    # filepath.Base, Dir and the library's slashes.
    ('windows/names of roots', 'defmodule T do\n  def main() do\n'
     '    IO.puts(inspect([Path.basename("/"), Path.basename("C:\\\\"), Path.basename("a\\\\b"), Path.basename("C:"), Path.basename("\\\\\\\\host\\\\share\\\\")]))\n'
     '    IO.puts(inspect([Path.dirname("/"), Path.dirname("C:\\\\"), Path.dirname("a\\\\b"), Path.dirname("C:\\\\a")]))\n'
     '  end\nend\n', {}),
]


# The gates whose RUNS are not programs with a frozen result: speed and
# memory_reclaim measure, arm64 names programs of examples/, and testing
# runs test files with alchem (CI runs alchem.exe test on Windows).
NOT_PROGRAMS = {'arm64', 'memory_reclaim', 'speed', 'testing'}


def gate_case(gate, module, i, run):
    """A record of RUNS as a program: its source, status, output, errors,
    environment, input and the files of its directory. Each gate keeps its
    own form; one that is none of these is an error, not passed over."""
    kinds = tuple(type(x).__name__ for x in run)
    case = {'name': f'gate/{gate}/{i}', 'env': {}, 'stdin': b'', 'files': {}}
    if kinds == ('str', 'int', 'bytes', 'bytes'):
        case.update(source=run[0], status=run[1], out=run[2], err=run[3])
    elif kinds == ('str', 'int', 'bytes', 'bytes', 'dict', 'bytes'):
        case.update(source=run[0], status=run[1], out=run[2], err=run[3], env=run[4], stdin=run[5],
                    files=getattr(module, 'FILES', {}))
    elif kinds == ('str', 'bytes', 'int', 'int', 'bytes', 'bytes'):  # system: input, whether root may run it
        case.update(source=run[0], stdin=run[1], status=run[3], out=run[4], err=run[5])
    elif kinds == ('dict', 'int', 'bytes', 'bytes'):
        # A program of several files is bundled where it is compiled, with
        # that directory in its errors: the one file is taken as it is.
        if set(run[0]) != {'main.alc'}:
            return None
        case.update(source=run[0]['main.alc'], status=run[1], out=run[2], err=run[3].replace(b'@/main.alc', b'<stdin>'))
    else:
        raise AssertionError(f'{gate}: a record of RUNS of a form unknown here: {kinds}')
    return case


def gate_cases():
    """(the programs of the gates that Windows prints alike, those of
    GATE_SKIPPED, how many programs of several files were left out)."""
    import hashlib
    import importlib.util
    sys.path.insert(0, str(ROOT / 'harness'))
    alike, otherwise, bundles = [], [], 0
    for path in sorted((ROOT / 'harness').glob('*.py')):
        text = path.read_text()
        if ('\nRUNS=' not in text and '\nRUNS =' not in text) or path.stem in NOT_PROGRAMS:
            continue
        spec = importlib.util.spec_from_file_location('gate_' + path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for i, run in enumerate(module.RUNS):
            case = gate_case(path.stem, module, i, run)
            if case is None:
                bundles += 1
            elif hashlib.sha1(case['source'].encode()).hexdigest()[:16] in GATE_SKIPPED:
                otherwise.append(case)
            else:
                alike.append(case)
    named = {hashlib.sha1(c['source'].encode()).hexdigest()[:16] for c in otherwise}
    assert named == set(GATE_SKIPPED), f'programs of GATE_SKIPPED are gone: take them out: {sorted(set(GATE_SKIPPED) - named)}'
    return alike, otherwise, bundles


def write_case(directory, number, case):
    """A program for check or reference: NNNN.alc, with NNNN.out, NNNN.err
    and NNNN.json (status, environment, files) where a result is frozen,
    and NNNN.in, its input."""
    import json
    (directory / (number + '.alc')).write_text(case['source'])
    (directory / (number + '.in')).write_bytes(case.get('stdin', b''))
    if 'out' in case:
        (directory / (number + '.out')).write_bytes(case['out'])
    if 'err' in case:
        (directory / (number + '.err')).write_bytes(case['err'])
    files = None
    if case.get('files'):
        files = case['name'].split('/')[1]
        for name, data in case['files'].items():
            (directory / 'files' / files / name).parent.mkdir(parents=True, exist_ok=True)
            (directory / 'files' / files / name).write_bytes(data)
    (directory / (number + '.json')).write_text(json.dumps({'status': case.get('status', 0), 'env': case.get('env', {}), 'files': files}))


def read_case(directory, number):
    import json
    case = json.loads((directory / (number + '.json')).read_text())
    case['source'] = (directory / (number + '.alc')).read_bytes()
    case['stdin'] = (directory / (number + '.in')).read_bytes()
    for part in ('out', 'err'):
        if (directory / (number + '.' + part)).exists():
            case[part] = (directory / (number + '.' + part)).read_bytes()
    return case


def given(case):
    """The program's standard input: its bytes, or none."""
    return {'input': case['stdin']} if case['stdin'] else {'stdin': subprocess.DEVNULL}


def place(directory, case, run):
    """The files of the program's directory, in run."""
    if case['files']:
        shutil.copytree(directory / 'files' / case['files'], run, dirs_exist_ok=True)


def pinned(out):
    """The pinned compiler built from the module cache as a Windows program."""
    examples = load_examples()
    env = dict(examples.env, GOOS='windows', GOARCH='amd64')
    subprocess.run(['go', 'build', '-o', str(Path(out).resolve()), './cmd/alchem'], cwd=examples.U, env=env, check=True)
    print(f'built {out}')


def normal(text, where):
    """Output with what differs from run to run as N: ports, the directory."""
    import re
    # As written, with slashes for backslashes, with each backslash doubled
    # as inspect writes it, and under Wine as Z: and the Linux path in
    # Windows' form.
    windows = str(where) if '\\' in str(where) else 'Z:' + str(where).replace('/', '\\')
    for form in sorted({str(where), windows, windows.replace('\\', '/'), windows.replace('\\', '\\\\')}, key=len, reverse=True):
        text = text.replace(form.encode(), b'DIR')
    return re.sub(rb'(127\.0\.0\.1|\[::1\]|localhost):\d+', rb'\1:N', text)


# Of those, what is a matter of timing on Windows, not of the program: the
# sh of Git for Windows writes printf 'one\ntwo' to a pipe in two writes,
# which the pinned runtime's blocking read finds apart and a read when the
# pipe is ready finds together.
#
# And the pinned nodes program counts its processes (Process.count) while
# Go's scheduler on Windows has yet to start a server Node.serve made, or
# to end the process of a cast of the wrong type: 50 ms later its counts
# are these programs' and those of both compilers on Linux.
REFERENCE_TIMING = {'3dc7ee2df1372fb7': 'processes: the parts a pipe is read in',
                    'c73676a8ef191eae': 'nodes: Process.count as Go schedules on Windows'}


def named(text, source):
    """Output with the file the pinned compiler was given as <stdin>, which
    the Windows compiler reads its program from: the pinned compiler names
    it with slashes."""
    for form in (str(source), str(source).replace('\\', '/')):
        text = text.replace(form.encode(), b'<stdin>')
    return text


def reference(directory, pinned_compiler, compiler, runner):
    import hashlib
    directory = Path(directory) / 'reference'
    names = (directory / 'names.txt').read_text().split('\n')[:-1]
    failed = []
    held = []
    timed = 0
    for i, name in enumerate(names):
        case = read_case(directory, f'{i:04}')
        if hashlib.sha1(case['source']).hexdigest()[:16] in REFERENCE_TIMING:
            timed += 1
            continue
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            d = Path(d)
            (d / 'p.alc').write_bytes(case['source'])
            # Under Wine the pinned compiler is the Linux one (it has a Go
            # toolchain there), which builds windows/amd64 programs as well.
            made = subprocess.run([*([] if runner and not str(pinned_compiler).endswith('.exe') else runner), str(pinned_compiler), 'build', '-target', 'windows/amd64', '-o', str(d / 'pinned.exe'), str(d / 'p.alc')],
                                  capture_output=True, timeout=600)
            ours = subprocess.run([*runner, str(compiler)], input=case['source'], capture_output=True, timeout=300)
            if made.returncode or ours.returncode:
                failed.append((name, f'did not build: {made.stderr[:200]!r} {ours.stderr[:200]!r}'))
                continue
            (d / 'native.exe').write_bytes(ours.stdout)
            got = []
            for program in ('pinned.exe', 'native.exe'):
                # A directory of its own for each: a process a program
                # leaves behind can hold its directory on Windows.
                run = d / ('run-' + program[:-4])
                run.mkdir()
                (run / 'tmp').mkdir()
                place(directory, case, run)
                env = dict(os.environ, TMP=str(run / 'tmp'), TEMP=str(run / 'tmp'), **case['env'])
                try:
                    r = subprocess.run([*runner, str(d / program)], capture_output=True, timeout=120, cwd=run, env=env, **given(case))
                    got.append((r.returncode, *(named(normal(text, run), d / 'p.alc') for text in (r.stdout, r.stderr))))
                except subprocess.TimeoutExpired:
                    # Never equal to the other's, which may have timed out too.
                    got.append((f'{program} timed out', b'', b''))
            for program in ('pinned', 'native'):
                try:
                    shutil.rmtree(d / ('run-' + program))
                except OSError:
                    held.append(f'{name} ({program})')
            if got[0] != got[1]:
                import difflib
                diff = ''
                for part, said in ((1, 'output'), (2, 'errors')):
                    lines = difflib.unified_diff(got[0][part].decode(errors='replace').split('\n'),
                                                 got[1][part].decode(errors='replace').split('\n'),
                                                 'pinned ' + said, 'native ' + said, lineterm='', n=0)
                    diff += ''.join('\n    ' + line[:240] for line in list(lines)[:40])
                failed.append((name, f'status pinned {got[0][0]}, native {got[1][0]}{diff}'))
            elif name.startswith('windows/'):
                # What both print is not frozen anywhere: it is shown.
                print(f'same {name}: {got[0][0]} {got[0][1][:300]!r} {got[0][2][:200]!r}')
    for name, why in failed:
        print(f'FAIL {name}: {why}')
    for name in held:
        print(f'note: a process of {name} outlived it, holding its directory')
    print(f'{len(names) - timed - len(failed)} of {len(names) - timed} print what the pinned compiler\'s Windows programs print'
          f' ({timed} a matter of timing, REFERENCE_TIMING)')
    return 1 if failed else 0


def load_examples():
    import importlib.util
    spec = importlib.util.spec_from_file_location('upstream_examples', ROOT / 'scripts/upstream-examples.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# The fewest upstream examples prepare may write: fewer means the Linux
# compiler no longer builds or runs some, which would pass unseen here.
EXAMPLES_AT_LEAST = 850


def prepare(out, compiler):
    examples = load_examples()
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    cases = [(n, s) for n, s in examples.cases() if not n.startswith('syntax/extern') and n not in SKIPPED]
    with ThreadPoolExecutor(os.cpu_count() or 4) as pool:
        results = list(pool.map(lambda c: examples.native(c[1], str(compiler)), cases))
    alike, otherwise, bundles = gate_cases()
    programs = [{'name': name, 'source': source, 'out': result[2].encode()}
                for (name, source), result in zip(cases, results) if result[0] == 'ran' and result[1] == 0]
    assert len(programs) >= EXAMPLES_AT_LEAST, f'only {len(programs)} upstream examples build and run to exit 0 on Linux'
    programs += alike
    programs += [{'name': name, 'source': source, 'out': printed.encode()} for name, source, printed in WINDOWS_ONLY]
    for i, case in enumerate(programs):
        write_case(out, f'{i:04}', case)
    (out / 'names.txt').write_text(''.join(c['name'] + '\n' for c in programs))
    # What Windows prints otherwise, for reference: no result is frozen.
    others = [{'name': n, 'source': s} for n, s in examples.cases() if n in SKIPPED]
    others += [{k: v for k, v in c.items() if k not in ('out', 'err', 'status')} for c in otherwise]
    others += [{'name': name, 'source': source, 'env': env} for name, source, env in REFERENCE_PROGRAMS]
    against = out / 'reference'
    against.mkdir()
    for i, case in enumerate(others):
        write_case(against, f'{i:04}', case)
    (against / 'names.txt').write_text(''.join(c['name'] + '\n' for c in others))
    print(f'{len(programs)} programs in {out} ({len(alike)} of the gates; {bundles} of several files left out),'
          f' {len(others)} to compare with the pinned compiler\'s')


def check_one(directory, compiler, number, name, runner):
    d = Path(tempfile.mkdtemp())
    why = check_in(d, compiler, directory, read_case(directory, number), runner)
    # A process the program left running holds p.exe on Windows.
    try:
        shutil.rmtree(d)
    except OSError as e:
        held = f'a process of it outlived it, holding {Path(e.filename).name}'
        why = f'{why}; {held}' if why else held
    return name, why


def check_in(d, compiler, directory, case, runner):
    """Why the program in d prints other than it should, or None."""
    # A temporary directory of its own: gate programs name files there.
    (d / 'tmp').mkdir()
    # Under Wine as a path of its drive Z:, which it takes there.
    tmp = ('Z:' + str(d / 'tmp').replace('/', '\\')) if runner else str(d / 'tmp')
    env = dict(os.environ, TMP=tmp, TEMP=tmp, **case['env'])
    built = subprocess.run([*runner, compiler], input=case['source'], capture_output=True, timeout=300)
    if built.returncode:
        return f'did not build: {built.stderr.decode(errors="replace")[:300]}'
    program = d / 'p.exe'
    program.write_bytes(built.stdout)
    run = d / 'run'
    run.mkdir()
    place(directory, case, run)
    try:
        got = subprocess.run([*runner, str(program)], capture_output=True, timeout=120, cwd=run, env=env, **given(case))
    except subprocess.TimeoutExpired:
        return 'timed out'
    # An upstream example's errors are not frozen (it ends 0); a gate's are.
    if got.returncode != case['status'] or got.stdout != case['out'] or got.stderr != case.get('err', got.stderr):
        return (f'exit {got.returncode}, want {case["status"]}\n  want {case["out"][:300]!r}\n  got  {got.stdout[:300]!r}\n'
                f'  want errors {case.get("err", b"")[:400]!r}\n  got errors  {got.stderr[:400]!r}')
    return None


def check(directory, compiler, jobs, runner, only='', repeat=1):
    directory = Path(directory)
    compiler = str(Path(compiler).resolve())
    names = (directory / 'names.txt').read_text().split('\n')[:-1]
    if only:
        # Some of them, each several times: a program whose result depends
        # on how its processes fall in time fails one run in a few.
        chosen = [i for i in range(len(names)) if names[i].startswith(only)] * repeat
        with ThreadPoolExecutor(jobs) as pool:
            results = list(pool.map(lambda i: check_one(directory, compiler, f'{i:04}', names[i], runner), chosen))
        failed = [(n, why) for n, why in results if why]
        for name, why in failed:
            print(f'FAIL {name}: {why}')
        print(f'{len(chosen) - len(failed)} of {len(chosen)} runs of {len(chosen) // repeat} programs ({only}, {repeat} times each) print what they print on Linux')
        return 1 if failed or not chosen else 0
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
        only = args[args.index('--only') + 1] if '--only' in args else ''
        repeat = int(args[args.index('--repeat') + 1]) if '--repeat' in args else 1
        return check(args[1], args[2], jobs, runner, only, repeat)
    sys.exit(__doc__)


if __name__ == '__main__':
    raise SystemExit(main())
