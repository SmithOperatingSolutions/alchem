#!/usr/bin/env python3
"""Native library outputs checked against independent numeric/byte oracles."""
from pathlib import Path
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time


def base_string(value,base):
    if value==0:return '0'
    negative=value<0;value=abs(value);out=''
    while value:value,digit=divmod(value,base);out='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'[digit]+out
    return ('-' if negative else '')+out


def verify(compiler):
    rng=random.Random(171126)
    values=[0,42,-42,-(1<<63),(1<<63)-1]+[rng.randrange(-(1<<63),(1<<63)) for _ in range(12)]
    cases=[]
    for value in values:
        for base in [2,8,10,16,36]:cases.append(('',f'IO.write(Integer.to_string({value},{base}))\nSystem.halt(0)',base_string(value,base).encode(),0))
        for base in [2,10,36,(1<<63)-1]:
            digits=[int(c,36) for c in base_string(abs(value),base)] if base<=36 else ([0] if value==0 else [])
            if base>36:
                number=abs(value)
                while number:number,digit=divmod(number,base);digits.insert(0,digit)
            if value<0:digits=[-x for x in digits]
            helper='def text(n: integer): string do Integer.to_string(n) end '
            body=f'IO.write(Enum.join(Enum.map(Integer.digits({value},{base}),&text),","))\nSystem.halt(0)'
            cases.append((helper,body,','.join(map(str,digits)).encode(),0))
        digits=[int(c) for c in str(abs(value))]
        cases.append(('',f'IO.write(Integer.to_string(Integer.undigits(['+','.join(map(str,digits))+'])))\nSystem.halt(0)',b'<stdin>:1:57: integer overflow\n  at M.main (<stdin>:1)\n' if value==-(1<<63) else str(abs(value)).encode(),2 if value==-(1<<63) else 0))
    cases += [
        ('', 'IO.write(String.duplicate("é中",3))\nSystem.halt(0)',('é中'*3).encode(),0),
        ('', 'IO.write(String.duplicate("",9223372036854775807))\nSystem.halt(0)',b'',0),
        ('', 'IO.write(String.duplicate("x",0))\nSystem.halt(0)',b'',0),
        ('', 'IO.write(Enum.join(["é","中","", "x"],"|"))\nSystem.halt(0)','é|中||x'.encode(),0),
        ('', 'IO.write(Enum.join(["a","b"]))\nSystem.halt(0)',b'ab',0),
        ('', 'empty: list[string] = []\nIO.write(Enum.join(empty,"|"))\nSystem.halt(0)',b'',0),
        ('def keep(n: integer): boolean do n > 100 end ', 'IO.write(Integer.to_string(Enum.sum(Enum.filter([-1,101,1000],&keep))))\nSystem.halt(0)',b'1101',0),
        ('def keep(s: string): boolean do byte_size(s) > 1 end ', 'IO.write(Enum.join(Enum.filter(["a","é","中"],&keep),","))\nSystem.halt(0)','é,中'.encode(),0),
        ('', 'IO.write("a\\x00b")\nIO.puts("end")\nSystem.stop(0)',b'a\0bend\n',0),
    ]
    # Failures of the library's machine code end the program at the call, as the pinned runtime ends it.
    errors=[('Integer.to_string(1,1)','base must be between 2 and 36'),('Integer.to_string(1,37)','base must be between 2 and 36'),('Integer.digits(1,0)','base must be at least 2'),('Integer.undigits([10])','digit out of range for the base'),('Integer.undigits([-1])','digit out of range for the base'),('Integer.undigits([1],1)','base must be at least 2'),('Integer.undigits([9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9,9])','integer overflow'),
            ('String.duplicate("x",-1)','duplicate needs a nonnegative count and a result under 1 GiB'),('String.duplicate("xx",536870913)','duplicate needs a nonnegative count and a result under 1 GiB')]
    cases += [('',f'value={expression}\nSystem.halt(0)',f'<stdin>:1:36: {reason}\n  at M.main (<stdin>:1)\n'.encode(),2) for expression,reason in errors]
    # A product past 64 bits is a panic of the pinned runtime, which names no place.
    cases += [('', 'value=String.duplicate("xx",9223372036854775807)\nSystem.halt(0)',b'<runtime>: panic: strings: Repeat output length overflow\n',2)]
    with tempfile.TemporaryDirectory(prefix='alchem-library-expansion-') as d:
        root=Path(d)
        def build(helpers,body):
            source=('defmodule M do '+helpers+'def main() do '+body+' end end').encode()
            r=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stderr)==(0,b''),(body,r.returncode,r.stderr)
            again=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
            assert (again.returncode,again.stdout,again.stderr)==(0,r.stdout,b''),'library determinism'
            output=root/'out';output.write_bytes(r.stdout);output.chmod(0o700);return output
        for helpers,body,expected,status in cases:
            out=build(helpers,body);r=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            if status==2:assert (r.returncode,r.stdout,r.stderr)==(2,b'',expected),(body,r.returncode,r.stdout,r.stderr,status,expected);continue
            if status:expected=b''
            assert (r.returncode,r.stdout,r.stderr)==(status,expected,b''),(body,r.returncode,r.stdout,r.stderr,status,expected)
        for api in ['system_time','os_time']:
            out=build('',f'IO.write(Integer.to_string(System.{api}()))\nSystem.halt(0)')
            before=time.time_ns();r=subprocess.run([str(out)],capture_output=True,env={'PATH':''});after=time.time_ns()
            assert r.returncode==0 and not r.stderr and before<=int(r.stdout)<=after,(api,r)
        out=build('','IO.write(System.pid())\nSystem.halt(0)')
        p=subprocess.Popen([str(out)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':''});data,errors=p.communicate(timeout=120)
        assert (p.returncode,data,errors)==(0,str(p.pid).encode(),b'')
        for body in ['v=Enum.filter([1],&bad)\nSystem.halt(0)','IO.write(Integer.to_string("x",10))\nSystem.halt(0)','IO.write(String.duplicate("x",true))\nSystem.halt(0)','System.halt(System.pid())','IO.write(System.pid(1))\nSystem.halt(0)']:
            source=('defmodule M do def bad(n: integer): integer do n end def main() do '+body+' end end').encode()
            r=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(body,r)
        out=build('','IO.write("hello")\nSystem.halt(42)')
        r=subprocess.run([str(out)],capture_output=True,preexec_fn=lambda:os.close(1),timeout=120)
        assert (r.returncode,r.stdout,r.stderr)==(74,b'',b'')
        with open('/dev/full','wb') as full:
            r=subprocess.run([str(out)],stdout=full,stderr=subprocess.PIPE,timeout=120)
            assert (r.returncode,r.stderr)==(74,b'')
        injected=0;tracer=shutil.which('strace')
        if tracer:
            for rule,expected in [('error=EINTR:when=1',(42,b'hello',b'')),('retval=0:when=1',(74,b'',b'')),('retval=2:when=1',(42,b'llo',b''))]:
                r=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e','inject=write:'+rule,str(out)],capture_output=True,timeout=120)
                if b'ptrace' in r.stderr and b'Operation not permitted' in r.stderr:print('SKIP IO.write injection: ptrace unavailable')
                else:
                    assert (r.returncode,r.stdout,r.stderr)==expected,(rule,r)
                    injected+=1
            out=build('','value=System.system_time()\nSystem.halt(0)')
            r=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e','inject=clock_gettime:error=EFAULT:when=1',str(out)],capture_output=True,timeout=120)
            if b'ptrace' in r.stderr and b'Operation not permitted' in r.stderr:print('SKIP clock injection: ptrace unavailable')
            else:
                assert (r.returncode,r.stdout,r.stderr)==(74,b'',b''),r
                injected+=1
        else:print('SKIP IO.write/clock injection: strace unavailable')
    print(f'Expanded library syscall injections: {injected}/4')
    print(f'PASS {len(cases)} expanded library programs, clock/PID checks and 6 rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
