#!/usr/bin/env python3
"""Differences from the pinned compiler that were closed: every program runs as the pinned compiler runs it.

harness/gaps-cases.json.xz holds the programs with the pinned compiler's
status, standard output and standard error for each, and the programs it
rejects (scripts/generate-gaps-cases.py makes the file from the pinned
compiler). They are lambdas wherever a type is expected of them (arguments,
list elements, tuple parts, map values, struct fields, branches, pipes,
returned values, nested), lambda bodies that take their type from the
result expected, values that are functions called where they stand,
function values through generic library functions, the bitwise operators,
the list functions kept without a module, put_elem, String.normalize, the
words that may name a binding, programs at and past each fixed limit the
native compiler had and at sizes of a few thousand (spec/source-capacity.md),
generic functions that need equality for a type variable (spec/alchem-generics.md)
and arguments of the library's enum parameters."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import lzma
import subprocess
import sys
import tempfile

# A library function's name in a comment or in the text of a string appends
# nothing (ny_pick reads code): both programs of a pair are the same but
# for such names, so their images have the same size. An interpolated
# expression is code and appends what it calls.
QUIET=('defmodule M do\n  # nothing to see: plain words in a comment, of the same length.\n  def main() do\n'
       '    IO.puts("a plain text: no names; only words of the same len")\n    IO.puts("count #{length([1, 2])}")\n  end\nend\n')
NAMED=('defmodule M do\n  # HTTP.serve(a, f) and Enum.chunk_every(x, 2) in a comment here\n  def main() do\n'
       '    IO.puts("HTTP.serve: not started; Regex.run( Enum.zip(a, b)")\n    IO.puts("count #{length([1, 2])}")\n  end\nend\n')
CALLED=('defmodule M do\n  def main() do\n    IO.puts("count #{Enum.count(Enum.dedup([1, 1, 2]))}")\n  end\nend\n',0,b'count 2\n')


def cases():
    return json.loads(lzma.decompress((Path(__file__).resolve().parent/'gaps-cases.json.xz').read_bytes()))


def verify(compiler):
    held=cases()
    with tempfile.TemporaryDirectory(prefix='alchem-gaps-') as d:
        def one(item):
            number,(source,status,stdout,stderr)=item
            built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            if status is None:
                assert (built.returncode,built.stdout)==(65,b''),(source,built.returncode)
                return 0
            assert (built.returncode,built.stderr)==(0,b''),(source,built.returncode,built.stderr)
            out=Path(d)/f'p{number}';out.unlink(missing_ok=True);out.write_bytes(built.stdout);out.chmod(0o700)
            for attempt in range(50):
                try:run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},cwd=d,stdin=subprocess.DEVNULL,timeout=120);break
                except OSError as error:
                    # Another thread's fork may still hold the file open for writing.
                    if error.errno!=26 or attempt==49:raise
            out.unlink()
            assert (run.returncode,run.stdout.decode('utf8','replace'),run.stderr.decode('utf8','replace'))==(status,stdout,stderr),(source,run,status,stdout,stderr)
            return 1
        with ThreadPoolExecutor(8) as pool:ran=sum(pool.map(one,enumerate(held)))
        sizes=[]
        for source in (QUIET,NAMED):
            built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (built.returncode,built.stderr)==(0,b''),(source,built.returncode)
            sizes.append(len(built.stdout))
        assert sizes[0]==sizes[1],('library names in a comment and a string appended something',sizes)
        source,status,stdout=CALLED
        built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
        assert built.returncode==0 and len(built.stdout)>sizes[0],('an interpolated call appended nothing',built.returncode,len(built.stdout),sizes)
        out=Path(d)/'called';out.unlink(missing_ok=True);out.write_bytes(built.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout)==(status,stdout),run
    print(f'PASS gaps: {ran} programs run as the pinned compiler runs them, {len(held)-ran} rejected; lambdas wherever a type is expected, bodies held to the result expected, calls of any function value, function values through generic functions, bitwise operators, the functions kept without a module, put_elem, String.normalize, binding names, fixed limits, and library names in comments and strings')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
