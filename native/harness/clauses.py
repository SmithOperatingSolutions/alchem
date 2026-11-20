#!/usr/bin/env python3
"""Function definitions: several arities of one name, default arguments, clauses
with patterns and guards, forms for arguments of different types, return and
raise. Every program runs as the pinned compiler runs it, or is rejected where
the pinned compiler rejects it."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_bundle',ROOT/'scripts/bundle-alchem.py')
bundler=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundler)

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    if n > 3 do\n'
  '      raise("too big")\n'
  '    end\n'
  '    n\n'
  '  end\n'
  '  def g(n: integer): integer do\n'
  '    raise("always")\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1)))\n'
  '    IO.puts(inspect(g(5)))\n'
  '  end\n'
  'end\n',
  2,
  b'1\n',
  b'<stdin>:9:5: always\n  at Example.g (<stdin>:9)\n  at Example.main (<stdin>:13)\n'),
 ('defmodule Example do\n'
  '  def f(0) do 1 end\n'
  '  def f(n: integer): integer do n * 2 end\n'
  '  def main() do IO.puts(inspect(f(0)+f(4))) end\n'
  'end\n',
  0,
  b'9\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0, b: integer \\\\ 5): integer do b end\n'
  '  def f(n: integer, b) do n + b end\n'
  '  def main() do IO.puts(inspect(f(3)+f(0)+f(1,1))) end\n'
  'end\n',
  0,
  b'15\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ 1 + 2): integer do a + b end\n'
  '  def main() do IO.puts(inspect(f(3))) end\n'
  'end\n',
  0,
  b'6\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ -2, c: list[integer] \\\\ [1, 2], d: option[string] \\\\ none, e: '
  'tuple[integer, string] \\\\ {1, "x"}, g: map[string, integer] \\\\ %{"a" => 1}): integer do a + b + length(c) + '
  'elem(e, 0) + Map.get(g, "a", 0) end\n'
  '  def main() do IO.puts(inspect(f(3))) end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer, c: integer \\\\ 1): integer do a + b + c end\n'
  '  def f(a: integer): integer do a end\n'
  '  def main() do IO.puts(inspect(f(3)+f(1,2)+f(1,2,3))) end\n'
  'end\n',
  0,
  b'13\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ 1): integer do a + b end\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.reduce([1, 2], 0, &f/2)))\n'
  '    IO.puts(inspect(Enum.reduce([1, 2], 0, &f)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n3\n',
  b''),
 ('defmodule Example do\n'
  '  def f([], acc): integer do acc end\n'
  '  def f([h | t]: list[integer], acc: integer) do f(t, acc + h) end\n'
  '  def main() do IO.puts(inspect(f([1, 2, 3], 0))) end\n'
  'end\n',
  0,
  b'6\n',
  b''),
 ('defmodule Example do\n'
  '  def show(n: integer): string do "int" end\n'
  '  def show(s: string): string do "str" end\n'
  '  def main() do IO.puts(show(1) <> show("a")) end\n'
  'end\n',
  0,
  b'intstr\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0): integer do 1 end\n'
  '  def f(n: integer): integer do n end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule Example do\n'
  '  def f(true): string do "y" end\n'
  '  def f(false) do "n" end\n'
  '  def main() do IO.puts(f(true) <> f(false)) end\n'
  'end\n',
  0,
  b'yn\n',
  b''),
 ('defmodule Example do\n'
  '  def f(some(n): option[integer]): integer do n end\n'
  '  def f(none) do 0 end\n'
  '  def main() do IO.puts(inspect(f(some(3)) + f(none))) end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def f({0, _}: tuple[integer, integer], b: boolean): integer do 0 end\n'
  '  def f({a, b}, true) do a + b end\n'
  '  def f({a, b}, false) do a - b end\n'
  '  def main() do IO.puts(inspect(f({0, 1}, true) + f({5, 1}, true) + f({5, 1}, false))) end\n'
  'end\n',
  0,
  b'10\n',
  b''),
 ('defmodule Example do\n'
  '  def f("a"): integer do 1 end\n'
  '  def f("b") do 2 end\n'
  '  def f(other) do String.length(other) end\n'
  '  def main() do IO.puts(inspect(f("a") + f("b") * 10 + f("hello") * 100)) end\n'
  'end\n',
  0,
  b'521\n',
  b''),
 ('defmodule Example do\n'
  '  def f([h | _]: list[integer]): integer when h > 10 do h end\n'
  '  def f([h | t]) when length(t) > 1 do 0 - h end\n'
  '  def f(_) do 0 end\n'
  '  def main() do IO.puts(inspect(f([11]) + f([1, 2, 3]) * 100 + f([]))) end\n'
  'end\n',
  0,
  b'-89\n',
  b''),
 ('defmodule Example do\n'
  '  def add(a: integer, b: integer \\\\ 10): integer do a + b end\n'
  '  def main() do\n'
  '    IO.puts(inspect(1 |> add()))\n'
  '    IO.puts(inspect(1 |> add(2)))\n'
  '    IO.puts(inspect(1 |> add() |> add(5) |> add()))\n'
  '  end\n'
  'end\n',
  0,
  b'11\n3\n26\n',
  b''),
 ('defmodule Example do\n'
  '  defp go(0, acc: integer): integer do acc end\n'
  '  defp go(n: integer, acc) do go(n - 1, acc + n) end\n'
  '  def main() do IO.puts(inspect(go(100, 0))) end\n'
  'end\n',
  0,
  b'5050\n',
  b''),
 ('defmodule Example do\n'
  '  def kind(0): string do "zero" end\n'
  '  def kind(n: integer) when n < 0 do "neg" end\n'
  '  def kind(_) do "pos" end\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.map([0, -1, 5], &kind/1)))\n'
  '    f = &kind\n'
  '    IO.puts(f(0))\n'
  '  end\n'
  'end\n',
  0,
  b'["zero", "neg", "pos"]\nzero\n',
  b''),
 ('defmodule Example do\n'
  '  def sign(n: integer): string do\n'
  '    if n < 0 do\n'
  '      return "negative"\n'
  '    end\n'
  '    "non-negative"\n'
  '  end\n'
  '  def find(items: list[integer], want: integer): boolean do\n'
  '    case items do\n'
  '      [] -> return false\n'
  '      [h | t] ->\n'
  '        if h == want do\n'
  '          return true\n'
  '        end\n'
  '        find(t, want)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(sign(-1) <> " " <> sign(1))\n'
  '    IO.puts(inspect(find([1, 2, 3], 2)) <> inspect(find([1, 2, 3], 9)))\n'
  '  end\n'
  'end\n',
  0,
  b'negative non-negative\ntruefalse\n',
  b''),
 ('defmodule Example do\n'
  '  def even?(0): boolean do true end\n'
  '  def even?(n: integer) do odd?(n - 1) end\n'
  '  def odd?(0): boolean do false end\n'
  '  def odd?(n: integer) do even?(n - 1) end\n'
  '  def main() do IO.puts(inspect(even?(10)) <> inspect(odd?(7)) <> inspect(even?(7))) end\n'
  'end\n',
  0,
  b'truetruefalse\n',
  b''),
 ('defmodule Example do\n'
  '  def color(:red): integer do 1 end\n'
  '  def color(:green) do 2 end\n'
  '  def color(_) do 0 end\n'
  '  def main() do IO.puts(inspect(color(:red) + color(:green) * 10 + color(:blue) * 100)) end\n'
  'end\n',
  0,
  b'21\n',
  b''),
 ('defmodule Example do\n'
  '  def area(side: integer): integer do side * side end\n'
  '  def area(w: integer, h: integer): integer do w * h end\n'
  '  def main() do\n'
  '    IO.puts(inspect(area(3) + area(2, 5)))\n'
  '    IO.puts(inspect(Enum.map([1, 2], &area/1)))\n'
  '    IO.puts(inspect(Enum.reduce([1, 2, 3], 1, &area/2)))\n'
  '    IO.puts(inspect(3 |> area() |> area(2)))\n'
  '  end\n'
  'end\n',
  0,
  b'19\n[1, 4]\n6\n18\n',
  b''),
 ('defmodule Example do\n'
  '  def fact(0): integer do 1 end\n'
  '  def fact(n: integer) when n > 0 do n * fact(n - 1) end\n'
  '  def fact(_) do raise("fact needs a non-negative number") end\n'
  '  def main() do\n'
  '    IO.puts(inspect(fact(5)))\n'
  '    IO.puts(inspect(fact(-1)))\n'
  '  end\n'
  'end\n',
  2,
  b'120\n',
  b'<stdin>:4:18: fact needs a non-negative number\n  at Example.fact (<stdin>:4)\n  at Example.main (<stdin>:7)\n'),
 ('defmodule Example do\n'
  '  def fact(0): integer do 1 end\n'
  '  def fact(n: integer) do\n'
  '    n * fact(n - 1)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(fact(20)))\n'
  '    IO.puts(inspect(fact(30)))\n'
  '  end\n'
  'end\n',
  2,
  b'2432902008176640000\n',
  b'<stdin>:4:7: integer overflow\n  at Example.fact (<stdin>:4)\n  at Example.fact (<stdin>:4)\n  at Example.fact '
  b'(<stdin>:4)\n  at Example.fact (<stdin>:4)\n  at Example.fact (<stdin>:4)\n  at Example.fact (<stdin>:4)\n  at E'
  b'xample.fact (<stdin>:4)\n  at Example.fact (<stdin>:4)\n  at Example.fact (<stdin>:4)\n  at Example.fact (<stdi'
  b'n>:4)\n  at Example.main (<stdin>:8)\n'),
 ('defmodule Example do\n'
  '  def count(0): integer do 0 end\n'
  '  def count(n: integer) do 1 + count(n - 1) end\n'
  '  def main() do\n'
  '    IO.puts(inspect(count(50000)))\n'
  '    IO.puts(inspect(count(200000)))\n'
  '  end\n'
  'end\n',
  2,
  b'50000\n',
  b'<stdin>:2:7: call depth exceeded\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.'
  b'count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:'
  b'3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example'
  b'.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>'
  b':3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Exampl'
  b'e.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin'
  b'>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Examp'
  b'le.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdi'
  b'n>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Exam'
  b'ple.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<std'
  b'in>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Exa'
  b'mple.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<st'
  b'din>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Ex'
  b'ample.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<s'
  b'tdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at E'
  b'xample.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<'
  b'stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at '
  b'Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n  at Example.count (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  struct Point do\n'
  '    x: integer\n'
  '    y: integer\n'
  '  end\n'
  '  type Shape do\n'
  '    circle(r: integer)\n'
  '    rect(w: integer, h: integer)\n'
  '    empty\n'
  '  end\n'
  '  def area(Shape.circle(r): Shape): integer do 3 * r * r end\n'
  '  def area(Shape.rect(w, h)) do w * h end\n'
  '  def area(Shape.empty) do 0 end\n'
  '  def norm(%Point{x: 0, y: y}: Point): integer do y end\n'
  '  def norm(%Point{x: x, y: y}) do x + y end\n'
  '  def main() do\n'
  '    IO.puts(inspect(area(Shape.circle(2)) + area(Shape.rect(2, 3)) + area(Shape.empty)))\n'
  '    IO.puts(inspect(norm(%Point{x: 0, y: 4}) + norm(%Point{x: 1, y: 2})))\n'
  '  end\n'
  'end\n',
  0,
  b'18\n7\n',
  b''),
 ('defmodule Example do\n'
  '  def get(ok(v): result[integer, string]): integer do v end\n'
  '  def get(error(m)) do String.length(m) end\n'
  '  def main() do\n'
  '    IO.puts(inspect(get(ok(4)) + get(error("abc"))))\n'
  '  end\n'
  'end\n',
  0,
  b'7\n',
  b''),
 ('defmodule Example do\n'
  '  def f(x: integer, y: integer): integer when x > y do\n'
  '    d = x - y\n'
  '    d * 2\n'
  '  end\n'
  '  def f(x, y) do\n'
  '    d = y - x\n'
  '    d * 3\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(5, 1) + f(1, 5))) end\n'
  'end\n',
  0,
  b'20\n',
  b''),
 ('defmodule Example do\n'
  '  def apply([]: list[integer], _: integer): list[integer] do [] end\n'
  '  def apply(items, k) do Enum.map(items, fn x -> x * k end) end\n'
  '  def main() do IO.puts(inspect(apply([1, 2], 3)) <> inspect(apply([], 3))) end\n'
  'end\n',
  0,
  b'[3, 6][]\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ @k): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ (1)): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ 2 * 3 - 1): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: string \\\\ "a" <> "b"): string do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'"ab"\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: string \\\\ "a#{1}"): string do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'"a1"\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: boolean \\\\ not true): boolean do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'false\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: boolean \\\\ 1 < 2): boolean do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: atom \\\\ :ok): atom do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b':ok\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: result[integer, string] \\\\ ok(1)): result[integer, string] do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'ok(1)\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: result[integer, string] \\\\ error("x")): result[integer, string] do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'error("x")\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: option[integer] \\\\ some(1 + 1)): option[integer] do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'some(2)\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: list[list[integer]] \\\\ [[1], []]): list[list[integer]] do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'[[1], []]\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ -(3)): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'-3\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ 10 / 2): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ 1 / 0): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:33: division by zero\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: boolean \\\\ true and false): boolean do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'false\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: list[integer] \\\\ []): list[integer] do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'[]\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: map[string, integer] \\\\ %{}): map[string, integer] do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'%{}\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: tuple[integer, list[string]] \\\\ {1, ["a"]}): tuple[integer, list[string]] do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'{1, ["a"]}\n',
  b''),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ 9223372036854775807 + 1): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:33: integer overflow\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def f(0, b: integer): integer do b end\n'
  '  def f(n: integer, b: integer \\\\ 5) do n + b end\n'
  '  def main() do IO.puts(inspect(f(3, 1))) end\n'
  'end\n',
  0,
  b'4\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer when 10 / n > 1 do 1 end\n'
  '  def f(_) do 2 end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(2)))\n'
  '    IO.puts(inspect(f(0)))\n'
  '  end\n'
  'end\n',
  2,
  b'1\n',
  b'<stdin>:2:38: division by zero\n  at Example.f (<stdin>:2)\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    g(n)\n'
  '  end\n'
  '  def g(0): integer do 0 end\n'
  '  def g(n: integer) when 10 / (n - 1) > 1 do 1 end\n'
  '  def g(_) do 2 end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(2)))\n'
  '    IO.puts(inspect(f(1)))\n'
  '  end\n'
  'end\n',
  2,
  b'1\n',
  b'<stdin>:6:29: division by zero\n  at Example.g (<stdin>:5)\n  at Example.f (<stdin>:3)\n  at Example.main (<std'
  b'in>:10)\n'),
 ('defmodule Example do\n'
  '  def pick(items: list[t], fallback: option[t] \\\\ none): option[t] do\n'
  '    case items do\n'
  '      [] -> fallback\n'
  '      [x | _] -> some(x)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(pick([1, 2])))\n'
  '    IO.puts(inspect(pick(["a"], some("z"))))\n'
  '    e: list[integer] = []\n'
  '    IO.puts(inspect(pick(e)))\n'
  '    IO.puts(inspect(pick(e, some(4))))\n'
  '  end\n'
  'end\n',
  0,
  b'some(1)\nsome("a")\nnone\nsome(4)\n',
  b''),
 ('defmodule Example do\n'
  '  def len([]: list[t]): integer do 0 end\n'
  '  def len([_ | rest]) do 1 + len(rest) end\n'
  '  def first([]: list[t], fallback: t): t do fallback end\n'
  '  def first([x | _], _) do x end\n'
  '  def member([]: list[t], _: t): boolean do false end\n'
  '  def member([x | rest], y) when x == y do true end\n'
  '  def member([_ | rest], y) do member(rest, y) end\n'
  '  def main() do\n'
  '    IO.puts(inspect(len([1, 2, 3]) + len(["a"])))\n'
  '    e: list[string] = []\n'
  '    IO.puts(first(e, "none") <> first(["a", "b"], "z"))\n'
  '    IO.puts(inspect(first([4], 0)))\n'
  '    IO.puts(inspect(member([1, 2, 3], 2)) <> inspect(member(["a"], "b")))\n'
  '  end\n'
  'end\n',
  0,
  b'4\nnonea\n4\ntruefalse\n',
  b''),
 ('defmodule Example do\n'
  '  def member([]: list[integer], _: integer): boolean do false end\n'
  '  def member([x | rest], y) when x == y do true end\n'
  '  def member([_ | rest], y) do member(rest, y) end\n'
  '  def main() do\n'
  '    IO.puts(inspect(member([1, 2, 3], 2)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule Example do\n'
  '  def f(none: integer): integer do none + 1 end\n'
  '  def g(none: option[integer]): integer do 1 end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1)))\n'
  '  end\n'
  'end\n',
  0,
  b'2\n',
  b''),
 ('defmodule Example do\n'
  '  def f(_: integer, _: string): integer do 1 end\n'
  '  def g(_x: integer): integer do 2 end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1, "a") + g(1)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ 1): integer do a + b end\n'
  '  def f(a: integer, b: integer, c: integer): integer do a + b + c end\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.reduce([1, 2], 0, &f/2)))\n'
  '    g = &f/3\n'
  '    IO.puts(inspect(g(1, 2, 3)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n6\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): string do\n'
  '    if n > 0 do "pos" else raise("neg") end\n'
  '  end\n'
  '  def g(n: integer): integer do\n'
  '    x = if n > 0 do n else raise("bad #{n}") end\n'
  '    x * 2\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(f(1))\n'
  '    IO.puts(inspect(g(2)))\n'
  '    IO.puts(inspect(g(-2)))\n'
  '  end\n'
  'end\n',
  2,
  b'pos\n4\n',
  b'<stdin>:6:28: bad -2\n  at Example.g <closure> (<stdin>:6)\n  at Example.g (<stdin>:6)\n  at Example.main (<std'
  b'in>:12)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer, 0): integer do n end\n'
  '  def f(n, m: integer) do n + m end\n'
  '  def main() do IO.puts(inspect(f(1, 0) + f(1, 2))) end\n'
  'end\n',
  0,
  b'4\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0: integer): integer do 1 end\n'
  '  def f(n: integer): integer when n > 0 do 2 end\n'
  '  def f(_: integer): integer do 3 end\n'
  '  def main() do IO.puts(inspect(f(0) + f(1) * 10 + f(-1) * 100)) end\n'
  'end\n',
  0,
  b'321\n',
  b''),
 ('defmodule Example do\n'
  '  def big?(n: integer): boolean do n > 10 end\n'
  '  def f(n: integer): string when big?(n) do "big" end\n'
  '  def f(n) when n in [1, 2, 3] do "small" end\n'
  '  def f(_) do "other" end\n'
  '  def main() do IO.puts(f(11) <> f(2) <> f(7)) end\n'
  'end\n',
  0,
  b'bigsmallother\n',
  b''),
 ('defmodule Example do\n'
  '  def g(0):\n'
  '      integer do\n'
  '\n'
  '    IO.puts("zero")\n'
  '    0\n'
  '  end\n'
  '  def g(n: integer)\n'
  '      when 10 / (n - 1) > 1 do\n'
  '    1\n'
  '  end\n'
  '  def g(_) do\n'
  '    2\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(g(0)))\n'
  '    IO.puts(inspect(g(2)))\n'
  '    IO.puts(inspect(g(1)))\n'
  '  end\n'
  'end\n',
  2,
  b'zero\n0\n1\n',
  b'<stdin>:9:15: division by zero\n  at Example.g (<stdin>:2)\n  at Example.main (<stdin>:18)\n'),
 ('defmodule Example do\n'
  '  def g(n: integer):\n'
  '      integer when 10 / (n - 1) > 1 do\n'
  '\n'
  '    IO.puts("zero")\n'
  '    0\n'
  '  end\n'
  '  def g(_) do\n'
  '    2\n'
  '  end\n'
  '  def k({a, b}: tuple[integer, integer]):\n'
  '     integer do\n'
  '\n'
  '    a / b\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(k({1, 1})))\n'
  '    IO.puts(inspect(g(1)))\n'
  '  end\n'
  'end\n',
  2,
  b'1\n',
  b'<stdin>:3:23: division by zero\n  at Example.g (<stdin>:2)\n  at Example.main (<stdin>:18)\n'),
 ('defmodule Example do\n'
  '  def h(a: integer, b: integer \\\\ 10 / 0): integer do\n'
  '    a + b\n'
  '  end\n'
  '  def main() do\n'
  '    y = [h(1,\n'
  '      2),   Example.h(  3   )]\n'
  '    IO.puts(inspect(y))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:7:13: division by zero\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def h(a: integer, b: integer \\\\ 10 / 0): integer do\n'
  '    a + b\n'
  '  end\n'
  '  def main() do\n'
  '    y =    3 |> h()\n'
  '    IO.puts(inspect(y))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:6:17: division by zero\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def h(a: integer, b: integer \\\\ 10 / 0): integer do\n'
  '    a + b\n'
  '  end\n'
  '  def main() do\n'
  '    y =    3 |> Example.h()\n'
  '    IO.puts(inspect(y))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:6:17: division by zero\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    return n + 1\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'2\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    if n > 0 do\n'
  '      return 1\n'
  '    else\n'
  '      return 2\n'
  '    end\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1) + f(-1))) end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  '    f = fn(x: integer): integer do\n'
  '      if x > 0 do\n'
  '        return 1\n'
  '      end\n'
  '      2\n'
  '    end\n'
  '    IO.puts(inspect(f(1) + f(-1)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def f(items: list[integer]): integer do\n'
  '    doubled = Enum.map(items, fn x ->\n'
  '      if x > 2 do\n'
  '        return 0\n'
  '      end\n'
  '      x * 2\n'
  '    end)\n'
  '    Enum.sum(doubled)\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f([1, 2, 3]))) end\n'
  'end\n',
  0,
  b'6\n',
  b''),
 ('defmodule Example do\n'
  '  def find(items: list[integer], want: integer): boolean do\n'
  '    case items do\n'
  '      [] -> return false\n'
  '      [h | t] ->\n'
  '        if h == want do\n'
  '          return true\n'
  '        end\n'
  '        find(t, want)\n'
  '    end\n'
  '  end\n'
  '  def main() do IO.puts(inspect(find([1, 2, 3], 2)) <> inspect(find([1, 2, 3], 9))) end\n'
  'end\n',
  0,
  b'truefalse\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0): integer do\n'
  '    return 7\n'
  '  end\n'
  '  def f(n: integer) when n > 5 do\n'
  '    if n > 10 do\n'
  '      return 10\n'
  '    end\n'
  '    n\n'
  '  end\n'
  '  def f(n) do\n'
  '    return 0 - n\n'
  '  end\n'
  '  def main() do IO.puts(inspect([f(0), f(7), f(20), f(3)])) end\n'
  'end\n',
  0,
  b'[7, 7, 10, -3]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): string do\n'
  '    if n < 0 do\n'
  '      IO.puts("neg")\n'
  '      return "negative"\n'
  '    end\n'
  '    IO.puts("after")\n'
  '    "non-negative"\n'
  '  end\n'
  '  def main() do IO.puts(f(-1) <> f(1)) end\n'
  'end\n',
  0,
  b'neg\nafter\nnegativenon-negative\n',
  b''),
 ('defmodule Example do\n'
  '  def g(n: integer): integer do n * 2 end\n'
  '  def f(n: integer): integer do\n'
  '    if n < 0 do\n'
  '      return g(n)\n'
  '    end\n'
  '    return n |> g() |> g()\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(-1) + f(1))) end\n'
  'end\n',
  0,
  b'2\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): option[integer] do\n'
  '    if n < 0 do\n'
  '      return none\n'
  '    end\n'
  '    some(n)\n'
  '  end\n'
  '  def g(n: integer): list[integer] do\n'
  '    if n < 0 do\n'
  '      return []\n'
  '    end\n'
  '    [n]\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(-1)) <> inspect(f(1)) <> inspect(g(-1)) <> inspect(g(2))) end\n'
  'end\n',
  0,
  b'nonesome(1)[][2]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    cond do\n'
  '      n > 10 -> return 1\n'
  '      n > 5 -> 2\n'
  '      true -> return 3\n'
  '    end\n'
  '  end\n'
  '  def main() do IO.puts(inspect([f(11), f(6), f(1)])) end\n'
  'end\n',
  0,
  b'[1, 2, 3]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    if n == 0 do\n'
  '      return 1 / n\n'
  '    end\n'
  '    return f(n - 1) + 1\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(3))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:16: division by zero\n  at Example.f (<stdin>:4)\n  at Example.f (<stdin>:6)\n  at Example.f (<stdin>'
  b':6)\n  at Example.f (<stdin>:6)\n  at Example.main (<stdin>:8)\n'),
 ('defmodule Example do\n'
  '  def first(items: list[t], fallback: t): t do\n'
  '    case items do\n'
  '      [] -> return fallback\n'
  '      [x | _] -> x\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    e: list[string] = []\n'
  '    IO.puts(first(e, "none") <> first(["a"], "z"))\n'
  '  end\n'
  'end\n',
  0,
  b'nonea\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    a = n * 2\n'
  '    if a > 10 do\n'
  '      b = a + 1\n'
  '      return b\n'
  '    end\n'
  '    c = a + 2\n'
  '    c\n'
  '  end\n'
  '  def main() do IO.puts(inspect([f(1), f(9)])) end\n'
  'end\n',
  0,
  b'[4, 19]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0, b: integer, c: integer, d: integer, e: integer, g: integer, h: integer, i: integer): integer do b + c '
  '+ d + e + g + h + i end\n'
  '  def f(a: integer, b, c, d, e, g, h, 0) do a * 1000 + b + c + d + e + g + h end\n'
  '  def f(a, b, c, d, e, g, h, i) when i > 100 do 0 - i end\n'
  '  def f(a, _, _, _, _, _, _, i) do a - i end\n'
  '  def main() do IO.puts(inspect([f(0, 1, 2, 3, 4, 5, 6, 7), f(1, 1, 2, 3, 4, 5, 6, 0), f(1, 1, 2, 3, 4, 5, 6, '
  '200), f(9, 1, 2, 3, 4, 5, 6, 7)])) end\n'
  'end\n',
  0,
  b'[28, 1021, -200, 2]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ 2, c: integer \\\\ 3, d: integer \\\\ 4, e: integer \\\\ 5, g: integer \\\\ '
  '6, h: integer \\\\ 7, i: string \\\\ "z"): string do\n'
  '    inspect(a + b + c + d + e + g + h) <> i\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(f(1) <> f(1, 1) <> f(1, 1, 1, 1, 1, 1) <> f(1, 1, 1, 1, 1, 1, 1) <> f(1, 1, 1, 1, 1, 1, 1, "q"))\n'
  '    IO.puts(10 |> f() )\n'
  '    IO.puts(10 |> f(20) |> String.length() |> f())\n'
  '  end\n'
  'end\n',
  0,
  b'28z27z13z7z7q\n37z\n30z\n',
  b''),
 ('defmodule Example do\n'
  '  def f(%{"a" => 1}: map[string, integer]): string do "a1" end\n'
  '  def f(%{"a" => n, "b" => m}) when n > m do "a>b" end\n'
  '  def f(%{"b" => m}) do "b#{m}" end\n'
  '  def f(_) do "other" end\n'
  '  def main() do\n'
  '    IO.puts(f(%{"a" => 1}) <> f(%{"a" => 5, "b" => 2}) <> f(%{"a" => 2, "b" => 5}) <> f(%{"c" => 1}))\n'
  '  end\n'
  'end\n',
  0,
  b'a1a>bb5other\n',
  b''),
 ('defmodule Example do\n'
  '  def kind(0): string do "zero" end\n'
  '  def kind(n: integer) when n < 0 do "neg" end\n'
  '  def kind(_) do "pos" end\n'
  '  def twice(f: fn[integer, string], n: integer): string do f(n) <> f(0 - n) end\n'
  '  def pick(): fn[integer, string] do &kind/1 end\n'
  '  def main() do\n'
  '    IO.puts(twice(&kind/1, 3))\n'
  '    IO.puts(twice(&kind, 0))\n'
  '    g = pick()\n'
  '    IO.puts(g(-9))\n'
  '    IO.puts(inspect(Enum.map([1, 0, -1], &kind/1)))\n'
  '    IO.puts(inspect([1, 0, -1] |> Enum.map(&kind/1) |> Enum.join(",")))\n'
  '  end\n'
  'end\n',
  0,
  b'posneg\nzerozero\nneg\n["pos", "zero", "neg"]\n"pos,zero,neg"\n',
  b''),
 ('defmodule Example do\n'
  '  def v(): integer do 1 end\n'
  '  def v(a: integer): integer do a + v() end\n'
  '  def v(a: integer, b: integer): integer do v(a) + v(b) end\n'
  '  def main() do\n'
  '    IO.puts(inspect(v() + v(10) + v(100, 1000)))\n'
  '    f = &v/0\n'
  '    g = &v/2\n'
  '    IO.puts(inspect(f() + g(1, 2)))\n'
  '  end\n'
  'end\n',
  0,
  b'1114\n6\n',
  b''),
 ('defmodule Example do\n'
  '  def f({some(x), [y | _]}: tuple[option[integer], list[integer]]): integer do x + y end\n'
  '  def f({none, [y, z | _]}) do y * z end\n'
  '  def f({some(x), []}) do x end\n'
  '  def f({none, _}) do -1 end\n'
  '  def main() do\n'
  '    e: list[integer] = []\n'
  '    IO.puts(inspect([f({some(1), [2]}), f({none, [3, 4]}), f({some(5), e}), f({none, [1]}), f({none, e})]))\n'
  '  end\n'
  'end\n',
  0,
  b'[3, 12, 5, -1, -1]\n',
  b''),
 ('defmodule Example do\n'
  '  def f("yes", true): integer do 1 end\n'
  '  def f("yes", false) do 2 end\n'
  '  def f(s: string, b: boolean) when b do String.length(s) end\n'
  '  def f(_, _) do 0 end\n'
  '  def main() do IO.puts(inspect([f("yes", true), f("yes", false), f("maybe", true), f("no", false)])) end\n'
  'end\n',
  0,
  b'[1, 2, 5, 0]\n',
  b''),
 ('defmodule Example do\n'
  '  def ack(0, n: integer): integer do n + 1 end\n'
  '  def ack(m: integer, 0) do ack(m - 1, 1) end\n'
  '  def ack(m, n) do ack(m - 1, ack(m, n - 1)) end\n'
  '  def main() do IO.puts(inspect(ack(2, 3))) end\n'
  'end\n',
  0,
  b'9\n',
  b''),
 ('defmodule Example do\n'
  '  def f(-1): string do "minus one" end\n'
  '  def f(0) do "zero" end\n'
  '  def f(n: integer) do inspect(n) end\n'
  '  def main() do IO.puts(f(-1) <> f(0) <> f(-2)) end\n'
  'end\n',
  0,
  b'minus onezero-2\n',
  b''),
 ('defmodule Example do\n'
  '  defp f(a: integer): integer do a end\n'
  '  def f(a: integer, b: integer): integer do f(a) + f(b) end\n'
  '  def main() do IO.puts(inspect(f(1, 2))) end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def join([]: list[string], sep: string \\\\ ", "): string do "" end\n'
  '  def join([one], _) do one end\n'
  '  def join([h | t], sep) do h <> sep <> join(t, sep) end\n'
  '  def main() do\n'
  '    IO.puts(join(["a", "b", "c"]))\n'
  '    IO.puts(["a", "b", "c"] |> join("-"))\n'
  '    IO.puts(["x"] |> join())\n'
  '  end\n'
  'end\n',
  0,
  b'a, b, c\na-b-c\nx\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ "x"): integer do a end\n'
  '  def main() do IO.puts(inspect(f(1, 2))) end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: string \\\\ "s"): string do b end\n'
  '  def main() do IO.puts(f(1) <> f(2, "t")) end\n'
  'end\n',
  0,
  b'st\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): list[integer] do\n'
  '    x = if n > 0 do\n'
  '      Enum.map([1, 2, 3], fn y ->\n'
  '        if y == 2 do\n'
  '          return 0\n'
  '        end\n'
  '        y\n'
  '      end)\n'
  '    else\n'
  '      []\n'
  '    end\n'
  '    x\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'[1, 0, 3]\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do\n'
  '    r = Enum.map([1, 2, 3], fn y ->\n'
  '      if y == 2 do\n'
  '        return 0\n'
  '      end\n'
  '      return y * 2\n'
  '    end)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 0, 6]\n',
  b''),
 ('defmodule Example do\n'
  '  def f({a, b}: tuple[integer, integer], limit: integer): string when a + b > limit do "over" end\n'
  '  def f({a, _}, limit) when a == limit do "edge" end\n'
  '  def f(_, _) do "under" end\n'
  '  def main() do IO.puts(f({3, 4}, 5) <> f({5, 0}, 5) <> f({1, 1}, 5)) end\n'
  'end\n',
  0,
  b'overedgeunder\n',
  b''),
 ('defmodule Example do\n'
  '  struct Opts do\n'
  '    depth: integer = 1\n'
  '    name: string\n'
  '  end\n'
  '  def show(%Opts{depth: 0, name: n}: Opts): string do n end\n'
  '  def show(%Opts{depth: d, name: n}) do n <> inspect(d) end\n'
  '  def main() do IO.puts(show(%Opts{name: "a", depth: 0}) <> show(%Opts{name: "b"})) end\n'
  'end\n',
  0,
  b'ab1\n',
  b''),
 ('defmodule Example do\n'
  '  def take(items: list[t], n: integer \\\\ 1): list[t] do Enum.take(items, n) end\n'
  '  def take(items: list[t], n: integer, pad: t): list[t] do\n'
  '    if length(items) >= n do Enum.take(items, n) else take(items ++ [pad], n, pad) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(take([1, 2, 3])) <> inspect(take(["a", "b"], 2)) <> inspect(take([1], 3, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1]["a", "b"][1, 0, 0]\n',
  b''),
 ('defmodule Example do\n'
  '  def size(a: integer): integer do a end\n'
  '  def size(a: integer, b: integer): integer do a + b end\n'
  '  def main() do\n'
  '    size = 5\n'
  '    IO.puts(inspect(size(size) + size(size, 1)))\n'
  '  end\n'
  'end\n',
  0,
  b'11\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): string when n > 0 and n < 10 or n == 100 do "in" end\n'
  '  def f(n) when not (n == 50) do "out" end\n'
  '  def f(_) do "fifty" end\n'
  '  def main() do IO.puts(f(5) <> f(100) <> f(11) <> f(50)) end\n'
  'end\n',
  0,
  b'ininoutfifty\n',
  b''),
 ('defmodule Example do\n'
  '  def op("add"): fn[integer, integer] do fn a -> a + 1 end end\n'
  '  def op(_) do fn a -> a end end\n'
  '  def main() do\n'
  '    f = op("add")\n'
  '    IO.puts(inspect(f(2)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def op("add", k: integer): fn[integer, integer] do fn a -> a + k end end\n'
  '  def op(_, _) do fn a -> a end end\n'
  '  def main() do\n'
  '    f = op("add", 1)\n'
  '    IO.puts(inspect(f(2)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def op("add", k: integer): fn[integer, integer, integer] do fn a, b -> a + k + b end end\n'
  '  def op(_, _) do fn a, b -> a end end\n'
  '  def main() do\n'
  '    f = op("add", 1)\n'
  '    IO.puts(inspect(f(2, 3)))\n'
  '  end\n'
  'end\n',
  0,
  b'6\n',
  b''),
 ('defmodule Example do\n'
  '  def op("add", k: integer, j: integer): fn[integer, integer] do fn a -> a + k end end\n'
  '  def op(_, _, _) do fn a -> a end end\n'
  '  def main() do\n'
  '    f = op("add", 1, 2)\n'
  '    IO.puts(inspect(f(2)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def op("add"): fn[integer, integer] do\n'
  '    g = fn(a: integer): integer do a + 1 end\n'
  '    g\n'
  '  end\n'
  '  def op(_) do fn(a: integer): integer do a end end\n'
  '  def main() do\n'
  '    f = op("add")\n'
  '    IO.puts(inspect(f(2)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def op(name: string): fn[integer, integer] when name == "add" do fn a -> a + 1 end end\n'
  '  def op(_) do fn a -> a end end\n'
  '  def main() do\n'
  '    f = op("add")\n'
  '    IO.puts(inspect(f(2)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def op("add"): fn[integer, integer] do &(&1 + 1) end\n'
  '  def op(_) do &(&1 * 2) end\n'
  '  def main() do\n'
  '    f = op("add")\n'
  '    IO.puts(inspect(f(2) + op("z")(5)))\n'
  '  end\n'
  'end\n',
  0,
  b'13\n',
  b''),
 ('defmodule Example do\n'
  '  def op(n: integer): fn[integer, integer] do\n'
  '    if n > 0 do\n'
  '      return fn a -> a + n end\n'
  '    end\n'
  '    fn a -> a end\n'
  '  end\n'
  '  def main() do\n'
  '    f = op(1)\n'
  '    IO.puts(inspect(f(2) + op(0)(5)))\n'
  '  end\n'
  'end\n',
  0,
  b'8\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ 1 + "a"): integer do a end\n'
  '  def main() do IO.puts(inspect(f(1, 2))) end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ "s"): integer do a end\n'
  '  def main() do IO.puts("x") end\n'
  'end\n',
  0,
  b'x\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: boolean \\\\ 1 in [1, 2]): boolean do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: string \\\\ "a\\\\\\\\b, c)"): string do b end\n'
  '  def main() do IO.puts(f(1)) end\n'
  'end\n',
  0,
  b'a\\\\b, c)\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: option[list[tuple[integer, string]]] \\\\ some([{1, "a"}, {2, "b"}])): string do '
  'inspect(b) end\n'
  '  def main() do IO.puts(f(1)) end\n'
  'end\n',
  0,
  b'some([{1, "a"}, {2, "b"}])\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: Range \\\\ 1..3): string do inspect(Enum.to_list(b)) end\n'
  '  def main() do IO.puts(f(1)) end\n'
  'end\n',
  0,
  b'[1, 2, 3]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: list[tuple[atom, integer]] \\\\ [x: 1, y: 2]): string do inspect(b) end\n'
  '  def main() do IO.puts(f(1)) end\n'
  'end\n',
  0,
  b'[x: 1, y: 2]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: string \\\\ "x#{1 + 1}y"): string do b end\n'
  '  def main() do IO.puts(f(1)) end\n'
  'end\n',
  0,
  b'x2y\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    if n > 0 do raise("a") else raise("b") end\n'
  '    1\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:17: a\n  at Example.f (<stdin>:3)\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    raise("a" <> inspect(n))\n'
  '    1\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: a1\n  at Example.f (<stdin>:3)\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    1 + raise("a")\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:9: a\n  at Example.f (<stdin>:3)\n  at Example.main (<stdin>:5)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): list[integer] do\n'
  '    [1, raise("a")]\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:9: a\n  at Example.f (<stdin>:3)\n  at Example.main (<stdin>:5)\n'),
 ('defmodule Example do\n'
  '  def g(a: integer, b: string): integer do a end\n'
  '  def f(n: integer): integer do\n'
  '    g(raise("x"), "s")\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:7: x\n  at Example.f (<stdin>:4)\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def main() do\n'
  '    IO.puts("before")\n'
  '    raise("in main")\n'
  '    IO.puts("after")\n'
  '  end\n'
  'end\n',
  2,
  b'before\n',
  b'<stdin>:4:5: in main\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    case n do\n'
  '      0 -> raise("zero")\n'
  '      1 -> return 5\n'
  '      _ -> n\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1) + f(2)))\n'
  '    IO.puts(inspect(f(0)))\n'
  '  end\n'
  'end\n',
  2,
  b'7\n',
  b'<stdin>:4:12: zero\n  at Example.f (<stdin>:4)\n  at Example.main (<stdin>:11)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    if n > 0 do return 1 else raise("b") end\n'
  '    1\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule Example do\n  def main() do\n    x: integer = raise("typed")\n    IO.puts(inspect(x))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:18: typed\n  at Example.main (<stdin>:3)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): string do\n'
  '    cond do\n'
  '      n > 0 -> "pos"\n'
  '      true -> raise("neg " <> inspect(n))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(f(1))\n'
  '    IO.puts(f(-3))\n'
  '  end\n'
  'end\n',
  2,
  b'pos\n',
  b'<stdin>:5:15: neg -3\n  at Example.f (<stdin>:5)\n  at Example.main (<stdin>:10)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): string do\n'
  '    raise("multi\\nline \\"q\\" é")\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(f(1))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: multi\nline "q" \xc3\xa9\n  at Example.f (<stdin>:3)\n  at Example.main (<stdin>:6)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    y = if n > 0 do n else raise("neg") end\n'
  '    raise("after #{y}")\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:5: after 1\n  at Example.f (<stdin>:4)\n  at Example.main (<stdin>:7)\n'),
 ('defmodule Example do\n'
  '  def f(none: option[integer]): integer do 0 end\n'
  '  def f(some(n)) do n end\n'
  '  def main() do IO.puts(inspect(f(some(3)) + f(none))) end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def f({a, b}: tuple[integer, integer], c: integer \\\\ 10): integer do a + b + c end\n'
  '  def main() do IO.puts(inspect(f({3, 4}) + f({1, 1}, 1))) end\n'
  'end\n',
  0,
  b'20\n',
  b''),
 ('defmodule Example do\n'
  '  struct P do\n'
  '    x: integer\n'
  '  end\n'
  '  def f(a: integer, b: P \\\\ %P{x: 1}): integer do a + b.x end\n'
  '  def main() do IO.puts(inspect(f(1, %P{x: 5}))) end\n'
  'end\n',
  0,
  b'6\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): string do "any" end\n'
  '  def main() do IO.puts(f(3)) end\n'
  '  def g(n: integer): string when n > 0 do "pos" end\n'
  '  def g(n) when n < 0 do "neg" end\n'
  '  def g(n) do "zero" end\n'
  'end\n',
  0,
  b'any\n',
  b''),
 ('defmodule Example do\n'
  '  def main() do IO.puts(inspect(f(3) + f(1, 1))) end\n'
  '  def f(0): integer do 0 end\n'
  '  def f(n: integer) do n + f(n - 1) end\n'
  '  def f(a: integer, b: integer): integer do a * b end\n'
  'end\n',
  0,
  b'7\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer when n > 100 do\n'
  '    return n / (n - 101)\n'
  '  end\n'
  '  def f(n) do\n'
  '    n\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1) + f(102)))\n'
  '    IO.puts(inspect(f(101)))\n'
  '  end\n'
  'end\n',
  2,
  b'103\n',
  b'<stdin>:3:14: division by zero\n  at Example.f (<stdin>:3)\n  at Example.main (<stdin>:10)\n'),
 ('defmodule Example do\n'
  '  def f(_: integer, 0): integer do 0 end\n'
  '  def f(a, _: integer) do a end\n'
  '  def main() do IO.puts(inspect(f(5, 0) + f(5, 1))) end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule Example do\n'
  '  def size(items: list[integer]): integer do length(items) end\n'
  '  def size(items: list[integer], extra: integer): integer do size(items) + extra end\n'
  '  def main() do\n'
  '    IO.puts(inspect([size([1, 2]), size([1], 10), [1, 2, 3] |> size(), [1] |> size(5)]))\n'
  '    IO.puts(inspect(Enum.map([[1], [1, 2]], &size/1)))\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 11, 3, 6]\n[1, 2]\n',
  b''),
 ('defmodule Example do\n'
  '  def add(a: integer, b: integer \\\\ 100): integer do a + b end\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.map([1, 2], &add(&1))))\n'
  '    IO.puts(inspect(Enum.map([1, 2], &add(&1, 1))))\n'
  '    IO.puts(inspect(Enum.map([1, 2], fn x -> add(x) end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[101, 102]\n[2, 3]\n[101, 102]\n',
  b''),
 ('defmodule Example do\n'
  '  def greet("", greeting: string \\\\ "hello"): string do greeting end\n'
  '  def greet(name: string, greeting) do "#{greeting}, #{name}" end\n'
  '  def main() do IO.puts(greet("") <> "|" <> greet("ada") <> "|" <> greet("bo", "hi")) end\n'
  'end\n',
  0,
  b'hello|hello, ada|hi, bo\n',
  b''),
 ('defmodule Example do\n'
  '  def classify([]: list[integer]): string do "empty" end\n'
  '  def classify([_]) do "one" end\n'
  '  def classify([a, b]) when a == b do "pair" end\n'
  '  def classify([_, _ | rest]) do "many+" <> inspect(length(rest)) end\n'
  '  def main() do IO.puts(classify([]) <> classify([1]) <> classify([2, 2]) <> classify([1, 2]) <> classify([1, 2, '
  '3, 4])) end\n'
  'end\n',
  0,
  b'emptyonepairmany+0many+2\n',
  b''),
 ('defmodule Example do\n'
  '  def show(n: integer): string do\n'
  '    "integer " <> Integer.to_string(n)\n'
  '  end\n'
  '  def show(""): string do\n'
  '    "empty"\n'
  '  end\n'
  '  def show(text: string): string do\n'
  '    "text " <> text\n'
  '  end\n'
  '  def area(side: integer): integer do\n'
  '    side * side\n'
  '  end\n'
  '  def area(sides: list[integer]): integer do\n'
  '    Enum.sum(sides)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(show(3) <> "|" <> show("") <> "|" <> show("x"))\n'
  '    IO.puts(inspect(area(3) + area([1, 2])))\n'
  '    IO.puts(inspect(Enum.map([1, 2], &show/1)))\n'
  '    IO.puts(inspect(Enum.map(["a", ""], &show/1)))\n'
  '    f: fn[integer, string] = &show/1\n'
  '    IO.puts(f(9))\n'
  '    IO.puts(3 |> show())\n'
  '    IO.puts("p" |> show())\n'
  '  end\n'
  'end\n',
  0,
  b'integer 3|empty|text x\n12\n["integer 1", "integer 2"]\n["text a", "empty"]\ninteger 9\ninteger 3\ntext p\n',
  b''),
 ('defmodule Example do\n'
  '  def conv(n: integer): string do inspect(n) end\n'
  '  def conv(s: string): integer do String.length(s) end\n'
  '  def conv(b: boolean): boolean do not b end\n'
  '  def main() do IO.puts(conv(conv("four")) <> inspect(conv(true))) end\n'
  'end\n',
  0,
  b'4false\n',
  b''),
 ('defmodule Example do\n'
  '  def size(text: string): integer do String.length(text) end\n'
  '  def size(items: list[integer]): integer do length(items) end\n'
  '  def size(text: string, extra: integer): integer do size(text) + extra end\n'
  '  def main() do IO.puts(inspect([size("abc"), size([1, 2]), size("abc", 10)])) end\n'
  'end\n',
  0,
  b'[3, 2, 13]\n',
  b''),
 ('defmodule Example do\n'
  '  def half(n: integer): integer do 10 / n end\n'
  '  def half(s: string): integer do\n'
  '    10 / String.length(s)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(half(5) + half("ab")))\n'
  '    IO.puts(inspect(half("")))\n'
  '  end\n'
  'end\n',
  2,
  b'7\n',
  b'<stdin>:4:8: division by zero\n  at Example.half#2 (<stdin>:4)\n  at Example.main (<stdin>:8)\n'),
 ('defmodule Example do\n'
  '  def first(items: list[t]): option[t] do\n'
  '    case items do\n'
  '      [] -> none\n'
  '      [x | _] -> some(x)\n'
  '    end\n'
  '  end\n'
  '  def first(text: string): option[string] do\n'
  '    if text == "" do none else some(String.slice(text, 0, 1)) end\n'
  '  end\n'
  '  def main() do IO.puts(inspect(first([1, 2])) <> inspect(first("hey")) <> inspect(first(["q"]))) end\n'
  'end\n',
  0,
  b'some(1)some("h")some("q")\n',
  b''),
 ('defmodule Example do\n'
  '  def run(f: fn[integer, integer], n: integer): integer do f(n) end\n'
  '  def run(f: fn[string, string], s: string): string do f(s) end\n'
  '  def main() do\n'
  '    IO.puts(inspect(run(fn x -> x + 1 end, 1)))\n'
  '    IO.puts(run(fn x -> x <> "!" end, "a"))\n'
  '  end\n'
  'end\n',
  0,
  b'2\na!\n',
  b''),
 ('defmodule Example do\n'
  '  struct Cat do\n'
  '    name: string\n'
  '  end\n'
  '  struct Dog do\n'
  '    name: string\n'
  '  end\n'
  '  def speak(c: Cat): string do c.name <> " meows" end\n'
  '  def speak(d: Dog): string do d.name <> " barks" end\n'
  '  def main() do IO.puts(speak(%Cat{name: "tom"}) <> ", " <> speak(%Dog{name: "rex"})) end\n'
  'end\n',
  0,
  b'tom meows, rex barks\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: list[integer], 0): integer do 0 end\n'
  '  def f(a: list[ integer ], n: integer) do length(a) + n end\n'
  '  def main() do IO.puts(inspect(f([1], 0) + f([1, 2], 3))) end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule Example do\n'
  '  def pad(s: string, n: integer \\\\ 3): string do String.duplicate(s, n) end\n'
  '  def pad(k: integer, n: integer): string do inspect(k * n) end\n'
  '  def main() do IO.puts(pad("a") <> pad("b", 2) <> pad(2, 4)) end\n'
  'end\n',
  0,
  b'aaabb8\n',
  b''),
 ('defmodule Example do\n'
  '  def sz(0): string do "zero" end\n'
  '  def sz(n: integer) when n > 9 do "big" end\n'
  '  def sz(_) do "small" end\n'
  '  def sz([]: list[integer]): integer do 0 end\n'
  '  def sz([_ | t]) do 1 + sz(t) end\n'
  '  def sz(s: string, n: integer): string do String.duplicate(s, n) end\n'
  '  def sz(a: integer, b: integer): integer do a * b end\n'
  '  def main() do\n'
  '    IO.puts(sz(0) <> sz(10) <> sz(3) <> inspect(sz([1, 2, 3])) <> sz("ab", 2) <> sz("c", 3) <> inspect(sz(6, '
  '7)))\n'
  '    IO.puts(inspect(Enum.map([[1], [1, 2]], &sz/1)) <> inspect(Enum.map([0, 50], &sz/1)))\n'
  '    g: fn[integer, integer, integer] = &sz/2\n'
  '    IO.puts(inspect(g(2, 3)))\n'
  '  end\n'
  'end\n',
  0,
  b'zerobigsmall3ababccc42\n[1, 2]["zero", "big"]\n6\n',
  b''),
 ('defmodule Example do\n'
  '  def pick(x: option[integer]): string do "option" end\n'
  '  def pick(x: list[integer]): string do "list" end\n'
  '  def main() do\n'
  '    IO.puts(pick(none) <> pick([]) <> pick(some(1)) <> pick([1]))\n'
  '  end\n'
  'end\n',
  0,
  b'optionlistoptionlist\n',
  b''),
 ('defmodule Example do\n'
  '  def twice(n: integer): integer do\n'
  '    if n == 0 do\n'
  '      return 0\n'
  '    end\n'
  '    n * 2\n'
  '  end\n'
  '  def twice(s: string): string do\n'
  '    if s == "" do\n'
  '      return "empty"\n'
  '    end\n'
  '    s <> s\n'
  '  end\n'
  '  def main() do IO.puts(inspect(twice(0) + twice(4)) <> twice("") <> twice("ab")) end\n'
  'end\n',
  0,
  b'8emptyabab\n',
  b''),
 ('defmodule Example do\n'
  '  def total([]: list[integer]): integer do 0 end\n'
  '  def total([h | t]) do h + total(t) end\n'
  '  def total(m: map[string, integer]): integer do total(Map.values(m)) end\n'
  '  def main() do IO.puts(inspect(total([1, 2]) + total(%{"a" => 10, "b" => 20}))) end\n'
  'end\n',
  0,
  b'33\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0, p: P): integer do 1 end\n'
  '  struct P do\n'
  '    x: integer\n'
  '  end\n'
  '  def f(n: integer, q) do n + q.x end\n'
  '  def main() do IO.puts(inspect(f(0, %P{x: 1}) + f(5, %P{x: 3}))) end\n'
  'end\n',
  0,
  b'9\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0): integer do 1 end\n'
  '  struct P do\n'
  '    x: integer\n'
  '  end\n'
  '  def f(n: integer) do n end\n'
  '  def main() do\n'
  '    p = %P{x: 3}\n'
  '    IO.puts(inspect(f(0) + f(5) + p.x))\n'
  '  end\n'
  'end\n',
  0,
  b'9\n',
  b''),
 ('defmodule Example do\n'
  '  struct P do\n'
  '    x: integer\n'
  '  end\n'
  '  def f(0, _: P): integer do 1 end\n'
  '  def f(n: integer, %P{x: x}) do n + x end\n'
  '  def main() do IO.puts(inspect(f(0, %P{x: 1}) + f(5, %P{x: 3}))) end\n'
  'end\n',
  0,
  b'9\n',
  b''),
 ('defmodule Example do\n'
  '  type Op do\n'
  '    add\n'
  '    neg\n'
  '  end\n'
  '  def run(Op.add, {a, b}: tuple[integer, integer]): integer do a + b end\n'
  '  def run(Op.neg: Op, {a, _}) do 0 - a end\n'
  '  def main() do IO.puts(inspect(run(Op.add, {1, 2}) + run(Op.neg, {5, 0}))) end\n'
  'end\n',
  0,
  b'-2\n',
  b''),
 ('defmodule Example do\n'
  '  struct P do\n'
  '    x: integer\n'
  '    y: integer\n'
  '  end\n'
  '  def f(p: P, 0): integer do p.x end\n'
  '  def f(%P{x: x, y: y}, n: integer) when n > 0 do x + y + n end\n'
  '  def f(_, _) do -1 end\n'
  '  def main() do IO.puts(inspect([f(%P{x: 1, y: 2}, 0), f(%P{x: 1, y: 2}, 3), f(%P{x: 1, y: 2}, -3)])) end\n'
  'end\n',
  0,
  b'[1, 6, -1]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer when n > 0 do 1 end\n'
  '  def f(n) when n > 0 do 2 end\n'
  '  def f(_) do 3 end\n'
  '  def main() do IO.puts(inspect(f(1) + f(-1))) end\n'
  'end\n',
  0,
  b'4\n',
  b''),
 ('defmodule Example do\n'
  '  defp step(0): integer do 0 end\n'
  '  defp step(n: integer) do n - 1 end\n'
  '  def main() do IO.puts(inspect(Enum.map([0, 5], &step/1))) end\n'
  'end\n',
  0,
  b'[0, 4]\n',
  b''),
 ('defmodule Example do\n'
  '  @unit 3\n'
  '  @name "u"\n'
  '  def scaled(a: integer, k: integer \\\\ @unit * 2, label: string \\\\ @name <> "!"): string do inspect(a * k) <> '
  'label end\n'
  '  def main() do IO.puts(scaled(2) <> scaled(2, 1) <> scaled(2, 1, "x")) end\n'
  'end\n',
  0,
  b'12u!2u!2x\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer): integer when a > b do\n'
  '    if a - b > 10 do\n'
  '      return 10\n'
  '    end\n'
  '    a - b\n'
  '  end\n'
  '  def f(a, b) when a == b do return 0 end\n'
  '  def f(a, b) do f(b, a) end\n'
  '  def main() do IO.puts(inspect([f(1, 50), f(3, 3), f(9, 2)])) end\n'
  'end\n',
  0,
  b'[10, 0, 7]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(items: list[integer]): integer do\n'
  '    g = fn(x: integer): integer do\n'
  '      h = fn(y: integer): integer do\n'
  '        if y > 1 do\n'
  '          return 100\n'
  '        end\n'
  '        y\n'
  '      end\n'
  '      if x == 0 do\n'
  '        return h(5)\n'
  '      end\n'
  '      h(x)\n'
  '    end\n'
  '    Enum.sum(Enum.map(items, g))\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f([0, 1, 2]))) end\n'
  'end\n',
  0,
  b'201\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0, _: option[integer]): integer do 0 end\n'
  '  def f(n: integer, o) do\n'
  '    v = case o do\n'
  '      some(x) -> x\n'
  '      none -> n\n'
  '    end\n'
  '    v * 2\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(0, none) + f(2, none) + f(2, some(5)))) end\n'
  'end\n',
  0,
  b'14\n',
  b''),
 ('defmodule Example do\n'
  '  def f(1): string do "one" end\n'
  '  def f(n: integer) do\n'
  '    """\n'
  '    n=#{n}\n'
  '    """\n'
  '  end\n'
  '  def main() do IO.write(f(1) <> f(2)) end\n'
  'end\n',
  0,
  b'onen=2\n',
  b''),
 ('defmodule Example do\n'
  '  def f("def f(x) do", n: integer): integer do n end\n'
  '  def f(s: string, n) when s == "when" do 0 - n end\n'
  '  def f(_, n) do n * 2 end\n'
  '  def main() do IO.puts(inspect([f("def f(x) do", 1), f("when", 1), f("end", 1)])) end\n'
  'end\n',
  0,
  b'[1, -1, 2]\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0): integer do 1 end\n'
  '  # the general case\n'
  '  @doc "more"\n'
  '  def f(n: integer) do n * f(n - 1) end\n'
  '  def main() do IO.puts(inspect(f(5))) end\n'
  'end\n',
  0,
  b'120\n',
  b''),
 ('defmodule Example do\n'
  '  def empty?([]: list[integer]): boolean do true end\n'
  '  def empty?(_) do false end\n'
  '  def first!([x | _]: list[integer]): integer do x end\n'
  '  def first!([]) do raise("empty") end\n'
  '  def main() do\n'
  '    IO.puts(inspect(empty?([])) <> inspect(empty?([1])) <> inspect(first!([7])))\n'
  '    IO.puts(inspect(first!([])))\n'
  '  end\n'
  'end\n',
  2,
  b'truefalse7\n',
  b'<stdin>:5:21: empty\n  at Example.first! (<stdin>:5)\n  at Example.main (<stdin>:8)\n'),
 ('defmodule Example do\n'
  '  def f(0): integer do 1 end\n'
  '  struct P do\n'
  '    x: integer\n'
  '  end\n'
  '  def f(n: integer) do n end\n'
  '  def main() do IO.puts(inspect(f(5))) end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule Example do\n'
  '  def f(a: integer \\\\ 1, b: integer \\\\ 2): integer do a * 10 + b end\n'
  '  def main() do IO.puts(inspect([f(), f(5), f(5, 6)])) end\n'
  'end\n',
  0,
  b'[12, 52, 56]\n',
  b''),
 ('defmodule Example do\n'
  '  def even?(0): boolean do true end\n'
  '  def even?(1) do false end\n'
  '  def even?(n: integer) do even?(n - 2) end\n'
  '  def label(n: integer): string when even?(n) do "even" end\n'
  '  def label(_) do "odd" end\n'
  '  def main() do IO.puts(label(10) <> label(7)) end\n'
  'end\n',
  0,
  b'evenodd\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    case n do\n'
  '      0 -> return 1\n'
  '      _ -> return 2\n'
  '    end\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(0) + f(5))) end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    case n do\n'
  '      0 -> raise("zero")\n'
  '      _ -> raise("other")\n'
  '    end\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(0))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:12: zero\n  at Example.f (<stdin>:4)\n  at Example.main (<stdin>:8)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    case n do\n'
  '      0 -> raise("zero")\n'
  '      _ -> raise("other")\n'
  '    end\n'
  '    3\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(0))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:12: zero\n  at Example.f (<stdin>:4)\n  at Example.main (<stdin>:9)\n'),
 ('defmodule Example do\n'
  '  def f(o: option[integer]): integer do\n'
  '    case o do\n'
  '      some(x) -> return x\n'
  '      none -> return 0\n'
  '    end\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(some(4)) + f(none))) end\n'
  'end\n',
  0,
  b'4\n',
  b''),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    cond do\n'
  '      n > 0 -> return 1\n'
  '      true -> return 2\n'
  '    end\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1) + f(-1))) end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0): integer do return 1 end\n'
  '  def f(n: integer) do return n end\n'
  '  def main() do IO.puts(inspect(f(0) + f(5))) end\n'
  'end\n',
  0,
  b'6\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0): integer do raise("z") end\n'
  '  def f(n: integer) do raise("n") end\n'
  '  def main() do IO.puts(inspect(f(0) + f(5))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:24: z\n  at Example.f (<stdin>:2)\n  at Example.main (<stdin>:4)\n'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    case n do\n'
  '      0 -> return 1\n'
  '      _ -> raise("x")\n'
  '    end\n'
  '    3\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(0))) end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule Example do\n'
  '  struct A do\n'
  '    v: integer\n'
  '  end\n'
  '  def show(a: A): string do "A" <> inspect(a.v) end\n'
  '  struct B do\n'
  '    v: string\n'
  '  end\n'
  '  type Kind do\n'
  '    one\n'
  '    two\n'
  '  end\n'
  '  def show(b: B): string do "B" <> b.v end\n'
  '  def show(Kind.one: Kind): string do "one" end\n'
  '  type Other do\n'
  '    x\n'
  '  end\n'
  '  def show(Kind.two) do "two" end\n'
  '  def main() do IO.puts(show(%A{v: 1}) <> show(%B{v: "b"}) <> show(Kind.one) <> show(Kind.two)) end\n'
  'end\n',
  0,
  b'A1Bbonetwo\n',
  b''),
 ('defmodule Example do\n'
  '  def f(0, _: P): integer do 1 end\n'
  '  struct P do\n'
  '    x: integer\n'
  '  end\n'
  '  def f(n: integer, %P{x: x}) do n + x end\n'
  '  def main() do IO.puts(inspect(f(0, %P{x: 1}) + f(5, %P{x: 3}))) end\n'
  'end\n',
  0,
  b'9\n',
  b''),
 ('defmodule Example do\n'
  '  def a(n: integer): integer do b(n) end\n'
  '  def b(0): integer do 10 / 0 end\n'
  '  struct P do\n'
  '    x: integer\n'
  '  end\n'
  '  def b(n: integer) do c(n) end\n'
  '  def c(n: integer): integer do b(n - 1) end\n'
  '  def main() do IO.puts(inspect(a(2))) end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:27: division by zero\n  at Example.b (<stdin>:3)\n  at Example.c (<stdin>:8)\n  at Example.b (<stdin>'
  b':7)\n  at Example.c (<stdin>:8)\n  at Example.b (<stdin>:7)\n  at Example.a (<stdin>:2)\n  at Example.main (<std'
  b'in>:9)\n')]
