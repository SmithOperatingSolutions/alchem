#!/usr/bin/env python3
"""Memory that is given back (spec/alchem-memory.md).

Every program here takes, over its run, several times the memory it is
allowed, and holds little of it at any moment. Each runs in an address space
in which its arena is 256 MiB (the reservation halves down to what the
system grants, nc_arena_init), must give the pinned compiler's output, and
must never have more than 64 MiB resident. Before values were given back
these programs ended with status 71 here. KEPT holds on to all it makes and
still does: the limit binds.

The programs and their expected output are written by a script from the
pinned compiler's own runs (status 0, nothing on standard error)."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import threading
import time

# (name, what it does, program, standard output as the pinned compiler gives it)
RUNS=[('server',
  'a process that handles a million messages, each a string of 800 bytes it turns to upper case',
  'defmodule Example do\n'
  '  def serve(self: pid[string], seen: integer, last: string): integer do\n'
  '    case Process.receive(self, 5000) do\n'
  '      {true, "stop"} -> seen + byte_size(last)\n'
  '      {true, m} -> serve(self, seen + 1, "handled " <> String.upcase(m))\n'
  '      {false, _} -> -1\n'
  '    end\n'
  '  end\n'
  '  def feed(to: pid[string], n: integer): integer do\n'
  '    if n == 0 do 0 else\n'
  '      Process.send(to, String.duplicate("request ", 100) <> Integer.to_string(n), 5000)\n'
  '      feed(to, n - 1)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    w: pid[string] = Process.spawn(fn(self: pid[string]): integer do\n'
  '      if serve(self, 0, "") == 1000809 do 7 else 1 end\n'
  '    end, 16)\n'
  '    feed(w, 1000000)\n'
  '    Process.send(w, "stop", 5000)\n'
  '    IO.puts(inspect(Process.await(w, 60000)))\n'
  '  end\n'
  'end\n',
  b'{true, "exit:7"}\n'),
 ('append',
  '400,000 turns of acc ++ [n] on a list of up to 2,000',
  'defmodule Example do\n'
  '  def loop(n: integer, acc: list[integer], total: integer): integer do\n'
  '    if n == 0 do\n'
  '      total + Enum.count(acc)\n'
  '    else\n'
  '      if Enum.count(acc) == 2000 do\n'
  '        loop(n - 1, [n], total + Enum.sum(acc))\n'
  '      else\n'
  '        loop(n - 1, acc ++ [n], total)\n'
  '      end\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(400000, [], 0)))\n'
  '  end\n'
  'end\n',
  b'79998201000\n'),
 ('mapput',
  '1,500,000 Map.put into a map of 64 string keys',
  'defmodule Example do\n'
  '  def loop(n: integer, m: map[string, integer]): map[string, integer] do\n'
  '    if n == 0 do m else\n'
  '      key = "k" <> Integer.to_string(rem(n, 64))\n'
  '      loop(n - 1, Map.put(m, key, Map.get(m, key, 0) + n))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    m = loop(1500000, %{})\n'
  '    IO.puts(inspect(Enum.count(m)))\n'
  '    IO.puts(inspect(Map.get(m, "k7", 0)))\n'
  '    IO.puts(inspect(Enum.sum(Map.values(m))))\n'
  '  end\n'
  'end\n',
  b'64\n17578289058\n1125000750000\n'),
 ('strings',
  '3,000,000 turns that pad, duplicate, join, replace and upcase strings',
  'defmodule Example do\n'
  '  def loop(n: integer, last: string, total: integer): integer do\n'
  '    if n == 0 do total + byte_size(last) else\n'
  '      line = String.pad_leading(Integer.to_string(n), 12, "0") <> ": " <> String.duplicate("ab", rem(n, 40)) <> "!"\n'
  '      loop(n - 1, String.upcase(line), total + byte_size(String.replace(line, "ab", "c")))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(3000000, "", 0)))\n'
  '  end\n'
  'end\n',
  b'103500017\n'),
 ('tasks',
  '150,000 tasks, one after another, each mapping over 300 numbers',
  'defmodule Example do\n'
  '  def work(n: integer): integer do\n'
  '    Enum.sum(Enum.map(Enum.to_list(n..n + 300), fn x -> rem(x, 7) end))\n'
  '  end\n'
  '  def loop(n: integer, total: integer): integer do\n'
  '    if n == 0 do total else\n'
  '      t = Task.async(fn -> work(n) end)\n'
  '      loop(n - 1, total + Task.await(t))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(150000, 0)))\n'
  '  end\n'
  'end\n',
  b'135450000\n'),
 ('churn',
  '300,000 puts and deletes of structs with lists of strings in a map of 200, summed along the way',
  'defmodule Example do\n'
  '  struct Item do\n'
  '    id: integer\n'
  '    name: string\n'
  '    tags: list[string]\n'
  '  end\n'
  '  def make(n: integer): Item do\n'
  '    %Item{id: n, name: "item-" <> Integer.to_string(n), tags: Enum.map([1, 2, 3], fn k -> "t" <> Integer.to_string(rem(n * k, 10)) end)}\n'
  '  end\n'
  '  def check(m: map[integer, Item]): integer do\n'
  '    Enum.reduce(Map.values(m), 0, fn it, acc ->\n'
  '      acc + it.id + byte_size(it.name) + Enum.sum(Enum.map(it.tags, fn t -> byte_size(t) end))\n'
  '    end)\n'
  '  end\n'
  '  def loop(n: integer, m: map[integer, Item], sum: integer): integer do\n'
  '    if n == 0 do sum + check(m) else\n'
  '      k = rem(n * 7919, 200)\n'
  '      m2 = Map.put(m, k, make(n))\n'
  '      m3 = if rem(n, 3) == 0 do Map.delete(m2, rem(n * 31, 200)) else m2 end\n'
  '      loop(n - 1, m3, if rem(n, 5000) == 0 do sum + check(m3) else sum end)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(300000, %{}, 0)))\n'
  '  end\n'
  'end\n',
  b'1464385754\n'),
 ('closures',
  '20,000 rounds of 50 function values with captured strings, streams and lists of strings',
  'defmodule Example do\n'
  '  def adders(n: integer, acc: list[fn[integer, integer]]): list[fn[integer, integer]] do\n'
  '    if n == 0 do acc else\n'
  '      label = "add" <> Integer.to_string(n)\n'
  '      adders(n - 1, [fn x -> x + n + byte_size(label) end | acc])\n'
  '    end\n'
  '  end\n'
  '  def round(n: integer, total: integer): integer do\n'
  '    if n == 0 do total else\n'
  '      fs = adders(50, [])\n'
  '      garbage = Enum.map(Enum.to_list(1..200), fn i -> Integer.to_string(i * n) end)\n'
  '      t = Enum.reduce(fs, 0, fn f, acc -> acc + f.(n) end)\n'
  '      evens = 1..n |> Stream.map(fn x -> x * 2 end) |> Stream.filter(fn x -> rem(x, 3) == 0 end) |> Enum.take(5)\n'
  '      round(n - 1, total + t + Enum.sum(evens) + byte_size(Enum.join(Enum.take(garbage, 3), ",")))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(round(20000, 0)))\n'
  '  end\n'
  'end\n',
  b'10032938741\n'),
 ('forms',
  '150,000 turns of for, case, with and cond used as values, each making lists of strings',
  'defmodule Example do\n'
  '  def pick(n: integer): result[string, string] do\n'
  '    if rem(n, 7) == 0 do error("no " <> Integer.to_string(n)) else ok(String.duplicate("p", rem(n, 30))) end\n'
  '  end\n'
  '  def round(n: integer, total: integer): integer do\n'
  '    if n == 0 do total else\n'
  '      names = for i <- 1..60, rem(i, 3) != 0 do "n" <> Integer.to_string(i * n) end\n'
  '      sizes = case rem(n, 3) do\n'
  '        0 -> Enum.map(names, fn s -> byte_size(s) end)\n'
  '        1 -> for s <- names do byte_size(s) + 1 end\n'
  '        _ -> [n]\n'
  '      end\n'
  '      got = with ok(a) <- pick(n), ok(b) <- pick(n + 1) do a <> b else error(why) -> why end\n'
  '      label = if rem(n, 2) == 0 do "even " <> got else cond do\n'
  '        rem(n, 5) == 0 -> "five"\n'
  '        true -> Enum.join(Enum.take(names, 2), "/")\n'
  '      end end\n'
  '      round(n - 1, total + Enum.sum(sizes) + byte_size(got) + byte_size(label))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(round(150000, 0)))\n'
  '  end\n'
  'end\n',
  b'3788806795\n'),
 ('deep',
  '20,000 calls deep, each holding a string and a list while the calls below it make and drop lists',
  'defmodule Example do\n'
  '  def churn(n: integer): integer do\n'
  '    Enum.count(Enum.map(Enum.to_list(1..100), fn i -> {i, Integer.to_string(i + n)} end))\n'
  '  end\n'
  '  def walk(n: integer, held: list[string]): integer do\n'
  '    if n == 0 do\n'
  '      Enum.sum(Enum.map(held, fn s -> byte_size(s) end))\n'
  '    else\n'
  '      mine = [String.duplicate("z", rem(n, 50)) <> Integer.to_string(n) | held]\n'
  '      before = churn(n)\n'
  '      below = walk(n - 1, if rem(n, 100) == 0 do [] else mine end)\n'
  '      below + Enum.count(mine) + before + churn(n + 1) + byte_size(hd(mine))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(walk(20000, [])))\n'
  '  end\n'
  'end\n',
  b'5591434\n'),
 ('prepend',
  'lists that share their ends, extended in place below a shared list and beside it',
  'defmodule Example do\n'
  '  def build(n: integer, acc: list[tuple[integer, string]]): list[tuple[integer, string]] do\n'
  '    if n == 0 do acc else build(n - 1, [{n, Integer.to_string(n * n)} | acc]) end\n'
  '  end\n'
  '  def loop(n: integer, shared: list[tuple[integer, string]], total: integer): integer do\n'
  '    if n == 0 do total else\n'
  '      mine = build(100, shared)\n'
  '      other = [{0, "zero"} | shared]\n'
  '      {a, sa} = hd(mine)\n'
  '      [_ | rest] = mine\n'
  '      keep = if rem(n, 50) == 0 do Enum.take(mine, 20) else shared end\n'
  '      loop(n - 1, Enum.take(keep, 30), total + a + byte_size(sa) + Enum.count(rest) + Enum.count(other) + byte_size(elem(hd(Enum.reverse(mine)), 1)))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(60000, [{-1, "start"}], 0)))\n'
  '  end\n'
  'end\n',
  b'8699964\n'),
 ('inspecting',
  'inspect of a list of 200,000 tuples (text that grows where it is written) and of 60,000 nested values',
  'defmodule Example do\n'
  '  def loop(n: integer, total: integer, last: string): integer do\n'
  '    if n == 0 do total + byte_size(last) else\n'
  '      value = {n, Enum.to_list(1..rem(n, 700)), %{"k" => [n, n + 1], "f" => [1]}, some(1.5), "text \\"quoted\\" " <> Integer.to_string(n)}\n'
  '      text = inspect(value)\n'
  '      loop(n - 1, total + byte_size(text), if rem(n, 1000) == 0 do text else last end)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    big = inspect(Enum.map(Enum.to_list(1..200000), fn i -> {i, Integer.to_string(i)} end))\n'
  '    IO.puts(inspect(byte_size(big)))\n'
  '    IO.puts(String.slice(big, byte_size(big) - 40, 40))\n'
  '    IO.puts(inspect(loop(60000, 0, "")))\n'
  '  end\n'
  'end\n',
  b'3777790\n {199999, "199999"}, {200000, "200000"}]\n103489523\n'),
 ('sorting',
  '4,000 sorts by a function that makes strings, with group_by and MapSet',
  'defmodule Example do\n'
  '  def loop(n: integer, total: integer): integer do\n'
  '    if n == 0 do total else\n'
  '      words = Enum.map(Enum.to_list(1..300), fn i -> Integer.to_string(rem(i * 7919 + n, 1000)) <> "w" end)\n'
  '      sorted = Enum.sort(words, fn a, b -> String.pad_leading(a, 6, "0") <= String.pad_leading(b, 6, "0") end)\n'
  '      groups = Enum.group_by(sorted, fn w -> byte_size(w) end)\n'
  '      set = MapSet.new(Enum.map(words, fn w -> rem(byte_size(w) * 31 + n, 17) end))\n'
  '      loop(n - 1, total + byte_size(hd(sorted)) + Enum.count(Map.keys(groups)) + MapSet.size(set) + byte_size(Enum.join(Enum.take(sorted, 4), "")))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(4000, 0)))\n'
  '  end\n'
  'end\n',
  b'68000\n'),
 ('failing',
  '1,000,000 turns of try with a raise in every third',
  'defmodule Example do\n'
  '  def risky(n: integer): string do\n'
  '    text = String.duplicate("e", rem(n, 300)) <> Integer.to_string(n)\n'
  '    if rem(n, 3) == 0 do raise("bad " <> text) else text end\n'
  '  end\n'
  '  def loop(n: integer, total: integer): integer do\n'
  '    if n == 0 do total else\n'
  '      got = try do\n'
  '        byte_size(risky(n))\n'
  '      rescue\n'
  '        e -> byte_size(e) + 1000\n'
  '      end\n'
  '      loop(n - 1, total + got)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(loop(1000000, 0)))\n'
  '  end\n'
  'end\n',
  b'490045328\n'),
 ('asking',
  'System.collect_garbage and System.memory around 400 MB of strings',
  'defmodule Example do\n'
  '  def fill(n: integer, total: integer): integer do\n'
  '    if n == 0 do total else fill(n - 1, total + byte_size(String.duplicate("g", 4096))) end\n'
  '  end\n'
  '  def main() do\n'
  '    before = Map.fetch!(System.memory(), :collections)\n'
  '    kept = Enum.map(Enum.to_list(1..1000), fn i -> "kept " <> Integer.to_string(i) end)\n'
  '    IO.puts(inspect(fill(100000, 0)))\n'
  '    System.collect_garbage()\n'
  '    after_it = System.memory()\n'
  '    IO.puts(inspect(Map.fetch!(after_it, :collections) > before))\n'
  '    IO.puts(inspect(Map.fetch!(after_it, :in_use) > 0 and Map.fetch!(after_it, :held) >= Map.fetch!(after_it, :idle)))\n'
  '    IO.puts(inspect(Map.fetch!(after_it, :in_use) < 64000000))\n'
  '    IO.puts(Enum.join(Enum.take(kept, 3), ", ") <> " ... " <> hd(Enum.reverse(kept)))\n'
  '  end\n'
  'end\n',
  b'409600000\ntrue\ntrue\ntrue\nkept 1, kept 2, kept 3 ... kept 1000\n'),
 ('bigmaps',
  'maps of thousands of entries (trees of leaves): 200,000 puts, deletes and lookups, string, tuple and float keys, equality, MapSet, group_by, patterns, '
  'inspect, JSON',
  'defmodule Example do\n'
  '  def next(seed: integer): integer do\n'
  '    rem(seed * 1103515245 + 12345, 2147483648)\n'
  '  end\n'
  '  def ops(n: integer, seed: integer, m: map[integer, integer], check: integer): tuple[map[integer, integer], integer] do\n'
  '    if n == 0 do {m, check} else\n'
  '      s = next(seed)\n'
  '      k = rem(div(s, 8), 3000)\n'
  '      c = rem(s, 8)\n'
  '      if c < 4 do ops(n - 1, s, Map.put(m, k, n), check + Enum.count(m)) else\n'
  '        if c < 6 do ops(n - 1, s, Map.delete(m, k), check + Map.get(m, k, -1)) else\n'
  '          ops(n - 1, s, m, check + (if Map.has_key?(m, k) do 1 else 0 end) + Map.get(m, rem(k * 7, 3000), 0))\n'
  '        end\n'
  '      end\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    first: map[integer, integer] = %{}\n'
  '    {m, check} = ops(200000, 1, first, 0)\n'
  '    IO.puts(inspect({Enum.count(m), check}))\n'
  '    IO.puts(inspect(Enum.take(Map.to_list(m), 5)))\n'
  '    IO.puts(inspect(Enum.sum(Map.keys(m)) + Enum.sum(Map.values(m))))\n'
  '    words = Enum.map(Enum.to_list(1..5000), fn i -> "w" <> Integer.to_string(rem(i * 7919, 10007)) end)\n'
  '    none: map[string, integer] = %{}\n'
  '    by = Enum.reduce(words, none, fn w, acc -> Map.put(acc, w, Map.get(acc, w, 0) + byte_size(w)) end)\n'
  '    IO.puts(inspect({Enum.count(by), Map.get(by, "w7919", 0), Enum.take(Map.keys(by), 3)}))\n'
  '    pairs = Map.new(Enum.map(Enum.to_list(1..2000), fn i -> {{rem(i, 50), "p" <> Integer.to_string(i)}, i * 3} end))\n'
  '    IO.puts(inspect({Enum.count(pairs), Map.get(pairs, {7, "p57"}, 0), Enum.take(Map.to_list(pairs), 2)}))\n'
  '    empty: map[integer, integer] = %{}\n'
  '    same = Enum.reduce(Enum.reverse(Map.to_list(m)), empty, fn {k, v}, acc -> Map.put(acc, k, v) end)\n'
  '    IO.puts(inspect({same == m, Map.put(same, -5, 1) == m, Map.delete(m, -99) == m, Map.equal?(Map.merge(m, same), m)}))\n'
  '    set = MapSet.new(Enum.map(Enum.to_list(1..3000), fn i -> rem(i * 31, 1009) end))\n'
  '    IO.puts(inspect({MapSet.size(set), MapSet.member?(set, 1008), MapSet.member?(set, 2000), Enum.take(MapSet.to_list(set), 4)}))\n'
  '    grouped = Enum.group_by(Enum.to_list(1..20000), fn i -> rem(i, 700) end)\n'
  '    IO.puts(inspect({Enum.count(grouped), Enum.take(Map.get(grouped, 5, []), 3)}))\n'
  '    freq = Enum.frequencies(words)\n'
  '    IO.puts(inspect({Enum.count(freq), Map.get(freq, "w1", 0)}))\n'
  '    total = for {k, v} <- m, rem(k, 2) == 0 do v end\n'
  '    IO.puts(inspect(Enum.sum(total)))\n'
  '    IO.puts(inspect({byte_size(inspect(m)), byte_size(JSON.encode!(by)), byte_size(inspect(set))}))\n'
  '    case Map.put(m, 77, 5) do\n'
  '      %{77 => v} -> IO.puts(inspect(v))\n'
  '      _ -> IO.puts("no")\n'
  '    end\n'
  '    nothing: map[float, integer] = %{}\n'
  '    {floats, _} = Enum.reduce(Enum.to_list(1..500), {nothing, 0.25}, fn i, {acc, f} -> {Map.put(acc, f, i), f + 0.25} end)\n'
  '    IO.puts(inspect({Enum.count(floats), Map.get(floats, 2.5, 0), Enum.take(Map.keys(floats), 3)}))\n'
  '    sorted = Map.new(Enum.map(Enum.to_list(1..1000), fn i -> {i, i * i} end))\n'
  '    more = Map.put(Map.delete(sorted, 500), 2000, 1)\n'
  '    IO.puts(inspect({Enum.count(more), Map.get(more, 999, 0), Map.get(more, 500, -1), Enum.take(Enum.reverse(Map.keys(more)), 2), sorted == more}))\n'
  '    IO.puts(inspect(Map.new(Enum.map(Enum.to_list(1..40), fn i -> {rem(i * 7, 41), i} end))))\n'
  '  end\n'
  'end\n',
  b'{1972, 6891514784}\n[{0, 5377}, {1, 6473}, {2, 9180}, {3, 2948}, {5, 4387}]\n10721588\n{5000, 5, ["w1000", "w10003", "w10004"]}\n{2000, 171, [{{0, "p100'
  b'"}, 300}, {{0, "p1000"}, 3000}]}\n{true, false, true, true}\n{1009, true, false, [0, 1, 2, 3]}\n{700, [5, 705, 1405]}\n{5000, 0}\n3824426\n{26553, 49454, '
  b'4956}\n5\n{500, 10, [0.25, 0.5, 0.75]}\n{1000, 998001, -1, [2000, 1000], false}\n%{1 => 6, 2 => 12, 3 => 18, 4 => 24, 5 => 30, 6 => 36, 7 => 1, 8 => 7, '
  b'9 => 13, 10 => 19, 11 => 25, 12 => 31, 13 => 37, 14 => 2, 15 => 8, 16 => 14, 17 => 20, 18 => 26, 19 => 32, 20 => 38, 21 => 3, 22 => 9, 23 => 15, 24 => 2'
  b'1, 25 => 27, 26 => 33, 27 => 39, 28 => 4, 29 => 10, 30 => 16, 31 => 22, 32 => 28, 33 => 34, 34 => 40, 35 => 5, 36 => 11, 37 => 17, 38 => 23, 39 => 29, 4'
  b'0 => 35}\n'),
 ('mailboxes',
  'four processes sent 100,000 lists of 20 strings each, a mailbox of 64',
  'defmodule Example do\n'
  '  def worker(self: pid[list[string]], got: integer): integer do\n'
  '    case Process.receive(self, 5000) do\n'
  '      {true, []} -> got\n'
  '      {true, batch} -> worker(self, got + Enum.sum(Enum.map(batch, fn s -> byte_size(s) end)))\n'
  '      {false, _} -> -1\n'
  '    end\n'
  '  end\n'
  '  def feed(ws: list[pid[list[string]]], n: integer): integer do\n'
  '    if n == 0 do 0 else\n'
  '      batch = Enum.map(Enum.to_list(1..20), fn i -> String.duplicate("m", rem(i * n, 97)) end)\n'
  '      Enum.each(ws, fn w -> Process.send(w, batch, 5000) end)\n'
  '      feed(ws, n - 1)\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    ws = Enum.map([1, 2, 3, 4], fn k ->\n'
  '      w: pid[list[string]] = Process.spawn(fn(self: pid[list[string]]): integer do\n'
  '        rem(worker(self, 0), 200)\n'
  '      end, 64)\n'
  '      w\n'
  '    end)\n'
  '    feed(ws, 100000)\n'
  '    none: list[string] = []\n'
  '    Enum.each(ws, fn w -> Process.send(w, none, 5000) end)\n'
  '    IO.puts(inspect(Enum.map(ws, fn w -> Process.await(w, 60000) end)))\n'
  '  end\n'
  'end\n',
  b'[{true, "exit:5"}, {true, "exit:5"}, {true, "exit:5"}, {true, "exit:5"}]\n'),
 ('appending',
  'strings built by acc <> piece: three million turns of a function that calls itself, a million of Enum.reduce and of for with reduce, and loops in which the string of a turn before is still held',
  'defmodule Example do\n'
  '  def build(n: integer, acc: string): string do\n'
  '    if n == 0 do acc else build(n - 1, acc <> "x") end\n'
  '  end\n'
  '  def digits(n: integer, acc: string, total: integer): tuple[string, integer] do\n'
  '    if n == 0 do {acc, total} else digits(n - 1, acc <> Integer.to_string(rem(n, 10)), total + byte_size(acc)) end\n'
  '  end\n'
  '  def keep(n: integer, acc: string, seen: list[string]): list[string] do\n'
  '    if n == 0 do [acc | seen] else keep(n - 1, acc <> Integer.to_string(n), [acc | seen]) end\n'
  '  end\n'
  '  def late(n: integer, acc: string, size: integer): tuple[string, integer] do\n'
  '    if n == 0 do {acc, size} else late(n - 1, acc <> "ab", byte_size(acc)) end\n'
  '  end\n'
  '  def twice(n: integer, acc: string): string do\n'
  '    if n == 0 do acc else twice(n - 1, acc <> "<" <> acc <> ">") end\n'
  '  end\n'
  '  def held(n: integer, acc: string, fs: list[fn[string]]): list[string] do\n'
  '    if n == 0 do Enum.map(fs, fn f -> f.() end) else\n'
  '      f = fn(): string do acc end\n'
  '      held(n - 1, acc <> "f", [f | fs])\n'
  '    end\n'
  '  end\n'
  '  def lines(items: list[string], acc: string): string do\n'
  '    case items do\n'
  '      [] -> acc\n'
  '      [x | rest] -> lines(rest, acc <> Enum.reduce(String.graphemes(x), "", fn c, line -> line <> c <> "." end) <> "\\n")\n'
  '    end\n'
  '  end\n'
  '  def join(items: list[string], start: string): string do\n'
  '    Enum.reduce(items, start, fn x, acc -> acc <> x end)\n'
  '  end\n'
  '  def words(n: integer): list[string] do\n'
  '    Enum.map(Enum.to_list(1..n), fn i -> "w" <> Integer.to_string(i) end)\n'
  '  end\n'
  '  def main() do\n'
  '    base = "0123456789012345678901234567890123456789"\n'
  '    long = build(3000000, "")\n'
  '    IO.puts(inspect({byte_size(long), String.slice(long, 2999990, 20)}))\n'
  '    {text, total} = digits(1000000, "", 0)\n'
  '    IO.puts(inspect({byte_size(text), total, String.slice(text, 0, 12), String.slice(text, 999990, 10)}))\n'
  '    folded = Enum.reduce(1..1000000, "", fn i, acc -> acc <> Integer.to_string(rem(i, 7)) end)\n'
  '    IO.puts(inspect({byte_size(folded), String.slice(folded, 999980, 20)}))\n'
  '    looped = for i <- 1..1000000, reduce: "" do\n'
  '      acc -> if rem(i, 3) == 0 do acc else acc <> Integer.to_string(rem(i, 5)) end\n'
  '    end\n'
  '    IO.puts(inspect({byte_size(looped), String.slice(looped, 0, 20)}))\n'
  '    piped = Enum.to_list(1..300000) |> Enum.reduce("", fn i, acc -> if acc == "" do "0" else acc <> "," <> Integer.to_string(rem(i, 9)) end end)\n'
  '    IO.puts(inspect({byte_size(piped), String.slice(piped, 0, 12)}))\n'
  '    a = build(50, base)\n'
  '    b = build(10, a)\n'
  '    c = build(3, a)\n'
  '    IO.puts(inspect({byte_size(base), byte_size(a), byte_size(b), byte_size(c), a == build(50, base), String.slice(c, 85, 10)}))\n'
  '    IO.puts(inspect(keep(4, base, [])))\n'
  '    IO.puts(inspect(late(5, base, 0)))\n'
  '    IO.puts(inspect({byte_size(twice(6, base)), twice(2, "ab")}))\n'
  '    IO.puts(inspect(held(3, base, [])))\n'
  '    IO.puts(lines(["abc", "de", "f"], base))\n'
  '    j1 = join(words(100), "")\n'
  '    j2 = join(words(50), j1)\n'
  '    j3 = join(["x", "y"], j1)\n'
  '    IO.puts(inspect({byte_size(j1), byte_size(j2), byte_size(j3), String.slice(j1, 272, 20), String.slice(j3, 274, 20)}))\n'
  '    fs = Enum.reduce(["p", "q", "r"], base, fn x, acc ->\n'
  '      f = fn(): string do acc end\n'
  '      acc <> x <> f.()\n'
  '    end)\n'
  '    IO.puts(inspect({byte_size(fs), String.slice(fs, 36, 50)}))\n'
  '    none: list[string] = []\n'
  '    IO.puts(inspect(Enum.reduce(["p", "q", "r"], {base, none}, fn x, {acc, seen} -> {acc <> x, [acc | seen]} end)))\n'
  '    IO.puts(Enum.reduce(words(40), "", fn x, acc -> if String.length(acc) > 60 do x else acc <> x end end))\n'
  '    both = Enum.reduce(["ab", "cd", "ef"], base, fn x, acc -> acc <> x <> acc end)\n'
  '    IO.puts(inspect({byte_size(both), String.slice(both, 300, 30)}))\n'
  '    kept = for x <- ["p", "q"], y <- ["1", "2"], reduce: j1 do\n'
  '      acc ->\n'
  '        one = [acc]\n'
  '        acc <> x <> y <> Integer.to_string(byte_size(hd(one)))\n'
  '    end\n'
  '    IO.puts(inspect({byte_size(kept), String.slice(kept, 285, 30), byte_size(j1)}))\n'
  '    got = try do\n'
  '      Enum.reduce(words(30), base, fn x, acc -> if x == "w20" do raise(acc <> "!") else acc <> x end end)\n'
  '    rescue\n'
  '      e -> "caught " <> Integer.to_string(byte_size(e))\n'
  '    end\n'
  '    IO.puts(inspect({got, join(["a", "b"], base)}))\n'
  '  end\n'
  'end\n',
  b'{3000000, "xxxxxxxxxx"}\n{1000000, 499999500000, "098765432109", "0987654321"}\n{1000000, "34560123456012345601"}\n{666667, "12402301341240230134"}\n{599999, "0,2,3,4,5,6,"}\n{40, 90, 100, 93, true, "xxxxxxxx"}\n["01234567890123456789012345678901234567894321", "0123456789012345678901234567890123456789432", "012345678901234567890123456789012345678943", "01234567890123456789012345678901234567894", "0123456789012345678901234567890123456789"]\n{"0123456789012345678901234567890123456789ababababab", 48}\n{2686, "ab<ab><ab<ab>>"}\n["0123456789012345678901234567890123456789ff", "0123456789012345678901234567890123456789f", "0123456789012345678901234567890123456789"]\n0123456789012345678901234567890123456789a.b.c.\nd.e.\nf.\n\n{292, 433, 294, "4w95w96w97w98w99w100", "95w96w97w98w99w100xy"}\n{327, "6789p0123456789012345678901234567890123456789q0123"}\n{"0123456789012345678901234567890123456789pqr", ["0123456789012345678901234567890123456789pq", "0123456789012345678901234567890123456789p", "0123456789012345678901234567890123456789"]}\nw25w26w27w28w29w30w31w32w33w34w35w36w37w38w39w40\n{334, "678901234567890123456789012345"}\n{312, "w99w100p1292p2297q1302q2307", 292}\n{"caught 89", "0123456789012345678901234567890123456789ab"}\n'),
 ('folds',
  'maps and sets built by Enum.reduce with Map.put, Map.update, Map.put_new and MapSet.put, changed where they are; the maps the folds started from and gave before stay as they were',
  'defmodule Example do\n'
  '  def key(i: integer): integer do\n'
  '    rem(i * 7919 + 13, 1000003)\n'
  '  end\n'
  '  def count(items: list[integer], start: map[integer, integer]): map[integer, integer] do\n'
  '    Enum.reduce(items, start, fn x, acc -> Map.put(acc, rem(x, 97), Map.get(acc, rem(x, 97), 0) + 1) end)\n'
  '  end\n'
  '  def tally(items: list[integer], start: map[integer, integer]): map[integer, integer] do\n'
  '    Enum.reduce(items, start, fn i, acc -> Map.update(acc, rem(i, 1000), 1, fn c -> c + 1 end) end)\n'
  '  end\n'
  '  def risky(items: list[integer], start: map[integer, integer]): map[integer, integer] do\n'
  '    Enum.reduce(items, start, fn x, acc -> if x == 77 do raise("stop at 77") else Map.put(acc, x, x) end end)\n'
  '  end\n'
  '  def first(): integer do\n'
  '    m0: map[integer, integer] = %{}\n'
  '    built = Enum.reduce(1..150000, m0, fn i, acc -> Map.put(acc, key(i), i) end)\n'
  '    IO.puts(inspect({map_size(built), Map.get(built, key(77), 0), Enum.take(Map.keys(built), 3), map_size(m0)}))\n'
  '    counted = Enum.reduce(1..3000000, m0, fn i, acc -> Map.update(acc, rem(i, 1000), 1, fn c -> c + 1 end) end)\n'
  '    IO.puts(inspect({map_size(counted), Map.fetch!(counted, 7), Enum.sum(Map.values(counted))}))\n'
  '    firsts = Enum.reduce(1..500000, m0, fn i, acc -> Map.put_new(acc, rem(i * 7, 3000), i) end)\n'
  '    IO.puts(inspect({map_size(firsts), Map.get(firsts, 7, 0), Map.get(firsts, 2999, 0)}))\n'
  '    s0: set[integer] = MapSet.new()\n'
  '    s1 = Enum.reduce(1..200000, s0, fn i, acc -> MapSet.put(acc, rem(i * 7919, 50021)) end)\n'
  '    s2 = Enum.reduce([1, 2, 3], s1, fn i, acc -> MapSet.put(acc, 0 - i) end)\n'
  '    IO.puts(inspect({MapSet.size(s0), MapSet.size(s1), MapSet.size(s2), MapSet.member?(s1, -1), MapSet.member?(s2, -1), Enum.take(MapSet.to_list(s2), 5)}))\n'
  '    0\n'
  '  end\n'
  '  def second(): integer do\n'
  '    m0: map[integer, integer] = %{}\n'
  '    m1 = count(Enum.to_list(1..1000), m0)\n'
  '    m2 = count(Enum.to_list(1..500), m1)\n'
  '    m3 = Map.put(m1, 5, -1)\n'
  '    m4 = count([5, 5, 5], m1)\n'
  '    IO.puts(inspect({map_size(m1), Map.get(m1, 5, 0), Map.get(m2, 5, 0), Map.get(m3, 5, 0), Map.get(m4, 5, 0)}))\n'
  '    c1 = tally(Enum.to_list(1..200000), m0)\n'
  '    c2 = tally(Enum.to_list(1..50), c1)\n'
  '    IO.puts(inspect({map_size(c1), Map.get(c1, 7, 0), Map.get(c2, 7, 0)}))\n'
  '    big = count(Enum.to_list(1..300), Map.new(Enum.map(Enum.to_list(1..5000), fn i -> {i * 3, i} end)))\n'
  '    IO.puts(inspect({map_size(big), Map.get(big, 3, 0), Map.get(big, 96, 0), Enum.take(Map.to_list(big), 4)}))\n'
  '    got = try do\n'
  '      map_size(risky(Enum.to_list(1..200), m1))\n'
  '    rescue\n'
  '      e -> byte_size(e)\n'
  '    end\n'
  '    again = risky(Enum.to_list(100..150), m1)\n'
  '    IO.puts(inspect({got, map_size(m1), Map.get(m1, 60, 0), Map.has_key?(m1, 150), map_size(again), Map.get(again, 120, 0)}))\n'
  '    nested = Enum.reduce(Enum.to_list(1..60), m0, fn x, acc ->\n'
  '      Enum.reduce(Enum.to_list(1..60), acc, fn y, inner -> Map.put(inner, x * 100 + y, map_size(inner)) end)\n'
  '    end)\n'
  '    IO.puts(inspect({map_size(nested), Map.get(nested, 6060, 0), Map.get(nested, 101, -1), Enum.sum(Map.values(nested))}))\n'
  '    sizes = Enum.reduce(Enum.to_list(1..2000), m0, fn x, acc -> Map.put(acc, x, map_size(acc)) end)\n'
  '    same = Enum.reduce(Enum.to_list(1..100), sizes, fn x, acc -> if rem(x, 2) == 0 do acc else Map.put(acc, 0 - x, x) end end)\n'
  '    IO.puts(inspect({map_size(sizes), Map.get(sizes, 2000, -1), Enum.sum(Map.values(sizes)), map_size(same), same == sizes}))\n'
  '    seen = Enum.reduce(Enum.to_list(1..2000), c1, fn i, acc -> Map.update(acc, i, map_size(acc), fn c -> c + map_size(acc) end) end)\n'
  '    IO.puts(inspect({map_size(seen), Map.get(seen, 5, 0), Map.get(seen, 1500, 0), Map.get(c1, 5, 0)}))\n'
  '    hist = Enum.reduce(Enum.to_list(1..50), {m0, 0}, fn x, {acc, n} -> {Map.put(acc, x, n), n + map_size(acc)} end)\n'
  '    IO.puts(inspect({map_size(elem(hist, 0)), elem(hist, 1)}))\n'
  '    0\n'
  '  end\n'
  '  def third(): integer do\n'
  '    m0: map[integer, integer] = %{}\n'
  '    c1 = tally(Enum.to_list(1..100000), m0)\n'
  '    firsts = Enum.reduce(1..500000, m0, fn i, acc -> Map.put_new(acc, rem(i * 7, 3000), i) end)\n'
  '    s0: set[integer] = MapSet.new()\n'
  '    s1 = Enum.reduce(1..200000, s0, fn i, acc -> MapSet.put(acc, rem(i * 7919, 50021)) end)\n'
  '    strs: map[string, string] = %{}\n'
  '    sm = Enum.reduce(1..100000, strs, fn i, acc -> Map.put(acc, "k#{rem(i * 31, 20011)}", "v#{i}") end)\n'
  '    IO.puts(inspect({map_size(sm), Map.get(sm, "k77", ""), Enum.take(Map.keys(sm), 3)}))\n'
  '    u = Enum.uniq(Enum.map(Enum.to_list(1..100000), fn i -> rem(i * 7919, 25013) end))\n'
  '    g = Enum.group_by(Enum.to_list(1..80000), fn i -> rem(i, 1000) end)\n'
  '    f = Enum.frequencies(Enum.map(Enum.to_list(1..80000), fn i -> rem(i, 777) end))\n'
  '    IO.puts(inspect({length(u), Enum.sum(u), map_size(g), Enum.take(Map.get(g, 5, []), 3), map_size(f), Map.get(f, 3, 0)}))\n'
  '    mm = Map.merge(c1, firsts)\n'
  '    ms = MapSet.new(Enum.map(Enum.to_list(1..100000), fn i -> rem(i * 31, 30011) end))\n'
  '    IO.puts(inspect({map_size(mm), Map.get(mm, 7, 0), Map.get(c1, 7, 0), MapSet.size(ms), MapSet.size(MapSet.union(ms, s1))}))\n'
  '    looped = for i <- 1..300000, reduce: m0 do\n'
  '      acc -> Map.put(acc, rem(i, 4000), Map.get(acc, rem(i, 4000), 0) + i)\n'
  '    end\n'
  '    IO.puts(inspect({map_size(looped), Map.get(looped, 7, 0)}))\n'
  '    0\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(first() + second() + third()))\n'
  '  end\n'
  'end\n',
  b'{150000, 77, [1, 4, 7], 0}\n{1000, 3000, 3000000}\n{3000, 1, 857}\n{0, 50021, 50024, false, true, [-3, -2, -1, 0, 1]}\n{97, 11, 17, -1, 14}\n{1000, 200, 201}\n{5065, 5, 35, [{0, 3}, {1, 4}, {2, 4}, {3, 5}]}\n{10, 97, 10, false, 148, 120}\n{3600, 3599, 0, 6478200}\n{2000, 1999, 1999000, 2050, false}\n{2001, 1200, 1500, 200}\n{50, 1225}\n{20011, "v80692", ["k0", "k1", "k10"]}\n{25013, 312812578, 1000, [5, 1005, 2005], 777, 103}\n{3000, 1, 100, 30011, 50021}\n{4000, 11100525}\n0\n'),
 ('keys',
  'maps of 120,000 float keys and 100,000 tuple keys as trees, with keys that are or hold a NaN, 0.0 and -0.0, deletes down to one leaf and a set of floats',
  'defmodule Example do\n'
  '  def fl(n: integer, m: map[float, integer]): map[float, integer] do\n'
  '    if n == 0 do m else fl(n - 1, Map.put(m, Float.from_integer(rem(n * 7919, 100003)) * 0.25, n)) end\n'
  '  end\n'
  '  def tu(n: integer, m: map[tuple[integer, string], integer]): map[tuple[integer, string], integer] do\n'
  '    if n == 0 do m else tu(n - 1, Map.put(m, {rem(n, 100), Integer.to_string(rem(n * 31, 50021))}, n)) end\n'
  '  end\n'
  '  def nans(n: integer, nan: float, m: map[float, integer]): map[float, integer] do\n'
  '    if n == 0 do m else nans(n - 1, nan, Map.put(Map.put(m, nan, n), Float.from_integer(n) + 0.5, n)) end\n'
  '  end\n'
  '  def pairs(n: integer, nan: float, m: map[tuple[float, integer], integer]): map[tuple[float, integer], integer] do\n'
  '    if n == 0 do m else pairs(n - 1, nan, Map.put(Map.put(m, {nan, rem(n, 7)}, n), {Float.from_integer(rem(n, 50)), n}, n)) end\n'
  '  end\n'
  '  def main() do\n'
  '    a: map[float, integer] = %{}\n'
  '    f = fl(120000, a)\n'
  '    IO.puts(inspect({map_size(f), Map.get(f, 2.5, 0), Map.get(f, 2.6, -1), Enum.take(Map.keys(f), 3), Enum.take(Enum.reverse(Map.to_list(f)), 2)}))\n'
  '    g = Enum.reduce(Enum.to_list(1..1000), f, fn i, acc -> Map.delete(acc, Float.from_integer(i) * 0.25) end)\n'
  '    IO.puts(inspect({map_size(g), Map.has_key?(g, 2.5), Map.has_key?(f, 2.5), Map.has_key?(g, 300.0), Enum.take(Map.keys(g), 2)}))\n'
  '    b: map[tuple[integer, string], integer] = %{}\n'
  '    t = tu(100000, b)\n'
  '    IO.puts(inspect({map_size(t), Map.get(t, {7, "217"}, 0), Map.get(t, {7, "nope"}, -1), Enum.take(Map.to_list(t), 3)}))\n'
  '    nan = Float.pow(-8.0, 0.5)\n'
  '    z = Map.put(Map.put(a, 0.0, 1), -0.0, 2)\n'
  '    IO.puts(inspect({map_size(z), Map.get(z, 0.0, 0), Map.get(z, -0.0, 0)}))\n'
  '    n1 = nans(40, nan, a)\n'
  '    n2 = nans(3000, nan, a)\n'
  '    IO.puts(inspect({map_size(n1), Map.get(n1, nan, -1), Map.has_key?(n1, nan), Map.get(n1, 7.5, 0), map_size(Map.delete(n1, nan)), map_size(Map.delete(n1, 7.5))}))\n'
  '    IO.puts(inspect({map_size(n2), Map.get(n2, nan, -1), Map.has_key?(n2, nan), Map.get(n2, 2999.5, 0), Map.get(n2, 0.5, -1), map_size(Map.delete(n2, nan)), map_size(Map.delete(n2, 77.5))}))\n'
  '    IO.puts(inspect({Enum.count(Map.keys(n2), fn k -> k > 0.0 end), n2 == n2, n1 == n1, Map.put(n1, 1.5, 1) == Map.put(n1, 1.5, 1)}))\n'
  '    small = Enum.reduce(Enum.to_list(1..20), n2, fn i, acc -> Map.delete(acc, Float.from_integer(i) + 0.5) end)\n'
  '    IO.puts(inspect({map_size(small), Map.get(small, 20.5, -1), Map.get(small, 21.5, -1)}))\n'
  '    shrunk = Enum.reduce(Enum.to_list(1..2990), n2, fn i, acc -> Map.delete(acc, Float.from_integer(i) + 0.5) end)\n'
  '    IO.puts(inspect({map_size(shrunk), Map.get(shrunk, 2995.5, -1), Enum.count(Map.keys(shrunk), fn k -> k > 0.0 end)}))\n'
  '    c: map[tuple[float, integer], integer] = %{}\n'
  '    p = pairs(2000, nan, c)\n'
  '    IO.puts(inspect({map_size(p), Map.get(p, {nan, 3}, -1), Map.get(p, {7.0, 57}, -1), Map.has_key?(p, {7.0, 58}), map_size(Map.delete(p, {nan, 3})), map_size(Map.delete(p, {7.0, 57}))}))\n'
  '    grown = Enum.reduce(Enum.to_list(1..100), n1, fn i, acc -> Map.put(acc, Float.from_integer(i) * 1.5, i) end)\n'
  '    IO.puts(inspect({map_size(grown), Map.get(grown, 150.0, 0), Map.get(grown, 40.5, 0), Map.has_key?(grown, nan), Enum.count(Map.keys(grown), fn k -> k > 0.0 end)}))\n'
  '    s = MapSet.new(Enum.map(Enum.to_list(1..50000), fn i -> Float.from_integer(rem(i * 7, 9973)) * 0.5 end))\n'
  '    IO.puts(inspect({MapSet.size(s), MapSet.member?(s, 3.5), MapSet.member?(s, 3.25), Enum.take(MapSet.to_list(s), 3)}))\n'
  '  end\n'
  'end\n',
  b'{100003, 73168, -1, [0.0, 0.25, 0.5], [{25000.5, 52685}, {25000.25, 5367}]}\n{99003, false, true, true, [0.0, 250.25]}\n{100000, 7, -1, [{{0, "10027"}, 21300}, {{0, "10065"}, 56800}, {{0, "10103"}, 92300}]}\n{1, 2, 2}\n{80, -1, false, 7, 80, 79}\n{6000, -1, false, 2999, -1, 6000, 5999}\n{3000, false, false, false}\n{5980, -1, 21}\n{3010, 2995, 10}\n{4000, -1, 57, false, 4000, 3999}\n{166, 100, 27, false, 126}\n{9973, true, false, [0.0, 0.5, 1.0]}\n'),
 ('dirty',
  '1,500 rounds that fill memory with bytes and addresses, drop it and build lists, maps and strings where it lay',
  'defmodule Example do\n'
  '  def junk(n: integer): integer do\n'
  '    words = Enum.map(Enum.to_list(1..2000), fn i -> {i + n, String.duplicate("\\xff", 40), [i, i + 1, i + 2]} end)\n'
  '    text = String.duplicate("z", 300000 + rem(n, 1000))\n'
  '    length(words) + byte_size(text)\n'
  '  end\n'
  '  def stack(n: integer, acc: list[integer]): list[integer] do\n'
  '    if n == 0 do acc else stack(n - 1, [n | acc]) end\n'
  '  end\n'
  '  def round(n: integer, total: integer): integer do\n'
  '    if n == 0 do total else\n'
  '      made = junk(n)\n'
  '      list = stack(3000 + rem(n, 500), [])\n'
  '      evens = Enum.filter(list, fn x -> rem(x, 2) == 0 end)\n'
  '      seen = Enum.uniq(Enum.map(list, fn x -> rem(x, 100) end))\n'
  '      empty: map[integer, integer] = %{}\n'
  '      m = Enum.reduce(list, empty, fn x, acc -> Map.put(acc, rem(x * 7, 900), x) end)\n'
  '      text = Enum.reduce(seen, "", fn x, acc -> acc <> Integer.to_string(x) end)\n'
  '      parts = String.split(String.duplicate("ab cd ", 50), " ")\n'
  '      round(n - 1, total + made + Enum.sum(list) + length(evens) + Enum.sum(seen) + map_size(m) + Enum.sum(Map.values(m)) + byte_size(text) + length(parts) + length([0 | list]))\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(round(1500, 0)))\n'
  '  end\n'
  'end\n',
  b'12187648500\n'),
 ('frames',
  '20,000 calls deep twice, each call with a list or a string it no longer needs, and functions that call themselves with bindings read in arms, fns, for and try',
  'defmodule Example do\n'
  '  struct Box do\n'
  '    label: string\n'
  '    items: list[integer]\n'
  '  end\n'
  '  def walk(n: integer): integer do\n'
  '    if n == 0 do 0 else\n'
  '      big = Enum.map(Enum.to_list(1..100), fn i -> {i, n} end)\n'
  '      c = Enum.count(big)\n'
  '      walk(n - 1) + c\n'
  '    end\n'
  '  end\n'
  '  def held(n: integer, past: list[integer]): integer do\n'
  '    if n == 0 do length(past) else\n'
  '      text = String.duplicate("t", 2000) <> Integer.to_string(n)\n'
  '      size = byte_size(text)\n'
  '      below = held(n - 1, [size | Enum.take(past, 3)])\n'
  '      below + size\n'
  '    end\n'
  '  end\n'
  '  def mixed(n: integer, acc: list[string]): list[string] do\n'
  '    if n == 0 do acc else\n'
  '      name = "n" <> Integer.to_string(n)\n'
  '      pair = {name, n}\n'
  '      box = %Box{label: name, items: [n, n + 1]}\n'
  '      opt = if rem(n, 2) == 0 do some(name) else none end\n'
  '      shown = case opt do\n'
  '        some(s) -> s <> "!"\n'
  '        none -> elem(pair, 0) <> "?"\n'
  '      end\n'
  '      parts = for i <- box.items do Integer.to_string(i) <> shown end\n'
  '      joined = Enum.join(parts, ",")\n'
  '      f = fn(x: string): string do x <> ":" <> box.label end\n'
  '      got = try do\n'
  '        if rem(n, 3) == 0 do raise(joined) else f.(joined) end\n'
  '      rescue\n'
  '        e -> "r" <> e\n'
  '      end\n'
  '      rest = mixed(n - 1, [got | acc])\n'
  '      [name | rest]\n'
  '    end\n'
  '  end\n'
  '  def twice(n: integer, text: string): string do\n'
  '    if n == 0 do text else\n'
  '      a = text <> "a"\n'
  '      b = twice(n - 1, a)\n'
  '      c = twice(n - 1, a <> "c")\n'
  '      b <> "|" <> c\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(walk(20000)))\n'
  '    IO.puts(inspect(held(20000, [])))\n'
  '    IO.puts(inspect(mixed(7, [])))\n'
  '    IO.puts(twice(3, "s"))\n'
  '  end\n'
  'end\n',
  b'2000000\n40088898\n["n7", "n6", "n5", "n4", "n3", "n2", "n1", "1n1?,2n1?:n1", "2n2!,3n2!:n2", "r3n3?,4n3?", "4n4!,5n4!:n4", "5n5?,6n5?:n5", "r6n6!,7n6!", "7n7?,8n7?:n7"]\nsaaa|saaac|saaca|saacac|sacaa|sacaac|sacaca|sacacac\n')]
# Holds on to 5,000 strings of 64 KiB: 320 MiB, more than the arena.
KEPT=('defmodule Example do\n'
 '  def keep(n: integer, held: list[string]): integer do\n'
 '    if n == 0 do Enum.count(held) else keep(n - 1, [String.duplicate("x", 65536) | held]) end\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(inspect(keep(5000, [])))\n'
 '  end\n'
 'end\n')
SPACE=512<<20
RESIDENT=64<<20


# The collector alone, in a program made here (its code follows this one's,
# which is assembled from the text below): a block of three pages is mapped
# through the collector's system-call entry, its middle page is unmapped, and
# the only address of a value of 4096 bytes is kept in its last page. After a
# collection and 8 MB of other values the value must be as it was (status 0):
# the page behind an unmapped one is still a block of the program.
# The text is spec/memory-unmapped-x86_64.s (as --64; objcopy -O binary -j .text):
#   mov r14,rsp; sub rsp,8192; lea rax,[rsp-4194304]; mov [r14-8],rax
#   mmap 64 MiB -> r12, r13 its end; call collector+15 (gm_init)
#   eax 9, rsi 12288, rdx 3, r10 0x22, r8 -1: call collector+10 -> r15
#   allocate 4096 bytes (call collector when r11 > r13), [r15+8192] = it,
#   fill it with 0x1122334455667788; allocate 64 bytes more
#   eax 11, rdi r15+4096, rsi 4096: call collector+10
#   eax 1000001: call collector+10; 2000 values of 4096 bytes of -1;
#   eax 1000001: call collector+10; compare the 512 words; exit 0 or 1
UNMAPPED=bytes([73,137,230,72,129,236,0,32,0,0,72,141,132,36,0,0,192,255,73,137,70,248,184,9,0,0,0,49,255,190,0,0,0,4,186,3,0,0,0,65,186,34,64,0,0,73,199,192,255,255,255,255,69,49,201,15,5,73,137,196,76,141,168,0,0,0,4,232,19,1,0,0,184,9,0,0,0,49,255,190,0,48,0,0,186,3,0,0,0,65,186,34,0,0,0,73,199,192,255,255,255,255,69,49,201,232,232,0,0,0,73,137,199,77,141,156,36,0,16,0,0,77,57,235,118,5,232,201,0,0,0,76,137,231,77,137,220,73,137,191,0,32,0,0,185,0,2,0,0,72,184,136,119,102,85,68,51,34,17,243,72,171,77,141,92,36,64,77,57,235,118,5,232,155,0,0,0,77,137,220,184,11,0,0,0,73,141,191,0,16,0,0,190,0,16,0,0,232,140,0,0,0,49,255,49,246,49,201,49,210,69,49,219,184,65,66,15,0,232,119,0,0,0,187,208,7,0,0,77,141,156,36,0,16,0,0,77,57,235,118,5,232,86,0,0,0,76,137,231,77,137,220,185,0,2,0,0,72,199,192,255,255,255,255,243,72,171,255,203,117,213,184,65,66,15,0,232,61,0,0,0,73,139,183,0,32,0,0,185,0,2,0,0,72,184,136,119,102,85,68,51,34,17,49,255,72,57,6,117,10,72,131,198,8,255,201,117,243,235,5,191,1,0,0,0,184,60,0,0,0,15,5])


def collector(root):
    """The collector's bytes, from the literals of native-memory-data.alc."""
    import re
    text=(root/'implementations/alchem/native-memory-data.alc').read_text()
    parts=re.findall(r'def gm_part_(\d+)\(\): bytes do b\[([0-9,]*)\] end',text)
    return b''.join(bytes(map(int,part[1].split(','))) for part in sorted(parts,key=lambda part:int(part[0])))


