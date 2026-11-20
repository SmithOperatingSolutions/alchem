#!/usr/bin/env python3
"""Where a value takes its type from its context, as the pinned compiler types
programs: values of open type, lambdas in generic calls, argument order."""
from pathlib import Path
import subprocess
import sys
import tempfile

DECLARATIONS='''  type Tree[t] do
    leaf
    node(left: Tree[t], value: t, right: Tree[t])
  end
  struct Box[t] do
    item: t
    tag: string = "b"
  end
  struct Unit[t] do
    tag: string = "u"
  end
  struct Account do
    owner: string
  end
  type Shape do
    circle(radius: integer)
    empty
  end
  def insert(t: Tree[integer], v: integer): Tree[integer] do Tree.node(t, v, Tree.leaf) end
  def size(t: Tree[x]): integer do
    case t do
      Tree.leaf -> 0
      Tree.node(l, _, r) -> size(l) + 1 + size(r)
    end
  end
  def id(x: t): t do x end
  def twice(f: fn[t, t], x: t): t do f(f(x)) end
  def apply(f: fn[a, b], x: a): b do f(x) end
  def apply2(x: a, f: fn[a, b]): b do f(x) end
  def make(f: fn[t, t]): fn[t, t] do f end
  def both(a: Tree[x], b: Tree[x]): integer do 1 end
  def keep(a: Tree[x], b: Tree[x]): Tree[x] do b end
  def inc(n: integer): integer do n + 1 end
  def add(v: integer, acc: integer): integer do v + acc end
  def pos(v: integer): boolean do v > 0 end
  def mk(name: string): Account do %Account{owner: name} end
  def opt(o: option[integer]): integer do case o do some(n) -> n none -> 0 end end
  def yes(b: boolean): string do if b do "y" else "n" end end
'''
# Main bodies the pinned compiler accepts, with their output.
ACCEPTED=[
    ('x = [some(1), none]\ny = [insert(Tree.leaf, 4), Tree.leaf]\nz = [[1], []]\nw = Enum.concat([1], [])\nIO.puts(Integer.to_string(Enum.count(x) + Enum.count(y) + Enum.count(z) + Enum.count(w)))',b'7\n'),
    ('IO.puts(yes(some(1) == none) <> yes(insert(Tree.leaf, 1) == Tree.leaf))\ne: list[integer] = []\nIO.puts(if [] == e do "y" else "n" end)',b'nn\ny\n'),
    ('a = if true do none else some(1) end\nb = if true do some(1) else none end\nc = if true do insert(Tree.leaf, 1) else Tree.leaf end\nd = if true do [] else [1] end\n'
     'e = case 1 do\n  1 -> none\n  _ -> some(2)\nend\nf = case some([1]) do some(l) -> l none -> [] end\nIO.puts(Integer.to_string(opt(a) + opt(b) + size(c) + Enum.count(d) + opt(e) + Enum.count(f)))',b'3\n'),
    ('IO.puts(Integer.to_string(opt(none) + opt(if true do none else some(1) end)))\nIO.puts(Integer.to_string(Tree.leaf |> insert(3) |> size()))',b'0\n1\n'),
    ('y: integer = twice(fn x -> x * 3 end, 2)\nIO.puts(Integer.to_string(y))\nIO.puts(Integer.to_string(twice(fn x -> x * 3 end, 2)))\nIO.puts(apply2(4, fn n -> Integer.to_string(n + 1) end))\n'
     'f: fn[integer, integer] = make(fn x -> x + 1 end)\nIO.puts(Integer.to_string(f(1)))\nn: integer = id(1) + twice(fn x -> x * 3 end, 2)\nIO.puts(Integer.to_string(n))\n'
     'IO.puts(Integer.to_string(1 + twice(fn x -> x * 3 end, 2)) <> Integer.to_string(2 * twice(fn x -> x * 3 end, 2)))\nIO.puts("a" <> twice(fn x -> x <> "!" end, "b"))\nb: boolean = id(1) == 1\nIO.puts(yes(b))',
     b'18\n18\n5\n2\n19\n1936\nab!!\ny\n'),
    ('IO.puts(Integer.to_string(Enum.sum(Enum.map([{1, 2}], fn {a, b} -> a + b end))))\nIO.puts(Integer.to_string(Enum.sum(Enum.map([1], &inc/1)) + apply(&inc/1, 4)))',b'3\n7\n'),
    ('a: Tree[integer] = keep(Tree.leaf, Tree.leaf)\nb: Tree[integer] = Tree.node(Tree.leaf, 1, Tree.leaf)\nc: list[option[integer]] = [none, some(1)]\nd: option[option[integer]] = some(none)\n'
     'e: result[integer, string] = ok(1)\nf: list[integer] = Enum.take([], 2)\ng: list[integer] = Enum.reverse([])\nh: list[integer] = Enum.concat([], [1])\ni: option[integer] = List.first([])\n'
     'j: option[list[integer]] = some([])\nk: map[integer, integer] = Map.put(%{}, 1, 2)\nIO.puts(Integer.to_string(size(a) + size(b) + Enum.count(c) + Enum.count(f) + Enum.count(g) + Enum.count(h) + Map.get(k, 1, 0)))',b'6\n'),
    ('IO.puts(Integer.to_string(Integer.undigits([]) + Enum.sum([]) + Enum.at([], 0, 9)))\nm = %{"a" => [1]}\nIO.puts(Integer.to_string(Enum.count(Map.get(m, "b", [])) + Enum.count(Enum.at([[1]], 5, []))))',b'9\n0\n'),
]
# Main bodies the pinned compiler rejects: (body, what it could not type).
REJECTED=[
    ('x = none','none bound without a type'),('x = []','an empty list bound without a type'),('x = %{}','an empty map bound without a type'),('x = ok(1)','ok bound without an error type'),
    ('x = Tree.leaf','a variant of a generic type bound without a type'),('x = %Unit{}','a generic struct with an unsettled parameter'),('x = some(none)','none inside some'),
    ('x = [none, some(1)]','a first list element of open type'),('x = {none, 1}','none inside a tuple'),('x = [[], [1]]','an empty list as first element'),
    ('IO.puts(yes(none == some(1)))','none as a left operand'),('IO.puts(yes(Tree.leaf == insert(Tree.leaf, 1)))','a variant as a left operand'),
    ('IO.puts(Integer.to_string(size(Tree.leaf)))','a variant for a parameter with an unsettled variable'),('x = id(Tree.leaf)','an open value through a generic function'),
    ('y = twice(fn x -> x * 3 end, 2)','a lambda before the argument that settles it, without a type'),('IO.puts(Integer.to_string(twice(fn x -> x * 3 end, 2) + 1))','such a call as a left operand'),
    ('IO.puts(twice(fn x -> x <> "!" end, "b") <> "a")','such a call as a left operand of <>'),('IO.puts(apply(fn n -> Integer.to_string(n + 1) end, 4))','a lambda whose parameter only a later argument settles'),
    ('f = make(fn x -> x + 1 end)','a lambda only the result type settles, without one'),('x = if true do [] else [] end','branches that are both open'),
    ('IO.puts(Enum.join(Enum.map([mk("a")], fn %Account{owner: o} -> o end), ","))','a struct pattern as a lambda parameter'),
    ('IO.puts(Enum.join(Enum.map([{mk("a"), 1}], fn {%Account{owner: o}, n} -> o end), ","))','a struct pattern inside a lambda parameter'),
    ('IO.puts(Integer.to_string(Enum.sum(Enum.map([Shape.circle(2)], fn Shape.circle(r) -> r end))))','a variant pattern as a lambda parameter'),
    ('IO.puts(Enum.join(Enum.map(["a"], &id/1), ","))','a generic function reference as a callback'),('IO.puts(Integer.to_string(apply(&id/1, 4)))','a generic function reference for a generic parameter'),
    ('IO.puts(Integer.to_string(both(Tree.leaf, Tree.node(Tree.leaf, 1, Tree.leaf))))','an open first argument'),('IO.puts(Integer.to_string(both(Tree.node(Tree.leaf, 1, Tree.leaf), Tree.leaf)))','an open argument of a constructor'),
    ('x = Tree.node(Tree.leaf, 1, Tree.leaf)','a constructor whose first argument is open, without a type'),('x = Enum.concat([], [1])','an empty first argument of concat, without a type'),
    ('x = Map.put(%{}, "a", 1)','an empty map as first argument, without a type'),('IO.puts(Integer.to_string(Enum.count([])))','count of an empty list'),('IO.puts(Enum.join([], ","))','join of an empty list'),
    ('IO.puts(Integer.to_string(Enum.reduce([], 42, &add/2)))','reduce over an empty list'),('IO.puts(Integer.to_string(Enum.count(Enum.map([], &inc/1))))','map over an empty list'),
    ('IO.puts(Integer.to_string(Enum.count(Enum.filter([], &pos/1))))','filter of an empty list'),('IO.puts(if Enum.empty?([]) do "y" else "n" end)','empty? of an empty list'),
    ('IO.puts(Integer.to_string(Map.get(%{}, 1, 5)))','get from an empty map'),('IO.puts(Integer.to_string(Enum.count(Map.keys(%{}))))','keys of an empty map'),
]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-inference-') as d:
        root=Path(d)
        def compiled(body):
            return subprocess.run([str(compiler)],input=('defmodule M do\n'+DECLARATIONS+'  def main() do\n'+body+'\nSystem.halt(0) end end').encode(),capture_output=True,env={'PATH':''},timeout=120)
        for body,stdout in ACCEPTED:
            result=compiled(body)
            assert (result.returncode,result.stderr)==(0,b''),(body[:100],result.returncode,result.stderr)
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(0,stdout,b''),(body[:100],run)
        for body,label in REJECTED:
            result=compiled(body+'\nIO.puts("x")')
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
    print(f'PASS inference: {len(ACCEPTED)} programs whose values take their types from context, {len(REJECTED)} the pinned compiler cannot type and rejects')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
