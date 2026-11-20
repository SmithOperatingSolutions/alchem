#!/usr/bin/env python3
"""Check Alchem literal conversion against independent arbitrary-precision ints."""
import argparse
import os
from pathlib import Path
import random
import subprocess
import tempfile
from run import ROOT,TARGET
from lexer import token

MIN=-(1<<63)
MAX=(1<<63)-1


def decimal(data,start,stop,negative,fallback):
    if len(data)>128: return 3,fallback
    if negative not in (0,1) or not 0<=start<stop<=len(data): return 2,fallback
    value=0
    for digit in data[start:stop]:
        if not 48<=digit<=57: return 1,fallback
        value=value*10+digit-48
        if value>(1<<63 if negative else MAX): return 4,fallback
    return 0,-value if negative else value


def integer(data,cursor,negative,fallback):
    start,kind,stop,error=token(data,cursor)
    if error: return error,fallback
    if kind!=3: return 1,fallback
    return decimal(data,start,stop,negative,fallback)


def cases():
    fixed=['0','00','42','9223372036854775806','9223372036854775807','9223372036854775808','9223372036854775809','18446744073709551616','0'*128,'0'*127+'1','0'*109+'9223372036854775808','0'*129,'x','1x','999999999999999999999x','-42','+42','4 2','']
    for text in fixed:
        for negative in (0,1): yield 'decimal',list(text.encode()),0,len(text),negative,MIN
    for digit in range(10):
        text='922337203685477580'+str(digit)
        for negative in (0,1): yield 'decimal',list(text.encode()),0,len(text),negative,MAX
    for byte in range(256):
        yield 'decimal',[byte],0,1,0,42
    for start,stop in [(1,3),(0,4),(1,4),(-1,2),(0,0),(3,2),(0,5),(MIN,2),(MAX,2),(0,MIN),(0,MAX)]:
        yield 'decimal',list(b'x42y'),start,stop,0,7
    for negative in [MIN,MAX,-1,2]: yield 'decimal',[52,50],0,2,negative,7
    for data in [b'',b' 42 + 7',b'-42',b'+42',b' 9223372036854775808 ',b' 9223372036854775809 ',b'12abc',b'\x00',b'\xff',b' '*128,b'0'*129]:
        for negative in [0,1,2]: yield 'integer',list(data),0,0,negative,MIN
    for cursor in [MIN,-1,0,2,3,MAX]: yield 'integer',list(b' 42'),cursor,0,0,MAX
    rng=random.Random(0xDEC1A1)
    for _ in range(64):
        value=rng.randrange(MIN,MAX+1)
        text='0'*rng.randrange(6)+str(abs(value))
        yield 'decimal',list(text.encode()),0,len(text),int(value<0),42
        overflow=rng.randrange(1<<63,1<<68)
        text=str(overflow)
        yield 'decimal',list(text.encode()),0,len(text),rng.randrange(2),42


def verify(frontend,rust,go):
    original=(ROOT/'implementations/alchem/lexer.alc').read_text()
    prefix=original.split('  # Native smoke test;',1)[0]
    chunks=[];pending=[]
    for case in cases():
        if len(case[1])>64:
            if pending: chunks.append(pending);pending=[]
            chunks.append([case])
        else:
            pending.append(case)
            if len(pending)==4: chunks.append(pending);pending=[]
    if pending: chunks.append(pending)
    with tempfile.TemporaryDirectory(prefix='alchem-integers-') as directory:
        root=Path(directory)
        for number,group in enumerate(chunks):
            assertions=[]
            for mode,data,start,stop,negative,fallback in group:
                literal='['+','.join(map(str,data))+']'
                if mode=='decimal':
                    error,value=decimal(data,start,stop,negative,fallback)
                    args=f'{literal}, {start}, {stop}, {negative}'
                else:
                    error,value=integer(data,start,negative,fallback)
                    args=f'{literal}, {start}, {negative}'
                assertions += [f'match_kind({mode}_error({args}), {error})',f'match_kind({mode}_or({args}, {fallback}), {value})']
            source=prefix+'  def main() do\n checks = '+' * '.join(assertions)+'\n if checks == 1 do System.halt(0) else System.halt(1) end\n end\nend\n'
            # Give empty list arguments an expected type through the public
            # conversion function signatures; semantic analysis handles them.
            path=root/'source.alc';path.write_text(source)
            result=subprocess.run([str(frontend),'--input',str(path),'--program'],capture_output=True,timeout=120)
            assert result.returncode==0,(number,group,result.stderr)
            ir=root/'source.json';ir.write_bytes(result.stdout)
            binaries=[]
            for index,compiler in enumerate([rust,go]):
                output=root/f'program-{index}'
                compiled=subprocess.run([str(compiler),'--target',TARGET,'--input',str(ir),'--output',str(output)],env=dict(os.environ,PATH=''),capture_output=True,timeout=120)
                assert compiled.returncode==0,(number,compiled.stderr)
                assert output.stat().st_mode & 0o777==0o700
                executed=subprocess.run([str(output)],capture_output=True,timeout=120)
                assert (executed.returncode,executed.stdout,executed.stderr)==(0,b'',b''),(number,group,index,executed)
                binaries.append(output.read_bytes())
            assert binaries[0]==binaries[1],number
            repeated=root/'repeat'
            result=subprocess.run([str(rust),'--target',TARGET,'--input',str(ir),'--output',str(repeated)],capture_output=True,timeout=120)
            assert result.returncode==0 and repeated.read_bytes()==binaries[0],number
    print(f'PASS {len(chunks)} Alchem integer oracle programs / {sum(1 for _ in cases())} cases: full i64, overflow, spans, all bytes and token integration')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frontend',type=Path);parser.add_argument('rust',type=Path);parser.add_argument('go',type=Path)
    args=parser.parse_args();verify(args.frontend.resolve(),args.rust.resolve(),args.go.resolve())
