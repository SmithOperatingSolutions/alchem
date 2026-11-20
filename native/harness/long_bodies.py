#!/usr/bin/env python3
"""Long statement sequences and deep calls: bodies of hundreds of statements
compile (a branch of about 100 used to end the compiler with status 70, main
stopped at 16 statements and a function at 64 KiB of code), and calls nest as
deep as in the pinned runtime: 100000, where the former guard stopped at 256."""
from pathlib import Path
import subprocess
import sys
import tempfile


def program(kind,count):
    lines=[f'IO.puts("line {i}")' for i in range(count)]
    if kind=='branch':
        return 'defmodule M do\n  def f(k: integer): integer do\n    if k > 0 do\n'+'\n'.join(lines)+'\n      1\n    else\n      2\n    end\n  end\n  def main() do\n    System.halt(f(1) - 1)\n  end\nend\n'
    if kind=='helper':
        return 'defmodule M do\n  def f(k: integer): integer do\n'+'\n'.join(lines)+'\n    0\n  end\n  def main() do\n    System.halt(f(1))\n  end\nend\n'
    return 'defmodule M do\n  def main() do\n'+'\n'.join(lines)+'\n  end\nend\n'


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-long-') as d:
        root=Path(d)
        def built(source):
            # A program of 20000 statements takes 21 s to compile on macOS
            # (signing is slow there) and several times that on a small runner.
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=600)
            assert (result.returncode,result.stderr)==(0,b''),(source[:120],result.returncode,result.stderr)
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            return subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        for kind in ['branch','helper','main']:
            for count in [17,120,600]+([20000] if kind!='helper' else []):
                run=built(program(kind,count))
                assert (run.returncode,run.stdout,run.stderr)==(0,''.join(f'line {i}\n' for i in range(count)).encode(),b''),(kind,count,run.returncode)
        depth='defmodule M do\n  def sum(n: integer): integer do if n == 0 do 0 else n + sum(n - 1) end end\n  def main() do\n    IO.puts(Integer.to_string(sum(%d)))\n    System.halt(0)\n  end\nend\n'
        # Calls nest 100000 deep under main, as in the pinned runtime; one more
        # stops the program with the place, the reason and the 61 calls around it.
        for count,total in [(257,33153),(99999,4999950000)]:
            run=built(depth%count)
            assert (run.returncode,run.stdout,run.stderr)==(0,f'{total}\n'.encode(),b''),(count,run.returncode,run.stderr[:200])
        for source in [depth%100000,'defmodule M do\n  def sum(n: integer): integer do 1 + sum(n + 1) end\n  def main() do\n    System.halt(sum(0))\n  end\nend\n']:
            run=built(source)
            assert (run.returncode,run.stdout,run.stderr)==(2,b'',b'<stdin>:2:7: call depth exceeded\n'+b'  at M.sum (<stdin>:2)\n'*61),(run.returncode,run.stderr[:200])
    print('PASS long bodies: 17/120/600 statements in a branch, a helper and main, 20000 in a branch and main; calls 257 and 99999 deep; the call depth limit at 100000')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
