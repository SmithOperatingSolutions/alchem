#!/usr/bin/env python3
"""Time and peak resident memory of list programs: the pinned compiler's
program beside the self-hosted compiler's (spec/alchem-lists.md has the
table this made). Not used by normal builds.

  scripts/benchmark-lists.py [--before OTHER_A2] [--only NAME] [--sizes N,N,...]

Each program is compiled by build/dev/alchem-upstream and by build/dev/A2
(and by OTHER_A2, a compiler built from an earlier source, when given), and
each executable is run once through scripts/limited (6 GB, 120 s) under
/usr/bin/time. A run that is killed or fails shows its status instead; the
outputs of the runs of one program must agree."""
from pathlib import Path
import argparse
import os
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]

WRAP='''defmodule Main do
  def build(n: integer, acc: list[integer]): list[integer] do
    if n == 0 do acc else build(n - 1, [n | acc]) end
  end
  def total(items: list[integer], acc: integer): integer do
    case items do
      [] -> acc
      [h | t] -> total(t, acc + h)
    end
  end
  def grow(n: integer, acc: list[integer]): list[integer] do
    if n == 0 do acc else grow(n - 1, acc ++ [n]) end
  end
  def noise(n: integer, seed: integer, acc: list[integer]): list[integer] do
    if n == 0 do acc else noise(n - 1, rem(seed * 48271 + 11, 2147483647), [seed | acc]) end
  end
  def fill(me: pid[integer], n: integer): integer do
    if n == 0 do 0 else
      Process.send(me, n, 1000)
      fill(me, n - 1)
    end
  end
  def drain(me: pid[integer], n: integer, acc: integer): integer do
    if n == 0 do acc else
      {_, x} = Process.receive(me, 1000)
      drain(me, n - 1, acc + x)
    end
  end
  def main() do
BODY
  end
end
'''

def body(lines):return WRAP.replace('BODY','\n'.join('    '+line for line in lines))

def over(expression,count='length(ys)'):
    return lambda n:body([f'xs = Enum.to_list(1..{n})',f'ys = {expression}',f'IO.puts(Integer.to_string({count}))'])

# name, sizes, program for a size
LIBRARY=[1_000_0,100_000,1_000_000]
CASES=[
    ('Enum.dedup',LIBRARY,over('Enum.dedup(Enum.map(xs, fn x -> div(x, 2) end))')),
    ('Enum.chunk_every',LIBRARY,over('Enum.chunk_every(xs, 3)')),
    ('Enum.zip',LIBRARY,over('Enum.zip(xs, xs)')),
    ('Enum.with_index',LIBRARY,over('Enum.with_index(xs)')),
    ('Enum.scan',LIBRARY,over('Enum.scan(xs, fn x, acc -> x + acc end)')),
    ('Enum.flat_map',LIBRARY,over('Enum.flat_map(xs, fn x -> [x, x] end)')),
    ('Enum.intersperse',LIBRARY,over('Enum.intersperse(xs, 0)')),
    ('Enum.take_every',LIBRARY,over('Enum.take_every(xs, 2)')),
    ('Enum.zip_with',LIBRARY,over('Enum.zip_with(xs, xs, fn a, b -> a + b end)')),
    ('Enum.chunk_by',LIBRARY,over('Enum.chunk_by(xs, fn x -> div(x, 3) end)')),
    ('Enum.map_every',LIBRARY,over('Enum.map_every(xs, 2, fn x -> x * 2 end)')),
    ('Enum.drop_every',LIBRARY,over('Enum.drop_every(xs, 2)')),
    ('Enum.split_with',LIBRARY,over('Enum.split_with(xs, fn x -> rem(x, 2) == 0 end)','length(elem(ys, 0))')),
    ('Enum.map_reduce',LIBRARY,over('Enum.map_reduce(xs, 0, fn x, acc -> {x * 2, acc + x} end)','elem(ys, 1)')),
    ('Enum.concat/1',LIBRARY,over('Enum.concat(Enum.chunk_every(xs, 3))')),
    ('Enum.group_by',LIBRARY,over('Enum.group_by(xs, fn x -> rem(x, 4) end)','map_size(ys)')),
    ('Enum.chunk_while',LIBRARY,over('Enum.chunk_while(xs, 0, fn x, acc -> if rem(x, 3) == 0 do {some(acc + x), 0} else {none, acc + x} end end, fn acc -> some(acc) end)')),
    ('Enum.reduce_while',LIBRARY,over('Enum.reduce_while(xs, 0, fn x, acc -> cont(acc + x) end)','ys')),
    ('List.duplicate',LIBRARY,lambda n:body([f'ys = List.duplicate(7, {n})','IO.puts(Integer.to_string(length(ys)))'])),
    ('List.flatten',LIBRARY,over('List.flatten(Enum.chunk_every(xs, 3))')),
    ('String.graphemes',LIBRARY,lambda n:body([f'ys = String.graphemes(String.duplicate("a", {n}))','IO.puts(Integer.to_string(length(ys)))'])),
    ('String.codepoints',LIBRARY,lambda n:body([f'ys = String.codepoints(String.duplicate("a", {n}))','IO.puts(Integer.to_string(length(ys)))'])),
    ('[n \\| acc] in a loop, then summed by [h \\| t]',[20_000,100_000,1_000_000,10_000_000],lambda n:body([f'IO.puts(Integer.to_string(total(build({n}, []), 0)))'])),
    ('Enum.reverse',[1_000_000],over('Enum.reverse(xs)')),
    ('Enum.map',[1_000_000],over('Enum.map(xs, fn x -> x + 1 end)')),
    ('acc ++ [x] in a loop',[10_000,20_000],lambda n:body([f'IO.puts(Integer.to_string(length(grow({n}, []))))'])),
    ('Enum.sort',[1_000_000],lambda n:body([f'ys = Enum.sort(noise({n}, 1, []))','IO.puts(Integer.to_string(hd(ys) + length(ys)))'])),
    ('for over a list',[1_000_000],over('for x <- xs, rem(x, 2) == 0, do: x * 3')),
    ('a mailbox of messages',[1_000_000],lambda n:body([f'me: pid[integer] = Process.self({n})',f'fill(me, {n})',f'IO.puts(Integer.to_string(drain(me, {n}, 0)))'])),
]