# (program, what the pinned compiler says of it): each is rejected
REJECTS=[('defmodule Example do\n'
  '  def f(0): integer do 1 end\n'
  '  def g(n: integer): integer do n end\n'
  '  def f(n: integer) do n end\n'
  '  def main() do IO.puts(inspect(f(1)+g(1))) end\n'
  'end\n',
  'unsupported syntax: clauses of f must be adjacent'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer when n > 0 do 1 end\n'
  '  def f(n: integer) when n <= 0 do 2 end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'non-exhaustive case: add a catch-all pattern'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do 1 end\n'
  '  def f(n: integer) when n <= 0 do 2 end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unreachable case branch'),
 ('defmodule Example do\n'
  '  def f(0): integer do 1 end\n'
  '  def f(n: integer): string do "x" end\n'
  '  def main() do IO.puts(inspect(f(0))) end\n'
  'end\n',
  'unsupported syntax: f returns integer in one clause and string in another'),
 ('defmodule Example do\n'
  '  def f(0): integer do 1 end\n'
  '  defp f(n: integer) do n end\n'
  '  def main() do IO.puts(inspect(f(3))) end\n'
  'end\n',
  'unsupported syntax: clauses of f must all be def or all be defp'),
 ('defmodule Example do\n'
  '  def f(0, b: integer): integer do b end\n'
  '  def f(n: integer, b: integer \\\\ 5) do n + b end\n'
  '  def main() do IO.puts(inspect(f(3))) end\n'
  'end\n',
  'wrong argument count for Example.f'),
 ('defmodule Example do\n'
  '  def f(a: integer \\\\ 1, b: integer): integer do a + b end\n'
  '  def main() do IO.puts(inspect(f(3,4))) end\n'
  'end\n',
  'unsupported syntax: a parameter without a default value cannot follow one that has it'),
 ('defmodule Example do\n'
  '  def g(): integer do 3 end\n'
  '  def f(a: integer, b: integer \\\\ g()): integer do a + b end\n'
  '  def main() do IO.puts(inspect(f(3))) end\n'
  'end\n',
  'unsupported syntax: a default value is a constant: literals, lists, tuples and maps of them, none, some(...), '
  'ok(...) or error(...)'),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ 1): integer do a + b end\n'
  '  def f(a: integer): integer do a end\n'
  '  def main() do IO.puts(inspect(f(3))) end\n'
  'end\n',
  'unsupported syntax: f/2 and f/1 both accept 1 arguments; a default argument overlaps another arity'),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer): integer do a + b end\n'
  '  def f(a: integer): integer do a end\n'
  '  def main() do IO.puts(inspect(Enum.map([1], &f))) end\n'
  'end\n',
  'unsupported syntax: f has more than one arity; write &f/2 or &f/1'),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ 1): integer do a + b end\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.map([1, 2], &f/1)))\n'
  '  end\n'
  'end\n',
  'f takes 2 arguments, not 1'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer when n > 0 do 1 end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'non-exhaustive case: add a catch-all pattern'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do 1 end\n'
  '  def f(0) do 2 end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unreachable case branch'),
 ('defmodule Example do\n  def main() do IO.puts("a") end\n  def main() do IO.puts("b") end\nend\n',
  'duplicate function "main"'),
 ('defmodule Example do\n'
  '  def f(n: integer) when n > 0: integer do 1 end\n'
  '  def f(_) do 2 end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unsupported syntax: expected identifier "do", found : ":"'),
 ('defmodule Example do\n'
  '  def f([], acc): integer do acc end\n'
  '  def f([h | t], acc) do f(t, acc + h) end\n'
  '  def main() do IO.puts(inspect(f([1, 2, 3], 0))) end\n'
  'end\n',
  'unsupported syntax: parameter 1 of f needs a type in one clause'),
 ('defmodule Example do\n'
  '  def f({a, b}: tuple[integer, integer], true): integer do a + b end\n'
  '  def main() do IO.puts(inspect(f({5, 1}, true))) end\n'
  'end\n',
  'non-exhaustive case: add a catch-all pattern'),
 ('defmodule Example do\n'
  '  def f(): integer do 1 end\n'
  '  def f() do 2 end\n'
  '  def main() do IO.puts(inspect(f())) end\n'
  'end\n',
  'duplicate function "Example.f"'),
 ('defmodule Example do\n'
  '  def len([]: list[t]): integer do 0 end\n'
  '  def len([_ | rest]) do 1 + len(rest) end\n'
  '  def first([]: list[t], fallback: t): t do fallback end\n'
  '  def first([x | _], _) do x end\n'
  '  def main() do\n'
  '    IO.puts(inspect(len([1, 2, 3]) + len(["a"])))\n'
  '    IO.puts(first([], "none") <> first(["a", "b"], "z"))\n'
  '    IO.puts(inspect(first([4], 0)))\n'
  '  end\n'
  'end\n',
  'empty list requires an expected list type'),
 ('defmodule Example do\n'
  '  def same(a: integer, a): boolean do true end\n'
  '  def same(_, _) do false end\n'
  '  def main() do IO.puts(inspect(same(1, 1))) end\n'
  'end\n',
  'unsupported syntax: parameter 2 of same needs a type in one clause'),
 ('defmodule Example do\n'
  '  def area(side: integer): integer do side * side end\n'
  '  def area(w: integer, h: integer): integer do w * h end\n'
  '  def main() do\n'
  '    IO.puts(inspect(area(3, 4, 5)))\n'
  '  end\n'
  'end\n',
  'unsupported syntax: area takes area/1 or area/2; no area/3 is defined'),
 ('defmodule Example do\n'
  '  type Shape do\n'
  '    circle(r: integer)\n'
  '    empty\n'
  '  end\n'
  '  def area(Shape.circle(r): Shape): integer do 3 * r * r end\n'
  '  def main() do\n'
  '    IO.puts(inspect(area(Shape.circle(2))))\n'
  '  end\n'
  'end\n',
  'non-exhaustive case: add a catch-all pattern'),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ length([1])): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unsupported syntax: a default value is a constant: literals, lists, tuples and maps of them, none, some(...), '
  'ok(...) or error(...)'),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ if true do 1 else 2 end): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unsupported syntax: a default value is a constant: literals, lists, tuples and maps of them, none, some(...), '
  'ok(...) or error(...)'),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ a): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unsupported syntax: a default value is a constant: literals, lists, tuples and maps of them, none, some(...), '
  'ok(...) or error(...)'),
 ('defmodule Example do\n'
  '  @k 5\n'
  '  def f(a: integer, b: integer \\\\ "x"): integer do b end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'expected integer, found string'),
 ('defmodule Example do\n'
  '  struct P do\n'
  '    x: integer\n'
  '  end\n'
  '  def f(a: integer, b: P \\\\ %P{x: 1}): integer do a + b.x end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unknown type "P"'),
 ('defmodule Example do\n  def main() when true do IO.puts("x") end\nend\n',
  'unsupported syntax: main needs a return type in one clause'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    return n + 1\n'
  '    n\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unreachable statement after return'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    x = if n > 0 do\n'
  '      return 100\n'
  '    else\n'
  '      2\n'
  '    end\n'
  '    x + 1\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1) + f(-1))) end\n'
  'end\n',
  'return cannot be used inside an if or case that produces a value'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    if n > 0 do\n'
  '      return "a"\n'
  '    end\n'
  '    2\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'expected integer, found string'),
 ('defmodule Example do\n  def main() do\n    IO.puts("a")\n    return 1\n  end\nend\n',
  'return type integer does not match void'),
 ('defmodule Example do\n  def main() do\n    IO.puts("a")\n    return\n  end\nend\n',
  'unsupported syntax: expected identifier "end", found EOF ""'),
 ('defmodule Example do\n'
  '  def main() do\n'
  '    f = fn x ->\n'
  '      if x > 0 do\n'
  '        return 1\n'
  '      end\n'
  '      2\n'
  '    end\n'
  '    IO.puts(inspect(f(1) + f(-1)))\n'
  '  end\n'
  'end\n',
  'cannot infer the parameter types of this function here; write fn(name: type): type do ... end, or pass it where a '
  'function type is expected'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    y = 1 + (if n > 0 do return 5 else 2 end)\n'
  '    y\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1) + f(-1))) end\n'
  'end\n',
  'return cannot be used inside an if or case that produces a value'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    if n > 10, do: return 1\n'
  '    unless n > 5 do\n'
  '      return 2\n'
  '    end\n'
  '    3\n'
  '  end\n'
  '  def main() do IO.puts(inspect([f(11), f(6), f(1)])) end\n'
  'end\n',
  'undefined binding return'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    return\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unsupported syntax: expected identifier "end", found EOF ""'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    return = n + 1\n'
  '    return\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unsupported syntax: expected expression, found "="'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    if n > 0 do\n'
  '      return 1\n'
  '    end\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'function "Example.f" must return on every path'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    total = 10 + if n > 0 do\n'
  '      if n > 5 do\n'
  '        return 99\n'
  '      end\n'
  '      1\n'
  '    else\n'
  '      2\n'
  '    end\n'
  '    total\n'
  '  end\n'
  '  def main() do IO.puts(inspect([f(1), f(9), f(-1)])) end\n'
  'end\n',
  'return cannot be used inside an if or case that produces a value'),
 ('defmodule Example do\n'
  '  def scale([]: list[integer], _: integer): list[integer] do [] end\n'
  '  def scale([h | t], k) when k > 0 do\n'
  '    f = fn x -> x * k + h end\n'
  '    [f(h) | scale(t, k)]\n'
  '  end\n'
  '  def scale(items, k) do\n'
  '    Enum.map(items, fn x -> x - k end)\n'
  '  end\n'
  '  def main() do IO.puts(inspect(scale([1, 2, 3], 2)) <> inspect(scale([1, 2], -1))) end\n'
  'end\n',
  'cannot infer the parameter types of this function here; write fn(name: type): type do ... end, or pass it where a '
  'function type is expected'),
 ('defmodule Example do\n'
  '  def length(a: integer, b: integer): integer do a + b end\n'
  '  def max(a: integer, b: integer, c: integer): integer do\n'
  '    if a > b do max(a, c) else max(b, c) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(length(1, 2)))\n'
  '    IO.puts(inspect(max(1, 5, 3)))\n'
  '    IO.puts(inspect(max(4, 2)))\n'
  '  end\n'
  'end\n',
  'wrong argument count for Example.max'),
 ('defmodule Example do\n'
  '  def f({some(x), [y | _]}: tuple[option[integer], list[integer]]): integer do x + y end\n'
  '  def f({none, [y, z | _]}) do y * z end\n'
  '  def f({some(x), []}) do x end\n'
  '  def f({none, []}) do -1 end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f({some(1), [2]})))\n'
  '  end\n'
  'end\n',
  'non-exhaustive case: add a catch-all pattern'),
 ('defmodule Example do\n'
  '  def f(0): string do "zero" end\n'
  '  def f(0) do "again" end\n'
  '  def f(n: integer) do inspect(n) end\n'
  '  def main() do IO.puts(f(0)) end\n'
  'end\n',
  'unreachable case branch'),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer, c: integer \\\\ 1): integer do a end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'wrong argument count for Example.f'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    if n > 0 do\n'
  '      return 1\n'
  '    else\n'
  '      return 2\n'
  '    end\n'
  '    3\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'unreachable statement after return'),
 ('defmodule Example do\n'
  '  def main() do\n'
  '    r = Enum.map([1, 2, 3], fn y ->\n'
  '      if y == 2 do\n'
  '        return "two"\n'
  '      end\n'
  '      y\n'
  '    end)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  'expected string, found integer'),
 ('defmodule Example do\n'
  '  def f(a: integer): string when a + 1 do "over" end\n'
  '  def f(_) do "under" end\n'
  '  def main() do IO.puts(f(1)) end\n'
  'end\n',
  'expected boolean, found integer'),
 ('defmodule Example do\n'
  '  def g(): integer do 1 end\n'
  '  def f(a: integer, b: integer \\\\ g()): integer do a end\n'
  '  def main() do IO.puts(inspect(f(1, 2))) end\n'
  'end\n',
  'unsupported syntax: a default value is a constant: literals, lists, tuples and maps of them, none, some(...), '
  'ok(...) or error(...)'),
 ('defmodule Example do\n'
  '  def f(a: integer, b: integer \\\\ zz): integer do a end\n'
  '  def main() do IO.puts(inspect(f(1, 2))) end\n'
  'end\n',
  'unsupported syntax: a default value is a constant: literals, lists, tuples and maps of them, none, some(...), '
  'ok(...) or error(...)'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    x = raise("a")\n'
  '    1\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1))) end\n'
  'end\n',
  'cannot infer the type this raise stands in for'),
 ('defmodule Example do\n  def main() do\n    raise(5)\n  end\nend\n', 'expected string, found integer'),
 ('defmodule Example do\n  def main() do\n    f = fn x -> raise("no #{x}") end\n    f(1)\n  end\nend\n',
  'cannot infer the parameter types of this function here; write fn(name: type): type do ... end, or pass it where a '
  'function type is expected'),
 ('defmodule Example do\n'
  '  def f({a, b}: tuple[integer, integer] \\\\ {1, 2}): integer do a + b end\n'
  '  def main() do IO.puts(inspect(f({3, 4}))) end\n'
  'end\n',
  'unsupported syntax: only a named parameter of a function can have a default value'),
 ('defmodule Example do\n'
  '  def f(a: integer, _: integer \\\\ 2): integer do a end\n'
  '  def main() do IO.puts(inspect(f(3))) end\n'
  'end\n',
  'unsupported syntax: only a named parameter of a function can have a default value'),
 ('defmodule Example do\n'
  '  def f(a: integer, b: string \\\\ "v#{a}"): string do b end\n'
  '  def main() do IO.puts(f(3, "x")) end\n'
  'end\n',
  'unsupported syntax: a default value is a constant: literals, lists, tuples and maps of them, none, some(...), '
  'ok(...) or error(...)'),
 ('defmodule Example do\n'
  '  def f([a, b]: list[integer]): integer do a + b end\n'
  '  def main() do IO.puts(inspect(f([1, 2]))) end\n'
  'end\n',
  'non-exhaustive case: add a catch-all pattern'),
 ('defmodule Example do\n'
  '  def f(true): string when 1 > 0 do "t" end\n'
  '  def f(false) do "f" end\n'
  '  def main() do IO.puts(f(true)) end\n'
  'end\n',
  'non-exhaustive case: add a catch-all pattern'),
 ('defmodule Example do\n'
  '  def show(n: integer): string do "i" end\n'
  '  def show(text: string): string do "s" end\n'
  '  def main() do IO.puts(show(true)) end\n'
  'end\n',
  'show takes (integer) or (string), not (boolean)'),
 ('defmodule Example do\n'
  '  def show(n: integer): string do "i" end\n'
  '  def show(text: string): string do "s" end\n'
  '  def show(m: integer): string do "again" end\n'
  '  def main() do IO.puts(show(1)) end\n'
  'end\n',
  'unsupported syntax: show is defined twice for (integer)'),
 ('defmodule Example do\n'
  '  def show(n: integer): string do "i" end\n'
  '  defp show(text: string): string do "s" end\n'
  '  def main() do IO.puts(show(1)) end\n'
  'end\n',
  'unsupported syntax: clauses of show must all be def or all be defp'),
 ('defmodule Example do\n'
  '  def join(a: string, b: string): string do a <> b end\n'
  '  def join(a: integer, b: integer): string do inspect(a + b) end\n'
  '  def join(a: string, n: integer): string do String.duplicate(a, n) end\n'
  '  def join(0, s: string) do "zero" <> s end\n'
  '  def join(n, s) do inspect(n) <> s end\n'
  '  def main() do IO.puts(join("a", "b") <> join(1, 2) <> join("z", 3) <> join(0, "!") <> join(7, "?")) end\n'
  'end\n',
  'unsupported syntax: join needs a return type in one clause'),
 ('defmodule Example do\n'
  '  def show(n: integer): string do "i" end\n'
  '  def show(""): string do "empty" end\n'
  '  def main() do IO.puts(show(1)) end\n'
  'end\n',
  'non-exhaustive case: add a catch-all pattern'),
 ('defmodule Example do\n'
  '  def show(n: integer): string do "i" end\n'
  '  def show(text: string): string do "s" end\n'
  '  def main() do\n'
  '    f = &show/1\n'
  '    IO.puts(f(1))\n'
  '  end\n'
  'end\n',
  'show is defined for arguments of several types, and a reference to it needs an expected function type: one of '
  '(integer) or (string)'),
 ('defmodule Example do\n'
  '  def tag(0): string do "zero" end\n'
  '  def tag("") do "empty" end\n'
  '  def tag(n: integer) do "int" end\n'
  '  def main() do IO.puts(tag(0)) end\n'
  'end\n',
  'unsupported syntax: tag needs a return type in one clause'),
 ('defmodule Example do\n'
  '  def keep(x: t): t do x end\n'
  '  def main() do IO.puts(inspect(Enum.map([1, 2], &keep/1))) end\n'
  'end\n',
  'reference to generic function Example.keep needs an expected function type'),
 ('defmodule Example do\n'
  '  def show(n: integer): string do "i" end\n'
  '  def other(): integer do 1 end\n'
  '  def show(text: string): string do "s" end\n'
  '  def main() do IO.puts(show(1)) end\n'
  'end\n',
  'unsupported syntax: clauses of show must be adjacent'),
 ('defmodule Example do\n'
  '  def f(): integer do 0 end\n'
  '  def f(a: integer \\\\ 1): integer do a end\n'
  '  def main() do IO.puts(inspect(f())) end\n'
  'end\n',
  'unsupported syntax: f/0 and f/1 both accept 0 arguments; a default argument overlaps another arity'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    case n do\n'
  '      0 -> return 1\n'
  '      _ -> return 2\n'
  '    end\n'
  '    3\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(0) + f(5))) end\n'
  'end\n',
  'unreachable statement after return'),
 ('defmodule Example do\n'
  '  def f(n: integer): integer do\n'
  '    cond do\n'
  '      n > 0 -> return 1\n'
  '      true -> return 2\n'
  '    end\n'
  '    7\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(1) + f(-1))) end\n'
  'end\n',
  'unreachable statement after return'),
 ('defmodule Example do\n'
  '  def f(o: option[integer]): integer do\n'
  '    case o do\n'
  '      some(x) -> return x\n'
  '      none -> return 0\n'
  '    end\n'
  '    9\n'
  '  end\n'
  '  def main() do IO.puts(inspect(f(some(4)) + f(none))) end\n'
  'end\n',
  'unreachable statement after return'),
 ('defmodule Example do\n'
  '  def f(0): integer do 1 end\n'
  '  struct P do\n'
  '    x: integer\n'
  '  end\n'
  '  def g(n: integer): integer do n end\n'
  '  def f(n: integer) do n end\n'
  '  def main() do IO.puts(inspect(f(5))) end\n'
  'end\n',
  'unsupported syntax: clauses of f must be adjacent')]
# A library of arities, defaults, clauses and a generic clause function, used
# from another module. Outcomes are the pinned `alchem run` on the same files.
SHAPES=('defmodule Shapes do\n'
 '  def area(side: integer): integer do side * side end\n'
 '  def area(w: integer, h: integer): integer do w * h end\n'
 '  defp area(a: integer, b: integer, c: integer): integer do a + b + c end\n'
 '  def perimeter(a: integer, b: integer \\\\ 0, c: integer \\\\ 10 / 2): integer do a + b + c + area(1, 1, 1) end\n'
 '  def kind(0): string do "none" end\n'
 '  def kind(n: integer) when n < 0 do raise("negative size") end\n'
 '  def kind(_) do "some" end\n'
 '  defp hidden(0): integer do 0 end\n'
 '  defp hidden(n: integer) do n end\n'
 '  def show(n: integer): integer do hidden(n) end\n'
 '  def len([]: list[t]): integer do 0 end\n'
 '  def len([_ | rest]) do 1 + len(rest) end\n'
 'end\n')


def app(body):
    return 'defmodule App do\n  import "shapes.alc"\n'+''.join(f'{line}\n' for line in body)+'end\n'


# (app.alc, status, standard output, standard error with the directory as {base})
PROJECTS=[
    (app(['  def area(x: integer): integer do x end','  def main() do',
          '    IO.puts(inspect([Shapes.area(3), Shapes.area(2, 5), area(7)]))',
          '    IO.puts(inspect([Shapes.perimeter(1), Shapes.perimeter(1, 2), Shapes.perimeter(1, 2, 3)]))',
          '    IO.puts(Shapes.kind(0) <> Shapes.kind(4))',
          '    IO.puts(inspect(Enum.map([1, 2], &Shapes.area/1)))',
          '    IO.puts(inspect(Enum.reduce([1, 2, 3], 1, &Shapes.area/2)))',
          '    IO.puts(inspect(Enum.map([0, 2], &Shapes.kind/1)))',
          '    IO.puts(inspect(Shapes.len(["a", "b"]) + Shapes.len([1])))',
          '    IO.puts(inspect(3 |> Shapes.area() |> Shapes.area(2) |> Shapes.perimeter()))',
          '    IO.puts(Shapes.kind(-1))','  end']),
     2,b'[9, 10, 7]\n[9, 11, 9]\nnonesome\n[1, 4]\n6\n["none", "some"]\n3\n26\n',
     '{base}/shapes.alc:7:38: negative size\n  at Shapes.kind ({base}/shapes.alc:7)\n  at App.main ({base}/app.alc:13)\n'),
    (app(['  def main() do','    IO.puts(inspect(Shapes.show(4)))','    IO.puts(inspect(Shapes.perimeter(1,','       2)))','  end']),0,b'4\n11\n',''),
]
# (app.alc, what the pinned compiler says of it)
PROJECT_REJECTS=[
    (app(['  def main() do','    IO.puts(inspect(Shapes.area(1, 2, 3)))','  end']),'Shapes.area is private to its module'),
    (app(['  def main() do','    IO.puts(inspect(Shapes.hidden(1)))','  end']),'Shapes.hidden is private to its module'),
    (app(['  def main() do','    IO.puts(inspect(Enum.map([1], &Shapes.area)))','  end']),'Shapes.area has more than one arity; write &Shapes.area/1 or &Shapes.area/2 or &Shapes.area/3'),
    (app(['  def main() do','    f = &Shapes.area/3','    IO.puts(inspect(f(1, 2, 3)))','  end']),'Shapes.area is private to its module'),
    (app(['  def main() do','    IO.puts(inspect(Shapes.perimeter()))','  end']),'wrong argument count for Shapes.perimeter'),
]


def verify(compiler):
    def compiled(source):
        return subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
    with tempfile.TemporaryDirectory(prefix='alchem-clauses-') as d:
        base=Path(d);out=base/'out'
        def run(source,label):
            result=compiled(source)
            assert (result.returncode,result.stderr)==(0,b''),(label,result.returncode,result.stderr)
            out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            return subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        for source,status,stdout,stderr in RUNS:
            done=run(source.encode(),source)
            assert (done.returncode,done.stdout,done.stderr)==(status,stdout,stderr),(source,done)
        for source,reason in REJECTS:
            result=compiled(source.encode())
            assert (result.returncode,result.stdout)==(65,b''),(source,reason,result.returncode)
        def project(index,text):
            root=base/f'project{index}';root.mkdir()
            (root/'app.alc').write_text(text);(root/'shapes.alc').write_text(SHAPES)
            return root,bundler.bundle(root/'app.alc')
        for index,(text,status,stdout,stderr) in enumerate(PROJECTS):
            root,bundle=project(index,text)
            done=run(bundle,('project',index))
            assert (done.returncode,done.stdout,done.stderr)==(status,stdout,stderr.replace('{base}',str(root)).encode()),('project',index,done)
        for index,(text,reason) in enumerate(PROJECT_REJECTS):
            result=compiled(project(len(PROJECTS)+index,text)[1])
            assert (result.returncode,result.stdout)==(65,b''),(reason,result.returncode)
        # A function of 300 clauses: one row per clause in the exhaustiveness matrix.
        many='defmodule Example do\n'+''.join(f'  def f({i}){": string" if i==0 else ""} do "{i}" end\n' for i in range(300))+'  def f(n: integer) do "big" end\n  def main() do IO.puts(f(0) <> f(150) <> f(299) <> f(300)) end\nend\n'
        done=run(many.encode(),'300 clauses')
        assert (done.returncode,done.stdout,done.stderr)==(0,b'0150299big\n',b''),('300 clauses',done)
    print(f'PASS clauses: {len(RUNS)+len(PROJECTS)+1} programs run as the pinned compiler runs them, {len(REJECTS)+len(PROJECT_REJECTS)} rejected; '
          'arities of one name, default arguments, clauses with patterns and guards, forms by parameter type, return, raise, calls and references from another module')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
