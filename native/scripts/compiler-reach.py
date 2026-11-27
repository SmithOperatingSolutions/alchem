#!/usr/bin/env python3
"""What of the compiler a set of programs reaches: the compiler's source,
as the bootstrap assembles it without compacting it, is compiled as the
module under test of a test that compiles each program, and the test's
cover file (ALCHEM_COVER_FILE, spec/alchem-failures.md) is reported as
`alchem test -cover-functions` reports one, file by file of
implementations/alchem.

    compiler-reach.py COMPILER [--gates] [--search PINNED COUNT SEED]
                      [--programs DIR] [--jobs N] [--keep DIR]

COMPILER is the compiler that builds the test (build/dev/A2), with
ALCHEM_REACH_BUILD_MEMORY (12G); each part runs with ALCHEM_MEMORY (8G). The programs:
--gates, those of the gates (harness/*.py RUNS, as windows-examples.py
collects them) and the upstream examples; --search, the random cases
generate-program-cases.py makes with the pinned command; --programs, the
.alc files of a directory. They are compiled in --jobs parts at once; a
program the compiler refuses still counts what it reached.

The compiler is one module of more than 1 MiB, which `alchem test` (the
bundler and the front end, as the pinned command) does not take: the test
is bundled here. The code for other systems (ARM64, macOS, Windows) is
reached only by compiling for them, and is reported apart.
"""
import argparse
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


def assembled():
    """The compiler's source as one module, and where each file of it
    starts: [(line, file name)]. A line that names the file is put before
    each file's text to find it, and taken out again."""
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
        text = bootstrap.source_text('functions', False)
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


def programs_of(args, directory):
    """The programs, written to directory as NNNNN.alc: how many."""
    texts = []
    if args.gates:
        examples = load('windows_examples', ROOT / 'scripts/windows-examples.py')
        alike, otherwise, _ = examples.gate_cases()
        texts += [c['source'] for c in alike + otherwise]
        upstream = load('upstream_examples', ROOT / 'scripts/upstream-examples.py')
        texts += [source for _, source in upstream.cases()]
    if args.search:
        pinned, count, seed = args.search
        generate = load('generate_program_cases', ROOT / 'scripts/generate-program-cases.py')
        made = generate.batches(Path(pinned).resolve(), int(count), seed)
        texts += [generate.program(cases)[0] for cases, _ in made if cases]
    if args.programs:
        texts += [p.read_text() for p in sorted(Path(args.programs).glob('*.alc'))]
    for i, text in enumerate(texts):
        (directory / f'{i:05}.alc').write_text(text)
    return len(texts)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('compiler', type=Path)
    parser.add_argument('--gates', action='store_true')
    parser.add_argument('--search', nargs=3, metavar=('PINNED', 'COUNT', 'SEED'))
    parser.add_argument('--programs', type=Path)
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    parser.add_argument('--keep', type=Path, help='keep the cover file and the report here')
    args = parser.parse_args()
    if not (args.gates or args.search or args.programs):
        parser.error('name the programs: --gates, --search or --programs')
    source, starts = assembled()
    with tempfile.TemporaryDirectory(prefix='alchem-reach-') as top:
        work = Path(top)
        every = work / 'programs'
        every.mkdir()
        count = programs_of(args, every)
        print(f'{count} programs', flush=True)
        limited = [str(ROOT / 'scripts/limited')]
        env = dict(os.environ, ALCHEM_MEMORY=os.environ.get('ALCHEM_MEMORY', '8G'), ALCHEM_SECONDS=os.environ.get('ALCHEM_SECONDS', '3600'))
        # Compiling the compiler with its statements counted takes some GiB.
        built = subprocess.run(limited + [str(args.compiler.resolve())], input=bundle(source), capture_output=True, env=dict(env, ALCHEM_MEMORY=os.environ.get('ALCHEM_REACH_BUILD_MEMORY', '12G')))
        if built.returncode or built.stderr:
            raise SystemExit(f'the compiler did not build the test: {built.returncode} {built.stderr.decode(errors="replace")[:300]}')
        test = work / 'reach'
        test.write_bytes(built.stdout)
        test.chmod(0o700)
        names = sorted(every.iterdir())
        parts = [names[i::args.jobs] for i in range(args.jobs) if names[i::args.jobs]]
        def run(k):
            part = work / f'part{k}'
            part.mkdir()
            for name in parts[k]:
                os.link(name, part / name.name)
            cover = work / f'cover{k}'
            subprocess.run(limited + [str(test)], cwd=work, capture_output=True,
                           # One test compiles every program of the part: no deadline of its own.
                           env=dict(env, REACH_PROGRAMS=str(part), ALCHEM_COVER_FILE=str(cover), ALCHEM_TEST_TIMEOUT='86400000'))
            return cover.read_text() if cover.exists() else ''
        with ThreadPoolExecutor(len(parts)) as pool:
            covers = list(pool.map(run, range(len(parts))))
        if not all(covers):
            raise SystemExit(f'{sum(1 for c in covers if not c)} of {len(parts)} parts wrote no cover file')
        counts = defaultdict(int)
        for text in covers:
            for row in text.splitlines():
                _, line, times = row.split('\t')
                counts[int(line)] += int(times)
        text = report(counts, source.split('\n'), starts)
        print(text, end='')
        if args.keep:
            args.keep.mkdir(parents=True, exist_ok=True)
            (args.keep / 'cover.tsv').write_text(''.join(f'{n}\t{t}\n' for n, t in sorted(counts.items())))
            (args.keep / 'report.txt').write_text(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
