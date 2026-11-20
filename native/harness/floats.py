#!/usr/bin/env python3
"""Floats: every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule M do\n'
  '  def main() do\n'
  'x = 1.5\n'
  'y: float = 0.25\n'
  'IO.puts(to_string(x + y))\n'
  'IO.puts(to_string(x - y))\n'
  'IO.puts(to_string(x * y))\n'
  'IO.puts(to_string(x / y))\n'
  'IO.puts(to_string(-x))\n'
  'IO.puts(to_string(x ** y))\n'
  'IO.puts(to_string(1.0e3))\n'
  'IO.puts("#{x} and #{y} #{x == y} #{x != y} #{x < y} #{x <= y} #{x > y} #{x >= y}")\n'
  'IO.puts(inspect(x))\n'
  '  end\n'
  'end\n',
  0,
  b'1.75\n1.25\n0.375\n6.0\n-1.5\n1.1066819197003217\n1.0e3\n1.5 and 0.25 false true false false true true\n'
  b'1.5\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1..3))\nIO.puts(inspect(Enum.sum(1..3)))\n  end\nend\n',
  0,
  b'1..3\n6\n',
  b''),
 ('defmodule M do\n  def main() do\nx = 1.0\nIO.puts(to_string(x / 0.0))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:21: division by zero\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nx = 0.0\ny = 0.0\nIO.puts(to_string(x / y))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:5:21: division by zero\n  at M.main (<stdin>:5)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Float.from_integer(3)))\n'
  'IO.puts(inspect(round(2.5)))\n'
  'IO.puts(inspect(round(-2.5)))\n'
  'IO.puts(inspect(trunc(-2.7)))\n'
  'IO.puts(inspect(ceil(2.1)))\n'
  'IO.puts(inspect(floor(-2.1)))\n'
  'IO.puts(inspect(abs(-2.5)))\n'
  'IO.puts(inspect(abs(2.5)))\n'
  'IO.puts(inspect(abs(-0.0)))\n'
  'IO.puts(Float.to_string(2.5))\n'
  'IO.puts(Float.to_string(1000.0))\n'
  'IO.puts(Float.to_string(1250.0))\n'
  'IO.puts(inspect(1000.0))\n'
  'IO.puts(inspect(Float.parse("2.5")))\n'
  'IO.puts(inspect(Float.parse("abc")))\n'
  'IO.puts(inspect(Float.parse("1e999")))\n'
  'IO.puts(inspect(Float.parse("inf")))\n'
  'IO.puts(inspect(Float.round(3.14159, 2)))\n'
  'IO.puts(inspect(Float.round(2.5)))\n'
  'IO.puts(inspect(Float.round(1.15, 1)))\n'
  'IO.puts(inspect(Float.ceil(2.11, 1)))\n'
  'IO.puts(inspect(Float.ceil(2.1)))\n'
  'IO.puts(inspect(Float.ceil(3.7, 1)))\n'
  'IO.puts(inspect(Float.ceil(12.5, 1)))\n'
  'IO.puts(inspect(Float.floor(2.19, 1)))\n'
  'IO.puts(inspect(Float.floor(0.3, 1)))\n'
  'IO.puts(inspect(Float.floor(2.7)))\n'
  'IO.puts(inspect(Float.pow(2.0, 3.0)))\n'
  'IO.puts(inspect(Float.ratio(0.75)))\n'
  'IO.puts(inspect(Float.max_finite() > 1.0e308))\n'
  'IO.puts(inspect(Float.min_finite() < -1.0e308))\n'
  'IO.puts(inspect(Float.max_finite()))\n'
  'IO.puts(inspect(Float.min_finite()))\n'
  '  end\n'
  'end\n',
  0,
  b'3.0\n3\n-3\n-2\n3\n-3\n2.5\n2.5\n-0.0\n2.5\n1.0e3\n1250.0\n1000.0\nok(2.5)\nerror("\\"abc\\" is not a fl'
  b'oat")\nerror("\\"1e999\\" is not a float")\nerror("\\"inf\\" is not a float")\n3.14\n3.0\n1.1\n2.2\n3.0'
  b'\n3.8\n12.5\n2.1\n0.2\n2.0\n8.0\n{3, 4}\ntrue\ntrue\n1.7976931348623157e308\n-1.7976931348623157e308\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(round(1.0e300)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: float out of integer range\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(trunc(-1.0e19)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: float out of integer range\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n  def main() do\nx = 0.0\nIO.puts(inspect(floor(x / x * 1.0)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:25: division by zero\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(1.5, 16)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: precision must be between 0 and 15\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(1.5, -1)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: precision must be between 0 and 15\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.ratio(1.0e300)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: Float.ratio: the fraction does not fit in 64-bit integers\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n  def main() do\nx = 1.0e308\nIO.puts(inspect(Float.ratio(x * 10.0)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:17: Float.ratio needs a finite float\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(String.to_float("2.5")))\n'
  'IO.puts(inspect(String.to_float("1e3")))\n'
  'IO.puts(inspect(String.to_float("inf")))\n'
  '  end\n'
  'end\n',
  2,
  b'2.5\n1000.0\n',
  b'<stdin>:5:17: "inf" is not a float\n  at M.main (<stdin>:5)\n'),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(String.to_float("x\\ty")))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: "x\\ty" is not a float\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n'
  '  def to_fahrenheit(celsius: float): float do\n'
  '    celsius * 1.8 + 32.0\n'
  '  end\n'
  '  def area(width: float, height: float): float do\n'
  '    width * height\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(to_string(to_fahrenheit(100.0)))\n'
  '    IO.puts(to_string(area(2.5, 4.0)))\n'
  '    count = 42\n'
  '    assert(Float.from_integer(count) + 0.5 == 42.5)\n'
  '    r = case 1.5 do\n'
  '      1.5 -> "one and a half"\n'
  '      _ -> "other"\n'
  '    end\n'
  '    IO.puts(r)\n'
  '  end\n'
  'end\n',
  0,
  b'212.0\n10.0\none and a half\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.sum(1..100)))\n'
  'IO.puts(inspect(Enum.sum([1.5, 2.5])))\n'
  '  end\n'
  'end\n',
  0,
  b'5050\n4.0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.sum([1, 2])))\n'
  'IO.puts(inspect(Enum.sum([1.5, 2.5])))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n4.0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'assert_in_delta(0.1 + 0.2, 0.3, 0.0001)\n'
  'IO.puts("ok")\n'
  'assert_in_delta(1.0, 2.0, 0.5)\n'
  '  end\n'
  'end\n',
  2,
  b'ok\n',
  b'<stdin>:5:1: assertion failed\n     left:  1.0\n     right: 2.0\n     delta: 0.5\n  at M.main (<stdin>:5'
  b')\n'),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.sum([1.5, 2.5])))\n  end\nend\n', 0, b'4.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.sum([1.5, 2.5, 0.1])))\n  end\nend\n',
  0,
  b'4.1\n',
  b''),
 ('defmodule M do\n  def main() do\nx = [1.5, 2.5]\nIO.puts(inspect(x))\n  end\nend\n',
  0,
  b'[1.5, 2.5]\n',
  b''),
 ('defmodule M do\n  def main() do\nx = [1.5, 2.5, 3.5]\nIO.puts(inspect(x))\n  end\nend\n',
  0,
  b'[1.5, 2.5, 3.5]\n',
  b''),
 ('defmodule M do\n  def main() do\nx = {1.5, 2.5}\nIO.puts(inspect(x))\n  end\nend\n',
  0,
  b'{1.5, 2.5}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(min(1.5, 2.5)))\n'
  'IO.puts(inspect(max(1.5, 2.5)))\n'
  'IO.puts(inspect(min(0.0, -0.0)))\n'
  'IO.puts(inspect(max(0.0, -0.0)))\n'
  'IO.puts(inspect(max(-0.0, 0.0)))\n'
  '  end\n'
  'end\n',
  0,
  b'1.5\n2.5\n0.0\n0.0\n-0.0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect([1.5, 2.5] == [1.5, 2.5]))\n'
  'IO.puts(inspect([1.5, 2.5] == [1.5, 2.6]))\n'
  'IO.puts(inspect({1.5, "a"} == {1.5, "a"}))\n'
  'IO.puts(inspect([0.0] == [-0.0]))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\ntrue\ntrue\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect([1.5, -0.0, 1.0e20, 1.0e-5]))\n'
  'IO.puts(inspect({1.5, %{"a" => 2.5}, some(0.1)}))\n'
  '  end\n'
  'end\n',
  0,
  b'[1.5, -0.0, 1.0e20, 1.0e-5]\n{1.5, %{"a" => 2.5}, some(0.1)}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.sum([1.5, 2.5, 0.1])))\n'
  'l: list[float] = []\n'
  'IO.puts(inspect(Enum.sum(l)))\n'
  '  end\n'
  'end\n',
  0,
  b'4.1\n0.0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(1.5 in [1.5, 2.5]))\n'
  'IO.puts(inspect(1.6 in [1.5, 2.5]))\n'
  'r: result[float, string] = ok(1.5)\n'
  'IO.puts(inspect(r))\n'
  'o: option[float] = none\n'
  'IO.puts(inspect(o))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\nok(1.5)\nnone\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 0.0\n'
  'nan = x / 1.0 * (1.0e308 * x)\n'
  'IO.puts(inspect(nan))\n'
  '  end\n'
  'end\n',
  0,
  b'0.0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 1.0e308\n'
  'inf = x * 10.0\n'
  'nan = inf - inf\n'
  'IO.puts(inspect(nan == nan))\n'
  'IO.puts(inspect(nan != nan))\n'
  'IO.puts(inspect(nan < 1.0))\n'
  'IO.puts(inspect(nan > 1.0))\n'
  'IO.puts(inspect(nan <= nan))\n'
  'IO.puts(inspect([nan] == [nan]))\n'
  'IO.puts(inspect(min(nan, 1.0)))\n'
  'IO.puts(inspect(min(1.0, nan)))\n'
  'IO.puts(inspect(max(nan, 1.0)))\n'
  'IO.puts(inspect(max(1.0, nan)))\n'
  'IO.puts(inspect(abs(nan)))\n'
  'IO.puts(inspect(abs(-inf)))\n'
  'IO.puts(inspect(-inf))\n'
  'IO.puts(to_string(-inf))\n'
  'IO.puts(inspect(Float.round(inf, 2)))\n'
  'IO.puts(inspect(Float.floor(nan, 2)))\n'
  'IO.puts(inspect(Float.ceil(-inf)))\n'
  'IO.puts(inspect(Float.round(nan)))\n'
  'IO.puts(inspect(inf ** 0.0))\n'
  'IO.puts(inspect(nan ** 0.0))\n'
  'IO.puts(inspect(1.0 ** nan))\n'
  'IO.puts(inspect(Float.pow(-8.0, 1.0 / 3.0)))\n'
  'IO.puts(inspect(Float.pow(2.0, 0.5)))\n'
  'IO.puts(inspect(Float.pow(2.0, -1074.0)))\n'
  'IO.puts(inspect(Float.pow(10.0, 308.0)))\n'
  'IO.puts(inspect(Float.pow(10.0, 309.0)))\n'
  'IO.puts(inspect(2.0 ** 3.0 ** 2.0))\n'
  'IO.puts(inspect(-2.0 ** 2.0))\n'
  '  end\n'
  'end\n',
  0,
  b'false\ntrue\nfalse\nfalse\nfalse\nfalse\nNaN.0\n1.0\nNaN.0\n1.0\nNaN.0\n+Inf\n-Inf\n-Inf\n+Inf\nNaN.0\n-'
  b'Inf\nNaN.0\n1.0\n1.0\n1.0\nNaN.0\n1.4142135623730951\n5.0e-324\n1.0000000000000006e308\n+Inf\n512.0\n4.'
  b'0\n',
  b''),
 ('defmodule M do\n  def main() do\nx = 1.0e308\nIO.puts(inspect(round(x * 10.0)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:17: float out of integer range\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nx = 0.0\nIO.puts(inspect(ceil(x / x)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:24: division by zero\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(round(9.2e18)))\n'
  'IO.puts(inspect(trunc(-9.223372036854775808e18)))\n'
  'IO.puts(inspect(floor(9223372036854774784.0)))\n'
  '  end\n'
  'end\n',
  0,
  b'9200000000000000000\n-9223372036854775808\n9223372036854774784\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(floor(9223372036854775808.0)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: float out of integer range\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Float.ratio(0.1)))\n'
  'IO.puts(inspect(Float.ratio(-0.0)))\n'
  'IO.puts(inspect(Float.ratio(-9223372036854775808.0)))\n'
  'IO.puts(inspect(Float.ratio(3.0)))\n'
  'IO.puts(inspect(Float.ratio(0.5)))\n'
  '  end\n'
  'end\n',
  0,
  b'{3602879701896397, 36028797018963968}\n{0, 1}\n{-9223372036854775808, 1}\n{3, 1}\n{1, 2}\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.ratio(9223372036854775808.0)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: Float.ratio: the fraction does not fit in 64-bit integers\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.ratio(1.0e-300)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: Float.ratio: the fraction does not fit in 64-bit integers\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Float.parse("0x1p-2")))\n'
  'IO.puts(inspect(Float.parse("1_000.5")))\n'
  'IO.puts(inspect(Float.parse("")))\n'
  'IO.puts(inspect(Float.parse(" 1")))\n'
  'IO.puts(inspect(Float.parse("1e400")))\n'
  'IO.puts(inspect(Float.parse("-0")))\n'
  'IO.puts(inspect(Float.parse("NaN")))\n'
  'IO.puts(inspect(Float.parse("été\\n\\"q\\"")))\n'
  'IO.puts(inspect(Float.parse(".5")))\n'
  'IO.puts(inspect(Float.parse("5.")))\n'
  'IO.puts(inspect(Float.parse("1e5")))\n'
  '  end\n'
  'end\n',
  0,
  b'ok(0.25)\nok(1000.5)\nerror("\\"\\" is not a float")\nerror("\\" 1\\" is not a float")\nerror("\\"1e4'
  b'00\\" is not a float")\nok(-0.0)\nerror("\\"NaN\\" is not a float")\nerror("\\"\xc3\xa9t\xc3\xa9\\\\n'
  b'\\\\\\"q\\\\\\"\\" is not a float")\nok(0.5)\nok(5.0)\nok(100000.0)\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(String.to_float("-2.5e-3")))\n'
  'IO.puts(inspect(String.to_float("7")))\n'
  '  end\n'
  'end\n',
  0,
  b'-0.0025\n7.0\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(String.to_float("nan")))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: "nan" is not a float\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(String.to_float("1e999")))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:17: "1e999" is not a float\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'a = 2.5\n'
  'b = a |> Float.round(0) |> Float.to_string()\n'
  'IO.puts(b)\n'
  'IO.puts(a |> round() |> to_string())\n'
  'IO.puts(inspect(3 |> Float.from_integer()))\n'
  '  end\n'
  'end\n',
  0,
  b'3.0\n3\n3.0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 2.5\n'
  'IO.puts("#{x * 2.0}|#{x / 2.0}|#{-x}|#{x - 5.0}")\n'
  'IO.puts("""\n'
  'value #{x}\n'
  '""")\n'
  '  end\n'
  'end\n',
  0,
  b'5.0|1.25|-2.5|-2.5\nvalue 2.5\n\n',
  b''),
 ('defmodule M do\n'
  '  @rate 0.5\n'
  '  @zero 0.0\n'
  '  struct P do\n'
  '    x: float\n'
  '    y: float\n'
  '  end\n'
  '  type Shape do\n'
  '    circle(radius: float)\n'
  '    rect(width: float, height: float)\n'
  '  end\n'
  '  def area(shape: Shape): float do\n'
  '    case shape do\n'
  '      Shape.circle(r) -> 3.14159 * r * r\n'
  '      Shape.rect(w, h) -> w * h\n'
  '    end\n'
  '  end\n'
  '  def half(v: float): float do v * @rate end\n'
  '  def main() do\n'
  '    p = %P{x: 1.5, y: -2.0}\n'
  '    IO.puts(inspect(p))\n'
  '    IO.puts(inspect(p.x + p.y))\n'
  '    IO.puts(inspect(area(Shape.circle(2.0))))\n'
  '    IO.puts(inspect(area(Shape.rect(2.0, 4.5))))\n'
  '    IO.puts(inspect(Shape.rect(2.0, 4.5)))\n'
  '    IO.puts(inspect(half(3.0)))\n'
  '    IO.puts(inspect(@zero * -1.5))\n'
  '    IO.puts(inspect(p == %P{x: 1.5, y: -2.0}))\n'
  '    IO.puts(inspect(Enum.map([1.5, 2.5], fn v -> v * 2.0 end)))\n'
  '    IO.puts(inspect(Enum.reduce([1.5, 2.5], 0.0, fn v, acc -> acc + v end)))\n'
  '    IO.puts(inspect(Enum.filter([1.5, 2.5, 3.5], fn v -> v > 2.0 end)))\n'
  '    m = %{"a" => 1.5, "b" => 2.5}\n'
  '    IO.puts(inspect(Map.get(m, "a")))\n'
  '    IO.puts(inspect(m))\n'
  '    t = {1, 2.5, "x"}\n'
  '    IO.puts(inspect(elem(t, 1)))\n'
  '    f = fn(v: float): float do v + 0.5 end\n'
  '    IO.puts(inspect(f(1.0)))\n'
  '  end\n'
  'end\n',
  0,
  b'%P{x: 1.5, y: -2.0}\n-0.5\n12.56636\n9.0\nShape.rect(2.0, 4.5)\n1.5\n0.0\ntrue\n[3.0, 5.0]\n4.0\n[2.5,'
  b' 3.5]\nsome(1.5)\n%{"a" => 1.5, "b" => 2.5}\n2.5\n1.5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 1.5\n'
  'r = case x do\n'
  '  1.5 -> "a"\n'
  '  -1.5 -> "b"\n'
  '  _ -> "c"\n'
  'end\n'
  'IO.puts(r)\n'
  'y = -1.5\n'
  'r2 = case y do\n'
  '  1.5 -> "a"\n'
  '  -1.5 -> "b"\n'
  '  _ -> "c"\n'
  'end\n'
  'IO.puts(r2)\n'
  'z = -0.0\n'
  'r3 = case z do\n'
  '  0.0 -> "zero"\n'
  '  _ -> "other"\n'
  'end\n'
  'IO.puts(r3)\n'
  'r4 = case {x, 1} do\n'
  '  {2.5, _} -> "p"\n'
  '  {1.5, 1} -> "q"\n'
  '  _ -> "r"\n'
  'end\n'
  'IO.puts(r4)\n'
  '  end\n'
  'end\n',
  0,
  b'a\nb\nzero\nq\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = if 1.5 > 1.0 do 2.5 else 3.5 end\n'
  'IO.puts(inspect(x))\n'
  'y = cond do\n'
  '  x > 3.0 -> 1.0\n'
  '  x > 2.0 -> 2.0\n'
  '  true -> 3.0\n'
  'end\n'
  'IO.puts(inspect(y))\n'
  '  end\n'
  'end\n',
  0,
  b'2.5\n2.0\n',
  b''),
 ('defmodule M do\n'
  '  @a 0.0\n'
  '  @b -1.5\n'
  '  @c @a * @b\n'
  '  @big 1.0e308\n'
  '  def main() do\n'
  '    IO.puts(inspect(@a * @b))\n'
  '    IO.puts(inspect(@c))\n'
  '    IO.puts(inspect(@c * 1.0))\n'
  '    IO.puts(inspect(@a * -1.0))\n'
  '  end\n'
  'end\n',
  0,
  b'0.0\n0.0\n0.0\n0.0\n',
  b''),
 ('defmodule M do\n'
  '  @n -0.0\n'
  '  def main() do\n'
  '    IO.puts(inspect(@n))\n'
  '    IO.puts(inspect(@n * 1.0))\n'
  '    IO.puts(inspect(@n + 0.0))\n'
  '  end\n'
  'end\n',
  0,
  b'-0.0\n-0.0\n0.0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Float.max_finite() * 2.0))\n'
  'IO.puts(inspect(Float.min_finite() * 2.0))\n'
  '  end\n'
  'end\n',
  0,
  b'+Inf\n-Inf\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Float.from_integer(0) * -1.0))\n'
  'IO.puts(inspect(-(0.0) * 1.0))\n'
  'IO.puts(inspect(- 1.5))\n'
  'IO.puts(inspect(-  0.0))\n'
  'IO.puts(inspect(0.0 * - 1.5))\n'
  'IO.puts(inspect(1.5 - -1.5))\n'
  'IO.puts(inspect(1.5 -1.5))\n'
  'IO.puts(inspect(1.5-1.5))\n'
  'IO.puts(inspect((0.0 - 0.0) * -1.0))\n'
  'IO.puts(inspect(5.0e-324 * 0.5))\n'
  'IO.puts(inspect(5.0e-324 * 0.5000001))\n'
  'IO.puts(inspect(-5.0e-324 * 0.25))\n'
  'IO.puts(inspect(0.1 + 0.2 - 0.3))\n'
  'IO.puts(inspect(1.0e308 + 1.0e308 * 0.5))\n'
  'IO.puts(inspect(0.1 * 3.0))\n'
  'IO.puts(inspect(1.0e16 + 1.0))\n'
  'IO.puts(inspect(9007199254740992.0 + 1.0 + 1.0))\n'
  'IO.puts(inspect(1.0 - 0.9))\n'
  '  end\n'
  'end\n',
  0,
  b'-0.0\n-0.0\n-1.5\n-0.0\n0.0\n3.0\n0.0\n0.0\n0.0\n0.0\n5.0e-324\n0.0\n5.551115123125783e-17\n1.5e308\n0'
  b'.30000000000000004\n1.0e16\n9007199254740992.0\n0.09999999999999998\n',
  b''),
 ('defmodule M do\n  def main() do\nx = 1.5\n  end\nend\n', 0, b'', b''),
 ('defmodule M do\n  def main() do\nx = 1\n  end\nend\n', 0, b'', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.5e1))\n  end\nend\n', 0, b'15.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.5e+1))\n  end\nend\n', 0, b'15.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.5e-1))\n  end\nend\n', 0, b'0.15\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.5e01))\n  end\nend\n', 0, b'15.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(01.50))\n  end\nend\n', 0, b'1.5\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1_0.5))\n  end\nend\n', 0, b'10.5\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1_000_000.25))\n  end\nend\n', 0, b'1000000.25\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.5e3 + 1.0))\n  end\nend\n', 0, b'1501.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1..3))\n  end\nend\n', 0, b'1..3\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.to_list(1..3)))\n  end\nend\n',
  0,
  b'[1, 2, 3]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.5e1 == 15.0))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.7976931348623158e308))\n  end\nend\n',
  0,
  b'1.7976931348623157e308\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.797693134862315807e308))\n  end\nend\n',
  0,
  b'1.7976931348623157e308\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(0.0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001))\n'
  '  end\n'
  'end\n',
  0,
  b'0.0\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.0e-999))\n  end\nend\n', 0, b'0.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(-1.0e-999))\n  end\nend\n', 0, b'-0.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(0.0e999))\n  end\nend\n', 0, b'0.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1_000))\n  end\nend\n', 0, b'1000\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1_000 + 1))\n  end\nend\n', 0, b'1001\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(%{1.5 => "a"}))\n  end\nend\n',
  0,
  b'%{1.5 => "a"}\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Map.get(%{1.5 => "a", 2.5 => "b"}, 2.5)))\n  end\nend\n',
  0,
  b'some("b")\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.map([1, 2], fn n -> Float.from_integer(n) / 2.0 end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[0.5, 1.0]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.sum(Enum.map([1, 2], fn n -> Float.from_integer(n) / 2.0 end))))\n'
  '  end\n'
  'end\n',
  0,
  b'1.5\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.uniq([1.5, 1.5, 2.5])))\n  end\nend\n',
  0,
  b'[1.5, 2.5]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.member?([1.5, 2.5], 2.5)))\n  end\nend\n',
  0,
  b'true\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.at([1.5, 2.5], 1)))\n  end\nend\n',
  0,
  b'some(2.5)\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(List.first([1.5, 2.5])))\n  end\nend\n',
  0,
  b'some(1.5)\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.reverse([1.5, 2.5])))\n  end\nend\n',
  0,
  b'[2.5, 1.5]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.map([1.5, 2.5], &round/1)))\n  end\nend\n',
  0,
  b'[2, 3]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.map([1, 2], &Float.from_integer/1)))\n  end\nend\n',
  0,
  b'[1.0, 2.0]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.map([1.5, 2.5], &Float.to_string/1)))\n  end\nend\n',
  0,
  b'["1.5", "2.5"]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.map([1.26, 2.54], &Float.round(&1, 1))))\n'
  '  end\n'
  'end\n',
  0,
  b'[1.3, 2.5]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.map([1.5, 2.5], &(&1 * 2.0))))\n  end\nend\n',
  0,
  b'[3.0, 5.0]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect([1.5, 2.5] ++ [3.5]))\n  end\nend\n',
  0,
  b'[1.5, 2.5, 3.5]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect([1.5, 2.5, 1.5] -- [1.5]))\n  end\nend\n',
  0,
  b'[2.5, 1.5]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(hd([1.5, 2.5])))\n  end\nend\n', 0, b'1.5\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(tl([1.5, 2.5])))\n  end\nend\n', 0, b'[2.5]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(length([1.5, 2.5])))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule M do\n  def main() do\nIO.inspect(1.5)\n  end\nend\n', 0, b'1.5\n', b''),
 ('defmodule M do\n  def main() do\nIO.inspect([1.5, 2.0])\n  end\nend\n', 0, b'[1.5, 2.0]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Kernel.round(2.5)))\n  end\nend\n', 0, b'3\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Kernel.abs(-2.5)))\n  end\nend\n', 0, b'2.5\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Kernel.max(1.5, 2.5)))\n  end\nend\n', 0, b'2.5\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Integer.parse("12")))\n  end\nend\n',
  0,
  b'ok(12)\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(to_string(1.0e15) <> " " <> to_string(1.0e16) <> " " <> to_string(123456789.0) <> " " <> '
  'to_string(100.0))\n'
  '  end\n'
  'end\n',
  0,
  b'1.0e15 1.0e16 123456789.0 100.0\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.zip([1.5, 2.5], ["a", "b"])))\n  end\nend\n',
  0,
  b'[{1.5, "a"}, {2.5, "b"}]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.sum([0.1, 0.2, 0.3])))\n  end\nend\n',
  0,
  b'0.6000000000000001\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.count([1.5])))\n  end\nend\n', 0, b'1\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(some(1.5) == some(1.5)))\n  end\nend\n',
  0,
  b'true\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.find([1.5, 2.5], fn v -> v > 2.0 end)))\n'
  '  end\n'
  'end\n',
  0,
  b'some(2.5)\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.any?([1.5, 2.5], fn v -> v > 2.0 end)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.reduce([1.5, 2.5], 1.0, fn v, acc -> acc * v end)))\n'
  '  end\n'
  'end\n',
  0,
  b'3.75\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.with_index([1.5, 2.5])))\n  end\nend\n',
  0,
  b'[{1.5, 0}, {2.5, 1}]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.into([{1, 1.5}], %{})))\n  end\nend\n',
  0,
  b'%{1 => 1.5}\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Integer.to_string(round(2.6))))\n  end\nend\n',
  0,
  b'"3"\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(2.675, 2)))\n  end\nend\n',
  0,
  b'2.67\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.floor(-2.675, 2)))\n  end\nend\n',
  0,
  b'-2.68\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.ceil(-2.675, 2)))\n  end\nend\n',
  0,
  b'-2.67\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(-0.0003, 2)))\n  end\nend\n',
  0,
  b'-0.0\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(5.0e15, 3)))\n  end\nend\n',
  0,
  b'5000000000000000.0\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(4503599627370.4961, 3)))\n  end\nend\n',
  0,
  b'4503599627370.496\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.ceil(-0.5)))\n  end\nend\n', 0, b'-0.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.floor(-0.0)))\n  end\nend\n', 0, b'-0.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(-0.4)))\n  end\nend\n', 0, b'-0.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(0.5)))\n  end\nend\n', 0, b'1.0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(1.0e300)))\n  end\nend\n',
  0,
  b'1.0e300\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1_000_000))\n  end\nend\n', 0, b'1000000\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(-1_0))\n  end\nend\n', 0, b'-10\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'm = %{1.5 => "a", -2.5 => "b", 0.5 => "c", -0.5 => "d", 100.0 => "e"}\n'
  'IO.puts(inspect(m))\n'
  'IO.puts(inspect(Map.get(m, -2.5)))\n'
  'IO.puts(inspect(Map.keys(m)))\n'
  'IO.puts(inspect(Map.has_key?(m, 0.5)))\n'
  'IO.puts(inspect(Map.delete(m, 1.5)))\n'
  '  end\n'
  'end\n',
  0,
  b'%{-2.5 => "b", -0.5 => "d", 0.5 => "c", 1.5 => "a", 100.0 => "e"}\nsome("b")\n[-2.5, -0.5, 0.5, 1.5, 1'
  b'00.0]\ntrue\n%{-2.5 => "b", -0.5 => "d", 0.5 => "c", 100.0 => "e"}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 1.0e308\n'
  'inf = x * 10.0\n'
  'm = %{inf => "a", -inf => "b", 0.0 => "c"}\n'
  'IO.puts(inspect(m))\n'
  '  end\n'
  'end\n',
  0,
  b'%{-Inf => "b", 0.0 => "c", +Inf => "a"}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = 0.0\n'
  'nan = z / z\n'
  'm = %{nan => "a", 1.0 => "b"}\n'
  'm2 = Map.put(m, nan, "c")\n'
  'IO.puts(inspect(m))\n'
  'IO.puts(inspect(m2))\n'
  'IO.puts(inspect(Map.get(m2, nan)))\n'
  'IO.puts(inspect(map_size(m2)))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:9: division by zero\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = 0.0\n'
  'm = %{z => "a"}\n'
  'm2 = Map.put(m, -z, "b")\n'
  'IO.puts(inspect(m2))\n'
  'IO.puts(inspect(Map.get(m2, 0.0)))\n'
  '  end\n'
  'end\n',
  0,
  b'%{-0.0 => "b"}\nsome("b")\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 1.0e308\n'
  'y = 10.0\n'
  'inf = x * y\n'
  'm = %{inf => "a", -inf => "b", 0.0 => "c", -1.5 => "d", 3.0e-310 => "e"}\n'
  'IO.puts(inspect(m))\n'
  'IO.puts(inspect(Map.keys(m)))\n'
  'IO.puts(inspect(Map.values(m)))\n'
  'IO.puts(inspect(Map.to_list(m)))\n'
  '  end\n'
  'end\n',
  0,
  b'%{-Inf => "b", -1.5 => "d", 0.0 => "c", 3.0e-310 => "e", +Inf => "a"}\n[-Inf, -1.5, 0.0, 3.0e-310, +I'
  b'nf]\n["b", "d", "c", "e", "a"]\n[{-Inf, "b"}, {-1.5, "d"}, {0.0, "c"}, {3.0e-310, "e"}, {+Inf, "a"}]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'm = Map.new([{2.5, 1}, {-1.5, 2}, {2.5, 3}])\n'
  'IO.puts(inspect(m))\n'
  'IO.puts(inspect(Map.fetch(m, 2.5)))\n'
  'IO.puts(inspect(Map.fetch(m, 9.5)))\n'
  'IO.puts(inspect(Map.has_key?(m, -1.5)))\n'
  'IO.puts(inspect(Map.put(m, 0.5, 9)))\n'
  'IO.puts(inspect(Map.delete(m, 2.5)))\n'
  'IO.puts(inspect(m == Map.new([{-1.5, 2}, {2.5, 3}])))\n'
  '  end\n'
  'end\n',
  0,
  b'%{-1.5 => 2, 2.5 => 3}\nsome(3)\nnone\ntrue\n%{-1.5 => 2, 0.5 => 9, 2.5 => 3}\n%{-1.5 => 2}\ntrue\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'm = %{2.5 => 1, -1.5 => 2}\n'
  'IO.puts(inspect(Map.update(m, 2.5, 0, fn v -> v + 10 end)))\n'
  'IO.puts(inspect(Map.merge(m, %{0.5 => 7})))\n'
  'IO.puts(inspect(Map.put_new(m, 2.5, 99)))\n'
  'IO.puts(inspect(Map.put_new(m, 3.5, 99)))\n'
  'IO.puts(inspect(Map.get(m, 7.5, 0)))\n'
  'IO.puts(inspect(Map.take(m, [2.5])))\n'
  'IO.puts(inspect(Map.drop(m, [2.5])))\n'
  'IO.puts(inspect(Enum.map(m, fn {k, v} -> k * Float.from_integer(v) end)))\n'
  '  end\n'
  'end\n',
  0,
  b'%{-1.5 => 2, 2.5 => 11}\n%{-1.5 => 2, 0.5 => 7, 2.5 => 1}\n%{-1.5 => 2, 2.5 => 1}\n%{-1.5 => 2, 2.5 => '
  b'1, 3.5 => 99}\n0\n%{2.5 => 1}\n%{-1.5 => 2}\n[-3.0, 2.5]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(Enum.uniq([1.5, 1.5, 2.5, 0.0, -0.0])))\n'
  'IO.puts(inspect(Enum.member?([1.5, 2.5], 2.5)))\n'
  'IO.puts(inspect(Enum.frequencies([1.5, 1.5, 2.5])))\n'
  'IO.puts(inspect(Enum.dedup([1.5, 1.5, 2.5])))\n'
  'IO.puts(inspect(List.delete([1.5, 2.5], 1.5)))\n'
  'IO.puts(inspect(Enum.find_index([1.5, 2.5], fn v -> v == 2.5 end)))\n'
  'IO.puts(inspect(Enum.group_by([1.5, 2.5, 1.7], fn v -> trunc(v) end)))\n'
  'IO.puts(inspect(Enum.group_by([1, 2, 3], fn v -> Float.from_integer(rem(v, 2)) end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1.5, 2.5, 0.0]\ntrue\n%{1.5 => 2, 2.5 => 1}\n[1.5, 2.5]\n[2.5]\nsome(1)\n%{1 => [1.5, 1.7], 2 => [2.5'
  b']}\n%{0.0 => [2], 1.0 => [1, 3]}\n',
  b''),
 ('defmodule M do\n'
  '  def same(a: t, b: t): boolean do a == b end\n'
  '  def pick(items: list[t], x: t): boolean do x in items end\n'
  '  struct Box[t] do\n'
  '    v: t\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(same(1.5, 1.5)))\n'
  '    IO.puts(inspect(same(0.0, -0.0)))\n'
  '    IO.puts(inspect(same(1.5, 2.5)))\n'
  '    z = 0.0\n'
  '    IO.puts(inspect(same(z / z, z / z)))\n'
  '    IO.puts(inspect(pick([1.5, 2.5], 2.5)))\n'
  '    IO.puts(inspect(same([1.5], [1.5])))\n'
  '    IO.puts(inspect(same({1.5, 1}, {1.5, 1})))\n'
  '    IO.puts(inspect(%Box{v: 1.5} == %Box{v: 1.5}))\n'
  '    IO.puts(inspect(%Box{v: 0.0} == %Box{v: -0.0}))\n'
  '    IO.puts(inspect(%Box{v: 1.5}))\n'
  '  end\n'
  'end\n',
  2,
  b'true\ntrue\nfalse\n',
  b'<stdin>:12:28: division by zero\n  at M.main (<stdin>:12)\n'),
 ('defmodule M do\n'
  '  def mean(values: list[float]): float do\n'
  '    Enum.sum(values) / Float.from_integer(length(values))\n'
  '  end\n'
  '  def variance(values: list[float]): float do\n'
  '    m = mean(values)\n'
  '    Enum.sum(Enum.map(values, fn v -> (v - m) * (v - m) end)) / Float.from_integer(length(values))\n'
  '  end\n'
  '  def sqrt(x: float): float do x ** 0.5 end\n'
  '  def fact(n: integer): float do\n'
  '    if n <= 1 do 1.0 else Float.from_integer(n) * fact(n - 1) end\n'
  '  end\n'
  '  def newton(x: float, guess: float, steps: integer): float do\n'
  '    if steps == 0 do guess else newton(x, (guess + x / guess) / 2.0, steps - 1) end\n'
  '  end\n'
  '  def main() do\n'
  '    data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]\n'
  '    IO.puts("mean #{mean(data)} variance #{variance(data)} sd #{sqrt(variance(data))}")\n'
  '    IO.puts(inspect(fact(20)))\n'
  '    IO.puts(inspect(fact(25)))\n'
  '    IO.puts(inspect(fact(170)))\n'
  '    IO.puts(inspect(fact(171)))\n'
  '    IO.puts(inspect(newton(2.0, 1.0, 20)))\n'
  '    IO.puts(inspect(Float.round(newton(2.0, 1.0, 20), 5)))\n'
  '    IO.puts(inspect(Enum.map(1..5, fn n -> 1.0 / Float.from_integer(n) end)))\n'
  '    IO.puts(inspect(Enum.reduce(1..100, 0.0, fn n, acc -> acc + 0.1 * Float.from_integer(n) end)))\n'
  '    c = 100.0\n'
  '    IO.puts("#{c}C is #{c * 9.0 / 5.0 + 32.0}F")\n'
  '    IO.puts(inspect(3.0e8 * 3.0e8))\n'
  '    IO.puts(inspect(6.02214076e23))\n'
  '    IO.puts(inspect(1.0 / 3.0))\n'
  '    IO.puts(inspect(2.0 / 3.0))\n'
  '    IO.puts(inspect(10.0 / 4.0))\n'
  '    IO.puts(inspect(1.0e21))\n'
  '    IO.puts(to_string(1.0e21))\n'
  '    IO.puts(to_string(123456789012345680.0))\n'
  '    IO.puts(inspect(123456789012345680.0))\n'
  '    IO.puts(to_string(0.00001))\n'
  '    IO.puts(to_string(0.0001))\n'
  '  end\n'
  'end\n',
  0,
  b'mean 5.0 variance 4.0 sd 2.0\n2.43290200817664e18\n1.5511210043330986e25\n7.257415615307994e306\n+Inf\n1.'
  b'414213562373095\n1.41421\n[1.0, 0.5, 0.3333333333333333, 0.25, 0.2]\n505.0\n100.0C is 212.0F\n9.0e16\n'
  b'6.02214076e23\n0.3333333333333333\n0.6666666666666666\n2.5\n1.0e21\n1.0e21\n1.2345678901234568e17\n1.23'
  b'45678901234568e17\n1.0e-5\n0.0001\n',
  b''),
 ('defmodule M do\n'
  '  def div(a: float, b: float): float do a / b end\n'
  '  def main() do\n'
  '    IO.puts(inspect(div(1.0, 4.0)))\n'
  '    IO.puts(inspect(div(1.0, 0.0)))\n'
  '  end\n'
  'end\n',
  2,
  b'0.25\n',
  b'<stdin>:2:43: division by zero\n  at M.div (<stdin>:2)\n  at M.main (<stdin>:5)\n'),
 ('defmodule M do\n'
  '  def f(x: float): integer do\n'
  '    y = x * 2.0\n'
  '    round(y * 1.0e300)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1.0e-300)))\n'
  '    IO.puts(inspect(Enum.map([1.0, 1.0e10], fn v -> M.f(v) end)))\n'
  '  end\n'
  'end\n',
  2,
  b'2\n',
  b'<stdin>:4:5: float out of integer range\n  at M.f (<stdin>:4)\n  at M.main <closure> (<stdin>:8)\n  at '
  b'M.main (<stdin>:8)\n'),
 ('defmodule M do\n  def main() do\nx = -0.0\nIO.puts(inspect(1.0 / x))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:21: division by zero\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(1.5 |> Float.round()))\n'
  'IO.puts(inspect(2.0 |> Float.pow(3.0)))\n'
  'IO.puts(inspect("2.5" |> Float.parse()))\n'
  'IO.puts(inspect("2.5" |> String.to_float()))\n'
  'IO.puts(inspect(2.5 |> to_string()))\n'
  'IO.puts(inspect(2.5 |> Float.ratio()))\n'
  'IO.puts(inspect(-2.5 |> abs()))\n'
  'IO.puts(inspect(2.5 |> max(3.5)))\n'
  '  end\n'
  'end\n',
  0,
  b'2.0\n8.0\nok(2.5)\n2.5\n"2.5"\n{5, 2}\n2.5\n3.5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 10.0\n'
  'IO.puts(inspect(x - 1.5))\n'
  'IO.puts(inspect(x -1.5))\n'
  'IO.puts(inspect(x-1.5))\n'
  'IO.puts(inspect(x - -1.5))\n'
  'IO.puts(inspect(x * -1.5))\n'
  'IO.puts(inspect(x / -4.0))\n'
  'IO.puts(inspect(-x ** 2.0))\n'
  'IO.puts(inspect(2.0 ** -1.0))\n'
  'IO.puts(inspect(x > 1.5 and x < 20.0))\n'
  'IO.puts(inspect(not (x == 10.0)))\n'
  'IO.puts(inspect(x + 1.0 * 2.0 - 3.0 / 4.0))\n'
  'IO.puts(inspect((x + 1.0) * (2.0 - 3.0) / 4.0))\n'
  '  end\n'
  'end\n',
  0,
  b'8.5\n8.5\n8.5\n11.5\n-15.0\n-2.5\n100.0\n0.5\ntrue\nfalse\n11.25\n-2.75\n',
  b''),
 ('defmodule M do\n'
  '  def classify(x: float): string do\n'
  '    cond do\n'
  '      x < 0.0 -> "negative"\n'
  '      x == 0.0 -> "zero"\n'
  '      x < 1.0e3 -> "small"\n'
  '      true -> "large"\n'
  '    end\n'
  '  end\n'
  '  def safe_div(a: float, b: float): result[float, string] do\n'
  '    if b == 0.0 do error("division by zero") else ok(a / b) end\n'
  '  end\n'
  '  def first(items: list[float]): option[float] do\n'
  '    case items do\n'
  '      [] -> none\n'
  '      [h | _] -> some(h)\n'
  '    end\n'
  '  end\n'
  '  def total(items: list[float]): float do\n'
  '    case items do\n'
  '      [] -> 0.0\n'
  '      [h | t] -> h + total(t)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(classify(-1.5) <> classify(0.0) <> classify(-0.0) <> classify(5.5) <> classify(1.0e4))\n'
  '    IO.puts(inspect(safe_div(1.0, 4.0)))\n'
  '    IO.puts(inspect(safe_div(1.0, 0.0)))\n'
  '    IO.puts(inspect(first([1.5, 2.5])))\n'
  '    IO.puts(inspect(first([])))\n'
  '    IO.puts(inspect(total([1.5, 2.5, 3.0])))\n'
  '    case safe_div(9.0, 3.0) do\n'
  '      ok(v) -> IO.puts("ok #{v}")\n'
  '      error(e) -> IO.puts(e)\n'
  '    end\n'
  '    t = {1.5, 2.5}\n'
  '    {a, b} = t\n'
  '    IO.puts(inspect(a + b))\n'
  '    [p, q] = [0.5, 0.25]\n'
  '    IO.puts(inspect(p * q))\n'
  '  end\n'
  'end\n',
  0,
  b'negativezerozerosmalllarge\nok(0.25)\nerror("division by zero")\nsome(1.5)\nnone\n7.0\nok 3.0\n4.0\n0.12'
  b'5\n',
  b''),
 ('defmodule M do\n'
  '  def apply(f: fn[float, float], x: float): float do f(x) end\n'
  '  def twice(x: float): float do x * 2.0 end\n'
  '  def compose(f: fn[float, float], g: fn[float, float]): fn[float, float] do\n'
  '    fn(x: float): float do g(f(x)) end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(apply(&twice/1, 1.5)))\n'
  '    IO.puts(inspect(apply(fn x -> x + 0.5 end, 1.5)))\n'
  '    h = compose(&twice/1, fn x -> x - 1.0 end)\n'
  '    IO.puts(inspect(h(4.0)))\n'
  '    scale = 2.5\n'
  '    IO.puts(inspect(Enum.map([1.0, 2.0], fn x -> x * scale end)))\n'
  '  end\n'
  'end\n',
  0,
  b'3.0\n2.0\n7.0\n[2.5, 5.0]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = 3.0\n'
  'IO.puts(inspect(Float.round(x / 7.0, 3)))\n'
  'IO.puts(inspect(Float.floor(x / 7.0, 3)))\n'
  'IO.puts(inspect(Float.ceil(x / 7.0, 3)))\n'
  'IO.puts(inspect(Float.to_string(x / 7.0)))\n'
  'IO.puts(inspect(round(x / 7.0 * 100.0)))\n'
  'IO.puts(inspect(trunc(1.0e10)))\n'
  'IO.puts(inspect(Float.from_integer(9007199254740993)))\n'
  'IO.puts(inspect(Float.from_integer(-9223372036854775807 - 1)))\n'
  'IO.puts(inspect(Float.from_integer(9223372036854775807)))\n'
  '  end\n'
  'end\n',
  0,
  b'0.429\n0.428\n0.429\n"0.42857142857142855"\n43\n10000000000\n9007199254740992.0\n-9.223372036854776e18\n'
  b'9.223372036854776e18\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts("#{-4.1449887646880346e+17} " <> inspect(-4.1449887646880346e+17))\n'
  'IO.puts("#{4.9e-324} " <> inspect(4.9e-324))\n'
  'IO.puts("#{4.8959585264576934e+278} " <> inspect(4.8959585264576934e+278))\n'
  'IO.puts("#{8638353731572480506139685.152251367e-238} " <> '
  'inspect(8638353731572480506139685.152251367e-238))\n'
  'IO.puts("#{8903804920.124893} " <> inspect(8903804920.124893))\n'
  'IO.puts("#{3.467443581611296e+180} " <> inspect(3.467443581611296e+180))\n'
  'IO.puts("#{7.213264545145106e-130} " <> inspect(7.213264545145106e-130))\n'
  'IO.puts("#{1072775727649675.3e-83} " <> inspect(1072775727649675.3e-83))\n'
  'IO.puts("#{7.781084065432434e-11} " <> inspect(7.781084065432434e-11))\n'
  'IO.puts("#{684854.257} " <> inspect(684854.257))\n'
  'IO.puts("#{-2.373036535955807e-108} " <> inspect(-2.373036535955807e-108))\n'
  'IO.puts("#{1.1258992597715162e+35} " <> inspect(1.1258992597715162e+35))\n'
  'IO.puts("#{102535.471256} " <> inspect(102535.471256))\n'
  'IO.puts("#{6.523709363967305e+80} " <> inspect(6.523709363967305e+80))\n'
  'IO.puts("#{1.2862700569905684e-308} " <> inspect(1.2862700569905684e-308))\n'
  'IO.puts("#{-2.531181409121447e+20} " <> inspect(-2.531181409121447e+20))\n'
  'IO.puts("#{-2.5927937746066815e+119} " <> inspect(-2.5927937746066815e+119))\n'
  'IO.puts("#{-866.3469857269171} " <> inspect(-866.3469857269171))\n'
  'IO.puts("#{5.482841095344694e-308} " <> inspect(5.482841095344694e-308))\n'
  'IO.puts("#{-8.813722369040187e+197} " <> inspect(-8.813722369040187e+197))\n'
  'IO.puts("#{-2.30518901278551e+284} " <> inspect(-2.30518901278551e+284))\n'
  'IO.puts("#{174_679_744_303.797} " <> inspect(174_679_744_303.797))\n'
  'IO.puts("#{4669248787.3963600717e-193} " <> inspect(4669248787.3963600717e-193))\n'
  'IO.puts("#{3.6633790673883503e-295} " <> inspect(3.6633790673883503e-295))\n'
  'IO.puts("#{2.052132435276533e+292} " <> inspect(2.052132435276533e+292))\n'
  'IO.puts("#{2.2480005775930857e-76} " <> inspect(2.2480005775930857e-76))\n'
  'IO.puts("#{-618631.16942} " <> inspect(-618631.16942))\n'
  'IO.puts("#{5.18476533909398e-309} " <> inspect(5.18476533909398e-309))\n'
  'IO.puts("#{980104.0} " <> inspect(980104.0))\n'
  'IO.puts("#{941.8581124373829} " <> inspect(941.8581124373829))\n'
  'IO.puts("#{8.32963919567359151239646395321689511194447853520926376975136147644039417171590340971834571932855813118721849850965868279008332532466248431733064299257168335621308448252702362686395088542035019113780996305516445384657503136135355881140093520355228348699662374272934655486595344914803375605113467378173340549120e307} '
  '" <> '
  'inspect(8.32963919567359151239646395321689511194447853520926376975136147644039417171590340971834571932855813118721849850965868279008332532466248431733064299257168335621308448252702362686395088542035019113780996305516445384657503136135355881140093520355228348699662374272934655486595344914803375605113467378173340549120e307))\n'
  'IO.puts("#{-1.0590156255849663e+129} " <> inspect(-1.0590156255849663e+129))\n'
  'IO.puts("#{48547007915059293.3493e122} " <> inspect(48547007915059293.3493e122))\n'
  'IO.puts("#{545.3793795456463} " <> inspect(545.3793795456463))\n'
  'IO.puts("#{-407.3504748021073} " <> inspect(-407.3504748021073))\n'
  'IO.puts("#{2.634858158773902e-51} " <> inspect(2.634858158773902e-51))\n'
  'IO.puts("#{24301292.013756238} " <> inspect(24301292.013756238))\n'
  'IO.puts("#{244298.5} " <> inspect(244298.5))\n'
  'IO.puts("#{1.0819471997658424e+273} " <> inspect(1.0819471997658424e+273))\n'
  'IO.puts("#{1.51790963521064906602522059249850004283692411633102432360465722414708838750035438755057972683687140218997168109038575778413360239937901496887207031250e-41} '
  '" <> '
  'inspect(1.51790963521064906602522059249850004283692411633102432360465722414708838750035438755057972683687140218997168109038575778413360239937901496887207031250e-41))\n'
  'IO.puts("#{-543.2332632273146} " <> inspect(-543.2332632273146))\n'
  'IO.puts("#{83710225270846565689237.720344e67} " <> inspect(83710225270846565689237.720344e67))\n'
  'IO.puts("#{1_0.5} " <> inspect(1_0.5))\n'
  'IO.puts("#{1.2795142978827492e-180} " <> inspect(1.2795142978827492e-180))\n'
  'IO.puts("#{-3.60063063375658e+262} " <> inspect(-3.60063063375658e+262))\n'
  'IO.puts("#{479.657317766241} " <> inspect(479.657317766241))\n'
  'IO.puts("#{-158369.3948} " <> inspect(-158369.3948))\n'
  'IO.puts("#{-9.008831509047858e+16} " <> inspect(-9.008831509047858e+16))\n'
  'IO.puts("#{-1.8312894964333763e-235} " <> inspect(-1.8312894964333763e-235))\n'
  'IO.puts("#{1367642942600312432.28507878e-122} " <> inspect(1367642942600312432.28507878e-122))\n'
  '  end\n'
  'end\n',
  0,
  b'-4.1449887646880346e17 -4.1449887646880346e17\n5.0e-324 5.0e-324\n4.8959585264576934e278 4.89595852645'
  b'76934e278\n8.638353731572481e-214 8.638353731572481e-214\n8903804920.124893 8903804920.124893\n3.467443'
  b'581611296e180 3.467443581611296e180\n7.213264545145106e-130 7.213264545145106e-130\n1.0727757276496753'
  b'e-68 1.0727757276496753e-68\n7.781084065432434e-11 7.781084065432434e-11\n684854.257 684854.257\n-2.373'
  b'036535955807e-108 -2.373036535955807e-108\n1.1258992597715162e35 1.1258992597715162e35\n102535.471256 '
  b'102535.471256\n6.523709363967305e80 6.523709363967305e80\n1.2862700569905684e-308 1.2862700569905684e-'
  b'308\n-2.531181409121447e20 -2.531181409121447e20\n-2.5927937746066815e119 -2.5927937746066815e119\n-866'
  b'.3469857269171 -866.3469857269171\n5.482841095344694e-308 5.482841095344694e-308\n-8.813722369040187e1'
  b'97 -8.813722369040187e197\n-2.30518901278551e284 -2.30518901278551e284\n174679744303.797 174679744303.'
  b'797\n4.66924878739636e-184 4.66924878739636e-184\n3.6633790673883503e-295 3.6633790673883503e-295\n2.05'
  b'2132435276533e292 2.052132435276533e292\n2.2480005775930857e-76 2.2480005775930857e-76\n-618631.16942 '
  b'-618631.16942\n5.18476533909398e-309 5.18476533909398e-309\n980104.0 980104.0\n941.8581124373829 941.85'
  b'81124373829\n8.329639195673591e307 8.329639195673591e307\n-1.0590156255849663e129 -1.0590156255849663e'
  b'129\n4.8547007915059295e138 4.8547007915059295e138\n545.3793795456463 545.3793795456463\n-407.350474802'
  b'1073 -407.3504748021073\n2.634858158773902e-51 2.634858158773902e-51\n24301292.013756238 24301292.0137'
  b'56238\n244298.5 244298.5\n1.0819471997658424e273 1.0819471997658424e273\n1.517909635210649e-41 1.517909'
  b'635210649e-41\n-543.2332632273146 -543.2332632273146\n8.371022527084656e89 8.371022527084656e89\n10.5 1'
  b'0.5\n1.2795142978827492e-180 1.2795142978827492e-180\n-3.60063063375658e262 -3.60063063375658e262\n479.'
  b'657317766241 479.657317766241\n-158369.3948 -158369.3948\n-9.008831509047858e16 -9.008831509047858e16\n'
  b'-1.8312894964333763e-235 -1.8312894964333763e-235\n1.3676429426003124e-104 1.3676429426003124e-104\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts("#{375.421} " <> inspect(375.421))\n'
  'IO.puts("#{-879088.8} " <> inspect(-879088.8))\n'
  'IO.puts("#{62.00724202646916} " <> inspect(62.00724202646916))\n'
  'IO.puts("#{1.520873253036128e-210} " <> inspect(1.520873253036128e-210))\n'
  'IO.puts("#{781880.46} " <> inspect(781880.46))\n'
  'IO.puts("#{656517327501705202436.1e36} " <> inspect(656517327501705202436.1e36))\n'
  'IO.puts("#{121.612} " <> inspect(121.612))\n'
  'IO.puts("#{822465051272420.342421092e-191} " <> inspect(822465051272420.342421092e-191))\n'
  'IO.puts("#{2.5764595078388533e-231} " <> inspect(2.5764595078388533e-231))\n'
  'IO.puts("#{-189380378940.0} " <> inspect(-189380378940.0))\n'
  'IO.puts("#{460_186_801.484} " <> inspect(460_186_801.484))\n'
  'IO.puts("#{7.12881346503468e+190} " <> inspect(7.12881346503468e+190))\n'
  'IO.puts("#{5.253807105661922e-287} " <> inspect(5.253807105661922e-287))\n'
  'IO.puts("#{00.5} " <> inspect(00.5))\n'
  'IO.puts("#{2.989096728972427e+163} " <> inspect(2.989096728972427e+163))\n'
  'IO.puts("#{-975106.0} " <> inspect(-975106.0))\n'
  'IO.puts("#{3.844989550636268e-166} " <> inspect(3.844989550636268e-166))\n'
  'IO.puts("#{4.455508415646675e+189} " <> inspect(4.455508415646675e+189))\n'
  'IO.puts("#{852_810_694_568.451} " <> inspect(852_810_694_568.451))\n'
  'IO.puts("#{-1.350665515572045e+17} " <> inspect(-1.350665515572045e+17))\n'
  'IO.puts("#{3.102349907255565e-26} " <> inspect(3.102349907255565e-26))\n'
  'IO.puts("#{-33260158.0} " <> inspect(-33260158.0))\n'
  'IO.puts("#{1.138481481714781e-308} " <> inspect(1.138481481714781e-308))\n'
  'IO.puts("#{123456789.0} " <> inspect(123456789.0))\n'
  'IO.puts("#{356.2739582621766} " <> inspect(356.2739582621766))\n'
  'IO.puts("#{-94842.82310044693} " <> inspect(-94842.82310044693))\n'
  'IO.puts("#{3.6147378671465184e+221} " <> inspect(3.6147378671465184e+221))\n'
  'IO.puts("#{91832732001.0} " <> inspect(91832732001.0))\n'
  'IO.puts("#{268.34625647806024} " <> inspect(268.34625647806024))\n'
  'IO.puts("#{3.93873278493638077339532539799028894068655331623229932800278260685011844088876387104392051696777343749e-21} '
  '" <> '
  'inspect(3.93873278493638077339532539799028894068655331623229932800278260685011844088876387104392051696777343749e-21))\n'
  'IO.puts("#{2.01875680156313e+82} " <> inspect(2.01875680156313e+82))\n'
  'IO.puts("#{1.6776676547166365e+304} " <> inspect(1.6776676547166365e+304))\n'
  'IO.puts("#{791306.0} " <> inspect(791306.0))\n'
  'IO.puts("#{941_273_215.461} " <> inspect(941_273_215.461))\n'
  'IO.puts("#{88065642468791.0} " <> inspect(88065642468791.0))\n'
  'IO.puts("#{672147298718777.5} " <> inspect(672147298718777.5))\n'
  'IO.puts("#{1.770979864155300398387282712064916267991065979003906250e0} " <> '
  'inspect(1.770979864155300398387282712064916267991065979003906250e0))\n'
  'IO.puts("#{7.98603627606120179914727192127971935503541403802192695916990024048488477243908383006742749981201632998296515494488100029855034124503511834789579423147011525743910410202836087909498147109613746754425016696475352369814194116065994566849512445894688093663707569902557736754532641517246376956553953583445479260161e307} '
  '" <> '
  'inspect(7.98603627606120179914727192127971935503541403802192695916990024048488477243908383006742749981201632998296515494488100029855034124503511834789579423147011525743910410202836087909498147109613746754425016696475352369814194116065994566849512445894688093663707569902557736754532641517246376956553953583445479260161e307))\n'
  'IO.puts("#{3.090303514099595e+19} " <> inspect(3.090303514099595e+19))\n'
  'IO.puts("#{6.409855420580593e-06} " <> inspect(6.409855420580593e-06))\n'
  'IO.puts("#{254915969.0} " <> inspect(254915969.0))\n'
  'IO.puts("#{2.089015665482287e-309} " <> inspect(2.089015665482287e-309))\n'
  'IO.puts("#{6.02479966275721e-182} " <> inspect(6.02479966275721e-182))\n'
  'IO.puts("#{259928.47287} " <> inspect(259928.47287))\n'
  'IO.puts("#{12706491766.962907892049165643009e156} " <> inspect(12706491766.962907892049165643009e156))\n'
  'IO.puts("#{428.44583110163603} " <> inspect(428.44583110163603))\n'
  'IO.puts("#{7.97015329862406e-309} " <> inspect(7.97015329862406e-309))\n'
  'IO.puts("#{2.3182343086965563e+118} " <> inspect(2.3182343086965563e+118))\n'
  'IO.puts("#{94.68187952073137} " <> inspect(94.68187952073137))\n'
  'IO.puts("#{496237471061133533315432.68070882047067600069974e134} " <> '
  'inspect(496237471061133533315432.68070882047067600069974e134))\n'
  '  end\n'
  'end\n',
  0,
  b'375.421 375.421\n-879088.8 -879088.8\n62.00724202646916 62.00724202646916\n1.520873253036128e-210 1.520'
  b'873253036128e-210\n781880.46 781880.46\n6.565173275017052e56 6.565173275017052e56\n121.612 121.612\n8.22'
  b'4650512724204e-177 8.224650512724204e-177\n2.5764595078388533e-231 2.5764595078388533e-231\n-189380378'
  b'940.0 -189380378940.0\n460186801.484 460186801.484\n7.12881346503468e190 7.12881346503468e190\n5.253807'
  b'105661922e-287 5.253807105661922e-287\n0.5 0.5\n2.989096728972427e163 2.989096728972427e163\n-975106.0 '
  b'-975106.0\n3.844989550636268e-166 3.844989550636268e-166\n4.455508415646675e189 4.455508415646675e189\n'
  b'852810694568.451 852810694568.451\n-1.350665515572045e17 -1.350665515572045e17\n3.102349907255565e-26 '
  b'3.102349907255565e-26\n-33260158.0 -33260158.0\n1.138481481714781e-308 1.138481481714781e-308\n12345678'
  b'9.0 123456789.0\n356.2739582621766 356.2739582621766\n-94842.82310044693 -94842.82310044693\n3.61473786'
  b'71465184e221 3.6147378671465184e221\n91832732001.0 91832732001.0\n268.34625647806024 268.3462564780602'
  b'4\n3.9387327849363804e-21 3.9387327849363804e-21\n2.01875680156313e82 2.01875680156313e82\n1.6776676547'
  b'166365e304 1.6776676547166365e304\n791306.0 791306.0\n941273215.461 941273215.461\n88065642468791.0 880'
  b'65642468791.0\n672147298718777.5 672147298718777.5\n1.7709798641553003 1.7709798641553003\n7.9860362760'
  b'61202e307 7.986036276061202e307\n3.090303514099595e19 3.090303514099595e19\n6.409855420580593e-6 6.409'
  b'855420580593e-6\n254915969.0 254915969.0\n2.089015665482287e-309 2.089015665482287e-309\n6.024799662757'
  b'21e-182 6.02479966275721e-182\n259928.47287 259928.47287\n1.2706491766962907e166 1.2706491766962907e16'
  b'6\n428.44583110163603 428.44583110163603\n7.97015329862406e-309 7.97015329862406e-309\n2.31823430869655'
  b'63e118 2.3182343086965563e118\n94.68187952073137 94.68187952073137\n4.962374710611335e157 4.9623747106'
  b'11335e157\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts("#{-3.642284421041558e+197} " <> inspect(-3.642284421041558e+197))\n'
  'IO.puts("#{-8.050028390691965e-224} " <> inspect(-8.050028390691965e-224))\n'
  'IO.puts("#{6180698217702552.91664594197589e-121} " <> inspect(6180698217702552.91664594197589e-121))\n'
  'IO.puts("#{-3.7752201859586308e+84} " <> inspect(-3.7752201859586308e+84))\n'
  'IO.puts("#{9.49200809268294e-309} " <> inspect(9.49200809268294e-309))\n'
  'IO.puts("#{-3.271286281905491e+284} " <> inspect(-3.271286281905491e+284))\n'
  'IO.puts("#{-4.3641937591439894e-263} " <> inspect(-4.3641937591439894e-263))\n'
  'IO.puts("#{4.417117661945961e+71} " <> inspect(4.417117661945961e+71))\n'
  'IO.puts("#{436.53644406472836} " <> inspect(436.53644406472836))\n'
  'IO.puts("#{1.2914061597716013e-206} " <> inspect(1.2914061597716013e-206))\n'
  'IO.puts("#{-1.186175308450813e-246} " <> inspect(-1.186175308450813e-246))\n'
  'IO.puts("#{-449486.0} " <> inspect(-449486.0))\n'
  'IO.puts("#{1.1352248469422897e-229} " <> inspect(1.1352248469422897e-229))\n'
  'IO.puts("#{-929791.4032} " <> inspect(-929791.4032))\n'
  'IO.puts("#{575.8118318916443} " <> inspect(575.8118318916443))\n'
  'IO.puts("#{-9.373115174349216e+185} " <> inspect(-9.373115174349216e+185))\n'
  'IO.puts("#{604_692_805_188.776} " <> inspect(604_692_805_188.776))\n'
  'IO.puts("#{-3.42477424324195e-236} " <> inspect(-3.42477424324195e-236))\n'
  'IO.puts("#{457.686402820515} " <> inspect(457.686402820515))\n'
  'IO.puts("#{5615043776011404.736034773750117099015e-117} " <> '
  'inspect(5615043776011404.736034773750117099015e-117))\n'
  'IO.puts("#{-717.6993344956584} " <> inspect(-717.6993344956584))\n'
  'IO.puts("#{2.7296241054675785} " <> inspect(2.7296241054675785))\n'
  'IO.puts("#{9.271335259028873e-168} " <> inspect(9.271335259028873e-168))\n'
  'IO.puts("#{6.052277488785252e-30} " <> inspect(6.052277488785252e-30))\n'
  'IO.puts("#{4.3952923387421405e+26} " <> inspect(4.3952923387421405e+26))\n'
  'IO.puts("#{602137.1333} " <> inspect(602137.1333))\n'
  'IO.puts("#{-3.627336780071897e-73} " <> inspect(-3.627336780071897e-73))\n'
  'IO.puts("#{-6.416276093270519e-261} " <> inspect(-6.416276093270519e-261))\n'
  'IO.puts("#{-1675295626711.0} " <> inspect(-1675295626711.0))\n'
  'IO.puts("#{66969865774878.0} " <> inspect(66969865774878.0))\n'
  'IO.puts("#{1.0861364149638798e-05} " <> inspect(1.0861364149638798e-05))\n'
  'IO.puts("#{17376021.442302753613797095733e-294} " <> inspect(17376021.442302753613797095733e-294))\n'
  'IO.puts("#{4.5935242089700004e-294} " <> inspect(4.5935242089700004e-294))\n'
  'IO.puts("#{7402817563.8368856e-223} " <> inspect(7402817563.8368856e-223))\n'
  'IO.puts("#{3.610858730443528e+16} " <> inspect(3.610858730443528e+16))\n'
  'IO.puts("#{123_484_748_523.844} " <> inspect(123_484_748_523.844))\n'
  'IO.puts("#{1.5972850127654981e-18} " <> inspect(1.5972850127654981e-18))\n'
  'IO.puts("#{1.0e-0} " <> inspect(1.0e-0))\n'
  'IO.puts("#{4191201472244352.52532831616025751257451e-145} " <> '
  'inspect(4191201472244352.52532831616025751257451e-145))\n'
  'IO.puts("#{-370.02313300009644} " <> inspect(-370.02313300009644))\n'
  'IO.puts("#{3.2626522339992623e-55} " <> inspect(3.2626522339992623e-55))\n'
  'IO.puts("#{5.960178953234477e-309} " <> inspect(5.960178953234477e-309))\n'
  'IO.puts("#{9007199254740992.0} " <> inspect(9007199254740992.0))\n'
  'IO.puts("#{497_199_545.852} " <> inspect(497_199_545.852))\n'
  'IO.puts("#{1.0598939654755962e-168} " <> inspect(1.0598939654755962e-168))\n'
  'IO.puts("#{-2.7666716567018014e-80} " <> inspect(-2.7666716567018014e-80))\n'
  'IO.puts("#{8.94185888191265e-309} " <> inspect(8.94185888191265e-309))\n'
  'IO.puts("#{3.5758759760389446e+21} " <> inspect(3.5758759760389446e+21))\n'
  'IO.puts("#{6.02479966275721e-182} " <> inspect(6.02479966275721e-182))\n'
  'IO.puts("#{614_802_952.193} " <> inspect(614_802_952.193))\n'
  '  end\n'
  'end\n',
  0,
  b'-3.642284421041558e197 -3.642284421041558e197\n-8.050028390691965e-224 -8.050028390691965e-224\n6.1806'
  b'98217702553e-106 6.180698217702553e-106\n-3.7752201859586308e84 -3.7752201859586308e84\n9.492008092682'
  b'94e-309 9.49200809268294e-309\n-3.271286281905491e284 -3.271286281905491e284\n-4.3641937591439894e-263'
  b' -4.3641937591439894e-263\n4.417117661945961e71 4.417117661945961e71\n436.53644406472836 436.536444064'
  b'72836\n1.2914061597716013e-206 1.2914061597716013e-206\n-1.186175308450813e-246 -1.186175308450813e-24'
  b'6\n-449486.0 -449486.0\n1.1352248469422897e-229 1.1352248469422897e-229\n-929791.4032 -929791.4032\n575.'
  b'8118318916443 575.8118318916443\n-9.373115174349216e185 -9.373115174349216e185\n604692805188.776 60469'
  b'2805188.776\n-3.42477424324195e-236 -3.42477424324195e-236\n457.686402820515 457.686402820515\n5.615043'
  b'776011405e-102 5.615043776011405e-102\n-717.6993344956584 -717.6993344956584\n2.7296241054675785 2.729'
  b'6241054675785\n9.271335259028873e-168 9.271335259028873e-168\n6.052277488785252e-30 6.052277488785252e'
  b'-30\n4.3952923387421405e26 4.3952923387421405e26\n602137.1333 602137.1333\n-3.627336780071897e-73 -3.62'
  b'7336780071897e-73\n-6.416276093270519e-261 -6.416276093270519e-261\n-1675295626711.0 -1675295626711.0\n'
  b'66969865774878.0 66969865774878.0\n1.0861364149638798e-5 1.0861364149638798e-5\n1.7376021442302755e-28'
  b'7 1.7376021442302755e-287\n4.5935242089700004e-294 4.5935242089700004e-294\n7.402817563836886e-214 7.4'
  b'02817563836886e-214\n3.610858730443528e16 3.610858730443528e16\n123484748523.844 123484748523.844\n1.59'
  b'72850127654981e-18 1.5972850127654981e-18\n1.0 1.0\n4.1912014722443526e-130 4.1912014722443526e-130\n-3'
  b'70.02313300009644 -370.02313300009644\n3.2626522339992623e-55 3.2626522339992623e-55\n5.96017895323447'
  b'7e-309 5.960178953234477e-309\n9.007199254740992e15 9007199254740992.0\n497199545.852 497199545.852\n1.'
  b'0598939654755962e-168 1.0598939654755962e-168\n-2.7666716567018014e-80 -2.7666716567018014e-80\n8.9418'
  b'5888191265e-309 8.94185888191265e-309\n3.5758759760389446e21 3.5758759760389446e21\n6.02479966275721e-'
  b'182 6.02479966275721e-182\n614802952.193 614802952.193\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts("#{1.629286742429765749022423726619341470668755458172912974248232848269912125936799144477550912107471849953458686922501838114696156365238242911820861796103315071055364726577100906127969620513850758774559762903557324859444782292098646416239012429143252638533202333885247336801573717124053902660236192093602394469886094382215909035488124202910330647715654995811269273436818556055183482577581439848322629558019652070682241186376377872231446153828788715046495926483793456730393672871827047245352291952353433461750843746333357624867170200431371574518172189776968732288685721936691930659934139716538790062120524344095642265341202913263914130106454038540708673110657400684431195259094238281249e-270} '
  '" <> '
  'inspect(1.629286742429765749022423726619341470668755458172912974248232848269912125936799144477550912107471849953458686922501838114696156365238242911820861796103315071055364726577100906127969620513850758774559762903557324859444782292098646416239012429143252638533202333885247336801573717124053902660236192093602394469886094382215909035488124202910330647715654995811269273436818556055183482577581439848322629558019652070682241186376377872231446153828788715046495926483793456730393672871827047245352291952353433461750843746333357624867170200431371574518172189776968732288685721936691930659934139716538790062120524344095642265341202913263914130106454038540708673110657400684431195259094238281249e-270))\n'
  'IO.puts("#{6.182638844724971e-167} " <> inspect(6.182638844724971e-167))\n'
  'IO.puts("#{8.314305143596198e-114} " <> inspect(8.314305143596198e-114))\n'
  'IO.puts("#{1.245899368887196e-206} " <> inspect(1.245899368887196e-206))\n'
  'IO.puts("#{1344502639136.8308} " <> inspect(1344502639136.8308))\n'
  'IO.puts("#{61808367735.0} " <> inspect(61808367735.0))\n'
  'IO.puts("#{-290859.6} " <> inspect(-290859.6))\n'
  'IO.puts("#{0.190074e87} " <> inspect(0.190074e87))\n'
  'IO.puts("#{2435638238913.0} " <> inspect(2435638238913.0))\n'
  'IO.puts("#{524.5406616324930204966079912e-211} " <> inspect(524.5406616324930204966079912e-211))\n'
  'IO.puts("#{934_515.136} " <> inspect(934_515.136))\n'
  'IO.puts("#{1.0e-0} " <> inspect(1.0e-0))\n'
  'IO.puts("#{219493476975091776500850.791162305253e-141} " <> '
  'inspect(219493476975091776500850.791162305253e-141))\n'
  'IO.puts("#{1.131988888473321e+64} " <> inspect(1.131988888473321e+64))\n'
  'IO.puts("#{704334174010.0} " <> inspect(704334174010.0))\n'
  'IO.puts("#{6.351463061309501e-263} " <> inspect(6.351463061309501e-263))\n'
  'IO.puts("#{-9.812718380288581e+260} " <> inspect(-9.812718380288581e+260))\n'
  'IO.puts("#{9517852887.200014803962e215} " <> inspect(9517852887.200014803962e215))\n'
  'IO.puts("#{-3.026415778437543e-133} " <> inspect(-3.026415778437543e-133))\n'
  'IO.puts("#{-611276452780361.9} " <> inspect(-611276452780361.9))\n'
  'IO.puts("#{149826.0} " <> inspect(149826.0))\n'
  'IO.puts("#{67040202016285652816294.53707540796e-130} " <> '
  'inspect(67040202016285652816294.53707540796e-130))\n'
  'IO.puts("#{0.33673544e-48} " <> inspect(0.33673544e-48))\n'
  'IO.puts("#{6.857655085992111e+302} " <> inspect(6.857655085992111e+302))\n'
  'IO.puts("#{41349.479079} " <> inspect(41349.479079))\n'
  'IO.puts("#{3.701491575958035e+224} " <> inspect(3.701491575958035e+224))\n'
  'IO.puts("#{7.77021311057983614325642312374006672757753780930454802768007770570812130285785732662621550179103122221668995786215919600505797052274508424798733256297529226971129062696587393467908137495259100297628704195746104773654684412852305920e229} '
  '" <> '
  'inspect(7.77021311057983614325642312374006672757753780930454802768007770570812130285785732662621550179103122221668995786215919600505797052274508424798733256297529226971129062696587393467908137495259100297628704195746104773654684412852305920e229))\n'
  'IO.puts("#{877206.551} " <> inspect(877206.551))\n'
  'IO.puts("#{1054657550551923.0} " <> inspect(1054657550551923.0))\n'
  'IO.puts("#{-10933.75} " <> inspect(-10933.75))\n'
  'IO.puts("#{5.978320115238021e-08} " <> inspect(5.978320115238021e-08))\n'
  'IO.puts("#{4.832426283889378e-14} " <> inspect(4.832426283889378e-14))\n'
  'IO.puts("#{283528474447077.3} " <> inspect(283528474447077.3))\n'
  'IO.puts("#{114.791} " <> inspect(114.791))\n'
  'IO.puts("#{-1.1132848236190815e-144} " <> inspect(-1.1132848236190815e-144))\n'
  'IO.puts("#{-2.1341185710654834e-81} " <> inspect(-2.1341185710654834e-81))\n'
  'IO.puts("#{795084.22785} " <> inspect(795084.22785))\n'
  'IO.puts("#{163493.17117} " <> inspect(163493.17117))\n'
  'IO.puts("#{2.0128589904991042e-233} " <> inspect(2.0128589904991042e-233))\n'
  'IO.puts("#{1.911407281375111e-308} " <> inspect(1.911407281375111e-308))\n'
  'IO.puts("#{873_349_146.535} " <> inspect(873_349_146.535))\n'
  'IO.puts("#{-5.137967560678052e-34} " <> inspect(-5.137967560678052e-34))\n'
  'IO.puts("#{4.004166190366202e-146} " <> inspect(4.004166190366202e-146))\n'
  'IO.puts("#{8.470329472543003e-22} " <> inspect(8.470329472543003e-22))\n'
  'IO.puts("#{51.8405972687713394007e-210} " <> inspect(51.8405972687713394007e-210))\n'
  'IO.puts("#{7.319604653182783e+131} " <> inspect(7.319604653182783e+131))\n'
  'IO.puts("#{0.0012432590397672394} " <> inspect(0.0012432590397672394))\n'
  'IO.puts("#{5.7094323552817145e+253} " <> inspect(5.7094323552817145e+253))\n'
  'IO.puts("#{67921028346645673494.21464677147e-33} " <> inspect(67921028346645673494.21464677147e-33))\n'
  'IO.puts("#{592_216.515} " <> inspect(592_216.515))\n'
  '  end\n'
  'end\n',
  0,
  b'1.6292867424297656e-270 1.6292867424297656e-270\n6.182638844724971e-167 6.182638844724971e-167\n8.3143'
  b'05143596198e-114 8.314305143596198e-114\n1.245899368887196e-206 1.245899368887196e-206\n1344502639136.'
  b'8308 1344502639136.8308\n61808367735.0 61808367735.0\n-290859.6 -290859.6\n1.90074e86 1.90074e86\n243563'
  b'8238913.0 2435638238913.0\n5.24540661632493e-209 5.24540661632493e-209\n934515.136 934515.136\n1.0 1.0\n'
  b'2.194934769750918e-118 2.194934769750918e-118\n1.131988888473321e64 1.131988888473321e64\n704334174010'
  b'.0 704334174010.0\n6.351463061309501e-263 6.351463061309501e-263\n-9.812718380288581e260 -9.8127183802'
  b'88581e260\n9.517852887200014e224 9.517852887200014e224\n-3.026415778437543e-133 -3.026415778437543e-13'
  b'3\n-611276452780361.9 -611276452780361.9\n149826.0 149826.0\n6.704020201628565e-108 6.704020201628565e-'
  b'108\n3.3673544e-49 3.3673544e-49\n6.857655085992111e302 6.857655085992111e302\n41349.479079 41349.47907'
  b'9\n3.701491575958035e224 3.701491575958035e224\n7.770213110579837e229 7.770213110579837e229\n877206.551'
  b' 877206.551\n1054657550551923.0 1054657550551923.0\n-10933.75 -10933.75\n5.978320115238021e-8 5.9783201'
  b'15238021e-8\n4.832426283889378e-14 4.832426283889378e-14\n283528474447077.3 283528474447077.3\n114.791 '
  b'114.791\n-1.1132848236190815e-144 -1.1132848236190815e-144\n-2.1341185710654834e-81 -2.134118571065483'
  b'4e-81\n795084.22785 795084.22785\n163493.17117 163493.17117\n2.0128589904991042e-233 2.0128589904991042'
  b'e-233\n1.911407281375111e-308 1.911407281375111e-308\n873349146.535 873349146.535\n-5.137967560678052e-'
  b'34 -5.137967560678052e-34\n4.004166190366202e-146 4.004166190366202e-146\n8.470329472543003e-22 8.4703'
  b'29472543003e-22\n5.184059726877134e-209 5.184059726877134e-209\n7.319604653182783e131 7.31960465318278'
  b'3e131\n0.0012432590397672394 0.0012432590397672394\n5.7094323552817145e253 5.7094323552817145e253\n6.79'
  b'2102834664567e-14 6.792102834664567e-14\n592216.515 592216.515\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts("#{1.0e0} " <> inspect(1.0e0))\n'
  'IO.puts("#{35539803062.3505335899019281568e-45} " <> inspect(35539803062.3505335899019281568e-45))\n'
  'IO.puts("#{8.721316032660397e-309} " <> inspect(8.721316032660397e-309))\n'
  'IO.puts("#{1.0} " <> inspect(1.0))\n'
  'IO.puts("#{1.57068435e-303} " <> inspect(1.57068435e-303))\n'
  'IO.puts("#{227.10447315869231189e-242} " <> inspect(227.10447315869231189e-242))\n'
  'IO.puts("#{5.909106315382871e-126} " <> inspect(5.909106315382871e-126))\n'
  'IO.puts("#{6.311054228357233e-08} " <> inspect(6.311054228357233e-08))\n'
  'IO.puts("#{-624885049568.0} " <> inspect(-624885049568.0))\n'
  'IO.puts("#{-84300.0} " <> inspect(-84300.0))\n'
  'IO.puts("#{644084.090348} " <> inspect(644084.090348))\n'
  'IO.puts("#{1.977371620166536e-308} " <> inspect(1.977371620166536e-308))\n'
  'IO.puts("#{-483855.509905} " <> inspect(-483855.509905))\n'
  'IO.puts("#{-3.425015292479569e-119} " <> inspect(-3.425015292479569e-119))\n'
  'IO.puts("#{2.05266436851307911012815549106363314289271979739936032545253753541201148458030266002338263386478183039822266364387750685734047514929834221675264416262507438659667968750e-49} '
  '" <> '
  'inspect(2.05266436851307911012815549106363314289271979739936032545253753541201148458030266002338263386478183039822266364387750685734047514929834221675264416262507438659667968750e-49))\n'
  'IO.puts("#{-261479.0} " <> inspect(-261479.0))\n'
  'IO.puts("#{-89075179468.0} " <> inspect(-89075179468.0))\n'
  'IO.puts("#{135935.894919} " <> inspect(135935.894919))\n'
  'IO.puts("#{884222366.374931476713482699735193e-112} " <> '
  'inspect(884222366.374931476713482699735193e-112))\n'
  'IO.puts("#{1.7290327071306454e-223} " <> inspect(1.7290327071306454e-223))\n'
  'IO.puts("#{860358077671928.6755543605971565037639e4} " <> '
  'inspect(860358077671928.6755543605971565037639e4))\n'
  'IO.puts("#{-765235.61295} " <> inspect(-765235.61295))\n'
  'IO.puts("#{189536.79381} " <> inspect(189536.79381))\n'
  'IO.puts("#{5.515652263101987e+216} " <> inspect(5.515652263101987e+216))\n'
  'IO.puts("#{0.09923655934986811} " <> inspect(0.09923655934986811))\n'
  'IO.puts("#{-200.81660199508235} " <> inspect(-200.81660199508235))\n'
  'IO.puts("#{6.938893903907228e-18} " <> inspect(6.938893903907228e-18))\n'
  'IO.puts("#{6.590419193872539e+142} " <> inspect(6.590419193872539e+142))\n'
  'IO.puts("#{7.349208577896573e+179} " <> inspect(7.349208577896573e+179))\n'
  'IO.puts("#{7.961303159219058e+16} " <> inspect(7.961303159219058e+16))\n'
  'IO.puts("#{7970.828219521486} " <> inspect(7970.828219521486))\n'
  'IO.puts("#{-2.946498254169656e-231} " <> inspect(-2.946498254169656e-231))\n'
  'IO.puts("#{-226549050866.3559} " <> inspect(-226549050866.3559))\n'
  'IO.puts("#{-459846171.0} " <> inspect(-459846171.0))\n'
  'IO.puts("#{-1.7917989691482383e-225} " <> inspect(-1.7917989691482383e-225))\n'
  'IO.puts("#{-955.3195439099653} " <> inspect(-955.3195439099653))\n'
  'IO.puts("#{4.40008029928310744395354906937289319639688601585705552690143388720168961e70} " <> '
  'inspect(4.40008029928310744395354906937289319639688601585705552690143388720168961e70))\n'
  'IO.puts("#{1.4886672275351804e-308} " <> inspect(1.4886672275351804e-308))\n'
  'IO.puts("#{1.0742204484476786e-178} " <> inspect(1.0742204484476786e-178))\n'
  'IO.puts("#{0.3} " <> inspect(0.3))\n'
  'IO.puts("#{2.984636599757591e-131} " <> inspect(2.984636599757591e-131))\n'
  'IO.puts("#{-6.23009575925199e-125} " <> inspect(-6.23009575925199e-125))\n'
  'IO.puts("#{424406.115} " <> inspect(424406.115))\n'
  'IO.puts("#{1.50489930173046e-308} " <> inspect(1.50489930173046e-308))\n'
  'IO.puts("#{1.5595107155491065e-308} " <> inspect(1.5595107155491065e-308))\n'
  'IO.puts("#{936.5429629827504} " <> inspect(936.5429629827504))\n'
  'IO.puts("#{604991189435351.894425711501620558143573e90} " <> '
  'inspect(604991189435351.894425711501620558143573e90))\n'
  'IO.puts("#{1.8762307157119124e-308} " <> inspect(1.8762307157119124e-308))\n'
  'IO.puts("#{5.1253327236687384e-144} " <> inspect(5.1253327236687384e-144))\n'
  'IO.puts("#{-3.0830023737319213e+297} " <> inspect(-3.0830023737319213e+297))\n'
  '  end\n'
  'end\n',
  0,
  b'1.0 1.0\n3.553980306235053e-35 3.553980306235053e-35\n8.721316032660397e-309 8.721316032660397e-309\n1.'
  b'0 1.0\n1.57068435e-303 1.57068435e-303\n2.271044731586923e-240 2.271044731586923e-240\n5.90910631538287'
  b'1e-126 5.909106315382871e-126\n6.311054228357233e-8 6.311054228357233e-8\n-624885049568.0 -62488504956'
  b'8.0\n-8.43e4 -84300.0\n644084.090348 644084.090348\n1.977371620166536e-308 1.977371620166536e-308\n-4838'
  b'55.509905 -483855.509905\n-3.425015292479569e-119 -3.425015292479569e-119\n2.0526643685130793e-49 2.05'
  b'26643685130793e-49\n-261479.0 -261479.0\n-89075179468.0 -89075179468.0\n135935.894919 135935.894919\n8.8'
  b'42223663749315e-104 8.842223663749315e-104\n1.7290327071306454e-223 1.7290327071306454e-223\n8.6035807'
  b'76719286e18 8.603580776719286e18\n-765235.61295 -765235.61295\n189536.79381 189536.79381\n5.51565226310'
  b'1987e216 5.515652263101987e216\n0.09923655934986811 0.09923655934986811\n-200.81660199508235 -200.8166'
  b'0199508235\n6.938893903907228e-18 6.938893903907228e-18\n6.590419193872539e142 6.590419193872539e142\n7'
  b'.349208577896573e179 7.349208577896573e179\n7.961303159219058e16 7.961303159219058e16\n7970.8282195214'
  b'86 7970.828219521486\n-2.946498254169656e-231 -2.946498254169656e-231\n-226549050866.3559 -22654905086'
  b'6.3559\n-459846171.0 -459846171.0\n-1.7917989691482383e-225 -1.7917989691482383e-225\n-955.319543909965'
  b'3 -955.3195439099653\n4.400080299283108e70 4.400080299283108e70\n1.4886672275351804e-308 1.48866722753'
  b'51804e-308\n1.0742204484476786e-178 1.0742204484476786e-178\n0.3 0.3\n2.984636599757591e-131 2.98463659'
  b'9757591e-131\n-6.23009575925199e-125 -6.23009575925199e-125\n424406.115 424406.115\n1.50489930173046e-3'
  b'08 1.50489930173046e-308\n1.5595107155491065e-308 1.5595107155491065e-308\n936.5429629827504 936.54296'
  b'29827504\n6.049911894353519e104 6.049911894353519e104\n1.8762307157119124e-308 1.8762307157119124e-308'
  b'\n5.1253327236687384e-144 5.1253327236687384e-144\n-3.0830023737319213e297 -3.0830023737319213e297\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts("#{245726856556824983485.581645710561e-31} " <> inspect(245726856556824983485.581645710561e-31))\n'
  'IO.puts("#{772.1739569188207} " <> inspect(772.1739569188207))\n'
  'IO.puts("#{2783044294.0} " <> inspect(2783044294.0))\n'
  'IO.puts("#{7.6409797926865e-310} " <> inspect(7.6409797926865e-310))\n'
  'IO.puts("#{9.092949315935642e-29} " <> inspect(9.092949315935642e-29))\n'
  'IO.puts("#{-604.7513755479443} " <> inspect(-604.7513755479443))\n'
  'IO.puts("#{176701.4449} " <> inspect(176701.4449))\n'
  'IO.puts("#{552_289.915} " <> inspect(552_289.915))\n'
  'IO.puts("#{-654.9732698399098} " <> inspect(-654.9732698399098))\n'
  'IO.puts("#{2.157253303736562e-308} " <> inspect(2.157253303736562e-308))\n'
  'IO.puts("#{0.0001} " <> inspect(0.0001))\n'
  'IO.puts("#{583435326395264547108935.6701247e-280} " <> inspect(583435326395264547108935.6701247e-280))\n'
  'IO.puts("#{-5.287689688583797e+63} " <> inspect(-5.287689688583797e+63))\n'
  'IO.puts("#{1.2217895253379843e-308} " <> inspect(1.2217895253379843e-308))\n'
  'IO.puts("#{1.0574179278569105e-308} " <> inspect(1.0574179278569105e-308))\n'
  'IO.puts("#{1.0e-7} " <> inspect(1.0e-7))\n'
  'IO.puts("#{3.105036184601418e+231} " <> inspect(3.105036184601418e+231))\n'
  'IO.puts("#{1.875463833563983e-308} " <> inspect(1.875463833563983e-308))\n'
  'IO.puts("#{54496.42179e-182} " <> inspect(54496.42179e-182))\n'
  'IO.puts("#{738.4911598266388} " <> inspect(738.4911598266388))\n'
  'IO.puts("#{636966554.3859823} " <> inspect(636966554.3859823))\n'
  'IO.puts("#{69.15287752361996} " <> inspect(69.15287752361996))\n'
  'IO.puts("#{8.256558099020199e-89} " <> inspect(8.256558099020199e-89))\n'
  'IO.puts("#{-1.872362598595162e+205} " <> inspect(-1.872362598595162e+205))\n'
  'IO.puts("#{4.9850658964674639796443282174530118684034551626330368188314160638359433218376555530259436697974391618052807839053667702020644498806343894587699917774584227113024714920430789371688776009745904484843903340271205332173891103215172619087016452262875810259179188225058336132835576129002253723688958501577351383540140665235144105645524170172647895651213319996960460961236189596648385487444561452975254987921300969217801773007564981196898802035664756148667275409254272887714100824665063330189911871853657437154217853396702963684571593040729706673116204354327888909751220902295298619886497956114762335374961328330169554878814608400716679170727729797363281251e-257} '
  '" <> '
  'inspect(4.9850658964674639796443282174530118684034551626330368188314160638359433218376555530259436697974391618052807839053667702020644498806343894587699917774584227113024714920430789371688776009745904484843903340271205332173891103215172619087016452262875810259179188225058336132835576129002253723688958501577351383540140665235144105645524170172647895651213319996960460961236189596648385487444561452975254987921300969217801773007564981196898802035664756148667275409254272887714100824665063330189911871853657437154217853396702963684571593040729706673116204354327888909751220902295298619886497956114762335374961328330169554878814608400716679170727729797363281251e-257))\n'
  'IO.puts("#{1492653472110731.2864845654449661094665e-138} " <> '
  'inspect(1492653472110731.2864845654449661094665e-138))\n'
  'IO.puts("#{833516.0} " <> inspect(833516.0))\n'
  'IO.puts("#{9.274467804694247e-309} " <> inspect(9.274467804694247e-309))\n'
  'IO.puts("#{-5.215524988277398e-277} " <> inspect(-5.215524988277398e-277))\n'
  'IO.puts("#{42874254381.0} " <> inspect(42874254381.0))\n'
  'IO.puts("#{-1.5891236979298077e+305} " <> inspect(-1.5891236979298077e+305))\n'
  'IO.puts("#{751938583938.0} " <> inspect(751938583938.0))\n'
  'IO.puts("#{1.4522751674099507e+178} " <> inspect(1.4522751674099507e+178))\n'
  'IO.puts("#{67287338635404510522125.1e156} " <> inspect(67287338635404510522125.1e156))\n'
  'IO.puts("#{6.242992959815317e-169} " <> inspect(6.242992959815317e-169))\n'
  'IO.puts("#{2552341.0} " <> inspect(2552341.0))\n'
  'IO.puts("#{-248.0225721381662} " <> inspect(-248.0225721381662))\n'
  'IO.puts("#{2.982059043205465e-10} " <> inspect(2.982059043205465e-10))\n'
  'IO.puts("#{1.141224374807671e-308} " <> inspect(1.141224374807671e-308))\n'
  'IO.puts("#{-2.6382037778213828e-23} " <> inspect(-2.6382037778213828e-23))\n'
  'IO.puts("#{-6.246720928551675e+240} " <> inspect(-6.246720928551675e+240))\n'
  'IO.puts("#{-60.36206001353219} " <> inspect(-60.36206001353219))\n'
  'IO.puts("#{53823786630321.13e-186} " <> inspect(53823786630321.13e-186))\n'
  'IO.puts("#{2936.25318e81} " <> inspect(2936.25318e81))\n'
  'IO.puts("#{-2.54960238327854e-194} " <> inspect(-2.54960238327854e-194))\n'
  'IO.puts("#{332.033} " <> inspect(332.033))\n'
  'IO.puts("#{9.027501131252832e+226} " <> inspect(9.027501131252832e+226))\n'
  'IO.puts("#{-854634.980237} " <> inspect(-854634.980237))\n'
  'IO.puts("#{23130.82127} " <> inspect(23130.82127))\n'
  'IO.puts("#{-1.0011727384198886e+88} " <> inspect(-1.0011727384198886e+88))\n'
  '  end\n'
  'end\n',
  0,
  b'2.4572685655682498e-11 2.4572685655682498e-11\n772.1739569188207 772.1739569188207\n2783044294.0 27830'
  b'44294.0\n7.6409797926865e-310 7.6409797926865e-310\n9.092949315935642e-29 9.092949315935642e-29\n-604.7'
  b'513755479443 -604.7513755479443\n176701.4449 176701.4449\n552289.915 552289.915\n-654.9732698399098 -65'
  b'4.9732698399098\n2.157253303736562e-308 2.157253303736562e-308\n0.0001 0.0001\n5.834353263952646e-257 5'
  b'.834353263952646e-257\n-5.287689688583797e63 -5.287689688583797e63\n1.2217895253379843e-308 1.22178952'
  b'53379843e-308\n1.0574179278569105e-308 1.0574179278569105e-308\n1.0e-7 1.0e-7\n3.105036184601418e231 3.'
  b'105036184601418e231\n1.875463833563983e-308 1.875463833563983e-308\n5.449642179e-178 5.449642179e-178\n'
  b'738.4911598266388 738.4911598266388\n636966554.3859823 636966554.3859823\n69.15287752361996 69.1528775'
  b'2361996\n8.256558099020199e-89 8.256558099020199e-89\n-1.872362598595162e205 -1.872362598595162e205\n4.'
  b'985065896467464e-257 4.985065896467464e-257\n1.4926534721107313e-123 1.4926534721107313e-123\n833516.0'
  b' 833516.0\n9.274467804694247e-309 9.274467804694247e-309\n-5.215524988277398e-277 -5.215524988277398e-'
  b'277\n42874254381.0 42874254381.0\n-1.5891236979298077e305 -1.5891236979298077e305\n751938583938.0 75193'
  b'8583938.0\n1.4522751674099507e178 1.4522751674099507e178\n6.72873386354045e178 6.72873386354045e178\n6.'
  b'242992959815317e-169 6.242992959815317e-169\n2552341.0 2552341.0\n-248.0225721381662 -248.022572138166'
  b'2\n2.982059043205465e-10 2.982059043205465e-10\n1.141224374807671e-308 1.141224374807671e-308\n-2.63820'
  b'37778213828e-23 -2.6382037778213828e-23\n-6.246720928551675e240 -6.246720928551675e240\n-60.3620600135'
  b'3219 -60.36206001353219\n5.382378663032113e-173 5.382378663032113e-173\n2.93625318e84 2.93625318e84\n-2'
  b'.54960238327854e-194 -2.54960238327854e-194\n332.033 332.033\n9.027501131252832e226 9.027501131252832e'
  b'226\n-854634.980237 -854634.980237\n23130.82127 23130.82127\n-1.0011727384198886e88 -1.0011727384198886'
  b'e88\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(7.685501178287569e-133))\n  end\nend\n',
  0,
  b'7.685501178287569e-133\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(-5.0e-324))\n'
  'IO.puts(inspect((1.5) * 1000000000000000.0 + 0.3))\n'
  'IO.puts(inspect((874.0) + (-31.642052263706915)))\n'
  'IO.puts(inspect(1.0e+308))\n'
  'IO.puts(inspect((1.0e-160 * (8.22530602375216e+295) * (-1.0e-200 * 1.60957324078822e+35)) + 1.0e-320 * '
  '3.0))\n'
  '  end\n'
  'end\n',
  0,
  b'-5.0e-324\n1500000000000000.2\n842.3579477362931\n1.0e308\n-1.323923247312563e-29\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(87.28262627420975 - 1.0))\n'
  'IO.puts(inspect(-1.4308433540797653e-230 * 5.0e-324 * 95.0 + (0.9999999999999999)))\n'
  'IO.puts(inspect(1.1890422028876234e+178 + (1.0e+200) + (1.0e+200) - ((0.0 + (9007199254740992.0)) * '
  '((1.0000000000000002) * (-2.5)))))\n'
  'IO.puts(inspect(2.2250738585072014e-308 * 9007199254740992.0))\n'
  'IO.puts(inspect(5.0e-324 - (-20.941960034654187) + (8.139031277478758e+123 - (-96.59807186981352))))\n'
  '  end\n'
  'end\n',
  0,
  b'86.28262627420975\n0.9999999999999999\n2.0e200\n2.004168360008973e-292\n8.139031277478758e123\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(8.186661307777221e+301))\n  end\nend\n',
  0,
  b'8.186661307777221e301\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(-27.0 - (-504041589.99941754)))\n'
  'IO.puts(inspect(3.055604050415308e-236 - (5.0169276004193883e+138 / 0.1)))\n'
  'IO.puts(inspect(1.0e+200))\n'
  'IO.puts(inspect(661.0 / 1.5 - (-1.0e+308) + 1.0e+16))\n'
  'IO.puts(inspect(1.4113290360170589e-95 + 4.7319935431057536e+32 - (-1.0e-200)))\n'
  '  end\n'
  'end\n',
  0,
  b'504041562.99941754\n-5.016927600419388e139\n1.0e200\n1.0e308\n4.7319935431057536e32\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(((1.0e+308) - (-710.0)) + 1.0e+200 + (-1.1284469810269443e+105) + (-1.0e-200) / '
  '(5.0e-324) * 0.3 * (-1.0e-200)))\n'
  'IO.puts(inspect(1.0523148217466608e+290))\n'
  'IO.puts(inspect((0.0 + 1.0e-320 * ((123.456) + 3.600669159268507e+79)) * (-1.0e+150 - '
  '(-24.067514371635497) * (-24.012465983087637 - (-3.0354430413149172e+224)))))\n'
  'IO.puts(inspect(3.0 * (-778.0)))\n'
  'IO.puts(inspect(-5.0e-324 * (-1.620360681786796e-281 - (79.26726454141851 / 1.1756292127427262e-298))))\n'
  '  end\n'
  'end\n',
  0,
  b'1.0e308\n1.0523148217466608e290\n2.6304600581145555e-15\n-2334.0\n3.331257153635849e-24\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(-1.0e-200))\n  end\nend\n', 0, b'-1.0e-200\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(-8.651572059183281e-279))\n'
  'IO.puts(inspect((-1.0e-200) * (-1.929959759159203e-71)))\n'
  'IO.puts(inspect((-712.0) + 0.2))\n'
  'IO.puts(inspect(-1.1920038596303412e+136))\n'
  'IO.puts(inspect(7.749557279510516e+256 + 1.7053821722063986e+94 + (-1.0e+150 * 0.3)))\n'
  '  end\n'
  'end\n',
  0,
  b'-8.651572059183281e-279\n1.929959759159203e-271\n-711.8\n-1.1920038596303412e136\n7.749557279510516e256\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect((273.0) - 852.0 + (-883.0 - (-511.0)) - (-865.0)))\n'
  'IO.puts(inspect(1.0e+200 - 804.0 - (-5.0e-324 / 1.0e-160 + (-2.6041519116156562e-54 + 1.5))))\n'
  'IO.puts(inspect(6.919793949091547e-92))\n'
  'IO.puts(inspect(-1.0 * (-1.0e+308) - (-1.4939496270493497e-213 - 3.0)))\n'
  'IO.puts(inspect(-3.050239769417317))\n'
  '  end\n'
  'end\n',
  0,
  b'-86.0\n1.0e200\n6.919793949091547e-92\n1.0e308\n-3.050239769417317\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(5.0e-324))\n'
  'IO.puts(inspect(94.15857962708066 + (57.0) + (-1.0e+308 * 1.0e-200) * 290.0 - 1000000000000000.0 - '
  '1.0e+150 + (4.917601656688732e+60)))\n'
  'IO.puts(inspect(1.0e-160))\n'
  'IO.puts(inspect((95.54954016226489) + (0.1)))\n'
  'IO.puts(inspect(-76.22509760153852))\n'
  '  end\n'
  'end\n',
  0,
  b'5.0e-324\n-1.0e150\n1.0e-160\n95.64954016226488\n-76.22509760153852\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect((64.74529502518155 * (871.0) * (0.1)) - (-4.60770526447061)))\n'
  '  end\n'
  'end\n',
  0,
  b'5643.922901957784\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(383.0))\n'
  'IO.puts(inspect(0.5 + 593.0))\n'
  'IO.puts(inspect(2.1422986463283743e-299 - (582.0) * ((2.2250738585072014e-308) / 2.6971218740991916e-219) '
  '- (426.0) - 1.7976931348623157e+308 * (1.0e-320 - (5.0e-324))))\n'
  'IO.puts(inspect(5.0e-324 + (-1.0) - (-2.865027041858098e-264 * 6.4886162784470446e-130)))\n'
  'IO.puts(inspect(-3.1622958155833474e-169 + (1.0e-160)))\n'
  '  end\n'
  'end\n',
  0,
  b'383.0\n593.5\n-426.0000000000018\n-1.0\n9.999999968377042e-161\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(-787.0))\n'
  'IO.puts(inspect((2.352210672829394e+175) + (-2.5) * (-1.0e+150 - (-606.0))))\n'
  'IO.puts(inspect(54.17438503517215))\n'
  'IO.puts(inspect(123.456))\n'
  'IO.puts(inspect((-5.0e-324 * (-322.0) * 1.5) * 752.0))\n'
  '  end\n'
  'end\n',
  0,
  b'-787.0\n2.352210672829394e175\n54.17438503517215\n123.456\n1.794525e-318\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(-2.0584946358692288e+173 + 4.588343567459629e-255 / (-5.445172827308245e-144)))\n'
  '  end\n'
  'end\n',
  0,
  b'-2.0584946358692288e173\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect((95.47279915381407 - 5.0e-324) - 625.0 - (-4.73001607988496e+16) + (97.28233214850454 * '
  '(5.0e-324) - (1000000000000000.0))))\n'
  'IO.puts(inspect((1.0e-320) + 1.7976931348623157e+308))\n'
  'IO.puts(inspect(-8.802028060087172e-257))\n'
  'IO.puts(inspect(1000000000000000.0 + 1.0000000000000002 - 1.0e+150 - (9007199254740992.0)))\n'
  'IO.puts(inspect(-5.0e-324 / 19.788424155151233))\n'
  '  end\n'
  'end\n',
  0,
  b'4.630016079884907e16\n1.7976931348623157e308\n-8.802028060087172e-257\n-1.0e150\n-0.0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(((3.194962279276955e+81) * 1.0e-160) + (9007199254740992.0 + 0.9999999999999999)))\n'
  'IO.puts(inspect(-3.833688416857797e+78 / 34.0))\n'
  'IO.puts(inspect((-9.539053082328101e+175) * (-1.7554056738329848e-196)))\n'
  'IO.puts(inspect((0.1) + (1.0) - 15.891763670928484))\n'
  'IO.puts(inspect(9007199254740992.0 - (-2.376327392469625e-149) + (-6.472696174714589e+235) * (-202.0) * '
  '(-7.746918206606953e-160 + 1.0e+308 + 5.0e-324 / (-402.0))))\n'
  '  end\n'
  'end\n',
  0,
  b'9007199254740992.0\n-1.1275554167228815e77\n1.674490790371277e-20\n-14.791763670928484\n+Inf\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1.0e-200))\n  end\nend\n', 0, b'1.0e-200\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(5.0e-324 + 1.0e+200))\n'
  'IO.puts(inspect(0.0))\n'
  'IO.puts(inspect(-5.199934076177294e+181 * (-297.0 + 1.0000000000000002) - 9007199254740992.0 - '
  '(-53.365240881612074)))\n'
  'IO.puts(inspect(-1.0e+308))\n'
  'IO.puts(inspect(5.0e-324))\n'
  '  end\n'
  'end\n',
  0,
  b'1.0e200\n0.0\n1.539180486548479e184\n-1.0e308\n5.0e-324\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect((1.0e+150) / (-5.1559242324135325e+212)))\n'
  'IO.puts(inspect(1.0))\n'
  'IO.puts(inspect((-766.0) + (-22.0)))\n'
  'IO.puts(inspect(-458.0 - 1.0e-160 - (-8.368403956951431e-252)))\n'
  'IO.puts(inspect(9.153098201363205e+140 - (-88.0)))\n'
  '  end\n'
  'end\n',
  0,
  b'-1.9395164764317946e-63\n1.0\n-788.0\n-458.0\n9.153098201363205e140\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect(5.0e-324))\n'
  'IO.puts(inspect(1.692412366516352e-88))\n'
  'IO.puts(inspect(((41.457595369039154 - 9.511057751493352e-172) + 0.9999999999999999 / (123.456)) - '
  '123.456 + 1.0e+16 + (613.0)))\n'
  'IO.puts(inspect((3.0) - 4.3902077565962204e-58 + 1000000000000000.0))\n'
  'IO.puts(inspect((0.1) / 0.3))\n'
  '  end\n'
  'end\n',
  0,
  b'5.0e-324\n1.692412366516352e-88\n1.0000000000000532e16\n1000000000000003.0\n0.33333333333333337\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'a0 = 1.0e-320\n'
  'b0 = 642.0\n'
  'c0 = -62.85516522525292\n'
  'IO.puts("#{a0 - b0 - c0} #{a0 < b0} #{a0 == b0} #{a0 >= c0} #{-a0} #{abs(b0)} #{min(a0, b0)} #{max(a0, '
  'c0)}")\n'
  'a1 = 312.0\n'
  'b1 = -73.95739544804863\n'
  'c1 = -6.004039341439814e-07\n'
  'IO.puts("#{a1 * b1 + c1} #{a1 < b1} #{a1 == b1} #{a1 >= c1} #{-a1} #{abs(b1)} #{min(a1, b1)} #{max(a1, '
  'c1)}")\n'
  'a2 = 123.456\n'
  'b2 = 7.15127490002977e-291\n'
  'c2 = 708.0\n'
  'IO.puts("#{a2 - b2 + c2} #{a2 < b2} #{a2 == b2} #{a2 >= c2} #{-a2} #{abs(b2)} #{min(a2, b2)} #{max(a2, '
  'c2)}")\n'
  'a3 = 658.0\n'
  'b3 = -463.0\n'
  'c3 = 48.95003056044152\n'
  'IO.puts("#{a3 - b3 * c3} #{a3 < b3} #{a3 == b3} #{a3 >= c3} #{-a3} #{abs(b3)} #{min(a3, b3)} #{max(a3, '
  'c3)}")\n'
  'a4 = -2.5\n'
  'b4 = -1.0e+150\n'
  'c4 = 5.6029891053604265e+221\n'
  'IO.puts("#{a4 * b4 * c4} #{a4 < b4} #{a4 == b4} #{a4 >= c4} #{-a4} #{abs(b4)} #{min(a4, b4)} #{max(a4, '
  'c4)}")\n'
  'a5 = 5.927687711863969e-164\n'
  'b5 = 9007199254740992.0\n'
  'c5 = 97.13623711897404\n'
  'IO.puts("#{a5 / b5 - c5} #{a5 < b5} #{a5 == b5} #{a5 >= c5} #{-a5} #{abs(b5)} #{min(a5, b5)} #{max(a5, '
  'c5)}")\n'
  'a6 = 1.0e+150\n'
  'b6 = 0.3\n'
  'c6 = 0.3\n'
  'IO.puts("#{a6 * b6 * c6} #{a6 < b6} #{a6 == b6} #{a6 >= c6} #{-a6} #{abs(b6)} #{min(a6, b6)} #{max(a6, '
  'c6)}")\n'
  'a7 = 1.0e-200\n'
  'b7 = -1.1125334562654325e+172\n'
  'c7 = -5.0e-324\n'
  'IO.puts("#{a7 - b7 - c7} #{a7 < b7} #{a7 == b7} #{a7 >= c7} #{-a7} #{abs(b7)} #{min(a7, b7)} #{max(a7, '
  'c7)}")\n'
  'a8 = 436.0\n'
  'b8 = -1.0\n'
  'c8 = 0.5\n'
  'IO.puts("#{a8 / b8 * c8} #{a8 < b8} #{a8 == b8} #{a8 >= c8} #{-a8} #{abs(b8)} #{min(a8, b8)} #{max(a8, '
  'c8)}")\n'
  'a9 = 1.7976931348623157e+308\n'
  'b9 = -912.0\n'
  'c9 = -5.0e-324\n'
  'IO.puts("#{a9 / b9 * c9} #{a9 < b9} #{a9 == b9} #{a9 >= c9} #{-a9} #{abs(b9)} #{min(a9, b9)} #{max(a9, '
  'c9)}")\n'
  'a10 = 1.7976931348623157e+308\n'
  'b10 = -49.74445121557651\n'
  'c10 = -29.88171994230406\n'
  'IO.puts("#{a10 * b10 - c10} #{a10 < b10} #{a10 == b10} #{a10 >= c10} #{-a10} #{abs(b10)} #{min(a10, b10)} '
  '#{max(a10, c10)}")\n'
  'a11 = 441.0\n'
  'b11 = 1.1277426374057956e+304\n'
  'c11 = 9007199254740992.0\n'
  'IO.puts("#{a11 + b11 + c11} #{a11 < b11} #{a11 == b11} #{a11 >= c11} #{-a11} #{abs(b11)} #{min(a11, b11)} '
  '#{max(a11, c11)}")\n'
  'a12 = 1.0e+150\n'
  'b12 = 1.6197761213437459e+56\n'
  'c12 = 1.0e-160\n'
  'IO.puts("#{a12 + b12 - c12} #{a12 < b12} #{a12 == b12} #{a12 >= c12} #{-a12} #{abs(b12)} #{min(a12, b12)} '
  '#{max(a12, c12)}")\n'
  'a13 = 1.7976931348623157e+308\n'
  'b13 = -4.164210078063188e+70\n'
  'c13 = -8.941715323869011e+272\n'
  'IO.puts("#{a13 / b13 * c13} #{a13 < b13} #{a13 == b13} #{a13 >= c13} #{-a13} #{abs(b13)} #{min(a13, b13)} '
  '#{max(a13, c13)}")\n'
  'a14 = 5.39421146935255e-305\n'
  'b14 = -1.0e-200\n'
  'c14 = -1.0e-200\n'
  'IO.puts("#{a14 * b14 + c14} #{a14 < b14} #{a14 == b14} #{a14 >= c14} #{-a14} #{abs(b14)} #{min(a14, b14)} '
  '#{max(a14, c14)}")\n'
  'a15 = 69.0\n'
  'b15 = 123.456\n'
  'c15 = 1.0e+200\n'
  'IO.puts("#{a15 * b15 - c15} #{a15 < b15} #{a15 == b15} #{a15 >= c15} #{-a15} #{abs(b15)} #{min(a15, b15)} '
  '#{max(a15, c15)}")\n'
  'a16 = 3.0\n'
  'b16 = 1.2517828132262522e-33\n'
  'c16 = -3.084995200497577e+60\n'
  'IO.puts("#{a16 + b16 * c16} #{a16 < b16} #{a16 == b16} #{a16 >= c16} #{-a16} #{abs(b16)} #{min(a16, b16)} '
  '#{max(a16, c16)}")\n'
  'a17 = 5.650606948552294e-115\n'
  'b17 = -48.33702232634882\n'
  'c17 = 2.4079443586692608e-43\n'
  'IO.puts("#{a17 * b17 * c17} #{a17 < b17} #{a17 == b17} #{a17 >= c17} #{-a17} #{abs(b17)} #{min(a17, b17)} '
  '#{max(a17, c17)}")\n'
  'a18 = -3.6547232063856764e+28\n'
  'b18 = -1.0e-200\n'
  'c18 = 0.5\n'
  'IO.puts("#{a18 * b18 * c18} #{a18 < b18} #{a18 == b18} #{a18 >= c18} #{-a18} #{abs(b18)} #{min(a18, b18)} '
  '#{max(a18, c18)}")\n'
  'a19 = -1.0e+308\n'
  'b19 = -1.0\n'
  'c19 = 19.96180105403147\n'
  'IO.puts("#{a19 + b19 * c19} #{a19 < b19} #{a19 == b19} #{a19 >= c19} #{-a19} #{abs(b19)} #{min(a19, b19)} '
  '#{max(a19, c19)}")\n'
  '  end\n'
  'end\n',
  0,
  b'-579.1448347747471 true false true -1.0e-320 642.0 1.0e-320 1.0e-320\n-23074.707380391577 false false tru'
  b'e -312.0 73.95739544804863 -73.95739544804863 312.0\n831.456 false false false -123.456 7.15127490002977e'
  b'-291 7.15127490002977e-291 708.0\n23321.864149484423 false false true -658.0 463.0 -463.0 658.0\n+Inf '
  b'false false false 2.5 1.0e150 -1.0e150 5.6029891053604265e221\n-97.13623711897404 true false false -5.927'
  b'687711863969e-164 9.007199254740992e15 5.927687711863969e-164 97.13623711897404\n9.0e148 false false true'
  b' -1.0e150 0.3 0.3 1.0e150\n1.1125334562654325e172 false false true -1.0e-200 1.1125334562654325e172 -1.11'
  b'25334562654325e172 1.0e-200\n-218.0 false false true -436.0 1.0 -1.0 436.0\n9.73879846162418e-19 false'
  b' false true -1.7976931348623157e308 912.0 -912.0 1.7976931348623157e308\n-Inf false false true -1.7976931'
  b'348623157e308 49.74445121557651 -49.74445121557651 1.7976931348623157e308\n1.1277426374057956e304 true fa'
  b'lse false -441.0 1.1277426374057956e304 441.0 9.007199254740992e15\n1.0e150 false false true -1.0e150 1.6'
  b'197761213437459e56 1.6197761213437459e56 1.0e150\n+Inf false false true -1.7976931348623157e308 4.1642100'
  b'78063188e70 -4.164210078063188e70 1.7976931348623157e308\n-1.0e-200 false false true -5.39421146935255e-3'
  b'05 1.0e-200 -1.0e-200 5.39421146935255e-305\n-1.0e200 true false false -69.0 123.456 69.0 1.0e200\n-3.'
  b'861743970868343e27 false false true -3.0 1.2517828132262522e-33 1.2517828132262522e-33 3.0\n-6.5769030475'
  b'26612e-156 false false false -5.650606948552294e-115 48.33702232634882 -48.33702232634882 2.407944358669'
  b'2608e-43\n1.8273616031928383e-172 true false false 3.6547232063856764e28 1.0e-200 -3.6547232063856764e28 '
  b'0.5\n-1.0e308 true false false 1.0e308 1.0 -1.0e308 19.96180105403147\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'a0 = -5.0e-324\n'
  'b0 = -202.0\n'
  'c0 = -1.0e-200\n'
  'IO.puts("#{a0 / b0 - c0} #{a0 < b0} #{a0 == b0} #{a0 >= c0} #{-a0} #{abs(b0)} #{min(a0, b0)} #{max(a0, '
  'c0)}")\n'
  'a1 = 1.0\n'
  'b1 = 123.456\n'
  'c1 = -1.0e-200\n'
  'IO.puts("#{a1 * b1 * c1} #{a1 < b1} #{a1 == b1} #{a1 >= c1} #{-a1} #{abs(b1)} #{min(a1, b1)} #{max(a1, '
  'c1)}")\n'
  'a2 = 1.0e+308\n'
  'b2 = 1.0e+308\n'
  'c2 = 1.0e+16\n'
  'IO.puts("#{a2 / b2 + c2} #{a2 < b2} #{a2 == b2} #{a2 >= c2} #{-a2} #{abs(b2)} #{min(a2, b2)} #{max(a2, '
  'c2)}")\n'
  'a3 = -1.0e-200\n'
  'b3 = 1.0e-160\n'
  'c3 = 0.3\n'
  'IO.puts("#{a3 - b3 + c3} #{a3 < b3} #{a3 == b3} #{a3 >= c3} #{-a3} #{abs(b3)} #{min(a3, b3)} #{max(a3, '
  'c3)}")\n'
  'a4 = 868.0\n'
  'b4 = -694.0\n'
  'c4 = 0.9999999999999999\n'
  'IO.puts("#{a4 * b4 + c4} #{a4 < b4} #{a4 == b4} #{a4 >= c4} #{-a4} #{abs(b4)} #{min(a4, b4)} #{max(a4, '
  'c4)}")\n'
  'a5 = 1.0e-160\n'
  'b5 = -90.60985487941706\n'
  'c5 = 123.456\n'
  'IO.puts("#{a5 - b5 * c5} #{a5 < b5} #{a5 == b5} #{a5 >= c5} #{-a5} #{abs(b5)} #{min(a5, b5)} #{max(a5, '
  'c5)}")\n'
  'a6 = -1.0e+308\n'
  'b6 = -1.3688679536285907e-250\n'
  'c6 = -764.0\n'
  'IO.puts("#{a6 - b6 * c6} #{a6 < b6} #{a6 == b6} #{a6 >= c6} #{-a6} #{abs(b6)} #{min(a6, b6)} #{max(a6, '
  'c6)}")\n'
  'a7 = 6.257400144236571e-125\n'
  'b7 = -390.0\n'
  'c7 = 1.0e+308\n'
  'IO.puts("#{a7 + b7 + c7} #{a7 < b7} #{a7 == b7} #{a7 >= c7} #{-a7} #{abs(b7)} #{min(a7, b7)} #{max(a7, '
  'c7)}")\n'
  'a8 = 0.0\n'
  'b8 = 5.0e-324\n'
  'c8 = -1.0\n'
  'IO.puts("#{a8 * b8 * c8} #{a8 < b8} #{a8 == b8} #{a8 >= c8} #{-a8} #{abs(b8)} #{min(a8, b8)} #{max(a8, '
  'c8)}")\n'
  'a9 = 123.456\n'
  'b9 = 1.5015365602698267e+50\n'
  'c9 = -917.0\n'
  'IO.puts("#{a9 + b9 + c9} #{a9 < b9} #{a9 == b9} #{a9 >= c9} #{-a9} #{abs(b9)} #{min(a9, b9)} #{max(a9, '
  'c9)}")\n'
  'a10 = -1.0e+308\n'
  'b10 = 1.0e-200\n'
  'c10 = 0.2\n'
  'IO.puts("#{a10 / b10 * c10} #{a10 < b10} #{a10 == b10} #{a10 >= c10} #{-a10} #{abs(b10)} #{min(a10, b10)} '
  '#{max(a10, c10)}")\n'
  'a11 = 0.0\n'
  'b11 = 2.3479627581618636e+101\n'
  'c11 = -2.5\n'
  'IO.puts("#{a11 * b11 * c11} #{a11 < b11} #{a11 == b11} #{a11 >= c11} #{-a11} #{abs(b11)} #{min(a11, b11)} '
  '#{max(a11, c11)}")\n'
  'a12 = 123.456\n'
  'b12 = -3.1904870134841445\n'
  'c12 = 5.0e-324\n'
  'IO.puts("#{a12 / b12 - c12} #{a12 < b12} #{a12 == b12} #{a12 >= c12} #{-a12} #{abs(b12)} #{min(a12, b12)} '
  '#{max(a12, c12)}")\n'
  'a13 = 42.81995218411771\n'
  'b13 = -94.18866996029591\n'
  'c13 = -13.0\n'
  'IO.puts("#{a13 - b13 - c13} #{a13 < b13} #{a13 == b13} #{a13 >= c13} #{-a13} #{abs(b13)} #{min(a13, b13)} '
  '#{max(a13, c13)}")\n'
  'a14 = 1.0e+16\n'
  'b14 = -1.0\n'
  'c14 = 17.0\n'
  'IO.puts("#{a14 + b14 - c14} #{a14 < b14} #{a14 == b14} #{a14 >= c14} #{-a14} #{abs(b14)} #{min(a14, b14)} '
  '#{max(a14, c14)}")\n'
  'a15 = 82.22505844986298\n'
  'b15 = -2.7445344871733747e+258\n'
  'c15 = -5.580979405199091e+138\n'
  'IO.puts("#{a15 - b15 * c15} #{a15 < b15} #{a15 == b15} #{a15 >= c15} #{-a15} #{abs(b15)} #{min(a15, b15)} '
  '#{max(a15, c15)}")\n'
  'a16 = -69.25125621208066\n'
  'b16 = 2.2250738585072014e-308\n'
  'c16 = -1.0e+150\n'
  'IO.puts("#{a16 * b16 - c16} #{a16 < b16} #{a16 == b16} #{a16 >= c16} #{-a16} #{abs(b16)} #{min(a16, b16)} '
  '#{max(a16, c16)}")\n'
  'a17 = 9007199254740992.0\n'
  'b17 = 1.0e+200\n'
  'c17 = -9.803455122090432e-221\n'
  'IO.puts("#{a17 / b17 * c17} #{a17 < b17} #{a17 == b17} #{a17 >= c17} #{-a17} #{abs(b17)} #{min(a17, b17)} '
  '#{max(a17, c17)}")\n'
  'a18 = 5.428034238268016e-246\n'
  'b18 = 6.212387115778398e+218\n'
  'c18 = 2.2250738585072014e-308\n'
  'IO.puts("#{a18 + b18 + c18} #{a18 < b18} #{a18 == b18} #{a18 >= c18} #{-a18} #{abs(b18)} #{min(a18, b18)} '
  '#{max(a18, c18)}")\n'
  'a19 = 0.2\n'
  'b19 = 673.0\n'
  'c19 = 0.2\n'
  'IO.puts("#{a19 * b19 - c19} #{a19 < b19} #{a19 == b19} #{a19 >= c19} #{-a19} #{abs(b19)} #{min(a19, b19)} '
  '#{max(a19, c19)}")\n'
  '  end\n'
  'end\n',
  0,
  b'1.0e-200 false false true 5.0e-324 202.0 -202.0 -5.0e-324\n-1.23456e-198 true false true -1.0 123.456 1.0'
  b' 1.0\n1.0e16 false true true -1.0e308 1.0e308 1.0e308 1.0e308\n0.3 true false false 1.0e-200 1.0e-160 '
  b'-1.0e-200 0.3\n-602391.0 false false true -868.0 694.0 -694.0 868.0\n11186.330243993312 false false fa'
  b'lse -1.0e-160 90.60985487941706 -90.60985487941706 123.456\n-1.0e308 true false false 1.0e308 1.368867953'
  b'6285907e-250 -1.0e308 -764.0\n1.0e308 false false false -6.257400144236571e-125 390.0 -390.0 1.0e308\n'
  b'-0.0 true false true -0.0 5.0e-324 0.0 0.0\n1.5015365602698267e50 true false true -123.456 1.501536560269'
  b'8267e50 123.456 123.456\n-Inf true false false 1.0e308 1.0e-200 -1.0e308 0.2\n-0.0 true false true -0.'
  b'0 2.3479627581618636e101 0.0 0.0\n-38.69503291448314 false false true -123.456 3.1904870134841445 -3.1904'
  b'870134841445 123.456\n150.0086221444136 false false true -42.81995218411771 94.18866996029591 -94.1886699'
  b'6029591 42.81995218411771\n9.999999999999984e15 false false true -1.0e16 1.0 -1.0 1.0e16\n-Inf false f'
  b'alse true -82.22505844986298 2.7445344871733747e258 -2.7445344871733747e258 82.22505844986298\n1.0e150 tr'
  b'ue false true 69.25125621208066 2.2250738585072014e-308 -69.25125621208066 -69.25125621208066\n-0.0 true '
  b'false true -9.007199254740992e15 1.0e200 9.007199254740992e15 9.007199254740992e15\n6.212387115778398e218'
  b' true false true -5.428034238268016e-246 6.212387115778398e218 5.428034238268016e-246 5.428034238268016e'
  b'-246\n134.4 true false true -0.2 673.0 0.2 0.2\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'v0 = 51.04105122691692\n'
  'IO.puts(inspect(Float.round(v0)) <> " " <> inspect(Float.floor(v0)) <> " " <> inspect(Float.ceil(v0)))\n'
  'v1 = 106.1865234375\n'
  'IO.puts(inspect(Float.ratio(v1)))\n'
  'v2 = -763.201\n'
  'IO.puts(Float.to_string(v2) <> " " <> to_string(v2) <> " #{v2} " <> inspect({v2, [v2]}))\n'
  'v3 = -2.593533348593867e-146\n'
  'IO.puts(inspect(Enum.sum([v3, -67.78990246156951, -44.933998338955284])) <> inspect([v3, '
  '-67.78990246156951] == [-2.593533348593867e-146, -67.78990246156951]))\n'
  'v4 = -75.3947308736675\n'
  'IO.puts(inspect(Float.round(v4, 6)) <> " " <> inspect(Float.floor(v4, 12)) <> " " <> '
  'inspect(Float.ceil(v4, 12)))\n'
  'v5 = 9166033021984.39\n'
  'IO.puts(inspect(Enum.sum([v5, 27.483422508432525, 6.237141273234283e-192])) <> inspect([v5, '
  '27.483422508432525] == [9166033021984.39, 27.483422508432525]))\n'
  'v6 = -61.23225797589007\n'
  'IO.puts(inspect(abs(v6)) <> inspect(-v6) <> inspect(min(v6, -56.3624195981937)) <> inspect(max(v6, '
  '-56.3624195981937)))\n'
  'v7 = -51424.375\n'
  'IO.puts(inspect(Float.ratio(v7)))\n'
  'v8 = 1.0e+16\n'
  'IO.puts(inspect(Float.round(v8, 2)) <> " " <> inspect(Float.floor(v8, 13)) <> " " <> '
  'inspect(Float.ceil(v8, 15)))\n'
  'v9 = -8.966619805209916\n'
  'IO.puts(inspect(round(v9)) <> " " <> inspect(trunc(v9)) <> " " <> inspect(ceil(v9)) <> " " <> '
  'inspect(floor(v9)))\n'
  'v10 = -1397.3665\n'
  'IO.puts(inspect(Enum.sum([v10, -4.624100165275483e+142, -2.1885587774980166])) <> inspect([v10, '
  '-4.624100165275483e+142] == [-1397.3665, -4.624100165275483e+142]))\n'
  'v11 = 2.11\n'
  'IO.puts(inspect(Enum.sum([v11, -96.178800127878, 887.864619])) <> inspect([v11, -96.178800127878] == '
  '[2.11, -96.178800127878]))\n'
  'v12 = 5.638875384763292e+145\n'
  'IO.puts(inspect(Float.round(v12, 1)) <> " " <> inspect(Float.floor(v12, 15)) <> " " <> '
  'inspect(Float.ceil(v12, 8)))\n'
  'v13 = 1.866258812489948e-71\n'
  'IO.puts(inspect(Float.round(v13)) <> " " <> inspect(Float.floor(v13)) <> " " <> '
  'inspect(Float.ceil(v13)))\n'
  'v14 = 4.314498508170388\n'
  'IO.puts(inspect(Enum.sum([v14, -1559896.5, 4503599627370496.0])) <> inspect([v14, -1559896.5] == '
  '[4.314498508170388, -1559896.5]))\n'
  'v15 = 3.7\n'
  'IO.puts(inspect(Float.pow(v15, 0.5)) <> " " <> inspect(v15 ** -2.0862516968388634))\n'
  'v16 = 19.167615087718787\n'
  'IO.puts(inspect(Float.round(v16, 15)) <> " " <> inspect(Float.floor(v16, 12)) <> " " <> '
  'inspect(Float.ceil(v16, 7)))\n'
  'v17 = 54.68811528368599\n'
  'IO.puts(Float.to_string(v17) <> " " <> to_string(v17) <> " #{v17} " <> inspect({v17, [v17]}))\n'
  'v18 = 9.2e+18\n'
  'IO.puts(inspect(Enum.sum([v18, 964325.4289675562, 2.5])) <> inspect([v18, 964325.4289675562] == [9.2e+18, '
  '964325.4289675562]))\n'
  'v19 = -9.223372036854776e+18\n'
  'IO.puts(inspect(Enum.sum([v19, -5.586535043800638, 0.285])) <> inspect([v19, -5.586535043800638] == '
  '[-9.223372036854776e+18, -5.586535043800638]))\n'
  'v20 = -486.4377\n'
  'IO.puts(inspect(Float.round(v20, 14)) <> " " <> inspect(Float.floor(v20, 7)) <> " " <> '
  'inspect(Float.ceil(v20, 2)))\n'
  'v21 = -423199.75\n'
  'IO.puts(inspect(round(v21)) <> " " <> inspect(trunc(v21)) <> " " <> inspect(ceil(v21)) <> " " <> '
  'inspect(floor(v21)))\n'
  'v22 = -1163767191653367.2\n'
  'IO.puts(inspect(Float.parse("-7.92e+01")))\n'
  'v23 = -7698.1985\n'
  'IO.puts(inspect(Float.from_integer(-6071519499685386878)) <> " " <> inspect(Float.from_integer(-1000) * '
  'v23))\n'
  'v24 = 52.07611083984375\n'
  'IO.puts(inspect(Float.ratio(v24)))\n'
  'v25 = -9.41625657\n'
  'IO.puts(inspect(abs(v25)) <> inspect(-v25) <> inspect(min(v25, -1.5)) <> inspect(max(v25, -1.5)))\n'
  'v26 = 9.223372036854776e+18\n'
  'IO.puts(inspect(Enum.sum([v26, 1.617607475185693, 59.28185021201014])) <> inspect([v26, '
  '1.617607475185693] == [9.223372036854776e+18, 1.617607475185693]))\n'
  'v27 = -16453406718162.809\n'
  'IO.puts(inspect(Float.round(v27, 10)) <> " " <> inspect(Float.floor(v27, 0)) <> " " <> '
  'inspect(Float.ceil(v27, 8)))\n'
  'v28 = 0.001\n'
  'IO.puts(inspect(round(v28)) <> " " <> inspect(trunc(v28)) <> " " <> inspect(ceil(v28)) <> " " <> '
  'inspect(floor(v28)))\n'
  'v29 = 79.7721332950369\n'
  'IO.puts(inspect(Float.from_integer(9206623962507027575)) <> " " <> inspect(Float.from_integer(-304) * '
  'v29))\n'
  'v30 = 1.067623689714213e+213\n'
  'IO.puts(inspect(Enum.sum([v30, 1.0e+16, -14579.633709532176])) <> inspect([v30, 1.0e+16] == '
  '[1.067623689714213e+213, 1.0e+16]))\n'
  'v31 = -3.6651225954982683e+276\n'
  'IO.puts(inspect(Float.pow(v31, 0.5)) <> " " <> inspect(v31 ** 3.4985547408155053))\n'
  'v32 = 8732082.5\n'
  'IO.puts(inspect(abs(v32)) <> inspect(-v32) <> inspect(min(v32, 9.223372036854776e+18)) <> '
  'inspect(max(v32, 9.223372036854776e+18)))\n'
  'v33 = 54.91782128016621\n'
  'IO.puts(inspect(Enum.sum([v33, -3.1896567998024495e+184, 250.13])) <> inspect([v33, '
  '-3.1896567998024495e+184] == [54.91782128016621, -3.1896567998024495e+184]))\n'
  'v34 = -59.4932267299743\n'
  'IO.puts(inspect(Float.parse("-0x1.2f3e7427f0091p+8")))\n'
  'v35 = 422733.5\n'
  'IO.puts(inspect(Float.from_integer(5900223107656138771)) <> " " <> inspect(Float.from_integer(-27) * '
  'v35))\n'
  '  end\n'
  'end\n',
  0,
  b'51.0 51.0 52.0\n{108735, 1024}\n-763.201 -763.201 -763.201 {-763.201, [-763.201]}\n-112.7239008005248tr'
  b'ue\n-75.394731 -75.394730873668 -75.394730873667\n9166033022011.875true\n61.2322579758900761.2322579758'
  b'9007-61.23225797589007-56.3624195981937\n{-411395, 8}\n1.0e16 1.0e16 1.0e16\n-9 -8 -8 -9\n-4.62410016527'
  b'5483e142true\n793.7958188721219true\n5.638875384763292e145 5.638875384763292e145 5.638875384763292e145'
  b'\n0.0 0.0 1.0\n4503599625810604.0true\n1.9235384061671346 0.0652511528311438\n19.167615087718787 19.1676'
  b'15087718 19.1676151\n54.68811528368599 54.68811528368599 54.68811528368599 {54.68811528368599, [54.688115'
  b'28368599]}\n9.200000000000965e18true\n-9.223372036854776e18true\n-486.4377 -486.4377001 -486.43\n-423200'
  b' -423199 -423199 -423200\nok(-79.2)\n-6.071519499685387e18 7698198.5\n{853215, 16384}\n9.416256579.41625'
  b'657-9.41625657-1.5\n9.223372036854776e18true\n-16453406718162.809 -16453406718163.0 -16453406718162.80'
  b'9\n0 0 1 0\n9.206623962507027e18 -24250.728521691217\n1.067623689714213e213true\nNaN.0 NaN.0\n8732082.5-8'
  b'732082.58732082.59.223372036854776e18\n-3.1896567998024495e184true\nok(-303.2439599)\n5.900223107656139'
  b'e18 -11413804.5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'v0 = 9.5244140625\n'
  'IO.puts(inspect(Float.ratio(v0)))\n'
  'v1 = -1.1862721733669756e-13\n'
  'IO.puts(inspect(Enum.sum([v1, -0.0, 1.5])) <> inspect([v1, -0.0] == [-1.1862721733669756e-13, -0.0]))\n'
  'v2 = -2.3457845\n'
  'IO.puts(inspect(round(v2)) <> " " <> inspect(trunc(v2)) <> " " <> inspect(ceil(v2)) <> " " <> '
  'inspect(floor(v2)))\n'
  'v3 = 175442.95\n'
  'IO.puts(inspect(abs(v3)) <> inspect(-v3) <> inspect(min(v3, -7.71109041602458e+139)) <> inspect(max(v3, '
  '-7.71109041602458e+139)))\n'
  'v4 = -32.936638864759104\n'
  'IO.puts(inspect(Float.from_integer(-8942761494852774549)) <> " " <> inspect(Float.from_integer(-375) * '
  'v4))\n'
  'v5 = -1.0e+300\n'
  'IO.puts(inspect(Enum.sum([v5, -3305854.5, 47.76983443834294])) <> inspect([v5, -3305854.5] == [-1.0e+300, '
  '-3305854.5]))\n'
  'v6 = 4503599627370.496\n'
  'IO.puts(Float.to_string(v6) <> " " <> to_string(v6) <> " #{v6} " <> inspect({v6, [v6]}))\n'
  'v7 = 117681077035450.28\n'
  'IO.puts(inspect(abs(v7)) <> inspect(-v7) <> inspect(min(v7, 1.0e-10)) <> inspect(max(v7, 1.0e-10)))\n'
  'v8 = 0.8070691503676264\n'
  'IO.puts(inspect(Float.pow(v8, -0.5)) <> " " <> inspect(v8 ** 3.3039514809046953))\n'
  'v9 = 952249.95\n'
  'IO.puts(inspect(Float.round(v9)) <> " " <> inspect(Float.floor(v9)) <> " " <> inspect(Float.ceil(v9)))\n'
  'v10 = -5.826881055581893\n'
  'IO.puts(inspect(round(v10)) <> " " <> inspect(trunc(v10)) <> " " <> inspect(ceil(v10)) <> " " <> '
  'inspect(floor(v10)))\n'
  'v11 = 10.0\n'
  'IO.puts(inspect(Float.parse("0x1.1bf043f133641p+17")))\n'
  'v12 = -97.02585674652721\n'
  'IO.puts(inspect(Float.from_integer(-1363499553738771775)) <> " " <> inspect(Float.from_integer(-635) * '
  'v12))\n'
  'v13 = 6.327796710769494e+285\n'
  'IO.puts(inspect(Float.round(v13)) <> " " <> inspect(Float.floor(v13)) <> " " <> '
  'inspect(Float.ceil(v13)))\n'
  'v14 = 709.78\n'
  'IO.puts(Float.to_string(v14) <> " " <> to_string(v14) <> " #{v14} " <> inspect({v14, [v14]}))\n'
  'v15 = -2928.34765625\n'
  'IO.puts(inspect(Float.ratio(v15)))\n'
  'v16 = 7.400046190111384\n'
  'IO.puts(inspect(Float.pow(v16, -14.0)) <> " " <> inspect(v16 ** -4.897697329761912))\n'
  'v17 = -5601.5234375\n'
  'IO.puts(inspect(Float.ratio(v17)))\n'
  'v18 = -3935476.5\n'
  'IO.puts(inspect(Float.round(v18, 8)) <> " " <> inspect(Float.floor(v18, 15)) <> " " <> '
  'inspect(Float.ceil(v18, 14)))\n'
  'v19 = 10.5\n'
  'IO.puts(inspect(Float.pow(v19, 11.0)) <> " " <> inspect(v19 ** 0.04495118433796552))\n'
  'v20 = -18.827924089847443\n'
  'IO.puts(inspect(Float.round(v20)) <> " " <> inspect(Float.floor(v20)) <> " " <> '
  'inspect(Float.ceil(v20)))\n'
  'v21 = 1.782313756828226e+90\n'
  'IO.puts(Float.to_string(v21) <> " " <> to_string(v21) <> " #{v21} " <> inspect({v21, [v21]}))\n'
  'v22 = 32531523752.346615\n'
  'IO.puts(inspect(Float.round(v22, 12)) <> " " <> inspect(Float.floor(v22, 12)) <> " " <> '
  'inspect(Float.ceil(v22, 0)))\n'
  'v23 = 70.3604261635843\n'
  'IO.puts(Float.to_string(v23) <> " " <> to_string(v23) <> " #{v23} " <> inspect({v23, [v23]}))\n'
  'v24 = -58.56314336257864\n'
  'IO.puts(inspect(Float.from_integer(-3127890616616309204)) <> " " <> inspect(Float.from_integer(-217) * '
  'v24))\n'
  'v25 = 49.62344954207322\n'
  'IO.puts(inspect(Enum.sum([v25, 2.6636766499605304e-80, 2.19])) <> inspect([v25, 2.6636766499605304e-80] '
  '== [49.62344954207322, 2.6636766499605304e-80]))\n'
  'v26 = 45.147727322807015\n'
  'IO.puts(inspect(Float.round(v26)) <> " " <> inspect(Float.floor(v26)) <> " " <> '
  'inspect(Float.ceil(v26)))\n'
  'v27 = -0.0\n'
  'IO.puts(inspect(Float.round(v27, 5)) <> " " <> inspect(Float.floor(v27, 6)) <> " " <> '
  'inspect(Float.ceil(v27, 5)))\n'
  'v28 = 2.19\n'
  'IO.puts(Float.to_string(v28) <> " " <> to_string(v28) <> " #{v28} " <> inspect({v28, [v28]}))\n'
  'v29 = -3.238054154270637e+267\n'
  'IO.puts(inspect(Float.parse("0.0")))\n'
  'v30 = -70.28623837188462\n'
  'IO.puts(inspect(Float.pow(v30, -0.5)) <> " " <> inspect(v30 ** 1.182911799456785))\n'
  'v31 = 80.33122100317681\n'
  'IO.puts(inspect(Float.from_integer(-1307763233003904248)) <> " " <> inspect(Float.from_integer(271) * '
  'v31))\n'
  'v32 = 0.6666666666666666\n'
  'IO.puts(inspect(Enum.sum([v32, 1.15, -2.430760468168254e-254])) <> inspect([v32, 1.15] == '
  '[0.6666666666666666, 1.15]))\n'
  'v33 = 8.797320610744606\n'
  'IO.puts(inspect(Float.pow(v33, -0.5)) <> " " <> inspect(v33 ** -0.8506649588306603))\n'
  'v34 = 56.82626459009029\n'
  'IO.puts(inspect(Float.pow(v34, -45.424947163945404)) <> " " <> inspect(v34 ** 1.7363164119022354))\n'
  'v35 = 51.7699\n'
  'IO.puts(inspect(round(v35)) <> " " <> inspect(trunc(v35)) <> " " <> inspect(ceil(v35)) <> " " <> '
  'inspect(floor(v35)))\n'
  '  end\n'
  'end\n',
  0,
  b'{9753, 1024}\n1.4999999999998814true\n-2 -2 -2 -3\n175442.95-175442.95-7.71109041602458e139175442.95\n-8'
  b'.942761494852775e18 12351.239574284664\n-1.0e300true\n4503599627370.496 4503599627370.496 450359962737'
  b'0.496 {4503599627370.496, [4503599627370.496]}\n117681077035450.28-117681077035450.281.0e-101176810770354'
  b'50.28\n1.113126767683834 0.492535598246323\n952250.0 952249.0 952250.0\n-6 -5 -5 -6\nok(145376.530798362'
  b'6)\n-1.3634995537387717e18 61611.41903404478\n6.327796710769494e285 6.327796710769494e285 6.3277967107'
  b'69494e285\n709.78 709.78 709.78 {709.78, [709.78]}\n{-749657, 256}\n6.772015950012075e-13 5.53035296881'
  b'9805e-5\n{-716995, 128}\n-3935476.5 -3935476.5 -3935476.5\n171033935811.63135 1.1114851595849022\n-19.0 '
  b'-19.0 -18.0\n1.782313756828226e90 1.782313756828226e90 1.782313756828226e90 {1.782313756828226e90, [1.782'
  b'313756828226e90]}\n32531523752.346615 32531523752.346615 32531523753.0\n70.3604261635843 70.3604261635'
  b'843 70.3604261635843 {70.3604261635843, [70.3604261635843]}\n-3.127890616616309e18 12708.202109679565'
  b'\n51.813449542073215true\n45.0 45.0 46.0\n-0.0 -0.0 -0.0\n2.19 2.19 2.19 {2.19, [2.19]}\nok(0.0)\nNaN.'
  b'0 NaN.0\n-1.3077632330039043e18 21769.760891860915\n1.8166666666666664true\n0.33715126238180115 0.15728'
  b'02493687091\n1.993881855541633e-80 1112.8904449601823\n52 51 52 51\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'v0 = 7.8084664952873065e+115\n'
  'IO.puts(inspect(Enum.sum([v0, 1.005, 1.0e-10])) <> inspect([v0, 1.005] == [7.8084664952873065e+115, '
  '1.005]))\n'
  'v1 = -506.21947603\n'
  'IO.puts(inspect(Float.from_integer(4820220618515982249)) <> " " <> inspect(Float.from_integer(239) * '
  'v1))\n'
  'v2 = -1.2598665785191614e-218\n'
  'IO.puts(inspect(abs(v2)) <> inspect(-v2) <> inspect(min(v2, 1000000000000000.0)) <> inspect(max(v2, '
  '1000000000000000.0)))\n'
  'v3 = 5.947052114398128\n'
  'IO.puts(inspect(Float.pow(v3, 0.5)) <> " " <> inspect(v3 ** 1.279028137534457))\n'
  'v4 = -17943255.82716822\n'
  'IO.puts(inspect(Float.from_integer(-1003701530416986714)) <> " " <> inspect(Float.from_integer(-201) * '
  'v4))\n'
  'v5 = 1.185698432825734e-162\n'
  'IO.puts(inspect(Float.round(v5)) <> " " <> inspect(Float.floor(v5)) <> " " <> inspect(Float.ceil(v5)))\n'
  'v6 = 785.5735\n'
  'IO.puts(inspect(Float.pow(v6, 0.32640263252983015)) <> " " <> inspect(v6 ** -2.0618581811469827))\n'
  'v7 = 64.07927263458461\n'
  'IO.puts(inspect(Float.parse("0x1.8000000000000p+1")))\n'
  'v8 = 9.2e+18\n'
  'IO.puts(inspect(Enum.sum([v8, 825773.4406633558, 2.11])) <> inspect([v8, 825773.4406633558] == [9.2e+18, '
  '825773.4406633558]))\n'
  'v9 = 3.642990995638712\n'
  'IO.puts(inspect(Enum.sum([v9, -1.0e+300, 205.657])) <> inspect([v9, -1.0e+300] == [3.642990995638712, '
  '-1.0e+300]))\n'
  'v10 = 4.4240913887312585e+201\n'
  'IO.puts(inspect(Float.from_integer(-3312446920293604128)) <> " " <> inspect(Float.from_integer(-523) * '
  'v10))\n'
  'v11 = 163.76570945176493\n'
  'IO.puts(Float.to_string(v11) <> " " <> to_string(v11) <> " #{v11} " <> inspect({v11, [v11]}))\n'
  'v12 = -57.63472\n'
  'IO.puts(inspect(Enum.sum([v12, 3.7, 59.78729485685872])) <> inspect([v12, 3.7] == [-57.63472, 3.7]))\n'
  'v13 = 5.0e-324\n'
  'IO.puts(inspect(round(v13)) <> " " <> inspect(trunc(v13)) <> " " <> inspect(ceil(v13)) <> " " <> '
  'inspect(floor(v13)))\n'
  'v14 = -44.99123515646293\n'
  'IO.puts(inspect(Float.from_integer(8660191306810367868)) <> " " <> inspect(Float.from_integer(35) * '
  'v14))\n'
  'v15 = -0.0\n'
  'IO.puts(inspect(Float.pow(v15, 22.0)) <> " " <> inspect(v15 ** -0.15534269075063634))\n'
  'v16 = 12.5\n'
  'IO.puts(inspect(Float.pow(v16, -0.5)) <> " " <> inspect(v16 ** -0.5181279350335197))\n'
  'v17 = 0.75\n'
  'IO.puts(inspect(abs(v17)) <> inspect(-v17) <> inspect(min(v17, 3.0)) <> inspect(max(v17, 3.0)))\n'
  'v18 = 2.675\n'
  'IO.puts(inspect(Float.parse("951302762224076.4404657748946722714e-81")))\n'
  'v19 = 31.92135985265537\n'
  'IO.puts(inspect(Float.parse("-0x1.dd72e00000000p+18")))\n'
  'v20 = 709.78\n'
  'IO.puts(inspect(Enum.sum([v20, -127.05008772653996, 987082277.116562])) <> inspect([v20, '
  '-127.05008772653996] == [709.78, -127.05008772653996]))\n'
  'v21 = -7.852401015424532e-271\n'
  'IO.puts(inspect(Float.round(v21)) <> " " <> inspect(Float.floor(v21)) <> " " <> '
  'inspect(Float.ceil(v21)))\n'
  'v22 = -493837.0\n'
  'IO.puts(inspect(Float.ratio(v22)))\n'
  'v23 = 4503599627370.496\n'
  'IO.puts(Float.to_string(v23) <> " " <> to_string(v23) <> " #{v23} " <> inspect({v23, [v23]}))\n'
  'v24 = -113327652.65241551\n'
  'IO.puts(inspect(round(v24)) <> " " <> inspect(trunc(v24)) <> " " <> inspect(ceil(v24)) <> " " <> '
  'inspect(floor(v24)))\n'
  'v25 = 10.503101508780773\n'
  'IO.puts(inspect(round(v25)) <> " " <> inspect(trunc(v25)) <> " " <> inspect(ceil(v25)) <> " " <> '
  'inspect(floor(v25)))\n'
  'v26 = -1.3137969970703125\n'
  'IO.puts(inspect(Float.ratio(v26)))\n'
  'v27 = 0.25\n'
  'IO.puts(inspect(abs(v27)) <> inspect(-v27) <> inspect(min(v27, 9225.5285)) <> inspect(max(v27, '
  '9225.5285)))\n'
  'v28 = 9.573457854402704\n'
  'IO.puts(inspect(Float.round(v28)) <> " " <> inspect(Float.floor(v28)) <> " " <> '
  'inspect(Float.ceil(v28)))\n'
  'v29 = 0.3333333333333333\n'
  'IO.puts(inspect(Float.round(v29, 1)) <> " " <> inspect(Float.floor(v29, 14)) <> " " <> '
  'inspect(Float.ceil(v29, 3)))\n'
  'v30 = 811717.75\n'
  'IO.puts(Float.to_string(v30) <> " " <> to_string(v30) <> " #{v30} " <> inspect({v30, [v30]}))\n'
  'v31 = 0.001\n'
  'IO.puts(Float.to_string(v31) <> " " <> to_string(v31) <> " #{v31} " <> inspect({v31, [v31]}))\n'
  'v32 = 2.011638465314352e-22\n'
  'IO.puts(inspect(Float.pow(v32, 15.0)) <> " " <> inspect(v32 ** -1.5938959803814043))\n'
  'v33 = 90.43365410375588\n'
  'IO.puts(inspect(Float.pow(v33, -0.5)) <> " " <> inspect(v33 ** -0.12288142355961718))\n'
  'v34 = 65.39589768297091\n'
  'IO.puts(inspect(Float.pow(v34, -0.4879944380112562)) <> " " <> inspect(v34 ** -0.954152269342611))\n'
  'v35 = 5.0e-324\n'
  'IO.puts(inspect(round(v35)) <> " " <> inspect(trunc(v35)) <> " " <> inspect(ceil(v35)) <> " " <> '
  'inspect(floor(v35)))\n'
  '  end\n'
  'end\n',
  0,
  b'7.8084664952873065e115true\n4.820220618515982e18 -120986.45477117\n1.2598665785191614e-2181.2598665785'
  b'191614e-218-1.2598665785191614e-2181000000000000000.0\n2.4386578510316137 9.780334711417376\n-1.003701'
  b'5304169868e18 3606594421.260812\n0.0 0.0 1.0\n8.810419781080471 1.0728409925562558e-6\nok(3.0)\n9.200000'
  b'000000825e18true\n-1.0e300true\n-3.3124469202936044e18 -2.3137997963064481e204\n163.76570945176493 163.'
  b'76570945176493 163.76570945176493 {163.76570945176493, [163.76570945176493]}\n5.852574856858723true\n0'
  b' 0 1 0\n8.660191306810368e18 -1574.6932304762024\n0.0 +Inf\n0.282842712474619 0.27018440626920315\n0.75-'
  b'0.750.753.0\nok(9.513027622240765e-67)\nok(-488907.5)\n987082859.8464743true\n-0.0 -1.0 -0.0\n{-493837, 1'
  b'}\n4503599627370.496 4503599627370.496 4503599627370.496 {4503599627370.496, [4503599627370.496]}\n-11'
  b'3327653 -113327652 -113327652 -113327653\n11 10 11 10\n{-86101, 65536}\n0.25-0.250.259225.5285\n10.0 9.0'
  b' 10.0\n0.3 0.33333333333333 0.334\n811717.75 811717.75 811717.75 {811717.75, [811717.75]}\n0.001 0.001 '
  b'0.001 {0.001, [0.001]}\n0.0 3.818427533936426e34\n0.10515621852558803 0.5749146491805988\n0.13002337994'
  b'84231 0.018522020686325472\n0 0 1 0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'v0 = -10374140201.887852\n'
  'IO.puts(inspect(Float.round(v0)) <> " " <> inspect(Float.floor(v0)) <> " " <> inspect(Float.ceil(v0)))\n'
  'v1 = 0.3333333333333333\n'
  'IO.puts(inspect(abs(v1)) <> inspect(-v1) <> inspect(min(v1, -56.93912551569276)) <> inspect(max(v1, '
  '-56.93912551569276)))\n'
  'v2 = -141299607312330.7\n'
  'IO.puts(inspect(Enum.sum([v2, 63.98107426855256, 3.14159])) <> inspect([v2, 63.98107426855256] == '
  '[-141299607312330.7, 63.98107426855256]))\n'
  'v3 = 709.78\n'
  'IO.puts(inspect(Float.round(v3)) <> " " <> inspect(Float.floor(v3)) <> " " <> inspect(Float.ceil(v3)))\n'
  'v4 = 0.285\n'
  'IO.puts(inspect(Float.round(v4, 0)) <> " " <> inspect(Float.floor(v4, 12)) <> " " <> '
  'inspect(Float.ceil(v4, 5)))\n'
  'v5 = -23522.365\n'
  'IO.puts(Float.to_string(v5) <> " " <> to_string(v5) <> " #{v5} " <> inspect({v5, [v5]}))\n'
  'v6 = 757012.980942197\n'
  'IO.puts(Float.to_string(v6) <> " " <> to_string(v6) <> " #{v6} " <> inspect({v6, [v6]}))\n'
  'v7 = -67.230315\n'
  'IO.puts(inspect(abs(v7)) <> inspect(-v7) <> inspect(min(v7, 78.75655)) <> inspect(max(v7, 78.75655)))\n'
  'v8 = -60.69730753205802\n'
  'IO.puts(inspect(Float.round(v8, 10)) <> " " <> inspect(Float.floor(v8, 12)) <> " " <> '
  'inspect(Float.ceil(v8, 6)))\n'
  'v9 = 85836.625\n'
  'IO.puts(inspect(Float.from_integer(8690500330189591130)) <> " " <> inspect(Float.from_integer(-821) * '
  'v9))\n'
  'v10 = 46797.5\n'
  'IO.puts(inspect(round(v10)) <> " " <> inspect(trunc(v10)) <> " " <> inspect(ceil(v10)) <> " " <> '
  'inspect(floor(v10)))\n'
  'v11 = -9.3e+18\n'
  'IO.puts(inspect(Float.round(v11)) <> " " <> inspect(Float.floor(v11)) <> " " <> '
  'inspect(Float.ceil(v11)))\n'
  'v12 = 3.2023665023935867e+295\n'
  'IO.puts(inspect(abs(v12)) <> inspect(-v12) <> inspect(min(v12, -83.588599)) <> inspect(max(v12, '
  '-83.588599)))\n'
  'v13 = 176.78\n'
  'IO.puts(inspect(Float.from_integer(-1537221871885146021)) <> " " <> inspect(Float.from_integer(387) * '
  'v13))\n'
  'v14 = -9.3e+18\n'
  'IO.puts(inspect(Float.round(v14)) <> " " <> inspect(Float.floor(v14)) <> " " <> '
  'inspect(Float.ceil(v14)))\n'
  'v15 = 3.7744028656878495e+299\n'
  'IO.puts(inspect(abs(v15)) <> inspect(-v15) <> inspect(min(v15, -689.2606112)) <> inspect(max(v15, '
  '-689.2606112)))\n'
  'v16 = 8.216137645606887\n'
  'IO.puts(inspect(Float.pow(v16, -23.0)) <> " " <> inspect(v16 ** 2.2984768300075995))\n'
  'v17 = -3.532893988844388e+40\n'
  'IO.puts(inspect(Float.from_integer(-6828077091136468641)) <> " " <> inspect(Float.from_integer(-375) * '
  'v17))\n'
  'v18 = -53.382916928336435\n'
  'IO.puts(inspect(Enum.sum([v18, -26.354502674499727, -178.0])) <> inspect([v18, -26.354502674499727] == '
  '[-53.382916928336435, -26.354502674499727]))\n'
  'v19 = -679.83\n'
  'IO.puts(inspect(Enum.sum([v19, -906292134890.8972, 2.2826198892614476e-98])) <> inspect([v19, '
  '-906292134890.8972] == [-679.83, -906292134890.8972]))\n'
  'v20 = -1.0477828979492188\n'
  'IO.puts(inspect(Float.ratio(v20)))\n'
  'v21 = 0.3333333333333333\n'
  'IO.puts(Float.to_string(v21) <> " " <> to_string(v21) <> " #{v21} " <> inspect({v21, [v21]}))\n'
  'v22 = -5.3314208984375\n'
  'IO.puts(inspect(Float.ratio(v22)))\n'
  'v23 = -9.223372036854776e+18\n'
  'IO.puts(inspect(Float.parse("0x1.8b770d8783e08p+3")))\n'
  'v24 = 91.79885774768903\n'
  'IO.puts(inspect(Float.round(v24, 8)) <> " " <> inspect(Float.floor(v24, 4)) <> " " <> '
  'inspect(Float.ceil(v24, 10)))\n'
  'v25 = -772.88875\n'
  'IO.puts(inspect(Float.round(v25, 9)) <> " " <> inspect(Float.floor(v25, 12)) <> " " <> '
  'inspect(Float.ceil(v25, 6)))\n'
  'v26 = 2.5\n'
  'IO.puts(inspect(Float.from_integer(-3498117683275755827)) <> " " <> inspect(Float.from_integer(-483) * '
  'v26))\n'
  'v27 = 2.1492602151863088e+182\n'
  'IO.puts(inspect(Float.pow(v27, 0.5)) <> " " <> inspect(v27 ** 2.9961928913529796))\n'
  'v28 = 164224540.39998794\n'
  'IO.puts(inspect(Enum.sum([v28, 55.15780838019134, -1377877365046.2593])) <> inspect([v28, '
  '55.15780838019134] == [164224540.39998794, 55.15780838019134]))\n'
  'v29 = 2.826889752371046\n'
  'IO.puts(inspect(Float.pow(v29, 0.5)) <> " " <> inspect(v29 ** -3.842266957007434))\n'
  'v30 = 9007199254740992.0\n'
  'IO.puts(inspect(Float.from_integer(1213425541197709704)) <> " " <> inspect(Float.from_integer(-56) * '
  'v30))\n'
  'v31 = 677673.0\n'
  'IO.puts(inspect(Float.ratio(v31)))\n'
  'v32 = 4503599627370496.0\n'
  'IO.puts(inspect(Float.parse("2E+p_9")))\n'
  'v33 = -40.95428520614437\n'
  'IO.puts(inspect(Float.parse("-5.621037580134082e-121")))\n'
  'v34 = 3.7364478299581202e+245\n'
  'IO.puts(inspect(Float.round(v34, 0)) <> " " <> inspect(Float.floor(v34, 6)) <> " " <> '
  'inspect(Float.ceil(v34, 9)))\n'
  'v35 = -9.3e+18\n'
  'IO.puts(inspect(Float.parse("E8_6x82")))\n'
  '  end\n'
  'end\n',
  0,
  b'-10374140202.0 -10374140202.0 -10374140201.0\n0.3333333333333333-0.3333333333333333-56.939125515692760.33'
  b'33333333333333\n-141299607312263.56true\n710.0 709.0 710.0\n0.0 0.284999999999 0.285\n-23522.365 -23522.'
  b'365 -23522.365 {-23522.365, [-23522.365]}\n757012.980942197 757012.980942197 757012.980942197 {757012.980'
  b'942197, [757012.980942197]}\n67.23031567.230315-67.23031578.75655\n-60.6973075321 -60.697307532059 -60'
  b'.697307\n8.690500330189592e18 -70471869.125\n46798 46797 46798 46797\n-9.3e18 -9.3e18 -9.3e18\n3.2023665'
  b'023935867e295-3.2023665023935867e295-83.5885993.2023665023935867e295\n-1.537221871885146e18 68413.86\n'
  b'-9.3e18 -9.3e18 -9.3e18\n3.7744028656878495e299-3.7744028656878495e299-689.26061123.7744028656878495e'
  b'299\n9.175774930002201e-22 126.57342452128249\n-6.828077091136469e18 1.3248352458166453e43\n-257.737419'
  b'60283616true\n-906292135570.7272true\n{-137335, 131072}\n0.3333333333333333 0.3333333333333333 0.333333'
  b'3333333333 {0.3333333333333333, [0.3333333333333333]}\n{-43675, 8192}\nok(12.358282818487183)\n91.79885'
  b'775 91.7988 91.7988577477\n-772.88875 -772.88875 -772.888749\n-3.498117683275756e18 -1207.5\n1.46603554'
  b'36299316e91 +Inf\n-1377713140450.7014true\n1.6813357048403648 0.01844806565774384\n1.2134255411977098e1'
  b'8 -5.0440315826549555e17\n{677673, 1}\nerror("\\"2E+p_9\\" is not a float")\nok(-5.621037580134082e-1'
  b'21)\n3.7364478299581202e245 3.7364478299581202e245 3.7364478299581202e245\nerror("\\"E8_6x82\\" is not a'
  b' float")\n',
  b'')]