def measure(executable):
    """(seconds, megabytes, output) of one run, or (status text, None, None)."""
    env=dict(os.environ,ALCHEM_MEMORY='6G',ALCHEM_SECONDS='120')
    with tempfile.NamedTemporaryFile() as report:
        run=subprocess.run(['/usr/bin/time','-f','%e %M','-o',report.name,str(ROOT/'scripts/limited'),str(executable)],capture_output=True,env=env)
        words=Path(report.name).read_text().split()
    if run.returncode!=0:return f'status {run.returncode}',None,None
    return float(words[-2]),int(words[-1])/1024,run.stdout


def cell(result):
    seconds,megabytes,_=result
    if megabytes is None:return seconds
    return f'{megabytes:,.0f} MB, {seconds:.2f} s'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--before');parser.add_argument('--only');parser.add_argument('--sizes')
    args=parser.parse_args()
    compilers=[('pinned',None)]+([('before',Path(args.before).resolve())] if args.before else [])+[('native',ROOT/'build/dev/A2')]
    print('| Program | Elements | '+' | '.join(name for name,_ in compilers)+' |')
    print('| --- | --- | '+' | '.join('---' for _ in compilers)+' |')
    env=dict(os.environ,GOTOOLCHAIN='local',GOPROXY='off',GOFLAGS='-mod=mod')
    with tempfile.TemporaryDirectory(prefix='alchem-benchmark-lists-') as d:
        root=Path(d)
        for name,sizes,make in CASES:
            if args.only and args.only not in name:continue
            for n in ([int(x) for x in args.sizes.split(',')] if args.sizes else sizes):
                source=root/'main.alc';source.write_text(make(n));row=[];outputs=set()
                for label,compiler in compilers:
                    out=root/label
                    if compiler is None:
                        made=subprocess.run([str(ROOT/'build/dev/alchem-upstream'),'build','-o',str(out),str(source)],capture_output=True,env=env)
                    else:
                        made=subprocess.run([str(compiler)],input=source.read_bytes(),capture_output=True)
                        if made.returncode==0:out.write_bytes(made.stdout);out.chmod(0o700)
                    if made.returncode!=0:row.append(f'does not compile ({made.returncode})');continue
                    result=measure(out);row.append(cell(result))
                    if result[2] is not None:outputs.add(result[2])
                assert len(outputs)<=1,(name,n,outputs)
                print(f'| `{name}` | {n:,} | '+' | '.join(row)+' |',flush=True)


if __name__=='__main__':sys.exit(main())
