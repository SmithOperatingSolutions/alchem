#!/usr/bin/env python3
"""Integer operators, the functions called without a module name, cond, list operators and membership: every program runs as the pinned compiler runs it, failures and their traces included."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(Integer.to_string(7 / z))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:29: division by zero\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(Integer.to_string(7 % z))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:29: division by zero\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'IO.puts(Integer.to_string(-7 % 2))\n'
  'IO.puts(Integer.to_string(-7 / 2))\n'
  'IO.puts(Integer.to_string(7 % -2))\n'
  'IO.puts(Integer.to_string(7 / 2 * 3 % 4))\n'
  '  end\n'
  'end\n',
  0,
  b'-1\n-3\n1\n1\n',
  b''),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(Integer.to_string(9223372036854775807 * (z+2)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:47: integer overflow\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(Integer.to_string(9223372036854775807 + (z+2)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:47: integer overflow\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(Integer.to_string(-9223372036854775807 - (z+2)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:48: integer overflow\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = -9223372036854775807 - 1 + z\nIO.puts(Integer.to_string(-x))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:5:27: integer overflow\n  at M.main (<stdin>:5)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = -9223372036854775807 - 1 + z\nIO.puts(Integer.to_string(x / (z-1)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:5:29: integer overflow\n  at M.main (<stdin>:5)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = -9223372036854775807 - 1 + z\nIO.puts(Integer.to_string(x % (z-1)))\n  end\nend\n',
  0,
  b'0\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'IO.puts(Integer.to_string(2 ** (z+62)))\n'
  'IO.puts(Integer.to_string((-2) ** 3))\n'
  'IO.puts(Integer.to_string(2 ** 3 ** 2))\n'
  'IO.puts(Integer.to_string(-2 ** 2))\n'
  'IO.puts(Integer.to_string((z-2) ** 63))\n'
  'IO.puts(Integer.to_string(3 ** 0 + 0 ** 0 + 1 ** 1000000000000 * 2 ** 2))\n'
  '  end\n'
  'end\n',
  0,
  b'4611686018427387904\n-8\n512\n4\n-9223372036854775808\n6\n',
  b''),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = z + 3\nIO.puts(Integer.to_string(-x ** 2))\n  end\nend\n', 0, b'9\n', b''),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(Integer.to_string(2 ** (z+63)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:29: integer overflow\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(Integer.to_string(3 ** (z+40)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:29: integer overflow\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(Integer.to_string(2 ** (z-1)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:29: integer power needs a nonnegative exponent\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'x = z + 3\n'
  '-1 |> Integer.to_string() |> IO.puts()\n'
  'IO.puts(Integer.to_string(x))\n'
  '  end\n'
  'end\n',
  0,
  b'-1\n3\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'IO.puts(Integer.to_string(1 + 2 * 3 - 4 / 2 ** 2 % 3))\n'
  'IO.puts("a" <> Integer.to_string(1 + 2) <> "b")\n'
  '  end\n'
  'end\n',
  0,
  b'6\na3b\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(Integer.to_string(9223372036854775807 + 1))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:47: integer overflow\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = 5 +\n  z\nIO.puts(Integer.to_string(x))\n  end\nend\n', 0, b'5\n', b''),
 ('defmodule M do\n'
  ' def f(n: integer): integer do n * 4611686018427387904 end\n'
  ' def g(n: integer): integer do 1 + f(n) end\n'
  ' def main() do\n'
  '  IO.puts(Integer.to_string(g(1)))\n'
  '  IO.puts(Integer.to_string(g(2)))\n'
  ' end\n'
  'end\n',
  2,
  b'4611686018427387905\n',
  b'<stdin>:2:34: integer overflow\n  at M.f (<stdin>:2)\n  at M.g (<stdin>:3)\n  at M.main (<stdin>:6)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = cond do\n  z == 1 -> "a"\n  z == 2 -> "b"\nend\nIO.puts(x)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:5: no cond clause matched\n  at M.main <closure> (<stdin>:4)\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'cond do\n'
  '  z == 1 -> IO.puts("a")\n'
  '  z == 2 -> IO.puts("b")\n'
  'end\n'
  'IO.puts("after")\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:4:1: no cond clause matched\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'cond do\n'
  '  z == 1 -> IO.puts("a")\n'
  '  true ->\n'
  '    y = 5\n'
  '    IO.puts(to_string(y))\n'
  '    IO.puts("c")\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'5\nc\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'x = cond do\n'
  '  z > 0 and\n'
  '    z < 5 -> "a"\n'
  '  z + 1 == 1 ->\n'
  '    w = "b"\n'
  '    w <> "!"\n'
  '  true -> "c"\n'
  'end\n'
  'IO.puts(x <> cond do\n'
  ' true -> "t"\n'
  'end)\n'
  '  end\n'
  'end\n',
  0,
  b'b!t\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'x = cond do\n'
  '  z == 1 -> "a"\n'
  '  z == 0 ->\n'
  '    cond do\n'
  '      z > 5 -> "deep"\n'
  '      true -> case z do\n'
  '        0 -> "zero"\n'
  '        _ -> "other"\n'
  '      end\n'
  '    end\n'
  '  true -> "c"\n'
  'end\n'
  'IO.puts(x)\n'
  '  end\n'
  'end\n',
  0,
  b'zero\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(to_string(max(3, 9)) <> max("a", "b") <> to_string(min(2, 1)) <> min("b", "ab") <> max("abc", "ab"))\n'
  'IO.puts(to_string(max(true, false)))\n'
  '  end\n'
  'end\n',
  0,
  b'9b1ababc\ntrue\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(to_string(length([1,2,3])) <> to_string(length({1,"a"})) <> to_string(length(%{"a" => 1})) <> to_string(map_size(%{1 => 2})))\n'
  '  end\n'
  'end\n',
  0,
  b'3211\n',
  b''),
 ('defmodule M do\n  def main() do\nx = [1,2,3]\nIO.puts(to_string(hd(x)) <> to_string(length(tl(x))) <> to_string(hd(tl(tl(x)))) <> hd(["s"]))\n  end\nend\n',
  0,
  b'123s\n',
  b''),
 ('defmodule M do\n  def main() do\nx: list[integer] = []\nIO.puts(to_string(hd(x)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:19: the list is empty\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nx: list[integer] = []\nIO.puts(to_string(length(tl(x))))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:26: the list is empty\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nIO.puts(to_string(5) <> to_string("s") <> to_string(false) <> to_string(-9223372036854775808))\n  end\nend\n',
  0,
  b'5sfalse-9223372036854775808\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(to_string(Kernel.rem(7, 2)) <> to_string(Kernel.length({1, 2})) <> to_string(div(-7, 2)) <> to_string(abs(-3)) <> to_string(rem(-7, 2)))\n'
  '  end\n'
  'end\n',
  0,
  b'12-33-1\n',
  b''),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(to_string(rem(7, z)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:19: division by zero\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(to_string(div(7, z)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:19: division by zero\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = -9223372036854775807 - 1 + z\nIO.puts(to_string(abs(x)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:5:19: integer overflow\n  at M.main (<stdin>:5)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nassert(z == 0)\nassert(true and not false)\nIO.puts("ok")\n  end\nend\n', 0, b'ok\n', b''),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nassert(z == 1)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:1: assertion failed\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\n[1,2] |> length() |> to_string() |> IO.puts()\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule M do\n'
  ' def length(x: integer): integer do x + 100 end\n'
  ' def main() do\n'
  '  IO.puts(to_string(length(1)) <> to_string(Kernel.length([1])))\n'
  ' end\n'
  'end\n',
  0,
  b'1011\n',
  b''),
 ('defmodule M do\n'
  ' def sign(n: integer): string do\n'
  '  cond do\n'
  '   n < 0 -> "neg"\n'
  '   n == 0 -> "zero"\n'
  '   true -> "pos"\n'
  '  end\n'
  ' end\n'
  ' def main() do\n'
  '  IO.puts(sign(-1) <> sign(0) <> sign(1))\n'
  ' end\n'
  'end\n',
  0,
  b'negzeropos\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(Enum.join(Enum.map([1, 2] ++ [3] ++ [] ++ [4, 5], &Integer.to_string/1), ","))\n  end\nend\n',
  0,
  b'1,2,3,4,5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(Enum.join(Enum.map([1, 2, 3, 2] -- [2], &Integer.to_string/1), ","))\n'
  'IO.puts(Enum.join(Enum.map([1, 2, 3, 2, 1] -- [2, 1, 2, 9], &Integer.to_string/1), ","))\n'
  'IO.puts(Enum.join(Enum.map([1] -- [], &Integer.to_string/1), ","))\n'
  '  end\n'
  'end\n',
  0,
  b'1,3,2\n3,1\n1\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(Enum.join(["a", "b", "a"] -- ["a"], ","))\n  end\nend\n', 0, b'b,a\n', b''),
 ('defmodule M do\n  def main() do\nx = [{1, "a"}, {2, "b"}] -- [{1, "a"}]\nIO.puts(to_string(length(x)))\n  end\nend\n', 0, b'1\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(Enum.join(Enum.map([1] ++ [2, 3] -- [2] ++ [9], &Integer.to_string/1), ","))\n  end\nend\n', 0, b'1,3,9\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'if 2 in [1, 2, 3] and not (5 in [1, 2]) do IO.puts("y") end\n'
  'IO.puts(to_string(z in [0]) <> to_string("b" in ["a"]) <> to_string({1, "a"} in [{1, "a"}]) <> to_string(z + 1 in [z + 1]))\n'
  '  end\n'
  'end\n',
  0,
  b'y\ntruefalsetruetrue\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(to_string(length([1] ++ [2]) == 2) <> to_string(1 + 1 in [2]))\n  end\nend\n', 0, b'truetrue\n', b''),
 ('defmodule M do\n'
  ' def has(xs: list[t], x: t): boolean do x in xs end\n'
  ' def less(xs: list[t], ys: list[t]): list[t] do xs -- ys end\n'
  ' def main() do\n'
  '  IO.puts(to_string(has(["a"], "a")) <> to_string(has([1], 2)) <> to_string(length(less([{1, 2}, {3, 4}], [{3, 4}]))))\n'
  ' end\n'
  'end\n',
  0,
  b'truefalse1\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(to_string(Enum.sum([9223372036854775807, 1])))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:19: integer overflow\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(to_string(Enum.sum([9223372036854775807, -1, 1, -5])))\n'
  'x: list[integer] = []\n'
  'IO.puts(to_string(Enum.sum(x) + Enum.sum([-9223372036854775807, -1])))\n'
  '  end\n'
  'end\n',
  0,
  b'9223372036854775802\n-9223372036854775808\n',
  b''),
 ('defmodule M do\n  def main() do\n[9223372036854775807, 1] |> Enum.sum() |> to_string() |> IO.puts()\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:29: integer overflow\n  at M.main (<stdin>:3)\n'),
 ('defmodule M do\n  def main() do\nIO.puts(to_string(Enum.reduce([9223372036854775807, 1], 0, fn x, a -> x + a end)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:73: integer overflow\n  at M.main <closure> (<stdin>:3)\n  at M.main (<stdin>:3)\n')]
# programs the pinned compiler rejects
REJECTS=['defmodule M do\n  def main() do\nz = Enum.count(System.argv())\ncond do\n  z -> IO.puts("a")\nend\n  end\nend\n',
 'defmodule M do\n  def main() do\nz = Enum.count(System.argv())\ncond do\nend\n  end\nend\n',
 'defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = cond do\n  z == 1 -> "a"\n  true -> 1\nend\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'f = fn n: integer -> cond do\n'
 '  n < 0 -> "neg"\n'
 '  n == 0 -> "zero"\n'
 '  true -> "pos"\n'
 'end end\n'
 'IO.puts(f(0-1) <> f(0) <> f(1))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nIO.puts(to_string(length("abc")))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(to_string([1]))\n  end\nend\n',
 'defmodule M do\n  def main() do\nassert(1)\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = assert(true)\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 'x: list[integer] = [] ++ []\n'
 'IO.puts(Enum.join(Enum.map(x, &Integer.to_string/1), ","))\n'
 'IO.puts(Enum.join(Enum.map([] ++ [1], &Integer.to_string/1), ","))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\nIO.puts(to_string(1 in []))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(to_string(1 in ["a"]))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(Enum.join(Enum.map([1] ++ ["a"], &Integer.to_string/1), ","))\n  end\nend\n']


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-operators-') as d:
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
    print(f'PASS operators: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; / % ** with overflow, division by zero and negative exponents; rem div abs min max length hd tl to_string map_size assert; cond; ++ -- in; && || !; Enum.sum overflow')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
