#!/usr/bin/env python3
"""Statements as the pinned compiler takes them: calls whose value is dropped,
if and case as statements, if without else, main that ends without
System.halt, System.halt anywhere, Enum.each, and what a statement may not be."""
from pathlib import Path
import subprocess
import sys
import tempfile

DECLARATIONS='''  def tell(n: integer): integer do
    IO.puts("tell")
    n
  end
  def show(a: option[string]): integer do
    case a do
      some(x) -> IO.puts(x)
      none -> IO.puts("no")
    end
    0
  end
  def only(n: integer): integer do
    if n > 0 do IO.puts("pos") end
    n
  end
  def check(n: integer): integer do
    if n > 2 do System.halt(7) end
    n
  end
'''
# (main body, standard output, exit status)
ACCEPTED=[
    ('tell(1)\nFile.write("/dev/null", "x")\nIO.puts("after")',b'tell\nafter\n',0),
    ('if 1 == 1 do tell(3) end\nif 1 == 1 do IO.puts("a") else tell(3) end\nif 1 == 2 do tell(1) else Integer.to_string(2) end\nIO.puts("after")',b'tell\na\nafter\n',0),
    ('x = 3\nif x > 2 do\n  IO.puts("big")\n  if x > 5 do IO.puts("huge") end\nend\ncase x do\n  3 -> tell(3)\n  _ -> IO.puts("z")\nend\n'
     'case {x, 1} do\n  {3, y} ->\n    IO.puts("a")\n    IO.puts(Integer.to_string(y))\n  _ -> IO.puts("b")\nend\nIO.puts("after")',b'big\ntell\na\n1\nafter\n',0),
    ('x = 1\ncase x do\n  1 -> ok({})\n  _ -> IO.puts("b")\nend\nif x == 1 do none end\nIO.puts("a")\ntell(4)',b'a\ntell\n',0),
    ('IO.puts(Integer.to_string(show(some("h")) + only(1) + check(1)))\nx = check(3)\nIO.puts("not reached")',b'h\npos\n2\n',7),
    ('Enum.each([1, 2], fn x -> IO.puts(Integer.to_string(x)) end)\n[1, 2] |> Enum.map(fn x -> x + 1 end) |> Enum.each(fn x -> IO.puts(Integer.to_string(x)) end)\n'
     'Enum.each(%{"b" => 2, "a" => 1}, fn {k, v} -> IO.puts(k <> Integer.to_string(v)) end)\nEnum.each([3], &tell/1)\ntotal = 10\n'
     'Enum.each([1, 2], fn x ->\n  y = x * 2 + total\n  if y > 12 do IO.puts(Integer.to_string(y)) end\nend)\n'
     'f: fn[integer, tuple[]] = fn x -> IO.puts("in") end\nf(1)\ng = Enum.map([1, 2], fn x -> IO.puts("m") end)\nIO.puts(Integer.to_string(Enum.count(g)))',
     b'1\n2\n2\n3\na1\nb2\ntell\n14\nin\nm\nm\n2\n',0),
]
REJECTED=[
    ('1 + 2\nIO.puts("after")','an operator expression as a statement'),('if 1 == 1 do 5 else 6 end\nIO.puts("after")','an if statement whose branches are values'),
    ('x = if 1 == 1 do IO.puts("a") else IO.puts("b") end\nIO.puts("after")','a statement if as a value'),('x = if 1 == 2 do tell(1) end\nIO.puts("after")','an if without else as a value'),
    ('ok(1)\nIO.puts("a")','a constructor as a statement'),('x = 2\nIO.puts("a")\nx','main ending in a name'),('IO.puts("a")\n5','main ending in a literal'),
    ('y = if 1 == 1 do tell(1) else "s" end\nIO.puts("x")','branches of different types as a value'),('x = Enum.each([1], fn x -> IO.puts("e") end)\nIO.puts("after")','Enum.each as a value'),
    ('f: fn[integer, integer] = fn x -> IO.puts("in") end\nIO.puts("x")','a function without a value where one returning integer is expected'),
    ('IO.puts(Integer.to_string(tell(if 1 == 1 do IO.puts("q") end)))','a statement if as an argument'),('x = System.halt(1)\nIO.puts("a")','System.halt as a value'),
]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-statements-') as d:
        root=Path(d)
        def compiled(body):
            return subprocess.run([str(compiler)],input=('defmodule M do\n'+DECLARATIONS+'  def main() do\n'+body+'\n  end\nend\n').encode(),capture_output=True,env={'PATH':''},timeout=120)
        for body,stdout,status in ACCEPTED:
            result=compiled(body)
            assert (result.returncode,result.stderr)==(0,b''),(body[:100],result.returncode,result.stderr)
            out=root/'out';out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,b''),(body[:100],run)
        for body,label in REJECTED:
            result=compiled(body)
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
    print(f'PASS statements: {len(ACCEPTED)} programs of dropped calls, if/case statements, main without halt and Enum.each; {len(REJECTED)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
