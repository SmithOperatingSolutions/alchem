#!/usr/bin/env python3
"""The compiler's own source grown to the 16 MiB input limit still builds itself from the seed."""
import base64
from importlib.util import spec_from_file_location,module_from_spec
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from run import ROOT

LIMIT=16776191
PROBE=b'defmodule M do\ndef twice(n: integer): integer do n * 2 end\ndef main() do\n IO.puts("grown")\n System.halt(twice(21))\nend\nend\n'


def grown(text,total,functions):
    """text with data functions (base64 byte literals joined as the library
    text is held, scripts/generate-prelude.py) before its entry, up to
    exactly total bytes."""
    at=text.index('def native_compile(');need=total-len(text.encode());made=[];size=0;source=random.Random(7)
    literal=lambda count:'b"'+base64.b64encode(bytes(source.randrange(256) for _ in range(count))).decode()+'"'
    for index in range(functions):
        head=f'def grown_data_{index}(): bytes do\n';tail='\nend\n'
        target=need-size if index==functions-1 else need//functions
        body=literal(99)
        while len(head)+len(body)+len(tail)+540<target:body=f'Enum.concat({body},{literal(384)})'
        made.append(head+body+' '*(target-len(head)-len(body)-len(tail))+tail);size+=len(made[-1])
    result=text[:at]+''.join(made)+text[at:]
    assert len(result.encode())==total,(len(result.encode()),total)
    return result


def verify(frontend,backend,compiler):
    spec=spec_from_file_location('alchem_bootstrap',ROOT/'scripts/bootstrap-alchem-compiler.py');boot=module_from_spec(spec);spec.loader.exec_module(boot)
    text=boot.source_text('functions');count=text.count('\ndef ')
    # Enough data functions to pass the 4096 that the table and seed IR V11
    # once held: the limit is 65,535 and the source limit comes first.
    # As many as leave each one room for its hundred bytes: the compiler's
    # own source grows with the library it holds, and what is left for data
    # shrinks.
    functions=min(6000,(LIMIT-len(text.encode()))//620)
    source=grown(text,LIMIT,functions)
    assert count+functions>4096
    assert len(source.encode())>4*boot.FRONTEND_LIMIT-2,'the grown source is past the pinned parser several times over'
    boot.source_text=lambda language="arithmetic",compact=True,seed=False:source
    with tempfile.TemporaryDirectory(prefix='alchem-grown-compiler-') as directory:
        root=Path(directory);seed=root/'A0'
        boot.bootstrap(seed,Path(frontend).resolve(),Path(backend).resolve(),'functions')
        previous=seed;images=[]
        for stage in (1,2):
            built=subprocess.run([str(previous)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=600)
            assert (built.returncode,built.stderr)==(0,b'') and built.stdout[:4]==b'\x7fELF',('grown self-build',stage,built.returncode,built.stderr)
            image=root/f'A{stage}';image.unlink(missing_ok=True);image.write_bytes(built.stdout);image.chmod(0o700);images.append(built.stdout);previous=image
        assert images[0]==images[1],'grown A1/A2 mismatch'
        # The functions added are data nothing calls: programs compile as they do
        # with the compiler built from the source as it is.
        want=subprocess.run([str(compiler)],input=PROBE,capture_output=True,env={'PATH':''},timeout=120)
        got=subprocess.run([str(previous)],input=PROBE,capture_output=True,env={'PATH':''},timeout=120)
        assert want.returncode==0 and (got.returncode,got.stdout,got.stderr)==(0,want.stdout,b''),('grown compiler output',got.returncode,got.stderr)
        program=root/'probe';program.unlink(missing_ok=True);program.write_bytes(got.stdout);program.chmod(0o700)
        run=subprocess.run([str(program)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(42,b'grown\n',b''),run
        over=subprocess.run([str(previous)],input=source.encode()+b' ',capture_output=True,env={'PATH':''},timeout=120)
        assert (over.returncode,over.stdout,over.stderr)==(65,b'',b'E_RUNTIME_INPUT: input exceeds byte limit\n'),('grown source one byte over',over.returncode,over.stderr)
    print(f'PASS grown compiler: a {len(source.encode())}-byte compiler source of {source.count(chr(10)+"def ")} functions built seed -> A1 == A2 ({len(images[1])} bytes) through the frontend in parts')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve(),Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve())
