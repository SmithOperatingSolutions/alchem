#!/usr/bin/env python3
"""Parsing: forms the pinned parser reads that the compiler took otherwise: every program runs as the pinned compiler runs it."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_bundle',ROOT/'scripts/bundle-alchem.py')
bundler=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundler)

# (files, status, standard output, standard error) as the pinned compiler runs
# main.alc; @ stands for the directory the files are in.
RUNS=[({'main.alc': 'defmodule T do\n  struct Box[a] do\n    v: a\n    w: list[tuple[a, integer]]\n  end\n  type Tree[a] do\n    leaf\n    node(l: Tree[a], v: a, r: Tree[a])\n  end\n  def main() do\n    b = %Box{v: 1, w: [{2, 3}]}\n    e: Tree[string] = Tree.leaf\n    t = Tree.node(e, "x", e)\n    IO.inspect(b)\n    IO.inspect(t)\n  end\nend\n'},
  0,
  b'%Box{v: 1, w: [{2, 3}]}\nTree.node(Tree.leaf, "x", Tree.leaf)\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def f(x: integer): integer do\n'
               '    x + 1\n'
               '  end\n'
               '  def main() do\n'
               '    x = 1\n'
               '    y = x\n'
               '    (x + 1) |> IO.inspect()\n'
               '    IO.puts("#{y}")\n'
               '  end\n'
               'end\n'},
  0,
  b'2\n1\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def f(x: integer): integer do\n'
               '    x + 1\n'
               '  end\n'
               '  def main() do\n'
               '    g = &f/1\n'
               '    y = g\n'
               '    (3 + 1) |> IO.inspect()\n'
               '    IO.puts("#{y(1)}")\n'
               '  end\n'
               'end\n'},
  0,
  b'4\n2\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def f(x: integer): integer do\n'
               '    x + 1\n'
               '  end\n'
               '  def main() do\n'
               '    y = f(1)\n'
               '    (2) |> IO.inspect()\n'
               '    z = f(3)\n'
               '    (z + 1) |> IO.inspect()\n'
               '    IO.puts("#{y}")\n'
               '  end\n'
               'end\n'},
  0,
  b'2\n5\n2\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def f(x: integer): integer do\n'
               '    x + 1\n'
               '  end\n'
               '  def main() do\n'
               '    t = {1, 2}\n'
               '    y = elem(t, 0)\n'
               '    (y + 1) |> IO.inspect()\n'
               '    s = "a"\n'
               '    w = s\n'
               '    ("b" <> w) |> IO.puts()\n'
               '  end\n'
               'end\n'},
  0,
  b'2\nba\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    b = 1\n'
               '    c = b\n'
               '    [c, 2] |> IO.inspect()\n'
               '  end\n'
               'end\n'},
  0,
  b'[1, 2]\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    b = [1]\n'
               '    c = b\n'
               '    [0] |> IO.inspect()\n'
               '    IO.inspect(c)\n'
               '  end\n'
               'end\n'},
  0,
  b'[0]\n[1]\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    a = 2\n'
               '    b = a\n'
               '    [x, y] = [b, 3]\n'
               '    IO.inspect(x + y)\n'
               '  end\n'
               'end\n'},
  0,
  b'5\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    l = [5, 6]\n'
               '    b = l\n'
               '    [0] |> IO.inspect()\n'
               '    IO.inspect(b[0])\n'
               '  end\n'
               'end\n'},
  0,
  b'[0]\n5\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def mk(v: integer): fn[boolean] do\n'
               '    n = v + 1\n'
               '    fn -> n > 0 end\n'
               '  end\n'
               '  def main() do\n'
               '    p = mk(3)\n'
               '    IO.inspect(p())\n'
               '  end\n'
               'end\n'},
  0,
  b'true\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def mk(v: integer): fn[integer, integer] do\n'
               '    n = v + 1\n'
               '    m = n * 2\n'
               '    fn x -> x + n + m end\n'
               '  end\n'
               '  def main() do\n'
               '    p = mk(3)\n'
               '    IO.inspect(p(2))\n'
               '  end\n'
               'end\n'},
  0,
  b'14\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def mk(v: integer): fn[integer, integer] do\n'
               '    fn x -> x + v end\n'
               '  end\n'
               '  def main() do\n'
               '    p = mk(3)\n'
               '    IO.inspect(p(2))\n'
               '  end\n'
               'end\n'},
  0,
  b'5\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def mk(v: integer): fn[integer, integer] do\n'
               '    n = v + 1\n'
               '    if n > 2 do\n'
               '      fn x -> x + n end\n'
               '    else\n'
               '      fn x -> x - n end\n'
               '    end\n'
               '  end\n'
               '  def main() do\n'
               '    p = mk(3)\n'
               '    IO.inspect(p(2))\n'
               '  end\n'
               'end\n'},
  0,
  b'6\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    x = 3\n'
               '    y = case x do\n'
               '      1 -> hd([])\n'
               '      2 -> 5\n'
               '      _ -> 7\n'
               '    end\n'
               '    IO.inspect(y)\n'
               '  end\n'
               'end\n'},
  0,
  b'7\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    x = 3\n'
               '    y = case x do\n'
               '      1 -> 5\n'
               '      2 -> hd([])\n'
               '      _ -> 7\n'
               '    end\n'
               '    IO.inspect(y)\n'
               '  end\n'
               'end\n'},
  0,
  b'7\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    x = 1\n'
               '    y = if x > 2 do hd([]) else 4 end\n'
               '    IO.inspect(y)\n'
               '    z = if x > 0 do 4 else hd([]) end\n'
               '    IO.inspect(z)\n'
               '    w = case x do\n'
               '      1 -> hd([])\n'
               '      _ -> 7\n'
               '    end\n'
               '    IO.inspect(w)\n'
               '  end\n'
               'end\n'},
  2,
  b'4\n4\n',
  b'@/main.alc:9:12: the list is empty\n  at T.main <closure> (@/main.alc:9)\n  at T.main (@/main.alc:8)\n'),
 ({'main.alc': 'defmodule T do\n'
               '  def main() do\n'
               '    x = 1\n'
               '    w = case x do\n'
               '      1 -> hd([])\n'
               '      _ -> "s"\n'
               '    end\n'
               '    IO.inspect(w)\n'
               '  end\n'
               'end\n'},
  2,
  b'',
  b'@/main.alc:5:12: the list is empty\n  at T.main <closure> (@/main.alc:5)\n  at T.main (@/main.alc:4)\n'),
 ({'main.alc': 'defmodule T do\n'
               '  type V do\n'
               '    list(items: list[integer])\n'
               '    integer(n: integer)\n'
               '    boolean(b: boolean)\n'
               '    string(s: string)\n'
               '    float(f: float)\n'
               '    atom(a: atom)\n'
               '    map(m: map[string, integer])\n'
               '    tuple(t: tuple[])\n'
               '    bytes(n: integer)\n'
               '    option(n: integer)\n'
               '    result(n: integer)\n'
               '    null\n'
               '  end\n'
               '  def main() do\n'
               '    IO.puts(inspect([V.list([1, 2]), V.integer(1), V.string("x"), V.null, V.float(1.5), '
               'V.boolean(true), V.atom(:a), V.map(%{}), V.tuple({}), V.bytes(1), V.option(1), '
               'V.result(1)]))\n'
               '    case V.integer(2) do\n'
               '      V.integer(n) -> IO.inspect(n)\n'
               '      V.string(s) -> IO.puts(s)\n'
               '      V.boolean(b) -> IO.inspect(b)\n'
               '      _ -> IO.puts("other")\n'
               '    end\n'
               '  end\n'
               'end\n'},
  0,
  b'[V.list([1, 2]), V.integer(1), V.string("x"), V.null, V.float(1.5), V.boolean(true), V.atom(:a), V.map(%'
  b'{}), V.tuple({}), V.bytes(1), V.option(1), V.result(1)]\n2\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  type V do\n'
               '    integer\n'
               '    string\n'
               '    boolean\n'
               '  end\n'
               '  def main() do\n'
               '    IO.inspect(V.integer)\n'
               '    IO.inspect(V.string == V.string)\n'
               '  end\n'
               'end\n'},
  0,
  b'V.integer\ntrue\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def g(x: integer): integer do\n'
               '    (IO.puts("x"))\n'
               '    (x + 1)\n'
               '  end\n'
               '  def main() do\n'
               '    IO.inspect(g(1))\n'
               '  end\n'
               'end\n'},
  0,
  b'x\n2\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def f(x: integer): integer do\n'
               '    x + 1\n'
               '  end\n'
               '  def main() do\n'
               '    (IO.puts("x"))\n'
               '    (f(1))\n'
               '    ((f(1)))\n'
               '    (f(2) |> f())\n'
               '    (Enum.map([1], fn x -> x end))\n'
               '    (IO.inspect(1))\n'
               '    (IO.write("a"))\n'
               '    (IO.puts("#{f(1)}"))\n'
               '    (f(1)) |> IO.inspect()\n'
               '    (1 + 2) |> f() |> IO.inspect()\n'
               '    IO.puts("y")\n'
               '  end\n'
               'end\n'},
  0,
  b'x\n1\na2\n2\n4\ny\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def f(x: integer): integer do\n'
               '    x + 1\n'
               '  end\n'
               '  def main() do\n'
               '    x = 1\n'
               '    z: integer = if x > 1 do hd([]) else 3 end\n'
               '    IO.inspect(z)\n'
               '    IO.inspect(1 + (if x > 1 do hd([]) else 3 end))\n'
               '    IO.puts(if x > 1 do hd([]) else "s" end)\n'
               '    w: integer = hd([])\n'
               '    IO.inspect(w)\n'
               '  end\n'
               'end\n'},
  2,
  b'3\n4\ns\n',
  b'@/main.alc:11:18: the list is empty\n  at T.main (@/main.alc:11)\n'),
 ({'main.alc': 'defmodule T do\n'
               '  def f(x: integer): integer do\n'
               '    x + 1\n'
               '  end\n'
               '  def g(x: integer): integer do\n'
               '    (IO.puts("x"))\n'
               '    (f(1))\n'
               '    (x + 1)\n'
               '  end\n'
               '  def main() do\n'
               '    IO.inspect(g(1))\n'
               '  end\n'
               'end\n'},
  0,
  b'x\n2\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def f(x: integer): integer do\n'
               '    x + 1\n'
               '  end\n'
               '  def mk(v: integer): fn[boolean] do\n'
               '    n = v + 1\n'
               '    m: fn[boolean] = fn -> n > 0 end\n'
               '    m\n'
               '  end\n'
               '  def mk2(v: integer): fn[boolean] do\n'
               '    n = v + 1\n'
               '    m = fn(): boolean do n > 0 end\n'
               '    m\n'
               '  end\n'
               '  def main() do\n'
               '    p = mk(3)\n'
               '    IO.inspect(p())\n'
               '    q = mk2(3)\n'
               '    IO.inspect(q())\n'
               '  end\n'
               'end\n'},
  0,
  b'true\ntrue\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  def apply(f: fn[integer, string], x: integer): string do\n'
               '    f(x)\n'
               '  end\n'
               '  def main() do\n'
               '    labels = Enum.map([0, -3, 7], fn\n'
               '      0 -> "zero"\n'
               '      n when n < 0 -> "negative"\n'
               '      _ -> "positive"\n'
               '    end)\n'
               '    IO.puts(inspect(labels))\n'
               '    areas = Enum.map([{2, 3}, {4, 0}], fn\n'
               '      {_, 0} -> 0\n'
               '      {width, height} -> width * height\n'
               '    end)\n'
               '    IO.puts(inspect(areas))\n'
               '    IO.puts(apply(fn\n'
               '      1 -> "a"\n'
               '      _ -> "b#{10 / (3 - 3)}"\n'
               '    end, 2))\n'
               '  end\n'
               'end\n'},
  2,
  b'["zero", "negative", "positive"]\n[6, 0]\n',
  b'@/main.alc:19:19: division by zero\n  at T.main <closure> (@/main.alc:19)\n  at T.apply (@/main.alc:3)'
  b'\n  at T.main (@/main.alc:17)\n'),
 ({'main.alc': 'defmodule T do\n'
               '  type V do\n'
               '    text(text: string)\n'
               '    list(items: list[integer])\n'
               '    integer(n: integer)\n'
               '    boolean(b: boolean)\n'
               '    string(s: string)\n'
               '    float(f: float)\n'
               '    null\n'
               '  end\n'
               '  def show(v: V): string do\n'
               '    case v do\n'
               '      V.text(t) -> t\n'
               '      V.list(l) -> "#{length(l)}"\n'
               '      V.integer(n) -> "#{n}"\n'
               '      V.boolean(b) -> "#{b}"\n'
               '      V.string(s) -> s\n'
               '      V.float(f) -> "#{f}"\n'
               '      V.null -> "null"\n'
               '    end\n'
               '  end\n'
               '  def main() do\n'
               '    IO.puts(show(V.text("a")) <> show(V.list([1])) <> show(V.integer(2)) <> '
               'show(V.boolean(true)) <> show(V.string("s")) <> show(V.null))\n'
               '    IO.puts(inspect([V.list([1, 2]), V.integer(1), V.string("x"), V.null, V.float(1.5)]))\n'
               '  end\n'
               'end\n'},
  0,
  b'a12truesnull\n[V.list([1, 2]), V.integer(1), V.string("x"), V.null, V.float(1.5)]\n',
  b''),
 ({'main.alc': 'defmodule T do\n'
               '  struct S do\n'
               '    string: string\n'
               '    integer: integer = 2\n'
               '    option: option[integer] = none\n'
               '    list: list[integer] = []\n'
               '    length: integer = 0\n'
               '    map: integer = 1\n'
               '  end\n'
               '  def main() do\n'
               '    s = %S{string: "a", list: [1]}\n'
               '    IO.inspect(s)\n'
               '    IO.puts(s.string <> "#{s.integer}#{length(s.list)}#{s.length}#{s.map}")\n'
               '    t = %S{s | integer: 5, option: some(1)}\n'
               '    IO.inspect(t)\n'
               '    case t do\n'
               '      %S{string: x, integer: n} -> IO.puts("#{x}#{n}")\n'
               '    end\n'
               '  end\n'
               'end\n'},
  0,
  b'%S{string: "a", integer: 2, option: none, list: [1], length: 0, map: 1}\na2101\n%S{string: "a", intege'
  b'r: 5, option: some(1), list: [1], length: 0, map: 1}\na5\n',
  b'')]

# Programs the pinned compiler rejects.
REJECTS=[# A field whose type is a type variable the declaration does not declare.
 {'main.alc': 'defmodule T do\n  struct C do\n    t: b\n  end\n  def main() do\n    IO.puts("x")\n  end\nend\n'},
 {'main.alc': 'defmodule T do\n  type S do\n    b(e: n)\n    c\n  end\n  def main() do\n    IO.puts("x")\n  end\nend\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    y = f\n'
              '    (3)\n'
              '    IO.puts("#{y}")\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    m = %{a: 1}\n'
              '    y = m.a\n'
              '    (y + 1) |> IO.inspect()\n'
              '    IO.inspect(y)\n'
              '    (1 + 1) |> IO.inspect()\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def main() do\n'
              '    x = 1\n'
              '    w = case x do\n'
              '      1 -> tl([])\n'
              '      _ -> ["s"]\n'
              '    end\n'
              '    IO.inspect(w)\n'
              '    IO.inspect(hd([]) + 1)\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    (IO.puts("x"))\n'
              '    (f(1))\n'
              '    (1 + 2)\n'
              '    IO.puts("y")\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    x = 2\n'
              '    (x)\n'
              '    (if x > 1 do IO.puts("a") else IO.puts("b") end)\n'
              '    IO.puts("y")\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    y = hd([])\n'
              '    IO.inspect(y)\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    IO.inspect(hd([]) + 1)\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    IO.inspect(hd([]))\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    x = 1\n'
              '    y = if x > 0 do hd([]) else hd([]) end\n'
              '    IO.inspect(y)\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    y = f\n'
              '    (3)\n'
              '    IO.puts("#{y}")\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    (1 + 2)\n'
              '    IO.puts("y")\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    (if 1 > 2 do IO.puts("a") else IO.puts("b") end)\n'
              '    IO.puts("y")\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    (if 1 > 2 do 1 else 2 end)\n'
              '    IO.puts("y")\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    (f(1) + 1)\n'
              '    IO.puts("y")\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def main() do\n'
              '    x = 2\n'
              '    (x)\n'
              '    IO.puts("y")\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def f(x: integer): integer do\n'
              '    x + 1\n'
              '  end\n'
              '  def mk(v: integer): fn[boolean] do\n'
              '    n = v + 1\n'
              '    m = fn -> n > 0 end\n'
              '    m\n'
              '  end\n'
              '  def main() do\n'
              '    p = mk(3)\n'
              '    IO.inspect(p())\n'
              '  end\n'
              'end\n'},
 {'main.alc': 'defmodule T do\n'
              '  def apply(f: fn[integer, string], x: integer): string do\n'
              '    f(x)\n'
              '  end\n'
              '  def main() do\n'
              '    IO.puts(apply(fn\n'
              '      1 -> "a"\n'
              '      n when n > 5 -> "b"\n'
              '    end, 2))\n'
              '  end\n'
              'end\n'}]


def bundled(files,directory):
    for name,text in files.items():(directory/name).write_text(text)
    return bundler.bundle(str(directory/'main.alc'))


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-parsing-') as d:
        d=Path(d).resolve();out=d/'out'
        for index,(files,status,stdout,stderr) in enumerate(RUNS):
            directory=d/f'run{index}';directory.mkdir()
            # A program of one file is also compiled as it is, without a bundle.
            sources=[(bundled(files,directory),stderr.replace(b'@/',str(directory).encode()+b'/'))]
            if len(files)==1:sources.append((files['main.alc'].encode(),stderr.replace(b'@/main.alc',b'<stdin>')))
            for source,expected in sources:
                result=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
                assert (result.returncode,result.stderr)==(0,b''),(files['main.alc'],result.returncode,result.stderr)
                out.write_bytes(result.stdout);out.chmod(0o700)
                run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
                assert (run.returncode,run.stdout,run.stderr)==(status,stdout,expected),(files['main.alc'],run,expected)
        for index,files in enumerate(REJECTS):
            directory=d/f'reject{index}';directory.mkdir()
            sources=[bundled(files,directory)]+([files['main.alc'].encode()] if len(files)==1 else [])
            for source in sources:
                result=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
                assert (result.returncode,result.stdout)==(65,b''),(files['main.alc'],result.returncode)
    print(f'PASS parsing: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; a ( or [ that starts a line, b[, fn without parameters after a binding, fn with clauses, hd([]) among other values, variants and fields named as types, ( call ) as a statement')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
