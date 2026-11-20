#!/usr/bin/env python3
"""The pipe operator: left |> call(args) passes left as the call's first argument."""
from pathlib import Path
import subprocess
import sys
import tempfile

HELPERS=('def inc(n: integer): integer do n + 1 end def add(a: integer, b: integer): integer do a + b end def yes(b: boolean): string do if b do "y" else "n" end end '
         'def adder(n: integer): fn[integer, integer] do &(&1 + n) end '
         'def log(n: integer): integer do\n n |> Integer.to_string() |> IO.puts()\n "warned" |> IO.warn()\n n + 1\n end '
         'def tell(b: boolean): integer do if b do\n "yes" |> IO.write()\n 1 else\n "no" |> IO.puts()\n 0 end end ')
# (main body, stdout, stderr): outcomes equal the pinned upstream `alchem run`.
CASES=[
    ('IO.puts(Integer.to_string(5 |> inc()))\nx = [1, 2, 3, 4] |> Enum.filter(&(&1 > 2)) |> Enum.map(&(&1 * 2)) |> Enum.sum()\nIO.puts(Integer.to_string(x))\n'
     'IO.puts("a b" |> String.upcase() |> String.split(" ") |> Enum.join("-"))\nr = [3, 4]\n  |> Enum.map(fn n -> n * n end)\n  |> Enum.sum()\nIO.puts(Integer.to_string(r))\n'
     'f = fn(n: integer): integer do n * 3 end\nIO.puts(Integer.to_string(2 |> f.() |> Integer.to_string() |> byte_size()))',b'6\n14\nA-B\n25\n1\n',b''),
    # Looser than + and <>, tighter than ==; the piped value is evaluated first.
    ('IO.puts(Integer.to_string(1 + 2 |> inc()))\nIO.puts(yes(2 |> inc() == 3))\nIO.puts("a" <> "b" |> String.upcase())\nIO.puts(Integer.to_string(-1 |> inc()))\n'
     'IO.puts(Integer.to_string(if true do 1 else 2 end |> inc()))\nIO.puts(Integer.to_string((1 |> inc()) * 5))\nIO.puts(Integer.to_string(add(1 |> inc(), 2 |> inc())))\n'
     'IO.puts(Integer.to_string(1 |> add(2 |> add(3 |> inc()))))\nIO.puts(Integer.to_string(1 |> add(2 |> inc()) |> add(100)))\nIO.puts(Integer.to_string(log(1) |> add(log(5))))',
     b'4\ny\nAB\n0\n2\n10\n5\n7\n104\n1\n5\n8\n',b'warned\nwarned\n'),
    # Every kind of call: qualified, through values, builtins, constructors, libraries with optional arguments.
    ('g = adder(10)\nk = 3\nm = %{"a" => 1} |> Map.put("b", 2)\nIO.puts(Integer.to_string(3 |> M.inc()))\nIO.puts(Integer.to_string({1, 2} |> elem(1)))\n'
     'IO.puts(Integer.to_string(case 5 |> some() do some(n) -> n none -> 0 end))\nIO.puts(255 |> Integer.to_string(16))\nIO.puts(Integer.to_string(5 |> g() |> g.()))\n'
     'IO.puts(Integer.to_string([1, 2] |> Enum.map(fn n -> n |> add(k) end) |> Enum.sum()))\nIO.puts(Integer.to_string(m |> Map.get("b", 0)))\n'
     'IO.puts("  x " |> String.trim() |> String.pad_leading(3, "-") |> String.reverse())\nIO.puts(Integer.to_string("abc" |> byte_size()))',
     b'4\n2\n5\nFF\n25\n9\n2\nx--\n3\n',b''),
    # A pipeline may end in IO.puts(), IO.write() or IO.warn() as a statement, in main, helpers, branches and lambdas.
    ('"x" |> IO.puts()\n5 |> inc() |> Integer.to_string() |> IO.puts()\nx = log(41)\n"a" <> "b" |> String.upcase() |> IO.write()\nIO.puts(Integer.to_string(x + tell(true) + tell(false)))\n'
     'Enum.sum(Enum.map([1, 2], fn n ->\n  n |> Integer.to_string() |> IO.puts()\n  n\nend)) |> Integer.to_string() |> IO.puts()',
     b'x\n6\n41\nAByesno\n43\n1\n2\n3\n',b'warned\n'),
]
# Rejected natively and by the pinned compiler.
REJECTIONS=[
    ('r = 1 |> add(2) |> inc','target without an argument list'),
    ('IO.puts(1 == 1 |> yes())','pipe binds tighter than =='),
    ('IO.puts(Integer.to_string(1 |> inc() + 10))','operator after the target call'),
    ('IO.puts(Integer.to_string(1 |> inc() * 2))','product after the target call'),
    ('IO.puts(1 |> System.pid())','call that takes no argument'),
    ('IO.puts(Integer.to_string(1 |> inc(2)))','one argument too many'),
    ('IO.puts(Integer.to_string("a" |> inc()))','piped value of the wrong type'),
    ('IO.puts(Integer.to_string(5 |> adder(1)()))','call result as the target'),
    ('IO.puts(Integer.to_string(5 |> 6))','target that is not a call'),
    ('x = "a" |> IO.puts()','binding a statement'),
    ('5 |> IO.puts()','output of a non-string'),
    ('IO.puts("a" |> IO.puts())','output as an argument'),
    ('"a" |> IO.puts("b")','output with an argument'),
    ('x = some("a" |> IO.puts())','output inside a constructor'),
    ('IO.puts(Integer.to_string(1 |> add(2, 3)))','two arguments too many'),
    ('IO.puts(Integer.to_string(1 |> missing()))','undefined target'),
]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-pipes-') as d:
        root=Path(d)
        def compiled(body):
            return subprocess.run([str(compiler)],input=('defmodule M do '+HELPERS+'def main() do '+body+'\nSystem.halt(0) end end').encode(),capture_output=True,env={'PATH':''},timeout=120)
        for body,stdout,stderr in CASES:
            result=compiled(body)
            assert (result.returncode,result.stderr)==(0,b''),(body[:120],result.returncode,result.stderr)
            assert compiled(body).stdout==result.stdout,'pipe determinism'
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(0,stdout,stderr),(body[:120],run)
        # Pipes nest inside arguments up to the expression nesting limit: seven deep, not eight.
        result=compiled('IO.puts(Integer.to_string('+'1 |> add('*7+'1'+')'*7+'))')
        assert result.returncode==0,('nested pipes',result.returncode)
        out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout)==(0,b'8\n'),('nested pipes',run)
        # Each nested pipe holds its value in a frame slot.
        result=compiled('IO.puts(Integer.to_string('+'1 |> add('*8+'1'+')'*8+'))')
        assert (result.returncode,result.stderr)==(0,b''),('eight nested pipes',result.returncode)
        out.write_bytes(result.stdout)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout)==(0,b'9\n'),('eight nested pipes',run)
        result=compiled('IO.puts(Integer.to_string('+'1 |> add('*40+'1'+')'*40+'))')
        assert (result.returncode,result.stderr)==(0,b''),('forty nested pipes',result.returncode)
        out.write_bytes(result.stdout)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout)==(0,b'41\n'),('forty nested pipes',run)
        # A chain is not nesting: forty calls in one pipeline.
        result=compiled('IO.puts(Integer.to_string(0'+' |> inc()'*40+'))')
        assert result.returncode==0,('pipe chain',result.returncode)
        out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout)==(0,b'40\n'),('pipe chain',run)
        for body,label in REJECTIONS:
            result=compiled(body)
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
    print(f'PASS pipes: {len(CASES)} programs with calls of every kind, precedence, evaluation order and output statements, nesting to the expression limit and a chain of 40, {len(REJECTIONS)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
