#!/usr/bin/env python3
"""== and != on compound values: lists, tuples, options, results, maps, structs
and sum types, against a structural oracle."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile

DECLARATIONS=('struct Account do owner: string\n balance: integer = 0\n tags: list[string] = []\n end '
              'type Tree do leaf\n node(left: Tree, value: integer, right: Tree)\n end '
              'struct Holder do f: fn[integer, integer]\n end '
              'def mk(name: string): Account do %Account{owner: name} end def yes(b: boolean): string do if b do "y" else "n" end end def inc(n: integer): integer do n + 1 end '
              'def grow(n: integer): Tree do if n == 0 do Tree.leaf else Tree.node(grow(n - 1), n, grow(n - 1)) end end '
              'def chain(n: integer, t: Tree): Tree do if n == 0 do t else chain(n - 1, Tree.node(t, n, Tree.leaf)) end end ')
# (main body, stdout): outcomes equal the pinned upstream `alchem run`.
CASES=[
    ('IO.puts(yes(mk("a") == mk("a")) <> yes(mk("a") == mk("b")) <> yes(%Account{owner: "a", tags: ["t"]} != mk("a")) <> yes(mk("a").tags == []))\n'
     'a = Tree.node(Tree.leaf, 1, Tree.node(Tree.leaf, 2, Tree.leaf))\nb = Tree.node(Tree.leaf, 1, Tree.node(Tree.leaf, 2, Tree.leaf))\n'
     'IO.puts(yes(a == b) <> yes(a == Tree.leaf) <> yes(Tree.leaf == Tree.leaf) <> yes(a != Tree.node(Tree.leaf, 1, Tree.node(Tree.leaf, 3, Tree.leaf))) <> yes(a == a))\n'
     'IO.puts(yes(grow(12) == grow(12)) <> yes(grow(12) == grow(11)))\nx = [1, 2]\nIO.puts(if x == [1, 2] and {x, 1} != {x, 2} do "ok" else "no" end)\n'
     'IO.puts(Integer.to_string(Enum.count(Enum.filter([mk("a"), mk("b"), mk("a")], fn acct -> acct == mk("a") end))))\n'
     'IO.puts(yes(%{"k" => [mk("a")]} == %{"k" => [mk("a")]}) <> yes(%{"k" => [mk("a")]} == %{"k" => [mk("b")]}))\n'
     'IO.puts(yes({[some(mk("a"))], %{1 => {true, "s"}}} == {[some(mk("a"))], %{1 => {true, "s"}}}) <> yes({[some(mk("a"))], %{1 => {true, "s"}}} == {[some(mk("a"))], %{1 => {true, "t"}}}))\n'
     'IO.puts(yes({} == {}) <> yes(some(1) == none))',b'ynyy\nynyyy\nyn\nok\n2\nyn\nyn\nyn\n'),
    ('m = %{"x" => 1, "y" => 2}\nn = Map.put(Map.put(Map.new([{"y", 2}]), "x", 1), "x", 1)\n'
     'IO.puts(yes(m == n) <> yes(m == Map.put(n, "z", 3)) <> yes(m == Map.put(n, "x", 9)) <> yes(Map.delete(m, "x") == %{"y" => 2}) <> yes(m != n))\n'
     # A chain of 2000 nodes compares by recursion deep in its own frames.
     'IO.puts(yes(Enum.reduce([1, 2, 3, 4, 5, 6, 7, 8], Tree.leaf, fn i, t -> chain(250, t) end) == Enum.reduce([1, 2, 3, 4, 5, 6, 7, 8], Tree.leaf, fn i, t -> chain(250, t) end)))',
     b'ynnyn\ny\n'),
]
REJECTIONS=[
    ('f = &inc/1\nx = f == f','functions'),('x = [&inc/1] == [&inc/1]','functions in a list'),('h = %Holder{f: &inc/1}\nx = h == h','a struct holding a function'),
    ('x = {1, 2} == {1, "a"}','tuples of different types'),('x = {1, 2} < {1, 3}','ordering of tuples'),('x = [1, 2] <= [1, 3]','ordering of lists'),
    ('x = mk("a") == Tree.leaf','a struct and a sum value'),('x = [1] == ["a"]','lists of different types'),('x = mk("a") > mk("b")','ordering of structs'),
]


def scalar(rng,kind):
    if kind=='integer':return rng.choice([0,1,-1,7,2**62,-(2**63)])
    if kind=='boolean':return rng.choice([True,False])
    return rng.choice(['','a','ab','é','a b','ab\x00'[:2]])


def kind(rng,depth):
    if depth==0 or rng.randrange(3)==0:return rng.choice(['integer','boolean','string'])
    shape=rng.choice(['list','tuple','option','result','map'])
    if shape=='tuple':return ('tuple',[kind(rng,depth-1) for _ in range(rng.randrange(0,4))])
    if shape=='result':return ('result',[kind(rng,depth-1),kind(rng,depth-1)])
    if shape=='map':return ('map',[rng.choice(['integer','string','boolean']),kind(rng,depth-1)])
    return (shape,[kind(rng,depth-1)])


def spell(k):
    return k if isinstance(k,str) else k[0]+'['+','.join(spell(c) for c in k[1])+']'


def value(rng,k):
    if isinstance(k,str):return scalar(rng,k)
    shape,parts=k
    if shape=='list':return [value(rng,parts[0]) for _ in range(rng.randrange(0,4))]
    if shape=='tuple':return tuple(value(rng,p) for p in parts)
    if shape=='option':return None if rng.randrange(3)==0 else ('some',value(rng,parts[0]))
    if shape=='result':return ('ok',value(rng,parts[0])) if rng.randrange(2) else ('error',value(rng,parts[1]))
    keys=[];[keys.append(key) for key in (scalar(rng,parts[0]) for _ in range(rng.randrange(0,4))) if key not in keys]
    return {'map':[(key,value(rng,parts[1])) for key in keys]}


def near(rng,k,v):
    """Mostly v itself or v with one part changed."""
    if rng.randrange(3)==0:return value(rng,k)
    if isinstance(k,str) or rng.randrange(4)==0:return v
    shape,parts=k
    if shape=='list' and v:
        i=rng.randrange(len(v));return v[:i]+[near(rng,parts[0],v[i])]+v[i+1:]
    if shape=='tuple' and v:
        i=rng.randrange(len(v));return v[:i]+(near(rng,parts[i],v[i]),)+v[i+1:]
    if shape=='option' and v:return ('some',near(rng,parts[0],v[1]))
    if shape=='result':return (v[0],near(rng,parts[0 if v[0]=='ok' else 1],v[1]))
    if shape=='map' and v['map']:
        pairs=list(v['map']);i=rng.randrange(len(pairs));pairs[i]=(pairs[i][0],near(rng,parts[1],pairs[i][1]));rng.shuffle(pairs);return {'map':pairs}
    return v


def text(k,v):
    if k=='integer':return str(v) if v!=-(2**63) else '(0 - 9223372036854775807 - 1)'
    if k=='boolean':return 'true' if v else 'false'
    if k=='string':return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,35,92) else f'\\x{b:02x}' for b in v.encode())+'"'
    shape,parts=k
    if shape=='list':return '['+', '.join(text(parts[0],x) for x in v)+']'
    if shape=='tuple':return '{'+', '.join(text(p,x) for p,x in zip(parts,v))+'}'
    if shape=='option':return 'none' if v is None else 'some('+text(parts[0],v[1])+')'
    if shape=='result':return v[0]+'('+text(parts[0 if v[0]=='ok' else 1],v[1])+')'
    return '%{'+', '.join(text(parts[0],key)+' => '+text(parts[1],x) for key,x in v['map'])+'}'


def same(k,a,b):
    if isinstance(k,str):return a==b
    shape,parts=k
    if shape=='list':return len(a)==len(b) and all(same(parts[0],x,y) for x,y in zip(a,b))
    if shape=='tuple':return all(same(p,x,y) for p,x,y in zip(parts,a,b))
    if shape=='option':return (a is None)==(b is None) and (a is None or same(parts[0],a[1],b[1]))
    if shape=='result':return a[0]==b[0] and same(parts[0 if a[0]=='ok' else 1],a[1],b[1])
    left=dict(a['map']);right=dict(b['map'])
    return left.keys()==right.keys() and all(same(parts[1],left[key],right[key]) for key in left)


def verify(compiler):
    rng=random.Random(92113)
    with tempfile.TemporaryDirectory(prefix='alchem-equality-') as d:
        root=Path(d)
        def built(source):
            return subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
        def ran(result,label):
            assert (result.returncode,result.stderr)==(0,b''),(label,result.returncode,result.stderr)
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            return subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        for body,stdout in CASES:
            run=ran(built('defmodule M do '+DECLARATIONS+'def main() do '+body+'\nSystem.halt(0) end end'),body[:60])
            assert (run.returncode,run.stdout,run.stderr)==(0,stdout,b''),(body[:60],run)
        pairs=0;equal=0
        for batch in range(20):
            helpers=[];lines=[];want=''
            for index in range(12):
                k=kind(rng,3)
                while isinstance(k,str):k=kind(rng,3)
                a=value(rng,k);b=near(rng,k,a)
                helpers.append(f'def a{index}(): {spell(k)} do {text(k,a)} end def b{index}(): {spell(k)} do {text(k,b)} end ')
                lines.append(f'IO.write(if a{index}() == b{index}() do "y" else "n" end)\nIO.write(if b{index}() != a{index}() do "n" else "y" end)\n')
                want+=('y' if same(k,a,b) else 'n')*2;pairs+=1;equal+=same(k,a,b)
            source='defmodule M do def run(n: integer): integer do\n'+''.join(lines[:6])+'n end def more(n: integer): integer do\n'+''.join(lines[6:])+'n end '+''.join(helpers)+'def main() do System.halt(run(0) + more(0)) end end'
            result=built(source)
            if result.returncode!=0:
                for helper,line in zip(helpers,lines):
                    one=built('defmodule M do '+helper+'def run(n: integer): integer do\n'+line+'n end def main() do System.halt(run(0)) end end')
                    assert one.returncode==0,('equality program rejected',helper[:300],one.returncode)
            run=ran(result,('batch',batch))
            if run.stdout.decode()!=want:
                for index,(helper,line) in enumerate(zip(helpers,lines)):
                    one=ran(built('defmodule M do '+helper+'def run(n: integer): integer do\n'+line+'n end def main() do System.halt(run(0)) end end'),'single')
                    assert one.stdout.decode()==want[index*2:index*2+2],('equality differs from the oracle',helper[:400],one.stdout,want[index*2:index*2+2])
            assert (run.returncode,run.stdout.decode(),run.stderr)==(0,want,b''),('equality batch',batch)
        assert 20<equal<pairs-20,('oracle balance',equal,pairs)
        for body,label in REJECTIONS:
            result=built('defmodule M do '+DECLARATIONS+'def main() do '+body+'\nSystem.halt(0) end end')
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
    print(f'PASS equality: {len(CASES)} programs with structs, sum types, maps and deep recursion, {pairs} random typed pairs against a structural oracle ({equal} equal), {len(REJECTIONS)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
