#!/usr/bin/env python3
"""What of the compiler a set of programs reaches: the compiler's source,
as the bootstrap assembles it without compacting it, is compiled as the
module under test of a test that compiles each program, and the test's
cover file (ALCHEM_COVER_FILE, spec/alchem-failures.md) is reported as
`alchem test -cover-functions` reports one, file by file of
implementations/alchem.

    compiler-reach.py COMPILER [--gates [WORD...]] [--search PINNED COUNT SEED]
                      [--programs DIR] [--others N] [--jobs N] [--keep DIR]
                      [--built FILE] [--seed FRONTEND BACKEND]

COMPILER is the compiler that builds the test (build/dev/A2), with
ALCHEM_REACH_BUILD_MEMORY (12G); each part runs with ALCHEM_MEMORY (8G).
The programs: --gates, every program the gates (scripts/verify-quick.py
and core_modules and core_tools of the complete suite: those that take the
compiler alone, and with --seed FRONTEND BACKEND those that take the seed's
two as well; all, or those whose names have one of the words given) give
the compiler: each gate is run with a compiler that
keeps what it is given and then compiles it, so a gate that fails counts
what it compiled until then, and is named; --search, the random cases
generate-program-cases.py makes with the pinned command; --programs, the
.alc files of a directory. A program met twice is compiled once, and one of
more than ALCHEM_REACH_LARGEST bytes (1 MiB: the compiler's own source and
the commands bundled with it) is left out and counted. They are compiled a
hundred to a run of the test, --jobs runs at once; a program the compiler
refuses still counts what it reached, and so does one that ends the test
(it is found by running its part in halves, and named).

The test asks what the alchem command asks of the compiler: the program,
why it is refused when it is (nc_explain) and, of one program in ten,
whether it would be taken (nc_checked).

The code for other systems (ARM64, macOS, Windows) is reached only by a
compiler for them, which is the source with another answer of nc_arm() or
nc_win(). --others N builds the test for each of the five systems (SYSTEMS)
and gives the four others one program in N: the first table is then
Linux x86-64 alone, the second every system together, and the functions
listed are those no system ran. Without it the code for other systems is
reported apart and its functions are not listed.

--built FILE keeps the tests (FILE-0 to FILE-4), and uses those that are
there.

The compiler is one module of more than 1 MiB, written with bytes, which
`alchem test` does not take: the test is bundled here.
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
# The systems the compiler compiles for, each a compiler of its own: the
# source with what nc_arm() and nc_win() give (scripts/build-arm64.py,
# build-windows.py), and for macOS SHA-256 as native-sha.alc has it.
SYSTEMS = [('Linux x86-64', 0, 0), ('Linux ARM64', 1, 0), ('Linux ARM64, position-independent', 2, 0), ('macOS ARM64', 3, 0), ('Windows x64', 0, 1)]
# Gates of the complete suite that verify-quick.py does not run.
SUITE = {'core_modules': 'verify(compiler)', 'core_tools': 'verify(compiler)'}
# How many programs one run of the test compiles.
PART = 100
# The test asks of the compiler what the alchem command asks of it
# (tools/alchem.alc): the program, why it is refused when it is, and, of one
# program in ten, whether it would be taken (alchem check).
TEST = '''defmodule AlchemReach do
  import "module:ReachCompiler"

  def asked(name: string, text: bytes): integer do
    made = Enum.count(ReachCompiler.nc_compile(text))
    told = if made == 0 do Enum.count(ReachCompiler.nc_explain(text)) else 0 end
    seen = if String.ends_with?(name, "0.alc") do Enum.count(ReachCompiler.nc_checked(text)) else 0 end
    made + told + seen
  end

  test "the compiler compiles the programs" do
    dir = case System.get_env("REACH_PROGRAMS") do
      some(d) -> d
      none -> "programs"
    end
    names = File.ls!(dir)
    made = Enum.map(names, fn name -> AlchemReach.asked(name, rx_ab(File.read!(dir <> "/" <> name))) end)
    assert(length(made) == length(names))
  end
end
'''


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assembled(traced=False, arm=0, win=0):
    """The compiler's source as one module, and where each file of it
    starts: [(line, file name)]. A line that names the file is put before
    each file's text to find it, and taken out again. traced: as the
    compiler that says where it ends (scripts/compiler-where.py), the
    module and its entry left as they are. arm, win: the compiler for
    another system (SYSTEMS)."""
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
        for name, value in (('nc_arm', arm), ('nc_win', win)):
            switch = f'  def {name}(): integer do 0 end\n'
            if text.count(switch) != 1:
                raise SystemExit(f'the compiler source has no single {name}()')
            text = text.replace(switch, f'  def {name}(): integer do {value} end\n')
        if arm == 3:
            text = bootstrap.darwin(text)
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


def placed(counts, lines, starts):
    """A system's counts by where each line stands in the files:
    {(file, function, the line the function starts at): {line: times}}."""
    defs = functions(lines, starts)
    found = defaultdict(dict)
    k, owner = 0, None
    for n in sorted(counts):
        while k < len(defs) and defs[k][0] <= n:
            owner = defs[k]
            k += 1
        if owner is not None:
            first, label, file, at = owner
            found[(file, label, at)][at + n - first] = counts[n]
    return found


def report(systems):
    """The tables of -cover-functions, file by file of the compiler.
    systems: [(name, counts by where they stand)], the first Linux x86-64."""
    out = []

    def table(found, chosen, title):
        rows = defaultdict(lambda: [0, 0, 0, 0])
        for (file, label, at), hits in found.items():
            if chosen(file):
                row = rows[file]
                row[0] += len(hits)
                row[1] += sum(1 for times in hits.values() if times > 0)
                row[2] += 1
                row[3] += 1 if any(hits.values()) else 0
        out.append(f'\n{title}\nPercentage | Functions run | File\n-----------|---------------|--------------------------')
        for file, (total, run, fns, fran) in sorted(rows.items(), key=lambda r: (r[1][1] / r[1][0] if r[1][0] else 1, r[0])):
            out.append(f'{100 * run / total if total else 100:9.1f}% | {f"{fran}/{fns}":>13} | {file}')
        total, run, fns, fran = (sum(row[i] for row in rows.values()) for i in range(4))
        out.append('-----------|---------------|--------------------------')
        out.append(f'{100 * run / total if total else 100:9.1f}% | {f"{fran}/{fns}":>13} | Total')

    table(systems[0][1], lambda file: file not in OTHER_SYSTEMS, f'Compiling for {systems[0][0]}')
    every = defaultdict(dict)
    for _, found in systems:
        for key, hits in found.items():
            for line, times in hits.items():
                every[key][line] = every[key].get(line, 0) + times
    if len(systems) > 1:
        table(every, lambda file: True, 'Compiling for ' + ', '.join(name for name, _ in systems))
    else:
        table(every, lambda file: file in OTHER_SYSTEMS, 'Code for other systems, compiling for this one')
    missed = defaultdict(list)
    for (file, label, at), hits in every.items():
        if not any(hits.values()) and (len(systems) > 1 or file not in OTHER_SYSTEMS):
            missed[file].append((at, label))
    for file in sorted(missed):
        out.append(f'\n{file}: functions not run: ' + ', '.join(f'{label} ({n})' for n, label in sorted(missed[file])))
    return '\n'.join(out) + '\n'


def recorded(compiler, words, jobs, work, seed=None):
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
    # The gates of the complete suite that take the compiler alone
    # (scripts/verify-local.sh), and with --seed those that take the seed's
    # frontend and backend as well.
    quick.GATES.update(SUITE)
    frontend, backend = seed or (None, None)
    names = [name for name, call in quick.GATES.items() if (call == 'verify(compiler)' or seed) and (not words or any(w in name for w in words))]
    if not seed:
        print('not run without --seed: ' + ' '.join(name for name, call in quick.GATES.items() if call != 'verify(compiler)'), flush=True)
    if not names:
        raise SystemExit(f'no gate has one of {words} in its name')
    failed = []
    with ThreadPoolExecutor(max(1, jobs)) as pool:
        for name, status, elapsed, _ in pool.map(lambda name: quick.run_gate(name, frontend, backend, shim), names):
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
        texts += recorded(args.compiler.resolve(), args.gates, args.jobs, directory.parent, [p.resolve() for p in args.seed] if args.seed else None)
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
    parser.add_argument('--built', type=Path, help='the tests (FILE-0, FILE-1, ...): made and kept there, or used when they are there')
    parser.add_argument('--seed', nargs=2, type=Path, metavar=('FRONTEND', 'BACKEND'), help='with --gates: the gates that take the seed\'s frontend and backend too')
    parser.add_argument('--others', type=int, default=0, metavar='N', help='compile for the other systems too, one program in N')
    args = parser.parse_args()
    if args.gates is None and not (args.search or args.programs):
        parser.error('name the programs: --gates, --search or --programs')
    with tempfile.TemporaryDirectory(prefix='alchem-reach-') as top:
        work = Path(top)
        every = work / 'programs'
        every.mkdir()
        programs_of(args, every)
        limited = [str(ROOT / 'scripts/limited')]
        env = dict(os.environ, ALCHEM_MEMORY=os.environ.get('ALCHEM_MEMORY', '8G'), ALCHEM_SECONDS=os.environ.get('ALCHEM_SECONDS', '3600'))
        names = sorted(every.iterdir())
        serial = iter(range(1 << 30))
        systems, ended, kept = [], [], ''
        for index, (system, arm, win) in enumerate(SYSTEMS if args.others else SYSTEMS[:1]):
            source, starts = assembled(arm=arm, win=win)
            test = work / f'reach{index}'
            built_at = args.built.with_name(f'{args.built.name}-{index}') if args.built else None
            if built_at and built_at.exists():
                shutil.copyfile(built_at, test)
            else:
                # Compiling the compiler with its statements counted takes some GiB.
                built = subprocess.run(limited + [str(args.compiler.resolve())], input=bundle(source), capture_output=True, env=dict(env, ALCHEM_MEMORY=os.environ.get('ALCHEM_REACH_BUILD_MEMORY', '12G')))
                if built.returncode or built.stderr:
                    raise SystemExit(f'the compiler did not build the test for {system}: {built.returncode} {built.stderr.decode(errors="replace")[:300]}')
                test.write_bytes(built.stdout)
                if built_at:
                    built_at.parent.mkdir(parents=True, exist_ok=True)
                    built_at.write_bytes(built.stdout)
                    built_at.chmod(0o700)
            test.chmod(0o700)

            def run(part, test=test):
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
                cover.unlink(missing_ok=True)
                if done.returncode == 0 and text:
                    return [text], []
                if len(part) == 1:
                    return ([text] if text else []), [part[0]]
                half = len(part) // 2
                first, second = run(part[:half]), run(part[half:])
                return first[0] + second[0], first[1] + second[1]
            # Every program for the first system; one in --others for the rest.
            chosen = names if index == 0 else names[::args.others]
            parts = [chosen[i:i + PART] for i in range(0, len(chosen), PART)]
            with ThreadPoolExecutor(max(1, args.jobs)) as pool:
                results = list(pool.map(run, parts))
            covers = [text for texts, _ in results for text in texts]
            ended += [(system, name) for _, names_ in results for name in names_]
            if not covers:
                raise SystemExit(f'no part wrote a cover file for {system}')
            counts = defaultdict(int)
            for text in covers:
                for row in text.splitlines():
                    _, line, times = row.split('\t')
                    counts[int(line)] += int(times)
            print(f'{system}: {len(chosen)} programs', flush=True)
            systems.append((system, placed(counts, source.split('\n'), starts)))
            kept += ''.join(f'{system}\t{file}\t{line}\t{times}\n' for (file, _, _), hits in sorted(systems[-1][1].items()) for line, times in sorted(hits.items()))
        text = report(systems)
        if ended:
            text += f'\n{len(ended)} programs ended the test, and count what they reached until then:\n' + ''.join(f'  {system}: {name.name} ({name.stat().st_size} bytes): {name.read_bytes()[:60]!r}\n' for system, name in ended)
        print(text, end='')
        if args.keep:
            args.keep.mkdir(parents=True, exist_ok=True)
            (args.keep / 'cover.tsv').write_text(kept)
            (args.keep / 'report.txt').write_text(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
