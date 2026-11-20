#!/usr/bin/env python3
"""Functions wider than the former fixed layouts: more than six parameters
and arguments, tuples of more than six elements, more than sixteen live
bindings. Each program's output is the pinned compiler's."""
from pathlib import Path
import subprocess
import sys
import tempfile

P=lambda n:', '.join(f'p{i}: integer' for i in range(n))
A=lambda n:', '.join(str(i+1) for i in range(n))
# (declarations, main body, standard output)
CASES=[
    (f'  def f({P(7)}): integer do p0 + p6 * 10 end\n  def g({P(30)}): integer do p0 + p29 + p15 end\n'
     f'  def r({P(12)}): integer do if p0 == 0 do p11 + p6 else r(p0 - 1, {", ".join(f"p{i}" for i in range(1,11))}, p11 + 1) end end\n',
     f'    IO.puts(Integer.to_string(f({A(7)})) <> " " <> Integer.to_string(g({A(30)})) <> " " <> Integer.to_string(r(5, {A(11)})))',b'71 47 22\n'),
    ('  def g(a: string, b: integer, c: list[integer], d: option[string], e: boolean, f: tuple[integer, string], h: string, i: integer): string do\n    case d do\n'
     '      some(s) -> a <> s <> h <> Integer.to_string(b + i + Enum.sum(c) + elem(f, 0))\n      none -> "n"\n    end\n  end\n'
     '  def pick(p: a, q: b, r: c, s: d, t: e, u: f, v: a): boolean do p == v end\n',
     '    IO.puts(g("a", 1, [2, 3], some("d"), true, {4, "t"}, "h", 5))\n    IO.puts("x" |> g(1, [2], none, false, {1, "t"}, "h", 2))\n'
     '    IO.puts("#{pick(1, "a", true, [1], some(2), {1, 2}, 1)}#{pick([1], "a", true, [1], some(2), {1, 2}, [2])}")',b'adh15\nn\ntruefalse\n'),
    ('  def ap(f: fn[integer, integer, integer, integer, integer, integer, integer, integer]): integer do f(1, 2, 3, 4, 5, 6, 7) end\n'
     '  def s7(a: integer, b: integer, c: integer, d: integer, e: integer, f: integer, g: integer): integer do a + g end\n'
     '  def mk(): fn[integer, integer, integer, integer, integer, integer, integer, integer] do fn a, b, c, d, e, f, g -> a + g end end\n',
     '    IO.puts(Integer.to_string(ap(&s7/7) + ap(fn a, b, c, d, e, f, g -> g * 2 end) + mk()(1, 2, 3, 4, 5, 6, 7)))\n    k = 100\n'
     '    f = fn(a: integer, b: integer, c: integer, d: integer, e: integer, g: integer, h: integer, i: integer, j: integer): integer do a + j + k end\n'
     '    IO.puts(Integer.to_string(f(1, 2, 3, 4, 5, 6, 7, 8, 9)))\n    IO.puts(Integer.to_string(Enum.reduce([1, 2], 0, fn v, acc -> acc + f(v, 2, 3, 4, 5, 6, 7, 8, v) end)))',b'30\n110\n206\n'),
    ('  def t(): tuple[integer, string, integer, integer, integer, integer, integer, string, integer] do {1, "b", 3, 4, 5, 6, 7, "h", 9} end\n'
     '  struct R do\n'+''.join(f'    f{i}: integer\n' for i in range(10))+'  end\n  type V do\n    big(a: integer, b: integer, c: integer, d: integer, e: integer, f: integer, g: integer, h: integer)\n    none_here\n  end\n',
     '    x = t()\n    {a, b, _, _, _, _, g, h, i} = x\n    IO.puts(b <> h <> Integer.to_string(a + g + i + elem(x, 8)))\n    IO.puts("#{x == t()}#{x == {1, "b", 3, 4, 5, 6, 7, "h", 0}}")\n'
     '    case x do\n      {1, _, _, _, _, _, _, "h", n} -> IO.puts(Integer.to_string(n))\n      _ -> IO.puts("no")\n    end\n'
     '    r = %R{'+', '.join(f'f{i}: {i}' for i in range(10))+'}\n    v = V.big(1, 2, 3, 4, 5, 6, 7, 8)\n    case v do\n      V.big(a2, _, _, _, _, _, _, h2) -> IO.puts(Integer.to_string(a2 + h2 + r.f9))\n      V.none_here -> IO.puts("n")\n    end',
     b'bh26\ntruefalse\n9\n18\n'),
    ('  def run(f: fn[integer, integer]): integer do f(1) end\n  def g(n: integer): integer do\n'+'\n'.join(f'    a{i} = n + {i}' for i in range(30))+'\n    if n == 0 do a29 else g(n - 1) + a17 end\n  end\n'
     '  def h(o: option[integer]): integer do\n'+'\n'.join(f'    b{i} = {i}' for i in range(20))+'\n    case o do\n      some(x) ->\n        {p, q} = {x, b19}\n        [first | rest] = [p + q, 1]\n        first + b0\n      none -> b5\n    end\n  end\n',
     '\n'.join(f'    v{i} = "{i}"' for i in range(200))+'\n    k = 5\n    IO.puts(v0 <> v199 <> Integer.to_string(run(fn x -> x + k + String.length(v150) end)))\n    IO.puts(Integer.to_string(g(5000) + h(some(3)) + h(none)))',
     b'01999\n12587556\n'),
]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-wide-') as d:
        root=Path(d)
        for declarations,body,stdout in CASES:
            result=subprocess.run([str(compiler)],input=('defmodule M do\n'+declarations+'  def main() do\n'+body+'\n  end\nend\n').encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(body[:100],result.returncode,result.stderr)
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(0,stdout,b''),(body[:100],run)
        many='defmodule M do\n  def main() do\n'+'\n'.join(f'    v{i} = {i}' for i in range(251))+'\n    IO.puts(Integer.to_string(v0))\n  end\nend\n'
        result=subprocess.run([str(compiler)],input=many.encode(),capture_output=True,env={'PATH':''},timeout=120)
        assert (result.returncode,result.stderr)==(0,b''),('251 live bindings',result.returncode)
        out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(0,b'0\n',b''),('251 live bindings',run)
    print(f'PASS wide: {len(CASES)} programs with 7 to 30 parameters, lambdas and function values of 7 to 9, tuples of 9, 200 live bindings, and 251 (once refused)')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
