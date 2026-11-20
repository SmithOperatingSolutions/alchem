#!/usr/bin/env python3
"""Check immutable allocation, byte returns and recursive references independently."""
import argparse
import json
from pathlib import Path
import random
import subprocess
import tempfile
from bytes_differential import function,constant,binary
from run import TARGET


def byte_function(name,params,ops,result):
    f=function(name,params,ops,result);f['return_type']='bytes';return f


def verify(compilers,count=64):
    rng=random.Random(0xC0A57)
    with tempfile.TemporaryDirectory(prefix='alchem-construct-') as directory:
        root=Path(directory)
        for case in range(count):
            seed=bytes(rng.randrange(256) for _ in range(rng.randrange(40)))
            suffix=bytes(rng.randrange(256) for _ in range(rng.randrange(24)))
            more=bytes(rng.randrange(256) for _ in range(rng.randrange(24)))
            depth=[0,1,8][case] if case<3 else rng.randrange(9)
            tag=rng.choice([-(1<<63),(1<<63)-1,-1,0,1])
            def oracle(value,n,tag):
                if n<=0:return value
                child=oracle(value+suffix,n-1,tag)
                return child+more if tag<0 else more+child
            expected=oracle(seed,depth,tag)+oracle(seed,depth,-tag if tag!=-(1<<63) else 1)+seed+suffix+more
            yes={'instructions':[],'value':'seed'}
            no={'instructions':[
                {'op':'bytes.concat','dest':'next','lhs':'seed','rhs':'suffix'},constant('one',1),binary('sub.i64','n1','n','one'),
                {'op':'call','dest':'child','callee':'build','args':['next','suffix','n1','more','tag','zero']},
                binary('lt.i64','negative','tag','zero'),
                {'op':'if.bytes','dest':'after','cond':'negative','then':{'instructions':[{'op':'bytes.concat','dest':'left','lhs':'child','rhs':'more'}],'value':'left'},'else':{'instructions':[{'op':'bytes.concat','dest':'right','lhs':'more','rhs':'child'}],'value':'right'}},
            ],'value':'after'}
            helper=byte_function('build',[('seed','bytes'),('suffix','bytes'),('n','i64'),('more','bytes'),('tag','i64'),('zero','i64')],[binary('le.i64','done','n','zero'),{'op':'if.bytes','dest':'r','cond':'done','then':yes,'else':no}],'r')
            ops=[{'op':'bytes.const','dest':'seed','values':list(seed)},{'op':'bytes.const','dest':'suffix','values':list(suffix)},{'op':'bytes.const','dest':'more','values':list(more)},constant('n',depth),constant('tag',tag),constant('other_tag',-tag if tag!=-(1<<63) else 1),constant('zero',0),
                {'op':'call','dest':'first','callee':'build','args':['seed','suffix','n','more','tag','zero']},
                {'op':'call','dest':'second','callee':'build','args':['seed','suffix','n','more','other_tag','zero']},
                {'op':'bytes.concat','dest':'joined','lhs':'first','rhs':'second'},
            ]
            previous='joined'
            for i,name in enumerate(['seed','suffix','more']):
                dest=f'kept{i}';ops.append({'op':'bytes.concat','dest':dest,'lhs':previous,'rhs':name});previous=dest
            ops += [{'op':'bytes.write','dest':'written','value':previous,'stream':'stdout'},{'op':'bytes.len','dest':'size','value':previous},binary('eq.i64','ok','written','size'),{'op':'if.i64','dest':'result','cond':'ok','then':{'instructions':[constant('yes',0)],'value':'yes'},'else':{'instructions':[constant('no',1)],'value':'no'}}]
            functions=[function('main',[],ops,'result'),helper];rng.shuffle(functions)
            path=root/'program.json';path.write_text(json.dumps({'version':8,'functions':functions}));binaries=[]
            for i,compiler in enumerate(compilers):
                output=root/f'program-{i}'
                result=subprocess.run([str(compiler),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
                assert result.returncode==0,(case,result.stderr)
                result=subprocess.run([str(output)],capture_output=True,timeout=120)
                assert (result.returncode,result.stdout,result.stderr)==(0,expected,b''),(case,i,'allocation/return/immutability mismatch')
                binaries.append(output.read_bytes())
            assert binaries[0]==binaries[1],case
    print(f'PASS {count} construction differential programs: byte returns, six arguments, recursion, branches and immutable live references')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('go',type=Path);parser.add_argument('rust',type=Path)
    args=parser.parse_args();verify([args.go.resolve(),args.rust.resolve()])
