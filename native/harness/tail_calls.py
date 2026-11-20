#!/usr/bin/env python3
"""Tail calls: a function's call to itself in return position runs as a loop, as the pinned compiler has it.

Every program runs as the pinned compiler runs it (status, output and, for a
failure, the trace). In order: calls that loop (the last expression of an if,
unless, case, cond or with that is a statement, of a clause, an explicit
return, in parentheses, the last call of a pipeline, by the module's name,
with defaults, more than six parameters, closures made in a turn); calls that
do not (a value used further, a form used as a value, a fn, a for, a try, two
functions, another form of the name, a generic function, no parameters) and
so stop at 100000 calls where they go that deep; failures inside a loop and
the depth a loop is counted as; and the library written in Alchem, whose
functions are no calls of the program (a search of the regex matcher, a
program that recurses through Enum functions exactly as deep as the pinned
runtime lets it). The programs spec/alchem-tail-calls.md describes.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
from native_memory import floor_arena

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[# case
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    case n do\n'
  '      0 -> acc\n'
  '      _ -> loop(n - 1, acc + n)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # cond
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    cond do\n'
  '      n == 0 -> acc\n'
  '      n == 1 -> loop(n - 1, acc + 1)\n'
  '      true -> loop(n - 1, acc + n)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # unless
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    unless n == 0 do loop(n - 1, acc + n) else acc end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # oneline
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0, do: acc, else: loop(n - 1, acc + n)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # o1
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    unless n > 0, do: acc, else: loop(n - 1, acc + n)\n'
  '  end\n'
  '  def w(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else\n'
  '      if n > 5, do: w(n - 1, acc + n)\n'
  '      w(n - 1, acc)\n'
  '    end\n'
  '  end\n'
  '  def c(n: integer, acc: integer): integer do\n'
  '    x = if n == 0, do: acc, else: c(n - 1, acc + n)\n'
  '    x\n'
  '  end\n'
  '  def d(n: integer, acc: integer): integer do\n'
  '    if n > 0, do: d(n - 1, acc + n), else: acc\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '    IO.puts(Integer.to_string(d(300000, 0)))\n'
  '    IO.puts(Integer.to_string(w(300000, 0)))\n'
  '    IO.puts(Integer.to_string(c(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'45000150000\n45000150000\n',
  b'<stdin>:5:7: call depth exceeded\n'+b'  at M.w (<stdin>:7)\n'*61),
 # with
 ('defmodule M do\n'
  '  def step(n: integer): result[integer, string] do\n'
  '    if n == 0 do error("done") else ok(n - 1) end\n'
  '  end\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    with ok(m) <- step(n) do\n'
  '      loop(m, acc + n)\n'
  '    else\n'
  '      error(_) -> acc\n'
  '    end\n'
  '  end\n'
  '  def loop2(n: integer, acc: integer): integer do\n'
  '    with ok(m) <- step(n) do\n'
  '      acc + m\n'
  '    else\n'
  '      error(_) -> loop2(n + 1, acc)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '    IO.puts(Integer.to_string(loop2(0, 5)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n5\n',
  b''),
 # withplain
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else\n'
  '      with {a, b} <- {n - 1, acc + n} do\n'
  '        loop(a, b)\n'
  '      end\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # w1
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    with {a, b} <- {n - 1, acc + n} do\n'
  '      if a == 0 do b else loop(a, b) end\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # w2
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else\n'
  '      with {a, b} <- {n - 1, acc + n} do\n'
  '        loop(a, b)\n'
  '      else\n'
  '        _ -> 0\n'
  '      end\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # w3
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else\n'
  '      with {a, b} <- {n - 1, acc + n} do\n'
  '        if a == 0 do b else loop(a, b) end\n'
  '      end\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # w4
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    with m <- n - 1 do\n'
  '      if m == 0 do acc else loop(m, acc + m) end\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'44999850000\n',
  b''),
 # w5
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    with {a, b} <- {n - 1, acc + n} do\n'
  '      if a == 0 do\n'
  '        return b\n'
  '      end\n'
  '      return loop(a, b)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # w6
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    {a, b} = {n - 1, acc + n}\n'
  '    if a == 0 do b else loop(a, b) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # w7
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    case {n - 1, acc + n} do\n'
  '      {0, b} -> b\n'
  '      {a, b} -> loop(a, b)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # clauses
 ('defmodule M do\n'
  '  def loop(0, acc: integer): integer do acc end\n'
  '  def loop(n: integer, acc: integer): integer do loop(n - 1, acc + n) end\n'
  '  def len([], acc: integer): integer do acc end\n'
  '  def len([_ | rest]: list[integer], acc: integer): integer do len(rest, acc + 1) end\n'
  '  def g(n: integer, acc: integer): integer when n > 0 do g(n - 1, acc + 2) end\n'
  '  def g(n: integer, acc: integer): integer do acc end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '    IO.puts(Integer.to_string(g(300000, 0)))\n'
  '    IO.puts(Integer.to_string(len(Enum.to_list(1..2000), 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n600000\n2000\n',
  b''),
 # caseguard
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    case {n, acc} do\n'
  '      {0, a} -> a\n'
  '      {m, a} when m > 100 ->\n'
  '        cond do\n'
  '          a > 5 -> loop(m - 1, a + 1)\n'
  '          true -> loop(m - 1, a + 2)\n'
  '        end\n'
  '      {m, a} -> loop(m - 1, a)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'299903\n',
  b''),
 # nested
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    y = n * 2\n'
  '    if n == 0 do acc else\n'
  '      case y do\n'
  '        2 -> loop(n - 1, acc + 100)\n'
  '        _ ->\n'
  '          z = acc + n\n'
  '          if z > 5 do loop(n - 1, z) else loop(n - 1, z + 1) end\n'
  '      end\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150099\n',
  b''),
 # ret
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n > 0 do\n'
  '      return loop(n - 1, acc + n)\n'
  '    end\n'
  '    acc\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # retdeep
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    case n do\n'
  '      0 -> return acc\n'
  '      _ ->\n'
  '        if n > 5 do\n'
  '          return loop(n - 1, acc + n)\n'
  '        end\n'
  '    end\n'
  '    loop(n - 1, acc + 1)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000149990\n',
  b''),
 # midret
 ('defmodule M do\n'
  '  def f(n: integer, acc: integer): integer do\n'
  '    if n > 0 do\n'
  '      if n > 5 do\n'
  '        return f(n - 1, acc + 2)\n'
  '      else\n'
  '        IO.puts("low")\n'
  '      end\n'
  '      return f(n - 1, acc + 1)\n'
  '    end\n'
  '    acc\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'low\nlow\nlow\nlow\nlow\n599995\n',
  b''),
 # paren
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else (loop(n - 1, acc + n)) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # retparen
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else return (loop(n - 1, acc + n)) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # pipe
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else n - 1 |> loop(acc + n) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # pipe2
 ('defmodule M do\n'
  '  def dec(n: integer): integer do n - 1 end\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else n |> dec() |> loop(acc + n) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # pipe3
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else n - 1 |> M.loop(acc + n) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # qualified
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else M.loop(n - 1, acc + n) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # private
 ('defmodule M do\n'
  '  defp loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else loop(n - 1, acc + n) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # default
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer \\\\ 0): integer do\n'
  '    if n == 0 do acc else loop(n - 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000)))\n'
  '  end\n'
  'end\n',
  0,
  b'0\n',
  b''),
 # default2
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer \\\\ 0): integer do\n'
  '    if n == 0 do acc else loop(n - 1, acc + 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000)))\n'
  '  end\n'
  'end\n',
  0,
  b'300000\n',
  b''),
 # defmid
 ('defmodule M do\n'
  '  def loop(n: integer, step: integer \\\\ 2, acc: integer \\\\ 0): integer do\n'
  '    if n <= 0 do acc else loop(n - step, step) end\n'
  '  end\n'
  '  def loop2(n: integer, step: integer \\\\ 2, acc: integer \\\\ 0): integer do\n'
  '    if n <= 0 do acc else loop2(n - step) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(600000)))\n'
  '    IO.puts(Integer.to_string(loop2(600000, 1, 7)))\n'
  '  end\n'
  'end\n',
  0,
  b'0\n0\n',
  b''),
 # arity
 ('defmodule M do\n'
  '  def loop(n: integer): integer do loop(n, 0) end\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else loop(n - 1, acc + n) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # forms2
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else loop(n - 1, acc + n) end\n'
  '  end\n'
  '  def loop(s: string, acc: integer): integer do\n'
  '    if acc > 300000 do acc else loop(s, acc + 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '    IO.puts(Integer.to_string(loop("a", 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n300001\n',
  b''),
 # swap
 ('defmodule M do\n'
  '  def loop(n: integer, a: integer, b: integer): integer do\n'
  '    if n == 0 do a * 3 + b else loop(n - 1, b, a + 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300001, 1, 20)))\n'
  '  end\n'
  'end\n',
  0,
  b'600062\n',
  b''),
 # seven
 ('defmodule M do\n'
  '  def loop(n: integer, a: integer, b: integer, c: integer, d: integer, e: integer, f: integer): integer do\n'
  '    if n == 0 do a + b * 2 + c * 3 + d * 4 + e * 5 + f * 6 else loop(n - 1, f, a, b, c, d, e) end\n'
  '  end\n'
  '  def six(n: integer, a: integer, b: integer, c: integer, d: integer, e: integer): integer do\n'
  '    if n == 0 do a + b * 2 + c * 3 + d * 4 + e * 5 else six(n - 1, e, a, b, c, d) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300001, 1, 2, 3, 4, 5, 6)))\n'
  '    IO.puts(Integer.to_string(six(300001, 1, 2, 3, 4, 5)))\n'
  '  end\n'
  'end\n',
  0,
  b'76\n45\n',
  b''),
 # many
 ('defmodule M do\n'
  '  def loop(n: integer, a: integer, b: integer, c: integer, d: integer, e: integer, f: integer, g: integer, h: integer): integer do\n'
  '    if n == 0 do a + b * 2 + c * 3 + d * 4 + e * 5 + f * 6 + g * 7 + h * 8 else loop(n - 1, h, a, b, c, d, e, f, g + 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 1, 2, 3, 4, 5, 6, 7, 8)))\n'
  '  end\n'
  'end\n',
  0,
  b'1350204\n',
  b''),
 # nine
 ('defmodule M do\n'
  '  def loop(n: integer, a: string, b: integer, c: list[integer], d: integer, e: integer, f: integer, g: integer, h: string): string do\n'
  '    if n == 0 do a <> h <> Integer.to_string(b + d + e + f + g + Enum.count(c)) else loop(n - 1, h, g, c, b, d, e, f + 1, a) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(loop(300001, "x", 2, [3], 4, 5, 6, 7, "y"))\n'
  '  end\n'
  'end\n',
  0,
  b'yx300026\n',
  b''),
 # closure
 ('defmodule M do\n'
  '  def loop(n: integer, fs: list[fn[integer, integer]]): list[fn[integer, integer]] do\n'
  '    if n == 0 do fs else\n'
  '      g = fn(x: integer): integer do x + n * 10 end\n'
  '      loop(n - 1, [g | fs])\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    fs = loop(5, [])\n'
  '    IO.puts(Enum.join(Enum.map(fs, fn f -> Integer.to_string(f.(1)) end), ","))\n'
  '  end\n'
  'end\n',
  0,
  b'11,21,31,41,51\n',
  b''),
 # float
 ('defmodule M do\n'
  '  def loop(n: integer, acc: float): float do\n'
  '    if n == 0 do acc else loop(n - 1, acc + 0.5) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Float.to_string(loop(300000, 0.0)))\n'
  '  end\n'
  'end\n',
  0,
  b'1.5e5\n',
  b''),
 # strloop
 ('defmodule M do\n'
  '  def count(s: string, n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else count(s, n - 1, acc + String.length(s)) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(count("héllo", 1000000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'5000000\n',
  b''),
 # struct
 ('defmodule M do\n'
  '  def loop(n: integer, acc: tuple[integer, string], xs: list[integer]): tuple[integer, string] do\n'
  '    {a, s} = acc\n'
  '    case xs do\n'
  '      [] -> acc\n'
  '      [h | t] -> loop(n + 1, {a + h, "x"}, t)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    {a, s} = loop(0, {0, ""}, Enum.to_list(1..2000))\n'
  '    IO.puts(Integer.to_string(a))\n'
  '  end\n'
  'end\n',
  0,
  b'2001000\n',
  b''),
 # structparam
 ('defmodule M do\n'
  '  struct P do\n'
  '    x: integer\n'
  '    y: integer\n'
  '  end\n'
  '  def walk(p: P): integer do\n'
  '    case p do\n'
  '      %P{x: 0, y: y} -> y\n'
  '      %P{x: x, y: y} -> walk(%P{x: x - 1, y: y + 2})\n'
  '    end\n'
  '  end\n'
  '  def tup({0, acc}: tuple[integer, integer]): integer do acc end\n'
  '  def tup({n, acc}: tuple[integer, integer]): integer do tup({n - 1, acc + 3}) end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(tup({300000, 0})))\n'
  '    IO.puts(Integer.to_string(walk(%P{x: 300000, y: 1})))\n'
  '  end\n'
  'end\n',
  0,
  b'900000\n600001\n',
  b''),
 # tenmillion
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else loop(n - 1, acc + n) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(10000000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'50000005000000\n',
  b''),
 # bound
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else\n'
  '      x = loop(n - 1, acc + n)\n'
  '      x\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'+b'  at M.loop (<stdin>:4)\n'*61),
 # valueif
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    x = 1\n'
  '    (if n == 0 do acc else loop(n - 1, acc + n) end)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:4)\n'),
 # withval
 ('defmodule M do\n'
  '  def f(n: integer, acc: integer): integer do\n'
  '    x = with {a, b} <- {n, acc} do\n'
  '      if a == 0 do b else f(a - 1, b + 1) end\n'
  '    end\n'
  '    x\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'
  b'  at M.f (<stdin>:3)\n'
  b'  at M.f <closure> (<stdin>:4)\n'),
 # lambda
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    f = fn(m: integer): integer do if m == 0 do acc else loop(m - 1, acc + m) end end\n'
  '    f.(n)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.loop <closure> (<stdin>:3)\n'),
 # capture
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else\n'
  '      f = &loop/2\n'
  '      f.(n - 1, acc + n)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'+b'  at M.loop (<stdin>:5)\n'*61),
 # try
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    try do\n'
  '      if n == 0 do acc else loop(n - 1, acc + n) end\n'
  '    rescue\n'
  '      e -> 0 - 1\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'-1\n',
  b''),
 # mutual
 ('defmodule M do\n'
  '  def a(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else b(n - 1, acc + n) end\n'
  '  end\n'
  '  def b(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else a(n - 1, acc + n) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(a(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'
  b'  at M.a (<stdin>:3)\n'
  b'  at M.b (<stdin>:6)\n'),
 # forms
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else loop(Integer.to_string(n - 1), acc + n) end\n'
  '  end\n'
  '  def loop(s: string, acc: integer): integer do\n'
  '    loop(String.to_integer(s), acc)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'
  b'  at M.loop (<stdin>:3)\n'
  b'  at M.loop#2 (<stdin>:6)\n'),
 # generic
 ('defmodule M do\n'
  '  def loop(n: integer, acc: a): a do\n'
  '    if n == 0 do acc else loop(n - 1, acc) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'+b'  at M.loop (<stdin>:3)\n'*61),
 # zero
 ('defmodule M do\n'
  '  def loop(): integer do\n'
  '    loop()\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop()))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'+b'  at M.loop (<stdin>:3)\n'*61),
 # orr
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): boolean do\n'
  '    n == 0 or loop(n - 1, acc + n)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'+b'  at M.loop (<stdin>:3)\n'*61),
 # orpipe
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): boolean do\n'
  '    n == 0 or n - 1 |> loop(acc + n)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:2:7: call depth exceeded\n'+b'  at M.loop (<stdin>:3)\n'*61),
 # notpipe
 ('defmodule M do\n'
  '  def loop(b: boolean, n: integer): boolean do\n'
  '    if n == 0 do b else not b |> loop(n - 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(true, 300001)))\n'
  '  end\n'
  'end\n',
  0,
  b'false\n',
  b''),
 # dropped
 ('defmodule M do\n'
  '  def f(n: integer, acc: integer): integer do\n'
  '    if n > 0 do\n'
  '      f(n - 1, acc + 1)\n'
  '    end\n'
  '    acc\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(20, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'0\n',
  b''),
 # shadow
 ('defmodule M do\n'
  '  def f(n: integer, acc: integer): integer do\n'
  '    f = fn(a: integer, b: integer): integer do a + b end\n'
  '    if n == 0 do acc else f(n - 1, acc + 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(30, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'30\n',
  b''),
 # foreffect
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else\n'
  '      for i <- [1] do\n'
  '        if i == 1 do\n'
  '          loop(0, i)\n'
  '        end\n'
  '      end\n'
  '      loop(n - 1, acc + n)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(300000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'45000150000\n',
  b''),
 # depthafter
 ('defmodule M do\n'
  '  def deep(n: integer): integer do\n'
  '    if n == 0 do 0 else 1 + deep(n - 1) end\n'
  '  end\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do deep(acc) else loop(n - 1, acc + 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(99998, 0)))\n'
  '    IO.puts(Integer.to_string(loop(99999, 0)))\n'
  '    IO.puts(Integer.to_string(loop(100000, 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'99998\n',
  b'<stdin>:2:7: call depth exceeded\n'+b'  at M.deep (<stdin>:3)\n'*61),
 # deepmix
 ('defmodule M do\n'
  '  def spin(n: integer, k: integer): integer do\n'
  '    if n == 0 do down(k) else spin(n - 1, k) end\n'
  '  end\n'
  '  def down(k: integer): integer do\n'
  '    if k == 0 do 0 else 1 + spin(3, k - 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(down(49999)))\n'
  '    IO.puts(Integer.to_string(down(50000)))\n'
  '    IO.puts(Integer.to_string(down(50001)))\n'
  '  end\n'
  'end\n',
  2,
  b'49999\n',
  b'<stdin>:5:7: call depth exceeded\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'
  b'  at M.down (<stdin>:6)\n'
  b'  at M.spin (<stdin>:3)\n'),
 # fail
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    x = acc + 1\n'
  '    if n == 0 do\n'
  '      [a, b] = [x]\n'
  '      a\n'
  '    else\n'
  '      loop(n - 1, x)\n'
  '    end\n'
  '  end\n'
  '  def outer(n: integer): integer do\n'
  '    loop(n, 0) + 1\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(outer(1000000)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:5:7: pattern match failed\n'
  b'  at M.loop (<stdin>:5)\n'
  b'  at M.outer (<stdin>:12)\n'
  b'  at M.main (<stdin>:15)\n'),
 # failclause
 ('defmodule M do\n'
  '  def loop([], acc: integer): integer do acc end\n'
  '  def loop([h | t]: list[integer], acc: integer): integer do\n'
  '    y = 100 / (h - 2999)\n'
  '    loop(t, acc + y)\n'
  '  end\n'
  '  def run(n: integer): integer do\n'
  '    x = loop(Enum.to_list(1..n), 0)\n'
  '    x\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(run(3000)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:13: division by zero\n'
  b'  at M.loop (<stdin>:4)\n'
  b'  at M.run (<stdin>:8)\n'
  b'  at M.main (<stdin>:12)\n'),
 # overflow
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else\n'
  '      loop(n - 1,\n'
  '        acc * 3)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(1000000, 1)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:5:13: integer overflow\n  at M.loop (<stdin>:4)\n  at M.main (<stdin>:9)\n'),
 # argfail
 ('defmodule M do\n'
  '  def loop(n: integer, a: integer, b: integer, c: integer, d: integer, e: integer, f: integer, g: integer): integer do\n'
  '    if n == 0 do a else\n'
  '      loop(n - 1, b, c, d, e, f, g,\n'
  '        100 / n - 1)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(1000, 1, 2, 3, 4, 5, 6, 7)))\n'
  '    IO.puts(Integer.to_string(loop(1000, 1, 2, 3, 4, 5, 6, 0 / (7 - 7))))\n'
  '  end\n'
  'end\n',
  2,
  b'13\n',
  b'<stdin>:10:62: division by zero\n  at M.main (<stdin>:10)\n'),
 # fmtloop
 ('defmodule M do\n'
  '  def loop(n: integer, acc: integer): integer do\n'
  '    if n == 0 do acc else\n'
  '      s = "item " <> Integer.to_string(n) <> ": " <> String.pad_leading(Integer.to_string(acc), 12, "0")\n'
  '      loop(n - 1, acc + String.length(s))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(loop(100000, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'2388895\n',
  b''),
 # regexdeep
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Regex.match?(~r/^(?:ab)*c$/, String.duplicate("ab", 30000) <> "c")))\n'
  '    IO.puts(inspect(Regex.match?(~r/^(a|b)*c$/, String.duplicate("ab", 500000) <> "c")))\n'
  '    IO.puts(inspect(Enum.count(Regex.scan(~r/(?:ab)+/, String.duplicate("ab", 200000) <> "c"))))\n'
  '  end\n'
  'end\n',
  0,
  b'true\ntrue\n1\n',
  b''),
 # iterate
 ('defmodule M do\n'
  '  def main() do\n'
  '    s = Stream.iterate(1, fn x -> x + 1 end)\n'
  '    IO.puts(inspect(Enum.to_list(Stream.take(s, 5))))\n'
  '    m = Stream.map(s, fn y -> y * 2 end)\n'
  '    IO.puts(inspect(Enum.to_list(Stream.take(m, 5))))\n'
  '    IO.puts(inspect(Enum.take(Stream.map(Stream.iterate(1, fn x -> x + 1 end), fn y -> y * 2 end), 5)))\n'
  '    IO.puts(inspect(Enum.take(Stream.filter(Stream.iterate(1, fn x -> x + 1 end), fn y -> rem(y, 2) == 0 end), 5)))\n'
  '    IO.puts(inspect(Enum.take(Stream.map(Stream.cycle([1, 2, 3]), fn y -> y * 2 end), 5)))\n'
  '    IO.puts(inspect(Enum.take(Stream.map(Stream.unfold(1, fn x -> some({x, x + 1}) end), fn y -> y * 2 end), 5)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 3, 4, 5]\n'+b'[2, 4, 6, 8, 10]\n'*3+b'[2, 4, 6, 2, 4]\n'+b'[2, 4, 6, 8, 10]\n',
  b''),
 # library
 ('defmodule M do\n'
  '  def f(n: integer): integer do\n'
  '    if n == 0 do 0 else Enum.sum(Enum.zip_with([n], [1], fn x, y -> f(x - y) + 1 end)) end\n'
  '  end\n'
  '  def g(n: integer): integer do\n'
  '    if n == 0 do 0 else Enum.reduce_while([n], 0, fn x, acc -> halt(g(x - 1) + 1) end) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(49999)))\n'
  '    IO.puts(Integer.to_string(g(49999)))\n'
  '  end\n'
  'end\n',
  0,
  b'49999\n49999\n',
  b''),
 # library2
 ('defmodule M do\n'
  '  def f(n: integer): integer do\n'
  '    if n == 0 do 0 else Enum.sum(Enum.flat_map([n], fn x -> [f(x - 1) + 1] end)) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(20000)))\n'
  '    IO.puts(Integer.to_string(f(49999)))\n'
  '  end\n'
  'end\n',
  0,
  b'20000\n49999\n',
  b''),
 # libloop
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(inspect(String.length(String.trim_leading(String.duplicate(" ", 300000) <> "x"))))\n'
  '    IO.puts(inspect(Integer.undigits(Enum.map(Enum.to_list(1..200000), fn x -> 0 end))))\n'
  '    IO.puts(inspect(Enum.sum(Enum.to_list(Stream.take_while(Stream.iterate(1, fn x -> x + 1 end), fn x -> x < 300000 end)))))\n'
  '    IO.puts(inspect(Enum.count(Regex.split(~r/,/, String.duplicate("a,", 100000)))))\n'
  '  end\n'
  'end\n',
  0,
  b'1\n0\n44999850000\n100001\n',
  b''),
 # fncons
 ('defmodule M do\n'
  '  def main() do\n'
  '    fs: list[fn[integer, integer]] = []\n'
  '    gs = [fn(x: integer): integer do x + 10 end, fn(y: integer): integer do y * 2 end | fs]\n'
  '    IO.puts(Enum.join(Enum.map(gs, fn f -> Integer.to_string(f.(1)) end), ","))\n'
  '  end\n'
  'end\n',
  0,
  b'11,2\n',
  b''),]

REJECTS=[# 5:9: return cannot be used inside an if or case that produces a value
 'defmodule M do\n'
  '  def f(n: integer): integer do\n'
  '    xs = for i <- [1, 2, 3] do\n'
  '      if i == n do\n'
  '        return 99\n'
  '      end\n'
  '      i\n'
  '    end\n'
  '    Enum.count(xs)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(2)))\n'
  '  end\n'
  'end\n',
 # 5:9: return cannot be used inside an if or case that produces a value
 'defmodule M do\n'
  '  def f(n: integer): integer do\n'
  '    for i <- [1, 2, 3] do\n'
  '      if i == n do\n'
  '        return 99\n'
  '      end\n'
  '      IO.puts("x")\n'
  '    end\n'
  '    7\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(2)))\n'
  '  end\n'
  'end\n',
 # 5:9: return cannot be used inside an if or case that produces a value
 'defmodule M do\n'
  '  def f(n: integer, acc: integer): integer do\n'
  '    try do\n'
  '      if n == 0 do\n'
  '        return acc\n'
  '      end\n'
  '      return f(n - 1, acc + 1)\n'
  '    rescue\n'
  '      e -> 0 - 1\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(300000, 0)))\n'
  '  end\n'
  'end\n',
 # 5:9: return cannot be used inside an if or case that produces a value
 'defmodule M do\n'
  '  def f(n: integer, acc: integer): integer do\n'
  '    x = with {a, b} <- {n, acc} do\n'
  '      if a == 0 do\n'
  '        return b\n'
  '      end\n'
  '      a + b\n'
  '    end\n'
  '    x\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(Integer.to_string(f(3, 0)))\n'
  '  end\n'
  'end\n',]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-tail-calls-') as d:
        out=Path(d)/'out'
        for source,status,stdout,stderr in RUNS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run.returncode,run.stdout[:300],run.stderr[:300])
            # Ten million turns take no stack and no memory: the same run in the
            # least a program is granted (a 4 MiB arena and a 2 MiB stack).
            if 'loop(10000000, 0)' in source:
                run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(out))
                assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),('ten million turns in the least memory',run)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    print(f'PASS tail calls: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; self calls in return position as loops, the calls that stay calls, depth and traces, ten million turns in 4 MiB')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
