#!/usr/bin/env python3
"""Immutable typed maps and iteration over structured entries."""
from pathlib import Path
import subprocess
import random
import sys
import tempfile
from self_hosted_components import verify_program


def verify(compiler):
    valid=[
        ('', 'm: map[integer, integer] = Map.put(%{},1000,42)\nSystem.halt(Map.get(m,1000,0))',42),
        ('', 'm: map[integer, string] = Map.put(Map.put(%{},-1,"hello"),42,"é中")\nSystem.halt(byte_size(Map.get(m,42,"")))',5),
        ('', 'm: map[string, integer] = Map.put(Map.put(%{},"é中",41),"é" <> "中",42)\nSystem.halt(Enum.count(m)+Map.get(m,"é中",0)-1)',42),
        ('', 'old: map[string, integer] = Map.put(%{},"a",42)\nnew=Map.put(old,"a",7)\nSystem.halt(Map.get(old,"a",0)+Map.get(new,"a",0)-7)',42),
        ('', 'm: map[boolean, boolean] = Map.put(%{},true,false)\nif Map.has_key?(m,true) and not Map.get(m,true,true) do System.halt(42) else System.halt(1) end',42),
        ('', 'm=Map.new([{1,7},{2,42},{1,9}])\nSystem.halt(Map.get(m,2,0)+Enum.count(m)-2)',42),
        ('def f(): map[string,option[tuple[integer,string]]] do Map.put(%{},"a",some({42,"yes"})) end ', 'System.halt(case Map.get(f(),"a",none) do some(v) -> elem(v,0) none -> 1 end)',42),
        ('', 'm: map[string, integer] = Map.put(%{},"x",42)\nSystem.halt(case Map.fetch(m,"x") do some(v) -> v none -> 1 end)',42),
        ('', 'm: map[string, integer] = Map.put(%{},"x",42)\nSystem.halt(case Map.get(m,"absent") do none -> 42 some(v) -> v end)',42),
        ('', 'm: map[integer, integer] = Map.put(Map.put(%{},1,42),2,7)\nn=Map.delete(m,2)\nSystem.halt(Map.get(n,1,0)+Enum.count(n)-1)',42),
        ('', 'm: map[integer, integer] = Map.put(%{},1,42)\nn=Map.delete(m,99)\nSystem.halt(Map.get(n,1,0))',42),
        ('def total(pair: tuple[integer,integer],acc: integer): integer do acc+elem(pair,0)+elem(pair,1) end ', 'm=Map.new([{1,10},{2,29}])\nSystem.halt(Enum.reduce(Map.to_list(m),0,&total))',42),
        ('', 'm=Map.new([{1,10},{2,29}])\nSystem.halt(Enum.sum(Map.keys(m))+Enum.sum(Map.values(m)))',42),
    ]
    valid += [
        ('', 'm=%{1 => 42,2 => 7}\nSystem.halt(Map.get(m,1,0))',42),
        ('', 'm=%{"é中" => [42], "empty" => []}\nSystem.halt(Enum.at(Map.get(m,"é中",[]),0,0))',42),
        ('', 'm=%{1 => %{2 => 42},3 => %{}}\nSystem.halt(Map.get(Map.get(m,1,%{}),2,0))',42),
        ('', 'm=%{1 => 7,1 => 42}\nSystem.halt(Map.get(m,1,0))',42),
    ]
    valid += [
        ('', 'm=%{3 => 30,1 => 10,2 => 20}\nSystem.halt(Enum.at(Map.keys(m),0,0)+41)',42),
        ('', 'm=Map.put(%{3 => 30,1 => 10},2,20)\nSystem.halt(Enum.at(Map.values(m),0,0)+32)',42),
        ('', 'm=%{true => 7,false => 42}\nSystem.halt(Enum.at(Map.values(m),0,0))',42),
        ('', 'm=%{"é" => 7,"a" => 9,"" => 42,"ab" => 8}\nSystem.halt(Enum.at(Map.values(m),0,0))',42),
        ('', 'm=%{"a" => 7,"a\\x00" => 9,"\\x00" => 42}\nSystem.halt(elem(Enum.at(Map.to_list(m),0,{"",0}),1))',42),
    ]
    rng=random.Random(171125)
    for _ in range(48):
        pairs=[(rng.randrange(-5,6),rng.randrange(-(1<<63),(1<<63))) for _ in range(rng.randrange(12))]
        mapping=dict(pairs)
        literal='['+','.join('{'+str(k)+','+str(v)+'}' for k,v in pairs)+']'
        for key in [-7,-1,0,1,7]:
            expected=mapping.get(key,99)
            valid.append(('',f'm: map[integer, integer] = Map.new({literal})\nif Map.get(m,{key},99) == {expected} and Enum.count(m) == {len(mapping)} do System.halt(0) else System.halt(1) end',0))
    with tempfile.TemporaryDirectory(prefix='alchem-maps-') as d:
        root=Path(d)
        for i,(helpers,body,status) in enumerate(valid):
            verify_program('defmodule M do '+helpers+'def main() do '+body+' end end',compiler,root,('map',i),status)
        bad=[
            'e: map[integer, integer] = %{}\nm=Map.put(e,[1],42)\nSystem.halt(0)',
            'e: map[integer, integer] = %{}\nm=Map.put(Map.put(e,1,42),"bad",7)\nSystem.halt(0)',
            'e: map[integer, integer] = %{}\nm=Map.put(Map.put(e,1,42),2,false)\nSystem.halt(0)',
            'e: map[integer, integer] = %{}\nSystem.halt(Map.get(Map.put(e,1,42),"bad",0))',
            'e: map[integer, integer] = %{}\nSystem.halt(Map.get(Map.put(e,1,42),1,false))',
            'e: map[string, integer] = %{}\nSystem.halt(Enum.sum(Map.keys(Map.put(e,"a",1))))',
            'm=Map.new([1,2])\nSystem.halt(0)',
            'm=Map.new([{[1],2}])\nSystem.halt(0)',
            'm=Map.put(%{},1)\nSystem.halt(0)',
            'm=Map.nonexistent(%{},1)\nSystem.halt(0)',
            'm=%{1 => 42, \"bad\" => 7}\nSystem.halt(0)',
            'm=[1}\nSystem.halt(0)',
        ]
        for body in bad:
            r=subprocess.run([str(compiler)],input=('defmodule M do def main() do '+body+' end end').encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(body,r.returncode,r.stderr)
    print(f'PASS {len(valid)} typed map programs and {len(bad)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
