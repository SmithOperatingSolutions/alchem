#!/usr/bin/env python3
"""Full-width immutable collections and typed named-function iteration."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from self_hosted_components import verify_program


def integer_list(values):return '['+','.join(map(str,values))+']'


def verify(compiler):
    valid=[
        ('', 'System.halt(Enum.at([1000,-958],0,0)+Enum.at([1000,-958],1,0))',42),
        ('def f(): list[integer] do [] end ', 'System.halt(Enum.count(f())+42)',42),
        ('def f(): list[string] do ["hello","é中"] end ', 'System.halt(byte_size(Enum.at(f(),1,"")))',5),
        ('def f(): list[option[integer]] do [some(42),none] end ', 'System.halt(case Enum.at(f(),0,none) do some(x) -> x none -> 1 end)',42),
        ('def f(): list[tuple[integer,string]] do [{42,"a"},{7,"b"}] end ', 'System.halt(elem(Enum.at(f(),0,{0,""}),0))',42),
        ('def f(): list[list[integer]] do [[42],[]] end ', 'System.halt(Enum.at(Enum.at(f(),0,[]),0,0))',42),
        ('def add(n: integer): integer do n+1 end ', 'System.halt(Enum.sum(Enum.map([10,20,9],&add)))',42),
        ('def add(value: integer,acc: integer): integer do value+acc end ', 'System.halt(Enum.reduce([1000,-958],0,&add))',42),
        ('def text(n: integer): string do Integer.to_string(n) end ', 'System.halt(byte_size(Enum.at(Enum.map([-123,42],&text),0,"")))',4),
        ('def add(n: integer): integer do n+1 end def apply(v: list[integer],f: fn[integer,integer]): list[integer] do Enum.map(v,f) end ', 'System.halt(Enum.at(apply([41],&add),0,0))',42),
        ('def size(s: string,acc: integer): integer do acc+byte_size(s) end ', 'System.halt(Enum.reduce(["é","中","abc"],34,&size))',42),
        ('def add(v: integer,acc: integer): integer do v+acc end ', 'empty: list[integer] = []\nSystem.halt(Enum.reduce(empty,42,&add))',42),
    ]
    valid += [
        ('', 'if Enum.sum([9223372036854775807,-1]) == 9223372036854775806 do System.halt(0) else System.halt(1) end',0),
        ('def grow(v: list[integer],n: integer): list[integer] do if n == 0 do v else grow(Enum.concat(v,v),n-1) end end def add(n: integer): integer do n+1 end ', 'System.halt(Enum.sum(Enum.map(grow([1],10),&add))-2006)',42),
        (''.join(f'def f{i}(n: integer): integer do n+1 end ' for i in range(300)), 'System.halt(Enum.at(Enum.map([41],&f299),0,0))',42),
    ]
    rng=random.Random(171124)
    data_sets=[[],[0],[-(1<<63),(1<<63)-1,1000,-1000],[42]*128]
    data_sets += [[rng.randrange(-(1<<63),(1<<63)) for _ in range(rng.randrange(12))] for _ in range(20)]
    for values in data_sets:
        source=integer_list(values)
        for index in [-100,-1,0,1,100,-(1<<63),(1<<63)-1]:
            normal=index+len(values) if index<0 else index
            expected=values[normal] if 0<=normal<len(values) else 999
            body=f'if Enum.at({source},{index},999) == {expected} do System.halt(0) else System.halt(1) end'
            valid.append(('',body,0))
        operations=[(f'Enum.reverse({source})',values[::-1]),(f'Enum.concat({source},[-1000,1000])',values+[-1000,1000])]
        for count in [-(1<<63),-2,0,2,(1<<63)-1]:
            take=values[:count] if count>=0 else values[max(0,len(values)+count):]
            drop=values[count:] if count>=0 else values[:max(0,len(values)+count)]
            operations += [(f'Enum.take({source},{count})',take),(f'Enum.drop({source},{count})',drop)]
        for start in [-100,-2,0,2,(1<<63)-1]:
            for count in [0,1,(1<<63)-1]:
                index=start+len(values) if start<0 else start
                expected=values[index:index+count] if 0<=index<len(values) else []
                operations.append((f'Enum.slice({source},{start},{count})',expected))
        for expression,expected in operations:
            checks=[f'Enum.count(value) == {len(expected)}']
            for i in set([0,len(expected)//2,len(expected)-1]):
                if i>=0 and i<len(expected):checks.append(f'Enum.at(value,{i},0) == {expected[i]}')
            valid.append(('',f'value: list[integer] = {expression}\nif '+ ' and '.join(checks)+' do System.halt(0) else System.halt(1) end',0))
    with tempfile.TemporaryDirectory(prefix='alchem-collections-') as d:
        root=Path(d)
        for number,(helpers,body,status) in enumerate(valid):
            verify_program('defmodule M do '+helpers+'def main() do '+body+' end end',compiler,root,('collection',number),status)
        bad=[
            'def f(): list[integer] do ["x"] end def main() do System.halt(0) end',
            'def main() do v=[1,"x"]\nSystem.halt(0) end',
            'def main() do System.halt(Enum.at([1],0,"wrong")) end',
            'def f(x: string): integer do byte_size(x) end def main() do v=Enum.map([1],&f)\nSystem.halt(0) end',
            'def f(x: integer,y: integer): integer do x+y end def main() do v=Enum.map([1],&f)\nSystem.halt(0) end',
            'def main() do v=Enum.map([1],&missing)\nSystem.halt(0) end',
            'def main() do v=Enum.map([1],&main)\nSystem.halt(0) end',
            'def main() do System.halt(Enum.sum(["x"])) end',
            'def main() do System.halt(Enum.fetch([1],0,42)) end',
        ]
        for body in bad:
            r=subprocess.run([str(compiler)],input=('defmodule M do '+body+' end').encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(body,r.returncode,r.stderr)
        helpers='def grow(v: list[integer],n: integer): list[integer] do if n == 0 do v else grow(Enum.concat(v,v),n-1) end end def text(n: integer): string do String.duplicate("x",1024) end '
        verify_program('defmodule M do '+helpers+'def main() do value=Enum.map(grow([1],12),&text)\nSystem.halt(0) end end',compiler,root,'callback allocation exhaustion',71)
        verify_program('defmodule M do def main() do value=Enum.slice([1000],0,-1)\nSystem.halt(0) end end',compiler,root,'generic slice negative count',(2,b'slice needs a nonnegative amount'))
    print(f'PASS {len(valid)} general collection programs and {len(bad)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
