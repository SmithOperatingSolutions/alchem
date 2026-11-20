#!/usr/bin/env python3
"""The order of values: every program runs as the pinned compiler runs it.

harness/ordering-cases.json.xz holds the programs with the pinned compiler's
status, standard output and standard error for each, and the programs it
rejects with its diagnostic (scripts/generate-ordering-cases.py makes the
file from the pinned compiler). They sort, take the least and the greatest
and compare, with every ordered library function and option, values of every
type with an order (integers, floats with NaN and infinities, strings,
booleans, atoms, and tuples and lists of them, nested), lists, maps and
ranges, empty and with duplicates, and the types the pinned language gives
no order."""
from pathlib import Path
import json
import lzma
import subprocess
import sys
import tempfile

# The wrong result this gate was written against, and the shapes around it.
RUNS=[('defmodule M do\n'
  '  def main() do\n'
  'IO.inspect(Enum.sort([{1, {2, 3}}, {1, {1, 3}}]))\n'
  'IO.inspect(Enum.sort([[[2], [1]], [[1, 5]], [[1], []]]))\n'
  'IO.inspect(Enum.max([{1, 2, 3, 4, 5, 6, 7}, {1, 2, 3, 4, 5, 6, 8}]))\n'
  'IO.inspect(List.keysort([{[2, 1], :a}, {[2], :b}, {[], :c}]))\n'
  'IO.inspect(max({1.5, "a", [true]}, {1.5, "a", [false, true]}))\n'
  'IO.inspect(Enum.sort_by(["bb", "a", "ccc"], fn s -> {String.length(s) > 1, s} end, :desc))\n'
  '  end\n'
  'end\n',
  0,
  b'[{1, {1, 3}}, {1, {2, 3}}]\n[[[1], []], [[1, 5]], [[2], [1]]]\n{1, 2, 3, 4, 5, 6, 8}\n[{[], :c}, {[2], :b}, {[2, 1], :a}]\n{1.5, "a", [true]}\n["ccc", "bb", "a"]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'e: list[tuple[integer, string]] = []\n'
  'IO.inspect(Enum.sort(e))\n'
  'IO.inspect([1] |> Enum.drop(1)\n'
  '  |> Enum.max())\n'
  '  end\n'
  'end\n',
  2,
  b'[]\n',
  b'<stdin>:6:6: empty error\n  at M.main (<stdin>:5)\n')]
REJECTS=['defmodule M do\n  def main() do\nIO.inspect(Enum.sort([some(1), none]))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.inspect({1, 2} < {1, 3})\n  end\nend\n',
 'defmodule M do\n  def less(x: t, y: t): boolean do\n    x < y\n  end\n  def main() do\nIO.inspect(less(1, 2))\n  end\nend\n']


def cases():
    held=json.loads(lzma.decompress((Path(__file__).resolve().parent/'ordering-cases.json.xz').read_bytes()))
    runs=[(source,status,stdout.encode(),stderr.encode()) for source,status,stdout,stderr in held if status is not None]
    return RUNS+runs,REJECTS+[source for source,status,_,_ in held if status is None]


def verify(compiler):
    runs,rejects=cases()
    with tempfile.TemporaryDirectory(prefix='alchem-ordering-') as d:
        out=Path(d)/'out'
        for source,status,stdout,stderr in runs:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=60)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=60)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run,status,stdout,stderr)
        for source in rejects:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=60)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    print(f'PASS ordering: {len(runs)} programs run as the pinned compiler runs them, {len(rejects)} rejected; sort, max, min, min_max, the _by forms, keysort, List.sort and min/max over every type with an order, NaN, stability, the order of calls, failures named where the program called the library')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
