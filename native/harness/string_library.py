#!/usr/bin/env python3
"""Typed native strings and output, independently checked as byte streams."""
from pathlib import Path
from source_syntax import native_bytes
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
from native_memory import profile,TraceUnavailable


def verify(compiler):
    values=['','hello','do end # [] ()','quote"slash\\','line\nreturn\rtab\t','é中😀','\0','x'*128]
    rng=random.Random(171118)
    values += [''.join(rng.choice('abcé中😀\n\t') for _ in range(rng.randrange(30))) for _ in range(40)]
    cases=[]
    for value in values:
        literal=json.dumps(value,ensure_ascii=False).replace('\\u0000','\\x00')
        cases.append(('def echo(s: string): string do s end ',f's=echo({literal})\nIO.puts(s)\nSystem.halt(byte_size(s))',value.encode()+b'\n',len(value.encode())))
    cases += [('',r'IO.puts("\#{literal}")'+ '\nSystem.halt(0)',b'#{literal}\n',0),('def a(s: string): string do b(s) end defp b(s: string): string do s end ','IO.puts(a("forward"))\nSystem.halt(0)',b'forward\n',0),('defp echo(s: string): string do if byte_size(s) == 0 do "empty" else s end end ','a="é"\nb=echo(a <> "中")\nIO.puts(b)\nIO.puts(a)\nSystem.halt(byte_size(b))','é中\né\n'.encode(),5),('',r'IO.puts("\x00\x7f\xFF")'+ '\nSystem.halt(0)',b'\0\x7f\xff\n',0)]
    cases += [('',f'IO.puts("\\x{value:02x}")\nSystem.halt(0)',bytes([value])+b'\n',0) for value in range(256)]
    cases += [('def pick(a: string,b: integer,c: list[integer],d: string,e: integer,f: string): string do if b < e do a <> d <> f else f end end ','a="A"\nb=pick(a,0,[42],"中",1,"Z")\nIO.puts(b)\nIO.puts(a)\nSystem.halt(byte_size(b))','A中Z\nA\n'.encode(),5)]
    numbers=[-(1<<63),(1<<63)-1,0,1,-1,42,-42]+[rng.randrange(-(1<<63),(1<<63)) for _ in range(96)]
    cases += [('',f's=Integer.to_string({value})\nIO.puts(s)\nSystem.halt(byte_size(s))',str(value).encode()+b'\n',len(str(value))) for value in numbers]
    with tempfile.TemporaryDirectory(prefix='alchem-string-') as directory:
        root=Path(directory)
        for helpers,body,expected,status in cases:
            source=('defmodule M do '+helpers+'def main() do '+body+' end end').encode()
            built=subprocess.run([str(compiler)],input=native_bytes(source),capture_output=True,env={'PATH':''},timeout=120)
            assert (built.returncode,built.stderr)==(0,b''),('string compilation',source,built)
            again=subprocess.run([str(compiler)],input=native_bytes(source),capture_output=True,env={'PATH':''},timeout=120)
            assert (again.returncode,again.stdout,again.stderr)==(0,built.stdout,b''),'string determinism'
            target=root/'target';target.unlink(missing_ok=True);target.write_bytes(built.stdout);target.chmod(0o700)
            result=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout,result.stderr)==(status,expected,b''),(source,result,expected)
        # Real output failures and both payload/newline interrupted writes.
        source=b'defmodule M do def main() do IO.puts("hello") System.halt(42) end end'
        built=subprocess.run([str(compiler)],input=native_bytes(source),capture_output=True,env={'PATH':''},timeout=120)
        assert built.returncode==0,built.stderr
        target=root/'errors';target.unlink(missing_ok=True);target.write_bytes(built.stdout);target.chmod(0o700)
        closed=subprocess.run([str(target)],capture_output=True,preexec_fn=lambda:os.close(1),timeout=120)
        assert (closed.returncode,closed.stdout,closed.stderr)==(74,b'',b''),closed
        with open('/dev/full','wb') as full:
            failed=subprocess.run([str(target)],stdout=full,stderr=subprocess.PIPE,timeout=120)
            assert (failed.returncode,failed.stderr)==(74,b''),failed
        tracer=shutil.which('strace');injected=0
        if tracer:
            for rule in ['error=EINTR:when=1','error=EINTR:when=2','retval=0:when=1','retval=0:when=2','retval=2:when=1']:
                result=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e','inject=write:'+rule,str(target)],capture_output=True,timeout=120)
                if b'ptrace' in result.stderr and b'Operation not permitted' in result.stderr:print('SKIP string output injection: ptrace unavailable')
                else:
                    expected=(42,b'hello\n',b'') if 'EINTR' in rule else (42,b'llo\n',b'') if 'retval=2' in rule else (74,b'hello' if 'when=2' in rule else b'',b'')
                    assert (result.returncode,result.stdout,result.stderr)==expected,(rule,result)
                    injected+=1
        else:print('SKIP string output injection: strace unavailable')
        measured=0
        for expression,charge in [('Integer.to_string(0)',16),('Integer.to_string(-9223372036854775808)',32),('Integer.to_string(9223372036854775807)',32),('"a" <> ""',16),('""',0)]:
            source=('defmodule M do def main() do s='+expression+'\nSystem.halt(0) end end').encode()
            built=subprocess.run([str(compiler)],input=native_bytes(source),capture_output=True,env={'PATH':''},timeout=120)
            assert built.returncode==0,built.stderr
            target=root/'arena';target.unlink(missing_ok=True);target.write_bytes(built.stdout);target.chmod(0o700)
            try:
                status,data,errors,charged=profile(target,b'')
                assert (status,data,errors,charged)==(0,b'',b'',charge),(expression,charged,charge)
                measured+=1
            except TraceUnavailable:print('SKIP string arena: ptrace unavailable')
        invalid=['Integer.to_string(\"x\")','Integer.to_string([])','Integer.to_string(1,2,3)','Integer.to_string()','String.length([])','String.length(1)','String.length(\"x\",1)','String.length()','byte_size([])' ,'Enum.count("x")','1 <> "x"','"x" + "y"','byte_size(1)','byte_size("x",1)',r'"bad\q"',r'"bad\xZ1"',r'"bad\u{}"',r'"bad\ud800"',r'"bad\18"','"unterminated','"line\nline"']
        bad=['Integer=1\nSystem.halt(0)']+['value='+expression+'\nSystem.halt(0)' for expression in invalid]+['IO.puts([])\nSystem.halt(0)','IO.puts(1)\nSystem.halt(0)','System.halt(\"x\")','IO.puts("x",1)\nSystem.halt(0)']
        for body in bad:
            source=('defmodule M do def main() do '+body+' end end').encode()
            result=subprocess.run([str(compiler)],input=native_bytes(source),capture_output=True,env={'PATH':''},timeout=120)
            assert result.returncode==65 and not result.stdout,('string rejection',source,result.returncode,result.stderr)
    print(f'String arena measurements: {measured}/5')
    print(f'String output fault injection: {injected}/5')
    print(f'PASS {len(cases)} native string/output programs and {len(bad)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
