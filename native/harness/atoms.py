#!/usr/bin/env python3
"""Atoms and keyword lists: every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule M do\n'
  '  def main() do\n'
  'x = :ok\n'
  'IO.puts(to_string(x))\n'
  'IO.puts(inspect(x))\n'
  'IO.puts("#{x} #{:error}")\n'
  'IO.puts(inspect(x == :ok) <> inspect(x != :ok) <> inspect(:a == :b))\n'
  '  end\n'
  'end\n',
  0,
  b'ok\n:ok\nok error\ntruefalsefalse\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect([:a, :b]))\n'
  'IO.puts(inspect({:ok, 1}))\n'
  'IO.puts(inspect(%{:a => 1, :b => 2}))\n'
  'm = %{:b => 2, :a => 1}\n'
  'IO.puts(inspect(Map.get(m, :a)))\n'
  'IO.puts(inspect(:b in [:a, :b]))\n'
  'IO.puts(inspect(some(:x)))\n'
  '  end\n'
  'end\n',
  0,
  b'[:a, :b]\n{:ok, 1}\n%{:a => 1, :b => 2}\nsome(1)\ntrue\nsome(:x)\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'x = :red\n'
  'y = case x do\n'
  '  :green -> 1\n'
  '  :red -> 2\n'
  '  _ -> 3\n'
  'end\n'
  'IO.puts(inspect(y))\n'
  'case {:ok, 5} do\n'
  '  {:ok, n} -> IO.puts(inspect(n))\n'
  '  {:error, _} -> IO.puts("e")\n'
  '  _ -> IO.puts("?")\n'
  'end\n'
  '  end\n'
  'end\n',
  0,
  b'2\n5\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'k = [a: 1, b: 2]\n'
  'IO.puts(inspect(k))\n'
  'IO.puts(inspect([{:a, 1}, {:b, 2}]) <> inspect([a: 1] == [{:a, 1}]))\n'
  'IO.puts(inspect([name: "ada", lang: "alchem"]))\n'
  'IO.puts(inspect(length(k)))\n'
  'e: list[tuple[atom, integer]] = []\n'
  'IO.puts(inspect(e))\n'
  '  end\n'
  'end\n',
  0,
  b'[a: 1, b: 2]\n[a: 1, b: 2]true\n[name: "ada", lang: "alchem"]\n2\n[]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect([:ok?, :stop!, :a_b1]))\n  end\nend\n', 0, b'[:ok?, :stop!, :a_b1]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(:a < :b))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule M do\n'
  '  def name(a: atom): string do\n'
  '    case a do\n'
  '      :x -> "ex"\n'
  '      other -> to_string(other)\n'
  '    end\n'
  '  end\n'
  '  def pick(n: integer): atom do\n'
  '    if n > 0 do :pos else :neg end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(name(:x) <> name(:why) <> inspect(pick(1)) <> inspect(pick(-1)))\n'
  '    IO.puts(inspect(Enum.map([1, -1], &pick/1)))\n'
  '    IO.puts(inspect(Enum.sort([3, 1, 2]) ))\n'
  '  end\n'
  'end\n',
  0,
  b'exwhy:pos:neg\n[:pos, :neg]\n[1, 2, 3]\n',
  b'')]
# programs the pinned compiler rejects
REJECTS=['defmodule M do\n  def main() do\nIO.puts(inspect(:a == "a"))\n  end\nend\n']


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-atoms-') as d:
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
    print(f'PASS atoms: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; atom literals, the atom type, equality, order, map keys, patterns, inspect, keyword lists')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
