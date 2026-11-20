#!/usr/bin/env python3
"""Regenerate harness/list-cases.json.xz: random programs that share and extend
lists, with what the pinned compiler prints for each. Not used by normal builds.

A list of the self-hosted compiler lies in a block other lists may lie in too
(spec/alchem-lists.md): a tail is an address inside its list, and an element
put before a list is written below it when the block has room there that no
other list took. A scenario therefore makes lists from one another in every
way the language has (prepending one or several elements, twice onto the same
list, onto tails and tails of tails, onto lists held by closures, maps,
structs, tuples and other lists, sent to a process and
back, inside for and reduce, through ++, --, reverse, take, drop, slice, map,
filter, sort and uniq) and then prints every list it made, the oldest first:
a write into a neighbour shows as a difference from the pinned compiler.
(A list cannot be a map key: the pinned compiler rejects it.)

Every program is run by build/dev/alchem-upstream (the pinned compiler behind
its memory and time ceiling). A case is the source and the standard output of
the run; the status is 0 and standard error empty for all of them.

  scripts/generate-list-cases.py                 write the gate's cases
  scripts/generate-list-cases.py SEED COUNT DIR  compare COUNT further programs
                                                 with build/dev/A2, keeping the
                                                 ones that differ in DIR"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import lzma
import os
import random
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PROGRAMS=300
SCENARIOS=10
STEPS=28

HEAD='''defmodule Main do
  struct Box do
    items: list[integer]
    more: list[list[integer]]
  end
  def rest(l: list[integer]): list[integer] do
    case l do
      [] -> []
      [_ | t] -> t
    end
  end
  def rest2(l: list[integer]): list[integer] do
    case l do
      [_, _ | t] -> t
      _ -> l
    end
  end
  def rests(l: list[list[integer]]): list[list[integer]] do
    case l do
      [] -> []
      [_ | t] -> t
    end
  end
  def first(l: list[list[integer]]): list[integer] do
    case l do
      [] -> []
      [h | _] -> h
    end
  end
  def push(n: integer, acc: list[integer]): list[integer] do
    if n <= 0 do acc else push(n - 1, [n | acc]) end
  end
  def walk(l: list[integer], acc: list[integer]): list[integer] do
    case l do
      [] -> acc
      [h | t] -> walk(t, [h + 1 | acc])
    end
  end
  def deep(l: list[integer]): list[integer] do
    case l do
      [] -> []
      [h | t] -> [h * 2 | deep(t)]
    end
  end
  def tails(l: list[integer]): list[list[integer]] do
    case l do
      [] -> [[]]
      [_ | t] -> [l | tails(t)]
    end
  end
  def swap(l: list[integer]): list[integer] do
    case l do
      [a, b | t] -> [b, a | t]
      _ -> l
    end
  end
  def echo(l: list[integer], k: integer): list[integer] do
    parent: pid[list[integer]] = Process.self(8)
    worker: pid[list[integer]] = Process.spawn(fn(self: pid[list[integer]]): integer do
      {_, got} = Process.receive(self, 1000)
      Process.send(parent, [k | got], 1000)
      Process.send(parent, [k + 1 | got], 1000)
      Process.send(parent, rest(got), 1000)
      0
    end, 8)
    Process.send(worker, l, 1000)
    {_, a} = Process.receive(parent, 1000)
    {_, b} = Process.receive(parent, 1000)
    {_, c} = Process.receive(parent, 1000)
    Process.await(worker, 1000)
    a ++ b ++ [0 - k | c]
  end
'''


class Scenario:
    def __init__(self,rng):
        self.r=rng;self.lines=[];self.L=[];self.LL=[];self.F=[];self.M=[];self.K=[];self.B=[];self.T=[];self.n=0
    def name(self,prefix):
        self.n+=1;return f'{prefix}{self.n}'
    def k(self):return self.r.randrange(-9,100)
    def small(self):return self.r.randrange(0,5)
    def l(self):
        # Recent lists are picked more often, so chains grow, but old ones stay in play.
        if self.r.random()<0.5:return self.r.choice(self.L[-4:])
        return self.r.choice(self.L)
    def ll(self):return self.r.choice(self.LL)
    def new_l(self,text):
        v=self.name('l');self.lines.append(f'{v}: list[integer] = {text}');self.L.append(v)
    def new_ll(self,text):
        v=self.name('n');self.lines.append(f'{v}: list[list[integer]] = {text}');self.LL.append(v)
    def step(self):
        r=self.r;c=r.randrange(100)
        if c<16:self.new_l(f'[{self.k()} | {self.l()}]')
        elif c<22:self.new_l(f'[{self.k()}, {self.k()} | {self.l()}]')
        elif c<25:self.new_l(f'[{self.k()}, {self.k()}, {self.k()} | {self.l()}]')
        elif c<33:self.new_l(f'rest({self.l()})')
        elif c<36:self.new_l(f'rest2({self.l()})')
        elif c<38:self.new_l(f'rest(rest({self.l()}))')
        elif c<40:self.new_l('['+', '.join(str(self.k()) for _ in range(r.randrange(0,5)))+']')
        elif c<42:self.new_l(f'{self.l()} ++ {self.l()}')
        elif c<44:self.new_l(f'Enum.reverse({self.l()})')
        elif c<46:self.new_l(f'Enum.drop({self.l()}, {self.small()})')
        elif c<48:self.new_l(f'Enum.take({self.l()}, {self.small()})')
        elif c<49:self.new_l(f'Enum.slice({self.l()}, {self.small()}, {self.small()})')
        elif c<50:self.new_l(f'tl([{self.k()} | {self.l()}])')
        elif c<52:self.new_l(f'Enum.map({self.l()}, fn x -> x + {self.small()} end)')
        elif c<53:self.new_l(f'Enum.filter({self.l()}, fn x -> rem(x, 2) == 0 end)')
        elif c<54:self.new_l(f'Enum.sort({self.l()})')
        elif c<55:self.new_l(f'{self.l()} -- {self.l()}')
        elif c<56:self.new_l(f'Enum.uniq({self.l()})')
        elif c<58:self.new_l(f'Enum.reduce({self.l()}, {self.l()}, fn x, acc -> [x | acc] end)')
        elif c<59:self.new_l(f'Enum.reduce({self.l()}, {self.l()}, fn x, acc -> [x, x + 1 | rest(acc)] end)')
        elif c<60:self.new_l(f'for x <- {self.l()}, do: x - 1')
        elif c<61:self.new_l(f'for x <- {self.l()}, rem(x, 3) != 0, do: x')
        elif c<63:self.new_l(f'push({self.small()}, {self.l()})')
        elif c<65:self.new_l(f'walk({self.l()}, {self.l()})')
        elif c<66:self.new_l(f'deep({self.l()})')
        elif c<68:self.new_l(f'swap({self.l()})')
        elif c<70:
            v=self.name('f');self.lines.append(f'{v}: fn[integer, list[integer]] = fn x -> [x | {self.l()}] end');self.F.append(v)
        elif c<71:
            v=self.name('f');self.lines.append(f'{v}: fn[integer, list[integer]] = fn x -> [x, x | rest({self.l()})] end');self.F.append(v)
        elif c<75 and self.F:self.new_l(f'{r.choice(self.F)}({self.k()})')
        elif c<77:self.new_ll(f'[{self.l()} | {self.ll()}]')
        elif c<78:self.new_ll(f'[{self.l()}, {self.l()}]')
        elif c<79:self.new_ll(f'rests({self.ll()})')
        elif c<80:self.new_ll(f'for x <- {self.l()}, do: [x | {self.l()}]')
        elif c<81:self.new_ll(f'Enum.map({self.l()}, fn x -> [x, x | {self.l()}] end)')
        elif c<82:self.new_ll(f'tails({self.l()})')
        elif c<83:self.new_ll(f'Enum.map({self.ll()}, fn x -> [{self.k()} | x] end)')
        elif c<84:self.new_ll(f'Enum.map({self.ll()}, fn x -> rest(x) end)')
        elif c<86:self.new_l(f'first({self.ll()})')
        elif c<87:self.new_l(f'Enum.concat({self.ll()})')
        elif c<88:self.new_l(f'Enum.reduce({self.ll()}, {self.l()}, fn x, acc -> [length(x) | acc] end)')
        elif c<90:
            v=self.name('m');self.lines.append(f'{v}: map[integer, list[integer]] = %{{1 => {self.l()}, 2 => {self.l()}}}');self.M.append(v)
        elif c<92 and self.M:
            m=r.choice(self.M);v=self.name('m')
            self.lines.append(f'{v} = Map.put({m}, {r.randrange(1,4)}, [{self.k()} | Map.get({m}, {r.randrange(1,4)}, [])])');self.M.append(v)
        elif c<94 and self.M:self.new_l(f'Map.get({r.choice(self.M)}, {r.randrange(1,4)}, {self.l()})')
        elif c<96:
            v=self.name('m');self.lines.append(f'{v}: map[tuple[integer, integer], list[integer]] = %{{{{1, {self.small()}}} => {self.l()}, {{2, {self.small()}}} => [{self.k()} | {self.l()}]}}');self.K.append(v)
            self.new_l(f'Map.get({v}, {{1, {self.small()}}}, {self.l()})')
        elif c<97:
            v=self.name('b');self.lines.append(f'{v} = %Box{{items: {self.l()}, more: {self.ll()}}}');self.B.append(v)
        elif c<98 and self.B:
            b=r.choice(self.B);v=self.name('b')
            self.lines.append(f'{v} = %Box{{{b} | items: [{self.k()} | {b}.items], more: [{self.l()} | {b}.more]}}');self.B.append(v)
            self.new_l(f'{v}.items')
        elif c<99:
            v=self.name('t');self.lines.append(f'{v} = {{{self.l()}, [{self.k()} | {self.l()}]}}');self.T.append(v)
            self.new_l(f'elem({v}, {r.randrange(2)})')
        else:self.new_l(f'echo({self.l()}, {self.k()})')
    def text(self,index):
        r=self.r
        self.new_l('['+', '.join(str(self.k()) for _ in range(r.randrange(0,4)))+']')
        self.new_l('[]')
        self.new_ll('[]')
        for _ in range(STEPS):self.step()
        shown=[f'IO.puts(inspect({v}))' for v in self.L+self.LL+self.M+self.K+self.B+self.T]
        body='\n'.join('    '+line for line in self.lines+shown)
        return f'  def s{index}(): integer do\n{body}\n    {index}\n  end\n'


def program(seed):
    rng=random.Random(seed)
    parts=[Scenario(rng).text(i) for i in range(SCENARIOS)]
    calls='\n'.join(f'    s{i}()' for i in range(SCENARIOS))
    return HEAD+''.join(parts)+f'  def main() do\n{calls}\n  end\nend\n'


def pinned(source):
    with tempfile.TemporaryDirectory(prefix='alchem-list-cases-') as d:
        path=Path(d)/'main.alc';path.write_text(source)
        env=dict(os.environ,GOTOOLCHAIN='local',GOPROXY='off',GOFLAGS='-mod=mod')
        run=subprocess.run([str(ROOT/'build/dev/alchem-upstream'),'run',str(path)],capture_output=True,env=env,timeout=300)
        return run.returncode,run.stdout.decode(),run.stderr.decode()


def native(source):
    with tempfile.TemporaryDirectory(prefix='alchem-list-cases-') as d:
        out=Path(d)/'out'
        made=subprocess.run([str(ROOT/'build/dev/A2')],input=source.encode(),capture_output=True,timeout=300)
        if made.returncode!=0:return made.returncode,'',made.stderr.decode()
        out.write_bytes(made.stdout);out.chmod(0o700)
        run=subprocess.run([str(ROOT/'scripts/limited'),str(out)],capture_output=True,timeout=300)
        return run.returncode,run.stdout.decode(),run.stderr.decode()


def main():
    if len(sys.argv)==4:
        seed,count,keep=int(sys.argv[1]),int(sys.argv[2]),Path(sys.argv[3]);keep.mkdir(parents=True,exist_ok=True)
        sources=[program(seed+i) for i in range(count)]
        with ThreadPoolExecutor(8) as pool:
            theirs=list(pool.map(pinned,sources));ours=list(pool.map(native,sources))
        differ=0
        for i,(source,a,b) in enumerate(zip(sources,theirs,ours)):
            if a!=b:
                differ+=1;(keep/f'{seed+i}.alc').write_text(source)
                (keep/f'{seed+i}.pinned').write_text(repr(a));(keep/f'{seed+i}.native').write_text(repr(b))
        print(f'{count} programs from seed {seed}: {differ} differ')
        return 1 if differ else 0
    sources=[program(i) for i in range(PROGRAMS)]
    with ThreadPoolExecutor(8) as pool:
        results=list(pool.map(pinned,sources))
    cases=[]
    for source,(status,stdout,stderr) in zip(sources,results):
        assert (status,stderr)==(0,''),(source,status,stderr)
        cases.append([source,stdout])
    data=lzma.compress(json.dumps(cases).encode(),preset=9|lzma.PRESET_EXTREME)
    (ROOT/'harness/list-cases.json.xz').write_bytes(data)
    print(f'{len(cases)} programs of {SCENARIOS} scenarios, {len(data)} bytes')
    return 0


if __name__=='__main__':sys.exit(main())
