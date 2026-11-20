#!/usr/bin/env python3
"""Nested options, tuples and result success/error paths through native code."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from self_hosted_components import verify_program


def verify(compiler):
    valid=[
        ('def f(): option[option[integer]] do some(some(42)) end ', 'System.halt(case f() do some(v) -> case v do some(x) -> x none -> 1 end none -> 2 end)',42),
        ('def f(): option[option[string]] do some(none) end ', 'System.halt(case f() do some(v) -> case v do some(x) -> byte_size(x) none -> 42 end none -> 1 end)',42),
        ('def f(v: tuple[integer,string]): string do elem(v,1) end ', 'System.halt(byte_size(f({42,"hello"})))',5),
        ('def f(): result[integer,string] do ok(42) end ', 'System.halt(case f() do ok(x) -> x error(e) -> byte_size(e) end)',42),
        ('def f(): result[integer,string] do error("bad") end ', 'System.halt(case f() do error(e) -> byte_size(e) ok(x) -> x end)',3),
        ('def f(): result[tuple[integer,string],option[boolean]] do ok({42,"yes"}) end ', 'System.halt(case f() do ok(v) -> elem(v,0) error(e) -> 1 end)',42),
    ]
    valid += [('def f(): result[tuple[],string] do ok({}) end ', 'System.halt(case f() do ok(unit) -> 42 error(e) -> 1 end)',42),('def f(): tuple[integer] do {42} end ', 'System.halt(elem(f(),0))',42)]
    valid += [('','error=20\nok=21\nelem=1\nSystem.halt(error+ok+elem)',42)]
    # none and some may name bindings and parameters; a binding hides the constructor, patterns stay.
    valid += [('def f(none: integer, some: integer): integer do none + some end def g(o: option[integer]): integer do case o do some(n) -> n none -> 0 end end ',
               'first = f(30, 2) + g(some(1)) + g(none)\nnone = 9\nx = some(none)\nSystem.halt(first + g(x))',42),
              ('','some = 40\nnone = 2\nSystem.halt(Enum.sum(Enum.map([some], fn n -> n + none end)))',42)]
    valid += [
        ('def f(n: integer): result[integer,string] do if n == 0 do ok(42) else error("bad") end end ', 'System.halt(case f(0) do error(e) -> byte_size(e) ok(x) -> x end)',42),
        ('def f(n: integer): result[integer,string] do if n == 0 do ok(42) else error("bad") end end ', 'System.halt(case f(1) do ok(x) -> x error(e) -> byte_size(e) end)',3),
        ('', 'v=if true do ok(42) else error("bad") end\nSystem.halt(case v do error(e) -> 1 ok(x) -> x end)',42),
        ('def f(): result[option[integer],tuple[string,boolean]] do error({"bad",true}) end ', 'v=case f() do error(e) -> elem(e,1) ok(x) -> false end\nif v do System.halt(42) else System.halt(1) end',42),
        ('def f(): result[result[string,integer],boolean] do ok(error(42)) end ', 'System.halt(case f() do ok(v) -> case v do error(e) -> e ok(s) -> byte_size(s) end error(b) -> 1 end)',42),
        ('def f(): option[tuple[string,option[integer]]] do some({"abc",some(39)}) end ', 'System.halt(case f() do none -> 1 some(t) -> case elem(t,1) do some(n) -> n+byte_size(elem(t,0)) none -> 2 end end)',42),
        ('def f(): tuple[option[string],option[boolean],option[integer],option[string],option[boolean],option[integer]] do {some("a"),some(true),some(3),none,none,some(42)} end ', 'System.halt(case elem(f(),5) do some(x) -> x none -> 1 end)',42),
        ('def f(a: tuple[integer,string],b: result[integer,boolean],c: option[tuple[integer,string]],d: tuple[boolean,integer],e: result[string,integer],f: option[string]): integer do elem(a,0)+elem(d,1) end ', 'System.halt(f({20,"x"},ok(1),none,{true,22},error(7),some("s")))',42),
        ('', 'original={42,"a"}\nother={9,"longer"}\nSystem.halt(elem(original,0)+byte_size(elem(other,1))-6)',42),
    ]
    # Types far beyond the former 60-bit word: accumulators, lambdas and function
    # values over tuples and results of collections. Outcomes equal the pinned upstream.
    state='tuple[list[string], map[string, integer], integer]'
    nested='result[tuple[tuple[list[string], map[string, string]], string], string]'
    six='tuple['+','.join(['string']*6)+']'
    limit='tuple['+','.join([six]*5+['tuple[string,string,string]'])+']'
    wide='tuple['+','.join([six]*6)+']'
    step=f'def step(part: string, acc: {state}): {state} do {{Enum.concat(elem(acc, 0), [part <> "!"]), Map.put(elem(acc, 1), part, byte_size(part)), elem(acc, 2) + 1}} end '
    fold=(f'def fold(target: string, acc: {nested}): {nested} do case acc do error(reason) -> error(reason) ok(pair) -> if target == "bad" do error("bad target") else '
          'ok({{Enum.concat(elem(elem(pair, 0), 0), [target]), Map.put(elem(elem(pair, 0), 1), target, "seen")}, elem(pair, 1) <> target}) end end end '
          f'def size(r: {nested}): integer do case r do error(reason) -> byte_size(reason) ok(pair) -> Enum.count(elem(elem(pair, 0), 0)) * 10 + byte_size(elem(pair, 1)) + Enum.count(Map.keys(elem(elem(pair, 0), 1))) end end ')
    begin='empty: list[string] = []\nindex: map[string, integer] = %{}\n'
    start=f'empty: list[string] = []\nindex: map[string, string] = %{{}}\nstart: {nested} = ok({{{{empty, index}}, ""}})\n'
    valid += [
        (step,begin+'out = Enum.reduce(["a", "bb", "ccc"], {empty, index, 0}, &step/2)\nSystem.halt(elem(out, 2) * 10 + Map.get(elem(out, 1), "bb", 0) + byte_size(Enum.join(elem(out, 0), ",")))',43),
        (step,begin+'out = Enum.reduce(["a", "bb"], {empty, index, 0}, fn part, acc -> step(part <> "?", acc) end)\nSystem.halt(elem(out, 2) * 10 + byte_size(Enum.join(elem(out, 0), ",")))',28),
        (fold,start+'System.halt(size(Enum.reduce(["x", "y", "x"], start, fn target, acc -> fold(target, acc) end)))',35),
        (fold,start+'System.halt(size(Enum.reduce(["x", "bad", "y"], start, &fold/2)))',10),
        (step+f'def apply(f: fn[{state}, {state}], x: {state}): {state} do f(x) end ',
         begin+f'twice = fn(t: {state}): {state} do step("q", step("p", t)) end\nout = apply(twice, {{empty, index, 5}})\nSystem.halt(elem(out, 2) * 6)',42),
        ('def deep(x: list[list[list[list[list[list[list[list[option[result[integer, string]]]]]]]]]]): integer do Enum.count(x) end ',
         'x: list[list[list[list[list[list[list[list[option[result[integer, string]]]]]]]]]] = []\nSystem.halt(deep(x) + 42)',42),
        # 47 bytes was the limit of fixed type fields; types now take up to 255 bytes.
        (f'def last(x: {limit}): string do elem(elem(x, 5), 2) end ',
         's = {"a","b","c","d","e","f"}\nSystem.halt(byte_size(last({s,s,s,s,s,{"x","y","forty-two"}})) + 33)',42),
        # 252 bytes as an annotation and as an inferred tuple of tuples of tuples.
        (f'def pick(x: tuple[{wide},{wide},{wide},{wide},{wide}]): string do elem(elem(elem(x, 4), 5), 0) end ',
         's = {"a","b","c","d","e","f"}\nw = {s,s,s,s,s,{"forty-two","b","c","d","e","f"}}\nSystem.halt(byte_size(pick({w,w,w,w,w})) + 33)',42),
        # Types beyond 255 bytes (once the limit) as an annotation and as an inferred tuple.
        (f'def f(x: tuple[{wide},{wide},{wide},{wide},{wide},{wide}]): integer do 1 end ','System.halt(42)',42),
        ('','s={"a","b","c","d","e","f"}\nw={s,s,s,s,s,s}\nv={w,w,w,w,w,w}\nSystem.halt(byte_size(elem(elem(elem(v, 5), 5), 5)) + 41)',42),
        # 126 levels of nesting, the most a type may be written with, as the pinned parser has it.
        ('def f(): '+('option['*125)+'integer'+(']'*125)+' do none end ','x = f()\nSystem.halt(42)',42),
    ]
    rng=random.Random(171123)
    for arity in range(2,7):
        for index in range(arity):
            values=[rng.randrange(-(1<<63),(1<<63)) for _ in range(arity)]
            expression='{'+','.join(map(str,values))+'}'
            valid.append(('',f'if elem({expression},{index}) == {values[index]} do System.halt(0) else System.halt(1) end',0))
    for success in [True,False]:
        for value in [-(1<<63),(1<<63)-1,0,42]:
            constructor='ok' if success else 'error'
            valid.append((f'def f(): result[integer,integer] do {constructor}({value}) end ',f'v=case f() do ok(x) -> x error(e) -> e end\nif v == {value} do System.halt(0) else System.halt(1) end',0))
    with tempfile.TemporaryDirectory(prefix='alchem-structural-') as d:
        root=Path(d)
        for i,(helpers,body,status) in enumerate(valid):
            verify_program('defmodule M do '+helpers+'def main() do '+body+' end end',compiler,root,('structural',i),status)
        bad=[
            'def f(): option[option[integer]] do some(some(true)) end def main() do System.halt(0) end',
            'def f(): tuple[integer,string] do {"bad",1} end def main() do System.halt(0) end',
            'def f(): result[integer,string] do error(false) end def main() do System.halt(0) end',
            'def main() do System.halt(elem({1,2},2)) end',
            'def main() do System.halt(case ok(1) do ok(x) -> x end) end',
            'def main() do System.halt(case error("x") do ok(x) -> x error(e) -> 1 end) end',
        ]
        bad += [
            'def f(): result[integer] do ok(1) end def main() do System.halt(0) end',
            'def f(): result[integer,string,boolean] do ok(1) end def main() do System.halt(0) end',
            'def f(): option[option[integer]] do some(none) end def main() do System.halt(case f() do some(x) -> x none -> none end) end',
            'def main() do System.halt(elem({1,2},-1)) end',
            'def main() do i=0\nSystem.halt(elem({1,2},i)) end',
            'def main() do v={1,2,}\nSystem.halt(0) end',
            'def main() do none = 5\ny: option[integer] = none\nSystem.halt(0) end',
            'def main() do some = 5\nx = some(1)\nSystem.halt(0) end',
            'def main() do none = 5\nnone = 6\nSystem.halt(0) end',
            'def f(): result[integer,string] do ok(1) end def main() do System.halt(case f() do ok(x) -> x ok(e) -> e end) end',
            'def f(): result[integer,string] do ok(1) end def main() do System.halt(case f() do ok(x) -> x error(e) -> x end) end',
            'def main() do v=if true do {1,"x"} else {1,false} end\nSystem.halt(0) end',
            # One level beyond 126.
            'def f(): '+('option['*126)+'integer'+(']'*126)+' do none end def main() do System.halt(0) end',
            step+'def main() do empty: list[string] = []\nindex: map[string, string] = %{}\nout = Enum.reduce(["a"], {empty, index, 0}, &step/2)\nSystem.halt(0) end',
        ]
        for body in bad:
            r=subprocess.run([str(compiler)],input=('defmodule M do '+body+' end').encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(body,r.returncode,r.stderr)
        # Balanced recursive allocation took more than the 4 MiB arena holds, without
        # exhausting frames, and exited 71. No tuple stays in use, so the program now
        # gives them back and runs to its end (spec/alchem-memory.md); tuples that
        # are kept (100,000 in a list) still exhaust the arena.
        text='defmodule M do def f(n: integer): integer do v={1,2,3,4,5,6}\nif n == 0 do 0 else f(n-1)+f(n-1) end end def main() do System.halt(f(17)) end end'
        verify_program(text,compiler,root,'tuples given back',0)
        text='defmodule M do def g(n: integer, kept: list[tuple[integer,integer,integer,integer,integer,integer]]): integer do if n == 0 do Enum.count(kept) else g(n-1,[{1,2,3,4,5,n} | kept]) end end def main() do System.halt(rem(g(100000,[]),7)) end end'
        verify_program(text,compiler,root,'tuple arena exhaustion',71)
    print(f'PASS {len(valid)} structural programs and {len(bad)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
