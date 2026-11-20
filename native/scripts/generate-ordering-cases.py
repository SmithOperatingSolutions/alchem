#!/usr/bin/env python3
"""Regenerate harness/ordering-cases.json.xz: the programs of the ordering gate
with what the pinned compiler makes of each. Not used by normal builds.

Every program is run by build/dev/alchem-upstream (the pinned compiler behind
its memory and time ceiling). A case is the source, then the status, standard
output and standard error of the run with the file named <stdin>; a program
the pinned compiler rejects has status null and its diagnostic."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import lzma
import os
import random
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
NAN='inf = Enum.reduce([1.0e308, 10.0], 1.0, fn a, b -> a * b end)\nnan = inf - inf\n'


def programs():
    P=[]
    def add(*lines): P.append('\n'.join(lines))
    random.seed(7)
    # (type name, element type text, sample list literals)
    T={
     'int':('integer',['[3, 1, 2, 1, -5]','[1]','[2, 2, 2]','[9223372036854775807, -9223372036854775808, 0]']),
     'str':('string',['["b", "a", "", "ab", "B", "a"]','["é", "z", "e", "ée"]','["x"]']),
     'float':('float',['[1.5, -2.0, 0.0, 1.5, -0.0]','[2.0]','[1.0e300, -1.0e-300, 3.25]']),
     'bool':('boolean',['[true, false, true, false]','[false]']),
     'atom':('atom',['[:b, :a, :c, :a]','[:zeta, :Alpha, :beta, :b]']),
     't1':('tuple[integer]',['[{3}, {1}, {2}]']),
     't2is':('tuple[integer, string]',['[{2, "a"}, {1, "b"}, {1, "a"}, {2, ""}]']),
     't2sa':('tuple[string, atom]',['[{"b", :x}, {"a", :z}, {"a", :y}]']),
     't2fb':('tuple[float, boolean]',['[{1.5, true}, {1.5, false}, {-1.0, true}]']),
     't3':('tuple[integer, integer, integer]',['[{1, 2, 3}, {1, 2, 2}, {0, 9, 9}, {1, 1, 9}]']),
     't4':('tuple[integer, string, boolean, atom]',['[{1, "a", true, :b}, {1, "a", true, :a}, {1, "a", false, :z}, {0, "z", true, :z}]']),
     't5':('tuple[integer, integer, integer, integer, integer]',['[{1, 2, 3, 4, 5}, {1, 2, 3, 4, 4}, {1, 2, 3, 3, 9}]']),
     't7':('tuple[integer, integer, integer, integer, integer, integer, integer]',['[{1, 2, 3, 4, 5, 6, 7}, {1, 2, 3, 4, 5, 6, 6}, {0, 2, 3, 3, 9, 1, 1}]']),
     'tnest':('tuple[integer, tuple[integer, integer]]',['[{1, {2, 3}}, {1, {1, 3}}, {0, {9, 9}}, {1, {1, 2}}]']),
     'tnest3':('tuple[tuple[string, tuple[integer, float]], atom]',['[{{"a", {1, 2.0}}, :x}, {{"a", {1, 1.5}}, :y}, {{"a", {0, 9.0}}, :z}, {{"", {5, 5.0}}, :w}]']),
     'tlist':('tuple[list[integer], string]',['[{[1, 2], "b"}, {[1], "z"}, {[1, 2], "a"}, {[], "q"}]']),
     'li':('list[integer]',['[[1, 2], [1], [], [1, 2, 3], [0, 9], [1, 2]]']),
     'ls':('list[string]',['[["b"], ["a", "b"], ["a"], []]']),
     'lf':('list[float]',['[[1.5], [1.5, -1.0], [0.5, 9.0], []]']),
     'lb':('list[boolean]',['[[true], [false, true], [], [false]]']),
     'la':('list[atom]',['[[:b], [:a, :b], [:a]]']),
     'lli':('list[list[integer]]',['[[[1], [2]], [[1], [1, 5]], [[0, 9]], [], [[]]]']),
     'lt':('list[tuple[integer, string]]',['[[{1, "b"}], [{1, "a"}, {0, "z"}], [{1, "a"}], []]']),
     'ltn':('list[tuple[integer, list[tuple[string, integer]]]]',['[[{1, [{"a", 2}]}], [{1, [{"a", 1}, {"b", 0}]}], [{1, [{"a", 1}]}], [{0, []}]]']),
    }
    BAD={
     'opt':('option[integer]','[some(1), none, some(0)]'),
     'res':('result[integer, string]','[ok(1), error("x")]'),
     'map':('map[string, integer]','[%{"a" => 1}, %{"b" => 0}]'),
     't0':('tuple[]','[{}, {}]'),
     'topt':('tuple[integer, option[integer]]','[{1, some(1)}, {1, none}]'),
     'lopt':('list[option[integer]]','[[some(1)], [none]]'),
     'fn':('fn[integer, integer]','[fn x -> x end, fn x -> x + 1 end]'),
     'range':('Range','[1..2, 0..5]'),
    }
    STRUCT='defmodule M do\n  struct P do\n    x: integer\n  end\n  type C do\n    red\n    blue\n  end\n  def main() do\n%s\n  end\nend\n'
    one=['Enum.sort(%s)','Enum.sort(%s, :asc)','Enum.sort(%s, :desc)','Enum.max(%s)','Enum.min(%s)','Enum.min_max(%s)',
         'Enum.max(%s, fn -> hd(%s) end)','Enum.min(%s, fn -> hd(%s) end)']
    by=['Enum.sort_by([4, 1, 3, 2, 0], fn i -> Enum.at(%s, rem(i, length(%s)), hd(%s)) end)',
        'Enum.sort_by([4, 1, 3, 2, 0], fn i -> Enum.at(%s, rem(i, length(%s)), hd(%s)) end, :asc)',
        'Enum.sort_by([4, 1, 3, 2, 0], fn i -> Enum.at(%s, rem(i, length(%s)), hd(%s)) end, :desc)',
        'Enum.max_by([4, 1, 3, 2, 0], fn i -> Enum.at(%s, rem(i, length(%s)), hd(%s)) end)',
        'Enum.min_by([4, 1, 3, 2, 0], fn i -> Enum.at(%s, rem(i, length(%s)), hd(%s)) end)',
        'Enum.min_max_by([4, 1, 3, 2, 0], fn i -> Enum.at(%s, rem(i, length(%s)), hd(%s)) end)']
    def fill(t,v): return t.replace('%s',v)
    for name,(ty,vals) in T.items():
        for v in vals:
            add(f'v: list[{ty}] = {v}',*[ 'IO.inspect('+fill(t,'v')+')' for t in one+by],
                'IO.inspect(List.keysort(Enum.map(v, fn x -> {x, 1} end) ++ Enum.map(v, fn x -> {x, 0} end)))',
                'IO.inspect(max(hd(v), Enum.at(v, length(v) - 1, hd(v))))','IO.inspect(min(hd(v), Enum.at(v, length(v) - 1, hd(v))))',
                'IO.inspect(Enum.reduce(v, hd(v), fn x, y -> max(x, y) end))','IO.inspect(Enum.reduce(v, hd(v), fn x, y -> min(y, x) end))')
            # literal directly as argument
            add(f'IO.inspect(Enum.sort({v}))',f'IO.inspect(Enum.max({v}))')
        # empty lists
        add(f'v: list[{ty}] = []','IO.inspect(Enum.sort(v))','IO.inspect(Enum.sort(v, :desc))','IO.inspect(Enum.sort_by(v, fn x -> x end))','IO.inspect(Enum.max(v, fn -> hd(%s) end))'.replace('%s',vals[0]),'IO.inspect(List.keysort(Enum.map(v, fn x -> {x, 1} end)))')
        for f in ['Enum.max(v)','Enum.min(v)','Enum.min_max(v)','Enum.max_by(v, fn x -> x end)','Enum.min_by(v, fn x -> x end)','Enum.min_max_by(v, fn x -> x end)','Enum.sort(v, :up)','Enum.sort_by(v, fn x -> x end, :down)']:
            add(f'v: list[{ty}] = []',f'IO.inspect({f})')
        add(f'v: list[{ty}] = {vals[0]}','IO.inspect(Enum.sort(v, :up))')
        add(f'v: list[{ty}] = {vals[0]}','IO.inspect(Enum.sort_by(v, fn x -> x end, :down))')
        # maps with these as values, sort over a map
        add(f'v: list[{ty}] = {vals[0]}','m = Map.new(Enum.with_index(v), fn p -> {elem(p, 1), elem(p, 0)} end)',
            'IO.inspect(Enum.sort(m))','IO.inspect(Enum.sort(m, :desc))','IO.inspect(Enum.max(m))','IO.inspect(Enum.min(m))','IO.inspect(Enum.min_max(m))',
            'IO.inspect(Enum.sort_by(m, fn p -> elem(p, 1) end))','IO.inspect(Enum.sort_by(m, fn p -> elem(p, 1) end, :desc))','IO.inspect(Enum.max_by(m, fn p -> elem(p, 1) end))','IO.inspect(Enum.min_by(m, fn p -> elem(p, 1) end))','IO.inspect(Enum.min_max_by(m, fn p -> elem(p, 1) end))')
        # operators in ordinary code
        for op in ['<','<=','>','>=']:
            add(f'v: list[{ty}] = {vals[0]}',f'IO.inspect(hd(v) {op} hd(tl(v)))' if vals[0].count(',')>0 else f'IO.inspect(hd(v) {op} hd(v))')
    for name,(ty,v) in BAD.items():
        for t in one[:6]+by+['List.keysort(Enum.map(%s, fn x -> {x, 1} end))','max(hd(%s), hd(%s))','min(hd(%s), hd(%s))','hd(%s) < hd(%s)','hd(%s) >= hd(%s)']:
            add(f'v: list[{ty}] = {v}','IO.inspect('+fill(t,'v')+')')
    for t in one[:6]+['Enum.sort_by(%s, fn p -> p.x end)','Enum.sort_by(%s, fn p -> p end)','max(hd(%s), hd(%s))','hd(%s) < hd(%s)']:
        P.append(STRUCT % ('v = [%P{x: 2}, %P{x: 1}]\nIO.inspect('+fill(t,'v')+')'))
        P.append(STRUCT % ('v = [C.red, C.blue]\nIO.inspect('+fill(t,'v')+')') if 'p.x' not in t else STRUCT % 'IO.inspect(1)')
    # ranges and other enumerables
    for t in ['Enum.sort(%s)','Enum.sort(%s, :desc)','Enum.sort(%s, :asc)','Enum.max(%s)','Enum.min(%s)','Enum.min_max(%s)','Enum.sort_by(%s, fn x -> 0 - x end)','Enum.sort_by(%s, fn x -> {rem(x, 2), x} end, :desc)','Enum.max_by(%s, fn x -> rem(x, 3) end)','Enum.min_by(%s, fn x -> [rem(x, 3)] end)','Enum.min_max_by(%s, fn x -> rem(x, 3) end)','Enum.max(%s, fn -> 0 end)','Enum.min(%s, fn -> 0 end)','Enum.sort(%s, fn a, b -> a >= b end)','Enum.max(%s, fn a, b -> a >= b end)','Enum.min(%s, fn a, b -> a <= b end)','Enum.sort_by(%s, fn x -> rem(x, 3) end, fn a, b -> a >= b end)','Enum.max_by(%s, fn x -> rem(x, 3) end, fn a, b -> a >= b end)','Enum.min_by(%s, fn x -> rem(x, 3) end, fn a, b -> a <= b end)','Enum.max(%s, fn a, b -> a >= b end, fn -> 0 end)','Enum.min(%s, fn a, b -> a <= b end, fn -> 0 end)']:
        for r in ['1..5','5..1//-1','1..0//1','1..10//3']:
            add('IO.inspect('+fill(t,r)+')')
        add('IO.inspect('+fill(t,'[5, 3, 8, 1, 9, 2]')+')')
        add('IO.inspect('+fill(t,'%{3 => 1, 1 => 2, 2 => 0}').replace('rem(x, 3)','elem(x, 1)').replace('rem(x, 2), x','elem(x, 1), elem(x, 0)').replace('0 - x','0 - elem(x, 1)').replace('-> 0 end','-> {0, 0} end')+')')
    # keyed maps of other key types
    for m in ['%{"b" => 1, "a" => 2}','%{:b => 1.5, :a => 0.5}','%{true => [1], false => [0]}','%{1.5 => "x", -1.0 => "y"}','%{2 => {1, "a"}, 1 => {1, "b"}}']:
        for t in ['Enum.sort(%s)','Enum.sort(%s, :desc)','Enum.max(%s)','Enum.min(%s)','Enum.min_max(%s)','Enum.sort_by(%s, fn p -> elem(p, 1) end)','Enum.max_by(%s, fn p -> elem(p, 1) end)','Enum.min_by(%s, fn p -> elem(p, 0) end)','Enum.sort_by(%s, fn p -> p end, :desc)','Enum.min_max_by(%s, fn p -> elem(p, 1) end)']:
            add('IO.inspect('+fill(t,m)+')')
    for m in ['%{1 => some(1), 2 => none}','%{1 => %{1 => 1}}']:
        for t in ['Enum.sort(%s)','Enum.sort(%s, :desc)','Enum.max(%s)','Enum.min(%s)','Enum.min_max(%s)','Enum.sort_by(%s, fn p -> elem(p, 0) end)','Enum.sort_by(%s, fn p -> elem(p, 1) end)']:
            add('IO.inspect('+fill(t,m)+')')
    # stability and call order of user functions
    add('v = [{2, "a"}, {1, "b"}, {2, "c"}, {1, "d"}, {0, "e"}, {2, "f"}]',
        'IO.inspect(Enum.sort_by(v, fn p -> elem(p, 0) end))','IO.inspect(Enum.sort_by(v, fn p -> elem(p, 0) end, :desc))','IO.inspect(Enum.sort_by(v, fn p -> elem(p, 0) end, :asc))',
        'IO.inspect(Enum.max_by(v, fn p -> elem(p, 0) end))','IO.inspect(Enum.min_by(v, fn p -> 0 - elem(p, 0) end))','IO.inspect(Enum.min_max_by(v, fn p -> rem(elem(p, 0), 2) end))',
        'IO.inspect(List.keysort(v))','IO.inspect(List.keysort(Enum.map(v, fn p -> {elem(p, 1) < "d", elem(p, 0)} end)))')
    for f in ['Enum.sort_by(v, fn x -> IO.inspect(x) end)','Enum.sort_by(v, fn x -> IO.inspect(x) end, :desc)','Enum.max_by(v, fn x -> IO.inspect(x) end)','Enum.min_by(v, fn x -> IO.inspect(x) end)','Enum.min_max_by(v, fn x -> IO.inspect(x) end)',
              'Enum.sort_by(v, fn x -> IO.inspect(x) end, fn a, b -> IO.inspect({a, b}) == {0, 0} or a <= b end)','Enum.max_by(v, fn x -> IO.inspect(x) end, fn a, b -> IO.inspect({a, b}) == {0, 0} or a >= b end)','Enum.min_by(v, fn x -> IO.inspect(x) end, fn a, b -> IO.inspect({a, b}) == {0, 0} or a <= b end)',
              'Enum.sort(v, fn a, b -> IO.inspect({a, b}) == {0, 0} or a <= b end)','Enum.max(v, fn a, b -> IO.inspect({a, b}) == {0, 0} or a >= b end)','Enum.min(v, fn a, b -> IO.inspect({a, b}) == {0, 0} or a <= b end)']:
        add('v = [3, 1, 2, 3, 1]',f'IO.inspect({f})')
    # floats with NaN and infinities
    for vals in ['[1.0, nan, 0.5]','[nan, 1.0, 0.5, nan, -1.0]','[3.0, 2.0, nan, 1.0, 0.0]','[inf, 0.0 - inf, 0.0]','[nan]','[nan, nan]','[2.0, nan, 1.0, nan, 0.0, 5.0, nan, 4.0, 3.0]']:
        for t in one+['Enum.sort_by(%s, fn x -> x end)','Enum.sort_by(%s, fn x -> x end, :desc)','Enum.max_by(%s, fn x -> x end)','Enum.min_by(%s, fn x -> x end)','Enum.min_max_by(%s, fn x -> x end)','Enum.sort(Enum.map(%s, fn x -> {x, 1} end))','Enum.sort(Enum.map(%s, fn x -> [x, 1.0] end), :desc)','Enum.max(Enum.map(%s, fn x -> {1, x} end))','Enum.min(Enum.map(%s, fn x -> [x] end))','List.keysort(Enum.map(%s, fn x -> {x, x} end))','List.sort(%s)','max(hd(%s), 1.0)','min(hd(%s), 1.0)','max(1.0, hd(%s))','min(1.0, hd(%s))','max({hd(%s), 2}, {1.0, 1})','min([hd(%s), 2.0], [1.0, 1.0])']:
            add(NAN+'v = '+vals,'IO.inspect('+fill(t,'v')+')')
    # long lists (beyond the 20-element blocks of the stable sort), random
    for n in [21, 40, 41, 64, 100]:
        xs=[random.randrange(0,12) for _ in range(n)]
        add('v = '+str(xs),'IO.inspect(Enum.sort(v))','IO.inspect(Enum.sort(v, :desc))','IO.inspect(Enum.sort_by(Enum.with_index(v), fn p -> elem(p, 0) end))','IO.inspect(Enum.sort_by(Enum.with_index(v), fn p -> elem(p, 0) end, :desc))','IO.inspect(Enum.sort(Enum.map(v, fn x -> {rem(x, 3), [x, 1]} end)))','IO.inspect(List.keysort(Enum.with_index(v)))','IO.inspect(Enum.min_max(v))')
        fs=[random.choice(['nan','1.0','2.0','0.5','3.5','-1.0','inf']) for _ in range(n)]
        add(NAN+'v = ['+', '.join(fs)+']','IO.inspect(Enum.sort(v))','IO.inspect(Enum.sort(v, :desc))','IO.inspect(Enum.sort_by(Enum.with_index(v), fn p -> elem(p, 0) end))','IO.inspect(Enum.sort_by(Enum.with_index(v), fn p -> elem(p, 0) end, :desc))','IO.inspect(Enum.sort(Enum.map(v, fn x -> {x, 1} end)))','IO.inspect(List.keysort(Enum.with_index(v)))','IO.inspect(Enum.min_max(v))','IO.inspect(List.sort(v))')
    # generic user functions: upstream gives no order to a type variable
    P.append('defmodule M do\n  def big(x: list[t]): t do\n    Enum.max(x)\n  end\n  def main() do\n    IO.inspect(big([1, 2]))\n  end\nend\n')
    P.append('defmodule M do\n  def srt(x: list[t]): list[t] do\n    Enum.sort(x)\n  end\n  def main() do\n    IO.inspect(srt([1, 2]))\n  end\nend\n')
    P.append('defmodule M do\n  def lt(x: t, y: t): boolean do\n    x < y\n  end\n  def main() do\n    IO.inspect(lt(1, 2))\n  end\nend\n')
    P.append('defmodule M do\n  def lt(x: ord, y: ord): boolean do\n    x < y\n  end\n  def main() do\n    IO.inspect(lt(1, 2))\n  end\nend\n')
    P.append('defmodule M do\n  def lt(x: ord, y: ord): ord do\n    max(x, y)\n  end\n  def main() do\n    IO.inspect(lt(1, 2))\n  end\nend\n')
    P.append('defmodule M do\n  def by(x: list[t], f: fn[t, k]): list[t] do\n    Enum.sort_by(x, f)\n  end\n  def main() do\n    IO.inspect(by([1, 2], fn x -> 0 - x end))\n  end\nend\n')
    P.append('defmodule M do\n  def by(x: list[t], f: fn[t, integer]): list[t] do\n    Enum.sort_by(x, f)\n  end\n  def main() do\n    IO.inspect(by([{1, some(2)}, {0, none}], fn x -> elem(x, 0) end))\n    IO.inspect(Enum.max_by([some(2), none, some(5)], fn x -> case x do\n      some(v) -> [v]\n      none -> []\n    end end))\n  end\nend\n')
    P.append('defmodule M do\n  def w(x: list[t], f: fn[t, t, boolean]): list[t] do\n    Enum.sort(x, f)\n  end\n  def main() do\n    IO.inspect(w([some(1), none, some(0)], fn a, b -> a == none or b != none end))\n  end\nend\n')
    # generic structs with many parameters stay comparable; sort_by keys from them
    P.append('defmodule M do\n  struct W[a, b, c, d, e, f, g] do\n    p: a\n    q: b\n    r: c\n    s: d\n    t: e\n    u: f\n    v: g\n  end\n  def main() do\n    x = [%W{p: 2, q: "a", r: 1.5, s: true, t: :k, u: [1], v: {1, 2}}, %W{p: 1, q: "b", r: 0.5, s: false, t: :j, u: [0], v: {0, 2}}]\n    IO.inspect(Enum.sort_by(x, fn w -> {w.v, w.u} end))\n    IO.inspect(Enum.max_by(x, fn w -> w.q end))\n    IO.inspect(Enum.uniq(x ++ x) == x)\n    IO.inspect(Enum.sort(Enum.map(x, fn w -> {w.r, w.t, w.s} end)))\n  end\nend\n')

    random.seed(11)
    def rtype(d):
        r=random.random()
        if d==0 or r<0.45: return random.choice(['integer','integer','string','float','boolean','atom'])
        if r<0.7: return 'list['+rtype(d-1)+']'
        return 'tuple['+', '.join(rtype(d-1) for _ in range(random.choice([1,2,2,3,4,6])))+']'
    def split(t):
        inner=t[t.index('[')+1:-1]; parts=[]; depth=0; cur=''
        for ch in inner:
            if ch=='[': depth+=1
            if ch==']': depth-=1
            if ch==',' and depth==0: parts.append(cur.strip()); cur=''
            else: cur+=ch
        parts.append(cur.strip()); return parts
    def rval(t,nan):
        if t=='integer': return str(random.choice([0,1,2,3,-1,-7,10,100,9223372036854775807,-9223372036854775807]))
        if t=='string': return '"'+random.choice(['','a','b','ab','abc','B','z','aa','é','zz y','a b'])+'"'
        if t=='float': return random.choice(['0.0','-0.0','1.5','-2.25','1.0e10','3.0','1.5']+(['nan','nan','inf','0.0 - inf'] if nan else []))
        if t=='boolean': return random.choice(['true','false'])
        if t=='atom': return ':'+random.choice(['a','b','ok','error','zed','B_x'])
        if t.startswith('list['):
            e=split(t)[0]; return '['+', '.join(rval(e,nan) for _ in range(random.choice([0,1,1,2,3])))+']'
        return '{'+', '.join(rval(e,nan) for e in split(t))+'}'
    FUNS=['Enum.sort(v)','Enum.sort(v, :asc)','Enum.sort(v, :desc)','Enum.max(v)','Enum.min(v)','Enum.min_max(v)','Enum.max(v, fn -> hd(v) end)','Enum.min(v, fn -> hd(v) end)',
     'Enum.sort_by(Enum.with_index(v), fn p -> elem(p, 0) end)','Enum.sort_by(Enum.with_index(v), fn p -> elem(p, 0) end, :desc)','Enum.sort_by(Enum.with_index(v), fn p -> elem(p, 0) end, :asc)',
     'Enum.max_by(Enum.with_index(v), fn p -> elem(p, 0) end)','Enum.min_by(Enum.with_index(v), fn p -> elem(p, 0) end)','Enum.min_max_by(Enum.with_index(v), fn p -> elem(p, 0) end)',
     'List.keysort(Enum.with_index(v))','max(hd(v), hd(tl(v)))','min(hd(v), hd(tl(v)))','Enum.reduce(v, fn x, y -> max(y, x) end)','Enum.reduce(v, fn x, y -> min(y, x) end)',
     'v |> Enum.sort() |> Enum.reverse()','v |> Enum.sort(:desc) |> Enum.take(2)','Enum.sort(Enum.map(v, fn x -> {x, x} end))','Enum.max(Enum.map(v, fn x -> [x, x] end))','Enum.sort(Enum.chunk_every(v, 2))',
     'Enum.sort(Map.new(Enum.with_index(v), fn p -> {elem(p, 1), elem(p, 0)} end), :desc)','Enum.min_max(Map.new(Enum.with_index(v), fn p -> {elem(p, 1), elem(p, 0)} end))']
    for i in range(150):
        nan=i%3==0
        t=rtype(3)
        n=random.choice([2,3,5,8,13,25,45])
        vals=[rval(t,nan and 'float' in t) for _ in range(random.choice([2,3,4]))]+[None]
        seq=[random.choice(vals[:-1]) if random.random()<0.5 else rval(t,nan and 'float' in t) for _ in range(n)]
        add((NAN if nan else '')+f'v: list[{t}] = ['+', '.join(seq)+']',*['IO.inspect('+f+')' for f in FUNS])
    # function references and captures
    add('IO.inspect(Enum.map([[3, 1], [2, 0]], &Enum.sort/1))','IO.inspect(Enum.map([[3, 1], [2, 0]], &Enum.max/1))','IO.inspect(Enum.reduce([3, 9, 2], &max/2))','IO.inspect(Enum.reduce([{3, "a"}, {1, "b"}], &min/2))',
        'IO.inspect(Enum.map([[{2, "a"}, {1, "z"}]], &Enum.min_max/1))','f: fn[list[string], list[string]] = &Enum.sort/1','IO.inspect(f(["b", "a"]))','IO.inspect(Enum.sort_by([{2, "a"}, {1, "z"}], &elem(&1, 1)))','IO.inspect(Enum.max_by(["aa", "b"], &String.length/1))',
        'IO.inspect(Enum.zip_with([1, 5], [4, 2], &max/2))','IO.inspect(Enum.map([{1, 2}, {5, 3}], fn {a, b} -> max(a, b) end))')
    for line in ['IO.inspect(Enum.map([[some(1)]], &Enum.sort/1))','IO.inspect(Enum.reduce([some(3)], &max/2))','IO.inspect(Enum.sort([]))','IO.inspect(Enum.max([]))','IO.inspect(Enum.sort([[]]))','IO.inspect(Enum.min_max([{}]))',
                 'IO.inspect(Enum.sort_by([1, 2], fn x -> some(x) end))','IO.inspect(Enum.max_by([1, 2], fn x -> %{x => 1} end))','IO.inspect(Enum.sort_by([1, 2], fn x -> {x, none} end, :desc))','IO.inspect(List.keysort([{some(1), 2}]))','IO.inspect(List.keysort([{{1, some(1)}, 2}]))',
                 'IO.inspect(Enum.sort(["a", "b"], :asc, :desc))','IO.inspect(Enum.sort([1, 2], "asc"))','IO.inspect(Enum.max([1, 2], 3))','IO.inspect(Enum.sort_by([1, 2], fn x -> x end, 1))','IO.inspect(max(1, "a"))','IO.inspect(max({1, 2}, {1, "a"}))','IO.inspect(min([1], [1.0]))','IO.inspect(max(1, 2.0))',
                 'IO.inspect(Enum.sort([1, 2.0]))','IO.inspect(Enum.sort(5))','IO.inspect(Enum.sort("abc"))','IO.inspect(Enum.max({3, 1}))','IO.inspect(List.sort([true, false]))','IO.inspect(List.sort([{1, 2}]))','IO.inspect(List.sort([:b, :a]))','IO.inspect(List.sort([[1]]))',
                 'IO.inspect(Enum.oms([2, 1], fn a, b -> a < b end))','IO.inspect(Enum.o_sort([2, 1], fn a, b -> a < b end))','IO.inspect(Enum.o_pdq([2, 1]))','IO.inspect(Enum.o_keys([2, 1], [1, 2], fn a, b -> a < b end))','IO.inspect(Enum.o_first([2, 1], fn a, b -> a < b end))','IO.inspect(Enum.map([[2, 1]], &Enum.o_pdq/1))','f = Enum.o_dir(:asc, fn a, b -> a < b end)','IO.inspect(Enum.osf([2, 1], fn a, b -> a < b end))','IO.inspect(Enum.o_stable([2, 1], fn a, b -> a < b end))','IO.inspect(Enum.o_unstable([2, 1], fn a, b -> a < b end))','IO.inspect(Enum.opq([2, 1]))','IO.inspect(Enum.okp([2, 1], [1, 2], fn a, b -> a < b end))','IO.inspect(Enum.oex([2, 1], fn a, b -> a < b end))',
                 'IO.inspect(List.sort([3, 1, 2]))','IO.inspect(List.sort(["b", "a", ""]))','IO.inspect(List.sort([2.5, -1.0, 0.0, -0.0]))','x: list[integer] = []\nIO.inspect(List.sort(x))','IO.inspect(Enum.sort(1..0//1))','IO.inspect(Enum.sort_by(1..0//1, fn x -> x end))','IO.inspect(Enum.sort(%{}))',
                 'm: map[integer, string] = %{}\nIO.inspect(Enum.sort(m))\nIO.inspect(Enum.sort_by(m, fn p -> elem(p, 1) end, :desc))\nIO.inspect(Enum.max(m, fn -> {0, "none"} end))','m: map[integer, string] = %{}\nIO.inspect(Enum.max(m))','m: map[integer, string] = %{}\nIO.inspect(Enum.min_max_by(m, fn p -> p end))',
                 'IO.inspect(Enum.max([1, 2], fn a, b -> a >= b end, fn -> 0 end))\ne: list[integer] = []\nIO.inspect(Enum.max(e, fn a, b -> a >= b end, fn -> 0 end))\nIO.inspect(Enum.min(%{1 => 2, 0 => 5}, fn a, b -> elem(a, 1) <= elem(b, 1) end, fn -> {0, 0} end))\nIO.inspect(Enum.max(%{1 => 2, 0 => 5}, fn a, b -> elem(a, 1) >= elem(b, 1) end))\nIO.inspect(Enum.sort(%{1 => 2, 0 => 5}, fn a, b -> elem(a, 1) >= elem(b, 1) end))\nIO.inspect(Enum.sort_by(%{1 => 2, 0 => 5}, fn a -> elem(a, 1) end, fn a, b -> a >= b end))\nIO.inspect(Enum.max_by(%{1 => 2, 0 => 5}, fn a -> elem(a, 1) end, fn a, b -> a >= b end))\nIO.inspect(Enum.min_by(%{1 => 2, 0 => 5}, fn a -> elem(a, 1) end, fn a, b -> a <= b end))',
                 ]:
        add(line)
    # many calls of a compound order allocate nothing: three million would not fit the arena
    add('a = {1, "a", [2.5]}','b = {1, "a", [2.0]}','r = Enum.to_list(1..100000)','IO.inspect(Enum.reduce(1..30, a, fn j, o -> Enum.reduce(r, o, fn i, acc -> if i > 0 do max(acc, b) else min(acc, b) end end) end))')
    add('v = [[3, 1], [2, 9]]','IO.inspect(Enum.reduce(1..3000, 0, fn i, acc -> acc + hd(Enum.max(v)) end))')
    # failures in user functions under library calls, and inside try
    # failures of the library inside try
    P.append('try do\n  e: list[integer] = []\n  IO.inspect(Enum.max(e))\nrescue\n  x -> IO.puts("rescued " <> x)\nend\nIO.inspect(Enum.sort([2, 1], :desc))')
    P.append('e: list[integer] = []\nx = try do\n  Enum.sort(e, :sideways)\nrescue\n  m -> [String.length(m)]\nafter\n  IO.puts("after")\nend\nIO.inspect(x)\nIO.inspect(Enum.min(e))')
    P.append('defmodule M do\n  def low(e: list[float]): float do\n    try do\n      Enum.min(e)\n    after\n      IO.puts("left")\n    end\n  end\n  def main() do\n    IO.inspect(low([2.5, 1.5]))\n    IO.inspect(low([]))\n  end\nend\n')
    P.append('defmodule M do\n  def main() do\n    e: list[integer] = []\n    r = try do\n      Enum.map([1], fn y -> y + Enum.max(e) end)\n    rescue\n      m -> raise("again: " <> m)\n    end\n    IO.inspect(r)\n  end\nend\n')
    P.append('e: list[integer] = []\nIO.inspect(Enum.map([[1], e], fn l ->\n  try do\n    Enum.min_max(l)\n  rescue\n    m -> {0, 0}\n  end\nend))\nIO.inspect(Enum.sort_by([[1], e, [5]], fn l ->\n  try do\n    Enum.max(l)\n  rescue\n    m -> 3\n  end\nend, :desc))\nIO.inspect(Enum.max_by([[1], e, [5]], fn l -> Enum.max(l) end))')
    add('IO.inspect(Enum.sort_by([3, 1, 2], fn a -> if a == 1 do raise("key " <> to_string(a)) else a end end))')
    add('IO.inspect(Enum.sort_by([3, 1, 2], fn a ->','  10 / (a - 1)','end, :desc))')
    add('IO.inspect(Enum.max_by([3, 1, 2], fn a -> hd(Enum.drop([a], a - 2)) end))')
    add('IO.inspect(Enum.min_max_by([3, 1, 2], fn a -> a end,','  :x))')
    add('x = [5]','IO.inspect(x','  |> Enum.drop(1)','  |> Enum.min())')
    add('x = [5]','y = Enum.sort(x,','  :sideways)','IO.inspect(y)')
    add('IO.inspect(Enum.map([[1], []], &Enum.max/1))')
    add('IO.inspect(Enum.map([[1], []], fn l -> Enum.min_max(l) end))')
    P.append('defmodule M do\n  def low(x: list[integer]): integer do\n    Enum.min(x)\n  end\n  def main() do\n    IO.inspect(low([4, 2]))\n    IO.inspect(Enum.map([[1], []], &low/1))\n  end\nend\n')
    P.append('defmodule Other do\n  def low(x: list[tuple[integer, string]]): tuple[integer, string] do\n    x |> Enum.reverse() |> Enum.min()\n  end\nend\ndefmodule M do\n  def main() do\n    IO.inspect(Other.low([{4, "a"}, {2, "b"}]))\n    IO.inspect(Other.low([]))\n  end\nend\n')

    add('IO.inspect({1, 2} |> max({0, 5}))','IO.inspect([2.5] |> min([2.5, 0.0]))','IO.inspect(Kernel.max({1, "b"}, {1, "a"}))','IO.inspect(Kernel.min(:b, :a))','IO.inspect(max(true, false))','IO.inspect(min("b", "a"))','IO.inspect(max(-1, 3) + min(2, 9))','IO.inspect(max(1.5, -0.0))','IO.inspect(min(0.0, -0.0))','IO.inspect(min(-0.0, 0.0))','IO.inspect(Enum.sort([0.0, -0.0, 0.0]))','IO.inspect(Enum.max([-0.0, 0.0]))','IO.inspect(Enum.min([0.0, -0.0]))')
    add('IO.inspect(Kernel.max(some(1), none))')
    add('IO.inspect(Enum.sort(["b", "a"]) < ["c"])')
    add('IO.inspect(Enum.max([1, 2]) < Enum.min([3, 4]))','IO.inspect(Enum.max(["a"]) <= Enum.min(["a", "b"]))','IO.inspect(Enum.min([:b, :a]) > :a)','IO.inspect(Enum.max([1.5]) >= 1.5)')
    P.extend(enumerables())
    return [p if 'defmodule' in p else 'defmodule M do\n  def main() do\n'+p.strip('\n')+'\n  end\nend\n' for p in P]


def enumerables():
    """Every ordered function over a set, a stream, a range and a map, with
    what a stream and the function write as the one is read and the other
    called; compound map keys; a regex where an order is needed."""
    P=[]
    srcs={'set':'MapSet.new([3, 1, 2, 5, 4])','setT':'MapSet.new([{2, "a"}, {1, "b"}, {1, "a"}])','stream':'Stream.map([3, 1, 2, 5, 4], fn x -> x * 2 end)','streamT':'Stream.map([3, 1, 2], fn x -> {rem(x, 2), [x]} end)','range':'1..6','rstep':'10..1//-3','map':'%{3 => "c", 1 => "a", 2 => "b"}','list':'[3, 1, 2, 5, 4]','filter':'Stream.filter(1..9, fn x -> rem(x, 2) == 1 end)','take':'Stream.take(Stream.cycle([2, 9, 4]), 5)','iter':'Stream.iterate(7, fn x -> rem(x * 5, 11) end) |> Stream.take(6)','sstr':'String.splitter("b a c", " ")'}
    fs=['Enum.sort(%s)','Enum.sort(%s, :desc)','Enum.sort(%s, :asc)','Enum.sort(%s, fn a, b -> a >= b end)','Enum.max(%s)','Enum.min(%s)','Enum.min_max(%s)','Enum.max(%s, fn -> hd(Enum.take(%s, 1)) end)','Enum.min(%s, fn -> hd(Enum.take(%s, 1)) end)',
        'Enum.max(%s, fn a, b -> a >= b end)','Enum.min(%s, fn a, b -> a <= b end)','Enum.max(%s, fn a, b -> a >= b end, fn -> hd(Enum.take(%s, 1)) end)','Enum.min(%s, fn a, b -> a <= b end, fn -> hd(Enum.take(%s, 1)) end)',
        'Enum.sort_by(%s, fn x -> {x != hd(Enum.take(%s, 1)), x} end)','Enum.sort_by(%s, fn x -> [x] end, :desc)','Enum.sort_by(%s, fn x -> x end, fn a, b -> a >= b end)','Enum.max_by(%s, fn x -> {x == hd(Enum.take(%s, 1)), x} end)','Enum.min_by(%s, fn x -> [x] end)','Enum.min_max_by(%s, fn x -> x end)',
        'Enum.max_by(%s, fn x -> [x] end, fn a, b -> a >= b end)','Enum.min_by(%s, fn x -> x end, fn a, b -> a <= b end)']
    for k,v in srcs.items():
        P.append('\n'.join(['e = '+v]+['IO.inspect('+f.replace('%s','e')+')' for f in fs]))
        for f in fs[:7]+fs[13:19]: P.append('IO.inspect('+f.replace('%s',v)+')')
    for v in ['MapSet.new([1]) |> MapSet.delete(1)','Stream.filter([1, 2], fn x -> x > 5 end)','1..0//1','Stream.take([1], 0)']:
        for f in ['Enum.sort(%s)','Enum.sort_by(%s, fn x -> x end, :desc)','Enum.max(%s, fn -> 0 end)','Enum.min(%s, fn a, b -> a <= b end, fn -> 0 end)','Enum.max(%s)','Enum.min_max(%s)','Enum.max_by(%s, fn x -> x end)','Enum.min_by(%s, fn x -> x end, fn a, b -> a <= b end)','Enum.min(%s, fn a, b -> a <= b end)','Enum.min_max_by(%s, fn x -> x end)','Enum.sort(%s, :up)']:
            P.append('e = '+v+'\nIO.inspect('+f.replace('%s','e')+')')
    st='Stream.map([3, 1, 2, 3], fn x -> IO.inspect({:read, x})\n  x end)'
    for f in ['Enum.sort(%s)','Enum.sort(%s, :desc)','Enum.sort(%s, fn a, b -> IO.inspect({a, b}) == {0, 0} or a <= b end)','Enum.max(%s)','Enum.min(%s)','Enum.min_max(%s)','Enum.max(%s, fn -> 0 end)','Enum.min(%s, fn -> 0 end)',
              'Enum.max(%s, fn a, b -> IO.inspect({a, b}) == {0, 0} or a >= b end)','Enum.min(%s, fn a, b -> IO.inspect({a, b}) == {0, 0} or a <= b end)','Enum.max(%s, fn a, b -> IO.inspect({a, b}) == {0, 0} or a >= b end, fn -> 0 end)','Enum.min(%s, fn a, b -> IO.inspect({a, b}) == {0, 0} or a <= b end, fn -> 0 end)',
              'Enum.sort_by(%s, fn x -> IO.inspect(x) end)','Enum.sort_by(%s, fn x -> IO.inspect(x) end, :desc)','Enum.sort_by(%s, fn x -> IO.inspect(x) end, fn a, b -> IO.inspect({a, b}) == {0, 0} or a <= b end)',
              'Enum.max_by(%s, fn x -> IO.inspect(x) end)','Enum.min_by(%s, fn x -> IO.inspect(x) end)','Enum.min_max_by(%s, fn x -> IO.inspect(x) end)',
              'Enum.max_by(%s, fn x -> IO.inspect(x) end, fn a, b -> IO.inspect({a, b}) == {0, 0} or a >= b end)','Enum.min_by(%s, fn x -> IO.inspect(x) end, fn a, b -> IO.inspect({a, b}) == {0, 0} or a <= b end)','List.keysort(Enum.to_list(Stream.map(%s, fn x -> {x, 1} end)))']:
        P.append('s = '+st+'\nIO.inspect('+f.replace('%s','s')+')')
        P.append('IO.inspect('+f.replace('%s','MapSet.new([3, 1, 2])')+')')
        P.append('IO.inspect('+f.replace('%s','4..1//-1')+')')
        P.append('IO.inspect('+f.replace('%s','%{3 => 1, 1 => 2}').replace('{0, 0}','{{0, 0}, {0, 0}}')+')')
    for v in ['MapSet.new([1, 2])','Stream.map([1], fn x -> some(x) end)','Stream.map([1], fn x -> %{x => 1} end)','1..3']:
        for f in ['Enum.sort_by(%s, fn x -> some(x) end)','Enum.max_by(%s, fn x -> {x, none} end)','Enum.sort(Stream.map(%s, fn x -> some(x) end))','Enum.min_max(Stream.map(%s, fn x -> ok(x) end))','List.keysort(%s)','max(%s, %s)','List.sort(%s)']:
            P.append('IO.inspect('+f.replace('%s',v)+')')
    P.append('IO.inspect(max(MapSet.new([1]), MapSet.new([2])))')
    P.append('IO.inspect(Enum.sort([MapSet.new([1])]))')
    P.append('IO.inspect(Enum.sort([1..2, 0..1]))')
    P.extend(['IO.inspect(List.first(MapSet.new([1])))', 'IO.inspect(List.first(1..3))', 'IO.inspect(List.keysort(MapSet.new([{1, 2}])))', 'IO.inspect(List.keysort(Stream.map([1], fn x -> {x, x} end)))', 'IO.inspect(List.sort(Stream.map([1], fn x -> x end)))', 'IO.inspect(List.last(MapSet.new([1])))', 'IO.inspect(List.delete(1..3, 2))', 'IO.inspect(List.flatten([1..3]))', 'IO.inspect(List.zip([1..3, 4..6]))', 'IO.inspect(List.keyfind(%{1 => 2}, 1, 0))', 'IO.inspect(List.foldl(MapSet.new([1, 2]), 0, fn x, a -> x + a end))', 'IO.inspect(List.sort(%{1 => 2}))', 'IO.inspect(max(1..2, 1..3))\n', 'IO.inspect(Enum.sort([~r/a/, ~r/b/]))', 'IO.inspect(Enum.max([~r/a/]))', 'IO.inspect(max(~r/a/, ~r/b/))', 'IO.inspect(Enum.sort_by(["a"], fn x -> ~r/a/ end))', 'IO.inspect(Enum.min_max([{1, ~r/a/}]))', 'IO.inspect(List.keysort([{~r/a/, 1}]))', 'IO.inspect(~r/a/ < ~r/b/)', 'IO.inspect(Enum.sort_by(["b", "a"], fn x -> x =~ ~r/a/ end))', 'IO.inspect(Enum.max_by(["b1", "a22", "c"], fn x -> Regex.scan(~r/\\d/, x) end))', 'IO.inspect(Enum.sort(Regex.split(~r/,/, "b,a,c")))', 'IO.inspect(%{~r/a/ => 1})', 'IO.inspect(Enum.sort(String.split("b a c", ~r/ /), :desc))\n', 'defmodule M do\n  def least(s: stream[a], l: fn[a, a, boolean]): option[a] do\n    start: option[a] = none\n    Enum.reduce(s, start, fn x, b ->\n      case b do\n        some(y) -> if l(x, y) do some(x) else b end\n        none -> some(x)\n      end\n    end)\n  end\n  def main() do\n    s = Stream.map([3, 1, 2, 3], fn x -> IO.inspect({:read, x})\n      x end)\n    IO.inspect(Enum.reduce(s, 0, fn x, a -> IO.inspect(x) + a end))\n    IO.inspect(least(s, fn a, b -> IO.inspect({a, b}) == {0, 0} or a < b end))\n  end\nend\n'])
    # tuple keys of 45 and 60 parts
    for n in (45,60):
        parts=(['1','"a"','2.5',':k','true']*12)[:n-1]
        a,b='{'+', '.join(parts+['true'])+'}','{'+', '.join(parts+['false'])+'}'
        P.append(f'a = {a}\nb = {b}\nIO.inspect(a == b)\nm = %{{a => 1, b => 2}}\nIO.inspect(Map.get(m, b))\nIO.inspect(map_size(Map.put(m, a, 5)))\ns = MapSet.new([a, b, a])\nIO.inspect(MapSet.size(s))\nIO.inspect(MapSet.member?(s, b))\nIO.inspect(Map.has_key?(Map.delete(m, a), a))\nIO.inspect(elem(max(a, b), {n-1}))\nIO.inspect(elem(hd(Enum.sort([a, b])), {n-1}))')
    return P


def pinned(source):
    with tempfile.TemporaryDirectory(prefix='alchem-ordering-') as d:
        (Path(d)/'p.alc').write_text(source)
        env=dict(os.environ,GOTOOLCHAIN='local',GOPROXY='off',GOFLAGS='-mod=mod')
        run=subprocess.run([str(ROOT/'build/dev/alchem-upstream'),'run','p.alc'],cwd=d,env=env,capture_output=True,timeout=300)
        place=re.compile(re.escape(d)+r'/p\.alc|(?<![\w/])p\.alc')
        stderr=place.sub('<stdin>',run.stderr.decode())
        if run.returncode in (0,2):
            return [source,run.returncode,run.stdout.decode(),stderr]
        assert run.returncode==1 and run.stdout==b'' and stderr.startswith('<stdin>:'),(source,run)
        return [source,None,'',stderr.split('\n')[0]]


if __name__=='__main__':
    with ThreadPoolExecutor(4) as pool:cases=list(pool.map(pinned,programs()))
    data=lzma.compress(json.dumps(cases,separators=(',',':')).encode(),preset=9|lzma.PRESET_EXTREME)
    (ROOT/'harness/ordering-cases.json.xz').write_bytes(data)
    print(f'Ordering cases: {len(cases)} programs ({sum(1 for c in cases if c[1] is None)} rejected), {len(data)} bytes')
