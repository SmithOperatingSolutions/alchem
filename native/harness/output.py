#!/usr/bin/env python3
"""Exercise native binary output, syscall clobbers, short writes and errors."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import tempfile
from bytes_differential import function,constant,binary
from run import TARGET

MESSAGE=b'E_RUNTIME_IO: output write failed\n'


def program(data,stream='stdout'):
    return {'version':7,'functions':[function('main',[],[
        {'op':'bytes.const','dest':'b','values':list(data)},
        {'op':'bytes.write','dest':'count','value':'b','stream':stream},
        {'op':'bytes.len','dest':'size','value':'b'},binary('eq.i64','ok','count','size'),
        {'op':'if.i64','dest':'r','cond':'ok','then':{'instructions':[constant('yes',0)],'value':'yes'},'else':{'instructions':[constant('no',1)],'value':'no'}},
    ],'r')]}


def verify(compilers,count=64):
    rng=random.Random(0x017A7)
    with tempfile.TemporaryDirectory(prefix='alchem-output-') as directory:
        root=Path(directory)
        for case in range(count):
            data=bytes(range(256))*4096 if case==0 else bytes(range(256)) if case==1 else bytes(rng.randrange(256) for _ in range(rng.randrange(4096)))
            stream=rng.choice(['stdout','stderr'])
            p=program(data,stream)
            # A six-register helper must preserve every argument across syscall.
            values=[rng.randrange(-(1<<63),(1<<63)) for _ in range(5)]
            helper=function('emit',[('b','bytes')]+[(f'p{i}','i64') for i in range(5)],p['functions'][0]['blocks'][0]['instructions'][1:-1]+[
                binary('sub.i64','x0','p0','p1'),binary('add.i64','x1','x0','p2'),binary('sub.i64','x2','x1','p3'),binary('add.i64','answer','x2','p4'),
                {'op':'if.i64','dest':'r','cond':'ok','then':{'instructions':[],'value':'answer'},'else':{'instructions':[constant('one',1),binary('add.i64','bad','answer','one')],'value':'bad'}},
            ],'r')
            expected=(values[0]-values[1]+values[2]-values[3]+values[4])&((1<<64)-1)
            if expected>=1<<63:expected-=1<<64
            ops=[p['functions'][0]['blocks'][0]['instructions'][0]]+[constant(f'a{i}',v) for i,v in enumerate(values)]+[
                {'op':'call','dest':'result','callee':'emit','args':['b']+[f'a{i}' for i in range(5)]},constant('expected',expected),binary('eq.i64','ok','result','expected'),
                {'op':'if.i64','dest':'r','cond':'ok','then':{'instructions':[constant('yes',0)],'value':'yes'},'else':{'instructions':[constant('no',1)],'value':'no'}},
            ]
            p={'version':7,'functions':[function('main',[],ops,'r'),helper]}
            path=root/'program.json';path.write_text(json.dumps(p));binaries=[]
            for index,compiler in enumerate(compilers):
                output=root/f'program-{index}'
                compiled=subprocess.run([str(compiler),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
                assert compiled.returncode==0,(case,compiled.stderr)
                executed=subprocess.run([str(output)],capture_output=True,timeout=120)
                assert (executed.returncode,executed.stdout,executed.stderr)==(0,data if stream=='stdout' else b'',data if stream=='stderr' else b''),(case,index,'binary output/count/live values differ')
                binaries.append(output.read_bytes())
            assert binaries[0]==binaries[1],case
        data=bytes(range(256))*4096
        path=root/'program.json';path.write_text(json.dumps(program(data)))
        injected=0
        for index,compiler in enumerate(compilers):
            output=root/f'errors-{index}'
            result=subprocess.run([str(compiler),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
            assert result.returncode==0,result.stderr
            result=subprocess.run([str(output)],capture_output=True,preexec_fn=lambda:os.close(1),timeout=120)
            assert (result.returncode,result.stdout,result.stderr)==(74,b'',MESSAGE),result
            with open('/dev/full','wb') as full:
                result=subprocess.run([str(output)],stdout=full,stderr=subprocess.PIPE,timeout=120)
                assert (result.returncode,result.stderr)==(74,MESSAGE),result
            # Fill a nonblocking pipe before reading. The first write is short;
            # retry must detect EAGAIN rather than claim full success or hang.
            read_fd,write_fd=os.pipe()
            try:
                fcntl.fcntl(write_fd,fcntl.F_SETFL,os.O_NONBLOCK)
                child=subprocess.Popen([str(output)],stdout=write_fd,stderr=subprocess.PIPE)
                os.close(write_fd);write_fd=-1
                try:
                    _,diagnostic=child.communicate(timeout=120)
                except subprocess.TimeoutExpired:
                    child.kill();child.communicate()
                    raise
                received=b''
                while True:
                    chunk=os.read(read_fd,65536)
                    if not chunk:break
                    received+=chunk
                assert child.returncode==74 and diagnostic==MESSAGE,(child.returncode,diagnostic)
                assert 0<len(received)<len(data) and received==data[:len(received)],'short write progress corrupted data'
            finally:
                os.close(read_fd)
                if write_fd!=-1:os.close(write_fd)
            tracer=shutil.which('strace')
            if tracer:
                result=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e','inject=write:error=EINTR:when=1',str(output)],capture_output=True,timeout=120)
                if b'ptrace' in result.stderr and b'Operation not permitted' in result.stderr:
                    print('SKIP EINTR injection: ptrace unavailable in this execution sandbox')
                else:
                    assert (result.returncode,result.stdout,result.stderr)==(0,data,b''),('EINTR retry failed',result.returncode,result.stderr[:512])
                    injected+=1
    print(f'PASS {count} binary-output differential programs plus closed-fd, /dev/full and forced-short-write checks per backend')
    print(f'EINTR fault injection: {injected}/{len(compilers)} backends (requires strace)')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('go',type=Path);parser.add_argument('rust',type=Path)
    args=parser.parse_args();verify([args.go.resolve(),args.rust.resolve()])
