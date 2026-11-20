#!/usr/bin/env python3
"""unless, the one-line if, module constants, raise and the functions called without a module name that are written in Alchem: every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'unless z == 1 do IO.puts("u") end\n'
  'x = unless z == 0 do 1 else 2 end\n'
  'IO.puts(to_string(x))\n'
  'unless z == 0 do\n'
  '  IO.puts("no")\n'
  'else\n'
  '  IO.puts("yes")\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'u\n2\nyes\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'x = if z == 0, do: 1, else: 2\n'
  'IO.puts(to_string(x))\n'
  'if z == 0, do: IO.puts("k")\n'
  'if z == 1, do: IO.puts("n"), else: IO.puts("e")\n'
  'IO.puts(inspect(Enum.find_value([1, 2, 3], fn n -> if n > 1, do: some(n * 10), else: none end)))\n'
  '  end\n'
  'end\n',
  0,
  b'1\nk\ne\nsome(20)\n',
  b''),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\ny = unless z == 0, do: "a", else: "b"\nIO.puts(y)\n  end\nend\n', 0, b'b\n', b''),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nunlessx = 5\nIO.puts(to_string(unlessx + z))\n  end\nend\n', 0, b'5\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect({concat([1], [2]), filter([1, 2, 3], fn(x: integer): boolean do x > 1 end), map([1, 2], fn(x: integer): integer do x * 2 end), reduce([1, '
  '2, 3], 0, fn(x: integer, acc: integer): integer do x + acc end), get(%{"a" => 1}, "z", 0), has_key(%{"a" => 1}, "a"), put(%{"a" => 1}, "b", 2), prepend([2, '
  '3], 1)}))\n'
  'IO.puts(inspect(5 |> then(fn n -> n * 2 end)))\n'
  'IO.puts(inspect(tap(5, fn n -> IO.write(Integer.to_string(n)) end)))\n'
  '  end\n'
  'end\n',
  0,
  b'{[1, 2], [2, 3], [2, 4], 6, 0, true, %{"a" => 1, "b" => 2}, [1, 2, 3]}\n10\n55\n',
  b''),
 ('defmodule M do\n'
  '  def map(x: integer): integer do x + 1 end\n'
  '  def main() do\n'
  '    IO.puts(inspect({map(1), Kernel.map([1], fn(x: integer): integer do x * 3 end)}))\n'
  '  end\n'
  'end\n',
  0,
  b'{2, [3]}\n',
  b''),
 ('defmodule Example do\n'
  '  @attempts 3\n'
  '  @delay_ms 250\n'
  '  @budget_ms @attempts * @delay_ms\n'
  '  @moduledoc "docs"\n'
  '  @names ["a",\n'
  '    "b"]\n'
  '  @pair {1, "x"}\n'
  '\n'
  '  @doc """\n'
  '  Plans.\n'
  '  """\n'
  '  def plan(): string do\n'
  '    Integer.to_string(@attempts) <> " tries within " <> Integer.to_string(@budget_ms) <> " ms"\n'
  '  end\n'
  '\n'
  '  @greeting "hi " <>\n'
  '    "there"\n'
  '\n'
  '  def main() do\n'
  '    IO.puts(plan())\n'
  '    IO.puts(inspect({@names, @pair, @greeting, @attempts + 1}))\n'
  '    x = @attempts\n'
  '    IO.puts(to_string(x * @delay_ms))\n'
  '  end\n'
  'end\n',
  0,
  b'3 tries within 750 ms\n{["a", "b"], {1, "x"}, "hi there", 4}\n750\n',
  b''),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts("a")\nraise("boom #{z}")\n  end\nend\n',
  2,
  b'a\n',
  b'<stdin>:5:1: boom 0\n  at M.main (<stdin>:5)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = if z == 0 do raise("no") else 5 end\nIO.puts(to_string(x))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:18: no\n  at M.main <closure> (<stdin>:4)\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\ny = case z do\n  1 -> "one"\n  _ -> raise("other")\nend\nIO.puts(y)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:6:8: other\n  at M.main <closure> (<stdin>:6)\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def f(n: integer): integer do\n'
  '    if n > 2 do raise("too big: " <> to_string(n)) else n end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(to_string(f(1)))\n'
  '    IO.puts(to_string(f(3)))\n'
  '  end\n'
  'end\n',
  2,
  b'1\n',
  b'<stdin>:3:17: too big: 3\n  at M.f (<stdin>:3)\n  at M.main (<stdin>:7)\n')]
# programs the pinned compiler rejects
REJECTS=['defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nx = if z == 0, do: 1\nIO.puts(to_string(x))\n  end\nend\n',
 'defmodule M do\n  @a 1\n  def main() do\n    IO.puts(to_string(@b))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(to_string(@a))\n  end\nend\n',
 'defmodule M do\n  @a @a + 1\n  def main() do\n    IO.puts(to_string(@a))\n  end\nend\n',
 'defmodule M do\n  def main() do\nraise(5)\n  end\nend\n']


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-forms-') as d:
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
    print(f'PASS forms: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; unless; if c, do: a, else: b; @name constants; raise; concat filter map reduce get has_key put prepend tap then')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