# programs the pinned compiler rejects
REJECTS=['defmodule M do\n  def main() do\nIO.puts(to_string(1 + 1.5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(to_string(1.5 + 1))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(to_string(1.5 % 0.5))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'IO.puts(inspect(min(1.5, 2.5)))\n'
 'IO.puts(inspect(max(1.5, 2.5)))\n'
 'IO.puts(inspect(min(0.0, -0.0)))\n'
 'IO.puts(inspect(max(0.0, -0.0)))\n'
 'IO.puts(inspect(max(-0.0, 0.0)))\n'
 'IO.puts(inspect([1.5, 2.5] == [1.5, 2.5]))\n'
 'IO.puts(inspect([1.5, 2.5] == [1.5, 2.6]))\n'
 'IO.puts(inspect({1.5, "a"} == {1.5, "a"}))\n'
 'IO.puts(inspect([0.0] == [-0.0]))\n'
 'IO.puts(inspect([1.5, -0.0, 1.0e20, 1.0e-5]))\n'
 'IO.puts(inspect({1.5, %{"a" => 2.5}, some(0.1)}))\n'
 'IO.puts(inspect(Enum.sum([1.5, 2.5, 0.1])))\n'
 'l: list[float] = []\n'
 'IO.puts(inspect(Enum.sum(l)))\n'
 'IO.puts(inspect(1.5 in [1.5, 2.5]))\n'
 'IO.puts(inspect(ok(1.5)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  @big 1.0e308\n  def main() do\n    IO.puts(inspect(@big * 10.0))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5 == 1))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1 == 1.5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5 < 1))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect([1.5, 2]))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect([1, 2.5]))\n  end\nend\n',
 'defmodule M do\n  def main() do\nx: float = 1\n  end\nend\n',
 'defmodule M do\n  def main() do\nx: integer = 1.5\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = if 1.5 do 1 else 2 end\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(round(1)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(trunc(1)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(ceil(1)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(floor(1)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(1, 2)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(1.5, 2.0)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.from_integer(1.5)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.to_string(1)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.parse(1.5)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(rem(1.5, 2.0)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(div(1.5, 2.0)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts("a" <> 1.5)\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.0..2.0))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5 in 1..3))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5 % 2.0))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(not 1.5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5 and true))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(min(1.5, 1)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(max(1, 1.5)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(abs("a")))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.pow(2, 3)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.pow(2.0, 3)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(2.0 ** 3))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(2 ** 3.0))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.ratio(1)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.nope(1.0)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.round()))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(1.0, 2, 3)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.max_finite(1)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(.5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5e))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5E3))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1e5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5.5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.7976931348623159e308))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.0e309))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(-1.0e309))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(String.to_float(1.5)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Enum.sum([1.5, 2])))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(length(1.5)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(hd(1.5)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(x)\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(1.5)\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1_.5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1._5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5_0))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5e1_0))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(b[1.5]))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(assert_in_delta(1.0, 2.0)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nassert_in_delta(1, 2, 3)\n  end\nend\n',
 'defmodule M do\n  def main() do\ny = case x do\n  end\nend\n',
 'defmodule M do\n  def main() do\n  1 -> "a"\n  end\nend\n',
 'defmodule M do\n  def main() do\n  _ -> "b"\n  end\nend\n',
 'defmodule M do\n  def main() do\nend\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(y)\n  end\nend\n',
 'defmodule M do\n  def main() do\n  1.5 -> "a"\n  end\nend\n',
 'defmodule M do\n  def main() do\nSystem.halt(1.5)\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.round(1.5, 1) == 1))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Integer.to_string(1.5)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5 ++ 2.5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(-true))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.5 <> "a"))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(round(1.5, 2)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(Float.floor(1.5, 1.0)))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1.797693134862315808e308))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(tuple_size({1.5, 2})))\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = 1.5\nIO.puts(x)\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'x = 1.5\n'
 'y = case x do\n'
 '  1 -> "a"\n'
 '  _ -> "b"\n'
 'end\n'
 'IO.puts(y)\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'x = 1\n'
 'y = case x do\n'
 '  1.5 -> "a"\n'
 '  _ -> "b"\n'
 'end\n'
 'IO.puts(y)\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nx = 1.5\ny = case x do\n  1.5 -> "a"\nend\nIO.puts(y)\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'x = 1.5\n'
 'y = case x do\n'
 '  1.5 -> "a"\n'
 '  1.5 -> "b"\n'
 '  _ -> "c"\n'
 'end\n'
 'IO.puts(y)\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1__0))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(1_))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'z = 0.0\n'
 'nan = z / 1.0 * 0.0 - (1.0e308 * 10.0 * z)\n'
 'm = %{nan => "a", 1.0 => "b"}\n'
 'm2 = Map.put(m, nan, "c")\n'
 'IO.puts(inspect(nan))\n'
 'IO.puts(inspect(m))\n'
 'IO.puts(inspect(m2))\n'
 'IO.puts(inspect(Map.get(m2, nan)))\n'
 'IO.puts(inspect(map_size(m2)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'IO.puts(inspect(Enum.sort([2.5, 1.5, -0.5, 10.0], fn a, b -> a <= b end)))\n'
 'IO.puts(inspect(Enum.sort([2.5, 1.5, -0.5, 10.0], fn a, b -> a >= b end)))\n'
 'IO.puts(inspect(Enum.reduce([2.5, 1.5, -0.5], fn v, acc -> max(v, acc) end)))\n'
 'IO.puts(inspect(Enum.map([1.5, 2.5], fn v -> round(v) end)))\n'
 'IO.puts(inspect(Enum.zip([1.5, 2.5], [1, 2])))\n'
 'IO.puts(inspect(Enum.with_index([1.5, 2.5])))\n'
 'IO.puts(inspect(Enum.take([1.5, 2.5, 3.5], 2)))\n'
 'IO.puts(inspect(Enum.flat_map([1.5, 2.5], fn v -> [v, v * 2.0] end)))\n'
 'IO.puts(inspect(Enum.all?([1.5, 2.5], fn v -> v > 1.0 end)))\n'
 'IO.puts(inspect(Enum.count([1.5, 2.5], fn v -> v > 2.0 end)))\n'
 'IO.puts(inspect(Enum.map_join([1.5, 2.5], "; ", fn v -> to_string(v) end)))\n'
 'IO.puts(inspect(Enum.chunk_every([1.5, 2.5, 3.5], 2)))\n'
 'IO.puts(inspect(Enum.reject([1.5, 2.5], fn v -> v < 2.0 end)))\n'
 'IO.puts(inspect(Enum.scan([1.5, 2.5, 3.0], 0.0, fn v, acc -> v + acc end)))\n'
 'IO.puts(inspect(Enum.at([1.5, 2.5], 1)))\n'
 'IO.puts(inspect(Enum.at([1.5, 2.5], 5)))\n'
 'IO.puts(inspect(List.last([1.5, 2.5])))\n'
 'IO.puts(inspect(Enum.reverse([1.5, 2.5])))\n'
 'IO.puts(inspect(Enum.concat([1.5], [2.5])))\n'
 'IO.puts(inspect(Enum.empty?([1.5])))\n'
 'IO.puts(inspect(Enum.slice([1.5, 2.5, 3.5], 1, 2)))\n'
 'IO.puts(inspect(Enum.drop([1.5, 2.5, 3.5], 1)))\n'
 'IO.puts(inspect(List.flatten([[1.5], [2.5]])))\n'
 'IO.puts(inspect(Enum.split([1.5, 2.5, 3.5], 1)))\n'
 'IO.puts(inspect(Enum.each([1.5], fn v -> IO.puts(to_string(v)) end)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect(+1.5))\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = 1.5\nIO.puts(inspect(+x))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'f = &Float.round/2\n'
 'IO.puts(inspect(f(2.567, 1)))\n'
 'g = &Float.pow/2\n'
 'IO.puts(inspect(g(2.0, 3.0)))\n'
 'h = &Float.parse/1\n'
 'IO.puts(inspect(h("1.5")))\n'
 'k = &abs/1\n'
 'IO.puts(inspect(k(-1.5)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'x = 2.5\n'
 'y = x\n'
 '  |> Float.round(0)\n'
 '  |> Float.to_string()\n'
 'IO.puts(y)\n'
 'z = 1.5 +\n'
 '  2.5\n'
 'IO.puts(inspect(z))\n'
 'w = 1.5\n'
 '  - 0.5\n'
 'IO.puts(inspect(w))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'x = 1.5\n'
 'IO.puts(inspect(x) <> " " <> inspect(x + 1.0)); IO.puts("z")\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'IO.puts(inspect(1.0e-200))\n'
 'IO.puts(inspect(4.656226079603238e+234 * (1.0e+200) + (3.964165708351725e+107) + '
 '(-1.8275404845916104e+114) * (-133.0)))\n'
 'IO.puts(inspect(((-5.858974449795755e-66) - 136.0) * 8.362371939277046e+279 + (4.5074226490977534e-271)))\n'
 'IO.puts(inspect(1780.7549939769574 + 1.0e+308 - 123.456 - (-934.0)))\n'
 'IO.puts(inspect(1.6755058009426036e-212))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'IO.puts(inspect(0.9999999999999999 * 6.424276491546564e+171))\n'
 'IO.puts(inspect(1.0e-320 + (6.1046150935308e+193 - (-1.5094647040214966)) - (67.14937426846149)))\n'
 'IO.puts(inspect((1000000000000000.0) / 1000000000000000.0 * (0.0) * 85.39675204463742))\n'
 'IO.puts(inspect((0.1 - 1.560356124414466e-152 - (123.456 + (1.7976931348623157e+308))) * '
 '(-26.712495549921186)))\n'
 'IO.puts(inspect(-74.13800306854348 + 0.1 * 1.0e-320 - (-1.7167867338682248e+214)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'IO.puts(inspect(-5.0e-324))\n'
 'IO.puts(inspect(((1.0000000000000002 + 244.0) * (3.0) / (1.0e+150)) - (-17.26164202254583 - (1.0e+200)) * '
 '1.0e+200 * (0.1)))\n'
 'IO.puts(inspect(401.0 - (1.0e-160) * (1000000000000000.0) * (-1.0e+150)))\n'
 'IO.puts(inspect(-5.0e-324))\n'
 'IO.puts(inspect(0.1 * (-943.0) + 0.0 / (-661.0)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 'IO.puts(inspect(-19.052619614842257 + 1.0e+308 + (-7.262679995424406e+154) * (-9.402241032757198e+235)))\n'
 'IO.puts(inspect((269.0 - 56.9660962972421) - 1.0e+16 - 3.0))\n'
 'IO.puts(inspect((1.0000000000000002 + 9007199254740992.0) + (1.330882798040039e-203) / 1000000000000000.0 '
 '- (-2.5 + 492.0 - 2.5218485283035306e+193 / (-47.12288443145265))))\n'
 'IO.puts(inspect(0.0 * 0.3 + (-92.14019785818968 * 9007199254740992.0)))\n'
 'IO.puts(inspect(-992.0))\n'
 '  end\n'
 'end\n']


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-floats-') as d:
        out=Path(d)/'out'
        for source,status,stdout,stderr in RUNS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    print(f'PASS floats: {len(RUNS)} programs run as the pinned compiler runs them (911 lines of output), {len(REJECTS)} rejected; literals and their shortest text in to_string, interpolation and inspect; + - * / ** and comparisons; constants folded as Go folds them; round trunc ceil floor abs min max; Float.parse round floor ceil pow ratio; String.to_float; float keys, patterns, equality and Enum.sum')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
