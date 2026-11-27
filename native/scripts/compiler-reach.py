#!/usr/bin/env python3
"""What of the compiler a set of programs reaches: the compiler's source,
as the bootstrap assembles it without compacting it, is compiled as the
module under test of a test that compiles each program, and the test's
cover file (ALCHEM_COVER_FILE, spec/alchem-failures.md) is reported as
`alchem test -cover-functions` reports one, file by file of
implementations/alchem.

    compiler-reach.py COMPILER [--gates [WORD...]] [--search PINNED COUNT SEED]
                      [--programs DIR] [--jobs N] [--keep DIR]
                      [--built FILE]

COMPILER is the compiler that builds the test (build/dev/A2), with
ALCHEM_REACH_BUILD_MEMORY (12G); each part runs with ALCHEM_MEMORY (8G). The programs:
--gates, every program the gates (scripts/verify-quick.py, those that take
the compiler alone; all, or those whose names have one of the words given)
give the compiler: each gate is run with a compiler that keeps what it is
given and then compiles it, so a gate that fails counts what it compiled
until then, and is named; --search, the random cases
generate-program-cases.py makes with the pinned command; --programs, the
.alc files of a directory. A program met twice is compiled once, and one of
more than ALCHEM_REACH_LARGEST bytes (1 MiB: the compiler's own source and
the commands bundled with it) is left out and counted. They are compiled a hundred to a run of the test, --jobs runs at once; a
program the compiler refuses still counts what it reached, and so does one
that ends the test (it is found by running its part in halves, and named). --built FILE keeps the test there, and uses the one that is there.

The compiler is one module of more than 1 MiB, which `alchem test` (the
bundler and the front end, as the pinned command) does not take: the test
is bundled here. The code for other systems (ARM64, macOS, Windows) is
reached only by compiling for them, and is reported apart.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Code that only compiling for another system reaches.
OTHER_SYSTEMS = {'native-x86arm.alc', 'native-arm64.alc', 'native-macho.alc', 'native-runtimes-arm64.alc',
                 'native-memory-data-arm64.alc', 'native-memory-data-darwin.alc', 'native-windows.alc', 'native-windows-data.alc'}
# How many programs one run of the test compiles.
PART = 100
TEST = '''defmodule AlchemReach do
  import "module:ReachCompiler"

  test "the compiler compiles the programs" do
    dir = case System.get_env("REACH_PROGRAMS") do
      some(d) -> d
      none -> "programs"
    end
    names = File.ls!(dir)
    made = Enum.map(names, fn name -> Enum.count(ReachCompiler.nc_compile(rx_ab(File.read!(dir <> "/" <> name)))) end)
    assert(length(made) == length(names))
  end
end
'''


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assembled(traced=False):
    """The compiler's source as one module, and where each file of it
    starts: [(line, file name)]. A line that names the file is put before
    each file's text to find it, and taken out again. traced: as the
    compiler that says where it ends (scripts/compiler-where.py), the
    module and its entry left as they are."""
    bootstrap = load('bootstrap', ROOT / 'scripts/bootstrap-alchem-compiler.py')
    plain = Path.read_text
    def marked(self, *args, **kwargs):
        text = plain(self, *args, **kwargs)
        if self.suffix == '.alc' and text.startswith('defmodule '):
            head, body = text.split('\n', 1)
            return head + '\n# @@' + self.name + '\n' + body
        return text
    Path.read_text = marked
    try:
        text = bootstrap.source_text('functions', False, traced=traced)
    finally:
        Path.read_text = plain
    lines, starts = [], []
    for line in text.split('\n'):
        if line.startswith('# @@'):
            starts.append((len(lines) + 1, line[4:]))
        else:
            lines.append(line)
    if lines[0] != 'defmodule NativeSourceCompiler do':
        raise SystemExit('the compiler source is not one NativeSourceCompiler module')
    if traced:
        return '\n'.join(lines), starts
    # The module under test: no compiler entry and no main, each line kept
    # where it is.
    lines[0] = 'defmodule ReachCompiler do'
    lines = ['' if l.startswith('  def native_compile(') or l.startswith('  def main()') else l for l in lines]
    return '\n'.join(lines), starts


def bundle(source):
    test = TEST.encode()
    compiler = source.encode()
    # Marked: AlchemReach calls rx_ab, which only the library and the
    # modules named Alchem may (scripts/bundle-alchem.py, marked).
    return (b'#alchem-bundle 2\x7f\n# %d reach_test.alc\n# %d compiler.alc\n' % (len(test), len(compiler))) + test + compiler


def functions(lines, starts):
    """Each function of the assembled source, in its order: (the line it
    starts at there, name/arity, its file, the line it starts at in its
    file). The bootstrap puts some files inside others, so a function's
    file is the one that has its first line; where two have it, the one
    whose text comes last before it."""
    def file_at(n):
        name = starts[0][1]
        for line, file in starts:
            if line > n:
                break
            name = file
        return name
    homes = defaultdict(list)
    for path in sorted((ROOT / 'implementations/alchem').glob('*.alc')):
        for k, line in enumerate(path.read_text().split('\n'), 1):
            if line.startswith('  def '):
                homes[line].append((path.name, k))
    found = []
    for n, line in enumerate(lines, 1):
        m = re.match(r'  def ([a-z_][A-Za-z0-9_]*[?!]?)\((.*)', line)
        if not m:
            continue
        params, depth, count, any_ = m.group(2), 0, 0, False
        for ch in params:
            if ch in '([{':
                depth += 1
            elif ch in ')]}':
                if depth == 0:
                    break
                depth -= 1
            elif ch == ',' and depth == 0:
                count += 1
            elif not ch.isspace():
                any_ = True
        label = f'{m.group(1)}/{count + 1 if any_ else 0}'
        places = homes.get(line, [])
        marked = file_at(n)
        place = next((p for p in places if p[0] == marked), places[0] if places else (marked, n))
        found.append((n, label, place[0], place[1]))
    return found


def report(counts, lines, starts):
    """The tables of -cover-functions, file by file of the compiler."""
    defs = functions(lines, starts)
    hits = defaultdict(dict)
    ran = defaultdict(dict)
    first = {}
    k, owner = 0, None
    for n in sorted(counts):
        while k < len(defs) and defs[k][0] <= n:
            owner = defs[k]
            k += 1
        if owner is None:
            continue
        _, label, file, at = owner
        hits[file][n] = counts[n]
        first.setdefault((file, label), at)
        ran[file][label] = ran[file].get(label, False) or counts[n] > 0
    rows = []
    for file in sorted(hits):
        missed = sorted((first[(file, label)], label) for label, r in ran[file].items() if not r)
        rows.append((file, len(hits[file]), sum(1 for x in hits[file].values() if x > 0), len(ran[file]), sum(ran[file].values()), missed))
    out = []
    def table(chosen, title):
        lines_all = sum(r[1] for r in chosen)
        lines_run = sum(r[2] for r in chosen)
        fns_all = sum(r[3] for r in chosen)
        fns_run = sum(r[4] for r in chosen)
        out.append(f'\n{title}\nPercentage | Functions run | File\n-----------|---------------|--------------------------')
        for file, total, run, fns, fran, _ in sorted(chosen, key=lambda r: (r[2] / r[1] if r[1] else 1, r[0])):
            out.append(f'{100 * run / total if total else 100:9.1f}% | {f"{fran}/{fns}":>13} | {file}')
        out.append('-----------|---------------|--------------------------')
        out.append(f'{100 * lines_run / lines_all if lines_all else 100:9.1f}% | {f"{fns_run}/{fns_all}":>13} | Total')
        return lines_run, lines_all
    mine = [r for r in rows if r[0] not in OTHER_SYSTEMS]
    other = [r for r in rows if r[0] in OTHER_SYSTEMS]
    table(mine, 'The compiler (for Linux x86-64)')
    table(other, 'Code for other systems')
    for file, _, _, _, _, missed in sorted(mine):
        if missed:
            out.append(f'\n{file}: functions not run: ' + ', '.join(f'{label} ({n})' for n, label in missed))
    return '\n'.join(out) + '\n'


def recorded(compiler, words, jobs, work):
    """What the gates give the compiler: each gate is run with a command in
    its place that keeps what it reads and gives it to the compiler."""
    kept = work / 'given'
    kept.mkdir()
    shim = work / 'recording-compiler'
    # A gate runs the compiler with an empty PATH: every command by its place.
    tools = {name: shutil.which(name) for name in ('sh', 'mktemp', 'cat')}
    shim.write_text(f'#!{tools["sh"]}\nf=$({tools["mktemp"]} {kept}/XXXXXXXXXXXX) || exit 70\n{tools["cat"]} > "$f"\nexec {compiler} "$@" < "$f"\n')
    shim.chmod(0o700)
    quick = load('verify_quick', ROOT / 'scripts/verify-quick.py')
    names = [name for name, call in quick.GATES.items() if call == 'verify(compiler)' and (not words or any(w in name for w in words))]
    if not names:
        raise SystemExit(f'no gate has one of {words} in its name')
    failed = []
    with ThreadPoolExecutor(max(1, jobs)) as pool:
        for name, status, elapsed, _ in pool.map(lambda name: quick.run_gate(name, None, None, shim), names):
            print(f'{elapsed:7.1f}s {"ran " if status == 0 else "FAIL"} {name}', flush=True)
            if status:
                failed.append(name)
    if failed:
        print(f'{len(failed)} of {len(names)} gates failed, and count what they compiled until then: {" ".join(failed)}', flush=True)
    return [path.read_bytes() for path in sorted(kept.iterdir())]


def programs_of(args, directory):
    """The programs, written to directory as NNNNN.alc: how many."""
    texts = []
    if args.gates is not None:
        texts += recorded(args.compiler.resolve(), args.gates, args.jobs, directory.parent)
    if args.search:
        pinned, count, seed = args.search
        generate = load('generate_program_cases', ROOT / 'scripts/generate-program-cases.py')
        made = generate.batches(Path(pinned).resolve(), int(count), seed)
        texts += [generate.program(cases)[0].encode() for cases, _ in made if cases]
    if args.programs:
        texts += [p.read_bytes() for p in sorted(Path(args.programs).glob('*.alc'))]
    largest = int(os.environ.get('ALCHEM_REACH_LARGEST', 1 << 20))
    seen, large = set(), 0
    for text in texts:
        key = hashlib.sha256(text).digest()
        if key in seen:
            continue
        seen.add(key)
        if len(text) > largest:
            large += 1
            continue
        (directory / f'{len(seen):05}.alc').write_bytes(text)
    print(f'{len(texts)} programs given, {len(seen)} different, {large} of more than {largest} bytes left out', flush=True)
    return len(seen) - large


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('compiler', type=Path)
    parser.add_argument('--gates', nargs='*', metavar='WORD')
    parser.add_argument('--search', nargs=3, metavar=('PINNED', 'COUNT', 'SEED'))
    parser.add_argument('--programs', type=Path)
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    parser.add_argument('--keep', type=Path, help='keep the cover file and the report here')
    parser.add_argument('--built', type=Path, help='the test: made and kept there, or used when it is there')
    args = parser.parse_args()
    if args.gates is None and not (args.search or args.programs):
        parser.error('name the programs: --gates, --search or --programs')
    source, starts = assembled()
    with tempfile.TemporaryDirectory(prefix='alchem-reach-') as top:
        work = Path(top)
        every = work / 'programs'
        every.mkdir()
        programs_of(args, every)
        limited = [str(ROOT / 'scripts/limited')]
        env = dict(os.environ, ALCHEM_MEMORY=os.environ.get('ALCHEM_MEMORY', '8G'), ALCHEM_SECONDS=os.environ.get('ALCHEM_SECONDS', '3600'))
        test = work / 'reach'
        if args.built and args.built.exists():
            shutil.copyfile(args.built, test)
        else:
            # Compiling the compiler with its statements counted takes some GiB.
            built = subprocess.run(limited + [str(args.compiler.resolve())], input=bundle(source), capture_output=True, env=dict(env, ALCHEM_MEMORY=os.environ.get('ALCHEM_REACH_BUILD_MEMORY', '12G')))
            if built.returncode or built.stderr:
                raise SystemExit(f'the compiler did not build the test: {built.returncode} {built.stderr.decode(errors="replace")[:300]}')
            test.write_bytes(built.stdout)
            if args.built:
                args.built.parent.mkdir(parents=True, exist_ok=True)
                args.built.write_bytes(built.stdout)
                args.built.chmod(0o700)
        test.chmod(0o700)
        names = sorted(every.iterdir())
        serial = iter(range(1 << 30))
        def run(part):
            """The cover files of a part's programs, and the programs that
            ended the test: a part that does not pass is run as two."""
            k = next(serial)
            place = work / f'part{k}'
            place.mkdir()
            for name in part:
                os.link(name, place / name.name)
            cover = work / f'cover{k}'
            done = subprocess.run(limited + [str(test)], cwd=work, capture_output=True,
                                  # One test compiles every program of the part: no deadline of its own.
                                  env=dict(env, REACH_PROGRAMS=str(place), ALCHEM_COVER_FILE=str(cover), ALCHEM_TEST_TIMEOUT='86400000'))
            text = cover.read_text() if cover.exists() else ''
            shutil.rmtree(place)
            if done.returncode == 0 and text:
                return [text], []
            if len(part) == 1:
                return ([text] if text else []), [part[0]]
            half = len(part) // 2
            first, second = run(part[:half]), run(part[half:])
            return first[0] + second[0], first[1] + second[1]
        parts = [names[i:i + PART] for i in range(0, len(names), PART)]
        with ThreadPoolExecutor(max(1, args.jobs)) as pool:
            results = list(pool.map(run, parts))
        covers = [text for texts, _ in results for text in texts]
        ended = [name for _, names_ in results for name in names_]
        if not covers:
            raise SystemExit('no part wrote a cover file')
        counts = defaultdict(int)
        for text in covers:
            for row in text.splitlines():
                _, line, times = row.split('\t')
                counts[int(line)] += int(times)
        text = report(counts, source.split('\n'), starts)
        if ended:
            text += f'\n{len(ended)} programs ended the test, and count what they reached until then:\n' + ''.join(f'  {name.name} ({name.stat().st_size} bytes): {name.read_bytes()[:60]!r}\n' for name in ended)
        print(text, end='')
        if args.keep:
            args.keep.mkdir(parents=True, exist_ok=True)
            (args.keep / 'cover.tsv').write_text(''.join(f'{n}\t{t}\n' for n, t in sorted(counts.items())))
            (args.keep / 'report.txt').write_text(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
