#!/usr/bin/env python3
"""with and for: every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule M do\n'
  '  def main() do\n'
  'r = with some(a) <- List.first([1,2]) do\n'
  '  some(a + 1)\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'some(2)\n',
  b''),
 ('defmodule M do\n  def main() do\nr = with [a, b] <- [1, 2, 3] do\n  [a + b]\nend\nIO.puts(inspect(r))\n  end\nend\n',
  0,
  b'[1, 2, 3]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with [a, b] <- [1, 2, 3] do\n'
  '  a + b\n'
  'else\n'
  '  [] -> 0\n'
  '  other -> length(other)\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("z"), [x] <- [1, 2] do\n'
  '  a + x\n'
  'else\n'
  '  error(e) -> 0 - 1\n'
  '  list -> length(list)\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'-1\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("7"), [x] <- [1, 2] do\n'
  '  a + x\n'
  'else\n'
  '  error(e) -> 0 - 1\n'
  '  [p, q] -> p + q\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("7"), [x] <- [1, 2, 3] do\n'
  '  a + x\n'
  'else\n'
  '  error(e) -> 0 - 1\n'
  '  [p, q] -> p + q\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: no case branch matched\n  at M.main <closure> (<stdin>:3)\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'with ok(a) <- Integer.parse("7") do\n'
  '  IO.puts("yes #{a}")\n'
  'end\n'
  'with ok(a) <- Integer.parse("q") do\n'
  '  IO.puts("yes #{a}")\n'
  'end\n'
  'with ok(a) <- Integer.parse("q") do\n'
  '  IO.puts("yes #{a}")\n'
  'else\n'
  '  error(m) -> IO.puts("no " <> m)\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'yes 7\nno "q" is not an integer\n',
  b''),
 ('defmodule M do\n  def main() do\nr = with {1, x} <- {2, 3} do\n  {x, x}\nend\nIO.puts(inspect(r))\n  end\nend\n',
  0,
  b'{2, 3}\n',
  b''),
 ('defmodule M do\n  def main() do\nr = with 1 <- 2 do\n  5\nend\nIO.puts(inspect(r))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("7") do\n'
  '  a\n'
  'else\n'
  '  error(e) when e == "x" -> 1\n'
  '  error(e) -> 2\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'7\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = 1 + with ok(a) <- Integer.parse("7") do\n'
  '  a\n'
  'else\n'
  '  _ -> 2\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'8\n',
  b''),
 ('defmodule M do\n  def main() do\nr = with x <- 1 do\n  x\nelse\n  _ -> 2\nend\nIO.puts(inspect(r))\n  end\nend\n',
  0,
  b'1\n',
  b''),
 ('defmodule M do\n'
  '  def parse_point(text: string): result[tuple[integer, integer], string] do\n'
  '    with [left, right] <- String.split(text, ","),\n'
  '         ok(x) <- Integer.parse(left),\n'
  '         ok(y) <- Integer.parse(right) do\n'
  '      ok({x, y})\n'
  '    else\n'
  '      error(reason) -> error("bad number: #{reason}")\n'
  '      parts -> error("expected 2 parts, got #{length(parts)}")\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(parse_point("3,4")))\n'
  '    IO.puts(inspect(parse_point("3")))\n'
  '    IO.puts(inspect(parse_point("3,x")))\n'
  '    assert(parse_point("3,4") == ok({3, 4}))\n'
  '    assert(parse_point("3") == error("expected 2 parts, got 1"))\n'
  '  end\n'
  'end\n',
  0,
  b'ok({3, 4})\nerror("expected 2 parts, got 1")\nerror("bad number: \\"x\\" is not an integer")\n',
  b''),
 ('defmodule M do\n'
  '  def half(n: integer): result[integer, string] do\n'
  '    if rem(n, 2) == 0 do ok(div(n, 2)) else error("odd #{n}") end\n'
  '  end\n'
  '  def name(n: integer): result[string, string] do\n'
  '    if n > 2 do ok("big") else error("small") end\n'
  '  end\n'
  '  def both(n: integer): result[string, string] do\n'
  '    with ok(h) <- half(n), ok(s) <- name(h) do\n'
  '      ok(s <> "!")\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(both(8)))\n'
  '    IO.puts(inspect(both(7)))\n'
  '    IO.puts(inspect(both(2)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok("big!")\nerror("odd 7")\nerror("small")\n',
  b''),
 ('defmodule M do\n'
  '  def half(n: integer): result[integer, string] do\n'
  '    if rem(n, 2) == 0 do ok(div(n, 2)) else error("odd #{n}") end\n'
  '  end\n'
  '  def both(n: integer): result[string, string] do\n'
  '    with ok(4) <- half(n) do\n'
  '      ok("four")\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(both(8)))\n'
  '    IO.puts(inspect(both(7)))\n'
  '    IO.puts(inspect(both(2)))\n'
  '  end\n'
  'end\n',
  2,
  b'ok("four")\nerror("odd 7")\n',
  b'<stdin>:6:19: no with clause matched\n  at M.both <closure> (<stdin>:6)\n  at M.both (<stdin>:6)\n  at M.main (<std'
  b'in>:13)\n'),
 ('defmodule M do\n'
  '  def first(xs: list[integer]): option[string] do\n'
  '    with some(1) <- List.first(xs) do\n'
  '      some("one")\n'
  '    end\n'
  '  end\n'
  '  def same(xs: list[integer]): option[integer] do\n'
  '    with some(1) <- List.first(xs) do\n'
  '      some(100)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(first([1])))\n'
  '    IO.puts(inspect(first([2])))\n'
  '    IO.puts(inspect(first([])))\n'
  '    IO.puts(inspect(same([1])))\n'
  '    IO.puts(inspect(same([2])))\n'
  '    IO.puts(inspect(same([])))\n'
  '  end\n'
  'end\n',
  0,
  b'some("one")\nnone\nnone\nsome(100)\nsome(2)\nnone\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r: result[integer, string] = with ok(a) <- Integer.parse("3"), ok(b) <- Integer.parse("x") do\n'
  '  ok(a + b)\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'error("\\"x\\" is not an integer")\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'f = fn(t: string): integer do\n'
  '  with ok(n) <- Integer.parse(t) do\n'
  '    n * 2\n'
  '  else\n'
  '    error(_) -> 0\n'
  '  end\n'
  'end\n'
  'IO.puts(inspect(f.("21")))\n'
  'IO.puts(inspect(f.("z")))\n'
  'IO.puts(inspect(Enum.map(["1", "q", "3"], fn t -> with ok(n) <- Integer.parse(t) do n else _ -> 0 - 1 end end)))\n'
  '  end\n'
  'end\n',
  0,
  b'42\n0\n[1, -1, 3]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'k = 10\n'
  'r = with ok(a) <- Integer.parse("3") do\n'
  '  with ok(b) <- Integer.parse("4") do\n'
  '    a + b + k\n'
  '  else\n'
  '    _ -> 0\n'
  '  end\n'
  'else\n'
  '  _ -> 0 - 1\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'17\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'with ok(a) <- Integer.parse("3") do\n'
  '  IO.puts("x")\n'
  'end\n'
  'with ok(a) <- Integer.parse("4") do\n'
  '  IO.puts("y #{a}")\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'x\ny 4\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 3\n'
  'if x > 2 do\n'
  '  with ok(a) <- Integer.parse("3") do\n'
  '    IO.puts("in if #{a + x}")\n'
  '  else\n'
  '    _ -> IO.puts("no")\n'
  '  end\n'
  'end\n'
  'case x do\n'
  '  3 -> with [h | _] <- [x] do IO.puts(inspect(h)) end\n'
  '  _ -> IO.puts("other")\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'in if 6\n3\n',
  b''),
 ('defmodule M do\n'
  '  def boom(n: integer): result[integer, string] do\n'
  '    [a] = [n, n]\n'
  '    ok(a)\n'
  '  end\n'
  '  def main() do\n'
  '    r = with ok(a) <- Integer.parse("3"),\n'
  '             ok(b) <- boom(a) do\n'
  '      a + b\n'
  '    else\n'
  '      _ -> 0\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:7)\n  at M.main (<stdin>'
  b':7)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): result[integer, string] do\n'
  '    [a] = [n, n]\n'
  '    ok(a)\n'
  '  end\n'
  '  def main() do\n'
  '    with ok(a) <- Integer.parse("3"),\n'
  '         ok(b) <- boom(a) do\n'
  '      IO.puts("x")\n'
  '    else\n'
  '      _ -> IO.puts("y")\n'
  '    end\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main (<stdin>:7)\n'),
 ('defmodule M do\n'
  '  def f(t: string): result[string, string] do\n'
  '    with ok(1) <- Integer.parse(t) do\n'
  '      ok("one")\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f("1")))\n'
  '    IO.puts(inspect(f("x")))\n'
  '    IO.puts(inspect(f("2")))\n'
  '  end\n'
  'end\n',
  2,
  b'ok("one")\nerror("\\"x\\" is not an integer")\n',
  b'<stdin>:3:19: no with clause matched\n  at M.f <closure> (<stdin>:3)\n  at M.f (<stdin>:3)\n  at M.main (<stdin>:10'
  b')\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("3") do\n'
  '  a\n'
  'else\n'
  '  error(e) -> 1\n'
  '  error(f) -> 2\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("3") do\n'
  '  a\n'
  'else\n'
  '  error(e) -> 1\n'
  '  _ -> 2\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("3") do\n'
  '  a\n'
  'else\n'
  '  _ -> 1\n'
  '  _ -> 2\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with true <- 1 < 2, false <- 2 < 1 do\n'
  '  "ok"\n'
  'else\n'
  '  true -> "t"\n'
  '  false -> "f"\n'
  'end\n'
  'IO.puts(r)\n'
  '  end\n'
  'end\n',
  0,
  b'ok\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with {:ok, v} <- {:ok, 5}, {:ok, w} <- {:error, 6} do\n'
  '  v + w\n'
  'else\n'
  '  {:error, n} -> 0 - n\n'
  '  _ -> 0\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'-6\n',
  b''),
 ('defmodule M do\n  def main() do\nr = with x <- 5, y <- x + 1 do\n  x * y\nend\nIO.puts(inspect(r))\n  end\nend\n',
  0,
  b'30\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with %{"a" => v} <- %{"a" => 1, "b" => 2} do\n'
  '  v\n'
  'else\n'
  '  m -> map_size(m)\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  'r2 = with %{"z" => v} <- %{"a" => 1, "b" => 2} do\n'
  '  v\n'
  'else\n'
  '  m -> map_size(m)\n'
  'end\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  0,
  b'1\n2\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with "a" <- "b" do\n'
  '  "matched"\n'
  'end\n'
  'IO.puts(r)\n'
  'r2 = with -1 <- 0 - 1, :x <- :x do\n'
  '  "neg"\n'
  'else\n'
  '  _ -> "no"\n'
  'end\n'
  'IO.puts(r2)\n'
  '  end\n'
  'end\n',
  0,
  b'b\nneg\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("3") do\n'
  '  x = a + 1\n'
  '  y = x * 2\n'
  '  y\n'
  'else\n'
  '  error(e) ->\n'
  '    z = String.length(e)\n'
  '    z + 1\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'8\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = (with ok(a) <- Integer.parse("3") do a else _ -> 0 end) + 1\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'4\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(with ok(a) <- Integer.parse("3") do a else _ -> 0 end))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("3") do\n'
  '  a\n'
  'else\n'
  '  error(e) -> if e == "" do 1 else 2 end\n'
  '  other -> 5\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def f(n: integer): integer do\n'
  '    with true <- n > 0 do\n'
  '      n\n'
  '    else\n'
  '      false -> 0 - n\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(3) + f(-4)))\n'
  '  end\n'
  'end\n',
  0,
  b'7\n',
  b''),
 ('defmodule M do\n'
  '  def half(n: integer): result[integer, string] do\n'
  '    if rem(n, 2) == 0 do ok(div(n, 2)) else error("odd #{n}") end\n'
  '  end\n'
  '  def both(n: integer): result[string, string] do\n'
  '    r: result[string, string] =\n'
  '      with ok(k) <- half(n),\n'
  '           ok(4) <-\n'
  '             half(k) do\n'
  '        ok("four")\n'
  '      end\n'
  '    r\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(both(16)))\n'
  '    IO.puts(inspect(both(7)))\n'
  '    IO.puts(inspect(both(4)))\n'
  '  end\n'
  'end\n',
  2,
  b'ok("four")\nerror("odd 7")\n',
  b'<stdin>:9:14: no with clause matched\n  at M.both <closure> (<stdin>:7)\n  at M.both <closure> (<stdin>:7)\n  at M.'
  b'both (<stdin>:7)\n  at M.main (<stdin>:17)\n'),
 ('defmodule M do\n'
  '  def half(n: integer): result[integer, string] do\n'
  '    if rem(n, 2) == 0 do ok(div(n, 2)) else error("odd #{n}") end\n'
  '  end\n'
  '  def both(n: integer): result[string, string] do\n'
  '    IO.puts("x")\n'
  '    with ok(k) <- half(n),\n'
  '           ok(4) <-\n'
  '             half(k) do\n'
  '        IO.puts("body")\n'
  '        ok("four")\n'
  '      end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(both(16)))\n'
  '    IO.puts(inspect(both(7)))\n'
  '    IO.puts(inspect(both(4)))\n'
  '  end\n'
  'end\n',
  2,
  b'x\nbody\nok("four")\nx\nerror("odd 7")\nx\n',
  b'<stdin>:9:14: no with clause matched\n  at M.both <closure> (<stdin>:7)\n  at M.both (<stdin>:7)\n  at M.main (<std'
  b'in>:17)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): result[integer, string] do\n'
  '    [a] = [n, n]\n'
  '    ok(a)\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      with ok(a) <- Integer.parse("3"),\n'
  '             ok(b) <-\n'
  '               boom(a) do\n'
  '        a + b\n'
  '      else\n'
  '        _ -> 0\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:8)\n  at M.main (<stdin>'
  b':8)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): result[integer, string] do\n'
  '    [a] = [n, n]\n'
  '    ok(a)\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      with ok(a) <- Integer.parse("3") do\n'
  '        IO.puts("in")\n'
  '        x = \n'
  '          boom(a)\n'
  '        2\n'
  '      else\n'
  '        _ -> 0\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'in\n',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:10)\n  at M.main (<stdin'
  b'>:8)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): result[integer, string] do\n'
  '    [a] = [n, n]\n'
  '    ok(a)\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      with ok(a) <- Integer.parse("z") do\n'
  '        2\n'
  '      else\n'
  '        error(_) -> \n'
  '          IO.puts("else")\n'
  '          x = boom(1)\n'
  '          0\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'else\n',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:13)\n  at M.main (<stdin'
  b'>:8)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): result[integer, string] do\n'
  '    [a] = [n, n]\n'
  '    ok(a)\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      case Integer.parse("3") do\n'
  '        ok(a) ->\n'
  '          case boom(a) do\n'
  '            ok(b) -> a + b\n'
  '            _ -> 0\n'
  '          end\n'
  '        _ -> 0\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:10)\n  at M.main (<stdin'
  b'>:8)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("3") do\n'
  '  a\n'
  'else\n'
  '  error(e) -> 1\n'
  '  x -> undefined_function(x) + "s"\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("3") do\n'
  '  a\n'
  'else\n'
  '  [x] -> undefined_function(x) + "s"\n'
  '  error(e) -> 1\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with x <- 5 do\n'
  '  x\n'
  'else\n'
  '  y -> undefined_function(y)\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with x <- 5 do\n'
  '  x\n'
  'else\n'
  '  Foo.bar(y) -> 1\n'
  '  %Zed{a: 1} -> 2\n'
  '  {1, 2, 3} -> 4\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with x <- 5 do\n'
  '  x\n'
  'else\n'
  '  Foo.bar(y) -> 1\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with x <- 5 do\n'
  '  x\n'
  'else\n'
  '  %Zed{a: 1} -> 2\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with x <- 5 do\n'
  '  x\n'
  'else\n'
  '  {1, 2, 3} -> 4\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with {a, b} <- {1, 2}, [c] <- [a + b] do\n'
  '  c\n'
  'else\n'
  '  [] -> 0\n'
  '  [_, _ | _] -> 2\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with [c] <- [1, 2] do\n'
  '  c\n'
  'else\n'
  '  [] -> 0\n'
  '  [_, _, _ | _] -> 2\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: no case branch matched\n  at M.main <closure> (<stdin>:3)\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n'
  '  def find(m: map[string, integer], k: string): option[integer] do\n'
  '    Map.get(m, k)\n'
  '  end\n'
  '  def sum(m: map[string, integer]): option[integer] do\n'
  '    with some(a) <- find(m, "a"),\n'
  '         some(b) <- find(m, "b") do\n'
  '      some(a + b)\n'
  '    end\n'
  '  end\n'
  '  def describe(m: map[string, integer]): string do\n'
  '    with some(a) <- find(m, "a"),\n'
  '         some(b) <- find(m, "b") do\n'
  '      "sum #{a + b}"\n'
  '    else\n'
  '      none -> "missing"\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(sum(%{"a" => 1, "b" => 2})))\n'
  '    IO.puts(inspect(sum(%{"a" => 1})))\n'
  '    IO.puts(describe(%{"a" => 1, "b" => 2}))\n'
  '    IO.puts(describe(%{"b" => 2}))\n'
  '  end\n'
  'end\n',
  0,
  b'some(3)\nnone\nsum 3\nmissing\n',
  b''),
 ('defmodule M do\n'
  '  def check(n: integer): result[integer, string] do\n'
  '    if n > 0 do ok(n) else error("not positive") end\n'
  '  end\n'
  '  def twice(n: integer): result[integer, string] do\n'
  '    with ok(a) <- check(n), ok(b) <- check(a - 1) do\n'
  '      ok(a + b)\n'
  '    end\n'
  '  end\n'
  '  def label(n: integer): string do\n'
  '    with ok(a) <- check(n), true <- a < 10 do\n'
  '      "small"\n'
  '    else\n'
  '      error(why) -> why\n'
  '      false -> "big"\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(twice(5)))\n'
  '    IO.puts(inspect(twice(1)))\n'
  '    IO.puts(inspect(twice(0)))\n'
  '    IO.puts(label(3) <> " " <> label(30) <> " " <> label(-3))\n'
  '  end\n'
  'end\n',
  0,
  b'ok(9)\nerror("not positive")\nerror("not positive")\nsmall big not positive\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("3") do\n'
  '  a\n'
  'else\n'
  '  error(e) when String.length(e) > 100 -> 1\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  'r2 = with ok(a) <- Integer.parse("zz") do\n'
  '  a\n'
  'else\n'
  '  error(e) when String.length(e) > 100 -> 1\n'
  'end\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  2,
  b'3\n',
  b'<stdin>:9:6: no case branch matched\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:9)\n'),
 ('defmodule M do\n'
  '  def go(t: string): integer do\n'
  '    with ok(a) <- Integer.parse(t) do\n'
  '      a\n'
  '    else\n'
  '      error(e) when String.length(e) > 100 -> 1\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(go("5")))\n'
  '    IO.puts(inspect(go("q")))\n'
  '  end\n'
  'end\n',
  2,
  b'5\n',
  b'<stdin>:3:5: no case branch matched\n  at M.go (<stdin>:3)\n  at M.main (<stdin>:11)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'with ok(a) <- Integer.parse("5") do\n'
  '  IO.puts("one")\n'
  'else\n'
  '  error(_) -> IO.puts("two")\n'
  'end\n'
  'with ok(a) <- Integer.parse("x") do\n'
  '  IO.puts("one")\n'
  'else\n'
  '  error(_) -> IO.puts("two")\n'
  'end\n'
  'with ok(a) <- Integer.parse("5"), [b] <- [a, a] do\n'
  '  IO.puts("one")\n'
  'end\n'
  'IO.puts("end")\n'
  '  end\n'
  'end\n',
  0,
  b'one\ntwo\nend\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r: option[integer] = with some(x) <- List.first([1]) do\n'
  '  none\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  'r2: list[integer] = with [x] <- [1, 2] do\n'
  '  []\n'
  'end\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  0,
  b'none\n[1, 2]\n',
  b''),
 ('defmodule M do\n'
  '  def f(a: integer, b: integer): result[integer, string] do\n'
  '    with true <- a > 0,\n'
  '         true <- b > 0 do\n'
  '      ok(a + b)\n'
  '    else\n'
  '      false -> error("negative")\n'
  '    end\n'
  '  end\n'
  '  def g(a: integer): result[integer, string] do\n'
  '    with ok(x) <- f(a, 1),\n'
  '         ok(y) <- f(x, -1) do\n'
  '      ok(x + y)\n'
  '    else\n'
  '      error(why) -> error("g: " <> why)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1, 2)) <> inspect(f(0, 2)) <> inspect(g(1)) <> inspect(g(-1)))\n'
  '  end\n'
  'end\n',
  0,
  b'ok(3)error("negative")error("g: negative")error("g: negative")\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("5") do a else _ -> 0 end + 1\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'6\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = Enum.map(["1", "b"], fn t ->\n'
  '  with ok(a) <- Integer.parse(t) do\n'
  '    a\n'
  '  else\n'
  '    error(_) -> 0\n'
  '  end\n'
  'end)\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 0]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with {x, y} <- {1, 2} do\n'
  '  x + y\n'
  'else\n'
  '  z -> 0\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(a) <- Integer.parse("7") do\n'
  '  a\n'
  'else\n'
  '  error(e) -> 0\n'
  '  error(e) -> 1\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'7\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with [a | _] <- [1, 2] do\n'
  '  a\n'
  'else\n'
  '  [_ | _] -> 5\n'
  '  [] -> 0\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'1\n',
  b''),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    x = 1\n'
  '    r =\n'
  '      x +\n'
  '      case x do\n'
  '        1 ->\n'
  '          boom(1)\n'
  '        _ -> 0\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:12)\n  at M.main (<stdin'
  b'>:10)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    x = 1\n'
  '    r =\n'
  '      (case x do\n'
  '        1 -> 5\n'
  '        _ -> 0\n'
  '      end) +\n'
  '      x +\n'
  '      boom(1)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main (<stdin>:9)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    x = 1\n'
  '    r =\n'
  '      if x == 1 do\n'
  '        y = 2\n'
  '        boom(1)\n'
  '      else\n'
  '        0\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:11)\n  at M.main (<stdin'
  b'>:9)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    x = 1\n'
  '    IO.puts(\n'
  '      inspect(\n'
  '        case x do\n'
  '          1 ->\n'
  '            boom(1)\n'
  '          _ -> 0\n'
  '        end))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:12)\n  at M.main (<stdin'
  b'>:10)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    x = 1\n'
  '    r =\n'
  '      case x do\n'
  '        1 ->\n'
  '          y =\n'
  '            case x do\n'
  '              1 ->\n'
  '                boom(1)\n'
  '              _ -> 2\n'
  '            end\n'
  '          y\n'
  '        _ -> 0\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:14)\n  at M.main <closur'
  b'e> (<stdin>:12)\n  at M.main (<stdin>:9)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    x = 1\n'
  '    r =\n'
  '      case x do\n'
  '        1 -> 5\n'
  '        _ -> 0\n'
  '      end\n'
  '    s = r +\n'
  '      boom(1)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main (<stdin>:13)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    x = 1\n'
  '    r =\n'
  '      boom(case x do\n'
  '        1 -> 5\n'
  '        _ -> 0\n'
  '      end)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main (<stdin>:8)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'squares = for n <- 1..5, do: n * n\n'
  'IO.puts(inspect(squares))\n'
  'pairs = for x <- [1, 2, 3], y <- [1, 2, 3], x < y do\n'
  '  {x, y}\n'
  'end\n'
  'IO.puts(inspect(pairs))\n'
  'present = for some(n) <- [some(1), none, some(3)], do: n\n'
  'IO.puts(inspect(present))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 4, 9, 16, 25]\n[{1, 2}, {1, 3}, {2, 3}]\n[1, 3]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'squares = for n <- 1..3, into: %{}, do: {n, n * n}\n'
  'IO.puts(inspect(squares))\n'
  'initials = for word <- ["bee", "ant", "bat"], uniq: true, do: String.slice(word, 0, 1)\n'
  'IO.puts(inspect(initials))\n'
  'total = for x <- [1, 2, 3], x != 2, reduce: 0 do\n'
  '  acc -> acc + x\n'
  'end\n'
  'IO.puts(inspect(total))\n'
  'counts: map[string, integer] = for word <- ["a", "b", "a"], reduce: %{} do\n'
  '  seen -> Map.update(seen, word, 1, &(&1 + 1))\n'
  'end\n'
  'IO.puts(inspect(counts))\n'
  '  end\n'
  'end\n',
  0,
  b'%{1 => 1, 2 => 4, 3 => 9}\n["b", "a"]\n4\n%{"a" => 2, "b" => 1}\n',
  b''),
 ('defmodule M do\n  def main() do\nr = for(n <- 1..5, do: n * n)\nIO.puts(inspect(r))\n  end\nend\n',
  0,
  b'[1, 4, 9, 16, 25]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'for n <- [1, 2, 3] do\n'
  '  IO.puts(inspect(n))\n'
  'end\n'
  'x = for n <- [1, 2, 3] do\n'
  '  IO.puts(inspect(n))\n'
  'end\n'
  'IO.puts(inspect(x))\n'
  '  end\n'
  'end\n',
  0,
  b'1\n2\n3\n1\n2\n3\n[{}, {}, {}]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'm = %{"b" => 2, "a" => 1}\n'
  'r = for {k, v} <- m, do: k <> inspect(v)\n'
  'IO.puts(inspect(r))\n'
  'r2 = for pair <- m, do: pair\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  0,
  b'["a1", "b2"]\n[{"a", 1}, {"b", 2}]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2], y <- [x, x * 10], z <- 1..2, do: {x, y, z}\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[{1, 1, 1}, {1, 1, 2}, {1, 10, 1}, {1, 10, 2}, {2, 2, 1}, {2, 2, 2}, {2, 20, 1}, {2, 20, 2}]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- 1..10, rem(x, 2) == 0, x > 4, do: x\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[6, 8, 10]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for {1, x} <- [{1, 2}, {2, 3}, {1, 4}], do: x\n'
  'IO.puts(inspect(r))\n'
  'r2 = for [h | _] <- [[1], [], [2, 3]], do: h\n'
  'IO.puts(inspect(r2))\n'
  'r3 = for ok(v) <- [Integer.parse("1"), Integer.parse("x")], do: v\n'
  'IO.puts(inspect(r3))\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 4]\n[1, 2]\n[1]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2, 3], into: [0], do: x * 2\n'
  'IO.puts(inspect(r))\n'
  's = for x <- ["a", "b"], into: "", do: x <> "!"\n'
  'IO.puts(inspect(s))\n'
  's2 = for x <- ["a", "b"], into: ">", do: x <> "!"\n'
  'IO.puts(inspect(s2))\n'
  'm = for x <- [1, 2], into: %{0 => 0}, do: {x, x}\n'
  'IO.puts(inspect(m))\n'
  'l = for x <- [1, 2], into: [], do: x\n'
  'IO.puts(inspect(l))\n'
  '  end\n'
  'end\n',
  0,
  b'[0, 2, 4, 6]\n"a!b!"\n">a!b!"\n%{0 => 0, 1 => 1, 2 => 2}\n[1, 2]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2, 1, 3, 2], uniq: true, do: x\n'
  'IO.puts(inspect(r))\n'
  'r2 = for x <- [1, 2, 1, 3, 2], uniq: false, do: x\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 3]\n[1, 2, 1, 3, 2]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2, 3], reduce: {0, 1} do\n'
  '  {s, p} -> {s + x, p * x}\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  'r2 = for x <- [1, 2, 3], reduce: 0 do\n'
  '  0 -> x\n'
  '  acc when acc > 2 -> acc * x\n'
  '  acc -> acc + x\n'
  'end\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  0,
  b'{6, 6}\n9\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2, 3], reduce: "" do\n'
  '  acc -> acc <> inspect(x)\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'"123"\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'e: list[integer] = []\n'
  'r = for x <- e, do: x + 1\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'k = 10\n'
  'f = fn(xs: list[integer]): list[integer] do\n'
  '  for x <- xs, do: x + k\n'
  'end\n'
  'IO.puts(inspect(f.([1, 2])))\n'
  'IO.puts(inspect(Enum.map([[1], [2, 3]], fn xs -> for x <- xs, do: x * k end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[11, 12]\n[[10], [20, 30]]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2] do\n'
  '  y = x * 2\n'
  '  z = y + 1\n'
  '  {y, z}\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[{2, 3}, {4, 5}]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2], do: for y <- [x, x], do: y + 1\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[[2, 2], [3, 3]]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [3, 4] do\n'
  '  if x > 3 do "big" else "small" end\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'["small", "big"]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = length(for x <- [3, 4], do: x) + 1\n'
  'IO.puts(inspect(r))\n'
  'IO.puts(inspect(Enum.sum(for x <- 1..4, do: x * x)))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n30\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2], uniq: true do\n'
  '  rem(x, 1)\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[0]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2], into: %{} do\n'
  '  {x, "v"}\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'%{1 => "v", 2 => "v"}\n',
  b''),
 ('defmodule M do\n'
  '  def f(xs: list[integer]): list[integer] do\n'
  '    for x <- xs, do: x + 1\n'
  '  end\n'
  '  def g(xs: list[integer]): integer do\n'
  '    for x <- xs, reduce: 0 do\n'
  '      acc -> acc + x\n'
  '    end\n'
  '  end\n'
  '  def h(xs: list[string]): map[string, integer] do\n'
  '    for x <- xs, reduce: %{} do\n'
  '      acc -> Map.put(acc, x, 1)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f([1, 2])))\n'
  '    IO.puts(inspect(g([1, 2])))\n'
  '    IO.puts(inspect(h(["a"])))\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 3]\n3\n%{"a" => 1}\n',
  b''),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2] do\n'
  '        y = x + 1\n'
  '        boom(y)\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closur'
  b'e> (<stdin>:11)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:15)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    for x <- [1, 2] do\n'
  '      y = x + 1\n'
  '      IO.puts(inspect(boom(y)))\n'
  '    end\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure'
  b'> (<stdin>:10)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:14)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2],\n'
  '          boom(x) > 0 do\n'
  '        x\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:12)\n  at M.main <closur'
  b'e> (<stdin>:9)\n  at M.main (<stdin>:15)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): list[integer] do\n'
  '    [a] = [n, n]\n'
  '    [a]\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2],\n'
  '          y <-\n'
  '            boom(x) do\n'
  '        x + y\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:12)\n  at M.main <closur'
  b'e> (<stdin>:9)\n  at M.main (<stdin>:18)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): list[integer] do\n'
  '    [a] = [n, n]\n'
  '    [a]\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <-\n'
  '            boom(1),\n'
  '          y <- [1] do\n'
  '        x + y\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>'
  b':18)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2], reduce: 0 do\n'
  '        acc ->\n'
  '          z = acc\n'
  '          boom(x) + z\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:11)\n  at M.main <closur'
  b'e> (<stdin>:9)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:13)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2], y <- [3], z <- [4], x > 0, do: boom(x + y + z)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:8)\n  at M.main <closure'
  b'> (<stdin>:9)\n  at M.main <closure> (<stdin>:15)\n  at M.main <closure> (<stdin>:12)\n  at M.main <closure> (<stdi'
  b'n>:9)\n  at M.main (<stdin>:17)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2], reduce: boom(0) do\n'
  '        acc -> acc\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:8)\n  at M.main (<stdin>'
  b':12)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2],\n'
  '        uniq: true do\n'
  '        boom(x)\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closur'
  b'e> (<stdin>:11)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:15)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2] do\n'
  '        [a] = [x, x]\n'
  '        a\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:5:9: pattern match failed\n  at M.main <closure> (<stdin>:5)\n  at M.main <closure> (<stdin>:7)\n  at M.mai'
  b'n <closure> (<stdin>:5)\n  at M.main (<stdin>:11)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2], y <- [0] do\n'
  '        div(x, y)\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:5:9: division by zero\n  at M.main <closure> (<stdin>:5)\n  at M.main <closure> (<stdin>:6)\n  at M.main <c'
  b'losure> (<stdin>:8)\n  at M.main <closure> (<stdin>:5)\n  at M.main (<stdin>:12)\n'),
 ('defmodule M do\n  def main() do\nfor x <- [1, 2], do: inspect(x)\nIO.puts("done")\n  end\nend\n', 0, b'done\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'for x <- [1, 2], into: %{}, do: {x, x}\n'
  'for x <- [1, 2], uniq: true, do: inspect(x)\n'
  'for x <- [1, 2], reduce: 0 do\n'
  '  acc -> acc + x\n'
  'end\n'
  'IO.puts("done")\n'
  '  end\n'
  'end\n',
  0,
  b'done\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'for x <- [1, 2] do\n'
  '  for y <- [3, 4] do\n'
  '    IO.puts(inspect(x * y))\n'
  '  end\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'3\n4\n6\n8\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2] do\n'
  '  for y <- [3, 4] do\n'
  '    IO.puts(inspect(x * y))\n'
  '  end\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n4\n6\n8\n[[{}, {}], [{}, {}]]\n',
  b''),
 ('defmodule M do\n  def main() do\nfor x <- [1, 2] do\n  if x > 1 do IO.puts("a") end\nend\n  end\nend\n',
  0,
  b'a\n',
  b''),
 ('defmodule M do\n  def main() do\nr = for x <- [1, 2] do\n  assert(x > 0)\nend\nIO.puts(inspect(r))\n  end\nend\n',
  0,
  b'[{}, {}]\n',
  b''),
 ('defmodule M do\n  def main() do\nfor x <- [1, 2] do\n  y = x\nend\n  end\nend\n', 0, b'', b''),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2] do\n'
  '        for y <- [3, 4] do\n'
  '          boom(x + y)\n'
  '        end\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closur'
  b'e> (<stdin>:11)\n  at M.main <closure> (<stdin>:11)\n  at M.main <closure> (<stdin>:15)\n  at M.main <closure> (<st'
  b'din>:16)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:20)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    for x <- [1, 2] do\n'
  '      for y <- [3, 4] do\n'
  '        IO.puts(inspect(boom(x + y)))\n'
  '      end\n'
  '    end\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure'
  b'> (<stdin>:10)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closure> (<stdin>:14)\n  at M.main <closure> (<std'
  b'in>:9)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:13)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2] do\n'
  '        if x > 5 do\n'
  '          1\n'
  '        else\n'
  '          z = x\n'
  '          boom(z)\n'
  '        end\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:13)\n  at M.main <closur'
  b'e> (<stdin>:15)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:19)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for x <- [1, 2] do\n'
  '        case x do\n'
  '          5 -> 1\n'
  '          _ ->\n'
  '            z = x\n'
  '            boom(z)\n'
  '        end\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:13)\n  at M.main <closur'
  b'e> (<stdin>:10)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:14)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r =\n'
  '      for {a, b} <- [{1, 2}], some(c) <- [some(a)], _ <- [0] do\n'
  '        boom(a + b + c)\n'
  '      end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure'
  b'> (<stdin>:10)\n  at M.main <closure> (<stdin>:16)\n  at M.main <closure> (<stdin>:13)\n  at M.main <closure> (<std'
  b'in>:9)\n  at M.main (<stdin>:18)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2], into: %{} do\n'
  '      {x, boom(x)}\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:8)\n  at M.main <closure'
  b'> (<stdin>:9)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:13)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): map[integer, integer] do\n'
  '    [a] = [n, n]\n'
  '    %{a => a}\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2], into: boom(1) do\n'
  '      {x, x}\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main (<stdin>:13)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      x\n'
  '    end\n'
  '    y = boom(1)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main (<stdin>:10)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def f(xs: list[integer]): list[integer] do\n'
  '    for x <- xs do\n'
  '      boom(x)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f([1])))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.f <closure> (<stdin>:8)\n  at M.f <closure> (<st'
  b'din>:9)\n  at M.f <closure> (<stdin>:9)\n  at M.f (<stdin>:13)\n  at M.main (<stdin>:12)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    f = fn(xs: list[integer]): list[integer] do\n'
  '      for x <- xs do\n'
  '        boom(x)\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(f.([1])))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure'
  b'> (<stdin>:10)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closure> (<stdin>:14)\n  at M.main (<stdin>:12'
  b')\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = Enum.map([1, 2], fn y ->\n'
  '      for x <- [y], do: boom(x)\n'
  '    end)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:8)\n  at M.main <closure'
  b'> (<stdin>:9)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closure> (<stdin>:13)\n  at M.main (<stdin>:7)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      with ok(v) <- Integer.parse("1") do\n'
  '        boom(v + x)\n'
  '      else\n'
  '        _ -> 0\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure'
  b'> (<stdin>:9)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:13)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      y = if x > 0 do boom(x) else 0 end\n'
  '      y + 1\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:8)\n  at M.main <closure'
  b'> (<stdin>:8)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:14)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    for x <- [1, 2] do\n'
  '      if x > 0 do\n'
  '        IO.puts("a")\n'
  '      end\n'
  '      for y <- [x] do\n'
  '        IO.puts(inspect(boom(y)))\n'
  '      end\n'
  '    end\n'
  '  end\n'
  'end\n',
  2,
  b'a\n',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:12)\n  at M.main <closur'
  b'e> (<stdin>:13)\n  at M.main <closure> (<stdin>:13)\n  at M.main <closure> (<stdin>:17)\n  at M.main <closure> (<st'
  b'din>:12)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:16)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2], x > 0, y <- [x], y > 0 do\n'
  '      cond do\n'
  '        x > 5 -> 1\n'
  '        true -> boom(y)\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closur'
  b'e> (<stdin>:12)\n  at M.main <closure> (<stdin>:13)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:18'
  b')\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      Enum.map([x], fn v ->\n'
  '        boom(v)\n'
  '      end)\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure'
  b'> (<stdin>:8)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:13)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2], reduce: 0 do\n'
  '      acc when acc > 100 -> acc\n'
  '      acc -> acc + boom(x)\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure'
  b'> (<stdin>:8)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:12)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): boolean do\n'
  '    [a] = [n, n]\n'
  '    a > 0\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2], reduce: 0 do\n'
  '      acc when boom(acc) -> acc\n'
  '      acc -> acc + x\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:7)\n  at M.main <closure'
  b'> (<stdin>:8)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:12)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      for y <- [3, 4] do\n'
  '        x + y\n'
  '      end\n'
  '    end\n'
  '    z = boom(1)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main (<stdin>:12)\n'),
 ('defmodule M do\n  def main() do\nr = for into: %{}, x <- [1, 2], do: {x, x}\nIO.puts(inspect(r))\n  end\nend\n',
  0,
  b'%{1 => 1, 2 => 2}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2], uniq: true, y <- [1, 2], do: x * y\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 4]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for "a" <- ["a", "b", "a"], do: 1\n'
  'IO.puts(inspect(r))\n'
  'y = 2\n'
  'r2 = for ^y <- [1, 2, 2], do: y\n'
  'IO.puts(inspect(r2))\n'
  'r3 = for {:ok, v} <- [{:ok, 1}, {:error, 2}, {:ok, 3}], do: v\n'
  'IO.puts(inspect(r3))\n'
  'r4 = for %{"k" => v} <- [%{"k" => 1}, %{"z" => 2}, %{"k" => 3, "z" => 4}], do: v\n'
  'IO.puts(inspect(r4))\n'
  'r5 = for [a, b] <- [[1, 2], [3], [4, 5]], [c | _] <- [[a + b]], do: c\n'
  'IO.puts(inspect(r5))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 1]\n[2, 2]\n[1, 3]\n[1, 3]\n[3, 9]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- 1..10//3, do: x\n'
  'IO.puts(inspect(r))\n'
  'r2 = for x <- 5..1, do: x\n'
  'IO.puts(inspect(r2))\n'
  'r3 = for x <- 3..1//1, do: x\n'
  'IO.puts(inspect(r3))\n'
  'm = %{3 => "c", 1 => "a", 2 => "b"}\n'
  'r4 = for {k, v} <- m, k > 1, do: v <> inspect(k)\n'
  'IO.puts(inspect(r4))\n'
  'r5 = for {k, _} <- m, {j, w} <- m, j < k, do: {k, w}\n'
  'IO.puts(inspect(r5))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 4, 7, 10]\n[5, 4, 3, 2, 1]\n[]\n["b2", "c3"]\n[{2, "a"}, {3, "a"}, {3, "b"}]\n',
  b''),
 ('defmodule M do\n'
  '  def noisy(n: integer): list[integer] do\n'
  '    IO.puts("gen #{n}")\n'
  '    [n, n + 1]\n'
  '  end\n'
  '  def check(n: integer): boolean do\n'
  '    IO.puts("filter #{n}")\n'
  '    n > 1\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- noisy(1), check(x), y <- noisy(x * 10), do: {x, y}\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'gen 1\nfilter 1\nfilter 2\ngen 20\n[{2, 20}, {2, 21}]\n',
  b''),
 ('defmodule M do\n'
  '  def size(n: integer): integer do\n'
  '    n + 1\n'
  '  end\n'
  '  def main() do\n'
  '    for x <- 1..300 do\n'
  '      for y <- 1..300 do\n'
  '        size(x * y)\n'
  '      end\n'
  '    end\n'
  '    for x <- 1..300, y <- 1..300 do\n'
  '      size(x * y)\n'
  '    end\n'
  '    IO.puts("done")\n'
  '  end\n'
  'end\n',
  0,
  b'done\n',
  b''),
 ('defmodule M do\n'
  '  def evens(xs: list[integer]): list[integer] do\n'
  '    for x <- xs, rem(x, 2) == 0 do\n'
  '      x\n'
  '    end\n'
  '  end\n'
  '  def units(xs: list[integer]): list[tuple[]] do\n'
  '    for x <- xs do\n'
  '      IO.puts(inspect(x))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(evens([1, 2, 3, 4])))\n'
  '    IO.puts(inspect(units([7])))\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 4]\n7\n[{}]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'c = true\n'
  'x = if c do for n <- [1, 2], do: n * 2 else [] end\n'
  'IO.puts(inspect(x))\n'
  'y = case x do\n'
  '  [] -> [0]\n'
  '  other -> for n <- other, do: n + 1\n'
  'end\n'
  'IO.puts(inspect(y))\n'
  'if c do\n'
  '  for n <- y do\n'
  '    IO.puts(inspect(n))\n'
  '  end\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 4]\n[3, 5]\n3\n5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2, 3], x > 5, do: x\n'
  'IO.puts(inspect(r))\n'
  'IO.puts(inspect(r == []))\n'
  '  end\n'
  'end\n',
  0,
  b'[]\ntrue\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = with ok(n) <- Integer.parse("3") do\n'
  '  for x <- 1..n, do: x * x\n'
  'else\n'
  '  _ -> []\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  'r2 = for t <- ["1", "x", "3"] do\n'
  '  with ok(n) <- Integer.parse(t) do\n'
  '    n\n'
  '  else\n'
  '    _ -> 0\n'
  '  end\n'
  'end\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 4, 9]\n[1, 0, 3]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2],\n'
  '        y <- [3, 4],\n'
  '        x + y > 4,\n'
  '        do:\n'
  '          x *\n'
  '            y\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[4, 6, 8]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2] do x end\n'
  'IO.puts(inspect(r))\n'
  'r2 = for(x <- [1, 2], y <- [3], do: x + y)\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2]\n[4, 5]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'xs = [1, 2, 3]\n'
  'total = for x <- xs, y <- xs, reduce: 0 do\n'
  '  acc -> acc + x * y\n'
  'end\n'
  'IO.puts(inspect(total))\n'
  'pairs = for x <- xs, reduce: %{0 => [0]} do\n'
  '  acc -> Map.put(acc, x, [x, x])\n'
  'end\n'
  'IO.puts(inspect(pairs))\n'
  '  end\n'
  'end\n',
  0,
  b'36\n%{0 => [0], 1 => [1, 1], 2 => [2, 2], 3 => [3, 3]}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2, 3], into: %{}, do: {rem(x, 2), x}\n'
  'IO.puts(inspect(r))\n'
  'r2 = for {k, v} <- %{1 => 2, 3 => 4}, into: %{}, do: {v, k}\n'
  'IO.puts(inspect(r2))\n'
  'r3 = for x <- ["b", "a"], into: %{"a" => 0}, do: {x, 1}\n'
  'IO.puts(inspect(r3))\n'
  '  end\n'
  'end\n',
  0,
  b'%{0 => 2, 1 => 3}\n%{2 => 1, 4 => 3}\n%{"a" => 1, "b" => 1}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r: list[option[integer]] = for x <- [1, 2], do: none\n'
  'IO.puts(inspect(r))\n'
  'r2: list[list[integer]] = for x <- [1, 2], do: []\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  0,
  b'[none, none]\n[[], []]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2], do: if x > 1 do "a" else "b" end\n'
  'IO.puts(inspect(r))\n'
  'r2 = for x <- [1, 2], do: (if x > 1, do: "a", else: "b")\n'
  'IO.puts(inspect(r2))\n'
  '  end\n'
  'end\n',
  0,
  b'["b", "a"]\n["b", "a"]\n',
  b''),
 ('defmodule M do\n  def main() do\nfor x <- [1, 2] do\n  IO.puts("a")\nend\n|> IO.inspect()\n  end\nend\n',
  0,
  b'a\na\n[{}, {}]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = (for x <- [1, 2], do: x) ++ [3]\n'
  'IO.puts(inspect(r))\n'
  'r2 = [0] ++ for x <- [1, 2], do: x\n'
  'IO.puts(inspect(r2))\n'
  'r3 = for x <- [1, 2] do x end |> Enum.sum()\n'
  'IO.puts(inspect(r3))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 3]\n[0, 1, 2]\n3\n',
  b''),
 ('defmodule M do\n'
  '  struct Shape do\n'
  '    name: string\n'
  '    sides: integer\n'
  '  end\n'
  '  def main() do\n'
  '    shapes = [%Shape{name: "tri", sides: 3}, %Shape{name: "sq", sides: 4}]\n'
  '    r = for %Shape{name: n, sides: s} <- shapes, s > 3, do: n\n'
  '    IO.puts(inspect(r))\n'
  '    r2 = for s <- shapes, do: s.sides\n'
  '    IO.puts(inspect(r2))\n'
  '    w = with %Shape{sides: 3, name: n} <- Enum.at(shapes, 1, %Shape{name: "none", sides: 0}) do\n'
  '      n\n'
  '    else\n'
  '      %Shape{name: other} -> "not a triangle: " <> other\n'
  '    end\n'
  '    IO.puts(w)\n'
  '  end\n'
  'end\n',
  0,
  b'["sq"]\n[3, 4]\nnot a triangle: sq\n',
  b''),
 ('defmodule M do\n'
  '  type Shape do\n'
  '    circle(radius: integer)\n'
  '    square(side: integer)\n'
  '    dot\n'
  '  end\n'
  '  def main() do\n'
  '    shapes = [Shape.circle(1), Shape.dot, Shape.square(2), Shape.circle(3)]\n'
  '    r = for Shape.circle(radius) <- shapes, do: radius\n'
  '    IO.puts(inspect(r))\n'
  '    w = with Shape.square(side) <- Enum.at(shapes, 0, Shape.dot) do\n'
  '      side\n'
  '    else\n'
  '      Shape.circle(r) -> 0 - r\n'
  '      Shape.dot -> 0\n'
  '    end\n'
  '    IO.puts(inspect(w))\n'
  '  end\n'
  'end\n',
  2,
  b'[1, 3]\n',
  b'<stdin>:11:9: no case branch matched\n  at M.main <closure> (<stdin>:11)\n  at M.main (<stdin>:11)\n'),
 ('defmodule M do\n  def main() do\nr = Enum.map(["a"], fn x -> IO.puts(x) end)\nIO.puts(inspect(r))\n  end\nend\n',
  0,
  b'a\n[{}]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = Enum.map(["a"], fn x -> IO.puts(x) end)\n'
  'IO.puts(inspect(r == [{}]))\n'
  '  end\n'
  'end\n',
  0,
  b'a\ntrue\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'counts: map[string, integer] = for word <- ["a", "b", "a"], reduce: %{} do\n'
  '  seen -> Map.put(seen, word, Map.get(seen, word, 0) + 1)\n'
  'end\n'
  'IO.puts(inspect(counts))\n'
  '  end\n'
  'end\n',
  0,
  b'%{"a" => 2, "b" => 1}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r: list[integer] = for x <- [1, 2, 3], reduce: [] do\n'
  '  acc -> [x | acc]\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[3, 2, 1]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r = for x <- [1, 2, 3] do\n'
  '  IO.puts(inspect(x))\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  'big = for x <- 1..20000, y <- [1, 2], rem(x, 2) == 0, do: x + y\n'
  'IO.puts(inspect(length(big)))\n'
  'IO.puts(inspect(Enum.sum(big)))\n'
  '  end\n'
  'end\n',
  0,
  b'1\n2\n3\n[{}, {}, {}]\n20000\n200050000\n',
  b''),
 ('defmodule M do\n  def main() do\nacc = [1]\nr = [0 | acc]\nIO.puts(inspect(r))\n  end\nend\n', 0, b'[0, 1]\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r: list[integer] = for x <- [1, 2, 3], reduce: [] do\n'
  '  acc -> [x] ++ acc\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[3, 2, 1]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r: map[integer, list[integer]] = for x <- [1, 2, 3], reduce: %{} do\n'
  '  acc -> Map.put(acc, rem(x, 2), Map.get(acc, rem(x, 2), []) ++ [x])\n'
  'end\n'
  'IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'%{0 => [2], 1 => [1, 3]}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'acc = [1]\n'
  'r = [0 | acc]\n'
  'IO.puts(inspect(r))\n'
  'r2 = [5, 6 | r]\n'
  'IO.puts(inspect(r2))\n'
  'r3 = [true || false | [false]]\n'
  'IO.puts(inspect(r3))\n'
  'r4 = [[1] |> Enum.sum() | [2]]\n'
  'IO.puts(inspect(r4))\n'
  'r5 = [[1 | [2]] | [[3]]]\n'
  'IO.puts(inspect(r5))\n'
  'r6 = ["a" | []]\n'
  'IO.puts(inspect(r6))\n'
  '  end\n'
  'end\n',
  0,
  b'[0, 1]\n[5, 6, 0, 1]\n[true, false]\n[1, 2]\n[[1, 2], [3]]\n["a"]\n',
  b''),
 ('defmodule M do\n  def main() do\nr = [1 | []]\nIO.puts(inspect(r))\n  end\nend\n', 0, b'[1]\n', b''),
 ('defmodule M do\n'
  '  def rev(xs: list[integer], acc: list[integer]): list[integer] do\n'
  '    case xs do\n'
  '      [] -> acc\n'
  '      [h | t] -> rev(t, [h | acc])\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(rev([1, 2, 3], [])))\n'
  '    r: list[integer] = for x <- [1, 2, 3], reduce: [] do\n'
  '      acc -> [x | acc]\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[3, 2, 1]\n[3, 2, 1]\n',
  b''),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      x\n'
  '    end |> Enum.map(fn v -> boom(v) end)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>'
  b':7)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    x = 3\n'
  '    r =\n'
  '      case x do\n'
  '        3 -> [1]\n'
  '        _ -> [2]\n'
  '      end |> Enum.map(fn v -> boom(v) end)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:12)\n  at M.main (<stdin'
  b'>:8)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 1\n'
  'case x do\n'
  '  1 -> ok({})\n'
  '  _ -> IO.puts("a")\n'
  'end\n'
  'IO.puts("end")\n'
  '  end\n'
  'end\n',
  0,
  b'end\n',
  b''),
 ('defmodule M do\n  def main() do\nwith ok(a) <- Integer.parse("5") do\n  ok({})\nend\nIO.puts("end")\n  end\nend\n',
  0,
  b'end\n',
  b''),
 ('defmodule M do\n  def main() do\nx = 1\ncase x do\n  1 -> ok(5)\n  _ -> ok(6)\nend\nIO.puts("end")\n  end\nend\n',
  0,
  b'end\n',
  b''),
 ('defmodule M do\n  def main() do\nx = 1\nif x > 0 do ok(5) else ok(6) end\nIO.puts("end")\n  end\nend\n',
  0,
  b'end\n',
  b''),
 ('defmodule M do\n  def main() do\nx = 1\nif x > 0 do\n  ok(5)\nend\nIO.puts("end")\n  end\nend\n', 0, b'end\n', b''),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    a1 = 1\n'
  '    a2 = 2\n'
  '    a3 = 3\n'
  '    a4 = 4\n'
  '    a5 = 5\n'
  '    a6 = 6\n'
  '    a7 = 7\n'
  '    a8 = 8\n'
  '    a9 = 9\n'
  '    r = for {x, y} <- [{1, 2}, {3, 4}], z <- [x, y], w <- [z], z > 0 do\n'
  '      a1 + a2 + a3 + a4 + a5 + a6 + a7 + a8 + a9 + x + y + z + w\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '    b1 = 1\n'
  '    b2 = 2\n'
  '    b3 = 3\n'
  '    r2 = for {x, y} <- [{1, 2}, {3, 4}], z <- [x, y], reduce: 0 do\n'
  '      acc -> acc + b1 + b2 + b3 + x + y + z\n'
  '    end\n'
  '    IO.puts(inspect(r2))\n'
  '    r3 = for p <- [1, 2], uniq: true do\n'
  '      for q <- [p, p] do\n'
  '        with ok(n) <- Integer.parse(inspect(q)) do\n'
  '          n + a9 + b3\n'
  '        else\n'
  '          _ -> 0\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r3))\n'
  '    r4 = for p <- [1, 2], q <- [3, 4], t <- [5], u <- [6] do\n'
  '      boom(p + q + t + u)\n'
  '    end\n'
  '    IO.puts(inspect(r4))\n'
  '  end\n'
  'end\n',
  2,
  b'[50, 52, 58, 60]\n54\n[[13, 13], [14, 14]]\n',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:38)\n  at M.main <closur'
  b'e> (<stdin>:39)\n  at M.main <closure> (<stdin>:48)\n  at M.main <closure> (<stdin>:45)\n  at M.main <closure> (<st'
  b'din>:42)\n  at M.main <closure> (<stdin>:39)\n  at M.main (<stdin>:49)\n'),
 ('defmodule M do\n'
  '  def classify(xs: list[integer]): map[string, list[integer]] do\n'
  '    for x <- xs, reduce: %{"even" => [], "odd" => []} do\n'
  '      acc ->\n'
  '        key = if rem(x, 2) == 0 do "even" else "odd" end\n'
  '        Map.put(acc, key, Map.get(acc, key, []) ++ [x])\n'
  '    end\n'
  '  end\n'
  '  def table(n: integer): list[string] do\n'
  '    for i <- 1..n do\n'
  '      row = for j <- 1..n, do: Integer.to_string(i * j)\n'
  '      Enum.join(row, " ")\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(classify([1, 2, 3, 4])))\n'
  '    for line <- table(3) do\n'
  '      IO.puts(line)\n'
  '    end\n'
  '    words = ["apple", "bob", "cat"]\n'
  '    lens = for w <- words, into: %{}, do: {w, String.length(w)}\n'
  '    IO.puts(inspect(lens))\n'
  '    for {w, n} <- lens, n > 3 do\n'
  '      IO.puts("#{w}: #{n}")\n'
  '    end\n'
  '    flat = for xs <- [[1, 2], [3]], x <- xs, do: x * 10\n'
  '    IO.puts(inspect(flat))\n'
  '    str = for c <- String.graphemes("abc"), into: "", do: String.upcase(c)\n'
  '    IO.puts(str)\n'
  '  end\n'
  'end\n',
  0,
  b'%{"even" => [2, 4], "odd" => [1, 3]}\n1 2 3\n2 4 6\n3 6 9\n%{"apple" => 5, "bob" => 3, "cat" => 3}\napple: 5\n[10,'
  b' 20, 30]\nABC\n',
  b''),
 ('defmodule M do\n'
  '  def boom(n: integer): result[integer, string] do\n'
  '    [a] = [n, n]\n'
  '    ok(a)\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      with ok(v) <- boom(x) do\n'
  '        v\n'
  '      else\n'
  '        _ -> 0\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:8)\n  at M.main <closure'
  b'> (<stdin>:9)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:13)\n'),
 ('defmodule M do\n'
  '  def half(n: integer): result[integer, string] do\n'
  '    if rem(n, 2) == 0 do ok(div(n, 2)) else error("odd") end\n'
  '  end\n'
  '  def main() do\n'
  '    r: list[result[string, string]] = for x <- [4, 3, 2] do\n'
  '      with ok(1) <- half(x) do\n'
  '        ok("one")\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:7:21: no with clause matched\n  at M.main <closure> (<stdin>:7)\n  at M.main <closure> (<stdin>:7)\n  at M.'
  b'main <closure> (<stdin>:8)\n  at M.main <closure> (<stdin>:8)\n  at M.main (<stdin>:12)\n'),
 ('defmodule M do\n'
  '  def classify(xs: list[integer]): map[string, list[integer]] do\n'
  '    for x <- xs, reduce: %{"even" => [], "odd" => []} do\n'
  '      acc ->\n'
  '        key = if rem(x, 2) == 0 do "even" else "odd" end\n'
  '        Map.put(acc, key, Map.get(acc, key, []) ++ [x])\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(classify([1, 2, 3, 4])))\n'
  '  end\n'
  'end\n',
  0,
  b'%{"even" => [2, 4], "odd" => [1, 3]}\n',
  b''),
 ('defmodule M do\n'
  '  def table(n: integer): list[string] do\n'
  '    for i <- 1..n do\n'
  '      row = for j <- 1..n, do: Integer.to_string(i * j)\n'
  '      Enum.join(row, " ")\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    for line <- table(3) do\n'
  '      IO.puts(line)\n'
  '    end\n'
  '  end\n'
  'end\n',
  0,
  b'1 2 3\n2 4 6\n3 6 9\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'words = ["apple", "bob", "cat"]\n'
  'lens = for w <- words, into: %{}, do: {w, String.length(w)}\n'
  'IO.puts(inspect(lens))\n'
  'for {w, n} <- lens, n > 3 do\n'
  '  IO.puts("#{w}: #{n}")\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'%{"apple" => 5, "bob" => 3, "cat" => 3}\napple: 5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'str = for c <- String.graphemes("abc"), into: "", do: String.upcase(c)\n'
  'IO.puts(str)\n'
  '  end\n'
  'end\n',
  0,
  b'ABC\n',
  b''),
 ('defmodule M do\n'
  '  def classify(xs: list[integer]): map[string, list[integer]] do\n'
  '    start: map[string, list[integer]] = %{"even" => [], "odd" => []}\n'
  '    Enum.reduce(xs, start, fn x, acc ->\n'
  '        key = if rem(x, 2) == 0 do "even" else "odd" end\n'
  '        Map.put(acc, key, Map.get(acc, key, []) ++ [x])\n'
  '    end)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(classify([1, 2, 3, 4])))\n'
  '  end\n'
  'end\n',
  0,
  b'%{"even" => [2, 4], "odd" => [1, 3]}\n',
  b''),
 ('defmodule M do\n'
  '  def classify(xs: list[integer]): map[string, list[integer]] do\n'
  '    r: map[string, list[integer]] = for x <- xs, reduce: %{"even" => [], "odd" => []} do\n'
  '      acc ->\n'
  '        key = if rem(x, 2) == 0 do "even" else "odd" end\n'
  '        Map.put(acc, key, Map.get(acc, key, []) ++ [x])\n'
  '    end\n'
  '    r\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(classify([1, 2, 3, 4])))\n'
  '  end\n'
  'end\n',
  0,
  b'%{"even" => [2, 4], "odd" => [1, 3]}\n',
  b''),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      unless x > 5 do\n'
  '        boom(x)\n'
  '      else\n'
  '        0\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure'
  b'> (<stdin>:13)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:17)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      cond do\n'
  '        x > 5 -> 1\n'
  '        x > 0 -> boom(x)\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closur'
  b'e> (<stdin>:11)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:15)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      if x > 5, do: 1, else: boom(x)\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:8)\n  at M.main <closure'
  b'> (<stdin>:10)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:14)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      if x > 5 do\n'
  '        1\n'
  '      else\n'
  '        if x > 7 do\n'
  '          2\n'
  '        else\n'
  '          y = x\n'
  '          boom(y)\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:15)\n  at M.main <closur'
  b'e> (<stdin>:18)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:22)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      with ok(v) <- Integer.parse("1") do\n'
  '        boom(v)\n'
  '      else\n'
  '        _ -> 0\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:9)\n  at M.main <closure'
  b'> (<stdin>:9)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:13)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    for x <- [1, 2] do\n'
  '      IO.puts("a")\n'
  '      if x > 0 do\n'
  '        IO.puts(inspect(boom(x)))\n'
  '      end\n'
  '    end\n'
  '  end\n'
  'end\n',
  2,
  b'a\n',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closur'
  b'e> (<stdin>:10)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:14)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      for y <- [x] do\n'
  '        for z <- [y] do\n'
  '          boom(z)\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closur'
  b'e> (<stdin>:11)\n  at M.main <closure> (<stdin>:11)\n  at M.main <closure> (<stdin>:15)\n  at M.main <closure> (<st'
  b'din>:16)\n  at M.main <closure> (<stdin>:10)\n  at M.main <closure> (<stdin>:20)\n  at M.main <closure> (<stdin>:21'
  b')\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:25)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2] do\n'
  '      for y <- [x], do: y\n'
  '    end\n'
  '    z = boom(1)\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main (<stdin>:10)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): boolean do\n'
  '    [a] = [n, n]\n'
  '    a > 0\n'
  '  end\n'
  '  def main() do\n'
  '    r = for x <- [1, 2], y <- [x], boom(y) do\n'
  '      for z <- [y] do\n'
  '        z\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:15)\n  at M.main <closur'
  b'e> (<stdin>:12)\n  at M.main <closure> (<stdin>:9)\n  at M.main (<stdin>:21)\n'),
 ('defmodule M do\n'
  '  def size(n: integer): integer do\n'
  '    n + 1\n'
  '  end\n'
  '  def main() do\n'
  '    for x <- 1..400 do\n'
  '      if rem(x, 2) == 0 do\n'
  '        for y <- 1..400 do\n'
  '          size(x * y)\n'
  '        end\n'
  '      else\n'
  '        case x do\n'
  '          1 -> for y <- 1..400 do\n'
  '            size(y)\n'
  '          end\n'
  '          _ ->\n'
  '            with true <- x > 2 do\n'
  '              for y <- 1..400 do\n'
  '                size(y)\n'
  '              end\n'
  '            end\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '    IO.puts("done")\n'
  '    if size(1) == 2 do\n'
  '      for y <- 1..3 do\n'
  '        IO.puts(inspect(y))\n'
  '      end\n'
  '    end\n'
  '  end\n'
  'end\n',
  0,
  b'done\n1\n2\n3\n',
  b''),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def main() do\n'
  '    x = 1\n'
  '    if x > 0 do\n'
  '      for y <- [x] do\n'
  '        if y > 5 do\n'
  '          boom(1)\n'
  '        else\n'
  '          boom(y)\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.main <closure> (<stdin>:13)\n  at M.main <closur'
  b'e> (<stdin>:11)\n  at M.main <closure> (<stdin>:11)\n  at M.main (<stdin>:15)\n'),
 ('defmodule M do\n'
  '  def boom(n: integer): integer do\n'
  '    [a] = [n, n]\n'
  '    a\n'
  '  end\n'
  '  def f(x: integer): list[integer] do\n'
  '    if x > 0 do\n'
  '      for y <- [x] do\n'
  '        if y > 5 do\n'
  '          boom(1)\n'
  '        else\n'
  '          boom(y)\n'
  '        end\n'
  '      end\n'
  '    else\n'
  '      []\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: pattern match failed\n  at M.boom (<stdin>:3)\n  at M.f <closure> (<stdin>:12)\n  at M.f <closure> (<s'
  b'tdin>:14)\n  at M.f <closure> (<stdin>:10)\n  at M.f (<stdin>:18)\n  at M.main (<stdin>:20)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  '    x = 3\n'
  '    r = if x > 0 do\n'
  '      for y <- [x] do\n'
  '        y * 2\n'
  '      end\n'
  '    else\n'
  '      []\n'
  '    end\n'
  '    IO.puts(inspect(r))\n'
  '    f = fn(n: integer): list[integer] do\n'
  '      if n > 0 do\n'
  '        for y <- [n] do\n'
  '          y * 3\n'
  '        end\n'
  '      else\n'
  '        []\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(f.(2)))\n'
  '    case x do\n'
  '      3 -> for y <- [1] do IO.puts(inspect(y)) end\n'
  '      _ -> IO.puts("no")\n'
  '    end\n'
  '    cond do\n'
  '      x > 1 -> for y <- [2] do IO.puts(inspect(y)) end\n'
  '      true -> IO.puts("no")\n'
  '    end\n'
  '  end\n'
  'end\n',
  0,
  b'[6]\n[6]\n1\n2\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    r = for a <- [1, 2] do\n'
  '      for b <- [1, 2] do\n'
  '        for c <- [1, 2] do\n'
  '          for d <- [1, 2] do\n'
  '            for e <- [1, 2] do\n'
  '              for f <- [1, 2] do\n'
  '                a + b + c + d + e + f\n'
  '              end\n'
  '            end\n'
  '          end\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '    IO.puts(inspect(length(r)))\n'
  '    for a <- [1, 2] do\n'
  '      for b <- [1, 2] do\n'
  '        for c <- [1, 2] do\n'
  '          for d <- [1, 2] do\n'
  '            for e <- [1, 2] do\n'
  '              for f <- [1, 2] do\n'
  '                IO.write(inspect(a + b + c + d + e + f))\n'
  '              end\n'
  '            end\n'
  '          end\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '    IO.puts("")\n'
  '  end\n'
  'end\n',
  0,
  b'2\n67787889788989910788989910899109101011788989910899109101011899109101011910101110111112\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    big = for x <- 1..100000, rem(x, 3) == 0, do: x * 2\n'
  '    IO.puts(inspect(length(big)))\n'
  '    IO.puts(inspect(Enum.sum(big)))\n'
  '    total = for x <- 1..100000, reduce: 0 do\n'
  '      acc -> acc + x\n'
  '    end\n'
  '    IO.puts(inspect(total))\n'
  '    for x <- 1..100000 do\n'
  '      if x == 99999 do IO.puts("near") end\n'
  '    end\n'
  '  end\n'
  'end\n',
  0,
  b'33333\n3333366666\n5000050000\nnear\n',
  b''),
 ('defmodule M do\n'
  '  def size(n: integer): integer do\n'
  '    n + 1\n'
  '  end\n'
  '  def walk(xs: list[integer]): integer do\n'
  '    for x <- xs do\n'
  '      if rem(x, 2) == 0 do\n'
  '        for y <- xs do\n'
  '          size(x * y)\n'
  '        end\n'
  '      else\n'
  '        case x do\n'
  '          1 -> for y <- xs do\n'
  '            size(y)\n'
  '          end\n'
  '          _ ->\n'
  '            with true <- x > 2 do\n'
  '              for y <- xs do\n'
  '                size(y)\n'
  '              end\n'
  '            end\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '    length(xs)\n'
  '  end\n'
  '  def main() do\n'
  '    xs = Enum.to_list(1..1500)\n'
  '    IO.puts(inspect(walk(xs)))\n'
  '    for x <- xs do\n'
  '      if x > 0 do\n'
  '        for y <- xs do\n'
  '          size(y)\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '    IO.puts("done")\n'
  '  end\n'
  'end\n',
  0,
  b'1500\ndone\n',
  b'')]
# programs the pinned compiler rejects
REJECTS=['defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("3"), ok(b) <- Integer.parse("4") do\n'
 '  ok(a + b)\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("3"), ok(b) <- Integer.parse("x") do\n'
 '  ok(a + b)\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("3"), ok(b) <- Integer.parse("x") do\n'
 '  a + b\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with some(a) <- List.first([1,2]) do\n'
 '  ok(a + 1)\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with a <- 5, b = a + 1, c <- b * 2 do\n'
 '  c\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("7"), a > 5 do\n'
 '  a\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("7"), do: ok(a * 2)\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("x"), do: ok(a * 2), else: (error(_) -> ok(0))\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nr = with {1, x} <- {2, 3} do\n  x\nend\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = with 1 <- 2 do\n  "a"\nend\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = with do\n  1\nend\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("7") do\n'
 '  a\n'
 'else\n'
 '  "x" -> 2\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def half(n: integer): result[integer, string] do\n'
 '    if rem(n, 2) == 0 do ok(div(n, 2)) else error("odd #{n}") end\n'
 '  end\n'
 '  def both(n: integer): result[string, atom] do\n'
 '    with ok(h) <- half(n) do\n'
 '      ok("x")\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(inspect(both(8)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'a = 1\n'
 'r = with ok(a) <- Integer.parse("3") do\n'
 '  a\n'
 'else\n'
 '  _ -> 0\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("3") do\n'
 '  a\n'
 'else\n'
 '  error(a) -> 0\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 'IO.puts(inspect(a))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    r =\n'
 '      with ok(a) <- Integer.parse("3"),\n'
 '           [b] <- [a, a] do\n'
 '        a + b\n'
 '      else\n'
 '        [] -> 0\n'
 '      end\n'
 '    IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    with ok(a) <- Integer.parse("3"),\n'
 '           [b] <- [a, a] do\n'
 '        IO.puts("a")\n'
 '      else\n'
 '        [] -> IO.puts("b")\n'
 '      end\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("3") do\n'
 '  a\n'
 'else\n'
 '  error(e) -> "s"\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("3") do\n'
 '  a\n'
 'else\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with x <- 5, y <- x + 1 do\n'
 '  x * y\n'
 'else\n'
 '  garbage(1) -> 7\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nr = with ok(a) <- Integer.parse("3") do a end\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("3") do\n'
 '  a\n'
 'else\n'
 '  error(e) -> 1\n'
 '  what is this ->\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nr = with x <- 5 do\n  x\nelse\n  y -> \nend\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = with ok(a) <- Integer.parse("3"), do\n  a\nend\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = with ok(a) <- Integer.parse("3") do\n  a\nelse\n  error(e) -> 1\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = with ok(a) <- 5 do\n  a\nelse\n  _ -> 0\nend\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'x = 5\n'
 'r = with ok(a) <- Integer.parse("3") do\n'
 '  a + x\n'
 'else\n'
 '  error(x) -> 0\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("3"), ok(a) <- Integer.parse("4") do\n'
 '  a\n'
 'else\n'
 '  _ -> 0\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def go(t: string) do\n'
 '    with ok(a) <- Integer.parse(t) do\n'
 '      IO.puts("got #{a}")\n'
 '    else\n'
 '      error(e) when String.length(e) > 100 -> IO.puts("long")\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    go("5")\n'
 '    go("q")\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nwith ok(a) <- Integer.parse("5") do\n  a + 1\nend\nIO.puts("end")\n  end\nend\n',
 'defmodule M do\n  def main() do\nwith ok(a) <- Integer.parse("5") do\n  a + 1\nelse\n  _ -> 0\nend\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = with ok(a) <- Integer.parse("5") do\n'
 '  IO.puts("x")\n'
 'else\n'
 '  _ -> IO.puts("y")\n'
 'end\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nr = with x <- 5 do\n  none\nend\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = with [x] <- [] do\n  x\nelse\n  _ -> 0\nend\n  end\nend\n',
 'defmodule M do\n  def main() do\nf = fn t -> with ok(a) <- Integer.parse(t), do: a end\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = for x <- [1, 2, 3], reduce: 0 do\n'
 '  0 -> x\n'
 '  1 -> 5\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = for x <- [1, 2, 3], reduce: [] do\n'
 '  acc -> acc ++ [x]\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = for x <- [1, 2, 3], reduce: 0 do\n'
 '  acc -> "s"\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nr = for x <- 5, do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- "abc", do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x > 1, x <- [1,2], do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1,2], x, do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = for x <- [1,2], into: %{}, uniq: true, do: {x, x}\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nr = for x <- [1,2], foo: 1, do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1,2], into: %{}, do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1,2], uniq: 1, do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [], do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = 5\nr = for x <- [1, 2], do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2], x <- [3], do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2], do: x\nIO.puts(inspect(x))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'for x <- [1, 2], do: IO.puts(inspect(x))\n'
 'for x <- [1, 2], do: x\n'
 'IO.puts("done")\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nfor x <- [1, 2] do\n  x + 1\nend\nIO.puts("done")\n  end\nend\n',
 'defmodule M do\n  def main() do\nfor x <- [1, 2] do\n  x + 1\nend\n  end\nend\n',
 'defmodule M do\n  def main() do\nfor x <- [1, 2], do: x\nIO.puts("done")\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = for x <- [1, 2] do\n'
 '  if x > 1 do IO.puts("a") else IO.puts("b") end\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = for x <- [1, 2] do\n'
 '  if x > 1 do IO.puts("a") end\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nfor x <- [1, 2] do\n  if x > 1 do 5 else 6 end\nend\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2] do\n  y = x\nend\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2] do\nend\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'fs = [fn(a: integer): integer do a end]\n'
 'r = for f <- fs, uniq: true, do: f\n'
 'IO.puts(inspect(length(r)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2], into: ["a"], do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2], into: "", do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2], into: 5, do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r = for x <- [1, 2], into: %{"a" => 1}, do: {x, x}\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2], reduce: 0, do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2], reduce: 0 do\nend\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- {1, 2}, do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- some(1), do: x\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for {a, b} <- [1, 2], do: a\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for(x <- [1, 2]) do\n  x\nend\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2], do: x, into: []\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2] do\n  x\nelse\n  y\nend\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = for x <- [1, 2], uniq: true, into: [], do: x\n  end\nend\n',
 'defmodule M do\n  def main() do\nnone_list = for x <- [1, 2], do: none\nIO.puts(inspect(none_list))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'r: list[string] = for x <- [1, 2, 3], reduce: [] do\n'
 '  acc -> [x | acc]\n'
 'end\n'
 'IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nr = [1 | ["a"]]\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nr = [1 | 2]\nIO.puts(inspect(r))\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = 1\ncase x do\n  1 -> 5\n  _ -> IO.puts("a")\nend\nIO.puts("end")\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = 1\nif x > 0 do\n  5\nend\nIO.puts("end")\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = 1\ncase x do\n  1 -> 5\n  _ -> 6\nend\nIO.puts("end")\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'with ok(a) <- Integer.parse("5") do\n'
 '  a + 1\n'
 'else\n'
 '  _ -> IO.puts("x")\n'
 'end\n'
 'IO.puts("end")\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nx = 1\nif x > 0 do 5 else 6 end\nIO.puts("end")\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = 1\nif x > 0 do\n  5\nelse\n  6\nend\nIO.puts("end")\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'x = some(1)\n'
 'case x do\n'
 '  some(a) -> 5\n'
 '  none -> 6\n'
 'end\n'
 'IO.puts("end")\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nx = 1\ncond do\n  x > 0 -> 5\n  true -> 6\nend\nIO.puts("end")\n  end\nend\n',
 'defmodule M do\n'
 '  def firsts[a](xs: list[list[a]]): list[a] do\n'
 '    for [h | _] <- xs, do: h\n'
 '  end\n'
 '  def distinct[a](xs: list[a]): list[a] do\n'
 '    for x <- xs, uniq: true, do: x\n'
 '  end\n'
 '  def pairs[a, b](xs: list[a], ys: list[b]): list[tuple[a, b]] do\n'
 '    for x <- xs, y <- ys, do: {x, y}\n'
 '  end\n'
 '  def keep[a](xs: list[option[a]], other: a): list[a] do\n'
 '    for x <- xs do\n'
 '      with some(v) <- x do\n'
 '        v\n'
 '      else\n'
 '        none -> other\n'
 '      end\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(inspect(firsts([[1, 2], [], [3]])))\n'
 '    IO.puts(inspect(firsts([["a"], ["b", "c"]])))\n'
 '    IO.puts(inspect(distinct(["a", "b", "a"])))\n'
 '    IO.puts(inspect(distinct([{1, 2}, {1, 2}, {2, 1}])))\n'
 '    IO.puts(inspect(pairs([1, 2], ["x"])))\n'
 '    IO.puts(inspect(keep([some(1), none], 0)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def boom(n: integer): integer do\n'
 '    [a] = [n, n]\n'
 '    a\n'
 '  end\n'
 '  def run(xs: list[integer]): result[integer, string] do\n'
 '    with [a, b] <- xs,\n'
 '         total = 0,\n'
 '         ok(c) <- Integer.parse("7") do\n'
 '      ok(a + b + c)\n'
 '    else\n'
 '      _ -> error("no")\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(inspect(run([1, 2])))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    f = fn(n: integer): list[integer] do\n'
 '      base = n * 10\n'
 '      for x <- 1..n, y <- [base], do: x + y\n'
 '    end\n'
 '    IO.puts(inspect(f.(3)))\n'
 '    g = fn xs -> for {a, b} <- xs, a < b, do: b - a end\n'
 '    IO.puts(inspect(Enum.map([[{1, 5}, {7, 2}], [{0, 1}]], g)))\n'
 '    Enum.each([1, 2], fn n ->\n'
 '      for x <- 1..n do\n'
 '        IO.puts("#{n}/#{x}")\n'
 '      end\n'
 '    end)\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def show(xs: list[integer]) do\n'
 '    for x <- xs do\n'
 '      IO.puts(inspect(x))\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    show([1, 2])\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def show(xs: list[integer]) do\n'
 '    for x <- xs do\n'
 '      IO.puts(inspect(x))\n'
 '    end\n'
 '    IO.puts("end")\n'
 '  end\n'
 '  def main() do\n'
 '    show([1, 2])\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def show(xs: list[integer]) do\n'
 '    IO.puts("start")\n'
 '  end\n'
 '  def main() do\n'
 '    show([1, 2])\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def show(xs: list[integer]) do\n'
 '    if length(xs) > 1 do\n'
 '      IO.puts("many")\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    show([1, 2])\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def show(xs: list[integer]) do\n'
 '    if length(xs) > 1 do\n'
 '      for x <- xs do\n'
 '        IO.puts(inspect(x))\n'
 '      end\n'
 '    end\n'
 '  end\n'
 '  def main() do\n'
 '    show([1, 2])\n'
 '  end\n'
 'end\n']


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-comprehensions-') as d:
        out=Path(d)/'out'
        for source,status,stdout,stderr in RUNS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    failing=sum(1 for run in RUNS if run[1]==2)
    print(f'PASS comprehensions: {len(RUNS)} programs run as the pinned compiler runs them ({failing} end in a failure and its trace), {len(REJECTS)} rejected; with clauses, else arms and values that do not match, for over lists, ranges and maps, filters, into, uniq and reduce, as values and as statements')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
