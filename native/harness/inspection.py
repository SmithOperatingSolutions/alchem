#!/usr/bin/env python3
"""inspect and IO.inspect of every kind of value, the escapes of a string, and pipelines as statements: every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule M do\n'
  '  struct P do\n'
  '    x: integer\n'
  '    name: string\n'
  '  end\n'
  '  type Shape do\n'
  '    circle(r: integer)\n'
  '    rect(w: integer, h: integer)\n'
  '    dot\n'
  '  end\n'
  '  type Tree[t] do\n'
  '    leaf\n'
  '    node(l: Tree[t], v: t, r: Tree[t])\n'
  '  end\n'
  '  struct Box[a] do\n'
  '    v: a\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(%P{x: 1, name: "a\\n\\"é\\u0001"}))\n'
  '    IO.puts(inspect([Shape.circle(1), Shape.rect(2, 3), Shape.dot]))\n'
  '    t: Tree[integer] = Tree.node(Tree.leaf, 5, Tree.node(Tree.leaf, 6, Tree.leaf))\n'
  '    IO.puts(inspect(t))\n'
  '    IO.puts(inspect(%Box{v: some("s")}))\n'
  '    IO.puts(inspect({1, "a", true, [1, 2], %{"k" => [some(-5), none], "a" => []}}))\n'
  '    r: result[integer, string] = ok(1)\n'
  '    e: result[integer, string] = error("bad")\n'
  '    IO.puts(inspect([r, e]))\n'
  '    f = fn(x: integer): integer do x end\n'
  '    IO.puts(inspect(f))\n'
  '    IO.puts(inspect({}))\n'
  '    IO.puts(inspect(%{1 => {2, 3}, -1 => {0, 0}}) <> inspect(%{true => 1, false => 2}))\n'
  '    x: list[integer] = []\n'
  '    IO.puts(inspect(x) <> inspect("") <> inspect(-9223372036854775808))\n'
  '    IO.inspect({1, "two"})\n'
  '    y = IO.inspect(5) + 1\n'
  '    IO.puts(inspect(y))\n'
  '    [1, 2] |> IO.inspect() |> length() |> IO.inspect()\n'
  '    m: map[string, integer] = %{}\n'
  '    IO.inspect(m)\n'
  '    IO.inspect(some(some(1)) == some(none))\n'
  '  end\n'
  'end\n',
  0,
  b'%P{x: 1, name: "a\\n\\"\xc3\xa9\\x01"}\n[Shape.circle(1), Shape.rect(2, 3), Shape.dot]\nTree.node(Tree.leaf, 5, Tree.node(Tree.leaf, 6, Tree.leaf))\n%Bo'
  b'x{v: some("s")}\n{1, "a", true, [1, 2], %{"a" => [], "k" => [some(-5), none]}}\n[ok(1), error("bad")]\n#Function<>\n{}\n%{-1 => {0, 0}, 1 => {2, 3}}%{fal'
  b'se => 2, true => 1}\n[]""-9223372036854775808\n{1, "two"}\n5\n6\n[1, 2]\n2\n%{}\nfalse\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts("a\\u0001b\\u00e9\\u{1F600}\\U0001F601\\u{41}")\n  end\nend\n',
  0,
  b'a\x01b\xc3\xa9\xf0\x9f\x98\x80\xf0\x9f\x98\x81A\n',
  b''),
 ('defmodule M do\n  def main() do\nx = """\n  a\\u00e9\\e\n  """\nIO.puts(inspect(x))\n  end\nend\n', 0, b'"a\xc3\xa9\\x1b\\n"\n', b''),
 ('defmodule M do\n  def main() do\nx = 5\nIO.puts("\\u00e9#{x}\\u{1F600}")\n  end\nend\n', 0, b'\xc3\xa95\xf0\x9f\x98\x80\n', b''),
 ('defmodule M do\n  def main() do\n[1, 2] |> IO.inspect() |> length() |> IO.inspect()\n  end\nend\n', 0, b'[1, 2]\n2\n', b''),
 ('defmodule M do\n  def main() do\nx = 4\nx + 1 |> to_string() |> IO.puts()\n"a" <> "b" |> IO.puts()\n(x * 2) |> IO.inspect()\n  end\nend\n',
  0,
  b'5\nab\n8\n',
  b'')]
# programs the pinned compiler rejects
REJECTS=['defmodule M do\n  def main() do\nIO.puts(inspect("\\a\\b\\f\\v\\e\\s|\\\'\\#\\101\\377\\x41\\n\\t\\r"))\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts("\\q")\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts("\\u12")\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts("\\ud800")\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts("\\u{}")\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts("\\u{110000}")\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts("\\18")\n  end\nend\n',
 'defmodule M do\n  def main() do\nIO.puts(inspect("\\400"))\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = 4\nx + 1\nIO.puts("a")\n  end\nend\n',
 'defmodule M do\n  def main() do\n[1, 2]\nIO.puts("a")\n  end\nend\n',
 'defmodule M do\n  def main() do\nx = "a |> b"\n"|>" <> x\nIO.puts("a")\n  end\nend\n']


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-inspection-') as d:
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
    print(f'PASS inspection: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; inspect of integers, strings, booleans, options, results, tuples, lists, maps, structs, sum types, generic and recursive types and functions; string escapes; pipeline statements')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
