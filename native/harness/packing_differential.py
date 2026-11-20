#!/usr/bin/env python3
"""Compare checked packing, argument order and byte-result lifetime independently."""
import argparse
import json
from pathlib import Path
import random
import subprocess
import tempfile
from bytes_differential import function,constant,binary
from construction_differential import byte_function
from run import TARGET

MESSAGE=b'E_RUNTIME_BYTE: expected byte value 0..255\n'


def verify(compilers,count=64):
    rng=random.Random(0xBA0C)
    with tempfile.TemporaryDirectory(prefix='alchem-pack-') as directory:
        root=Path(directory)
        for case in range(count):
            a=[rng.randrange(128),rng.randrange(128)]+[rng.randrange(256) for _ in range(4)]
            b=[rng.randrange(128),rng.randrange(128)]+[rng.randrange(256) for _ in range(4)]
            invalid=case%4==3
            if invalid:a[rng.randrange(6)]=rng.choice([-1,256,-(1<<63),(1<<63)-1])
            order=[5,0,4,1,3,2]
            def packet(values):return bytes([values[i] for i in order]+[values[0]+values[1]])
            helper=byte_function('pack',[(f'p{i}','i64') for i in range(6)],[binary('add.i64','sum','p0','p1'),{'op':'bytes.pack','dest':'r','args':[f'p{i}' for i in order]+['sum']}],'r')
            ops=[constant(f'a{i}',v) for i,v in enumerate(a)]+[constant(f'b{i}',v) for i,v in enumerate(b)]+[
                {'op':'call','dest':'first','callee':'pack','args':[f'a{i}' for i in range(6)]},
                {'op':'call','dest':'second','callee':'pack','args':[f'b{i}' for i in range(6)]},
                {'op':'bytes.concat','dest':'joined','lhs':'first','rhs':'second'},
                {'op':'bytes.pack','dest':'extra','args':['b0','b5','b0']},
                {'op':'bytes.concat','dest':'all','lhs':'joined','rhs':'extra'},
                {'op':'bytes.write','dest':'count','value':'all','stream':'stdout'},constant('r',0),
            ]
            functions=[function('main',[],ops,'r'),helper];rng.shuffle(functions)
            path=root/'program.json';path.write_text(json.dumps({'version':9,'functions':functions}));binaries=[]
            for i,compiler in enumerate(compilers):
                output=root/f'program-{i}'
                result=subprocess.run([str(compiler),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
                assert result.returncode==0,(case,result.stderr)
                result=subprocess.run([str(output)],capture_output=True,timeout=120)
                expected=(72,b'',MESSAGE) if invalid else (0,packet(a)+packet(b)+bytes([b[0],b[5],b[0]]),b'')
                assert (result.returncode,result.stdout,result.stderr)==expected,(case,i,'packing/order/lifetime mismatch')
                binaries.append(output.read_bytes())
            assert binaries[0]==binaries[1],case
    print(f'PASS {count} packing differential programs: computed values, six arguments, order, aliases, full-width range errors and byte returns')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('go',type=Path);parser.add_argument('rust',type=Path)
    args=parser.parse_args();verify([args.go.resolve(),args.rust.resolve()])
