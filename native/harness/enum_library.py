#!/usr/bin/env python3
"""Byte-profile Enum operations compiled by Alchem, checked against Python."""
from pathlib import Path
from source_syntax import native_bytes
import random
import subprocess
import sys
import tempfile
from self_hosted_components import literal,product,verify_legacy_program as verify_program


def verify(compiler):
    rng=random.Random(171117);count=0
    inputs=[[],[0],[255,0,42],list(range(128))]+[[rng.randrange(256) for _ in range(rng.randrange(25))] for _ in range(16)]
    with tempfile.TemporaryDirectory(prefix='alchem-enum-') as directory:
        root=Path(directory)
        for data in inputs:
            operations=[('sum',f'Enum.sum({literal(data)})',sum(data)),('reverse',f'Enum.reverse({literal(data)})',data[::-1])]
            for n in [-(1<<63),-129,-2,-1,0,1,2,129,(1<<63)-1]:
                take=data[:n] if n>=0 else data[max(0,len(data)+n):]
                drop=data[n:] if n>=0 else data[:max(0,len(data)+n)]
                operations += [('take',f'Enum.take({literal(data)},{n})',take),('drop',f'Enum.drop({literal(data)},{n})',drop)]
            for name,expression,expected in operations:
                checks=[f'value == {expected}'] if isinstance(expected,int) else [f'Enum.count(value) == {len(expected)}']+[f'Enum.at(value,{i},-1) == {value}' for i,value in enumerate(expected)]
                for part in range(0,len(checks),16):
                    group=checks[part:part+16];helpers=''
                    for i,check in enumerate(group):helpers+=f'def check{i}(value: '+('integer' if isinstance(expected,int) else 'list[integer]')+f'): integer do if {check} do 1 else 0 end end '
                    terms=[f'check{i}(value)' for i in range(len(group))]
                    body='value='+expression+'\nif '+product(terms)+' == 1 do System.halt(0) else System.halt(1) end'
                    source='defmodule M do '+helpers+'def main() do '+body+' end end'
                    verify_program(source,compiler,root,(name,data,expected,part))
                count+=1
        for expression in ['Enum.sum(1)','Enum.reverse(1)','Enum.take([],[])','Enum.drop([],[])','Enum.sum([],1)','Enum.reverse([],1)','Enum.take([])','Enum.drop([])']:
            result=subprocess.run([str(compiler)],input=native_bytes(('defmodule M do def main() do value='+expression+'\n System.halt(0) end end').encode()),capture_output=True,env={'PATH':''},timeout=120)
            assert result.returncode==65 and not result.stdout,('Enum type rejection',expression,result)
        alias='defmodule M do def main() do a=[40,2]\nb=Enum.reverse(a)\nc=Enum.take(a,1)\nd=Enum.drop(a,1)\nSystem.halt(Enum.at(a,0,0)+Enum.at(b,0,0)+Enum.count(c)-Enum.count(d)) end end'
        verify_program(alias,compiler,root,'Enum immutability and live references',42)
        exhausted='defmodule M do def grow(b: list[integer],n: integer): list[integer] do if n == 0 do b else grow(Enum.concat(b,b),n-1) end end def main() do a=grow([0],20)\nb=Enum.reverse(a)\nc=Enum.reverse(b)\nSystem.halt(Enum.count(c)) end end'
        verify_program(exhausted,compiler,root,'reverse arena exhaustion',71)
    print(f'PASS {count} self-hosted Enum byte cases and 8 type/arity rejections, immutability and arena exhaustion')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
