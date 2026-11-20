#!/usr/bin/env python3
"""Check V6 full-width process statuses and unrestricted helper arithmetic."""
import argparse
import json
from pathlib import Path
import random
import subprocess
import tempfile
from bytes_differential import function,constant,binary
from run import TARGET

MESSAGE=b'E_HALT_STATUS: expected status 0..255\n'


def verify(compilers,count=64):
    rng=random.Random(0x57A705)
    mask=(1<<64)-1
    def signed(value):
        value &= mask
        return value-(1<<64) if value>=1<<63 else value
    with tempfile.TemporaryDirectory(prefix='alchem-status-') as directory:
        root=Path(directory)
        for case in range(count):
            value=[-(1<<63),-1,0,1,70,255,256,(1<<63)-1][case] if case<8 else rng.randrange(-(1<<63),1<<63)
            # A wide helper result may be transformed into a valid status in
            # main, or used as a default from checked indexing. Only the final
            # returned status is restricted.
            helper=function('wide',[('x','i64')],[constant('one',1),binary('mul.i64','r','x','one')],'r')
            ops=[constant('x',value),{'op':'call','dest':'wide','callee':'wide','args':['x']}]
            expected=value
            if case%4==0 and case>=8:
                ops += [constant('same',value),binary('sub.i64','zero','wide','same'),constant('answer',42),binary('add.i64','r','zero','answer')]
                expected=42
            elif case%4==1 and case>=8:
                data=[rng.randrange(256) for _ in range(rng.randrange(8))]
                index=rng.randrange(-10,10)
                ops += [{'op':'bytes.const','dest':'b','values':data},constant('index',index),{'op':'bytes.get','dest':'r','buffer':'b','index':'index','default':'wide'}]
                normalized=index+len(data) if index<0 else index
                expected=data[normalized] if 0<=normalized<len(data) else value
            else:
                bias=rng.randrange(-300,300) if case>=8 else 0
                ops += [constant('bias',bias),binary('add.i64','r','wide','bias')]
                expected=signed(value+bias)
            functions=[function('main',[],ops,'r'),helper];rng.shuffle(functions)
            path=root/'program.json';path.write_text(json.dumps({'version':6,'functions':functions}))
            binaries=[]
            for index,compiler in enumerate(compilers):
                output=root/f'program-{index}'
                result=subprocess.run([str(compiler),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
                assert result.returncode==0,(case,result.stderr)
                result=subprocess.run([str(output)],capture_output=True,timeout=120)
                valid=0<=expected<=255
                assert (result.returncode,result.stdout,result.stderr)==(expected if valid else 70,b'',b'' if valid else MESSAGE),(case,index,expected,result)
                binaries.append(output.read_bytes())
            assert binaries[0]==binaries[1],case
    print(f'PASS {count} checked-status differential programs: full i64, wide helpers and byte/default paths')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('go',type=Path);parser.add_argument('rust',type=Path)
    args=parser.parse_args();verify([args.go.resolve(),args.rust.resolve()])
