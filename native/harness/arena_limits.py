#!/usr/bin/env python3
"""Check allocation bounds, charging and mmap failure on actual native output."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from bytes_differential import function,constant
from construction_differential import byte_function
from run import TARGET

MESSAGE=b'E_RUNTIME_ALLOC: byte allocation failed or limit exceeded\n'


def verify(compilers):
    maximum=1<<20
    def literal(name,size):return {'op':'bytes.const','dest':name,'values':[0]*(size-1)+[42] if size else []}
    def joined(dest,lhs='a',rhs='b'):return {'op':'bytes.concat','dest':dest,'lhs':lhs,'rhs':rhs}
    def main(ops,buffer):return function('main',[],ops+[constant('index',-1),constant('fallback',7),{'op':'bytes.get','dest':'r','buffer':buffer,'index':'index','default':'fallback'}],'r')
    cases=[]
    for name,a,b,repeats,fifth,error in [
        ('result-boundary',maximum,0,1,False,False),('result-overflow',maximum,1,1,False,True),
        ('arena-boundary',maximum-8,0,4,False,False),('arena-overflow',maximum-8,0,4,True,True),
    ]:
        ops=[literal('a',a),literal('b',b)]+[joined(f'r{i}') for i in range(repeats)]
        if fifth:ops += [joined('extra','b','b')]
        cases.append((name,[main(ops,f'r{repeats-1}')],error))
    # An untaken oversized construction must not consume arena space or fail.
    ops=[literal('a',maximum),literal('b',1),{'op':'const.bool','dest':'flag','value':False},
         {'op':'if.bytes','dest':'chosen','cond':'flag','then':{'instructions':[joined('bad')],'value':'bad'},'else':{'instructions':[],'value':'a'}}]
    cases.append(('untaken-overflow',[main(ops,'chosen')],False))
    for extra in [False,True]:
        # 2^18 leaf allocations, each align8(1+8)=16 bytes, exactly 4 MiB.
        functions=[]
        for i in range(18):
            functions.append(byte_function(f'f{i}',[],[{'op':'call','dest':'discard','callee':f'f{i+1}','args':[]},{'op':'call','dest':'r','callee':f'f{i+1}','args':[]}],'r'))
        functions.append(byte_function('f18',[],[literal('a',1),literal('b',0),joined('r')],'r'))
        ops=[{'op':'call','dest':'value','callee':'f0','args':[]}]
        if extra:ops += [literal('empty',0),joined('extra','empty','empty')]
        cases.append(('alignment-overflow' if extra else 'alignment-boundary',[main(ops,'value')]+functions,extra))
    with tempfile.TemporaryDirectory(prefix='alchem-arena-') as directory:
        root=Path(directory)
        for name,functions,error in cases:
            path=root/'program.json';path.write_text(json.dumps({'version':8,'functions':functions}));binaries=[]
            for i,compiler in enumerate(compilers):
                output=root/f'program-{i}'
                result=subprocess.run([str(compiler),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
                assert result.returncode==0,(name,result.stderr)
                result=subprocess.run([str(output)],capture_output=True,timeout=120)
                assert (result.returncode,result.stdout,result.stderr)==(71 if error else 42,b'',MESSAGE if error else b''),(name,i,result)
                binaries.append(output.read_bytes())
            assert binaries[0]==binaries[1],name
        tracer=shutil.which('strace');injected=0
        if tracer:
            path=root/'mapping.json';path.write_text(json.dumps({'version':8,'functions':[function('main',[],[constant('r',0)],'r')]}))
            for i,compiler in enumerate(compilers):
                output=root/f'mapping-{i}'
                result=subprocess.run([str(compiler),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
                assert result.returncode==0,result.stderr
                result=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e','inject=mmap:error=ENOMEM:when=1',str(output)],capture_output=True,timeout=120)
                if b'ptrace' in result.stderr and b'Operation not permitted' in result.stderr:print('SKIP mmap injection: ptrace unavailable')
                else:
                    assert (result.returncode,result.stdout,result.stderr)==(71,b'',MESSAGE),('mmap failure',result)
                    trace=(root/'trace').read_text()
                    assert 'PROT_READ|PROT_WRITE' in trace and 'PROT_EXEC' not in trace and 'MAP_PRIVATE|MAP_ANONYMOUS' in trace and '4194304' in trace,'arena mapping permissions/size differ'
                    injected+=1
    print('PASS 7 arena-budget programs: exact result/arena/alignment boundaries, exhaustion and discarded allocation charges')
    print(f'mmap failure injection: {injected}/{len(compilers)} backends (requires strace)')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('go',type=Path);parser.add_argument('rust',type=Path)
    args=parser.parse_args();verify([args.go.resolve(),args.rust.resolve()])
