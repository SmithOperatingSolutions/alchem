#!/usr/bin/env python3
"""Stored native booleans with independent comparison/type oracles."""
from pathlib import Path
from source_syntax import native_bytes
import random
import subprocess
import sys
import tempfile
from self_hosted_components import verify_legacy_program as verify_program
from native_memory import profile,TraceUnavailable


def verify(compiler):
    cases=[('','a=true\nb=false\nif a do if not b do System.halt(42) else System.halt(1) end else System.halt(2) end',42),('defp same(a: boolean,b: boolean): boolean do a == b end ','if same(true,not false) do System.halt(42) else System.halt(1) end',42),('def f(n: integer): boolean do if n == 0 do true else not f(n-1) end end ','if f(20) do System.halt(42) else System.halt(1) end',42)]
    rng=random.Random(171119)
    pairs=[(-(1<<63),(1<<63)-1),(0,0),(-1,1)]+[(rng.randrange(-(1<<63),(1<<63)),rng.randrange(-(1<<63),(1<<63))) for _ in range(24)]
    for op in ['==','!=','<','<=','>','>=']:
        for a,b in pairs:
            expected=42 if eval(f'{a}{op}{b}') else 7
            cases.append(('',f'predicate={a} {op} {b}\nif predicate do System.halt(42) else System.halt(7) end',expected))
    for data in ['[]','[0]','[0,255]']:
        cases.append(('',f'value=Enum.empty?({data})\nif value do System.halt(42) else System.halt(7) end',42 if data=='[]' else 7))
    cases += [('def forever(): string do forever() end ','found=String.contains?("",forever())\nSystem.halt(0)',2),('def ready?(): boolean do true end ','if ready?() do System.halt(42) else System.halt(1) end',42),('def pick(a: boolean,b: integer,c: list[integer],d: string,e: boolean,f: integer): boolean do if a do e else b < f end end ','if pick(true,1,[0],"x",false,2) do System.halt(7) else System.halt(42) end',42)]
    for op in ['and','or']:
        for a in [False,True]:
            for b in [False,True]:
                expected=(a and b) if op=='and' else (a or b)
                cases.append(('',f'p={str(a).lower()} {op} {str(b).lower()}\nif p do System.halt(42) else System.halt(7) end',42 if expected else 7))
    for expression,status in [('true or false and false',42),('(true or false) and false',7),('not false and true',42),('1 < 2 and 3 > 2',42)]:
        cases.append(('',f'if {expression} do System.halt(42) else System.halt(7) end',status))
    for expression,status in [('true or forever()',42),('false and forever()',7),('false or forever()',2),('true and forever()',2)]:
        cases.append(('def forever(): boolean do forever() end ',f'if {expression} do System.halt(42) else System.halt(7) end',status))
    texts=[b'',b'a',b'aaaa',b'ababa',b'abcabc','é中😀'.encode(),b'\0\xff']
    pairs=[(a,b) for a in texts for b in texts]+[(bytes(rng.randrange(256) for _ in range(rng.randrange(40))),bytes(rng.randrange(256) for _ in range(rng.randrange(8)))) for _ in range(48)]
    for a,b in pairs:
        literal=lambda data:'"'+''.join(f'\\x{value:02x}' for value in data)+'"'
        for name,expected in [('contains?',b in a),('starts_with?',a.startswith(b)),('ends_with?',a.endswith(b))]:
            cases.append(('',f'found=String.{name}({literal(a)},{literal(b)})\nif found do System.halt(42) else System.halt(7) end',42 if expected else 7))
    with tempfile.TemporaryDirectory(prefix='alchem-bool-') as directory:
        root=Path(directory)
        for number,(helpers,body,status) in enumerate(cases):
            verify_program('defmodule M do '+helpers+'def main() do '+body+' end end',compiler,root,('boolean',number),status)
        invalid=['x=false and 1\nSystem.halt(0)','x=true or []\nSystem.halt(0)','x=none or false\nSystem.halt(0)','a=String.contains?([],\"x\")\nSystem.halt(0)','a=String.starts_with?(\"x\",1)\nSystem.halt(0)','a=String.ends_with?(\"x\")\nSystem.halt(0)','System.halt(true)','a=true+1\nSystem.halt(0)','if 1 do System.halt(0) else System.halt(1) end','a=not 1\nSystem.halt(0)','a=true < false\nSystem.halt(0)','a=true == 1\nSystem.halt(0)','a=Enum.empty?("x")\nSystem.halt(0)','a=Enum.empty?([],1)\nSystem.halt(0)','a=if true do true else 1 end\nSystem.halt(0)','a=1 < 2 < 3\nSystem.halt(0)']
        for body in invalid:
            result=subprocess.run([str(compiler)],input=native_bytes(('defmodule M do def main() do '+body+' end end').encode()),capture_output=True,env={'PATH':''},timeout=120)
            assert result.returncode==65 and not result.stdout,('boolean rejection',body,result.returncode,result.stderr)
        measured=0
        for expression,charge in [('true',0),('1 < 2',0),('Enum.empty?([])',8),('String.contains?("abc","b")',0)]:
            source=('defmodule M do def main() do p='+expression+'\nSystem.halt(0) end end').encode()
            built=subprocess.run([str(compiler)],input=native_bytes(source),capture_output=True,env={'PATH':''},timeout=120)
            assert built.returncode==0,built.stderr
            target=root/'arena';target.unlink(missing_ok=True);target.write_bytes(built.stdout);target.chmod(0o700)
            try:
                status,data,errors,charged=profile(target,b'')
                assert (status,data,errors,charged)==(0,b'',b'',charge),(expression,charged,charge)
                measured+=1
            except TraceUnavailable:print('SKIP boolean arena: ptrace unavailable')
    print(f'Boolean/predicate arena measurements: {measured}/4')
    print(f'PASS {len(cases)} native boolean programs and {len(invalid)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