def unmapped(root,path):
    """UNMAPPED and the collector as an executable: one segment, read, written and run."""
    import struct
    code=UNMAPPED+collector(root);base=0x10000;size=120+len(code)
    head=b'\x7fELF\x02\x01\x01'+bytes(9)+struct.pack('<HHIQQQIHHHHHH',2,62,1,base+120,64,0,0,64,56,1,0,0,0)
    path.write_bytes(head+struct.pack('<IIQQQQQQ',1,7,0,base,base,size,size,4096)+code);path.chmod(0o700)
    return subprocess.run([str(path)],stdin=subprocess.DEVNULL,capture_output=True,timeout=60)


def bounded(executable):
    """A preexec_fn: the image and 512 MiB of address space, of which the arena takes 256 MiB."""
    space=executable.stat().st_size+SPACE
    return lambda:resource.setrlimit(resource.RLIMIT_AS,(space,space))


def resident(pid,seen):
    """The most memory the process had resident, in bytes, as the kernel counts it (VmHWM), read while it runs."""
    while True:
        try:
            for line in Path(f'/proc/{pid}/status').read_text().split('\n'):
                if line.startswith('VmHWM:'):seen[0]=max(seen[0],int(line.split()[1])*1024)
        except (OSError,ValueError):return
        time.sleep(0.02)


