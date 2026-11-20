#!/usr/bin/env python3
"""Floats on ARM64 as the pinned compiler's ARM64 programs have them.

Go's compiler for ARM64 makes an addition or subtraction of floats with a
product as an operand one fused multiply-add, through a variable and
through a function it inlines; its math.Log is log.go compiled so and its
math.Exp exp_arm64.s (spec/arm64.md). A program of FORMS, each a function of
four floats parsed at run time (so that no compiler folds them), built for
ARM64 by the compiler and run under QEMU, must print what the same program
built by the pinned compiler for linux/arm64 prints, and built for x86-64
what the pinned compiler's x86-64 program prints. Those are kept in
harness/arm64-floats.json; with build/dev/alchem-upstream at hand
`--freeze` makes them again.

The one form left out is a sum of two products: which of them Go fuses
follows how its CSE numbers every value of the function the sum is inlined
into (spec/arm64.md)."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import os
import random
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run import ROOT  # noqa: E402

TOOLS = ROOT / 'build/arm64-tools/bin'
FROZEN = Path(__file__).resolve().parent / 'arm64-floats.json'
FORMS = ['a * b + c', 'a * b - c', 'c - a * b', 'c + a * b', 'a * b * c + d', '(a + b) * c + d', 'a / b + c', 'a * b',
         'a + b + c', 'a * b - c * d', 'a * a - b * b', 'sq(a) + b', 'b - sq(a)', 'mul(a, b) + c', 'c - mul(a, b)',
         '(a * b) + c', '-(a * b) + c', '-(a * b) - c', 'c + (a * b) * d', 'big(a, b) + c', 'scaled(a) - c',
         'VARt = a * b\n    t + c', 'VARt = a * b\n    c - t', 'VARt = mul(a, b)\n    t + c', 'VARt = a * b\n    u = t + d\n    u + c',
         # Constants through names, which Go's compiler folds (and then fuses nothing).
         'VARk = 2.5\n    t = k * 3.0\n    t + a', 'VARk = 2.5\n    t = k * a\n    t + c', 'VARk = 1.0e308\n    u = k * 10.0\n    u - u + a',
         'VARk = -(0.5 * 3.0)\n    k * b + c',
         'Float.pow(abs(a), b / 10.0)', 'Float.pow(a, 3.0)', 'Float.round(a, 3)', 'Float.floor(a * 100.0) / 100.0',
         'Float.round(a * b + c, 5)', 'Float.ceil(a, 2)', 'a ** b', 'abs(a) ** (b / 7.0)',
         'Float.pow(1.0 + abs(a) / 1000.0, abs(b) * 100.0)']
HELPERS = ['  def p(s: string): float do', '    case Float.parse(s) do', '      ok(x) -> x', '      error(_) -> 0.0', '    end', '  end',
           '  def abs(x: float): float do if x < 0.0 do 0.0 - x else x end end',
           '  def sq(x: float): float do x * x end',
           '  def mul(x: float, y: float): float do x * y end',
           # Inlined by Go and a product at its top: (x+y)*(x-y)*0.5.
           '  def big(x: float, y: float): float do (x + y) * (x - y) * 0.5 end',
           '  def scaled(x: float): float do 2.5e-3 * x end']


def program(seed=1, count=500):
    rng = random.Random(seed)

    def value():
        k = rng.random()
        if k < .3:
            x = rng.uniform(-10, 10)
        elif k < .6:
            x = rng.uniform(-1, 1) * 10 ** rng.randrange(-20, 20)
        elif k < .8:
            x = rng.uniform(0, 3)
        else:
            x = float(rng.randrange(-100, 100)) / rng.choice([1, 3, 7, 10, 1000])
        return '%.17e' % x
    lines = ['defmodule M do', *HELPERS]
    body = []
    for i in range(count):
        form = rng.choice(FORMS)
        a, b, c, d = value(), value(), value(), value()
        if form.startswith('VAR'):
            lines.append(f'  def f{i}(a: float, b: float, c: float, d: float): float do\n    {form[3:]}\n  end')
        else:
            lines.append(f'  def f{i}(a: float, b: float, c: float, d: float): float do {form} end')
        body.append(f'    IO.puts(inspect(f{i}(p("{a}"), p("{b}"), p("{c}"), p("{d}"))))')
    return '\n'.join(lines + ['  def main() do'] + body + ['  end', 'end', ''])


def ran(command, cwd):
    done = subprocess.run(command, capture_output=True, cwd=cwd, timeout=300, stdin=subprocess.DEVNULL)
    return [done.returncode, done.stdout.decode(), done.stderr.decode()]


def freeze():
    source = program()
    env = dict(os.environ, GOTOOLCHAIN='local', GOPROXY='off', GOFLAGS='-mod=mod')
    upstream = ROOT / 'build/dev/alchem-upstream'
    with tempfile.TemporaryDirectory(prefix='alchem-arm64-floats-') as d:
        root = Path(d)
        (root / 'p.alc').write_text(source)
        frozen = {}
        for name, target, run in (('amd64', [], []), ('arm64', ['-target', 'linux/arm64'], [str(TOOLS / 'qemu-aarch64-static')])):
            subprocess.run([str(upstream), 'build', *target, '-o', str(root / name), str(root / 'p.alc')], check=True, env=env, timeout=600)
            frozen[name] = ran(run + [str(root / name)], root)
        FROZEN.write_text(json.dumps(frozen, indent=0) + '\n')
    print(f'froze {FROZEN}')


def verify(compiler):
    frozen = json.loads(FROZEN.read_text())
    source = program().encode()
    spec = spec_from_file_location('build_arm64', ROOT / 'scripts/build-arm64.py')
    build = module_from_spec(spec)
    spec.loader.exec_module(build)
    with tempfile.TemporaryDirectory(prefix='alchem-arm64-floats-') as d:
        root = Path(d)
        arm = root / 'alchem-compiler-arm64'
        build.build(compiler, arm)
        for name, made_by, run in (('amd64', compiler, []), ('arm64', arm, [str(TOOLS / 'qemu-aarch64-static')])):
            made = subprocess.run([str(made_by)], input=source, capture_output=True, env={'PATH': ''}, timeout=300)
            assert made.returncode == 0, (name, made.returncode, made.stderr[:300])
            (root / name).write_bytes(made.stdout)
            (root / name).chmod(0o700)
            got = ran(run + [str(root / name)], root)
            want = frozen[name]
            lines = [(i, w, g) for i, (w, g) in enumerate(zip(want[1].split('\n'), got[1].split('\n'))) if w != g]
            assert got == want, (name, got[0], want[0], lines[:5], got[2][:300])
    print(f'PASS arm64_floats: {len(frozen["arm64"][1].splitlines())} float results of {len(FORMS)} forms (fused multiply-adds, Log, Exp, Pow)'
          ' as the pinned compiler\'s ARM64 and x86-64 programs print them')


if __name__ == '__main__':
    if sys.argv[1:] == ['--freeze']:
        freeze()
    else:
        verify(Path(sys.argv[1]).resolve())
