#!/usr/bin/env python3
"""alchem, the test, run, build, check and new commands with the bundler and the compiler in one program (tools/alchem.alc, scripts/build-alchem.py), against the pinned command line (spec/alchem-testing-gen.md).

harness/test-driver-cases.json.xz holds projects (their files), runs of the
pinned `alchem test`, `alchem run` and `alchem build` in them with the
status, standard output and standard error of each, and the cover file the
pinned runner's test program writes for a test file under `--cover`
(scripts/generate-test-driver-cases.py makes the file from the pinned
compiler). alchem is built by the compiler under test, from the same
source, and run in a copy of each project: the same status and the same text, but
for the time a run took, the times of a trace, and the message after "did
not compile:", which is the pinned compiler's diagnostic there and the
compiler's one message here. The cover file of each test program, run with
ALCHEM_COVER_FILE, is the pinned one line for line (the program is bundled
by tools/alchem-bundle.alc and compiled by the compiler under test)."""
from pathlib import Path
import json
import lzma
import os
import re
import socket
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec,spec_from_file_location

ROOT=Path(__file__).resolve().parents[1]


def cases():
    return json.loads(lzma.decompress((Path(__file__).resolve().parent/'test-driver-cases.json.xz').read_bytes()))


def shown(text,root):
    """What a run printed, without what differs from run to run and from compiler to compiler."""
    text=text.replace(str(root)+'/','').replace(str(root),'.')
    text=re.sub(r'Finished in [0-9.]+ seconds','Finished in X seconds',text)
    text=re.sub(r'\([0-9.]+ms\)','(Xms)',text)
    return re.sub(r'( did not compile:\n)(  [^\n]*\n)+',r'\1  (message)\n',text)


def lay(files,root):
    for path,text in files.items():
        (root/path).parent.mkdir(parents=True,exist_ok=True);(root/path).write_bytes(text.encode('utf8','surrogateescape'))


def tools(compiler,base):
    """alchem and the bundler alone, built by the compiler."""
    spec=spec_from_file_location('build_alchem',ROOT/'scripts/build-alchem.py');builder=module_from_spec(spec);spec.loader.exec_module(builder)
    # A compiler that makes macOS programs (Mach-O) builds `alchem` for macOS.
    probe=subprocess.run([str(compiler)],input=b'defmodule M do\n  def main() do\n    System.halt(0)\n  end\nend\n',capture_output=True,env={'PATH':''},timeout=120)
    made={'alchem':base/'alchem'};builder.build(compiler,made['alchem'],probe.stdout[:4]==b'\xcf\xfa\xed\xfe')
    built=subprocess.run([str(compiler)],input=(ROOT/'tools/alchem-bundle.alc').read_bytes(),capture_output=True,env={'PATH':''},timeout=300)
    assert (built.returncode,built.stderr)==(0,b''),('alchem-bundle',built.returncode,built.stderr)
    made['alchem-bundle']=base/'alchem-bundle';made['alchem-bundle'].unlink(missing_ok=True);made['alchem-bundle'].write_bytes(built.stdout);made['alchem-bundle'].chmod(0o700)
    return made


def driven(compiler,made,root,temporary,command,arguments,given):
    # Nothing but alchem itself builds a program: no compiler or bundler is named.
    run=subprocess.run([str(made['alchem']),command]+arguments,input=given.encode(),capture_output=True,cwd=root,env={'PATH':'/usr/bin:/bin','TMPDIR':str(temporary)},timeout=600)
    return [run.returncode,shown(run.stdout.decode('utf8','replace'),root),shown(run.stderr.decode('utf8','replace'),root)]


def covered(compiler,made,root,temporary,test):
    """The cover file of one test file's program."""
    bundle=subprocess.run([str(made['alchem-bundle']),test],capture_output=True,cwd=root,env={'PATH':''},timeout=120)
    assert bundle.returncode==0,(test,bundle.stderr)
    built=subprocess.run([str(compiler)],input=bundle.stdout,capture_output=True,env={'PATH':''},timeout=300)
    assert (built.returncode,built.stderr)==(0,b''),(test,built.returncode,built.stderr)
    out=temporary/'covered';out.unlink(missing_ok=True);out.write_bytes(built.stdout);out.chmod(0o700);cover=temporary/'cover'
    if cover.exists():cover.unlink()
    subprocess.run([str(out)],capture_output=True,cwd=root,env={'PATH':'','ALCHEM_SEED':'7','ALCHEM_COVER_FILE':str(cover),'ALCHEM_TEST_TIMEOUT':'30000'},timeout=300)
    return cover.read_text().replace(str(root)+'/','') if cover.exists() else ''