def run(executable,limit=True):
    process=subprocess.Popen([str(executable)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':''},preexec_fn=bounded(executable) if limit else None)
    seen=[0];watch=threading.Thread(target=resident,args=(process.pid,seen),daemon=True);watch.start()
    try:out,err=process.communicate(timeout=300)
    finally:
        if process.returncode is None:process.kill();process.wait()
    watch.join(timeout=5)
    return process.returncode,out,err,seen[0]


def build(compiler,source,path):
    result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=180)
    assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
    path.write_bytes(result.stdout);path.chmod(0o700)
    return path


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-memory-reclaim-') as d:
        root=Path(d)
        def one(item):
            name,what,source,stdout=item
            program=build(compiler,source,root/name)
            status,out,err,most=run(program)
            assert (status,out,err)==(0,stdout,b''),(name,what,status,out[-200:],err[-400:])
            assert 0<most<=RESIDENT,(name,what,'resident',most)
            return most
        with ThreadPoolExecutor(4) as pool:most=list(pool.map(one,RUNS))
        program=build(compiler,KEPT,root/'kept')
        status,out,err,_=run(program)
        assert (status,out,err)==(71,b'',b''),('kept',status,out,err)
        middle=unmapped(Path(__file__).resolve().parents[1],root/'unmapped')
        assert (middle.returncode,middle.stdout,middle.stderr)==(0,b'',b''),('unmapped',middle.returncode,middle.stderr)
    print(f'PASS memory_reclaim: {len(RUNS)} programs that take several times their 256 MiB arena run in it as the pinned compiler runs them, at most {max(most)>>20} MiB resident; one that holds on to 320 MiB exits 71; a value whose only address lies behind an unmapped page of its block is kept')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
