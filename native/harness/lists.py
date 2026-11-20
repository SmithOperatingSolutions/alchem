#!/usr/bin/env python3
"""Lists that share their storage (spec/alchem-lists.md): every program runs
as the pinned compiler runs it, and the arena is charged what the layout says.

A tail is an address inside its list and an element put before a list is
written into the list's block when the pair below it is unclaimed, so the
programs here make lists from one another in every way the language has and
then look at all of them again: two prepends onto one list, onto a tail and a
tail of a tail, onto lists held by closures, maps, structs, tuples and other
lists, sent between processes, inside for and reduce, across the lengths at
which a block is full, and onto what drop, take, slice, reverse, ++, --, sort,
map, filter, a range, String.split, Map.keys and the other makers of lists
give. harness/list-cases.json.xz holds random programs of the same kind
with the pinned compiler's output (scripts/generate-list-cases.py)."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import json
import lzma
import subprocess
import sys
import tempfile
from native_memory import profile,TraceUnavailable

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule Main do\n'
  '  def rest(l: list[integer]): list[integer] do\n'
  '    case l do\n'
  '      [] -> []\n'
  '      [_ | t] -> t\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    base = [3, 4, 5]\n'
  '    a = [2 | base]\n'
  '    b = [9 | base]\n'
  '    c = [1 | a]\n'
  '    d = [8 | a]\n'
  '    e = [0 | c]\n'
  '    t = rest(c)\n'
  '    f = [7 | t]\n'
  '    g = [6 | t]\n'
  '    u = rest(rest(e))\n'
  '    h = [5 | u]\n'
  '    i = [4, 3 | rest(u)]\n'
  '    j = [11, 12, 13, 14, 15, 16 | e]\n'
  '    k = [21 | rest(j)]\n'
  '    IO.inspect({base, a, b, c, d, e})\n'
  '    IO.inspect({t, f, g, u, h, i})\n'
  '    IO.inspect({j, k})\n'
  '    IO.inspect({t == a, u == a, rest(h) == a, length(i), rest(k) == rest(rest(j))})\n'
  '    empty: list[integer] = []\n'
  '    x = [1 | empty]\n'
  '    y = [2 | empty]\n'
  '    z = [3 | rest(x)]\n'
  '    IO.inspect({empty, x, y, z, rest(x), rest(rest(x)), tl(y) == empty})\n'
  '  end\n'
  'end\n',
  0,
  b'{[3, 4, 5], [2, 3, 4, 5], [9, 3, 4, 5], [1, 2, 3, 4, 5], [8, 2, 3, 4, 5], [0, 1, 2, 3, 4, 5]}\n{[2, 3, 4, 5], [7,'
  b' 2, 3, 4, 5], [6, 2, 3, 4, 5], [2, 3, 4, 5], [5, 2, 3, 4, 5], [4, 3, 3, 4, 5]}\n{[11, 12, 13, 14, 15, 16, 0, 1, 2'
  b', 3, 4, 5], [21, 12, 13, 14, 15, 16, 0, 1, 2, 3, 4, 5]}\n{true, true, true, 5, false}\n{[], [1], [2], [3], [], [],'
  b' true}\n',
  b''),
 ('defmodule Main do\n'
  '  struct Box do\n'
  '    items: list[integer]\n'
  '    more: list[list[integer]]\n'
  '  end\n'
  '  def rest(l: list[integer]): list[integer] do\n'
  '    case l do\n'
  '      [] -> []\n'
  '      [_ | t] -> t\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    base = [1, 2, 3]\n'
  '    grown = [0 | base]\n'
  '    push: fn[integer, list[integer]] = fn x -> [x | base] end\n'
  '    onto: fn[integer, list[integer]] = fn x -> [x | grown] end\n'
  '    under: fn[integer, list[integer]] = fn x -> [x, x | rest(grown)] end\n'
  '    a = push(10)\n'
  '    b = push(11)\n'
  '    c = onto(12)\n'
  '    d = onto(13)\n'
  '    e = under(14)\n'
  '    more = [-1 | grown]\n'
  '    f = onto(15)\n'
  '    IO.inspect({base, grown, a, b, c, d, e, more, f})\n'
  '    m = %{1 => base, 2 => grown, 3 => [5 | grown]}\n'
  '    m2 = Map.put(m, 1, [7 | Map.get(m, 1, [])])\n'
  '    m3 = Map.put(m2, 4, [8 | Map.get(m, 1, [])])\n'
  '    m4 = Map.put(m3, 2, [9 | Map.get(m3, 3, [])])\n'
  '    IO.inspect({m, m2, m3, m4})\n'
  '    box = %Box{items: grown, more: [base, grown]}\n'
  '    box2 = %Box{box | items: [20 | box.items], more: [[21 | box.items] | box.more]}\n'
  '    box3 = %Box{box2 | items: [22 | box.items]}\n'
  '    IO.inspect({box, box2, box3})\n'
  '    pair = {grown, [30 | grown]}\n'
  '    both = {[31 | elem(pair, 0)], [32 | rest(elem(pair, 1))]}\n'
  '    IO.inspect({pair, both, grown, base})\n'
  '  end\n'
  'end\n',
  0,
  b'{[1, 2, 3], [0, 1, 2, 3], [10, 1, 2, 3], [11, 1, 2, 3], [12, 0, 1, 2, 3], [13, 0, 1, 2, 3], [14, 14, 1, 2, 3], ['
  b'-1, 0, 1, 2, 3], [15, 0, 1, 2, 3]}\n{%{1 => [1, 2, 3], 2 => [0, 1, 2, 3], 3 => [5, 0, 1, 2, 3]}, %{1 => [7, 1, 2,'
  b' 3], 2 => [0, 1, 2, 3], 3 => [5, 0, 1, 2, 3]}, %{1 => [7, 1, 2, 3], 2 => [0, 1, 2, 3], 3 => [5, 0, 1, 2, 3], 4 ='
  b'> [8, 1, 2, 3]}, %{1 => [7, 1, 2, 3], 2 => [9, 5, 0, 1, 2, 3], 3 => [5, 0, 1, 2, 3], 4 => [8, 1, 2, 3]}}\n{%Box{i'
  b'tems: [0, 1, 2, 3], more: [[1, 2, 3], [0, 1, 2, 3]]}, %Box{items: [20, 0, 1, 2, 3], more: [[21, 0, 1, 2, 3], [1,'
  b' 2, 3], [0, 1, 2, 3]]}, %Box{items: [22, 0, 1, 2, 3], more: [[21, 0, 1, 2, 3], [1, 2, 3], [0, 1, 2, 3]]}}\n{{[0, '
  b'1, 2, 3], [30, 0, 1, 2, 3]}, {[31, 0, 1, 2, 3], [32, 0, 1, 2, 3]}, [0, 1, 2, 3], [1, 2, 3]}\n',
  b''),
 ('defmodule Main do\n'
  '  def rest(l: list[integer]): list[integer] do\n'
  '    case l do\n'
  '      [] -> []\n'
  '      [_ | t] -> t\n'
  '    end\n'
  '  end\n'
  '  def worker(parent: pid[list[integer]], self: pid[list[integer]], tag: integer): integer do\n'
  '    {_, got} = Process.receive(self, 1000)\n'
  '    Process.send(parent, [tag | got], 1000)\n'
  '    Process.send(parent, [tag + 1, tag + 2 | rest(got)], 1000)\n'
  '    {_, again} = Process.receive(self, 1000)\n'
  '    Process.send(parent, [tag + 3 | again], 1000)\n'
  '    0\n'
  '  end\n'
  '  def main() do\n'
  '    parent: pid[list[integer]] = Process.self(16)\n'
  '    shared = [1, 2, 3]\n'
  '    one: pid[list[integer]] = Process.spawn(fn(self: pid[list[integer]]): integer do worker(parent, self, 100) end, '
  '4)\n'
  '    two: pid[list[integer]] = Process.spawn(fn(self: pid[list[integer]]): integer do worker(parent, self, 200) end, '
  '4)\n'
  '    Process.send(one, shared, 1000)\n'
  '    Process.send(two, shared, 1000)\n'
  '    mine = [0 | shared]\n'
  '    Process.send(one, mine, 1000)\n'
  '    Process.send(two, rest(mine), 1000)\n'
  '    Process.await(one, 1000)\n'
  '    Process.await(two, 1000)\n'
  '    {_, a} = Process.receive(parent, 1000)\n'
  '    {_, b} = Process.receive(parent, 1000)\n'
  '    {_, c} = Process.receive(parent, 1000)\n'
  '    {_, d} = Process.receive(parent, 1000)\n'
  '    {_, e} = Process.receive(parent, 1000)\n'
  '    {_, f} = Process.receive(parent, 1000)\n'
  '    IO.inspect(Enum.sort([a, b, c, d, e, f]))\n'
  '    IO.inspect({shared, mine, [-1 | shared], [-2 | mine]})\n'
  '  end\n'
  'end\n',
  0,
  b'[[100, 1, 2, 3], [101, 102, 2, 3], [103, 0, 1, 2, 3], [200, 1, 2, 3], [201, 202, 2, 3], [203, 1, 2, 3]]\n{[1, 2, '
  b'3], [0, 1, 2, 3], [-1, 1, 2, 3], [-2, 0, 1, 2, 3]}\n',
  b''),
 ('defmodule Main do\n'
  '  def rest(l: list[integer]): list[integer] do\n'
  '    case l do\n'
  '      [] -> []\n'
  '      [_ | t] -> t\n'
  '    end\n'
  '  end\n'
  '  def tails(l: list[integer]): list[list[integer]] do\n'
  '    case l do\n'
  '      [] -> [[]]\n'
  '      [_ | t] -> [l | tails(t)]\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    base = [1, 2, 3, 4]\n'
  '    rows = for x <- base, do: [x | base]\n'
  '    more = for x <- base, y <- rest(base), x < y, do: [x, y | rest(rest(base))]\n'
  '    onto = Enum.map(tails(base), fn t -> [0 | t] end)\n'
  '    twice = Enum.map(tails(base), fn t -> [[9 | t], [8 | t]] end)\n'
  '    folded = Enum.reduce(base, base, fn x, acc -> [x | acc] end)\n'
  '    kept = Enum.reduce(base, {base, [base]}, fn x, acc -> {[x | elem(acc, 0)], [[x | elem(acc, 0)] | elem(acc, 1)]} '
  'end)\n'
  '    summed = for t <- tails(folded), reduce: 0 do\n'
  '      acc -> acc + length([7 | t])\n'
  '    end\n'
  '    nested = [base, rest(base), [5 | base], [6 | rest(base)]]\n'
  '    deeper = [nested, [[7 | base] | nested], tl(nested)]\n'
  '    IO.inspect(rows)\n'
  '    IO.inspect(more)\n'
  '    IO.inspect(onto)\n'
  '    IO.inspect(twice)\n'
  '    IO.inspect({folded, kept, summed})\n'
  '    IO.inspect(deeper)\n'
  '    IO.inspect({base, tails(base)})\n'
  '  end\n'
  'end\n',
  0,
  b'[[1, 1, 2, 3, 4], [2, 1, 2, 3, 4], [3, 1, 2, 3, 4], [4, 1, 2, 3, 4]]\n[[1, 2, 3, 4], [1, 3, 3, 4], [1, 4, 3, 4], '
  b'[2, 3, 3, 4], [2, 4, 3, 4], [3, 4, 3, 4]]\n[[0, 1, 2, 3, 4], [0, 2, 3, 4], [0, 3, 4], [0, 4], [0]]\n[[[9, 1, 2, 3,'
  b' 4], [8, 1, 2, 3, 4]], [[9, 2, 3, 4], [8, 2, 3, 4]], [[9, 3, 4], [8, 3, 4]], [[9, 4], [8, 4]], [[9], [8]]]\n{[4, '
  b'3, 2, 1, 1, 2, 3, 4], {[4, 3, 2, 1, 1, 2, 3, 4], [[4, 3, 2, 1, 1, 2, 3, 4], [3, 2, 1, 1, 2, 3, 4], [2, 1, 1, 2, '
  b'3, 4], [1, 1, 2, 3, 4], [1, 2, 3, 4]]}, 45}\n[[[1, 2, 3, 4], [2, 3, 4], [5, 1, 2, 3, 4], [6, 2, 3, 4]], [[7, 1, 2'
  b', 3, 4], [1, 2, 3, 4], [2, 3, 4], [5, 1, 2, 3, 4], [6, 2, 3, 4]], [[2, 3, 4], [5, 1, 2, 3, 4], [6, 2, 3, 4]]]\n{['
  b'1, 2, 3, 4], [[1, 2, 3, 4], [2, 3, 4], [3, 4], [4], []]}\n',
  b''),
 ('defmodule Main do\n'
  '  def build(n: integer, acc: list[integer]): list[integer] do\n'
  '    if n == 0 do acc else build(n - 1, [n | acc]) end\n'
  '  end\n'
  '  def total(items: list[integer], acc: integer): integer do\n'
  '    case items do\n'
  '      [] -> acc\n'
  '      [h | t] -> total(t, acc + h)\n'
  '    end\n'
  '  end\n'
  '  # Every length from 0 to n: the list so far is extended twice, once on to the\n'
  '  # next round and once aside, and what was put aside must stay as it was.\n'
  '  def fork(n: integer, acc: list[integer], aside: list[list[integer]]): list[list[integer]] do\n'
  '    if n == 0 do [acc | aside] else fork(n - 1, [n | acc], [[0 - n | acc] | aside]) end\n'
  '  end\n'
  '  def sums(lists: list[list[integer]], acc: list[integer]): list[integer] do\n'
  '    case lists do\n'
  '      [] -> acc\n'
  '      [l | rest] -> sums(rest, [total(l, 0) * 1000 + length(l) | acc])\n'
  '    end\n'
  '  end\n'
  '  def step(items: list[integer], n: integer, acc: integer): integer do\n'
  '    case items do\n'
  '      [] -> acc\n'
  '      [_ | t] -> step(t, n + 1, acc + total([n | t], 0) + total([n, n | items], 0))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    all = fork(70, [], [])\n'
  '    IO.inspect(sums(all, []))\n'
  '    long = build(5000, [])\n'
  '    IO.inspect(step(Enum.take(long, 300), 1, 0))\n'
  '    IO.inspect({total(long, 0), length(long), hd(long), total(Enum.drop(long, 4990), 0)})\n'
  '    left = [0 | long]\n'
  '    right = [-1 | long]\n'
  '    IO.inspect({total(left, 0), total(right, 0), total(long, 0), length(left), hd(right), hd(tl(right))})\n'
  '  end\n'
  'end\n',
  0,
  b'[-69999, 1002, 71003, 140004, 208005, 275006, 341007, 406008, 470009, 533010, 595011, 656012, 716013, 775014, 83'
  b'3015, 890016, 946017, 1001018, 1055019, 1108020, 1160021, 1211022, 1261023, 1310024, 1358025, 1405026, 1451027, '
  b'1496028, 1540029, 1583030, 1625031, 1666032, 1706033, 1745034, 1783035, 1820036, 1856037, 1891038, 1925039, 1958'
  b'040, 1990041, 2021042, 2051043, 2080044, 2108045, 2135046, 2161047, 2186048, 2210049, 2233050, 2255051, 2276052,'
  b' 2296053, 2315054, 2333055, 2350056, 2366057, 2381058, 2395059, 2408060, 2420061, 2431062, 2441063, 2450064, 245'
  b'8065, 2465066, 2471067, 2476068, 2480069, 2483070, 2485070]\n18180400\n{12502500, 5000, 1, 49955}\n{12502500, 12502'
  b'499, 12502500, 5001, -1, 1}\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    base = [5, 6]\n'
  '    a = [4 | base]\n'
  '    IO.inspect({Enum.drop(a, 1) == base, Enum.drop(a, 3), Enum.drop(a, 9), Enum.take(a, 2), Enum.slice(a, 1, 2), '
  'Enum.slice(a, 1, 1), tl(a), hd(a)})\n'
  '    d = Enum.drop(a, 1)\n'
  '    IO.inspect({[1 | d], [2 | d], d, a, [3 | Enum.take(a, 0)], [3 | Enum.drop(a, 3)]})\n'
  '    r = Enum.reverse(a)\n'
  '    IO.inspect({[0 | r], [1 | r], r ++ a, [9 | a ++ r], a -- [5], [7 | a -- [9]], Enum.uniq([1 | [1 | a]])})\n'
  '    s = Enum.sort([3, 1, 2])\n'
  '    IO.inspect({[0 | s], [9 | s], s, [4 | Enum.filter(s, fn x -> x > 1 end)], [5 | Enum.map(s, fn x -> x * 2 '
  'end)]})\n'
  '    g = 1..4\n'
  '    l = Enum.to_list(g)\n'
  '    IO.inspect({[0 | l], [9 | l], l, g, g.first, g.last, g.step, [7 | Enum.take(g, 2)], 3 in g, '
  'Enum.to_list(5..1//-2)})\n'
  '    w = String.split("a,b,c", ",")\n'
  '    IO.inspect({["z" | w], ["y" | tl(w)], w, Enum.join(["x" | w], "-"), ["q" | String.graphemes("hé")], '
  'Integer.digits(120), [0 | Integer.digits(7)]})\n'
  '    m = %{2 => "b", 1 => "a"}\n'
  '    IO.inspect({[0 | Map.keys(m)], ["c" | Map.values(m)], [{3, "c"} | Map.to_list(m)], Map.new([{0, "z"} | '
  'Map.to_list(m)])})\n'
  '    IO.inspect({MapSet.to_list(MapSet.new([3 | l])), [1.5 | [2.5]], Enum.sum([0.5 | [1.5, 2.0]]), [:a | [:b]]})\n'
  '  end\n'
  'end\n',
  0,
  b'{true, [], [], [4, 5], [5, 6], [5], [5, 6], 4}\n{[1, 5, 6], [2, 5, 6], [5, 6], [4, 5, 6], [3], [3]}\n{[0, 6, 5, 4]'
  b', [1, 6, 5, 4], [6, 5, 4, 4, 5, 6], [9, 4, 5, 6, 6, 5, 4], [4, 6], [7, 4, 5, 6], [1, 4, 5, 6]}\n{[0, 1, 2, 3], [9'
  b', 1, 2, 3], [1, 2, 3], [4, 2, 3], [5, 2, 4, 6]}\n{[0, 1, 2, 3, 4], [9, 1, 2, 3, 4], [1, 2, 3, 4], 1..4, 1, 4, 1, '
  b'[7, 1, 2], true, [5, 3, 1]}\n{["z", "a", "b", "c"], ["y", "b", "c"], ["a", "b", "c"], "x-a-b-c", ["q", "h", "'
  b'\xc3\xa9"], [1, 2, 0], [0, 7]}\n{[0, 1, 2], ["c", "a", "b"], [{3, "c"}, {1, "a"}, {2, "b"}], %{0 => "z", 1 => "a", '
  b'2 => "b"}}\n{[1, 2, 3, 4], [1.5, 2.5], 4.0, [:a, :b]}\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    xs = [3, 3, 1, 2, 2, 2, 5, 1]\n'
  '    IO.inspect(Enum.flat_map(xs, fn x -> [x, x * 10] end))\n'
  '    IO.inspect(Enum.concat([[1, 2], [], [3]]))\n'
  '    IO.inspect(Enum.intersperse(xs, 0))\n'
  '    IO.inspect(Enum.map_intersperse(xs, 0, fn x -> x + 1 end))\n'
  '    IO.inspect(Enum.dedup(xs))\n'
  '    IO.inspect(Enum.dedup_by(xs, fn x -> rem(x, 2) end))\n'
  '    IO.inspect(Enum.uniq(xs))\n'
  '    IO.inspect(Enum.uniq_by(xs, fn x -> rem(x, 3) end))\n'
  '    IO.inspect(Enum.with_index(xs))\n'
  '    IO.inspect(Enum.with_index(xs, 5))\n'
  '    IO.inspect(Enum.with_index(xs, fn x, i -> x * i end))\n'
  '    IO.inspect(Enum.zip(xs, ["a", "b", "c"]))\n'
  '    IO.inspect(Enum.zip_with(xs, [1, 2, 3], fn a, b -> a + b end))\n'
  '    IO.inspect(Enum.split_with(xs, fn x -> x > 2 end))\n'
  '    IO.inspect(Enum.chunk_every(xs, 3))\n'
  '    IO.inspect(Enum.chunk_every(xs, 3, 2))\n'
  '    IO.inspect(Enum.chunk_every(xs, 3, 5))\n'
  '    IO.inspect(Enum.chunk_every(xs, 3, 3, [0, 0]))\n'
  '    IO.inspect(Enum.chunk_every(xs, 3, 3, :discard))\n'
  '    IO.inspect(Enum.chunk_by(xs, fn x -> rem(x, 2) end))\n'
  '    e: list[integer] = []\n'
  '    IO.inspect(Enum.chunk_by(e, fn x -> rem(x, 2) end))\n'
  '    IO.inspect(Enum.scan(xs, fn x, acc -> x + acc end))\n'
  '    IO.inspect(Enum.scan(xs, 100, fn x, acc -> x + acc end))\n'
  '    IO.inspect(Enum.map_reduce(xs, 0, fn x, acc -> {x * 2, acc + x} end))\n'
  '    IO.inspect(Enum.flat_map_reduce(xs, 0, fn x, acc -> {[x, acc], acc + x} end))\n'
  '    IO.inspect(Enum.map_every(xs, 3, fn x -> x * 100 end))\n'
  '    IO.inspect(Enum.take_every(xs, 3))\n'
  '    IO.inspect(Enum.drop_every(xs, 3))\n'
  '    IO.inspect(Enum.group_by(xs, fn x -> rem(x, 3) end))\n'
  '    IO.inspect(Enum.group_by(xs, fn x -> rem(x, 3) end, fn x -> x * 2 end))\n'
  '    IO.inspect(Enum.chunk_while(xs, 0, fn x, acc -> if acc + x > 4 do {some(acc), x} else {none, acc + x} end end, '
  'fn acc -> some(acc) end))\n'
  '    IO.inspect(Enum.sort(Enum.shuffle(xs)))\n'
  '    IO.inspect(length(Enum.shuffle(e)))\n'
  '    IO.inspect(Enum.take_random(xs, 0))\n'
  '    IO.inspect(String.graphemes("héllo"))\n'
  '    IO.inspect(String.codepoints("héllo"))\n'
  '  end\n'
  'end\n',
  0,
  b'[3, 30, 3, 30, 1, 10, 2, 20, 2, 20, 2, 20, 5, 50, 1, 10]\n[1, 2, 3]\n[3, 0, 3, 0, 1, 0, 2, 0, 2, 0, 2, 0, 5, 0, 1]'
  b'\n[4, 0, 4, 0, 2, 0, 3, 0, 3, 0, 3, 0, 6, 0, 2]\n[3, 1, 2, 5, 1]\n[3, 2, 5]\n[3, 1, 2, 5]\n[3, 1, 2]\n[{3, 0}, {3,'
  b' 1}, {1, 2}, {2, 3}, {2, 4}, {2, 5}, {5, 6}, {1, 7}]\n[{3, 5}, {3, 6}, {1, 7}, {2, 8}, {2, 9}, {2, 10}, {5, 11}, '
  b'{1, 12}]\n[0, 3, 2, 6, 8, 10, 30, 7]\n[{3, "a"}, {3, "b"}, {1, "c"}]\n[4, 5, 4]\n{[3, 3, 5], [1, 2, 2, 2, 1]}\n[['
  b'3, 3, 1], [2, 2, 2], [5, 1]]\n[[3, 3, 1], [1, 2, 2], [2, 2, 5], [5, 1]]\n[[3, 3, 1], [2, 5, 1]]\n[[3, 3, 1], [2, 2,'
  b' 2], [5, 1, 0]]\n[[3, 3, 1], [2, 2, 2]]\n[[3, 3, 1], [2, 2, 2], [5, 1]]\n[]\n[3, 6, 7, 9, 11, 13, 18, 19]\n[103, '
  b'106, 107, 109, 111, 113, 118, 119]\n{[6, 6, 2, 4, 4, 4, 10, 2], 19}\n{[3, 0, 3, 3, 1, 6, 2, 7, 2, 9, 2, 11, 5, 13,'
  b' 1, 18], 19}\n[300, 3, 1, 200, 2, 2, 500, 1]\n[3, 2, 5]\n[3, 1, 2, 2, 1]\n%{0 => [3, 3], 1 => [1, 1], 2 => [2, 2'
  b', 2, 5]}\n%{0 => [6, 6], 1 => [2, 2], 2 => [4, 4, 4, 10]}\n[3, 4, 4, 2, 5, 1]\n[1, 1, 2, 2, 2, 3, 3, 5]\n0\n[]\n["'
  b'h", "\xc3\xa9", "l", "l", "o"]\n["h", "\xc3\xa9", "l", "l", "o"]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.inspect(String.graphemes(""))\n'
  '    IO.inspect(String.graphemes("a"))\n'
  '    IO.inspect(String.graphemes("a\\r\\nb\\r\\n\\r\\nc\\n\\rd"))\n'
  '    IO.inspect(String.graphemes("é̂̃̄̅̆̇̈̉̊̋̌̍xyz"))\n'
  '    IO.inspect(String.graphemes("0123456789abcdéf"))\n'
  '    IO.inspect(String.graphemes("0123456789abcd́ef"))\n'
  '    IO.inspect(String.graphemes("0123456789abćdef"))\n'
  '    IO.inspect(String.graphemes("0123456789ab́cdef"))\n'
  '    IO.inspect(String.graphemes("0123456789ábcdef"))\n'
  '    IO.inspect(String.graphemes("👨\u200d👩\u200d👧\u200d👦👨\u200d👩\u200d👧\u200d👦 🇩🇪🇫🇷🇩 👍🏽x"))\n'
  '    IO.inspect(String.graphemes("한국어 각 กำ नमस्ते"))\n'
  '    IO.inspect(length(String.graphemes(String.duplicate("é", 50))))\n'
  '    IO.inspect(length(String.graphemes(String.duplicate("́", 70))))\n'
  '    IO.inspect(length(String.graphemes(String.duplicate("🇩", 33))))\n'
  '    IO.inspect(String.graphemes(String.duplicate("ab\\r\\n", 9)))\n'
  '    IO.inspect(String.codepoints(""))\n'
  '    IO.inspect(String.codepoints("a\\r\\nb"))\n'
  '    IO.inspect(String.codepoints("éx👍🏽🇩🇪한"))\n'
  '    IO.inspect(String.split_at("éx👍🏽", 2))\n'
  '    IO.inspect(String.split_at("abc", -1))\n'
  '    IO.inspect(String.jaro_distance("martha", "marhta"))\n'
  '    IO.inspect(String.jaro_distance("dixon", "dicksonx"))\n'
  '    IO.inspect(String.jaro_distance("", "a"))\n'
  '    IO.inspect(List.duplicate("x", 3))\n'
  '    IO.inspect(List.duplicate(1, 0))\n'
  '    IO.inspect(List.flatten([[1], [], [2, 3], [4]]))\n'
  '    IO.inspect(List.zip([[1, 2, 3], [4, 5], [6, 7, 8]]))\n'
  '    IO.inspect(List.zip([1, 2, 3], ["a", "b"]))\n'
  '    e: list[list[integer]] = []\n'
  '    IO.inspect(List.zip(e))\n'
  '    IO.inspect(Path.join("/a/b/../c/./d//e", "../../x/.."))\n'
  '    IO.inspect(Path.join("../../a", "../../../b"))\n'
  '    IO.inspect(Path.join("a/b", "../../.."))\n'
  '    IO.inspect(Path.join("/..", "a/.."))\n'
  '    IO.inspect(Keyword.validate([a: 1, b: 2, c: 3, b: 4, d: 5], [:a]))\n'
  '    IO.inspect(Keyword.validate([a: 1, z: 2, y: 3, z: 4], [a: 0, q: 9]))\n'
  '    IO.inspect(Keyword.validate([a: 1], [a: 0, q: 9]))\n'
  '    IO.inspect(Enum.to_list(Stream.chunk_every(1..10, 3)))\n'
  '    IO.inspect(Enum.to_list(Stream.chunk_every(1..10, 3, 2)))\n'
  '    IO.inspect(Enum.to_list(Stream.chunk_every(1..10, 3, 5)))\n'
  '    IO.inspect(Enum.to_list(Stream.chunk_every(1..10, 4, 1)))\n'
  '    IO.inspect(Enum.to_list(Stream.chunk_every(1..3, 5, 2)))\n'
  '    IO.inspect(Enum.to_list(Stream.chunk_by([1, 1, 2, 3, 3, 3, 1], fn x -> x end)))\n'
  '    IO.inspect(Enum.to_list(Stream.chunk_by(1..10, fn x -> div(x, 4) end)))\n'
  '    IO.inspect(Enum.to_list(Stream.uniq_by([1, 2, 3, 4, 5, 6, 1], fn x -> rem(x, 3) end)))\n'
  '    IO.inspect(Enum.to_list(Stream.uniq([3, 1, 3, 2, 1])))\n'
  '    IO.inspect(OptionParser.split("a \'b c\' \\"d e\\"  f\\\\ g h\\\\"))\n'
  '    IO.inspect(OptionParser.split(""))\n'
  '    IO.inspect(OptionParser.parse(["x", "--name", "n", "y", "--bad", "-z", "--", "--k", "w"], [strict: [name: '
  ':string]]))\n'
  '    IO.inspect(OptionParser.parse(["x", "--name", "n", "y", "--k", "w"], [switches: [name: :string]]))\n'
  '    IO.inspect(OptionParser.parse_head(["--name", "n", "y", "--k", "w"], [switches: [name: :string]]))\n'
  '    IO.inspect(Enum.reduce_while([1, 2, 3, 4], 0, fn x, acc -> if x > 2 do halt(acc) else cont(acc + x) end end))\n'
  '    IO.inspect(Enum.reduce_while(e, 7, fn x, acc -> cont(acc + length(x)) end))\n'
  '    IO.inspect(Enum.flat_map([1, 2, 3], fn x -> List.duplicate(x, x) end))\n'
  '    IO.inspect(Enum.group_by(["a", "bb", "c", "dd", "eee"], fn s -> String.length(s) end))\n'
  '    IO.inspect(Enum.dedup([1.0, 1.0, 2.0]))\n'
  '    IO.inspect(Kernel.prepend([1, 2], 0))\n'
  '  end\n'
  'end\n',
  0,
  b'[]\n["a"]\n["a", "\\r\\n", "b", "\\r\\n", "\\r\\n", "c", "\\n", "\\r", "d"]\n["e\xcc\x81\xcc\x82\xcc\x83\xcc'
  b'\x84\xcc\x85\xcc\x86\xcc\x87\xcc\x88\xcc\x89\xcc\x8a\xcc\x8b\xcc\x8c\xcc\x8d", "x", "y", "z"]\n["0", "1", "2", "3"'
  b', "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e\xcc\x81", "f"]\n["0", "1", "2", "3", "4", "5", "6", "7", "8"'
  b', "9", "a", "b", "c", "d\xcc\x81", "e", "f"]\n["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", '
  b'"c\xcc\x81", "d", "e", "f"]\n["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b\xcc\x81", "c", "d", "e", '
  b'"f"]\n["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "a\xcc\x81", "b", "c", "d", "e", "f"]\n["\xf0\x9f'
  b'\x91\xa8\\u200d\xf0\x9f\x91\xa9\\u200d\xf0\x9f\x91\xa7\\u200d\xf0\x9f\x91\xa6", "\xf0\x9f\x91\xa8\\u200d\xf0\x9f'
  b'\x91\xa9\\u200d\xf0\x9f\x91\xa7\\u200d\xf0\x9f\x91\xa6", " ", "\xf0\x9f\x87\xa9\xf0\x9f\x87\xaa", "\xf0'
  b'\x9f\x87\xab\xf0\x9f\x87\xb7", "\xf0\x9f\x87\xa9", " ", "\xf0\x9f\x91\x8d\xf0\x9f\x8f\xbd", "x"]\n["\xed\x95\x9c", '
  b'"\xea\xb5\xad", "\xec\x96\xb4", " ", "\xea\xb0\x81", " ", "\xe0\xb8\x81", "\xe0\xb8\xb3", " ", "\xe0\xa4\xa8",'
  b' "\xe0\xa4\xae", "\xe0\xa4\xb8\xe0\xa5\x8d", "\xe0\xa4\xa4\xe0\xa5\x87"]\n50\n1\n17\n["a", "b", "\\r\\n", "a", "b",'
  b' "\\r\\n", "a", "b", "\\r\\n", "a", "b", "\\r\\n", "a", "b", "\\r\\n", "a", "b", "\\r\\n", "a", "b", "\\r\\n", "'
  b'a", "b", "\\r\\n", "a", "b", "\\r\\n"]\n[]\n["a", "\\r", "\\n", "b"]\n["e", "\xcc\x81", "x", "\xf0\x9f\x91\x8d"'
  b', "\xf0\x9f\x8f\xbd", "\xf0\x9f\x87\xa9", "\xf0\x9f\x87\xaa", "\xed\x95\x9c"]\n{"e\xcc\x81", "x\xf0\x9f\x91\x8d\xf0'
  b'\x9f\x8f\xbd"}\n{"ab", "c"}\n0.9444444444444445\n0.7666666666666666\n0.0\n["x", "x", "x"]\n[]\n[1, 2, 3, 4]\n[[1,'
  b' 4, 6], [2, 5, 7]]\n[{1, "a"}, {2, "b"}]\n[]\n"/a/c"\n"../../../../b"\n".."\n"/"\nerror([:b, :c, :d])\nerror([:z'
  b', :y])\nok([a: 1, q: 9])\n[[1, 2, 3], [4, 5, 6], [7, 8, 9], [10]]\n[[1, 2, 3], [3, 4, 5], [5, 6, 7], [7, 8, 9], [9,'
  b' 10]]\n[[1, 2, 3], [6, 7, 8]]\n[[1, 2, 3, 4], [2, 3, 4, 5], [3, 4, 5, 6], [4, 5, 6, 7], [5, 6, 7, 8], [6, 7, 8, 9]'
  b', [7, 8, 9, 10]]\n[]\n[[1, 1], [2], [3, 3, 3], [1]]\n[[1, 2, 3], [4, 5, 6, 7], [8, 9, 10]]\n[1, 2, 3]\n[3, 1, 2]\n'
  b'["a", "b c", "d e", "f g", "h\\\\"]\n[]\n{[name: "n"], ["x", "y", "--k", "w"], [{"--bad", none}, {"-z", none}]}\n'
  b'{[name: "n", k: "w"], ["x", "y"], []}\n{[name: "n"], ["y", "--k", "w"], []}\n3\n7\n[1, 2, 2, 3, 3, 3]\n%{1 => ["a'
  b'", "c"], 2 => ["bb", "dd"], 3 => ["eee"]}\n[1.0, 2.0]\n[0, 1, 2]\n',
  b''),
 ('defmodule Main do\n'
  '  @primes [2, 3, 5, 7]\n'
  '  @names ["a", "b"]\n'
  '  def pick(x: integer, opts: list[tuple[atom, integer]] \\\\ []): integer do\n'
  '    Keyword.get(opts, :by, 1) * x\n'
  '  end\n'
  '  def kind(x: integer): string when x in [1, 2, 3] do "small" end\n'
  '  def kind(x: integer): string do "big" end\n'
  '  def sum([]: list[integer]): integer do 0 end\n'
  '  def sum([h | t]: list[integer]): integer do h + sum(t) end\n'
  '  def pairs([a, b | t]: list[integer]): list[tuple[integer, integer]] do [{a, b} | pairs(t)] end\n'
  '  def pairs(_: list[integer]): list[tuple[integer, integer]] do [] end\n'
  '  def main() do\n'
  '    IO.inspect({@primes, [1 | @primes], @primes, [0 | tl(@primes)], @names})\n'
  '    IO.inspect({pick(3), pick(3, [by: 4]), kind(2), kind(9), sum([1 | @primes]), pairs([9 | @primes])})\n'
  '    a = for x <- @primes, into: [0, 1], do: x * x\n'
  '    b = for x <- @primes, uniq: true, do: rem(x, 3)\n'
  '    c = for x <- [1 | @primes], y <- tl(@primes), x < y, do: {x, y}\n'
  '    d = for {k, v} <- %{1 => [1], 2 => [2, 2]}, x <- [k | v], do: x\n'
  '    e = for x <- MapSet.new([3 | @primes]), do: x\n'
  '    f: list[integer] = for x <- 1..4, reduce: [] do\n'
  '      acc -> [x | acc]\n'
  '    end\n'
  '    IO.inspect({a, b, c, d, e, f})\n'
  '    IO.inspect(Enum.into([1, 2], [0]))\n'
  '    IO.inspect(Enum.into(%{1 => 2}, [{0, 0}]))\n'
  '    s = "#{inspect([1 | @primes])} #{length(@primes)}"\n'
  '    IO.inspect(s)\n'
  '    with [h | t] <- tl(@primes), [g | _] <- t do\n'
  '      IO.inspect({h, g, t})\n'
  '    end\n'
  '    r = try do\n'
  '      hd(Enum.drop(@primes, 4))\n'
  '    rescue\n'
  '      _ -> -1\n'
  '    end\n'
  '    IO.inspect(r)\n'
  '    IO.inspect(Enum.at([1 | @primes], -1))\n'
  '    IO.inspect(Enum.fetch(@primes, 9))\n'
  '    IO.inspect(List.first(Enum.drop(@primes, 4)))\n'
  '    IO.inspect(List.last([9 | @primes]))\n'
  '    IO.inspect(Enum.member?([1 | @primes], 7))\n'
  '    IO.inspect([[1 | @primes] | [@primes]] == [[1, 2, 3, 5, 7], [2, 3, 5, 7]])\n'
  '    IO.inspect(Enum.sort([[3 | @primes], @primes, tl(@primes), []]))\n'
  '    IO.inspect(Enum.max([tl(@primes), @primes]))\n'
  '    IO.inspect(Enum.slice([1 | @primes], 1..2))\n'
  '    IO.inspect(Enum.slice([1 | @primes], -2..-1))\n'
  '    IO.inspect(Enum.take([1 | @primes], -2))\n'
  '    IO.inspect(Enum.drop([1 | @primes], -2))\n'
  '    IO.inspect(Enum.split([1 | @primes], 2))\n'
  '    IO.inspect(List.delete_at([1 | @primes], 1))\n'
  '    IO.inspect(List.insert_at(@primes, 1, 9))\n'
  '    IO.inspect(List.replace_at(@primes, -1, 9))\n'
  '    IO.inspect(Enum.reverse(@primes, [0 | @primes]))\n'
  '    IO.inspect(Enum.zip(@primes, @names))\n'
  '    IO.inspect(Enum.unzip([{1, "a"}, {2, "b"}]))\n'
  '  end\n'
  'end\n',
  0,
  b'{[2, 3, 5, 7], [1, 2, 3, 5, 7], [2, 3, 5, 7], [0, 3, 5, 7], ["a", "b"]}\n{3, 12, "small", "big", 18, [{9, 2}, {3,'
  b' 5}]}\n{[0, 1, 4, 9, 25, 49], [2, 0, 1], [{1, 3}, {1, 5}, {1, 7}, {2, 3}, {2, 5}, {2, 7}, {3, 5}, {3, 7}, {5, 7}]'
  b', [1, 1, 2, 2, 2], [2, 3, 5, 7], [4, 3, 2, 1]}\n[0, 1, 2]\n[{0, 0}, {1, 2}]\n"[1, 2, 3, 5, 7] 4"\n{3, 5, [5, 7]}'
  b'\n-1\nsome(7)\nnone\nnone\nsome(7)\ntrue\ntrue\n[[], [2, 3, 5, 7], [3, 2, 3, 5, 7], [3, 5, 7]]\n[3, 5, 7]\n[2, 3]\n'
  b'[5, 7]\n[5, 7]\n[1, 2, 3]\n{[1, 2], [3, 5, 7]}\n[1, 3, 5, 7]\n[2, 9, 3, 5, 7]\n[2, 3, 5, 9]\n[7, 5, 3, 2, 0, 2, 3, '
  b'5, 7]\n[{2, "a"}, {3, "b"}]\n{[1, 2], ["a", "b"]}\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.inspect(Enum.max([1, 2]))\n'
  '    IO.inspect(Enum.min([1, 2]))\n'
  '    IO.inspect({Enum.split([1, 2, 3], 2), Enum.split([1, 2, 3], -1), Enum.split([1, 2, 3], -9)})\n'
  '    IO.inspect({Enum.count_until([1, 2, 3], 2), Enum.count_until([1, 2, 3], 9)})\n'
  '    IO.inspect({Enum.slice([1, 2, 3], 0..1), Enum.slice([1, 2, 3, 4, 5], 1..9//2)})\n'
  '    IO.inspect(String.splitter("red,green blue;x", [",", " ", ";"]) |> Enum.to_list())\n'
  '    IO.inspect(String.splitter("abc", ["x"]) |> Enum.to_list())\n'
  '  end\n'
  'end\n',
  0,
  b'2\n1\n{{[1, 2], [3]}, {[1, 2], [3]}, {[], [1, 2, 3]}}\n{2, 3}\n{[1, 2], [2, 4]}\n["red", "green", "blue", "x"]\n["'
  b'abc"]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    a = [1, 2, 3]\n'
  '    IO.inspect([0 | a])\n'
  '    e = Enum.drop(a, 3)\n'
  '    IO.inspect(hd([9 | e]))\n'
  '    IO.inspect(hd(e))\n'
  '  end\n'
  'end\n',
  2,
  b'[0, 1, 2, 3]\n9\n',
  b'<stdin>:7:16: the list is empty\n  at Main.main (<stdin>:7)\n'),
 ('defmodule Main do\n'
  '  def third(l: list[integer]): integer do\n'
  '    [_, _, x | _] = l\n'
  '    x\n'
  '  end\n'
  '  def main() do\n'
  '    a = [1, 2]\n'
  '    IO.inspect(third([0 | a]))\n'
  '    IO.inspect(third(tl(a)))\n'
  '  end\n'
  'end\n',
  2,
  b'2\n',
  b'<stdin>:3:5: pattern match failed\n  at Main.third (<stdin>:3)\n  at Main.main (<stdin>:9)\n'),
 ('defmodule Main do\n'
  '  def walk(l: list[integer], n: integer): integer do\n'
  '    case l do\n'
  '      [] -> n\n'
  '      [h | t] -> walk(t, n + div(100, h))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    a = [5, 0, 2]\n'
  '    IO.inspect(walk([4 | tl(tl(a))], 0))\n'
  '    IO.inspect([1 | a][3])\n'
  '    IO.inspect(walk([10 | a], 0))\n'
  '  end\n'
  'end\n',
  2,
  b'75\n2\n',
  b'<stdin>:5:30: division by zero\n  at Main.walk (<stdin>:5)\n  at Main.main (<stdin>:12)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    a = [1, 2, 3]\n'
  '    IO.inspect(Enum.scan([4 | a], fn x, acc -> x + acc end))\n'
  '    IO.inspect(Enum.with_index([5 | a], fn x, i -> div(x, 2 - i) end))\n'
  '  end\n'
  'end\n',
  2,
  b'[4, 5, 7, 10]\n',
  b'<stdin>:5:52: division by zero\n  at Main.main <closure> (<stdin>:5)\n  at Main.main (<stdin>:5)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    xs = [4, 2, 0, 1]\n'
  '    IO.inspect(Enum.take_every(xs, 2))\n'
  '    IO.inspect(Enum.chunk_by(xs, fn x -> div(8, x) end))\n'
  '  end\n'
  'end\n',
  2,
  b'[4, 0]\n',
  b'<stdin>:5:42: division by zero\n  at Main.main <closure> (<stdin>:5)\n  at Main.main (<stdin>:5)\n'),
 ('defmodule Main do\n'
  '  def half(x: integer): integer do\n'
  '    div(10, x)\n'
  '  end\n'
  '  def main() do\n'
  '    xs = [4, 2, 0, 1]\n'
  '    IO.inspect(Enum.map_reduce(xs, 1, fn x, acc -> {half(acc), x} end))\n'
  '    IO.inspect(Enum.zip_with(xs, xs, fn a, b -> half(a) end))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: division by zero\n  at Main.half (<stdin>:3)\n  at Main.main <closure> (<stdin>:7)\n  at Main.main (<s'
  b'tdin>:7)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    e: list[integer] = []\n'
  '    xs = [4, 4, 1, 3, 3, 3, 2]\n'
  '    IO.inspect({Enum.dedup_by(e, fn x -> x end), Enum.dedup_by([7], fn x -> x end), Enum.dedup_by(xs, fn x -> '
  'rem(x, 2) end), Enum.dedup_by(xs, fn x -> x end)})\n'
  '    IO.inspect({Enum.dedup_by([1.5, 1.6, 2.5], fn x -> trunc(x) end), Enum.dedup_by(["a", "A", "b"], fn s -> '
  'String.downcase(s) end)})\n'
  '    IO.inspect({Enum.zip_with(e, xs, fn a, b -> a + b end), Enum.zip_with(xs, e, fn a, b -> a + b end), '
  'Enum.zip_with(xs, [10, 20], fn a, b -> a + b end), Enum.zip_with([1], xs, fn a, b -> {a, b} end)})\n'
  '    IO.inspect({Enum.split_with(e, fn x -> x > 1 end), Enum.split_with(xs, fn x -> x > 2 end), Enum.split_with(xs, '
  'fn x -> x > 9 end), Enum.split_with(xs, fn x -> x < 9 end)})\n'
  '    IO.inspect({Enum.chunk_by(e, fn x -> x end), Enum.chunk_by([5], fn x -> x end), Enum.chunk_by(xs, fn x -> x '
  'end), Enum.chunk_by(xs, fn x -> x > 2 end), Enum.chunk_by(xs, fn x -> 0 end)})\n'
  '    IO.inspect({Enum.scan(e, 5, fn x, acc -> x + acc end), Enum.scan(xs, 5, fn x, acc -> x + acc end), '
  'Enum.scan(xs, "", fn x, acc -> acc <> Integer.to_string(x) end)})\n'
  '    IO.inspect({Enum.map_reduce(e, 5, fn x, acc -> {x, acc + x} end), Enum.map_reduce(xs, 0, fn x, acc -> {acc, acc '
  '+ x} end)})\n'
  '    IO.inspect({Enum.take_every(e, 2), Enum.take_every(xs, 0), Enum.take_every(xs, 1), Enum.take_every(xs, 2), '
  'Enum.take_every(xs, 3), Enum.take_every(xs, 7), Enum.take_every(xs, 8)})\n'
  '    IO.inspect({Enum.drop_every(e, 2), Enum.drop_every(xs, 0), Enum.drop_every(xs, 1), Enum.drop_every(xs, 2), '
  'Enum.drop_every(xs, 3), Enum.drop_every(xs, 7), Enum.drop_every(xs, 8)})\n'
  '    IO.inspect(Enum.zip_with(xs, xs, fn a, b -> IO.inspect({a, b}) end))\n'
  '    IO.inspect(Enum.chunk_by(xs, fn x -> IO.inspect(x) end))\n'
  '    IO.inspect(Enum.dedup_by(xs, fn x -> IO.inspect(x) end))\n'
  '    IO.inspect(Enum.split_with(%{1 => 2, 3 => 4}, fn p -> elem(p, 0) > 1 end))\n'
  '    IO.inspect(Enum.chunk_by(%{1 => 2, 3 => 2, 4 => 5}, fn p -> elem(p, 1) end))\n'
  '    IO.inspect(Enum.take_every(1..10, 3))\n'
  '    IO.inspect(Enum.zip_with(1..3, [4, 5, 6], fn a, b -> a * b end))\n'
  '    IO.inspect(Enum.map_reduce(1..3, 0, fn x, acc -> {x * 2, acc + x} end))\n'
  '    IO.inspect(Enum.take_every(xs, -1))\n'
  '  end\n'
  'end\n',
  2,
  b'{[], [7], [4, 1, 2], [4, 1, 3, 2]}\n{[1.5, 2.5], ["a", "b"]}\n{[], [], [14, 24], [{1, 4}]}\n{{[], []}, {[4, 4, 3, 3'
  b', 3], [1, 2]}, {[], [4, 4, 1, 3, 3, 3, 2]}, {[4, 4, 1, 3, 3, 3, 2], []}}\n{[], [[5]], [[4, 4], [1], [3, 3, 3], [2'
  b']], [[4, 4], [1], [3, 3, 3], [2]], [[4, 4, 1, 3, 3, 3, 2]]}\n{[], [9, 13, 14, 17, 20, 23, 25], ["4", "44", "441",'
  b' "4413", "44133", "441333", "4413332"]}\n{{[], 5}, {[0, 4, 8, 9, 12, 15, 18], 20}}\n{[], [], [4, 4, 1, 3, 3, 3, 2]'
  b', [4, 1, 3, 2], [4, 3, 2], [4], [4]}\n{[], [4, 4, 1, 3, 3, 3, 2], [], [4, 3, 3], [4, 1, 3, 3], [4, 1, 3, 3, 3, 2]'
  b', [4, 1, 3, 3, 3, 2]}\n{4, 4}\n{4, 4}\n{1, 1}\n{3, 3}\n{3, 3}\n{3, 3}\n{2, 2}\n[{4, 4}, {4, 4}, {1, 1}, {3, 3}, '
  b'{3, 3}, {3, 3}, {2, 2}]\n4\n4\n1\n3\n3\n3\n2\n[[4, 4], [1], [3, 3, 3], [2]]\n4\n4\n1\n3\n3\n3\n2\n[4, 1, 3, 2]\n{'
  b'[{3, 4}], [{1, 2}]}\n[[{1, 2}, {3, 2}], [{4, 5}]]\n[1, 4, 7, 10]\n[4, 10, 18]\n{[2, 4, 6], 6}\n',
  b'<stdin>:22:16: nth must be a nonnegative integer\n  at Main.main (<stdin>:22)\n')]
# programs the pinned compiler rejects
REJECTS=['defmodule Main do\n  def main() do\n    IO.inspect(%{[1] => 2})\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    m: map[list[integer], integer] = %{}\n    IO.inspect(m)\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.inspect([1 | 2])\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.inspect([1 | ["a"]])\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    x = [1, 2]\n    IO.inspect(["a" | x])\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.inspect([1 | [2] | [3]])\n  end\nend\n',
 'defmodule Main do\n'
 '  def main() do\n'
 '    x: list[integer] = [1 | []]\n'
 '    [h | t] = x\n'
 '    IO.inspect(h + t)\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n  def main() do\n    x = [1, 2]\n    [h | t] = x\n    IO.inspect([t | x])\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.inspect(Enum.o_room(3))\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    x: list[integer] = Enum.o_room(3)\n    IO.inspect(x)\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    IO.inspect(Enum.o_turn([1, 2]))\n  end\nend\n',
 'defmodule Main do\n'
 '  def f(m: map[k, v]): integer do\n'
 '    map_size(m)\n'
 '  end\n'
 '  def main() do\n'
 '    IO.inspect(f(%{1 => 2}))\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n'
 '  struct P[a] do\n'
 '    m: map[a, integer]\n'
 '  end\n'
 '  def main() do\n'
 '    IO.inspect(%P{m: %{1 => 2}})\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n  def main() do\n    q: map[tuple[], integer] = %{}\n    IO.inspect(q)\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    q: map[option[integer], string] = %{}\n    IO.inspect(q)\n  end\nend\n',
 'defmodule Main do\n'
 '  def f(m: list[map[map[integer, integer], integer]]): integer do\n'
 '    1\n'
 '  end\n'
 '  def main() do\n'
 '    IO.inspect(1)\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n  def main() do\n    IO.inspect([| [1]])\n  end\nend\n',
 'defmodule Main do\n  def main() do\n    x = [1]\n    IO.inspect([1 | x | x])\n  end\nend\n']

HEAD='''defmodule Main do
  def build(n: integer, acc: list[integer]): list[integer] do
    if n == 0 do acc else build(n - 1, [n | acc]) end
  end
  def total(items: list[integer], acc: integer): integer do
    case items do
      [] -> acc
      [h | t] -> total(t, acc + h)
    end
  end
  def last(items: list[integer], n: integer): integer do
    case items do
      [] -> n
      [h, _, _ | t] -> last(t, h)
      [h | t] -> last(t, h)
    end
  end
  def main() do
BODY
    System.halt(0)
  end
end
'''
# n elements are put before [] one at a time into blocks of 4, 12, 28, ...
# pairs (2^(k+3)-4; a block is 24 bytes more than its pairs), each twice the
# one before and 4 more: 64 bytes an element at most and 24 a block, and 32
# an element when the last block is just full, as at 131,068.
def started(out):
    """Run a program this process has just written. Another thread's fork may
    still hold the file open for writing for a moment (ETXTBSY)."""
    import time
    for attempt in range(200):
        try:return subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        except OSError as error:
            if error.errno!=26 or attempt==199:raise
            time.sleep(0.02)

def prepended(n):
    blocks=[];room=0
    while room<n:room=2*room+4;blocks.append(16*room+24)
    return sum(blocks)
N=100000
# 1..N as a list: the range (40 bytes: a fifth word says where a step of 0 was
# written, alchem-failures.md), its list before the range's own three
# words (16N+48) and what Enum.to_list adds (88).
LIST=40+16*N+48+88
# A list of N made at once: its block.
ONCE=16*N+24
# (statements of main, bytes charged, the bound that says the charge is linear)
#
# Walking a list by [h | t], by [h, _, _ | t] or by tl takes nothing, and
# neither does Enum.drop or a slice that ends where the list ends. A builder
# of the library takes the room of its list once (ONCE) and what it puts
# there: a tuple of two is 24 bytes, a list of two 56, a list of four 88, a
# string of one byte 16 and the 16 bytes String.graphemes reads it from 24.
# The few bytes more are the function values a call makes.
CHARGES=[
    ('x = 1',0,0),
    ('xs: list[integer] = []\n    ys = [xs, xs]',56,56),
    ('xs = build(4, [])',88,64*4+24),
    ('xs = build(5, [])',88+216,64*5+48),
    ('xs = build(100000, [])',prepended(N),64*N+24*15),
    ('xs = build(131068, [])',prepended(N),32*131068+24*15),
    ('xs = build(200000, [])',prepended(N)+16*262140+24,64*2*N+24*16),
    ('xs = build(100000, [])\n    n = total(xs, 0) + last(xs, 0) + length(tl(tl(xs)))',prepended(N),64*N+24*15),
    ('xs = Enum.to_list(1..100000)',LIST,LIST),
    ('xs = Enum.to_list(1..100000)\n    n = total(xs, 0) + last(xs, 0) + length(Enum.drop(xs, 7)) + length(Enum.slice(xs, 50000, 50000))',LIST,LIST),
    # A list that others share from below is copied once, with as much room again.
    ('xs = Enum.to_list(1..100000)\n    ys = [0 | Enum.drop(xs, 50000)]',LIST+16*(2*50000+4)+24,LIST+32*N),
    ('xs = Enum.to_list(1..100000)\n    ys = Enum.reverse(xs)',LIST+ONCE,LIST+ONCE),
    ('xs = Enum.to_list(1..100000)\n    ys = Enum.map(xs, fn x -> x + 1 end)',LIST+ONCE+16,LIST+ONCE+16),
    ('xs = Enum.to_list(1..100000)\n    ys = xs ++ xs',LIST+32*N+24,LIST+32*N+24),
    ('xs = Enum.to_list(1..100000)\n    ys = Enum.with_index(xs)',LIST+ONCE+24*N+32,LIST+40*N+56),
    ('xs = Enum.to_list(1..100000)\n    ys = Enum.zip(xs, xs)',LIST+ONCE+24*N+48,LIST+40*N+72),
    ('xs = Enum.to_list(1..100000)\n    ys = Enum.dedup(xs)',LIST+ONCE+32,LIST+16*N+56),
    ('xs = Enum.to_list(1..100000)\n    ys = Enum.scan(xs, fn x, acc -> x + acc end)',LIST+ONCE+56,LIST+16*N+80),
    # The lists the function gives (56 each), the list of them, and theirs joined.
    ('xs = Enum.to_list(1..100000)\n    ys = Enum.flat_map(xs, fn x -> [x, x] end)',LIST+56*N+ONCE+32*N+24+120,LIST+104*N+168),
    # 25,000 chunks, the last of them the list's own end, in a list with room for one more.
    ('xs = Enum.to_list(1..100000)\n    ys = Enum.chunk_every(xs, 4)',LIST+88*24999+16*25001+24,LIST+26*N),
    ('ys = String.graphemes(String.duplicate("a", 100000))',100008+ONCE+40*N-64,57*N),  # the literal "a" lies in the image: 16 bytes fewer
]

def cases():
    held=json.loads(lzma.decompress((Path(__file__).resolve().parent/'list-cases.json.xz').read_bytes()))
    return RUNS+[(source,0,stdout.encode(),b'') for source,stdout in held]


def verify(compiler):
    runs=cases()
    with tempfile.TemporaryDirectory(prefix='alchem-lists-') as d:
        root=Path(d)
        def one(item):
            index,(source,status,stdout,stderr)=item
            out=root/f'out{index}'
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.write_bytes(result.stdout);out.chmod(0o700)
            run=started(out)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run,status,stdout,stderr)
            out.unlink()
        with ThreadPoolExecutor(4) as pool:list(pool.map(one,enumerate(runs)))
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=60)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
        measured=0
        for body,expected,bound in CHARGES:
            result=subprocess.run([str(compiler)],input=HEAD.replace('BODY','    '+body).encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(body,result.returncode,result.stderr)
            target=root/'charged';target.write_bytes(result.stdout);target.chmod(0o700)
            try:
                status,data,errors,charged=profile(target,b'')
                assert (status,data,errors,charged)==(0,b'',b'',expected),(body,status,errors,charged,expected)
                assert charged<=bound,(body,charged,bound)
                measured+=1
            except TraceUnavailable:print('SKIP list arena measurement: ptrace unavailable')
    print(f'PASS lists: {len(runs)} programs run as the pinned compiler runs them ({len(runs)-len(RUNS)} of them random, ten scenarios each), {len(REJECTS)} rejected; lists made from one another and looked at again, tails, prepending in place and to a copy, the library\'s builders; arena measurements: {measured}/{len(CHARGES)}')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
