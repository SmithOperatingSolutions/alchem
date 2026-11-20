#!/usr/bin/env python3
"""Sets (spec/alchem-sets-streams.md): every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule Main do\n'
  '  def main() do\n'
  '    s = MapSet.new([3, 1, 2, 3])\n'
  '    IO.puts(inspect(s))\n'
  '    IO.inspect(MapSet.new(["b", "a"]))\n'
  '    IO.inspect(MapSet.new([true, false]))\n'
  '    t: set[integer] = MapSet.new()\n'
  '    IO.inspect(t)\n'
  '    IO.inspect(MapSet.put(t, 5))\n'
  '    IO.inspect(s == MapSet.new([1, 2, 3]))\n'
  '    IO.inspect(2 in s)\n'
  '    IO.inspect(Enum.map(s, fn x -> x * 2 end))\n'
  '    IO.inspect(for x <- s do x + 1 end)\n'
  '    IO.inspect(Enum.into([5, 4, 4], MapSet.new()))\n'
  '    IO.inspect(for x <- [3, 3, 1], into: MapSet.new() do x end)\n'
  '  end\n'
  'end\n',
  0,
  b'MapSet.new([1, 2, 3])\nMapSet.new(["a", "b"])\nMapSet.new([false, true])\nMapSet.new([])\nMapSet.new([5])\ntrue\ntrue\n[2, 4, 6]\n[2, 3, 4]\nMapSet.new(['
  b'4, 5])\nMapSet.new([1, 3])\n',
  b''),
 ('defmodule Main do\n'
  '  struct Bag do\n'
  '    items: set[string]\n'
  '    feed: stream[integer]\n'
  '  end\n'
  '  def evens(s: stream[integer]): stream[integer] do\n'
  '    Stream.filter(s, fn x -> rem(x, 2) == 0 end)\n'
  '  end\n'
  '  def firsts(s: stream[a], n: integer): list[a] do\n'
  '    Enum.take(s, n)\n'
  '  end\n'
  '  def both(a: set[integer], b: set[integer]): set[integer] do\n'
  '    MapSet.intersection(a, b)\n'
  '  end\n'
  '  def describe(s: set[integer]): string do\n'
  '    case MapSet.to_list(s) do\n'
  '      [] -> "empty"\n'
  '      [x] -> "one #{x}"\n'
  '      [x | rest] -> "#{x} and #{length(rest)} more"\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    b = %Bag{items: MapSet.new(["x", "a"]), feed: Stream.from_index(1)}\n'
  '    IO.inspect(b.items)\n'
  '    IO.inspect(Enum.take(evens(b.feed), 3))\n'
  '    IO.inspect(firsts(Stream.cycle(["a", "b"]), 3))\n'
  '    IO.inspect(firsts(Stream.map(1..5, fn x -> {x, x * x} end), 2))\n'
  '    IO.inspect(both(MapSet.new(1..10), MapSet.new(5..15//5)))\n'
  '    IO.inspect(describe(MapSet.new([3, 1, 2])))\n'
  '    IO.inspect(describe(MapSet.new([7])))\n'
  '    e: set[integer] = MapSet.new()\n'
  '    IO.inspect(describe(e))\n'
  '    IO.inspect(b)\n'
  '    sets = [MapSet.new([2, 1]), MapSet.new([1, 2]), MapSet.new([3])]\n'
  '    IO.inspect(Enum.uniq(sets))\n'
  '    IO.inspect(Enum.dedup(sets))\n'
  '    IO.inspect(MapSet.new([1]) in sets)\n'
  '    IO.inspect({MapSet.new([1, 2]) == MapSet.new([2, 1]), MapSet.new([1, 2]) != MapSet.new([2]), MapSet.equal?(MapSet.new(["a"]), MapSet.new(["a"]))})\n'
  '    m = %{"k" => MapSet.new([1])}\n'
  '    IO.inspect(Map.update(m, "k", MapSet.new([0]), fn s -> MapSet.put(s, 9) end))\n'
  '    o = some(MapSet.new([true]))\n'
  '    case o do\n'
  '      some(s) -> IO.inspect(MapSet.member?(s, true))\n'
  '      none -> IO.puts("none")\n'
  '    end\n'
  '    r = if MapSet.size(b.items) > 1 do ok(b.items) else error("few") end\n'
  '    IO.inspect(r)\n'
  '    t = try do\n'
  '      Enum.take(Stream.map(1..3, fn x -> if x == 2 do raise("boom") else x end end), 3)\n'
  '    rescue\n'
  '      err -> [0]\n'
  '    end\n'
  '    IO.inspect(t)\n'
  '    IO.inspect(Enum.reduce(MapSet.new(["b", "a"]), "", fn x, acc -> acc <> x end))\n'
  '    IO.inspect(MapSet.new(["é", "e", "z", "a", "", "aa", "B"]))\n'
  '    IO.inspect(MapSet.new([-1, 5, -9223372036854775807, 0]))\n'
  '    IO.inspect(MapSet.new([2.5, -1.0, 0.0, 1.0e10]))\n'
  '    IO.inspect(MapSet.new([:z, :a, :m]))\n'
  '    IO.inspect(MapSet.new([{2, :a}, {1, :z}, {1, :b}]))\n'
  '    IO.inspect(MapSet.filter(MapSet.new(1..10), fn x -> rem(x, 3) == 0 end))\n'
  '    IO.inspect(MapSet.reject(MapSet.new(1..10), fn x -> rem(x, 3) == 0 end))\n'
  '    IO.inspect(MapSet.split_with(MapSet.new(1..5), fn x -> x > 3 end))\n'
  '    IO.inspect({MapSet.subset?(MapSet.new([1]), MapSet.new([1, 2])), MapSet.subset?(MapSet.new([3]), MapSet.new([1, 2])), MapSet.disjoint?(MapSet.new([1]), '
  'MapSet.new([1, 2])), MapSet.disjoint?(MapSet.new([5]), MapSet.new([1, 2]))})\n'
  '    IO.inspect({MapSet.difference(MapSet.new(1..5), MapSet.new([2, 9])), MapSet.symmetric_difference(MapSet.new(1..3), MapSet.new(2..5)), '
  'MapSet.union(MapSet.new(["a"]), MapSet.new(["b", "a"]))})\n'
  '    IO.inspect({MapSet.delete(MapSet.new([1]), 5), MapSet.delete(MapSet.new([1]), 1), MapSet.put(MapSet.new([1]), 1), MapSet.size(MapSet.new("a,b,a" |> '
  'String.split(",")))})\n'
  '    IO.inspect(MapSet.new(["a", "bb", "cc"], &String.length(&1)))\n'
  '    big = MapSet.new(1..300)\n'
  '    IO.inspect({MapSet.size(big), MapSet.member?(big, 300), Enum.sum(big), 301 in big})\n'
  '  end\n'
  'end\n',
  0,
  b'MapSet.new(["a", "x"])\n[2, 4, 6]\n["a", "b", "a"]\n[{1, 1}, {2, 4}]\nMapSet.new([5, 10])\n"1 and 2 more"\n"one 7"\n"empty"\n%Bag{items: MapSet.new(["a"'
  b', "x"]), feed: #Function<>}\n[MapSet.new([1, 2]), MapSet.new([3])]\n[MapSet.new([1, 2]), MapSet.new([3])]\nfalse\n{true, true, true}\n%{"k" => MapSet.new'
  b'([1, 9])}\ntrue\nok(MapSet.new(["a", "x"]))\n[0]\n"ab"\nMapSet.new(["", "B", "a", "aa", "e", "z", "\xc3\xa9"])\nMapSet.new([-9223372036854775807, -1, 0,'
  b' 5])\nMapSet.new([-1.0, 0.0, 2.5, 10000000000.0])\nMapSet.new([:a, :m, :z])\nMapSet.new([{1, :b}, {1, :z}, {2, :a}])\nMapSet.new([3, 6, 9])\nMapSet.new(['
  b'1, 2, 4, 5, 7, 8, 10])\n{MapSet.new([4, 5]), MapSet.new([1, 2, 3])}\n{true, false, false, true}\n{MapSet.new([1, 3, 4, 5]), MapSet.new([1, 4, 5]), MapSet.n'
  b'ew(["a", "b"])}\n{MapSet.new([1]), MapSet.new([]), MapSet.new([1]), 2}\nMapSet.new([1, 2])\n{300, true, 45150, false}\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.new(MapSet.new([{1, 2}])))\n  end\nend\n', 0, b'%{1 => 2}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.new(Stream.map(1..3, fn x -> {x, x * 2} end)))\n  end\nend\n', 0, b'%{1 => 2, 2 => 4, 3 => 6}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.new(1..3, fn x -> {x, x * 2} end))\n  end\nend\n', 0, b'%{1 => 2, 2 => 4, 3 => 6}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.new(MapSet.new([1, 2]), fn x -> {x, x * 2} end))\n  end\nend\n', 0, b'%{1 => 2, 2 => 4}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.from_keys(1..3, 0))\n  end\nend\n', 0, b'%{1 => 0, 2 => 0, 3 => 0}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.take(%{1 => 2, 3 => 4}, MapSet.new([1])))\n  end\nend\n', 0, b'%{1 => 2}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.drop(%{1 => 2, 3 => 4}, 1..2))\n  end\nend\n', 0, b'%{3 => 4}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.split(%{1 => 2, 3 => 4}, Stream.take(Stream.from_index(), 2)))\n  end\nend\n',
  0,
  b'{%{1 => 2}, %{3 => 4}}\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.flatten(Stream.map(1..2, fn x -> [x] end)))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.zip(Stream.map(1..2, fn x -> [x, x] end)))\n  end\nend\n', 0, b'[[1, 2], [1, 2]]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.foldl(1..3, 0, fn x, acc -> x + acc end))\n  end\nend\n', 0, b'6\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.foldr(MapSet.new([1, 2]), 0, fn x, acc -> x - acc end))\n  end\nend\n', 0, b'-1\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.delete(1..3, 2))\n  end\nend\n', 0, b'[1, 3]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.delete_at(1..3, 0))\n  end\nend\n', 0, b'[2, 3]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.insert_at(1..3, 0, 9))\n  end\nend\n', 0, b'[9, 1, 2, 3]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.replace_at(1..3, 0, 9))\n  end\nend\n', 0, b'[9, 2, 3]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.update_at(1..3, 0, fn x -> x * 5 end))\n  end\nend\n', 0, b'[5, 2, 3]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.pop_at(1..3, 0))\n  end\nend\n', 0, b'{some(1), [2, 3]}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.starts_with?(1..3, 1..2))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(List.ends_with?(1..3, MapSet.new([3])))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Integer.undigits(1..3))\n  end\nend\n', 0, b'123\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Integer.undigits(Stream.take(Stream.cycle([1]), 3), 2))\n  end\nend\n', 0, b'7\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Path.join(MapSet.new(["a", "b"])))\n  end\nend\n', 0, b'"a/b"\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.to_list(MapSet.new([{1, 2}])))\n  end\nend\n', 0, b'[{1, 2}]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(MapSet.to_list(1..3))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(MapSet.new(Stream.map(3..1, fn x -> x end)))\n  end\nend\n', 0, b'MapSet.new([1, 2, 3])\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(MapSet.new(1..3, fn x -> rem(x, 2) end))\n  end\nend\n', 0, b'MapSet.new([0, 1])\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(MapSet.new(%{1 => 2}))\n  end\nend\n', 0, b'MapSet.new([{1, 2}])\n', b''),
 ('defmodule Main do\n  def main() do\ns = Stream.map([1], fn x -> x end)\nIO.inspect({s, [s], some(s), %{1 => s}})\n  end\nend\n',
  0,
  b'{#Function<>, [#Function<>], some(#Function<>), %{1 => #Function<>}}\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.count(MapSet.new([1, 2])))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.sum(MapSet.new([1, 2])))\n  end\nend\n', 0, b'3\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.empty?(MapSet.new([1, 2])))\n  end\nend\n', 0, b'false\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.reverse(MapSet.new([1, 2])))\n  end\nend\n', 0, b'[2, 1]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.at(MapSet.new([1, 2]), 1))\n  end\nend\n', 0, b'some(2)\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.filter(MapSet.new([1, 2]), fn x -> x > 1 end))\n  end\nend\n', 0, b'[2]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.reduce(MapSet.new([1, 2]), 0, fn x, a -> x + a end))\n  end\nend\n', 0, b'3\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.join(MapSet.new([1, 2]), ","))\n  end\nend\n', 0, b'"1,2"\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.sort(MapSet.new([2, 1]), :desc))\n  end\nend\n', 0, b'[2, 1]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.zip(MapSet.new([2, 1]), MapSet.new(["a", "b"])))\n  end\nend\n', 0, b'[{1, "a"}, {2, "b"}]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.member?(MapSet.new([2, 1]), 2))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.max(MapSet.new([2, 1])))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.group_by(MapSet.new([2, 1, 3]), fn x -> rem(x, 2) end))\n  end\nend\n',
  0,
  b'%{0 => [2], 1 => [1, 3]}\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.map(MapSet.new(["b", "a"]), &String.upcase/1))\n  end\nend\n', 0, b'["A", "B"]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.into(MapSet.new([2, 1]), []))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.into(MapSet.new([2, 1]), MapSet.new([5])))\n  end\nend\n', 0, b'MapSet.new([1, 2, 5])\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.into([{1, 2}], MapSet.new()))\n  end\nend\n', 0, b'MapSet.new([{1, 2}])\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.into(1..3, MapSet.new(), fn x -> x * 2 end))\n  end\nend\n', 0, b'MapSet.new([2, 4, 6])\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.into(Stream.take(Stream.from_index(), 2), %{}, fn x -> {x, x} end))\n  end\nend\n',
  0,
  b'%{0 => 0, 1 => 1}\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.uniq(MapSet.new([2, 1])))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule Main do\n  def main() do\nEnum.each(MapSet.new([2, 1]), fn x -> IO.puts("#{x}") end)\n  end\nend\n', 0, b'1\n2\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.into([1, 2, 3], MapSet.new(), fn x -> x * 2 end))\n  end\nend\n', 0, b'MapSet.new([2, 4, 6])\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.into([1, 2], %{}, fn x -> {x, x} end))\n  end\nend\n', 0, b'%{1 => 1, 2 => 2}\n', b''),
 ('defmodule Main do\n  def main() do\ns: set[integer] = Enum.into([1, 2, 3], MapSet.new(), fn x -> x * 2 end)\nIO.inspect(s)\n  end\nend\n',
  0,
  b'MapSet.new([2, 4, 6])\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = MapSet.new([{2, "b"}, {1, "z"}, {1, "a"}, {2, "b"}])\n'
  'IO.inspect(s)\n'
  'IO.inspect({1, "a"} in s)\n'
  'IO.inspect(MapSet.member?(s, {3, "a"}))\n'
  'IO.inspect(MapSet.put(s, {0, ""}))\n'
  'IO.inspect(MapSet.delete(s, {1, "z"}))\n'
  '  end\n'
  'end\n',
  0,
  b'MapSet.new([{1, "a"}, {1, "z"}, {2, "b"}])\ntrue\nfalse\nMapSet.new([{0, ""}, {1, "a"}, {1, "z"}, {2, "b"}])\nMapSet.new([{1, "a"}, {2, "b"}])\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'm = %{{1, 2} => "a", {0, 5} => "b"}\n'
  'IO.inspect(m)\n'
  'IO.inspect(Map.get(m, {0, 5}, ""))\n'
  'IO.inspect(Map.put(m, {0, 1}, "c"))\n'
  'IO.inspect(m[{1, 2}])\n'
  '  end\n'
  'end\n',
  0,
  b'%{{0, 5} => "b", {1, 2} => "a"}\n"b"\n%{{0, 1} => "c", {0, 5} => "b", {1, 2} => "a"}\n"a"\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(MapSet.new([{1.5, :b, true}, {1.5, :a, true}, {0.5, :z, false}, {1.5, :a, false}]))\n  end\nend\n',
  0,
  b'MapSet.new([{0.5, :z, false}, {1.5, :a, false}, {1.5, :a, true}, {1.5, :b, true}])\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(MapSet.new([{{1, 2}, "x"}, {{1, 1}, "y"}, {{0, 9}, "z"}]))\n  end\nend\n',
  0,
  b'MapSet.new([{{0, 9}, "z"}, {{1, 1}, "y"}, {{1, 2}, "x"}])\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(MapSet.union(MapSet.new([{1, 2}]), MapSet.new([{0, 3}, {1, 2}])))\n  end\nend\n',
  0,
  b'MapSet.new([{0, 3}, {1, 2}])\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(MapSet.new([{1, 2}]) == MapSet.new([{1, 2}, {1, 2}]))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.frequencies([{1, 2}, {1, 2}, {0, 1}]))\n  end\nend\n', 0, b'%{{0, 1} => 1, {1, 2} => 2}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.group_by([1, 2, 3, 4], fn x -> {rem(x, 2), x > 2} end))\n  end\nend\n',
  0,
  b'%{{0, false} => [2], {0, true} => [4], {1, false} => [1], {1, true} => [3]}\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.uniq([{1, 2}, {1, 2}]))\n  end\nend\n', 0, b'[{1, 2}]\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(MapSet.new(%{1 => "a", 2 => "b"}))\n  end\nend\n', 0, b'MapSet.new([{1, "a"}, {2, "b"}])\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Map.new(MapSet.new([{1, 2}, {0, 1}])))\n  end\nend\n', 0, b'%{0 => 1, 1 => 2}\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(for x <- [1, 2], y <- [1, 2], into: MapSet.new() do {x + y, x * y} end)\n  end\nend\n',
  0,
  b'MapSet.new([{2, 1}, {3, 2}, {4, 4}])\n',
  b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  's = MapSet.new(["b", "a"])\n'
  'IO.inspect({"a" in s, "c" in s, 3 in MapSet.new([1, 3]), 2.5 in MapSet.new([2.5]), :x in MapSet.new([:y])})\n'
  'IO.inspect({5 in 1..1000000000, 0 in 1..10, 4 in 1..10//2, 5 in 10..1, 7 in Stream.from_index(), 3 in Stream.take(Stream.from_index(), 3), {1, 2} in %{1 => '
  '2}, 2 in [1, 2]})\n'
  'for x <- 1..3 do IO.puts("#{x}") end\n'
  'IO.inspect(for x <- Stream.take(Stream.from_index(), 3), y <- MapSet.new([2, 1]) do {x, y} end)\n'
  'IO.inspect(for x <- Stream.each(1..3, fn x -> IO.puts("made #{x}") end) do IO.inspect(x) end)\n'
  'IO.inspect(for x <- 1..1000000, x > 999998 do x end)\n'
  'IO.inspect(for {k, v} <- %{1 => 2}, into: MapSet.new() do k + v end)\n'
  'IO.inspect(for x <- 3..1, uniq: true do x end)\n'
  '  end\n'
  'end\n',
  0,
  b'{true, false, true, true, false}\n{true, false, false, true, true, false, true, true}\n1\n2\n3\n[{0, 1}, {0, 2}, {1, 1}, {1, 2}, {2, 1}, {2, 2}]\nmade 1\n1'
  b'\nmade 2\n2\nmade 3\n3\n[1, 2, 3]\n[999999, 1000000]\nMapSet.new([3])\n[3, 2, 1]\n',
  b'')]

# programs the pinned compiler rejects
REJECTS=['defmodule Main do\n  def main() do\ns = Stream.map([1], fn x -> x end)\nIO.inspect(s == s)\n  end\nend\n',
 'defmodule Main do\n  def main() do\ns = Stream.map([1], fn x -> x end)\nIO.inspect([s] == [s])\n  end\nend\n',
 'defmodule Main do\n  def main() do\ns = MapSet.new([1])\nIO.inspect(s < s)\n  end\nend\n',
 'defmodule Main do\n  def main() do\ns = MapSet.new([1])\nIO.puts("#{s}")\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(MapSet.new([MapSet.new([1])]))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(%{MapSet.new([1]) => 1})\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(Enum.sort([MapSet.new([2]), MapSet.new([1])]))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(MapSet.new([1]) == MapSet.new(["a"]))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(MapSet.union(MapSet.new([1]), MapSet.new(["a"])))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(MapSet.put(MapSet.new([1]), "a"))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(MapSet.member?(MapSet.new([1]), "a"))\n  end\nend\n',
 'defmodule Main do\n  def main() do\ns: set[string] = MapSet.new([1])\nIO.inspect(s)\n  end\nend\n',
 'defmodule Main do\n  def main() do\ns: stream[string] = Stream.map([1], fn x -> x end)\nIO.inspect(s)\n  end\nend\n',
 'defmodule Main do\n  def main() do\ns: stream[integer] = [1, 2]\nIO.inspect(s)\n  end\nend\n',
 'defmodule Main do\n  def main() do\ns: set[integer] = [1, 2]\nIO.inspect(s)\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(length(MapSet.new([1])))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(hd(MapSet.new([1])))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(MapSet.new([1]) ++ [2])\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(Enum.each(MapSet.new([2, 1]), fn x -> IO.puts("#{x}") end))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(Enum.each([1], fn x -> x end))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(Enum.each(%{1 => 2}, fn x -> x end))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nx = Enum.each([1], fn x -> x end)\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(MapSet.new([{1, [2]}]))\n  end\nend\n',
 'defmodule Main do\n  def main() do\nIO.inspect(MapSet.new([{}]))\n  end\nend\n',
 'defmodule Main do\n  def add(s: set[a], x: a): set[a] do\n    MapSet.put(s, x)\n  end\n  def main() do\nIO.inspect(add(MapSet.new([1]), 2))\n  end\nend\n',
 'defmodule Main do\n  def n(xs: list[a]): integer do\n    MapSet.size(MapSet.new(xs))\n  end\n  def main() do\nIO.inspect(n([1]))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(MapSet.__map(MapSet.new([1])))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(Stream.__list(Stream.map([1], fn x -> x end)))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(Stream.__of([1]))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\ns = Stream.map([1], fn x -> x end)\nIO.inspect(Enum.to_list(s.()))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(Stream.map(5, fn x -> x end))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.map([1], fn x, y -> x end)))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take([1], "a")))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(MapSet.union(MapSet.new([1]), [2]))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.zip([1])))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nx = Stream.run([1])\n  end\nend\n',
 'defmodule Main do\n  def f(s: stream[a]): list[a] do\n    Enum.to_list(s)\n  end\n  def main() do\nIO.inspect(f([1, 2]))\n  end\nend\n',
 'defmodule Main do\n  def f(s: stream[integer]): list[integer] do\n    Enum.to_list(s)\n  end\n  def main() do\nIO.inspect(f(MapSet.new([1])))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.cycle()))\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\ns: set[list[integer]] = MapSet.new()\nIO.inspect(s)\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(MapSet.new([1]) |> Enum.map(fn x -> x end) |> MapSet.size())\n  end\nend\n',
 'defmodule Main do\n\n  def main() do\nIO.inspect(send(self(), Stream.map([1], fn x -> x end)))\n  end\nend\n']


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-sets-') as d:
        out=Path(d)/'out'
        for source,status,stdout,stderr in RUNS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=60)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=60)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=60)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    print(f'PASS sets: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; the set type, MapSet, order, equality, inspect, sets as enumerables, in, for and into, sets and maps of tuples, enumerables of every kind where a library function takes one')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
