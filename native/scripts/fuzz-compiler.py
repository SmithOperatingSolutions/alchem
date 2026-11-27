#!/usr/bin/env python3
"""Programs the compiler must take or refuse, and nothing else: a search
that needs no other compiler to say what is right.

    fuzz-compiler.py COMPILER COUNT [--seed S] [--jobs N] [--keep DIR]
                     [--kinds changed,made] [--seconds T] [--memory BYTES]

COUNT cases are made from the seed, the same ones every time. Two kinds:

changed  a program of the gates (harness/*.py RUNS) or of examples/, with
         one to three small changes: a token taken out, doubled, exchanged
         with its neighbour or replaced by one of another place, a line
         taken out or doubled, the text cut short, a number made large, a
         byte put in. Most are no longer programs. The compiler must give
         an executable with status 0 and nothing on standard error, or
         nothing with status 65: any other status, a signal, more than
         --seconds (120) or more than --memory (2 GiB) of memory is a
         failure. A changed program is not run: what it does is not known.
made     a program written here with what it prints: hundreds or thousands
         of bindings, statements between them, function values that hold
         them, long sums, nested conditions, many functions, many clauses,
         long lists. The compiler must take it, twice alike, and the
         program must print that.

A failure is printed with its case; --keep writes each to DIR, a changed
one made smaller first (lines are taken out while it still fails the same
way). The status is 1 when there is one.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import importlib.util
import multiprocessing
import os
from pathlib import Path
import random
import re
import resource
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'"(?:\\.|[^"\\\n])*"|[A-Za-z_][A-Za-z0-9_]*[?!]?|\d+(?:\.\d+)?|\s+|[^\sA-Za-z0-9_]')
NUMBERS = ['0', '1', '255', '256', '65535', '65536', '2147483647', '2147483648', '4294967296',
           '9223372036854775807', '9223372036854775808', '18446744073709551616', '99999999999999999999999999']
WORDS = ['do', 'end', 'else', 'fn', '->', 'case', 'if', 'def', 'defmodule', 'when', '|>', '<>', '(', ')', '[', ']', '{', '}',
         ',', ':', '=', '==', '"', '#{', '%', '&', '\\\\', 'with', 'for', '<-', 'try', 'rescue', 'cond', 'true', 'nil', '\n']


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def corpus():
    """The programs that are changed: those of the gates and the examples."""
    examples = load('windows_examples', ROOT / 'scripts/windows-examples.py')
    alike, otherwise, _ = examples.gate_cases()
    texts = [c['source'] for c in alike + otherwise]
    texts += [p.read_text() for p in sorted((ROOT / 'examples').glob('*.alc'))]
    return sorted(set(t for t in texts if len(t) < 20000))


def changed(rng, texts):
    text = rng.choice(texts)
    for _ in range(rng.choice([1, 1, 1, 2, 2, 3])):
        tokens = TOKEN.findall(text)
        if len(tokens) < 4:
            break
        lines = text.split('\n')
        at = rng.randrange(len(tokens))
        kind = rng.randrange(11)
        if kind == 0:
            del tokens[at]
        elif kind == 1:
            tokens.insert(at, tokens[at])
        elif kind == 2 and at + 1 < len(tokens):
            tokens[at], tokens[at + 1] = tokens[at + 1], tokens[at]
        elif kind == 3:
            tokens[at] = rng.choice(tokens)
        elif kind == 4:
            tokens[at] = rng.choice(TOKEN.findall(rng.choice(texts)) or ['x'])
        elif kind == 5:
            tokens.insert(at, rng.choice(WORDS))
        elif kind == 6:
            numbers = [i for i, t in enumerate(tokens) if t[0].isdigit()]
            if numbers:
                tokens[rng.choice(numbers)] = rng.choice(NUMBERS)
        elif kind == 7:
            del lines[rng.randrange(len(lines))]
            tokens = None
        elif kind == 8:
            k = rng.randrange(len(lines))
            lines.insert(k, lines[k])
            tokens = None
        elif kind == 9:
            tokens = tokens[:at]
        else:
            tokens.insert(at, chr(rng.choice([0, 9, 13, 34, 35, 92, 123, 127, 128, 233, 0x2028, 0x1F600])))
        text = '\n'.join(lines) if tokens is None else ''.join(tokens)
    return text.encode('utf8', 'surrogatepass')


def main_of(body, more=''):
    return 'defmodule M do\n' + more + '  def main() do\n' + ''.join('    ' + line + '\n' for line in body) + '    System.halt(0)\n  end\nend\n'


def made(rng):
    """(a program, what it prints)."""
    size = rng.choice([3, 20, 95, 130, 300, 300, 700, 2000])
    kind = rng.randrange(7)
    out = []
    if kind == 0:
        # Bindings, each of one or two before it, and statements between.
        values, body, held = [rng.randrange(-9, 10)], [], []
        body.append(f'x0 = {values[0]}')
        for i in range(1, size):
            j, k, c = rng.randrange(i), rng.randrange(i), rng.randrange(1, 50)
            form = rng.randrange(6)
            if form == 0 and abs(values[j] + values[k]) < 1 << 40:
                body.append(f'x{i} = x{j} + x{k}')
                values.append(values[j] + values[k])
            elif form == 1 and abs(values[j] - values[k]) < 1 << 40:
                body.append(f'x{i} = (x{j} - x{k}) + {c}')
                values.append(values[j] - values[k] + c)
            elif form == 2:
                body.append(f'x{i} = if x{j} > x{k} do x{j} - {c} else x{k} + {c} end')
                values.append(values[j] - c if values[j] > values[k] else values[k] + c)
            elif form == 3:
                body.append(f'f{i}: fn[integer, integer] = fn a -> a + x{j} - {c} end')
                body.append(f'x{i} = f{i}(x{k})')
                held.append((i, j, c))
                values.append(values[k] + values[j] - c)
            else:
                body.append(f'x{i} = x{j} + {c}')
                values.append(values[j] + c)
            if rng.randrange(12) == 0:
                body.append(f'IO.puts(Integer.to_string(x{k}))')
                out.append(str(values[k]))
            if rng.randrange(20) == 0:
                body.append(f'if x{j} > {c} do IO.puts("more {i}") else IO.puts("less {i}") end')
                out.append(f'more {i}' if values[j] > c else f'less {i}')
            if held and rng.randrange(15) == 0:
                h, j2, c2 = rng.choice(held)
                body.append(f'IO.puts(Integer.to_string(f{h}(x{k})))')
                out.append(str(values[k] + values[j2] - c2))
        body.append(f'IO.puts("#{{x{size - 1}}} #{{x{size // 2}}} #{{x0}}")')
        out.append(f'{values[-1]} {values[size // 2]} {values[0]}')
        return main_of(body), out
    if kind == 1:
        # A long sum, in brackets here and there.
        # 1,024 operators are taken in one chain (spec/source-capacity.md).
        terms = [rng.randrange(1, 1000) for _ in range(min(size, 1000))]
        # Brackets inside one another: 126 are taken (spec/source-capacity.md).
        text, total, inside = str(terms[0]), terms[0], 0
        for t in terms[1:]:
            if rng.randrange(8) == 0 and inside < 100:
                inside += 1
                text, total = f'({text}) - {t}', total - t
            else:
                text, total = f'{text} + {t}', total + t
        return main_of([f'x = {text}', 'IO.puts(Integer.to_string(x))']), [str(total)]
    if kind == 2:
        # Conditions inside one another.
        depth = min(size, rng.choice([2, 8, 15, 40, 120]))
        k = rng.randrange(depth + 2)
        text = '0'
        for d in range(depth, 0, -1):
            text = f'if k == {d} do {d * 7} else {text} end'
        more = f'  def pick(k: integer): integer do\n    {text}\n  end\n'
        return main_of([f'IO.puts(Integer.to_string(pick({k})))', 'IO.puts(Integer.to_string(pick(0)))'], more), [str(k * 7 if 1 <= k <= depth else 0), '0']
    if kind == 3:
        # Many functions, each calling the one before.
        adds = [rng.randrange(1, 100) for _ in range(size)]
        more = '  def f0(n: integer): integer do\n    n + %d\n  end\n' % adds[0]
        more += ''.join(f'  def f{i}(n: integer): integer do\n    f{i - 1}(n) + {adds[i]}\n  end\n' for i in range(1, size))
        return main_of([f'IO.puts(Integer.to_string(f{size - 1}(5)))', f'IO.puts(Integer.to_string(f{size // 2}(0)))'], more), [str(5 + sum(adds)), str(sum(adds[:size // 2 + 1]))]
    if kind == 4:
        # A function of many clauses.
        count = min(size, 300)
        gives = [rng.randrange(1000) for _ in range(count)]
        more = ''.join(f'  def pick({i}): integer do\n    {gives[i]}\n  end\n' for i in range(count))
        more += '  def pick(n: integer): integer do\n    0 - n\n  end\n'
        asked = [rng.randrange(count + 3) for _ in range(5)]
        return main_of([f'IO.puts(Integer.to_string(pick({a})))' for a in asked], more), [str(gives[a] if a < count else -a) for a in asked]
    if kind == 5:
        # A long list, and a function value that holds a binding.
        items = [rng.randrange(-500, 500) for _ in range(size)]
        add = rng.randrange(100)
        body = [f'by = {add}', f'items = [{", ".join(str(i) for i in items)}]',
                'more = Enum.map(items, fn v -> v + by end)',
                'IO.puts(Integer.to_string(Enum.count(more)))',
                'IO.puts(Integer.to_string(Enum.reduce(more, 0, fn v, acc -> acc + v end)))',
                'IO.puts(Integer.to_string(Enum.count(Enum.filter(items, fn v -> v > by end))))']
        return main_of(body), [str(size), str(sum(items) + add * size), str(sum(1 for i in items if i > add))]
    # Strings bound one after another, joined and interpolated.
    values, body = ['s'], ['t0 = "s"']
    for i in range(1, min(size, 400)):
        j = rng.randrange(i)
        if rng.randrange(2) and len(values[j]) < 40:
            body.append(f't{i} = t{j} <> "{i}"')
            values.append(values[j] + str(i))
        else:
            body.append(f't{i} = "<#{{t{j}}}>"' if len(values[j]) < 40 else f't{i} = "{i}"')
            values.append(f'<{values[j]}>' if len(values[j]) < 40 else str(i))
        if rng.randrange(10) == 0:
            body.append(f'IO.puts(t{i})')
            out.append(values[i])
    body.append(f'IO.puts(t{len(values) - 1})')
    out.append(values[-1])
    return main_of(body), out


def compiled(compiler, text, seconds, memory):
    """(what is wrong or None, the executable): the compiler gives an
    executable or refuses, within the time and the memory."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    try:
        done = subprocess.run([compiler], input=text, capture_output=True, env={'PATH': ''}, timeout=seconds)
    except subprocess.TimeoutExpired:
        return f'the compiler took more than {seconds} s', None
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss * 1024
    if peak > memory and peak > before * 1024:
        return f'the compiler took {peak >> 20} MiB', None
    if done.returncode == 0 and done.stderr == b'' and done.stdout[:4] == b'\x7fELF':
        return None, done.stdout
    if done.returncode == 65 and done.stdout == b'':
        return None, None
    if done.returncode < 0:
        return f'the compiler ended by signal {-done.returncode}', None
    return f'the compiler ended with status {done.returncode}, {len(done.stdout)} bytes and {done.stderr[:200]!r}', None


