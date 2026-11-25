#!/usr/bin/env python3
"""Random programs, and what the pinned compiler makes of them: the cases of
harness/programs.py, and a search for programs the native compiler makes
otherwise.

    generate-program-cases.py PINNED --write ALCHEM COUNT [--seed N]    write harness/programs.json.xz
    generate-program-cases.py PINNED --search ALCHEM COUNT [--seed N] [--keep DIR]

A case is the body of a function that gives a string: an expression of a
random type, built from the signatures `doc --all --json` of the pinned
command lists for the library and from the forms of the language (if, case,
cond, with, for, fn, captures, pipes, patterns, structs, sum types, guards,
interpolation, try), shown with inspect. A body that fails gives its message.
A hundred cases are one program. The pinned `check` refuses a case by its
line: the case is left out, as the point is what it takes.

--search runs COUNT cases through ALCHEM too, and prints, smallest first, the
cases it refuses or that print otherwise; --keep writes each to DIR.
--write keeps every case, with the numbers of those ALCHEM refuses (the gate
lets these be refused, and no others). A case ALCHEM answers otherwise than
the pinned command is an error: it is mended, not written down.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import lzma
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'harness/programs.json.xz'
BATCH = 100
# Modules whose functions wait, reach outside the program, or give what
# differs from run to run; single functions likewise. Float.pow is as the
# processor is: Go's uses fused multiply-add where there is one
# (spec/alchem-floats.md, harness/floats.py).
LEFT = set('Process Task Task.Supervisor Agent Server Supervisor DynamicSupervisor Registry Port Node TCP UDP HTTP WebSocket System File IO Logger Testing Gen DiskStore TLS Markup'.split())
LEFT_FUNCTIONS = re.compile(r'Float\.pow|random|shuffle|strong_rand|hash_password|verify_password|utc_now|utc_today|\.now|today|monotonic|sleep|crash|throw|raise|halt|exit|to_existing_atom|from_local|local|expand|absname|wildcard|cwd|tzdata|run_until|interval|repeatedly|cycle|iterate|unfold|resource|flunk|assert|refute|^Kernel\.|print|inspect|unique|memory')
SCALARS = ['integer', 'float', 'string', 'boolean', 'atom']
PRELUDE = '''  struct P do
    x: integer
    name: string = "p"
    tags: list[string] = []
  end

  type Shape do
    dot
    circle(r: integer)
    rect(w: integer, h: integer)
  end

  def area(s: Shape): integer do
    case s do
      Shape.dot -> 0
      Shape.circle(r) when r > 2 -> r * r * 3
      Shape.circle(r) -> r
      Shape.rect(w, h) -> w * h
    end
  end

  def fact(0): integer do
    1
  end

  def fact(n: integer): integer do
    if n < 0 do 0 - n else n * fact(n - 1) end
  end

  def pair(a: a, b: b): tuple[b, a] do
    {b, a}
  end

  def apply_to(x: a, f: fn[a, b]): b do
    f(x)
  end

  def opt(n: integer): option[integer] do
    if n > 0 do some(n) else none end
  end

  def res(n: integer): result[integer, string] do
    if n > 0 do ok(n) else error("bad " <> to_string(n)) end
  end

  defp twice(n: integer, by: integer \\\\ 2): integer do
    n * by
  end
'''


def split_types(text):
    parts, depth, current = [], 0, ''
    for ch in text:
        depth += (ch == '[') - (ch == ']')
        if ch == ',' and depth == 0:
            parts.append(current.strip())
            current = ''
        else:
            current += ch
    return parts + [current.strip()] if current.strip() else parts


def head(t):
    i = t.find('[')
    return (t, []) if i < 0 else (t[:i], split_types(t[i + 1:-1]))


def subst(t, b):
    if t in b:
        return b[t]
    name, args = head(t)
    return name if not args and '[' not in t else f'{name}[{",".join(subst(a, b) for a in args)}]'


def unify(pattern, t, b):
    """Bind the one-letter variables of pattern so that it is t."""
    if re.fullmatch(r'[a-z]', pattern):
        if pattern in b:
            return b[pattern] == t
        b[pattern] = t
        return True
    (p, ps), (n, ns) = head(pattern), head(t)
    return p == n and len(ps) == len(ns) and all(unify(x, y, b) for x, y in zip(ps, ns))


def variables(t):
    return set(re.findall(r'(?<![A-Za-z_.])[a-z](?![A-Za-z_])', t))


def library(pinned):
    """[(name, parameter types, result type)] of the functions used."""
    run = subprocess.run([str(pinned), 'doc', '--all', '--json'], capture_output=True, text=True, check=True)
    found = []
    for module in json.loads(run.stdout):
        for f in module['functions']:
            name = f['name']
            full = name if '.' in name or module['name'] == 'Kernel' else module['name'] + '.' + name
            if module['name'] in LEFT or LEFT_FUNCTIONS.search(full):
                continue
            for signature in f['signatures']:
                m = re.fullmatch(r'[^(]*\((.*)\) -> (.*)', signature)
                if m and 'pid' not in signature and 'generator' not in signature and 'pattern' not in signature:
                    found.append((full, split_types(m.group(1)), m.group(2).strip()))
    return found


class Make:
    def __init__(self, seed, functions):
        self.r = random.Random(seed)
        self.functions = functions
        self.by_result = {}
        for f in functions:
            self.by_result.setdefault(head(f[2])[0] if not re.fullmatch(r'[a-z]', f[2]) else '?', []).append(f)
        self.count = 0

    def name(self):
        self.count += 1
        return f'v{self.count}'

    def type(self, depth=2):
        r = self.r
        if depth == 0 or r.random() < .45:
            return r.choice(SCALARS + ['integer', 'string'])
        kind = r.choice(['list', 'list', 'list', 'option', 'result', 'tuple', 'map', 'set', 'P', 'Shape', 'Date'])
        inner = lambda: self.type(depth - 1)
        if kind in ('list', 'option'):
            return f'{kind}[{inner()}]'
        if kind == 'set':
            return f'set[{r.choice(["integer", "string", "atom"])}]'
        if kind == 'result':
            return f'result[{inner()},string]'
        if kind == 'tuple':
            return f'tuple[{",".join(inner() for _ in range(r.choice([2, 2, 3])))}]'
        if kind == 'map':
            return f'map[{r.choice(["string", "integer", "atom"])},{inner()}]'
        return kind

    def literal(self, t, depth):
        r = self.r
        name, args = head(t)
        e = lambda x: self.expr(x, depth - 1, {})
        if t == 'integer':
            return str(r.choice([0, 1, 2, 3, 5, 7, 10, 42, 100, 255, 1000, -1, -7, 9223372036854775807]))
        if t == 'float':
            return r.choice(['0.0', '1.0', '1.5', '-2.25', '3.75', '100.0', '1.0e10', '0.1'])
        if t == 'string':
            return r.choice(['""', '"a"', '"abc"', '"Hello, World"', '"héllo"', '"a b c"', '"1"', '"42"', '"x\\ty\\n"', '"👍🏽z"', '"AbC,d"', '"  pad "', '"a\\"b"', '"#{1 + 1}z"'])
        if t == 'boolean':
            return r.choice(['true', 'false'])
        if t == 'atom':
            return r.choice([':a', ':b', ':ok', ':lower', ':nfc', ':x_y'])
        if t == 'P':
            return r.choice(['%P{x: ' + e('integer') + '}', '%P{x: 1, name: ' + e('string') + ', tags: ' + e('list[string]') + '}'])
        if t == 'Shape':
            return r.choice(['Shape.dot', f'Shape.circle({e("integer")})', f'Shape.rect({e("integer")}, {e("integer")})'])
        if t == 'Date':
            return r.choice(['~D[2026-01-05]', '~D[2024-02-29]', '~D[1999-12-31]'])
        if t == 'Time':
            return r.choice(['~T[13:04:05]', '~T[00:00:00.250]'])
        if t == 'NaiveDateTime':
            return '~N[2026-01-05 13:04:05]'
        if t == 'DateTime':
            return '~U[2026-01-05 13:04:05Z]'
        if t == 'Range':
            return r.choice(['1..3', '0..5', '5..1//-2', '1..10//3'])
        if t == 'regex':
            return r.choice(['~r/a/', '~r/[a-z]+/i', '~r/(\\d)(\\w*)/'])
        if t == 'Duration':
            return r.choice(['Duration.new!([day: 2])', 'Duration.new!([hour: 1, minute: 30])'])
        if t == 'URI':
            return 'URI.parse("http://e.com/a?b=1")'
        if t == 'Version':
            return 'Version.parse!("1.2.3")'
        if name == 'list':
            if args[0].startswith('tuple[atom,') and r.random() < .3:
                return f'[k: {e(head(args[0])[1][1])}]'
            return '[' + ', '.join(e(args[0]) for _ in range(r.randrange(0 if depth > 0 else 1, 4))) + ']'
        if name == 'option':
            return f'some({e(args[0])})' if r.random() < .75 else 'none'
        if name == 'result':
            return f'ok({e(args[0])})' if r.random() < .7 else f'error({e(args[1])})'
        if name == 'tuple':
            return '{' + ', '.join(e(a) for a in args) + '}'
        if name == 'map':
            return '%{' + ', '.join(f'{self.literal(args[0], 0)} => {e(args[1])}' for _ in range(r.randrange(1, 3))) + '}'
        if name == 'set':
            return f'MapSet.new({self.literal("list[" + args[0] + "]", 0)})'
        if name == 'stream':
            return f'Stream.map({self.literal("list[" + args[0] + "]", 0)}, fn s -> s end)'
        if name == 'enum':
            return self.literal(f'list[{args[0]}]', depth)
        if name == 'fn':
            return self.function(args, depth, {})
        raise KeyError(t)

    def function(self, args, depth, scope):
        params, result = args[:-1], args[-1]
        names = [self.name() for _ in params]
        inner = {**scope, **dict(zip(names, params))}
        body = self.expr(result, depth - 1, inner)
        if self.r.random() < .25:
            return 'fn(' + ', '.join(f'{n}: {p}' for n, p in zip(names, params)) + f'): {result} do {body} end'
        return f'fn {", ".join(names)} -> {body} end' if names else f'fn -> {body} end'

    def call(self, t, depth, scope):
        r = self.r
        pool = self.by_result.get(head(t)[0], []) + self.by_result.get('?', [])
        for _ in range(12):
            if not pool:
                break
            name, params, result = r.choice(pool)
            b = {}
            if not unify(result, t, b):
                continue
            for v in sorted(set().union(*[variables(p) for p in params], set()) - set(b)):
                b[v] = r.choice(['integer', 'string', 'atom', 'tuple[integer,string]', 'list[integer]'] if r.random() < .4 else ['integer', 'string'])
            try:
                args = [self.expr(subst(p, b), depth - 1, scope) for p in params]
            except KeyError:
                continue
            if args and r.random() < .2:
                return f'({args[0]} |> {name}({", ".join(args[1:])}))'
            return f'{name}({", ".join(args)})'
        return self.literal(t, depth)

    def expr(self, t, depth, scope):
        r = self.r
        held = [n for n, ty in scope.items() if ty == t]
        if held and r.random() < .5:
            return r.choice(held)
        if depth <= 0:
            return r.choice(held) if held else self.literal(t, 0)
        e = lambda x, s=None: self.expr(x, depth - 1, scope if s is None else s)
        roll = r.random()
        if roll < .2:
            return self.literal(t, depth)
        if roll < .62:
            return self.call(t, depth, scope)
        forms = ['if', 'case', 'cond', 'with', 'apply', 'elem', 'unwrap', 'casetuple', 'caselist', 'try', 'caseshape', 'capture']
        if t == 'integer':
            forms += ['arith', 'arith', 'area', 'fact', 'bits', 'field', 'reduce', 'twice']
        if t == 'boolean':
            forms += ['compare', 'compare', 'logic', 'in', 'match']
        if t == 'string':
            forms += ['concat', 'interpolate', 'interpolate', 'inspect', 'heredoc']
        if t == 'float':
            forms += ['farith']
        if t.startswith('list['):
            forms += ['for', 'for', 'append', 'cons', 'forfilter', 'minus']
        if t == 'P':
            forms += ['update']
        f = r.choice(forms)
        v, w = self.name(), self.name()
        if f == 'if':
            return f'(if {e("boolean")} do {e(t)} else {e(t)} end)'
        if f == 'case':
            return f'(case opt({e("integer")}) do some({v}) -> {e(t, {**scope, v: "integer"})}; none -> {e(t)} end)'.replace('; ', '\n      ').replace(' do some', ' do\n      some').replace(' end)', '\n    end)', 1) if False else f'(case opt({e("integer")}) do\n      some({v}) -> {e(t, {**scope, v: "integer"})}\n      none -> {e(t)}\n    end)'
        if f == 'caseshape':
            return f'(case {e("Shape")} do\n      Shape.circle({v}) when {v} > 1 -> {e(t, {**scope, v: "integer"})}\n      Shape.rect({v}, _) -> {e(t, {**scope, v: "integer"})}\n      _ -> {e(t)}\n    end)'
        if f == 'casetuple':
            a = r.choice(SCALARS)
            return f'(case {{{e("integer")}, {e(a)}}} do\n      {{0, _}} -> {e(t)}\n      {{{v}, {w}}} -> {e(t, {**scope, v: "integer", w: a})}\n    end)'
        if f == 'caselist':
            a = r.choice(SCALARS)
            return f'(case {e("list[" + a + "]")} do\n      [] -> {e(t)}\n      [{v}] -> {e(t, {**scope, v: a})}\n      [{v}, {w} | _] -> {e(t, {**scope, v: a, w: a})}\n    end)'
        if f == 'cond':
            return f'(cond do\n      {e("boolean")} -> {e(t)}\n      true -> {e(t)}\n    end)'
        if f == 'with':
            return f'(with ok({v}) <- res({e("integer")}),\n          some({w}) <- opt({e("integer")}) do\n      {e(t, {**scope, v: "integer", w: "integer"})}\n    else\n      _ -> {e(t)}\n    end)' if r.random() < .0 else f'(with ok({v}) <- res({e("integer")}) do\n      {e(t, {**scope, v: "integer"})}\n    else\n      error(_) -> {e(t)}\n    end)'
        if f == 'apply':
            a = r.choice(SCALARS + ['list[integer]'])
            return f'apply_to({e(a)}, {self.function([a, t], depth, scope)})'
        if f == 'capture':
            return f'apply_to({e("integer")}, &({self.expr(t, depth - 2, {**scope, "&1": "integer"})}))' if r.random() < 2 and False else f'apply_to({e("integer")}, fn {v} -> {e(t, {**scope, v: "integer"})} end)'
        if f == 'elem':
            return f'elem({{{e("integer")}, {e(t)}}}, 1)'
        if f == 'unwrap':
            return f'elem(pair({e(t)}, {e("string")}), 1)'
        if f == 'try':
            return f'(try do\n      {e(t)}\n    rescue\n      _ -> {e(t)}\n    end)'
        if f == 'arith':
            return f'({e("integer")} {r.choice(["+", "-", "*"])} {e("integer")})' if r.random() < .7 else f'{r.choice(["div", "rem"])}({e("integer")}, {e("integer")})'
        if f == 'bits':
            return f'({e("integer")} {r.choice(["&&&", "|||", "^^^"])} {e("integer")})'
        if f == 'farith':
            return f'({e("float")} {r.choice(["+", "-", "*", "/"])} {e("float")})'
        if f == 'area':
            return f'area({e("Shape")})'
        if f == 'fact':
            return f'fact({r.choice(["0", "3", "5", "20"])})'
        if f == 'twice':
            return f'twice({e("integer")})' if r.random() < .5 else f'twice({e("integer")}, {e("integer")})'
        if f == 'field':
            return f'({e("P")}).x' if False else f'apply_to({e("P")}, fn {v} -> {v}.x end)'
        if f == 'reduce':
            return f'Enum.reduce({e("list[integer]")}, {e("integer")}, fn {v}, {w} -> {e("integer", {**scope, v: "integer", w: "integer"})} end)'
        if f == 'compare':
            a = self.type(1)
            return f'({e(a)} {r.choice(["==", "!="])} {e(a)})' if r.random() < .6 else f'({e("integer")} {r.choice(["<", ">", "<=", ">="])} {e("integer")})'
        if f == 'logic':
            return f'({e("boolean")} {r.choice(["and", "or"])} {e("boolean")})' if r.random() < .7 else f'(not {e("boolean")})'
        if f == 'in':
            a = r.choice(['integer', 'string', 'atom'])
            return f'({e(a)} in {e("list[" + a + "]")})'
        if f == 'match':
            return f'({e("string")} =~ ~r/[a-c]/)'
        if f == 'concat':
            return f'({e("string")} <> {e("string")})'
        if f == 'interpolate':
            return f'"<#{{{e(r.choice(["integer", "string", "float", "boolean", "atom"]))}}}>"' if depth < 2 else f'("<" <> "#{{{self.literal(r.choice(["integer", "float", "boolean"]), 0)}}}" <> {e("string")})'
        if f == 'inspect':
            return f'inspect({e(self.type(2))})'
        if f == 'heredoc':
            return '~s(a "b" #{' + self.literal('integer', 0) + '})'
        if f == 'for':
            a = r.choice(SCALARS)
            return f'for {v} <- {e("list[" + a + "]")}, do: {e(t[5:-1], {**scope, v: a})}' if r.random() < .0 else f'(for {v} <- {e("list[" + a + "]")} do {e(t[5:-1], {**scope, v: a})} end)'
        if f == 'forfilter':
            return f'(for {v} <- {e("list[integer]")}, {v} > {self.literal("integer", 0)}, {w} <- [1, 2] do {e(t[5:-1], {**scope, v: "integer", w: "integer"})} end)'
        if f == 'append':
            return f'({e(t)} ++ {e(t)})'
        if f == 'minus':
            return f'({e(t)} -- {e(t)})'
        if f == 'cons':
            return f'[{e(t[5:-1])} | {e(t)}]'
        if f == 'update':
            return f'apply_to({e("P")}, fn {v} -> %P{{{v} | x: {e("integer", {**scope, v: "P"})}}} end)'
        raise AssertionError(f)

    def case(self):
        """The text of a body that gives a string, and what it reads as."""
        while True:
            self.count = 0
            t = self.type(2)
            r = self.r
            try:
                lines, scope = [], {}
                for _ in range(r.choice([0, 0, 1, 2])):
                    n, ty = self.name(), self.type(1)
                    lines.append(f'{n}: {ty} = {self.expr(ty, 2, scope)}' if r.random() < .5 else f'{n} = {self.expr(ty, 2, scope)}')
                    scope[n] = ty
                lines.append(f'inspect({self.expr(t, r.choice([1, 2, 2, 3]), scope)})')
            except KeyError:
                continue
            if sum(map(len, lines)) < 700:
                return lines


def program(cases):
    """The program of [(number, lines)], and for each line the case it is of."""
    out = ['defmodule Cases do'] + PRELUDE.split('\n')
    of = {}
    for number, lines in cases:
        first = len(out)
        out += [f'  def c{number}(): string do'] + ['    ' + part for line in lines for part in line.split('\n')] + ['  end', '']
        for i in range(first, len(out)):
            of[i + 1] = number
    out += ['  def shown(n: integer, f: fn[string]): tuple[] do', '    text = try do', '      f()', '    rescue', '      m -> "failed: " <> m', '    end', '    IO.puts("#{n} " <> inspect(text))', '    {}', '  end', '', '  def main() do']
    out += [f'    shown({number}, fn -> c{number}() end)' for number, _ in cases]
    out += ['    IO.puts("end")', '  end', 'end', '']
    return '\n'.join(out), of


def answers(text):
    return dict(line.split(' ', 1) for line in text.split('\n') if re.match(r'\d+ ', line))


def command(tool, verb, text, *more, timeout=300):
    with tempfile.TemporaryDirectory(prefix='alchem-programs-') as top:
        path = Path(top).resolve() / 'm.alc'
        path.write_text(text)
        try:
            run = subprocess.run([str(tool), verb, *more, str(path)], capture_output=True, text=True, errors='replace', timeout=timeout, cwd=top)
        except subprocess.TimeoutExpired:
            return 124, '', 'timed out'
        return run.returncode, run.stdout, (run.stdout + run.stderr).replace(str(path), 'm.alc')


def taken(pinned, cases):
    """The cases the pinned compiler takes, and what it prints for each."""
    cases = list(cases)
    for _ in range(4 * len(cases)):
        text, of = program(cases)
        status, _, said = command(pinned, 'check', text)
        if status == 0:
            break
        m = re.search(r'm\.alc:(\d+):', said)
        number = of.get(int(m.group(1))) if m else None
        if number is None:
            return [], {}
        cases = [c for c in cases if c[0] != number]
    if not cases:
        return [], {}
    status, out, said = command(pinned, 'run', program(cases)[0])
    if status == 0 and out.endswith('end\n'):
        # A case that makes a text of megabytes is about memory.
        given = {n: text for n, text in answers(out).items() if len(text) < 4000}
        return [c for c in cases if str(c[0]) in given], given
    if len(cases) == 1:
        return [], {}
    # A case ends the program, or Go refuses what the check took.
    half = len(cases) // 2
    (a, x), (b, y) = taken(pinned, cases[:half]), taken(pinned, cases[half:])
    return a + b, {**x, **y}


def differing(alchem, cases, wanted):
    """[(number, lines, wanted, what alchem gives)]."""
    status, out, said = command(alchem, 'run', program(cases)[0])
    got = answers(out)
    if status == 0 and all(got.get(str(n)) == wanted.get(str(n)) for n, _ in cases):
        return []
    if len(cases) == 1:
        n, lines = cases[0]
        return [(n, lines, wanted.get(str(n)), got.get(str(n)) if status == 0 else said.strip()[:300])]
    if status == 0:
        return [(n, lines, wanted.get(str(n)), got.get(str(n))) for n, lines in cases if got.get(str(n)) != wanted.get(str(n))]
    half = len(cases) // 2
    return differing(alchem, cases[:half], wanted) + differing(alchem, cases[half:], wanted)


def batches(pinned, count, seed):
    functions = library(pinned)
    def one(k):
        make = Make(f'{seed}/{k}', functions)
        return taken(pinned, [(k * BATCH + i, make.case()) for i in range(BATCH)])
    with ThreadPoolExecutor(os.cpu_count() or 4) as pool:
        return list(pool.map(one, range((count + BATCH - 1) // BATCH)))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('pinned', type=Path)
    parser.add_argument('--write', nargs=2, metavar=('ALCHEM', 'COUNT'))
    parser.add_argument('--search', nargs=2, metavar=('ALCHEM', 'COUNT'))
    parser.add_argument('--seed', default='1')
    parser.add_argument('--keep', type=Path)
    args = parser.parse_args()
    pinned = args.pinned.resolve()
    if args.search:
        alchem, count = Path(args.search[0]).resolve(), int(args.search[1])
        made = batches(pinned, count, args.seed)
        with ThreadPoolExecutor(os.cpu_count() or 4) as pool:
            found = [d for part in pool.map(lambda m: differing(alchem, *m) if m[0] else [], made) for d in part]
        total = sum(len(cases) for cases, _ in made)
        print(f'{total} of {count} cases are programs; {len(found)} differ')
        if total * 2 < count:
            raise SystemExit('fewer than half are programs: the generator or the pinned command is at fault')
        found.sort(key=lambda d: sum(map(len, d[1])))
        for n, lines, wanted, got in found:
            print(f'--- {n}')
            print('\n'.join(lines))
            print('  pinned:', wanted)
            print('  native:', got)
            if args.keep:
                args.keep.mkdir(parents=True, exist_ok=True)
                (args.keep / f'{args.seed}-{n}.alc').write_text(program([(n, lines)])[0])
        return 1 if found else 0
    alchem, count = Path(args.write[0]).resolve(), int(args.write[1])
    made = [m for m in batches(pinned, count, args.seed) if m[0]]
    total = sum(len(cases) for cases, _ in made)
    if total * 2 < count:
        raise SystemExit('fewer than half are programs: the generator or the pinned command is at fault')
    with ThreadPoolExecutor(os.cpu_count() or 4) as pool:
        found = [d for part in pool.map(lambda m: differing(alchem, *m), made) for d in part]
    wrong = [d for d in found if 'E_COMPILE' not in (d[3] or '')]
    if wrong:
        raise SystemExit(f'{len(wrong)} cases are answered otherwise than the pinned command answers them: {str(wrong[0])[:1500]}')
    CASES.write_bytes(lzma.compress(json.dumps({'programs': made, 'refused': sorted(d[0] for d in found)}).encode(), preset=9))
    print(f'wrote {CASES.name}: {total} cases in {len(made)} programs, {len(found)} of them refused')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
