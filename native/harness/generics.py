#!/usr/bin/env python3
"""Type variables: generic functions, structs and sum types with parameters,
and equality of values whose type is a variable."""
from pathlib import Path
import subprocess
import sys
import tempfile

DECLARATIONS='''  struct Pair[a, b] do
    left: a
    right: b
  end
  type Tree[t] do
    leaf
    node(left: Tree[t], value: t, right: Tree[t])
  end
  struct Box[t] do
    item: t
    count: integer = 1
  end
  def swap(pair: Pair[a, b]): Pair[b, a] do
    %Pair{left: pair.right, right: pair.left}
  end
  def size(t: Tree[x]): integer do
    case t do
      Tree.leaf -> 0
      Tree.node(l, _, r) -> size(l) + 1 + size(r)
    end
  end
  def insert(t: Tree[integer], v: integer): Tree[integer] do
    case t do
      Tree.leaf -> Tree.node(Tree.leaf, v, Tree.leaf)
      Tree.node(l, x, r) -> if v < x do Tree.node(insert(l, v), x, r) else Tree.node(l, x, insert(r, v)) end
    end
  end
  def total(t: Tree[integer]): integer do
    case t do
      Tree.leaf -> 0
      Tree.node(l, v, r) -> total(l) + v + total(r)
    end
  end
  def pairs(xs: list[a], y: b): list[Pair[a, b]] do Enum.map(xs, fn x -> %Pair{left: x, right: y} end) end
  def unbox(b: Box[t]): t do b.item end
  def first_or(items: list[t], fallback: t): t do
    case items do
      [] -> fallback
      [head | _] -> head
    end
  end
  def id(x: t): t do x end
  def twice(f: fn[t, t], x: t): t do f(f(x)) end
  def pick(c: boolean, a: t, b: t): t do if c do a else b end end
  def wrap(x: t): list[t] do [x] end
  def flip(a: x, b: y): tuple[y, x] do {b, a} end
  def count(items: list[t]): integer do
    case items do
      [] -> 0
      [_ | rest] -> 1 + count(rest)
    end
  end
  def same(x: t, y: t): boolean do x == y end
  def contains(items: list[t], x: t): boolean do
    case items do
      [] -> false
      [h | rest] -> h == x or contains(rest, x)
    end
  end
  def yes(b: boolean): string do if b do "y" else "n" end end
'''
# (main body, stdout): outcomes equal the pinned upstream `alchem run`.
CASES=[
    # Generic functions: each call picks the types.
    ('IO.puts(first_or(["a"], "z") <> Integer.to_string(first_or(Enum.take([1], 0), 9)))\nIO.puts(id("s") <> Integer.to_string(id(4)) <> yes(id(true)))\n'
     'IO.puts(Integer.to_string(twice(fn x -> x * 3 end, 2)) <> twice(&String.upcase/1, "a"))\nIO.puts(pick(true, "a", "b") <> Integer.to_string(pick(false, 1, 2)))\n'
     'IO.puts(Integer.to_string(Enum.sum(wrap(5))) <> Enum.join(wrap("w"), ""))\np = flip(1, "s")\nIO.puts(elem(p, 0) <> Integer.to_string(elem(p, 1)))\n'
     'IO.puts(Integer.to_string(count([1, 2, 3]) + count(["a"])))\nIO.puts(Integer.to_string(case id(some(4)) do some(n) -> n none -> 0 end))\n'
     'IO.puts(Integer.to_string(id(id(id(7)))) <> first_or(wrap(id("q")), "z"))\nf: fn[string, string] = &id/1\nh: fn[integer, integer, boolean] = &same\n'
     'IO.puts(Enum.join(Enum.map(["a", "b"], f), ",") <> yes(h(1, 1)))',
     b'a9\ns4y\n18A\na2\n5w\ns1\n4\n4\n7q\na,by\n'),
    # Structs and sum types with parameters: literals and constructors settle them.
    ('s = swap(%Pair{left: 1, right: "one"})\nIO.puts(s.left <> Integer.to_string(s.right))\nt = insert(insert(insert(Tree.leaf, 5), 3), 8)\nIO.puts(Integer.to_string(size(t)) <> Integer.to_string(total(t)))\n'
     'u: Tree[string] = Tree.node(Tree.leaf, "a", Tree.leaf)\nIO.puts(Integer.to_string(size(u)))\nps = pairs([1, 2], "k")\n'
     'IO.puts(Integer.to_string(Enum.count(ps)) <> Enum.join(Enum.map(ps, fn p -> p.right <> Integer.to_string(p.left) end), ","))\n'
     'b = %Box{item: "x"}\nc: Box[integer] = %Box{item: 5, count: 2}\nIO.puts(b.item <> Integer.to_string(b.count + c.item + c.count) <> unbox(b) <> Integer.to_string(unbox(c)))\n'
     'q: Pair[string, integer] = swap(%Pair{left: 1, right: "a"})\nr = %Pair{q | right: 2}\nIO.puts(q.left <> r.left <> Integer.to_string(r.right))',
     b'one1\n316\n1\n2k1,k2\nx8x5\naa2\n'),
    # Patterns over generic types, and equality where a type is a variable.
    ('x = case %Pair{left: 1, right: "a"} do\n  %Pair{left: 1, right: r} -> r\n  %Pair{right: r} -> r <> "?"\nend\n%Box{item: i} = %Box{item: 7}\nIO.puts(x <> Integer.to_string(i))\n'
     'u: Tree[string] = Tree.node(Tree.leaf, "v", Tree.leaf)\nIO.puts(case u do\n  Tree.node(_, v, Tree.leaf) -> v\n  _ -> "-"\nend)\n'
     'IO.puts(yes(same(1, 1)) <> yes(same("a", "b")) <> yes(same([1, 2], [1, 2])) <> yes(same(%Pair{left: 1, right: "x"}, %Pair{left: 1, right: "x"})))\n'
     'IO.puts(yes(contains([1, 2, 3], 2)) <> yes(contains(["a"], "b")) <> yes(contains([{1, "a"}], {1, "a"})))\nt = insert(insert(insert(Tree.leaf, 5), 3), 8)\n'
     'IO.puts(yes(t == insert(insert(insert(Tree.leaf, 5), 3), 8)) <> yes(t == insert(Tree.leaf, 5)))\n'
     'IO.puts(yes(%Box{item: "x"} == %Box{item: "x"}) <> yes(%Pair{left: [1], right: some("a")} == %Pair{left: [1], right: some("b")}))\n'
     'w = insert(insert(Tree.leaf, 5), 3)\nIO.puts(yes(same(w, insert(insert(Tree.leaf, 5), 3))) <> yes(same(w, insert(Tree.leaf, 5))) <> yes(contains([w], w)))\n'
     'IO.puts(yes(%Box{item: [1, 2]} != %Box{item: [1, 3]}) <> yes(same(some(1), none)))\ng: fn[list[integer], list[integer], boolean] = &same/2\nIO.puts(yes(g([1], [1])) <> yes(g([1], [2])))',
     b'a7\nv\nynyy\nyny\nyn\nyn\nyny\nyn\nyn\n'),
]
# Rejected natively and by the pinned compiler.
REJECTIONS=[
    ('IO.puts(pick(true, "a", 2))','one variable with two types'),('IO.puts(yes(same(1, "a")))','equality of two types'),
    ('c: Box[integer] = %Box{item: "s"}','instance of another argument'),('p: Pair[integer] = %Pair{left: 1, right: "a"}','too few type arguments'),
    ('p: Pair = %Pair{left: 1, right: "a"}','generic type without arguments'),('t: Tree[string] = insert(Tree.leaf, 1)','one instance where another is expected'),
    ('x = id(1) + id("a")','result of the wrong type'),('x = count(5)','argument that is not a list'),('x = unbox(%Pair{left: 1, right: 2})','another generic type'),
    ('x = twice(fn x -> "s" end, 2)','lambda against a settled variable'),
    ('f = &id','reference to a generic function without an expected type'),
]
# Invalid generic declarations and bodies.
INVALID=[
    'defmodule M do def double(x: t): t do x + x end def main() do System.halt(1) end end',
    'defmodule M do def other(x: a, y: b): a do y end def main() do System.halt(1) end end',
    'defmodule M do def less(x: t, y: t): boolean do x < y end def main() do System.halt(1) end end',
    'defmodule M do struct Box[T] do item: integer end def main() do System.halt(1) end end',
    'defmodule M do struct Box[t do item: t end def main() do System.halt(1) end end',
    'defmodule M do struct Box[t] do item: t end def f(b: Box[integer, string]): integer do 1 end def main() do System.halt(1) end end',
]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-generics-') as d:
        root=Path(d)
        def compiled(body):
            return subprocess.run([str(compiler)],input=('defmodule M do\n'+DECLARATIONS+'  def main() do\n'+body+'\nSystem.halt(0) end end').encode(),capture_output=True,env={'PATH':''},timeout=120)
        for body,stdout in CASES:
            result=compiled(body)
            assert (result.returncode,result.stderr)==(0,b''),(body[:100],result.returncode,result.stderr)
            assert compiled(body).stdout==result.stdout,'generic determinism'
            out=root/'out';out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(0,stdout,b''),(body[:100],run)
        # Up to six type parameters compare; comparators for concrete compound types
        # are code, so a million generic calls with list arguments allocate nothing
        # (each used to take an arena record, which exhausted the 4 MiB arena).
        extra=('defmodule M do\n  struct Six[a, b, c, d, e, f] do\n one: a\n two: b\n three: c\n four: d\n five: e\n six: f\n end\n'
               '  def same(x: t, y: t): boolean do x == y end\n  def yes(b: boolean): string do if b do "y" else "n" end end\n'
               '  def grow(items: list[integer], n: integer): list[integer] do if n == 0 do items else grow(Enum.concat(items, items), n - 1) end end\n'
               '  def inner(row: list[integer], a: list[integer], b: list[integer]): integer do\n    Enum.reduce(row, 0, fn i, acc -> if same(a, b) do acc + 1 else acc end end)\n  end\n'
               '  def main() do\n    x = %Six{one: 1, two: "b", three: [3], four: some(4), five: {5, "e"}, six: true}\n    y = %Six{one: 1, two: "b", three: [3], four: some(4), five: {5, "e"}, six: true}\n'
               '    z = %Six{one: 1, two: "b", three: [3], four: some(4), five: {5, "x"}, six: true}\n    IO.puts(yes(x == y) <> yes(x == z) <> yes(same(x, y)) <> yes(same(x, z)))\n'
               '    IO.puts(yes(same([1, 2], [1, 2])) <> yes(same({1, "a"}, {1, "b"})) <> yes(same(%{"k" => [1]}, %{"k" => [1]})) <> yes(same(some([1]), none)))\n'
               '    row = grow([1], 10)\n    a = [1, 2, 3]\n    b = [1, 2, 3]\n    total = Enum.reduce(row, 0, fn i, acc -> acc + inner(row, a, b) end)\n    IO.puts(Integer.to_string(total))\n    System.halt(0)\n  end\nend\n')
        result=subprocess.run([str(compiler)],input=extra.encode(),capture_output=True,env={'PATH':''},timeout=120)
        assert (result.returncode,result.stderr)==(0,b''),('six parameters and comparators',result.returncode,result.stderr)
        out=root/'out';out.write_bytes(result.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(0,b'ynyn\nynyn\n1048576\n',b''),('six parameters and comparators',run)
        # More than six type parameters: comparators travel as an array on the
        # stack, and a generic function takes those past its sixth value there.
        nine=('defmodule M do\n  struct Nine[a, b, c, d, e, f, g, h, i] do\n one: a\n two: b\n three: list[c]\n four: d\n five: e\n six: f\n seven: g\n eight: option[list[h]]\n nine: i\n end\n'
              '  type Seven[a, b, c, d, e, f, g] do\n first(x: a, y: b, z: c)\n second(p: d, q: e, r: list[tuple[f, g]])\n third\n end\n'
              '  def same(x: t, y: t): boolean do x == y end\n  def yes(b: boolean): string do if b do "y" else "n" end end\n'
              '  def last(n: Nine[a, b, c, d, e, f, g, h, i], m: Nine[a, b, c, d, e, f, g, h, i]): i do if n == m do n.nine else m.nine end end\n'
              '  def wrap(n: Nine[a, b, c, d, e, f, g, h, i]): fn[i, boolean] do fn x -> x == n.nine end end\n'
              '  def deep(n: Nine[a, b, c, d, e, f, g, h, i], k: integer): boolean do if k == 0 do [n] == [n] else deep(n, k - 1) end end\n'
              '  def main() do\n    a = %Nine{one: 1, two: "b", three: [3], four: some(4), five: {5, "e"}, six: true, seven: "g", eight: some(["h"]), nine: 9}\n'
              '    b = %Nine{one: 1, two: "b", three: [3], four: some(4), five: {5, "e"}, six: true, seven: "g", eight: some(["h"]), nine: 9}\n'
              '    c = %Nine{one: 1, two: "b", three: [3], four: some(4), five: {5, "e"}, six: true, seven: "g", eight: some(["x"]), nine: 9}\n'
              '    d = %Nine{one: 1, two: "b", three: [4], four: some(4), five: {5, "e"}, six: true, seven: "g", eight: some(["h"]), nine: 7}\n'
              '    IO.puts(yes(a == b) <> yes(a == c) <> yes(a == d) <> yes(same(a, b)) <> yes(same(a, c)) <> yes(same([a], [b])) <> yes(same([a], [d])))\n'
              '    IO.puts(Integer.to_string(last(a, a)) <> Integer.to_string(last(a, d)) <> yes(deep(a, 3)))\n    f = wrap(a)\n    IO.puts(yes(f(9)) <> yes(f(8)))\n'
              '    p: Seven[integer, string, boolean, integer, string, integer, string] = Seven.second(1, "q", [{1, "a"}])\n'
              '    q: Seven[integer, string, boolean, integer, string, integer, string] = Seven.second(1, "q", [{1, "b"}])\n'
              '    r: Seven[integer, string, boolean, integer, string, integer, string] = Seven.third\n'
              '    IO.puts(yes(p == p) <> yes(p == q) <> yes(p == r) <> yes(r == r) <> yes(same(p, q)))\n    System.halt(0)\n  end\nend\n')
        result=subprocess.run([str(compiler)],input=nine.encode(),capture_output=True,env={'PATH':''},timeout=120)
        assert (result.returncode,result.stderr)==(0,b''),('nine parameters',result.returncode,result.stderr)
        out=root/'out';out.write_bytes(result.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(0,b'ynnynyn\n97y\nyn\nynnyn\n',b''),('nine parameters',run)
        for body,label in REJECTIONS:
            result=compiled(body)
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
        for source in INVALID:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source[:90],result.returncode)
    print(f'PASS generics: {len(CASES)} programs with generic functions, generic structs and sum types, patterns and equality through type variables, six and nine type parameters, a million generic calls without allocation, {len(REJECTIONS)} rejections, {len(INVALID)} invalid declarations')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
