#!/usr/bin/env python3
"""Ranges: every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect({1..4, 3..1, 0..10//5, 5..1//-2, 1..0//1, 1..1}))\n'
  'IO.puts(inspect({Enum.to_list(1..4), Enum.to_list(3..1), Enum.to_list(0..10//5), Enum.to_list(1..0//1)}))\n'
  '  end\n'
  'end\n',
  0,
  b'{1..4, 3..1, 0..10//5, 5..1//-2, 1..0, 1..1}\n{[1, 2, 3, 4], [3, 2, 1], [0, 5, 10], []}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect({Enum.sum(1..100), 3 in 1..5, 9 in 1..5, Enum.map(1..3, fn x -> x * 2 end), Enum.count(1..10//3), Enum.filter(1..6, &(rem(&1, 2) == 0))}))\n'
  '  end\n'
  'end\n',
  0,
  b'{5050, true, false, [2, 4, 6], 4, [2, 4, 6]}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'z = Enum.count(System.argv())\n'
  'r = 1..10//3\n'
  'IO.puts(inspect({r.first, r.last, r.step}))\n'
  'x = z + 2\n'
  'IO.puts(inspect(x..x * 3))\n'
  'IO.puts(inspect(1..3 == 1..3) <> inspect(1..3 == 1..4))\n'
  '  end\n'
  'end\n',
  0,
  b'{1, 10, 3}\n2..6\ntruefalse\n',
  b''),
 ('defmodule M do\n  def main() do\nz = Enum.count(System.argv())\nIO.puts(inspect(1..5//z))\n  end\nend\n', 0, b'1..5\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'r: Range = 1..3\n'
  'IO.puts(inspect(Enum.reverse(r)))\n'
  'l: list[integer] = Enum.to_list(2..4)\n'
  'IO.puts(inspect(l ++ [9]))\n'
  '  end\n'
  'end\n',
  0,
  b'[3, 2, 1]\n[2, 3, 4, 9]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1..2 + 3))\nIO.puts(inspect(Enum.to_list(1 + 1..2 * 2)))\n  end\nend\n', 0, b'1..5\n[2, 3, 4]\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect({Enum.any?(1..3, &(&1 > 2)), Enum.find(1..10, &(&1 > 4)), Enum.take(1..10, 3), Enum.join(1..3, "-"), Enum.concat([1, 2], 3..4), '
  'Enum.count_until(1..1000, 5)}))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, some(5), [1, 2, 3], "1-2-3", [1, 2, 3, 4], 5}\n',
  b''),
 ('defmodule M do\n  def total(r: Range): integer do Enum.sum(r) + r.first end\n  def main() do\n    IO.puts(inspect(total(1..4)))\n  end\nend\n',
  0,
  b'11\n',
  b'')]
# programs the pinned compiler rejects
REJECTS=[]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-ranges-') as d:
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
    print(f'PASS ranges: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; first..last, steps, fields, inspect, equality, ranges as lists of integers')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
