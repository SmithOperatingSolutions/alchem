#!/usr/bin/env python3
"""The nil of an option, a result and a sum type, and the calls that are no statements or give no value, as the pinned compiler has them (spec/alchem-failures.md).

harness/nil-forms-cases.json.xz holds the programs with the pinned
compiler's status, standard output and standard error for each, and the
programs it rejects (scripts/generate-nil-forms-cases.py makes the file from
the pinned compiler). They read the value a receive that ran out of time
leaves beside false (an option, a result, a sum type, structs and tuples of
them) in every way a program can: inspect and interpolation, == and !=
(also through type variables, lists, tuples, maps and structs), case with
and without a catch-all, clauses, with, for, pattern bindings, the
library's functions that take an option from a function, JSON, sending the
value on, tasks and agents. And they hold the forms the pinned compiler
rejects that the native compiler took: Kernel. before what is no function
of its own, elem, put_elem and a variant of a sum type as a statement, a
pipeline that ends in one, Process.self as a statement, and a call of a
function that gives no value where a value is used."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import lzma
import subprocess
import sys
import tempfile


def cases():
    return json.loads(lzma.decompress((Path(__file__).resolve().parent/'nil-forms-cases.json.xz').read_bytes()))


def verify(compiler):
    held=cases()
    with tempfile.TemporaryDirectory(prefix='alchem-nil-forms-') as d:
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
    print(f'PASS nil_forms: {ran} programs run as the pinned compiler runs them, {len(held)-ran} rejected; the nil of options, results and sum types read every way, calls that are no statements and calls that give no value')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
