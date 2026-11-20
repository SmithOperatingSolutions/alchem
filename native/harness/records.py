#!/usr/bin/env python3
"""Structs and sum types: declarations, literals, fields, updates, constructors,
case over variants, and both through imports."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
from native_memory import floor_arena

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_bundle',ROOT/'scripts/bundle-alchem.py')
bundler=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundler)

GEO='''defmodule Geo do
  struct Size do
    width: integer
    height: integer = 2
  end

  type Shape do
    circle(radius: integer)
    rect(width: integer, height: integer)
    empty
  end

  def area(size: Size): integer do
    size.width * size.height
  end

  def make(w: integer): Size do
    %Size{width: w}
  end

  def unit(): Shape do
    Shape.circle(1)
  end
end
'''
DECLARATIONS='''  struct Account do
    owner: string
    balance: integer = 0
    tags: list[string] = []
  end
  struct Pair do
    left: Account
    right: Account
  end
  type Shape do
    circle(radius: integer)
    rect(width: integer, height: integer)
    empty
  end
  type Tree do
    leaf
    node(left: Tree, value: integer, right: Tree)
  end
  struct Box do
    shape: Shape
    label: string = "box"
  end
  def deposit(account: Account, amount: integer): Account do
    %Account{account | balance: account.balance + amount}
  end
  def mk(name: string): Account do %Account{owner: name} end
  def area(shape: Shape): integer do
    case shape do
      Shape.circle(radius) -> 3 * radius * radius
      Shape.rect(width, height) -> width * height
      Shape.empty -> 0
    end
  end
  def sum(t: Tree): integer do
    case t do
      Tree.leaf -> 0
      Tree.node(l, v, r) -> sum(l) + v + sum(r)
    end
  end
  def grow(n: integer): Tree do
    if n == 0 do Tree.leaf else Tree.node(grow(n - 1), n, grow(n - 1)) end
  end
'''
# (main body, stdout): outcomes equal the pinned upstream `alchem run`.
CASES=[
    # Structs: literals in any order, defaults, field reads, updates, nesting.
    ('a = %Account{owner: "ada", balance: 10}\nr = deposit(a, 15)\nIO.puts(r.owner <> Integer.to_string(r.balance + a.balance))\n'
     'IO.puts(Integer.to_string(%Account{owner: "bo"}.balance + Enum.count(mk("x").tags)))\nz = %Account{balance: 3, owner: "z"}\nIO.puts(z.owner <> Integer.to_string(z.balance))\n'
     'p = %Pair{left: mk("l"), right: mk("r")}\nIO.puts(p.left.owner <> p.right.owner <> Integer.to_string(deposit(p.left, 4).balance))\n'
     'b = %Account{a | owner: "b", balance: 7}\nIO.puts(a.owner <> b.owner <> Integer.to_string(b.balance))\n'
     'e = %Account{owner: "a" <> "b", balance: 1 + 2}\nIO.puts(e.owner <> Integer.to_string(e.balance))',b'ada35\n0\nz3\nlr4\nadab7\nab3\n'),
    # Struct values in lists, options, tuples, lambdas, captures and reductions.
    ('xs = [mk("a"), mk("b")]\nIO.puts(Enum.join(Enum.map(xs, &(&1.owner)), ","))\no = some(mk("a"))\nIO.puts(case o do some(a) -> a.owner none -> "-" end)\n'
     't = {mk("t"), 1}\nIO.puts(elem(t, 0).owner)\nf = fn(a: Account): integer do a.balance + 1 end\nIO.puts(Integer.to_string(f(deposit(mk("x"), 41))))\n'
     'total = Enum.reduce([1, 2, 3], mk("acc"), fn n, a -> deposit(a, n) end)\nIO.puts(Integer.to_string(total.balance))\nq = "p" |> mk() |> deposit(5) |> deposit(6)\nIO.puts(Integer.to_string(q.balance))',
     b'a,b\na\nt\n42\n6\n11\n'),
    # Sum types: constructors, exhaustive cases, catch-alls, wildcards, recursion.
    ('IO.puts(Integer.to_string(area(Shape.rect(2, 3)) + area(Shape.empty) + area(Shape.circle(2))))\n'
     'IO.puts(Integer.to_string(sum(Tree.node(Tree.node(Tree.leaf, 1, Tree.leaf), 2, Tree.node(Tree.leaf, 3, Tree.leaf)))))\n'
     'x = case Shape.circle(5) do\n  Shape.circle(r) -> r\n  _ -> 0\nend\ny = case Shape.empty do\n  Shape.circle(r) -> r\n  other -> area(other) + 9\nend\n'
     'v = case Shape.rect(1, 2) do\n  Shape.rect(_, h) -> h\n  _ -> 0\nend\nIO.puts(Integer.to_string(x + y + v))\n'
     'IO.puts(case Shape.circle(1) do\n  Shape.circle(r) -> "c"\n  Shape.rect(w, h) -> "r"\n  Shape.empty -> "e"\nend)\nIO.puts(Integer.to_string(sum(grow(10))))',b'18\n6\n16\nc\n2036\n'),
    # Arms with statements, cases in lambdas and in cases, sum values in structs, lists and options.
    ('x = case Shape.rect(1, 2) do\n  Shape.rect(w, h) ->\n    IO.puts("rect")\n    d = w + h\n    d * 2\n  Shape.circle(r) -> r\n  Shape.empty -> 0\nend\nIO.puts(Integer.to_string(x))\n'
     'IO.puts(Enum.join(Enum.map([Shape.empty, Shape.circle(2)], fn s -> case s do\n  Shape.circle(r) -> Integer.to_string(r)\n  _ -> "-"\nend end), ","))\n'
     'n = case Shape.rect(1, 2) do\n  Shape.rect(w, h) -> case Tree.leaf do\n    Tree.leaf -> w + h + 10\n    Tree.node(a, b, c) -> b\n  end\n  _ -> 0\nend\nIO.puts(Integer.to_string(n))\n'
     'b = %Box{shape: Shape.rect(4, 5)}\nIO.puts(b.label <> Integer.to_string(area(b.shape)))\nIO.puts(Integer.to_string(Enum.sum(Enum.map([Shape.circle(1), Shape.empty, Shape.rect(1, 2)], &area/1))))\n'
     'o = some(Shape.circle(4))\nIO.puts(Integer.to_string(case o do some(s) -> area(s) none -> 0 end))\nk = %Box{shape: Shape.empty, label: "L"}\n'
     'IO.puts(case k.shape do\n  Shape.empty -> k.label\n  _ -> "?"\nend)',b'rect\n6\n-,2\n13\nbox20\n5\n48\nL\n'),
    # Types of an imported module are Module.Name; the same names coexist.
    ('s = %Geo.Size{width: 3}\nt: Geo.Size = Geo.make(5)\nIO.puts(Integer.to_string(Geo.area(s) + t.width + Geo.make(3).height))\nu = Geo.unit()\ng: Geo.Shape = Geo.Shape.rect(2, 5)\n'
     'x = case g do\n  Geo.Shape.rect(w, h) -> w * h\n  _ -> 0\nend\ny = case u do\n  Geo.Shape.circle(r) -> r\n  _ -> 0\nend\nIO.puts(Integer.to_string(x + y + area(Shape.circle(1))))',b'13\n14\n'),
]
# Rejected natively and by the pinned compiler.
REJECTIONS=[
    ('a = %Account{balance: 3}','missing field'),('a = %Account{}','missing field in an empty literal'),('a = %Account{owner: "a", nope: 1}','unknown field'),
    ('a = %Account{owner: "a", owner: "b"}','duplicate field'),('a = %Account{owner: 1}','field of the wrong type'),('a = mk("a")\nIO.puts(a.nope)','read of an unknown field'),
    ('a = mk("a")\nb = %Account{a | nope: 1}','update of an unknown field'),('p = %Pair{left: mk("l"), right: mk("r")}\nb = %Account{p | owner: "b"}','update from another struct'),
    ('s = %Size{width: 3}','imported struct without its module'),('a: Pair = mk("a")','one struct where another is expected'),('a = %Nope{x: 1}','undeclared struct'),
    ('x = Geo.Size.width','field of a type name'),('x = case Shape.empty do\n  Shape.circle(r) -> r\n  Shape.empty -> 0\nend','case that is not exhaustive'),
    ('x = case Shape.empty do\n  Shape.circle(r) -> r\n  Shape.circle(q) -> q\n  Shape.rect(w, h) -> w\n  Shape.empty -> 0\nend','variant matched twice'),
    ('x = case Shape.empty do\n  _ -> 1\n  Shape.empty -> 0\nend','arm after a catch-all'),('x = area(Shape.rect(2))','constructor with too few arguments'),
    ('x = area(Shape.circle("a"))','constructor argument of the wrong type'),('x = area(Shape.square(1))','unknown variant'),
    ('x = case Shape.empty do\n  Shape.circle(a, b) -> a\n  _ -> 0\nend','pattern with too many names'),('s: Shape = Tree.leaf','one sum type where another is expected'),
    ('t = Shape.circle','variant with fields used bare'),('x = case Tree.leaf do\n  Shape.empty -> 1\n  _ -> 0\nend','pattern of another sum type'),
    ('x = case Shape.empty do\n  Shape.circle(r) -> r\n  _ -> "s"\nend','arms of different types'),('x = case Geo.unit() do\n  Shape.circle(r) -> r\n  _ -> 0\nend','local pattern for an imported type'),
    ('s = Geo.Shape','type name as a value'),('s = Geo.Nope.rect(1, 2)','variant of an undeclared imported type'),('x = area(Geo.unit())','imported sum type where the local one is expected'),
]
# Invalid declarations.
INVALID=[
    'defmodule M do struct Account do owner: string end struct Account do owner: string end def main() do System.halt(1) end end',
    'defmodule M do struct Account do owner: string end type Account do one end def main() do System.halt(1) end end',
    'defmodule M do struct account do owner: string end def main() do System.halt(1) end end',
    'defmodule M do struct Account do owner: string def main() do System.halt(1) end end',
    'defmodule M do struct Account do owner: Nope end def main() do x = %Account{owner: 1}\nSystem.halt(1) end end',
    'defmodule M do struct Account do balance: integer = "zero" end def main() do x = %Account{}\nSystem.halt(1) end end',
    'defmodule M do def f(a: Nope): integer do 1 end def main() do System.halt(1) end end',
    'defmodule M do type Shape do circle(radius: integer) Rect end def main() do x = Shape.circle(1)\nSystem.halt(1) end end',
    'defmodule M do type Shape do circle(radius) empty end def main() do x = Shape.empty\nSystem.halt(1) end end',
]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-records-') as d:
        root=Path(d);(root/'geo.alc').write_text(GEO)
        def compiled(body):
            (root/'app.alc').write_text('defmodule App do\n  import "geo.alc"\n'+DECLARATIONS+'  def main() do\n'+body+'\n  System.halt(0)\n  end\nend\n')
            return subprocess.run([str(compiler)],input=bundler.bundle(root/'app.alc'),capture_output=True,env={'PATH':''},timeout=120)
        for body,stdout in CASES:
            result=compiled(body)
            assert (result.returncode,result.stderr)==(0,b''),(body[:100],result.returncode,result.stderr)
            assert compiled(body).stdout==result.stdout,'record determinism'
            out=root/'out';out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(0,stdout,b''),(body[:100],run)
        # Values come from the arena: a tree of 2^17 nodes exhausts it at its 4 MiB floor
        # (floor_arena) and fits the 16 GiB an unlimited run reserves.
        result=compiled('IO.puts(Integer.to_string(sum(grow(17))))')
        out=root/'out';out.write_bytes(result.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(out))
        assert (result.returncode,run.returncode,run.stdout)==(0,71,b''),('tree arena',result.returncode,run.returncode)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stderr)==(0,b'') and run.stdout.strip().isdigit(),('tree past 4 MiB',run.returncode,run.stdout[:80])
        for body,label in REJECTIONS:
            result=compiled(body)
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
        for source in INVALID:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source[:90],result.returncode)
    print(f'PASS records: {len(CASES)} programs with structs and sum types, local and imported, arena exhaustion, {len(REJECTIONS)} rejections, {len(INVALID)} invalid declarations')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