def one(job):
    compiler, kind, text, wanted, seconds, memory = job
    wrong, image = compiled(compiler, text, seconds, memory)
    if wrong or kind == 'changed':
        return wrong
    if image is None:
        return 'the compiler refused it'
    again = compiled(compiler, text, seconds, memory)[1]
    if again != image:
        return 'the compiler made another executable the second time'
    with tempfile.TemporaryDirectory(prefix='alchem-fuzz-') as d:
        program = Path(d) / 'program'
        program.write_bytes(image)
        program.chmod(0o700)
        try:
            run = subprocess.run([str(program)], capture_output=True, env={'PATH': ''}, cwd=d, timeout=seconds)
        except subprocess.TimeoutExpired:
            return f'the program took more than {seconds} s'
    if (run.returncode, run.stdout, run.stderr) != (0, wanted, b''):
        return f'the program ended with status {run.returncode} and printed {run.stdout[-200:]!r} {run.stderr[:200]!r}, not {wanted[-200:]!r}'
    return None


def smaller(compiler, text, wrong, seconds, memory):
    """The text with the lines taken out that the failure does not need."""
    def same(candidate):
        return compiled(compiler, candidate, seconds, memory)[0] == wrong
    lines = text.split(b'\n')
    size = max(1, len(lines) // 2)
    tries = 0
    while size >= 1 and tries < 400:
        at, cut = 0, False
        while at < len(lines) and tries < 400:
            rest = lines[:at] + lines[at + size:]
            tries += 1
            if rest and same(b'\n'.join(rest)):
                lines, cut = rest, True
            else:
                at += size
        if size == 1 and not cut:
            break
        size = max(1, size // 2) if size > 1 else 1
    return b'\n'.join(lines)


def cases(seed, count, kinds):
    """The cases of a seed: (number, kind, text, what it prints)."""
    texts = corpus() if 'changed' in kinds else []
    for number in range(count):
        rng = random.Random(f'{seed}/{number}')
        # One case in eight is made: they are the large ones.
        kind = 'made' if 'changed' not in kinds or ('made' in kinds and number % 8 == 0) else 'changed'
        if kind == 'made':
            text, out = made(rng)
            yield number, kind, text.encode(), ''.join(line + '\n' for line in out).encode()
        else:
            yield number, kind, changed(rng, texts), b''


def search(compiler, count, seed, jobs, kinds, seconds, memory, keep=None, say=print):
    """How many cases failed; each is said, and kept."""
    failed = 0
    every = list(cases(seed, count, kinds))
    # Processes, each with the memory of its own compiles; forked, so that a
    # gate that loads this file by its path has its functions there too.
    with ProcessPoolExecutor(max(1, jobs), mp_context=multiprocessing.get_context('fork')) as pool:
        results = pool.map(one, [(str(compiler), kind, text, wanted, seconds, memory) for _, kind, text, wanted in every], chunksize=8)
        for (number, kind, text, wanted), wrong in zip(every, results):
            if wrong is None:
                continue
            failed += 1
            if kind == 'changed' and not wrong.startswith('the compiler took'):
                text = smaller(str(compiler), text, wrong, seconds, memory)
            say(f'FAIL case {number} ({kind}, {len(text)} bytes, {hashlib.sha256(text).hexdigest()[:12]}): {wrong}')
            if keep:
                keep.mkdir(parents=True, exist_ok=True)
                (keep / f'{number:06}.alc').write_bytes(text)
                (keep / f'{number:06}.txt').write_text(f'seed {seed} case {number} ({kind})\n{wrong}\n')
    return failed


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('compiler', type=Path)
    parser.add_argument('count', type=int)
    parser.add_argument('--seed', default='1')
    parser.add_argument('--jobs', type=int, default=os.cpu_count() or 4)
    parser.add_argument('--keep', type=Path)
    parser.add_argument('--kinds', default='changed,made')
    parser.add_argument('--seconds', type=int, default=120)
    parser.add_argument('--memory', type=int, default=2 << 30)
    args = parser.parse_args()
    kinds = set(args.kinds.split(','))
    if not kinds or kinds - {'changed', 'made'}:
        parser.error('--kinds: changed, made or both')
    failed = search(args.compiler.resolve(), args.count, args.seed, args.jobs, kinds, args.seconds, args.memory, args.keep)
    if failed:
        print(f'{failed} of {args.count} cases failed (seed {args.seed})')
        return 1
    print(f'PASS {args.count} cases (seed {args.seed}): the compiler took or refused each, and what it made of the made ones printed what they say')
    return 0


if __name__ == '__main__':
    sys.exit(main())
