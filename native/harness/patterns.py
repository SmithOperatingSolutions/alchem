#!/usr/bin/env python3
"""Patterns: case over any type with nested patterns, literals, pins and guards;
pattern bindings; pattern parameters; exhaustiveness and unreachable arms."""
from pathlib import Path
import subprocess
import sys
import tempfile

DECLARATIONS=('struct Account do owner: string\n balance: integer = 0\n end '
              'type Shape do circle(radius: integer)\n rect(width: integer, height: integer)\n empty\n end '
              'def mk(name: string): Account do %Account{owner: name} end '
              'def owner_of(%Account{owner: name}: Account): string do name end def first({a, b}: tuple[integer, string]): integer do a end '
              'def both({a, b}: tuple[integer, integer], scale: integer, {h, {i, _}}: tuple[integer, tuple[integer, string]]): integer do (a + b) * scale + h + i end '
              'def pick(o: option[integer]): integer do\n some(x) = o\n x\n end '
              'def total(l: list[integer]): integer do case l do\n [a, b, c] -> a + b + c\n [a, b | rest] -> a * b + Enum.sum(rest)\n [a] -> a\n [] -> 0\n end end '
              'def size(n: integer): string do case n do\n k when k > 10 -> "big"\n k when k > 3 -> "mid"\n _ -> "small"\n end end ')
