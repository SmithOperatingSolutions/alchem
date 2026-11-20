#!/usr/bin/env python3
"""IO.puts/IO.write/IO.warn statements inside helpers, if/else branches and case arms."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

# (helpers, main body, stdout, status): expected output follows Alchem evaluation order.
CASES=[
    ('def log(n: integer): integer do IO.puts(Integer.to_string(n))\n IO.write("w")\n n + 1 end ',
     'x = log(41)\nIO.puts(Integer.to_string(x))\nSystem.halt(0)',b'41\nw42\n',0),
    ('def count(n: integer): integer do if n == 0 do IO.puts("done")\n 0 else IO.puts(Integer.to_string(n))\n y = count(n - 1)\n y + n end end ',
     'IO.puts(Integer.to_string(count(3)))\nSystem.halt(0)',b'3\n2\n1\ndone\n6\n',0),
    ('def a(): integer do IO.write("a")\n 1 end def b(): integer do IO.write("b")\n 2 end def add(x: integer, y: integer): integer do IO.write("+")\n x + y end ',
     'System.halt(add(a(),b())+39)',b'ab+',42),
    ('def pick(c: boolean): string do if c do IO.write("yes ")\n IO.write("taken ")\n "t" else IO.write("no ")\n "f" end end ',
     'IO.puts(pick(true) <> pick(false))\nSystem.halt(0)',b'yes taken no tf\n',0),
    ('def nested(n: integer): integer do if n > 0 do IO.write("p")\n if n > 5 do IO.write("big")\n n else IO.write("small")\n s = n * 2\n s end else IO.write("z")\n 0 end end ',
     'System.halt(nested(7)+nested(3)+nested(0))',b'pbigpsmallz',13),
    ('def lines(o: option[string]): integer do case o do some(s) -> 1 none -> 0 end end def echo(n: integer): integer do if n == 0 do 0 else IO.puts("line " <> Integer.to_string(n))\n echo(n - 1) + 1 end end ',
     'System.halt(echo(200))',b''.join(b'line %d\n'%n for n in range(200,0,-1)),200),
    ('def empty(): integer do IO.puts("")\n IO.write("")\n 7 end ',
     'System.halt(empty())',b'\n',7),
    # Output statements at the start of case arms, for results and options.
    ('def arm(r: result[integer,string]): integer do case r do ok(n) -> IO.puts("ok arm")\n n error(e) -> IO.puts("error arm " <> e)\n IO.write("!")\n 0 end end ',
     'System.halt(arm(ok(40))+arm(error("bad"))+2)',b'ok arm\nerror arm bad\n!',42),
    ('def pick(o: option[string]): string do case o do some(s) -> IO.write("some ")\n s none -> IO.write("none ")\n "-" end end ',
     'IO.puts(pick(some("x")) <> pick(none))\nSystem.halt(0)',b'some none x-\n',0),
    ('def greet(name: string): string do IO.write("hello ")\n name end ',
     'name = greet("x")\nIO.puts(name)\nSystem.halt(0)',b'hello x\n',0),
]
REJECTIONS=[
    'def f(): integer do IO.puts(1)\n 0 end ',
    'def f(): integer do IO.puts("a") end ',
    'def f(): integer do if true do IO.puts("a") else 1 end end ',
    'def f(): integer do IO.write(b[65])\n 0 end ',
    'def f(): string do IO.puts("a")\n 1 end ',
    'def f(): integer do IO.warn(1)\n 0 end ',
    'def f(): integer do IO.warn("a", "b")\n 0 end ',
    'def f(): integer do IO.warn("a") end ',
]
# IO.warn writes a line to standard error: (helpers, main body, stdout, stderr, status),
# each equal to the pinned upstream `alchem run`.
WARNINGS=[
    ('def f(n: integer): integer do IO.warn("in f")\n if n > 0 do IO.warn("pos")\n n else 0 end end ',
     'IO.warn("start")\nIO.puts("out")\nx = f(2)\nIO.warn("\\xc3\\xa9" <> Integer.to_string(x))\nSystem.halt(3)',b'out\n',b'start\nin f\npos\n\xc3\xa92\n',3),
    ('def arm(r: result[integer,string]): integer do case r do ok(n) -> n error(e) -> IO.warn("error: " <> e)\n 1 end end ',
     'IO.warn("")\nSystem.halt(arm(error("bad"))+arm(ok(2)))',b'',b'\nerror: bad\n',3),
]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-effect-helpers-') as d:
        root=Path(d)
        for helpers,body,stdout,status in CASES:
            source=('defmodule M do '+helpers+'def main() do '+body+' end end').encode()
            r=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stderr)==(0,b''),(helpers,r.returncode,r.stderr)
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(r.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,b''),(helpers,body,run)
        # Output failure inside a helper exits 74 like main-body output.
        run=subprocess.run([str(out)],capture_output=True,preexec_fn=lambda:os.close(1),timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(74,b'',b''),run
        for helpers,body,stdout,stderr,status in WARNINGS:
            source=('defmodule M do '+helpers+'def main() do '+body+' end end').encode()
            r=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stderr)==(0,b''),(helpers,r.returncode,r.stderr)
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(r.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(helpers,body,run)
        # A failed write to standard error is ignored, as the pinned runtime does: closed or full.
        run=subprocess.run([str(out)],stdout=subprocess.PIPE,preexec_fn=lambda:os.close(2),timeout=120)
        assert (run.returncode,run.stdout)==(3,b''),run
        with open('/dev/full','wb') as full:run=subprocess.run([str(out)],stdout=subprocess.PIPE,stderr=full,timeout=120)
        assert (run.returncode,run.stdout)==(3,b''),run
        for helpers in REJECTIONS:
            source=('defmodule M do '+helpers+'def main() do System.halt(f()) end end').encode()
            r=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(helpers,r)
    print(f'PASS effectful helpers: {len(CASES)} programs with IO in helpers/branches/case arms, ordering, untaken branches, closed stdout, {len(WARNINGS)} IO.warn programs with closed and full stderr, {len(REJECTIONS)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