# -cover-functions, which the pinned command has not: the functions of each
# file that ran, and those none of whose lines ran, by name and line (the
# clauses of label/1 are one function).
FUNCTIONS={'cart.alc':'defmodule Cart do\n  def total(items: list[integer]): integer do\n    Enum.sum(items)\n  end\n\n  def empty?(items: list[integer]): boolean do\n    items == []\n  end\n\n  def kind(n: integer): string do\n    if n > 10 do\n      "big"\n    else\n      "small"\n    end\n  end\n\n  def label(0): string do\n    "none"\n  end\n\n  def label(n: integer): string do\n    "#{n} items"\n  end\nend\n',
           'cart_test.alc':'defmodule CartTest do\n  import "cart.alc"\n\n  test "total" do\n    assert(Cart.total([1, 2]) == 3)\n    assert(Cart.kind(3) == "small")\n  end\nend\n'}
FUNCTIONS_OUT=('.\n\nFinished in X seconds\n1 test, 0 failures\n\nRandomized with seed 1\n\n'
    'Percentage | File\n-----------|--------------------------\n     37.5% | cart.alc\n'
    '-----------|--------------------------\n     37.5% | Total\n\ncart.alc: lines not run: 7, 12, 18-19, 23\n\n'
    'Functions run | File\n--------------|--------------------------\n          2/4 | cart.alc\n\n'
    'cart.alc: functions not run: Cart.empty?/1 (6), Cart.label/1 (18)\n')


def verify(compiler):
    held=cases()
    with tempfile.TemporaryDirectory(prefix='alchem-test-driver-') as top:
        base=Path(top);made=tools(compiler,base);temporary=base/'tmp';temporary.mkdir()
        roots={}
        for name,files in held['projects'].items():
            roots[name]=base/'projects'/name;roots[name].mkdir(parents=True);lay(files,roots[name])
        for project,command,arguments,given,status,stdout,stderr in held['runs']:
            seen=driven(compiler,made,roots[project],temporary,command,arguments,given)
            assert seen==[status,stdout,stderr],(project,command,arguments,seen,[status,stdout,stderr])
        # Standard input a socket, which /proc cannot open again: the program
        # reads no input, as with an empty one (a special built-in testing it
        # ended the shell with status 2).
        project,command,arguments,given,status,stdout,stderr=next(r for r in held['runs'] if r[1]=='run' and r[3]=='')
        mine,theirs=socket.socketpair();theirs.close()
        try:run=subprocess.run([str(made['alchem']),command]+arguments,stdin=mine,capture_output=True,cwd=roots[project],env={'PATH':'/usr/bin:/bin','TMPDIR':str(temporary)},timeout=600)
        finally:mine.close()
        seen=[run.returncode,shown(run.stdout.decode('utf8','replace'),roots[project]),shown(run.stderr.decode('utf8','replace'),roots[project])]
        assert seen==[status,stdout,stderr],('run with a socket for input',project,arguments,seen)
        for project,test,text in held['covers']:
            seen=covered(compiler,made,roots[project],temporary,test)
            assert seen==text,(project,test,seen,text)
        root=base/'projects'/'functions';root.mkdir(parents=True);lay(FUNCTIONS,root)
        seen=driven(compiler,made,root,temporary,'test',['-seed','1','-cover-functions','.'],'')
        assert seen==[0,FUNCTIONS_OUT,''],('-cover-functions',seen)
        left=[p.name for p in temporary.iterdir() if p.name.startswith('alchem-')]
        assert not left,('the driver left its work behind',left)
    print(f"PASS test_driver: {len(held['runs'])} runs of alchem test, run, build, check and new in {len(held['projects'])} projects as the pinned command line prints them, {len(held['covers'])} cover files line for line, and -cover-functions")


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
