#!/usr/bin/env python3
"""Native stdin: binary preservation, exact limits, EOF, errors and EINTR."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from bytes_differential import function, constant, binary
from run import TARGET

LIMIT=b'E_RUNTIME_INPUT: input exceeds byte limit\n'
IO=b'E_RUNTIME_IO: input read failed\n'


def program(limit,version=10):
    # Version 11, which builds the compiler, reads up to 16 MiB; its arena is explicit.
    return {'version':version,**({'arena_bytes':40<<20} if version==11 else {}),'functions':[function('main',[],[
        {'op':'bytes.read','dest':'b','limit':limit},
        {'op':'call','dest':'saved','callee':'identity','args':['b']},
        {'op':'bytes.read','dest':'eof','limit':0},
        {'op':'bytes.write','dest':'w','value':'saved','stream':'stdout'},
        {'op':'bytes.len','dest':'n','value':'eof'},
    ],'n'),dict(function('identity',[('v','bytes')],[],'v'),return_type='bytes')]}


def build(compiler,root,p,index):
    path=root/'input.json';path.write_text(json.dumps(p));output=root/f'input-{index}'
    result=subprocess.run([str(compiler),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
    assert result.returncode==0,result.stderr
    return output


def verify(compilers):
    injected=0;cases=0
    with tempfile.TemporaryDirectory(prefix='alchem-input-') as directory:
        root=Path(directory)
        for limit,data in [(0,b''),(0,b'x'),(128,b''),(128,b'6*7\n'),(128,bytes(range(128))),(128,b'x'*129),(256,bytes(range(256))),(1048576,bytes(range(256))*4096),(1048576,b'x'*1048577),(4194303,bytes(range(256))*16383+bytes(range(255))),(4194303,b'x'*4194304),(4194304,bytes(range(256))*16384),(4194304,b'x'*4194305),(16776191,bytes(range(256))*65531+bytes(range(255))),(16776191,b'x'*16776192),(16777216,bytes(range(256))*65536),(16777216,b'x'*16777217)]:
            images=[]
            for index,compiler in enumerate(compilers):
                output=build(compiler,root,program(limit,11 if limit>1048576 else 10),index)
                result=subprocess.run([str(output)],input=data,capture_output=True,timeout=120,env=dict(os.environ,PATH=''))
                expected=(65,b'',LIMIT) if len(data)>limit else (0,data,b'')
                assert (result.returncode,result.stdout,result.stderr)==expected,(limit,len(data),index,result.returncode,result.stderr)
                images.append(output.read_bytes())
            assert images[0]==images[1],'backend image mismatch'
            cases+=1
        # Full-capacity reservations, not only the actual EOF length, are charged.
        for count,expected in [(4,0),(5,71)]:
            ops=[{'op':'bytes.read','dest':f'b{i}','limit':1048567} for i in range(count)]+[constant('zero',0)]
            p={'version':10,'functions':[function('main',[],ops,'zero')]}
            for index,compiler in enumerate(compilers):
                output=build(compiler,root,p,index)
                result=subprocess.run([str(output)],input=b'',capture_output=True,timeout=120)
                diagnostic=b'E_RUNTIME_ALLOC: byte allocation failed or limit exceeded\n' if expected else b''
                assert (result.returncode,result.stdout,result.stderr)==(expected,b'',diagnostic),result
        # All six incoming parameters survive reading, allocating and writing.
        helper=program(256)['functions'][0]
        helper['name']='read_and_emit'
        helper['params']=[{'name':f'p{i}','type':'i64'} for i in range(6)]
        ops=helper['blocks'][0]['instructions']
        ops += [binary('add.i64','s0','p0','p1'),binary('sub.i64','s1','s0','p2'),binary('add.i64','s2','s1','p3'),binary('sub.i64','s3','s2','p4'),binary('add.i64','s4','s3','p5')]
        helper['blocks'][0]['terminator']['value']='s4'
        ops=[constant(f'a{i}',i+1) for i in range(6)]+[{'op':'call','dest':'result','callee':'read_and_emit','args':[f'a{i}' for i in range(6)]}]
        p={'version':10,'functions':[function('main',[],ops,'result'),helper,program(1)['functions'][1]]}
        for index,compiler in enumerate(compilers):
            output=build(compiler,root,p,index)
            result=subprocess.run([str(output)],input=bytes(range(256)),capture_output=True,timeout=120)
            assert (result.returncode,result.stdout,result.stderr)==(5,bytes(range(256)),b''),result
        for index,compiler in enumerate(compilers):
            output=build(compiler,root,program(128),index)
            result=subprocess.run([str(output)],capture_output=True,preexec_fn=lambda:os.close(0),timeout=120)
            assert (result.returncode,result.stdout,result.stderr)==(74,b'',IO),result
            # Feed in separate writes to require accumulation across short reads.
            with subprocess.Popen([str(output)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as child:
                child.stdin.write(b'6*');child.stdin.flush()
                child.stdin.write(b'7\n');child.stdin.close();child.stdin=None
                out,err=child.communicate(timeout=120)
                assert (child.returncode,out,err)==(0,b'6*7\n',b'')
            tracer=shutil.which('strace')
            if tracer:
                result=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e','inject=read:error=EINTR:when=1',str(output)],input=b'6*7',capture_output=True,timeout=120)
                if b'ptrace' in result.stderr and b'Operation not permitted' in result.stderr:print('SKIP input EINTR: ptrace unavailable')
                else:
                    assert (result.returncode,result.stdout,result.stderr)==(0,b'6*7',b''),result
                    injected+=1
            invalid=[program(value) for value in [-1,1048577,4194304,None,True,1.5,'128']]+[program(value,11) for value in [-1,16777217,None]]
            missing=program(128);del missing['functions'][0]['blocks'][0]['instructions'][0]['limit'];invalid.append(missing)
            extra=program(128);extra['functions'][0]['blocks'][0]['instructions'][0]['stream']='stdin';invalid.append(extra)
            old=program(128);old['version']=9;invalid.append(old)
            for p in invalid:
                path=root/'invalid.json';path.write_text(json.dumps(p));output.write_bytes(b'preserve')
                result=subprocess.run([str(compiler),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
                assert result.returncode!=0 and output.read_bytes()==b'preserve',(p,result)
    print(f'PASS {cases} bounded-input cases per backend plus arena reservation, six-register helper, closed-fd, short-read and invalid-IR preservation')
    print(f'Input EINTR injection: {injected}/{len(compilers)} backends')


if __name__=='__main__':verify([Path(p).resolve() for p in sys.argv[1:]])
