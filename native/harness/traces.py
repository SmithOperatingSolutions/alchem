#!/usr/bin/env python3
"""A program that cannot go on ends as the pinned runtime ends it: the file,
line and column, the reason, and one line per active call, with status 2."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_bundle',ROOT/'scripts/bundle-alchem.py')
bundler=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundler)

FILES={'lib/util.alc':'''defmodule Util do
  def unwrap(o: option[integer]): integer do
    some(x) = o
    x
  end

  def each(items: list[option[integer]]): integer do
    Enum.sum(Enum.map(items, fn some(v) -> v end))
  end
end
''','app.alc':'''# A comment before the module.
defmodule App do
  import "lib/util.alc"

  def deep(n: integer, o: option[integer]): integer do
    if n == 0 do
      Util.unwrap(o)
    else
      deep(n - 1, o) + 1
    end
  end
  def sum(n: integer): integer do
    if n == 0 do 0 else n + sum(n - 1) end
  end
  def gen(x: t, o: option[t]): t do
    some(y) = o
    y
  end

  def main() do
    mode = Enum.at(System.argv(), 0, "a")
    if mode == "a" do
      {1, y} = {2, 5}
      IO.puts(Integer.to_string(y))
    end
    if mode == "b" do IO.puts(Integer.to_string(deep(3, none))) end
    if mode == "c" do IO.puts(Integer.to_string(Util.each([some(1), none]))) end
    if mode == "d" do
      IO.puts(Integer.to_string(Enum.reduce([1, 2], 0, fn v, acc ->
        f: fn[option[integer], integer] = fn o -> Util.unwrap(o) end
        acc + f(none)
      end)))
    end
    if mode == "e" do
      z = Enum.reduce(["é"], 2, fn "é", 1 -> 5 end)
      IO.puts(Integer.to_string(z))
    end
    if mode == "f" do
      x = case {1, 2} do
        {a, b} ->
          [h | t] = Enum.drop([a], b)
          h
      end
      IO.puts(Integer.to_string(x + gen(1, none)))
    end
    if mode == "g" do IO.puts(Integer.to_string(deep(200, none))) end
    if mode == "h" do IO.puts(Integer.to_string(sum(99999))) end
    if mode == "i" do IO.puts(Integer.to_string(sum(100000))) end
    if mode == "j" do
      IO.puts(Integer.to_string([some(1), none] |> Enum.map(&Util.unwrap/1) |> Enum.sum()))
    end
    IO.puts("end")
  end
end
'''}
# mode -> (standard output, standard error with {a} for app.alc and {u} for lib/util.alc)
EXPECTED={
    'a':(b'','{a}:23:7: pattern match failed\n  at App.main ({a}:23)\n'),
    'b':(b'','{u}:3:5: pattern match failed\n  at Util.unwrap ({u}:3)\n  at App.deep ({a}:7)\n'+'  at App.deep ({a}:9)\n'*3+'  at App.main ({a}:26)\n'),
    'c':(b'','{u}:8:33: pattern match failed\n  at Util.each <closure> ({u}:8)\n  at Util.each ({u}:8)\n  at App.main ({a}:27)\n'),
    'd':(b'','{u}:3:5: pattern match failed\n  at Util.unwrap ({u}:3)\n  at App.main <closure> ({a}:30)\n  at App.main <closure> ({a}:31)\n  at App.main ({a}:29)\n'),
    'e':(b'','{a}:35:41: pattern match failed\n  at App.main <closure> ({a}:35)\n  at App.main ({a}:35)\n'),
    'f':(b'','{a}:41:11: pattern match failed\n  at App.main <closure> ({a}:41)\n  at App.main ({a}:39)\n'),
    'g':(b'','{u}:3:5: pattern match failed\n  at Util.unwrap ({u}:3)\n  at App.deep ({a}:7)\n'+'  at App.deep ({a}:9)\n'*61),
    'h':(b'4999950000\nend\n',''),
    'i':(b'','{a}:12:7: call depth exceeded\n'+'  at App.sum ({a}:13)\n'*61),
    'j':(b'','{u}:3:5: pattern match failed\n  at Util.unwrap ({u}:3)\n  at App.main ({a}:50)\n'),
}


def write(root):
    for name,text in FILES.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    return root/'app.alc'


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-traces-') as d:
        root=Path(d).resolve();entry=write(root)
        # The bundle keeps every file's lines and names the files.
        bundle=bundler.bundle(entry)
        built=subprocess.run([str(compiler)],input=bundle,capture_output=True,env={'PATH':''},timeout=120)
        assert (built.returncode,built.stderr)==(0,b''),(built.returncode,built.stderr)
        out=root/'out';out.write_bytes(built.stdout);out.chmod(0o700)
        for mode,(stdout,stderr) in EXPECTED.items():
            run=subprocess.run([str(out),mode],capture_output=True,env={'PATH':''},timeout=120)
            want=stderr.format(a=entry,u=root/'lib/util.alc').encode()
            assert (run.returncode,run.stdout,run.stderr)==(2 if stderr else 0,stdout,want),(mode,run.returncode,run.stdout,run.stderr[:300])
        # Source given to the compiler directly has no file name.
        plain=subprocess.run([str(compiler)],input=b'defmodule M do\n  def main() do\n    IO.puts(System.cwd!())\n    [a] = [1, 2]\n  end\nend\n',capture_output=True,env={'PATH':''},timeout=120)
        assert (plain.returncode,plain.stderr)==(0,b''),plain.stderr
        out.write_bytes(plain.stdout)
        run=subprocess.run([str(out)],capture_output=True,cwd=root,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(2,str(root).encode()+b'\n',b'<stdin>:4:5: pattern match failed\n  at M.main (<stdin>:4)\n'),run
    print(f'PASS traces: {len(EXPECTED)} runs across two bundled files with the file, line, column and calls of each failure; closures, the 63-call limit of a trace, the call depth limit, System.cwd!')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
