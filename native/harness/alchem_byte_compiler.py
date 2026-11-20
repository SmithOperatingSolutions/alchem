#!/usr/bin/env python3
"""Typed byte source programs compiled entirely by the saved Alchem compiler."""
import base64
from pathlib import Path
from source_syntax import native_bytes
import random
import shutil
import subprocess
import sys
import tempfile
from native_memory import floor_arena
from run import ROOT,TARGET


def module(helpers,body):return f'defmodule M do {helpers} def main() do {body} end end'


def verify(frontend,backends,saved_compilers=None):
    factory='def make(x: integer): list[integer] do [x,0,255] end '
    inspect='def inspect(b: list[integer]): integer do Enum.at(b,0,-1) end '
    valid=[
        (module(factory+inspect,'System.halt(inspect(make(42)))'),42),
        (module('def empty(): list[integer] do [] end ','b=empty()\n System.halt(Enum.count(b)+42)'),42),
        (module('','a=[40]\n b=Enum.concat(a,[2])\n System.halt(Enum.at(a,0,0)+Enum.at(b,-1,0))'),42),
        (module('def pick(x: integer,b: list[integer]): list[integer] do if x < 0 do b else [7] end end ','a=pick(-1,[42])\n System.halt(Enum.at(a,0,0))'),42),
        (module('def f(b: list[integer]): list[integer] do g(b) end def g(b: list[integer]): list[integer] do Enum.concat(b,[]) end ','System.halt(Enum.at(f([42]),0,0))'),42),
        (module('def f(b: list[integer],n: integer): list[integer] do if n == 0 do b else f(Enum.concat(b,[1]),n-1) end end ','System.halt(Enum.count(f([],42)))'),42),
        (module('def f(a: list[integer],b: integer,c: list[integer],d: integer,e: list[integer],f: integer): integer do Enum.at(a,0,0)+b+Enum.at(c,0,0)+d+Enum.at(e,0,0)+f end ','System.halt(f([10],10,[10],10,[1],1))'),42),
        (module('','a=[1,2]\n System.halt(Enum.at(a,-3,42))'),42),
        (module('','a=[1,2]\n System.halt(Enum.at(a,9223372036854775807,42))'),42),
        (module('','a=[1,2]\n System.halt(Enum.at(a,-9223372036854775808,42))'),42),
    ]
    valid += [
        (module('','b=['+','.join(str(i) for i in range(32))+']\n System.halt(Enum.count(b)+10)'),42),
        (module('def f(a: list[integer],b: integer,c: list[integer],d: integer,e: list[integer],f: integer): list[integer] do if b < d do Enum.concat(a,e) else c end end ','a=f([10],0,[1],1,[32],2)\n System.halt(Enum.at(a,0,0)+Enum.at(a,-1,0))'),42),
    ]
    valid += [
        (module('def f(x: integer): list[integer] do if x == 0 do [42] else [256] end end ','System.halt(Enum.at(f(0),0,0))'),42),
    ]
    valid += [
        (module('','b=Enum.slice([10,20,40,1],-2,5)\n System.halt(Enum.count(b)+Enum.at(b,0,0))'),42),
        (module('','a=[40,2]\n b=Enum.slice(a,0,1)\n System.halt(Enum.at(b,0,0)+Enum.at(a,-1,0))'),42),
        (module('','b=Enum.slice([1,42],1,9223372036854775807)\n System.halt(Enum.at(b,0,0))'),42),
        (module('','b=Enum.slice([1],-9223372036854775808,9223372036854775807)\n System.halt(Enum.count(b)+42)'),42),
    ]
    rng=random.Random(1718)
    for _ in range(32):
        values=[rng.randrange(256) for _ in range(rng.randrange(1,12))];idx=rng.randrange(-len(values),len(values))
        valid.append((module(factory+inspect,f'a={values}\n b=Enum.concat(a,make(7))\n System.halt(Enum.at(b,{idx},0))'),(values+[7,0,255])[idx]))
    invalid=[
        module(factory,'System.halt(Enum.count(make([1])))'),
        module('def f(b: list[integer]): integer do b end ','System.halt(0)'),
        module('def f(): list[integer] do 1 end ','System.halt(0)'),
        module('','System.halt([1])'),
        module('','System.halt(Enum.count(42))'),
        module('','System.halt(Enum.at([1],[0],0))'),
        module('','System.halt(Enum.at([1],0,[]))'),
        module('','b=Enum.concat([1],2)\n System.halt(0)'),
        module('','b=[[1]]\n System.halt(0)'),
        module('','System.halt([1]+[2])'),
        module('','System.halt(-[1])'),
        module('','b=if 1 == 1 do [1] else 2 end\n System.halt(0)'),
        module('','System.halt(if [1] == [1] do 1 else 0 end)'),
        module('','b=[1|[]]\n System.halt(0)'),
        module('','b=['+','.join('1' for _ in range(129))+']\n System.halt(0)'),
    ]
    invalid += [module('',body) for body in [
        'System.halt(Enum.count())','System.halt(Enum.count([1],2))',
        'System.halt(Enum.at([1],0))','b=Enum.concat([1])\n System.halt(0)',
        'b=Enum.map([1])\n System.halt(0)','b=[true]\n System.halt(0)',
        'b=if 1 == 1 do x=[1]\n x else [2] end\n System.halt(Enum.count(x))',
    ]]
    errors=[(module('','a=[256]\n System.halt(0)'),72),(module('','a=[-1]\n System.halt(0)'),72)]
    invalid += [module('',body) for body in [
        'b=Enum.slice(1,0,1)\n System.halt(0)',
        'b=Enum.slice([1],[],1)\n System.halt(0)',
        'b=Enum.slice([1],0,[])\n System.halt(0)',
    ]]
    errors.append((module('','b=Enum.slice([1],0,-1)\n System.halt(0)'),73))
    errors += [(module(factory,'b=make('+str(value)+')\n System.halt(0)'),72) for value in [-(1<<63),(1<<63)-1]]
    fill='def fill(n: integer): integer do if n == 0 do b=[1]\n 0 else fill(n-1)+fill(n-1) end end '
    empty='def fill(n: integer): integer do if n == 0 do b=[]\n 0 else fill(n-1)+fill(n-1) end end '
    grow='def grow(n: integer): list[integer] do if n == 0 do [1] else a=grow(n-1)\n Enum.concat(a,a) end end '
    # 0+f(n-1): a call that is the function's whole value runs as a loop and never goes deep.
    recurse='def f(n: integer): integer do if n == 0 do 1 else 0+f(n-1) end end '
    budgets=[
        (module(fill,'System.halt(fill(18))'),0),
        # These two took one allocation more than the 4 MiB arena holds and
        # exited 71; nothing of what fill makes stays in use, so a program now
        # gives it back and runs to its end (spec/alchem-memory.md). grow, below,
        # keeps what it makes and still exhausts the arena.
        (module(fill,'x=fill(18)\n b=[]\n System.halt(x)'),0),
        (module(fill,'x=fill(18)\n b=[256]\n System.halt(x)'),72),
        (module(empty,'System.halt(fill(19))'),0),
        (module(empty,'x=fill(19)\n b=[]\n System.halt(x)'),0),
        (module(grow,'System.halt(Enum.count(grow(20))-1048534)'),42),
        # A concatenation may pass 1 MiB (the former cap); only the arena bounds it. The
        # fill and grow programs run held to the arena's 4 MiB floor (floor_arena).
        (module(grow,'a=Enum.concat(grow(20),[1])\n System.halt(Enum.count(a)-1048535)'),42),
        (module(grow,'a=grow(21)\n System.halt(0)'),71),
        # Calls nest 100000 deep, as in the pinned runtime; a call that never
        # returns is stopped there.
        (module(recurse,'b=[1,f(300)]\n System.halt(Enum.at([41],0,7)+f(99000))'),42),
        (module(recurse,'b=[-1,f(-1)]\n System.halt(0)'),2),
        (module(recurse,'System.halt(Enum.at([42],0,f(-1)))'),2),
    ]
    # b"..." holds bytes in base64 (nl_coded_value), as the library's packed
    # text is held; the seed adapter reads it as a list.
    long=base64.b64encode(bytes(range(256))+bytes(range(128))).decode()
    coded=[
        (module('def d(): bytes do b"AP8Q" end ','System.halt(Enum.at(d(),1,0)-213)'),42),
        (module('def d(): bytes do b"YQ==" end ','System.halt(Enum.at(d(),0,0)-55+Enum.count(d())-1)'),42),
        (module('def d(): bytes do b"YWI=" end ','System.halt(Enum.count(d())*21)'),42),
        (module('def d(): bytes do b"" end ','System.halt(42+Enum.count(d()))'),42),
        (module('def d(): bytes do Enum.concat(b"KiorKg==",b"//8=") end ','System.halt(Enum.at(d(),4,0)-213+Enum.count(d())-6)'),42),
        (module(f'def d(): bytes do b"{long}" end ','System.halt(Enum.count(d())-342+Enum.at(d(),383,0)-127)'),42),
    ]
    refused=[module(f'def d(): bytes do b"{text}" end ','System.halt(Enum.count(d()))') for text in ['YQ=','Y===','YQ==YQ==','Y*Q=','YQ=a','A'*4100]]
    injected=0
    with tempfile.TemporaryDirectory(prefix='alchem-byte-source-') as directory:
        root=Path(directory);compiler_images=[]
        for index,backend in enumerate(backends):
            compiler=root/f'compiler-{index}'
            if saved_compilers is None:
                built=subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap-alchem-compiler.py'),'--language','functions','--frontend',str(frontend),'--backend',str(backend),'--output',str(compiler)],capture_output=True,timeout=120)
                assert built.returncode==0,built.stderr
            else:compiler=saved_compilers[index]
            compiler_images.append(compiler.read_bytes())
            for source,expected in valid:
                result=subprocess.run([str(compiler)],input=native_bytes(source.encode()),capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==0 and not result.stderr,(source,result.returncode,result.stderr)
                target=root/'target';target.write_bytes(result.stdout);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
                assert (run.returncode,run.stdout,run.stderr)==(expected,b'',b''),(source,run)
                repeat=subprocess.run([str(compiler)],input=native_bytes(source.encode()),capture_output=True,env={'PATH':''},timeout=120)
                assert repeat.stdout==result.stdout,'nondeterministic output'
                if index==0:
                    path=root/'reference.alc';path.write_text(source)
                    lowered=subprocess.run([str(frontend),'--input',str(path),'--program'],capture_output=True,timeout=120)
                    assert lowered.returncode==0,(source,lowered.stderr)
                    ir=root/'reference.json';ir.write_bytes(lowered.stdout)
                    built=subprocess.run([str(backend),'--target',TARGET,'--input',str(ir),'--output',str(root/'reference')],capture_output=True,timeout=120)
                    assert built.returncode==0,built.stderr
                    run=subprocess.run([str(root/'reference')],capture_output=True,timeout=120)
                    assert run.returncode==expected,('upstream oracle',source,run)
            for source in invalid:
                result=subprocess.run([str(compiler)],input=native_bytes(source.encode()),capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==65 and not result.stdout and result.stderr,(source,result)
            for source,expected in coded:
                result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==0 and not result.stderr,(source[:120],result.returncode,result.stderr)
                target=root/'coded';target.write_bytes(result.stdout);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
                assert (run.returncode,run.stdout,run.stderr)==(expected,b'',b''),(source[:120],run)
                if index==0:
                    path=root/'coded.alc';path.write_text(source)
                    lowered=subprocess.run([str(frontend),'--input',str(path),'--program'],capture_output=True,timeout=120)
                    assert lowered.returncode==0,(source[:120],lowered.stderr)
                    ir=root/'coded.json';ir.write_bytes(lowered.stdout)
                    built=subprocess.run([str(backend),'--target',TARGET,'--input',str(ir),'--output',str(root/'coded-seed')],capture_output=True,timeout=120)
                    assert built.returncode==0,built.stderr
                    run=subprocess.run([str(root/'coded-seed')],capture_output=True,timeout=120)
                    assert run.returncode==expected,('seed adapter',source[:120],run)
            for source in refused:
                result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==65 and not result.stdout,(source[:120],result)
            for source,status in errors+budgets:
                result=subprocess.run([str(compiler)],input=native_bytes(source.encode()),capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==0,result
                target=root/'bad';target.write_bytes(result.stdout);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(target) if 'fill(' in source or 'grow(' in source else None)
                # Status 2: the runtime stopped a call nested past the depth limit.
                stopped=run.stderr.split(b'\n')[0].endswith(b': call depth exceeded') if status==2 else run.stderr==b''
                assert (run.returncode,run.stdout)==(status,b'') and stopped,(source,run.returncode,run.stderr[:200])
            source=module(factory+inspect,'System.halt(inspect(make(42)))')
            result=subprocess.run([str(compiler)],input=native_bytes(source.encode()),capture_output=True,env={'PATH':''},timeout=120)
            assert result.returncode==0,result
            target=root/'mmap-test';target.write_bytes(result.stdout);target.chmod(0o700)
            tracer=shutil.which('strace')
            if tracer:
                # The arena is asked for in halves from 16 GiB down to 4 MiB: refused every time
                # the program exits 71; refused once it runs in the next half.
                result=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e','inject=mmap:error=ENOMEM',str(target)],capture_output=True,timeout=120)
                if b'ptrace' in result.stderr and b'Operation not permitted' in result.stderr:print('SKIP generated byte mmap fault: ptrace unavailable')
                else:
                    assert (result.returncode,result.stdout,result.stderr)==(71,b'',b''),result
                    trace=(root/'trace').read_text()
                    assert trace.count('mmap(')==13 and '17179873280' in trace and ', 4198400,' in trace and 'MAP_NORESERVE' in trace and 'PROT_EXEC' not in trace,trace
                    once=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e','inject=mmap:error=ENOMEM:when=1',str(target)],capture_output=True,timeout=120)
                    plain=subprocess.run([str(target)],capture_output=True,timeout=120)
                    assert (once.returncode,once.stdout,once.stderr)==(plain.returncode,plain.stdout,plain.stderr) and plain.returncode!=71,(once,plain)
                    assert ', 8589938688,' in (root/'trace').read_text()
                    injected+=1
        assert compiler_images[0]==compiler_images[1],'Go/Rust bootstrap differs'
    print(f'PASS Alchem-written byte source compiler: {len(valid)} programs, {len(invalid)} type/profile rejections, {len(coded)} base64 literals and {len(refused)} refused, {len(errors)} byte errors, {len(budgets)} arena/evaluation-order programs per backend')

    print(f'Generated-program mmap ENOMEM injection: {injected}/{len(backends)} backends')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve(),[Path(p).resolve() for p in sys.argv[2:]])
