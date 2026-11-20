#!/usr/bin/env python3
"""Verify pack operand/code bounds and validation-before-allocation semantics."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from bytes_differential import function,constant
from construction_differential import byte_function
from run import TARGET

ALLOC=b'E_RUNTIME_ALLOC: byte allocation failed or limit exceeded\n'
BYTE=b'E_RUNTIME_BYTE: expected byte value 0..255\n'


def verify(compilers):
    cases=[]
    for size,error in [(4096,False),(4097,True)]:
        ops=[constant('x',42),{'op':'bytes.pack','dest':'b','args':['x']*size},{'op':'bytes.len','dest':'size','value':'b'},constant('expected',size),{'op':'eq.i64','dest':'ok','lhs':'size','rhs':'expected'},{'op':'if.i64','dest':'r','cond':'ok','then':{'instructions':[constant('yes',0)],'value':'yes'},'else':{'instructions':[constant('no',1)],'value':'no'}}]
        cases.append((f'operands-{size}',[function('main',[],ops,'r')],error,0,b''))
    cases.append(('empty',[function('main',[],[{'op':'bytes.pack','dest':'b','args':[]},{'op':'bytes.len','dest':'r','value':'b'}],'r')],False,0,b''))
    for extra in ['none','valid','invalid']:
        functions=[byte_function(f'f{i}',[],[{'op':'call','dest':'discard','callee':f'f{i+1}','args':[]},{'op':'call','dest':'r','callee':f'f{i+1}','args':[]}],'r') for i in range(18)]
        functions.append(byte_function('f18',[],[constant('x',42),{'op':'bytes.pack','dest':'r','args':['x']}],'r'))
        ops=[{'op':'call','dest':'b','callee':'f0','args':[]}]
        if extra=='valid':ops.append({'op':'bytes.pack','dest':'extra','args':[]})
        if extra=='invalid':ops += [constant('bad',256),{'op':'bytes.pack','dest':'extra','args':['bad']}]
        ops += [constant('i',0),constant('fallback',7),{'op':'bytes.get','dest':'r','buffer':'b','index':'i','default':'fallback'}]
        result=42 if extra=='none' else 71 if extra=='valid' else 72
        cases.append(('arena-'+extra,[function('main',[],ops,'r')]+functions,False,result,b'' if extra=='none' else ALLOC if extra=='valid' else BYTE))
    with tempfile.TemporaryDirectory(prefix='alchem-pack-limits-') as directory:
        root=Path(directory)
        for name,functions,compile_error,status,diagnostic in cases:
            source=root/'program.json';source.write_text(json.dumps({'version':9,'functions':functions}));binaries=[]
            for i,compiler in enumerate(compilers):
                output=root/f'program-{i}';output.write_bytes(b'existing output')
                result=subprocess.run([str(compiler),'--target',TARGET,'--input',str(source),'--output',str(output)],capture_output=True,timeout=120)
                if compile_error:
                    assert result.returncode!=0 and b'E_UNSUPPORTED' in result.stderr,(name,result)
                    assert output.read_bytes()==b'existing output',name
                else:
                    assert result.returncode==0,(name,result.stderr)
                    result=subprocess.run([str(output)],capture_output=True,timeout=120)
                    assert (result.returncode,result.stdout,result.stderr)==(status,b'',diagnostic),(name,i,result)
                    binaries.append(output.read_bytes())
            if not compile_error:assert binaries[0]==binaries[1],name
    print('PASS 6 pack-limit programs: 4096/4097 operands, empty allocation, exact arena charging and byte-error precedence at exhaustion')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('go',type=Path);parser.add_argument('rust',type=Path)
    args=parser.parse_args();verify([args.go.resolve(),args.rust.resolve()])