# (main body, stdout, stderr, status): outcomes equal the pinned upstream `alchem run`
# (whose pattern failure adds a line naming the source location).
CASES=[
    # Structs, tuples, booleans, integers and strings, with literals and names.
    ('a = case mk("a") do\n  %Account{owner: "a", balance: b} -> b + 1\n  %Account{owner: o} -> byte_size(o)\nend\nz = case mk("zzz") do\n  %Account{owner: "a", balance: b} -> b + 1\n  %Account{owner: o} -> byte_size(o)\nend\n'
     'IO.puts(Integer.to_string(a * 10 + z))\nIO.puts(case {3, "x"} do\n  {1, t} -> t\n  {n, "x"} -> Integer.to_string(n)\n  _ -> "other"\nend)\n'
     'IO.puts(Integer.to_string(case {true, 1} do\n  {true, n} -> n\n  {false, n} -> n + 1\nend))\nIO.puts(case 1 > 0 do\n  true -> "t"\n  false -> "f"\nend)\n'
     'IO.puts(case 3 do\n  1 -> "one"\n  3 -> "three"\n  n -> Integer.to_string(n)\nend)\nIO.puts(Integer.to_string(case "b" do\n  "a" -> 1\n  "b" -> 2\n  _ -> 0\nend))\n'
     'IO.puts(case 0 - 5 do\n  -5 -> "m"\n  _ -> "o"\nend)\nIO.puts(Integer.to_string(case mk("z") do\n  %Account{balance: 0} -> 1\n  _ -> 2\nend))',
     b'13\n3\n1\nt\nthree\n2\nm\n1\n',b'',0),
    # Pins, guards, nested constructors, lists with heads and tails.
    ('expected = 3\nIO.puts(case {3, "x"} do\n  {^expected, text} -> text\n  _ -> "other"\nend)\nIO.puts(size(50) <> size(5) <> size(1))\n'
     'IO.puts(Integer.to_string(case {4, "s"} do\n  {n, s} when n - 1 > 2 and s == "s" -> n - 1\n  {n, _} -> 0 - n\nend))\n'
     'IO.puts(Integer.to_string(case some(Shape.rect(2, 3)) do\n  some(Shape.rect(w, h)) -> w * h\n  some(Shape.circle(r)) -> r\n  some(Shape.empty) -> 0\n  none -> 1\nend))\n'
     'IO.puts(Integer.to_string(total([1, 2, 3]) + total([4, 5, 6, 7]) * 100 + total([9]) * 10000 + total([]) + total([2, 3]) * 1000000))\n'
     'IO.puts(case {some({1, "a"}), [Shape.circle(2)]} do\n  {some({1, s}), [Shape.circle(r) | _]} -> s <> Integer.to_string(r)\n  {none, _} -> "none"\n  _ -> "other"\nend)\n'
     'IO.puts(case ["a", "b", "c"] do\n  [_ | t] -> Enum.join(t, ",")\n  [] -> ""\nend)\n'
     'IO.puts(Integer.to_string(case {Shape.rect(1, 2), Shape.empty} do\n  {Shape.rect(w, _), Shape.empty} -> w\n  {Shape.circle(r), _} -> r\n  {_, Shape.circle(q)} -> q\n  {Shape.empty, _} -> 0\n  {Shape.rect(_, h), Shape.rect(_, k)} -> h + k\nend))',
     b'x\nbigmidsmall\n3\n6\n6093306\na2\nb,c\n1\n',b'',0),
    # Results, options with literals, wildcards in any place, maps.
    ('r: result[tuple[integer, string], string] = ok({1, "a"})\nIO.puts(case r do\n  ok({1, s}) -> s\n  ok({_, s}) -> s <> "!"\n  error(e) -> e\nend)\n'
     'IO.puts(case some(3) do\n  some(3) -> "three"\n  some(n) -> Integer.to_string(n)\n  none -> "none"\nend)\n'
     'IO.puts(Integer.to_string(case {1, 2} do\n  {_, 2} -> 1\n  {1, _} -> 2\n  {_, _} -> 3\nend))\nm = %{"a" => 1, "b" => 2}\n'
     'x = case m do\n  %{"a" => 1, "b" => b} -> b\n  %{"a" => a} -> a\n  _ -> 0\nend\n%{"b" => y} = m\nIO.puts(Integer.to_string(x + y))\n'
     'IO.puts(Integer.to_string(case %{"count" => 4} do\n  %{"count" => n} when n > 0 -> n\n  _ -> 0\nend))\nIO.puts(Integer.to_string(case %{"a" => 1} do\n  %{} -> 1\nend))\n'
     'IO.puts(case %{1 => "a"} do\n  %{2 => s} -> s\n  %{1 => "b"} -> "b"\n  %{1 => s} -> s <> "!"\n  _ -> "none"\nend)\n'
     'IO.puts(Integer.to_string(case {%{"k" => [1, 2]}, 3} do\n  {%{"z" => _}, n} -> n\n  {%{"k" => [a | _]}, n} -> a + n\n  _ -> 0\nend))',
     b'a\nthree\n1\n4\n4\n1\na!\n4\n',b'',0),
    # Pattern bindings and pattern parameters of named functions and lambdas.
    ('{count, label} = {3, "ok"}\nIO.puts(label <> Integer.to_string(count))\n%Account{owner: o, balance: b} = mk("q")\nIO.puts(o <> Integer.to_string(b))\n'
     '[head | rest] = [1, 2, 3]\n[p, q] = [7, 8]\nIO.puts(Integer.to_string(head + Enum.count(rest) + p + q))\nShape.rect(w, h) = Shape.rect(3, 4)\n'
     '{%Account{owner: n}, [x, y]} = {mk("n"), [1, 2]}\nIO.puts(n <> Integer.to_string(w * h + x + y))',b'ok3\nq0\n18\nn15\n',b'',0),
    ('IO.puts(Integer.to_string(if true do\n  {c, d} = {1, 2}\n  c + d\nelse 0 end))\n'
     'IO.puts(owner_of(mk("z")) <> Integer.to_string(first({4, "s"})) <> Integer.to_string(both({1, 2}, 10, {5, {6, "x"}})))\nk = 10\n'
     'IO.puts(Integer.to_string(Enum.sum(Enum.map([{1, 2}, {3, 4}], fn {e, f} -> e * f end)) + Enum.reduce([{1, "a"}, {2, "bb"}], 0, fn {i, s}, acc -> acc + i * k + byte_size(s) end)))\n'
     'IO.puts(Integer.to_string(Enum.sum(Enum.map([some(1)], fn some(v) -> v end)) + pick(some(4))))\n'
     't: fn [integer, integer] = fn u -> u + 2 end\nIO.puts(Integer.to_string(Enum.sum(Enum.map([[1, 2], [5]], fn [g | r] -> g + Enum.count(r) end)) + t(1)))',
     b'3\nz441\n47\n5\n10\n',b'',0),
    # A value that does not match stops the program with status 2.
    ('IO.puts("before")\nIO.puts(Integer.to_string(pick(none)))',b'before\n',b'<stdin>:7:2: pattern match failed\n  at M.pick (<stdin>:7)\n  at M.main (<stdin>:19)\n',2),
    ('{1, y} = {2, 5}\nIO.puts(Integer.to_string(y))',b'',b'<stdin>:18:24: pattern match failed\n  at M.main (<stdin>:18)\n',2),
    ('IO.puts(Integer.to_string(Enum.sum(Enum.map([some(1), none], fn some(v) -> v end))))',b'',b'<stdin>:18:88: pattern match failed\n  at M.main <closure> (<stdin>:18)\n  at M.main (<stdin>:18)\n',2),
]
# Rejected natively and by the pinned compiler.
REJECTIONS=[
    ('x = case mk("a") do\n  %Account{owner: "a", balance: b} -> b + 1\nend','struct case that is not exhaustive'),
    ('x = case 3 do\n  1 -> "one"\n  3 -> "three"\nend','integers without a catch-all'),('x = case 5 do\n  n when n > 10 -> "big"\nend','only guarded arms'),
    ('x = case [1, 2, 3] do\n  [a] -> a\n  [h | t] -> h\nend','lists without the empty list'),('x = case true do\n  true -> 1\nend','booleans without false'),
    ('x = case %{"a" => 1} do\n  %{"a" => a} -> a\nend','maps without a catch-all'),
    ('x = case {Shape.rect(1, 2), Shape.empty} do\n  {Shape.rect(w, _), Shape.empty} -> w\n  {Shape.circle(r), _} -> r\n  {_, Shape.circle(q)} -> q\n  {Shape.empty, _} -> 0\nend','pairs of variants with one pair missing'),
    ('x = case 3 do\n  n -> 1\n  3 -> 2\nend','arm after a name'),('x = case 3 do\n  3 -> 1\n  3 -> 2\n  _ -> 0\nend','the same integer twice'),
    ('x = case "a" do\n  "a" -> 1\n  "a" -> 2\n  _ -> 0\nend','the same string twice'),('x = case {true, 1} do\n  {true, n} -> n\n  {false, n} -> n\n  {_, 0} -> 0\nend','arm after an exhaustive set'),
    ('x = case {1, 2} do\n  {a, a} -> a\nend','one name bound twice'),('x = case 3 do\n  "a" -> 1\n  _ -> 2\nend','literal of another type'),
    ('{a, a} = {1, 2}','one name bound twice in a binding'),('{a, b} = 5','tuple pattern for an integer'),('x = case {1, 2} do\n  {a, b, c} -> a\nend','tuple pattern of the wrong size'),
    ('x = case mk("a") do\n  %Account{nope: n} -> 1\nend','unknown field in a pattern'),('x = case mk("a") do\n  %Account{owner: o, owner: p} -> 1\nend','field listed twice'),
    ('x = case some(1) do\n  some(a) -> a\n  none -> "s"\nend','arms of different types'),('y = 1\nx = case 2 do\n  ^z -> 1\n  _ -> 0\nend','pin of an unknown name'),
    ('x = case 2 do\n  n when n -> 1\n  _ -> 0\nend','guard that is not a boolean'),
]
# Parameters of named functions must match every value.
INVALID=[
    'defmodule M do type Shape do circle(radius: integer)\n empty\n end def radius(Shape.circle(r): Shape): integer do r end def main() do System.halt(1) end end',
    'defmodule M do def f({1, b}: tuple[integer, integer]): integer do b end def main() do System.halt(1) end end',
    'defmodule M do def f({a, b}: integer): integer do a end def main() do System.halt(1) end end',
    'defmodule M do def f({a, a}: tuple[integer, integer]): integer do a end def main() do System.halt(1) end end',
]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-patterns-') as d:
        root=Path(d)
        def compiled(body):
            return subprocess.run([str(compiler)],input=('defmodule M do '+DECLARATIONS+'def main() do '+body+'\nSystem.halt(0) end end').encode(),capture_output=True,env={'PATH':''},timeout=120)
        for body,stdout,stderr,status in CASES:
            result=compiled(body)
            assert (result.returncode,result.stderr)==(0,b''),(body[:100],result.returncode,result.stderr)
            assert compiled(body).stdout==result.stdout,'pattern determinism'
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(body[:100],run)
        for body,label in REJECTIONS:
            result=compiled(body)
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
        for source in INVALID:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source[:90],result.returncode)
    print(f'PASS patterns: {len(CASES)} programs with case over every type, nested patterns, literals, pins, guards, maps, bindings and parameters, {len(REJECTIONS)} rejections, {len(INVALID)} invalid parameters')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
