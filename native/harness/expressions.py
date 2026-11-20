#!/usr/bin/env python3
"""Compare the Alchem expression frontend to Python AST and arbitrary ints."""
import argparse
import ast
import os
from pathlib import Path
import random
import subprocess
import tempfile
from run import ROOT,TARGET

MIN=-(1<<63)
MAX=(1<<63)-1
MASK=(1<<64)-1


def wrap(value):
    value &= MASK
    return value-(1<<64) if value>=1<<63 else value


def oracle(text):
    def evaluate(node):
        if isinstance(node,ast.Constant):
            assert isinstance(node.value,int) and 0<=node.value<=MAX
            return node.value
        if isinstance(node,ast.UnaryOp):
            if isinstance(node.op,ast.USub) and isinstance(node.operand,ast.Constant) and node.operand.value==1<<63:
                return MIN
            value=evaluate(node.operand)
            return wrap(-value) if isinstance(node.op,ast.USub) else value
        assert isinstance(node,ast.BinOp)
        lhs,rhs=evaluate(node.left),evaluate(node.right)
        return wrap(lhs+rhs if isinstance(node.op,ast.Add) else lhs-rhs if isinstance(node.op,ast.Sub) else lhs*rhs)
    return evaluate(ast.parse(text.strip(),mode='eval').body)


def cases():
    for text in ['42','1+2*3','(1+2)*3','20-5-3','2*3*4','-2*-3','+-+-42','--9223372036854775808','+-9223372036854775808','9223372036854775807+1','-9223372036854775808-1','9223372036854775807*2','-(2+3)*4','\t 42 \r','0'*128,' '*126+'42','('*16+'42'+')'*16,'-'*16+'42']:
        # Python treats decimal leading zeros and CR whitespace differently;
        # these particular zero-only / whitespace cases have explicit values.
        value=0 if text=='0'*128 else 42 if text.strip()=='42' else oracle(text)
        yield list(text.encode()),0,value
    for text,value in [('0042',42),('0042*01',42),('1--2',3),('1++2',3),('1+'*63+'1',64),('('*16+'1+'*47+'1'+')'*16,48),('('*8+'-'*8+'42'+')'*8,42)]:
        yield list(text.encode()),0,value
    for text,error in [('',2),('  ',2),('a',2),('1a',2),('1 2',2),('()',2),('(1',2),('1)',2),('1+',2),('*1',2),('1**2',2),('1//2',1),('1 + @',1),('9223372036854775808',4),('-9223372036854775809',4),('-+9223372036854775808',4),('-(9223372036854775808)',4),('('*17+'1'+')'*17,5),('-'*17+'1',5),('0'*129,3),('1\x00',1),('1\xff',1),('('*8+'-'*9+'1'+')'*8,5),('9223372036854775808 @',1)]:
        yield list(text.encode('latin1')),error,MIN
    rng=random.Random(0xEAA1)
    def expression(depth):
        if depth==0 or rng.randrange(4)==0: return str(rng.randrange(10000))
        if rng.randrange(4)==0: return rng.choice(['+','-'])+'('+expression(depth-1)+')'
        return '('+expression(depth-1)+rng.choice(['+','-','*'])+expression(depth-1)+')'
    for _ in range(64):
        text=expression(3)
        yield list(text.encode()),0,oracle(text)
        yield list((text+' +').encode()),2,MIN


def verify(frontend,rust,go):
    original=(ROOT/'implementations/alchem/lexer.alc').read_text()
    prefix=original.split('  # Native smoke test;',1)[0]
    count=0
    with tempfile.TemporaryDirectory(prefix='alchem-expressions-') as directory:
        root=Path(directory)
        for data,error,value in cases():
            literal='['+','.join(map(str,data))+']'
            for expression,expected in [(f'expression_error({literal})',error),(f'expression_or({literal}, -9223372036854775808)',value)]:
                source=prefix+'  def main() do\n if '+expression+' == '+str(expected)+' do System.halt(0) else System.halt(1) end\n end\nend\n'
                mode=['--program']
                path=root/'source.alc';path.write_text(source)
                result=subprocess.run([str(frontend),'--input',str(path)]+mode,capture_output=True,timeout=120)
                assert result.returncode==0,(count,data,result.stderr)
                ir=root/'source.json';ir.write_bytes(result.stdout);binaries=[]
                for index,compiler in enumerate([rust,go]):
                    output=root/f'program-{index}'
                    compiled=subprocess.run([str(compiler),'--target',TARGET,'--input',str(ir),'--output',str(output)],env=dict(os.environ,PATH=''),capture_output=True,timeout=120)
                    assert compiled.returncode==0,(count,compiled.stderr)
                    assert output.stat().st_mode & 0o777==0o700
                    executed=subprocess.run([str(output)],capture_output=True,timeout=120)
                    assert (executed.returncode,executed.stdout,executed.stderr)==(0,b'',b''),(count,data,index,executed)
                    binaries.append(output.read_bytes())
                assert binaries[0]==binaries[1],count
                repeat=root/'repeat'
                result=subprocess.run([str(rust),'--target',TARGET,'--input',str(ir),'--output',str(repeat)],capture_output=True,timeout=120)
                assert result.returncode==0 and repeat.read_bytes()==binaries[0],count
                count+=1
    print(f'PASS {count} Alchem expression oracle programs (all source-main programs): precedence, full i64, errors and bounds')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frontend',type=Path);parser.add_argument('rust',type=Path);parser.add_argument('go',type=Path)
    args=parser.parse_args();verify(args.frontend.resolve(),args.rust.resolve(),args.go.resolve())
