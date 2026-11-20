#!/usr/bin/env python3
"""Streams and lazy ranges (spec/alchem-sets-streams.md): every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule Main do\n\n  def main() do\nst = Stream.map([1, 2, 3], fn x -> x * 2 end)\nIO.inspect(st)\nIO.inspect(Enum.to_list(st))\n  end\nend\n',
  0,
  b'#Function<>\n[2, 4, 6]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(Stream.iterate(3, &(&1 * 3)), 4))\n  end\nend\n', 0, b'[3, 9, 27, 81]\n', b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect(Stream.map(1..1000000000, &(&1 * 2)) |> Enum.take(3))\n'
  'IO.inspect(Stream.filter(1..10, &(rem(&1, 3) == 0)) |> Enum.to_list())\n'
  'IO.inspect(Enum.take(1..1000000000, 3))\n'
  'IO.inspect(Enum.to_list(Stream.take(Stream.map(MapSet.new([3, 1]), fn x -> x + 1 end), 5)))\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 4, 6]\n[3, 6, 9]\n[1, 2, 3]\n[2, 4]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(1..10, 3))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(1..1000000000, 3))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule Main do\n\n  def main() do\nr = 1..1000000000\nIO.inspect(Enum.to_list(Stream.take(r, 3)))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule Main do\n\n  def main() do\ns = Stream.map(MapSet.new([3, 1]), fn x -> x + 1 end)\nIO.inspect(Enum.to_list(s))\n  end\nend\n',
  0,
  b'[2, 4]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\ns = Stream.take(Stream.map([3, 1], fn x -> x + 1 end), 5)\nIO.inspect(Enum.to_list(s))\n  end\nend\n',
  0,
  b'[4, 2]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take(Stream.map(MapSet.new([3, 1]), fn x -> x + 1 end), 5)))\n  end\nend\n',
  0,
  b'[2, 4]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take(Stream.map([3, 1], fn x -> x + 1 end), 5)))\n  end\nend\n', 0, b'[4, 2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take([3, 1], 5)))\n  end\nend\n', 0, b'[3, 1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take([3, 1], 1)))\n  end\nend\n', 0, b'[3]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.map([1, 2], fn x -> x + 1 end)))\n  end\nend\n', 0, b'[2, 3]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.filter([1, 2], fn x -> x > 1 end)))\n  end\nend\n', 0, b'[2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.reject([1, 2], fn x -> x > 1 end)))\n  end\nend\n', 0, b'[1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.each([1, 2], fn x -> x > 1 end)))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take([1, 2], 1)))\n  end\nend\n', 0, b'[1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.drop([1, 2], 1)))\n  end\nend\n', 0, b'[2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take_while([1, 2], fn x -> x < 2 end)))\n  end\nend\n', 0, b'[1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.drop_while([1, 2], fn x -> x < 2 end)))\n  end\nend\n', 0, b'[2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take_every([1, 2], 2)))\n  end\nend\n', 0, b'[1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.drop_every([1, 2], 2)))\n  end\nend\n', 0, b'[2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.map_every([1, 2], 2, fn x -> x * 5 end)))\n  end\nend\n', 0, b'[5, 2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.with_index([1, 2], 2)))\n  end\nend\n', 0, b'[{1, 2}, {2, 3}]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.with_index([1, 2])))\n  end\nend\n', 0, b'[{1, 0}, {2, 1}]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.scan([1, 2], 0, fn x, a -> x + a end)))\n  end\nend\n', 0, b'[1, 3]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.scan([1, 2], fn x, a -> x + a end)))\n  end\nend\n', 0, b'[1, 3]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.dedup_by([1, 2], fn x -> x end)))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.dedup([1, 2])))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.uniq_by([1, 2], fn x -> x end)))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.uniq([1, 2])))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(Stream.iterate(1, fn x -> x + 1 end), 2))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 # What reads a stream may write into the element it is given: iterate gives each a cell of its own.
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(Stream.map(Stream.iterate(1, fn x -> x + 1 end), fn y -> y * 2 end), 5))\nIO.inspect(Enum.count(Enum.to_list(Stream.take(Stream.map(Stream.iterate(1, fn x -> x + 1 end), fn x -> x * 2 end), 200000))))\n  end\nend\n', 0, b'[2, 4, 6, 8, 10]\n200000\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(Stream.repeatedly(fn -> 1 end), 2))\n  end\nend\n', 0, b'[1, 1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.unfold(1, fn n -> if n > 20 do none else some({n, n * 3}) end end)))\n  end\nend\n',
  0,
  b'[1, 3, 9]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(Stream.from_index(5), 2))\n  end\nend\n', 0, b'[5, 6]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(Stream.from_index(), 2))\n  end\nend\n', 0, b'[0, 1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.duplicate("a", 2)))\n  end\nend\n', 0, b'["a", "a"]\n', b''),
 ('defmodule Main do\n\n  def main() do\nStream.run(Stream.each([1, 2], fn x -> IO.puts("x") end))\n  end\nend\n', 0, b'x\nx\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.zip_with([1, 2], [3, 4], fn x, y -> x + y end)))\n  end\nend\n', 0, b'[4, 6]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.zip([1, 2], [3, 4])))\n  end\nend\n', 0, b'[{1, 3}, {2, 4}]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(Stream.cycle([1, 2]), 5))\n  end\nend\n', 0, b'[1, 2, 1, 2, 1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.concat([1, 2], [3])))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.flat_map([1, 2], fn x -> [x, x] end)))\n  end\nend\n', 0, b'[1, 1, 2, 2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.concat([[1, 2], [3]])))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.transform(1..10, 0, fn n, total -> if total + n > 6 do none else some({[total + n], total + n}) end end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 3, 6]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.intersperse([1, 2], 0)))\n  end\nend\n', 0, b'[1, 0, 2]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.chunk_every([1, 2, 3], 2, 1)))\n  end\nend\n', 0, b'[[1, 2], [2, 3]]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.chunk_every([1, 2, 3], 2)))\n  end\nend\n', 0, b'[[1, 2], [3]]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.chunk_by([1, 1, 2], fn x -> x end)))\n  end\nend\n', 0, b'[[1, 1], [2]]\n', b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.chunk_while(1..7, 0, fn n, total -> if total + n >= 6 do {some(total + n), 0} else {none, total + n} end end, fn total -> if '
  'total > 0 do some(total) else none end end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[6, 9, 6, 7]\n',
  b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.resource(fn -> 3 end, fn n -> if n == 0 do none else some({[n], n - 1}) end end, fn _ -> 0 end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[3, 2, 1]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.zip([[1, 2], [3, 4]])))\n  end\nend\n', 0, b'[[1, 3], [2, 4]]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take(Stream.interval(1), 2))\n  end\nend\n', 0, b'[0, 1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.timer(1)))\n  end\nend\n', 0, b'[0]\n', b''),
 ('defmodule Main do\n\n  def main() do\nEnum.each(Stream.map([1, 2], fn x -> x + 1 end), fn x -> IO.puts("#{x}") end)\n  end\nend\n', 0, b'2\n3\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.reduce(Stream.map([1, 2], fn x -> x + 1 end), 0, fn x, a -> x + a end))\n  end\nend\n',
  0,
  b'5\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.reduce(Stream.map([1, 2], fn x -> x + 1 end), fn x, a -> x + a end))\n  end\nend\n', 0, b'5\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.find(Stream.from_index(), fn x -> x > 3 end))\n  end\nend\n', 0, b'some(4)\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.find(Stream.take(Stream.from_index(), 2), 9, fn x -> x > 3 end))\n  end\nend\n', 0, b'9\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.find_index(Stream.from_index(5), fn x -> x > 7 end))\n  end\nend\n', 0, b'some(3)\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.find_value(Stream.from_index(5), fn x -> if x > 7 do some(x * 2) else none end end))\n  end\nend\n',
  0,
  b'some(16)\n',
  b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect(Enum.find_value(Stream.take(Stream.from_index(5), 1), 0, fn x -> if x > 7 do some(x * 2) else none end end))\n'
  '  end\n'
  'end\n',
  0,
  b'0\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.any?(Stream.from_index(), fn x -> x > 3 end))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.any?(Stream.map(1..3, fn x -> x > 3 end)))\n  end\nend\n', 0, b'false\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.all?(Stream.from_index(), fn x -> x < 3 end))\n  end\nend\n', 0, b'false\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.all?(Stream.map(1..3, fn x -> x < 5 end)))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.member?(Stream.from_index(), 7))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect({Enum.at(Stream.from_index(), 7), Enum.at(Stream.take(Stream.from_index(), 3), -1), Enum.at(Stream.take(Stream.from_index(), 3), 5)})\n'
  '  end\n'
  'end\n',
  0,
  b'{some(7), some(2), none}\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect({Enum.at(Stream.from_index(), 7, 0), Enum.at(Stream.take(Stream.from_index(), 3), 9, -1)})\n  end\nend\n',
  0,
  b'{7, -1}\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.fetch(Stream.from_index(), 7))\n  end\nend\n', 0, b'some(7)\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.fetch!(Stream.from_index(), 7))\n  end\nend\n', 0, b'7\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect({Enum.empty?(Stream.from_index()), Enum.empty?(Stream.take(Stream.from_index(), 0))})\n  end\nend\n',
  0,
  b'{false, true}\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.count_until(Stream.from_index(), fn x -> rem(x, 2) == 0 end, 4))\n  end\nend\n', 0, b'4\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect({Enum.count_until(Stream.from_index(), 4), Enum.count_until(1..1000000, 5)})\n  end\nend\n',
  0,
  b'{4, 5}\n',
  b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect(Enum.reduce_while(Stream.from_index(), 0, fn x, acc -> if x > 3 do halt(acc) else cont(acc + x) end end))\n'
  '  end\n'
  'end\n',
  0,
  b'6\n',
  b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect({Enum.count(Stream.take(Stream.from_index(), 4)), Enum.count(Stream.take(Stream.from_index(), 9), fn x -> x > 3 end), '
  'Enum.sum(Stream.take(Stream.from_index(), 4))})\n'
  '  end\n'
  'end\n',
  0,
  b'{4, 5, 6}\n',
  b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect({Enum.slice(Stream.from_index(), 2, 3), Enum.slice(Stream.take(Stream.from_index(), 9), -3, 2)})\n'
  '  end\n'
  'end\n',
  0,
  b'{[2, 3, 4], [6, 7]}\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.zip_reduce(Stream.from_index(), [5, 6], 0, fn x, y, acc -> acc + x * y end))\n  end\nend\n',
  0,
  b'6\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect({Enum.concat([1, 2], 3..4), Enum.concat(1..2, [9]), Enum.concat(1..2, 3..4)})\n  end\nend\n',
  0,
  b'{[1, 2, 3, 4], [1, 2, 9], [1, 2, 3, 4]}\n',
  b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect({Enum.map(Stream.take(Stream.from_index(), 3), fn x -> x * 2 end), Enum.filter(1..10, fn x -> x > 7 end), Enum.take_while(Stream.from_index(), '
  'fn x -> x < 3 end)})\n'
  '  end\n'
  'end\n',
  0,
  b'{[0, 2, 4], [8, 9, 10], [0, 1, 2]}\n',
  b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect({Enum.sum(1..10000000), Enum.count(1..3000000), Enum.reduce(1..3000000, 0, fn x, acc -> x + acc end)})\n'
  '  end\n'
  'end\n',
  0,
  b'{50000005000000, 3000000, 4500001500000}\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.count(Stream.map(1..3000000, fn x -> x end)))\n  end\nend\n', 0, b'3000000\n', b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect({Enum.zip(Stream.from_index(), ["a", "b"]), Enum.with_index(Stream.take(Stream.cycle(["x"]), 2)), Enum.zip(1..3, Stream.cycle([0]))})\n'
  '  end\n'
  'end\n',
  0,
  b'{[{0, "a"}, {1, "b"}], [{"x", 0}, {"x", 1}], [{1, 0}, {2, 0}, {3, 0}]}\n',
  b''),
 ('defmodule Main do\n'
  '\n'
  '  def main() do\n'
  'IO.inspect({Enum.sort(Stream.take(Stream.cycle([3, 1]), 3)), Enum.join(Stream.take(Stream.cycle(["x"]), 2), "-"), Enum.max(Stream.take(Stream.from_index(), '
  '4)), Enum.reverse(1..3)})\n'
  '  end\n'
  'end\n',
  0,
  b'{[1, 3, 3], "x-x", 3, [3, 2, 1]}\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take_while(Stream.from_index(), fn x -> x < 3 end)))\n  end\nend\n',
  0,
  b'[0, 1, 2]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take_while([0, 1, 5, 6], fn x -> x < 3 end))\n  end\nend\n', 0, b'[0, 1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.take_while(Stream.map([0, 1, 5, 6], fn x -> x end), fn x -> x < 3 end))\n  end\nend\n',
  0,
  b'[0, 1]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.to_list(Stream.take_while([0, 1, 5, 6], fn x -> x < 3 end)))\n  end\nend\n', 0, b'[0, 1]\n', b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.drop_while(Stream.map([0, 1, 5, 6], fn x -> x end), fn x -> x < 3 end))\n  end\nend\n',
  0,
  b'[5, 6]\n',
  b''),
 ('defmodule Main do\n\n  def main() do\nIO.inspect(Enum.reject(Stream.map([0, 1, 5, 6], fn x -> x end), fn x -> x < 3 end))\n  end\nend\n',
  0,
  b'[5, 6]\n',
  b''),
 ('defmodule Main do\n'
  '  def total(xs: stream[integer]): integer do Enum.sum(xs) end\n'
  '  def evens(): stream[integer] do 0..10//2 end\n'
  '  def odd(n: integer): stream[integer] do\n'
  '    if n > 0 do 1..n//2 else 1..1 end\n'
  '  end\n'
  '  def main() do\n'
  'IO.inspect(total(1..3))\n'
  's: stream[integer] = 1..3\n'
  'IO.inspect(s)\n'
  'IO.inspect(Enum.to_list(s))\n'
  'IO.inspect(Enum.to_list(evens()))\n'
  'IO.inspect(Enum.to_list(odd(7)))\n'
  'IO.inspect(1..3 |> total())\n'
  '  end\n'
  'end\n',
  0,
  b'6\n#Function<>\n[1, 2, 3]\n[0, 2, 4, 6, 8, 10]\n[1, 3, 5, 7]\n6\n',
  b''),
 ('defmodule Main do\n'
  '  def total(xs: stream[integer]): integer do Enum.sum(xs) end\n'
  '  def main() do\n'
  'IO.inspect(1..3 |> total())\n'
  'IO.inspect((1..4) |> total())\n'
  'IO.inspect(total(1..5))\n'
  'IO.inspect(1..3 |> Enum.sum())\n'
  'IO.inspect(1..3 |> Enum.map(fn x -> x end) |> Enum.sum())\n'
  '  end\n'
  'end\n',
  0,
  b'6\n10\n15\n6\n6\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(String.splitter("a,b,c", ",") |> Enum.take(2))\n'
  'IO.inspect(String.splitter("red,green blue", [",", " "]) |> Enum.to_list())\n'
  'IO.inspect(String.splitter("a b", " "))\n'
  '  end\n'
  'end\n',
  0,
  b'["a", "b"]\n["red", "green", "blue"]\n#Function<>\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.sum_by(s, fn x -> IO.puts("f #{x}")\n'
  ' x * 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n12\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.product_by(s, fn x -> IO.puts("f #{x}")\n'
  ' x * 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n48\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.frequencies_by(s, fn x -> IO.puts("f #{x}")\n'
  ' rem(x, 2) end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n%{0 => 1, 1 => 2}\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.group_by(s, fn x -> IO.puts("f #{x}")\n'
  ' rem(x, 2) end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n%{0 => [2], 1 => [1, 3]}\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.group_by(s, fn x -> IO.puts("f #{x}")\n'
  ' rem(x, 2) end, fn x -> IO.puts("g #{x}")\n'
  ' x * 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\ng 1\nmade 2\nf 2\ng 2\nmade 3\nf 3\ng 3\n%{0 => [4], 1 => [2, 6]}\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.split_with(s, fn x -> IO.puts("f #{x}")\n'
  ' rem(x, 2) == 0 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n{[2], [1, 3]}\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.map_reduce(s, 0, fn x, acc -> IO.puts("f #{x}")\n'
  ' {x * 2, acc + x} end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n{[2, 4, 6], 6}\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.flat_map_reduce(s, 0, fn x, acc -> IO.puts("f #{x}")\n'
  ' {[x, x], acc + x} end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n{[1, 1, 2, 2, 3, 3], 6}\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.with_index(s, fn x, i -> IO.puts("f #{x}")\n'
  ' x * i end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n[0, 2, 6]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.map_intersperse(s, 0, fn x -> IO.puts("f #{x}")\n'
  ' x * 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n[2, 0, 4, 0, 6]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(MapSet.new(s, fn x -> IO.puts("f #{x}")\n'
  ' x * 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\nMapSet.new([2, 4, 6])\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.map(s, fn x -> IO.puts("f #{x}")\n'
  ' x * 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n[2, 4, 6]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.filter(s, fn x -> IO.puts("f #{x}")\n'
  ' x > 1 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n[2, 3]\n',
  b''),
 ('defmodule Main do\n  def main() do\ns = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\nEnum.each(s, fn x -> IO.puts("f #{x}") end)\n  end\nend\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.reduce(s, 0, fn x, acc -> IO.puts("f #{x}")\n'
  ' x + acc end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n6\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.reduce(s, fn x, acc -> IO.puts("f #{x}")\n'
  ' x + acc end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nmade 2\nf 2\nmade 3\nf 3\n6\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.flat_map(s, fn x -> IO.puts("f #{x}")\n'
  ' [x, x] end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n[1, 1, 2, 2, 3, 3]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.take(s, 2))\n'
  'IO.inspect(Enum.take(s, 0))\n'
  'IO.inspect(Enum.take(s, -2))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nmade 2\n[1, 2]\n[]\nmade 1\nmade 2\nmade 3\n[2, 3]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.take_while(s, fn x -> IO.puts("f #{x}")\n'
  ' x < 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\n[1]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.drop_while(s, fn x -> IO.puts("f #{x}")\n'
  ' x < 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\n[2, 3]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.find(s, fn x -> IO.puts("f #{x}")\n'
  ' x > 1 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nsome(2)\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.any?(s, fn x -> IO.puts("f #{x}")\n'
  ' x > 1 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\ntrue\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.all?(s, fn x -> IO.puts("f #{x}")\n'
  ' x < 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nfalse\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.count(s, fn x -> IO.puts("f #{x}")\n'
  ' x < 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n1\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.zip(s, Stream.each([7, 8], fn x -> IO.puts("other #{x}") end)))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nother 7\nmade 2\nother 8\nmade 3\n[{1, 7}, {2, 8}]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.zip_with(Stream.each([7, 8], fn x -> IO.puts("other #{x}") end), s, fn x, y -> IO.puts("f #{x}")\n'
  ' x + y end))\n'
  '  end\n'
  'end\n',
  0,
  b'other 7\nmade 1\nf 7\nother 8\nmade 2\nf 8\n[8, 10]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.at(s, 1))\n'
  'IO.inspect(Enum.member?(s, 2))\n'
  'IO.inspect(Enum.empty?(s))\n'
  'IO.inspect(Enum.count_until(s, 2))\n'
  'IO.inspect(Enum.fetch!(s, 0))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nmade 2\nsome(2)\nmade 1\nmade 2\ntrue\nmade 1\nfalse\nmade 1\nmade 2\n2\nmade 1\n1\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.scan(s, fn x, acc -> IO.puts("f #{x}")\n'
  ' x + acc end))\n'
  'IO.inspect(Enum.scan(s, 10, fn x, acc -> IO.puts("g #{x}")\n'
  ' x + acc end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nmade 2\nf 2\nmade 3\nf 3\n[1, 3, 6]\nmade 1\ng 1\nmade 2\ng 2\nmade 3\ng 3\n[11, 13, 16]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.map_every(s, 2, fn x -> IO.puts("f #{x}")\n'
  ' x * 2 end))\n'
  'IO.inspect(Enum.dedup_by(s, fn x -> IO.puts("g #{x}")\n'
  ' x > 1 end))\n'
  'IO.inspect(Enum.uniq_by(s, fn x -> IO.puts("h #{x}")\n'
  ' x > 1 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nmade 3\nf 3\n[2, 2, 6]\nmade 1\ng 1\nmade 2\ng 2\nmade 3\ng 3\n[1, 2]\nmade 1\nh 1\nmade 2\nh 2\nmade 3\nh 3\n[1, 2]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.chunk_by(s, fn x -> IO.puts("g #{x}")\n'
  ' x > 1 end))\n'
  'IO.inspect(Enum.chunk_every(s, 2))\n'
  'IO.inspect(Enum.reject(s, fn x -> IO.puts("h #{x}")\n'
  ' x > 1 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\ng 1\nmade 2\ng 2\nmade 3\ng 3\n[[1], [2, 3]]\nmade 1\nmade 2\nmade 3\n[[1, 2], [3]]\nmade 1\nh 1\nmade 2\nh 2\nmade 3\nh 3\n[1]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.reduce_while(s, 0, fn x, acc -> IO.puts("f #{x}")\n'
  ' if x > 1 do halt(acc) else cont(acc + x) end end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\n1\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.find_index(s, fn x -> IO.puts("f #{x}")\n'
  ' x > 1 end))\n'
  'IO.inspect(Enum.find_value(s, fn x -> IO.puts("g #{x}")\n'
  ' if x > 1 do some(x) else none end end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nsome(1)\nmade 1\ng 1\nmade 2\ng 2\nsome(2)\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.map_join(s, "-", fn x -> IO.puts("f #{x}")\n'
  ' x * 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n"2-4-6"\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.sort_by(s, fn x -> IO.puts("f #{x}")\n'
  ' 0 - x end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nmade 2\nmade 3\nf 1\nf 2\nf 3\n[3, 2, 1]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'IO.inspect(Enum.into(s, [], fn x -> IO.puts("f #{x}")\n'
  ' 0 - x end))\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\nf 1\nmade 2\nf 2\nmade 3\nf 3\n[-1, -2, -3]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  's = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\n'
  'for x <- s, y <- Stream.each(1..2, fn y -> IO.puts("inner #{y}") end) do IO.puts("#{x} #{y}") end\n'
  '  end\n'
  'end\n',
  0,
  b'made 1\ninner 1\n1 1\ninner 2\n1 2\nmade 2\ninner 1\n2 1\ninner 2\n2 2\nmade 3\ninner 1\n3 1\ninner 2\n3 2\n',
  b''),
 ('defmodule Main do\n  def main() do\ns = Stream.each(1..3, fn x -> IO.puts("made #{x}") end)\nIO.inspect(2 in s)\nIO.inspect(9 in s)\n  end\nend\n',
  0,
  b'made 1\nmade 2\ntrue\nmade 1\nmade 2\nmade 3\nfalse\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.take(1..5, -2)))\n'
  'IO.inspect(Enum.to_list(Stream.take(1..5, 0)))\n'
  'IO.inspect(Enum.to_list(Stream.take(1..5, 9)))\n'
  'IO.inspect(Enum.to_list(Stream.take(1..5, -9)))\n'
  '  end\n'
  'end\n',
  0,
  b'[4, 5]\n[]\n[1, 2, 3, 4, 5]\n[1, 2, 3, 4, 5]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.drop(1..5, -2)))\n'
  'IO.inspect(Enum.to_list(Stream.drop(1..5, 0)))\n'
  'IO.inspect(Enum.to_list(Stream.drop(1..5, 9)))\n'
  'IO.inspect(Enum.to_list(Stream.drop(1..5, -9)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 3]\n[1, 2, 3, 4, 5]\n[]\n[]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.take_every(1..10, 0)))\n'
  'IO.inspect(Enum.to_list(Stream.take_every(1..10, 1)))\n'
  'IO.inspect(Enum.to_list(Stream.take_every(1..10, 3)))\n'
  '  end\n'
  'end\n',
  0,
  b'[]\n[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n[1, 4, 7, 10]\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.to_list(Stream.take_every(1..10, -1)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:25: nth must be a nonnegative integer\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.drop_every(1..10, 0)))\n'
  'IO.inspect(Enum.to_list(Stream.drop_every(1..10, 1)))\n'
  'IO.inspect(Enum.to_list(Stream.drop_every(1..10, 3)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n[]\n[2, 3, 5, 6, 8, 9]\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.to_list(Stream.drop_every(1..10, -1)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:25: nth must be a nonnegative integer\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.map_every(1..10, 0, &(&1 * 10))))\n'
  'IO.inspect(Enum.to_list(Stream.map_every(1..10, 1, &(&1 * 10))))\n'
  'IO.inspect(Enum.to_list(Stream.map_every(1..10, 3, &(&1 * 10))))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]\n[10, 2, 3, 40, 5, 6, 70, 8, 9, 100]\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.to_list(Stream.map_every(1..10, -3, &(&1 * 10))))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:25: nth must be a nonnegative integer\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.chunk_every(1..10, 3, 2)))\n'
  'IO.inspect(Enum.to_list(Stream.chunk_every(1..10, 2, 3)))\n'
  'IO.inspect(Enum.to_list(Stream.chunk_every(1..10, 3, 1)))\n'
  'IO.inspect(Enum.to_list(Stream.chunk_every(1..10, 4, 4)))\n'
  'IO.inspect(Enum.to_list(Stream.chunk_every(1..3, 5, 2)))\n'
  'IO.inspect(Enum.to_list(Stream.chunk_every(1..6, 3, 3)))\n'
  'IO.inspect(Enum.to_list(Stream.chunk_every(1..7, 3, 5)))\n'
  '  end\n'
  'end\n',
  0,
  b'[[1, 2, 3], [3, 4, 5], [5, 6, 7], [7, 8, 9], [9, 10]]\n[[1, 2], [4, 5], [7, 8], [10]]\n[[1, 2, 3], [2, 3, 4], [3, 4, 5], [4, 5, 6], [5, 6, 7], [6, 7, 8], '
  b'[7, 8, 9], [8, 9, 10]]\n[[1, 2, 3, 4], [5, 6, 7, 8], [9, 10]]\n[]\n[[1, 2, 3], [4, 5, 6]]\n[[1, 2, 3], [6, 7]]\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.to_list(Stream.chunk_every(1..10, 0)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:25: chunk_every needs a positive count and step\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.to_list(Stream.chunk_every(1..10, 2, 0)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:25: chunk_every needs a positive count and step\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  'x: list[integer] = []\n'
  'IO.inspect(Enum.to_list(Stream.chunk_every(x, 2)))\n'
  'IO.inspect(Enum.to_list(Stream.chunk_by(x, &(&1))))\n'
  'IO.inspect(Enum.to_list(Stream.dedup(x)))\n'
  'IO.inspect(Enum.to_list(Stream.uniq(x)))\n'
  'IO.inspect(Enum.to_list(Stream.intersperse(x, 0)))\n'
  'IO.inspect(Enum.to_list(Stream.zip(x, x)))\n'
  'IO.inspect(Enum.to_list(Stream.with_index(x)))\n'
  'IO.inspect(Enum.to_list(Stream.scan(x, &(&1 + &2))))\n'
  '  end\n'
  'end\n',
  0,
  b'[]\n[]\n[]\n[]\n[]\n[]\n[]\n[]\n',
  b''),
 ('defmodule Main do\n  def main() do\nx: list[integer] = []\nIO.inspect(Enum.take(Stream.cycle(x), 2))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:22: cannot cycle over an empty enumerable\n  at Main.main (<stdin>:4)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.take(Stream.cycle(1..3), 7))\n'
  'IO.inspect(Enum.take(Stream.cycle(MapSet.new([2, 1])), 3))\n'
  'IO.inspect(Enum.take(Stream.cycle(%{1 => 2}), 2))\n'
  'IO.inspect(Enum.take(Stream.cycle(Stream.take(Stream.from_index(), 2)), 5))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 3, 1, 2, 3, 1]\n[1, 2, 1]\n[{1, 2}, {1, 2}]\n[0, 1, 0, 1, 0]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.concat([1], [2])))\n'
  'IO.inspect(Enum.to_list(Stream.concat(1..2, Stream.take(Stream.from_index(5), 2))))\n'
  'IO.inspect(Enum.take(Stream.concat(Stream.from_index(), [1]), 2))\n'
  'IO.inspect(Enum.to_list(Stream.concat([[1, 2], [], [3]])))\n'
  'IO.inspect(Enum.to_list(Stream.concat(Stream.map(1..3, fn x -> [x, x] end))))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2]\n[1, 2, 5, 6]\n[0, 1]\n[1, 2, 3]\n[1, 1, 2, 2, 3, 3]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.dedup([1, 1, 2, 2, 1, 3, 3])))\n'
  'IO.inspect(Enum.to_list(Stream.dedup_by([1, 3, 2, 4, 5], &rem(&1, 2))))\n'
  'IO.inspect(Enum.to_list(Stream.dedup(["a", "a", "b"])))\n'
  'IO.inspect(Enum.to_list(Stream.dedup([{1, 2}, {1, 2}, {2, 1}])))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 1, 3]\n[1, 2, 5]\n["a", "b"]\n[{1, 2}, {2, 1}]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.uniq([3, 1, 3, 2, 1])))\n'
  'IO.inspect(Enum.to_list(Stream.uniq_by(["a", "b", "cc", "dd", "e"], &String.length(&1))))\n'
  'IO.inspect(Enum.to_list(Stream.uniq([[1], [1], [2]])))\n'
  '  end\n'
  'end\n',
  0,
  b'[3, 1, 2]\n["a", "cc"]\n[[1], [2]]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.take(Stream.iterate(1, &(&1 * 2)), 0))\n'
  'IO.inspect(Enum.take(Stream.iterate("a", &(&1 <> "b")), 3))\n'
  'IO.inspect(Enum.take(Stream.repeatedly(fn -> "x" end), 3))\n'
  'IO.inspect(Enum.take(Stream.unfold({0, 1}, fn {a, b} -> some({a, {b, a + b}}) end), 8))\n'
  '  end\n'
  'end\n',
  0,
  b'[]\n["a", "ab", "abb"]\n["x", "x", "x"]\n[0, 1, 1, 2, 3, 5, 8, 13]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.duplicate("ab", 3)))\n'
  'IO.inspect(Enum.to_list(Stream.duplicate(1, 0)))\n'
  'IO.inspect(Enum.to_list(Stream.duplicate(1, -2)))\n'
  '  end\n'
  'end\n',
  0,
  b'["ab", "ab", "ab"]\n[]\n[]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.intersperse(4..6, 0)))\n'
  'IO.inspect(Enum.to_list(Stream.intersperse([1], 0)))\n'
  'IO.inspect(Enum.take(Stream.intersperse(Stream.from_index(), -1), 4))\n'
  '  end\n'
  'end\n',
  0,
  b'[4, 0, 5, 0, 6]\n[1]\n[0, -1, 1, -1]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.scan(1..4, &(&1 + &2))))\n'
  'IO.inspect(Enum.to_list(Stream.scan(1..4, 10, &(&1 + &2))))\n'
  'IO.inspect(Enum.to_list(Stream.scan(["a", "b"], "", fn x, acc -> acc <> x end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 3, 6, 10]\n[11, 13, 16, 20]\n["a", "ab"]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.with_index(["a", "b"])))\n'
  'IO.inspect(Enum.to_list(Stream.with_index(["a", "b"], 5)))\n'
  'IO.inspect(Enum.to_list(Stream.with_index(["a", "b"], -1)))\n'
  '  end\n'
  'end\n',
  0,
  b'[{"a", 0}, {"b", 1}]\n[{"a", 5}, {"b", 6}]\n[{"a", -1}, {"b", 0}]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.zip(Stream.from_index(), ["a", "b"])))\n'
  'IO.inspect(Enum.to_list(Stream.zip([1, 2, 3], [4])))\n'
  'IO.inspect(Enum.to_list(Stream.zip([[1, 2], [3, 4], [5, 6]])))\n'
  'IO.inspect(Enum.to_list(Stream.zip([[1, 2], [3]])))\n'
  'IO.inspect(Enum.to_list(Stream.zip_with(1..3, Stream.cycle([10]), &(&1 + &2))))\n'
  '  end\n'
  'end\n',
  0,
  b'[{0, "a"}, {1, "b"}]\n[{1, 4}]\n[[1, 3, 5], [2, 4, 6]]\n[[1, 3]]\n[11, 12, 13]\n',
  b''),
 ('defmodule Main do\n  def main() do\nx: list[list[integer]] = []\nIO.inspect(Enum.to_list(Stream.zip(x)))\n  end\nend\n', 0, b'[]\n', b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.flat_map(1..3, fn n -> if n == 2 do [] else [n, -n] end end)))\n'
  'IO.inspect(Enum.take(Stream.flat_map(Stream.from_index(), fn n -> [n, n] end), 5))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, -1, 3, -3]\n[0, 0, 1, 1, 2]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.chunk_by([1, 1, 2, 3, 3], &(&1))))\n'
  'IO.inspect(Enum.to_list(Stream.chunk_by(1..6, &(rem(&1, 3) == 0))))\n'
  'IO.inspect(Enum.take(Stream.chunk_by(Stream.from_index(), &div(&1, 3)), 2))\n'
  '  end\n'
  'end\n',
  0,
  b'[[1, 1], [2], [3, 3]]\n[[1, 2], [3], [4, 5], [6]]\n[[0, 1, 2], [3, 4, 5]]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.chunk_while(1..7, 0, fn n, total -> if total + n >= 6 do {some(total + n), 0} else {none, total + n} end end, fn total -> if '
  'total > 0 do some(total) else none end end)))\n'
  'IO.inspect(Enum.take(Stream.chunk_while(Stream.from_index(), 0, fn n, total -> if total + n >= 6 do {some(total + n), 0} else {none, total + n} end end, fn '
  'total -> none end), 2))\n'
  '  end\n'
  'end\n',
  0,
  b'[6, 9, 6, 7]\n[6, 9]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.to_list(Stream.take_while(1..10, &(&1 < 4))))\n'
  'IO.inspect(Enum.to_list(Stream.drop_while(1..6, &(&1 < 4))))\n'
  'IO.inspect(Enum.to_list(Stream.drop_while([1, 5, 1], &(&1 < 4))))\n'
  'IO.inspect(Enum.to_list(Stream.reject(1..6, &(rem(&1, 2) == 0))))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 2, 3]\n[4, 5, 6]\n[5, 1]\n[1, 3, 5]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.take(Stream.from_index(9223372036854775806), 5))\n'
  'IO.inspect(Enum.to_list(Stream.take(Stream.from_index(-3), 4)))\n'
  '  end\n'
  'end\n',
  0,
  b'[9223372036854775806, 9223372036854775807]\n[-3, -2, -1, 0]\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.to_list(Stream.timer(1)))\nIO.inspect(Enum.take(Stream.interval(1), 3))\n  end\nend\n',
  0,
  b'[0]\n[0, 1, 2]\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.take(Stream.interval(-1), 3))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:22: sleep duration must be nonnegative\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.to_list(Stream.timer(-1)))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:25: sleep duration must be nonnegative\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  'c = Stream.resource(fn -> IO.puts("open")\n'
  ' 3 end, fn n -> if n == 0 do none else some({[n, n * 10], n - 1}) end end, fn n -> IO.puts("close #{n}") end)\n'
  'IO.inspect(Enum.to_list(c))\n'
  'IO.inspect(Enum.take(c, 3))\n'
  'IO.inspect(Enum.take(c, 0))\n'
  'IO.inspect(Enum.find(c, fn x -> x == 20 end))\n'
  '  end\n'
  'end\n',
  0,
  b'open\nclose 0\n[3, 30, 2, 20, 1, 10]\nopen\nclose 1\n[3, 30, 2]\n[]\nopen\nclose 1\nsome(20)\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'c = Stream.resource(fn -> IO.puts("open")\n'
  ' 3 end, fn n -> if n == 0 do none else some({[n, n * 10], n - 1}) end end, fn n -> IO.puts("close #{n}") end)\n'
  'IO.inspect(Enum.zip(c, [1]))\n'
  'IO.inspect(Enum.zip([1], c))\n'
  'IO.inspect(Enum.to_list(Stream.concat(c, c)))\n'
  'IO.inspect(Enum.take(Stream.cycle(c), 8))\n'
  '  end\n'
  'end\n',
  0,
  b'open\nclose 2\n[{3, 1}]\nopen\nclose 2\n[{1, 3}]\nopen\nclose 0\nopen\nclose 0\n[3, 30, 2, 20, 1, 10, 3, 30, 2, 20, 1, 10]\nopen\nclose 0\nopen\nclose 2\n['
  b'3, 30, 2, 20, 1, 10, 3, 30]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'c = Stream.resource(fn -> IO.puts("open")\n'
  ' 3 end, fn n -> if n == 0 do none else some({[n, n * 10], n - 1}) end end, fn n -> IO.puts("close #{n}") end)\n'
  'for x <- c, x > 20 do IO.puts("got #{x}") end\n'
  'IO.inspect(30 in c)\n'
  'IO.inspect(Enum.take(Stream.map(c, fn x -> x + 1 end), 1))\n'
  'IO.inspect(Enum.at(c, 1))\n'
  'Stream.run(c)\n'
  '  end\n'
  'end\n',
  0,
  b'open\ngot 30\nclose 0\nopen\nclose 2\ntrue\nopen\nclose 2\n[4]\nopen\nclose 2\nsome(30)\nopen\nclose 0\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'c = Stream.resource(fn -> IO.puts("open")\n'
  ' 3 end, fn n -> if n == 0 do none else some({[n, n * 10], n - 1}) end end, fn n -> IO.puts("close #{n}") end)\n'
  'd = Stream.resource(fn -> IO.puts("open d")\n'
  ' 2 end, fn n -> if n == 0 do none else some({[n], n - 1}) end end, fn n -> IO.puts("close d #{n}") end)\n'
  'IO.inspect(Enum.take(Stream.zip(c, d), 1))\n'
  'IO.inspect(Enum.to_list(Stream.zip(c, d)))\n'
  'IO.inspect(Enum.to_list(Stream.zip(d, c)))\n'
  '  end\n'
  'end\n',
  0,
  b'open\nopen d\nclose 2\nclose d 1\n[{3, 2}]\nopen\nopen d\nclose d 0\nclose 1\n[{3, 2}, {30, 1}]\nopen d\nopen\nclose d 0\nclose 2\n[{2, 3}, {1, 30}]\n',
  b''),
 ('defmodule Main do\n  def main() do\n    IO.inspect(Enum.fetch!([1], 5))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:16: out of bounds error\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n'
  '  def pick(xs: list[integer]): integer do\n'
  '    Enum.fetch!(Stream.map(xs, fn x -> x end), 5)\n'
  '  end\n'
  '  def main() do\n'
  '    IO.inspect(pick([1]))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: out of bounds error\n  at Main.pick (<stdin>:3)\n  at Main.main (<stdin>:6)\n'),
 ('defmodule Main do\n  def main() do\n    s = Stream.map([1, 0], fn x -> div(10, x) end)\n    IO.inspect(Enum.to_list(s))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:36: division by zero\n  at Main.main <closure> (<stdin>:3)\n  at Main.main (<stdin>:4)\n'),
 ('defmodule Main do\n  def main() do\n    x = [1]\n      |> Enum.map(fn x -> x end)\n      |> Enum.fetch!(5)\n    IO.inspect(x)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:5:10: out of bounds error\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n'
  '  def bad(x: integer): integer do\n'
  '    div(x, 0)\n'
  '  end\n'
  '  def main() do\n'
  '    x = [1,\n'
  '      Enum.fetch!([1],\n'
  '         5)]\n'
  '    IO.inspect(x)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:7:7: out of bounds error\n  at Main.main (<stdin>:6)\n'),
 ('defmodule Main do\n'
  '  def bad(x: integer): integer do\n'
  '    div(x, 0)\n'
  '  end\n'
  '  def main() do\n'
  '    x = {Enum.at([1], 0, 0),\n'
  '      bad(2)}\n'
  '    IO.inspect(x)\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:3:5: division by zero\n  at Main.bad (<stdin>:3)\n  at Main.main (<stdin>:6)\n'),
 ('defmodule Main do\n  def main() do\n    x = Enum.map([1, 2], fn v ->\n      Enum.fetch!([v], v)\n    end)\n    IO.inspect(x)\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:7: out of bounds error\n  at Main.main <closure> (<stdin>:4)\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    s = Stream.map([1, 2], fn v ->\n'
  '      w = v + 1\n'
  '      Enum.fetch!([v], w)\n'
  '    end)\n'
  '    IO.inspect(Enum.take(Stream.filter(s, fn x -> x > 0 end), 2))\n'
  '  end\n'
  'end\n',
  2,
  b'',
  b'<stdin>:5:7: out of bounds error\n  at Main.main <closure> (<stdin>:5)\n  at Main.main (<stdin>:7)\n'),
 ('defmodule Main do\n'
  '  def main() do\n'
  'c = Stream.resource(fn -> 2 end, fn n -> if n == 0 do none else some({[n], n - 1}) end end, fn n -> n end)\n'
  'IO.inspect(Enum.take(Stream.cycle(c), 5))\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 1, 2, 1, 2]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.into(Stream.map(1..3, fn x -> x end), %{}, fn x -> {x, x} end))\n'
  'IO.inspect(Enum.into(1..3, "a", fn x -> "#{x}" end))\n'
  'IO.inspect(Enum.into(1..3, MapSet.new([9]), fn x -> x * 2 end))\n'
  'IO.inspect(Enum.into(1..3, [0], fn x -> x * 2 end))\n'
  '  end\n'
  'end\n',
  0,
  b'%{1 => 1, 2 => 2, 3 => 3}\n"a123"\nMapSet.new([2, 4, 6, 9])\n[0, 2, 4, 6]\n',
  b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  'IO.inspect(Enum.map_join(1..3, fn x -> x * 2 end))\n'
  'IO.inspect(Enum.map_join(1..3, ", ", fn x -> "<#{x}>" end))\n'
  'IO.inspect(Enum.map_join(1..3, ", ", fn x -> x > 1 end))\n'
  '  end\n'
  'end\n',
  0,
  b'"246"\n"<1>, <2>, <3>"\n"false, true, true"\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.map_join(1..3, fn x -> x * 2 end))\n  end\nend\n', 0, b'"246"\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.map_join(1..3, ", ", fn x -> "<#{x}>" end))\n  end\nend\n', 0, b'"<1>, <2>, <3>"\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.map_join(1..3, ", ", fn x -> x > 1 end))\n  end\nend\n', 0, b'"false, true, true"\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.map_join([1, 2, 3], ", ", fn x -> x > 1 end))\n  end\nend\n', 0, b'"false, true, true"\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.map_join(MapSet.new([1, 2, 3]), ", ", fn x -> x > 1 end))\n  end\nend\n',
  0,
  b'"false, true, true"\n',
  b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.map_join(1..3, ", ", fn x -> :a end))\n  end\nend\n', 0, b'"a, a, a"\n', b''),
 ('defmodule Main do\n'
  '  def main() do\n'
  '    IO.inspect(Enum.sum(1..10000000))\n'
  '    IO.inspect(Enum.count(Stream.filter(Stream.map(1..5000000, fn x -> x * 3 end), fn x -> rem(x, 2) == 0 end)))\n'
  '    IO.inspect(Enum.reduce(Stream.take(Stream.cycle([1, 2, 3]), 3000000), 0, fn x, acc -> x + acc end))\n'
  '    IO.inspect(Enum.find(Stream.from_index(), fn x -> x > 2000000 end))\n'
  '    IO.inspect(Enum.at(Stream.iterate(0, fn x -> x + 2 end), 1000000))\n'
  '    IO.inspect(Stream.from_index() |> Stream.map(&(&1 * 2)) |> Stream.drop(2000000) |> Stream.take_every(7) |> Enum.take(3))\n'
  '    IO.inspect(Enum.count(Stream.dedup(Stream.map(1..2000000, fn x -> div(x, 2) end))))\n'
  '    IO.inspect(Enum.sum(Stream.with_index(1..200000) |> Stream.map(fn {a, i} -> a * i end) |> Stream.take(1000)))\n'
  '    IO.inspect(Enum.count(Stream.zip(1..20000, Stream.cycle([0]))))\n'
  '    IO.inspect(Enum.sum(Stream.scan(1..1000000, &(&1 + &2)) |> Stream.take(10)))\n'
  '    IO.inspect(Enum.sum(Stream.flat_map(1..10000, fn x -> [x, x] end)))\n'
  '    IO.inspect(Enum.count(Stream.unfold(0, fn n -> if n > 10000 do none else some({n, n + 1}) end end)))\n'
  '    IO.inspect(Enum.count(Stream.repeatedly(fn -> 1 end) |> Stream.take(2000000)))\n'
  '    IO.inspect(Enum.count(Stream.concat(1..1000000, 1..1000000)))\n'
  '    IO.inspect(Enum.sum(for x <- 1..300000, rem(x, 1000) == 0 do x end))\n'
  '    IO.inspect(7 in Stream.map(Stream.from_index(), fn x -> x - 3000000 end))\n'
  '    IO.inspect(Enum.count_until(1..1000000, 5))\n'
  '    IO.inspect(Enum.member?(1..10000000, -1))\n'
  '    IO.inspect(Enum.reduce(1..3000000, 0, fn x, acc -> rem(x + acc, 1000) end))\n'
  '    Enum.each(Stream.take(Stream.from_index(), 3), fn x -> IO.puts("#{x}") end)\n'
  '  end\n'
  'end\n',
  0,
  b'50000005000000\n2500000\n6000000\nsome(2000001)\nsome(2000000)\n[4000000, 4000014, 4000028]\n1000001\n333333000\n20000\n220\n100010000\n10001\n2000000\n2'
  b'000000\n45150000\ntrue\n5\nfalse\n0\n0\n1\n2\n',
  b''),
 ('defmodule Main do\n  def main() do\n    m = File.stream!("/nonexistent/zz")\n    IO.puts("made")\n    IO.inspect(Enum.take(m, 1))\n  end\nend\n',
  2,
  b'made\n',
  b'<stdin>:3:9: could not stream /nonexistent/zz: no such file or directory\n  at Main.main (<stdin>:5)\n'),
 ('defmodule Main do\n  def main() do\nm = File.stream!("/nonexistent/zz")\nIO.inspect(Enum.to_list(m))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:5: could not stream /nonexistent/zz: no such file or directory\n  at Main.main (<stdin>:4)\n'),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.to_list(File.stream!("/nonexistent/zz")))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:25: could not stream /nonexistent/zz: no such file or directory\n  at Main.main (<stdin>:3)\n'),
 ('defmodule Main do\n  def main() do\nm = File.stream!("/nonexistent/zz")\nIO.puts("made")\n  end\nend\n', 0, b'made\n', b''),
 ('defmodule Main do\n  def main() do\nIO.inspect(Enum.take(File.stream!("/nonexistent/zz"), 1))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:3:22: could not stream /nonexistent/zz: no such file or directory\n  at Main.main (<stdin>:3)\n')]

# programs the pinned compiler rejects
REJECTS=['defmodule Main do\n  def total(xs: list[integer]): integer do Enum.sum(xs) end\n  def main() do\nIO.inspect(total(1..3))\n  end\nend\n',
 'defmodule Main do\n'
 '  def total(xs: list[integer]): integer do Enum.sum(xs) end\n'
 '  def main() do\n'
 'r = 1..3\n'
 's: stream[integer] = r\n'
 'IO.inspect(Enum.to_list(s))\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n  def total(xs: stream[integer]): integer do Enum.sum(xs) end\n  def main() do\nr = 1..3\nIO.inspect(total(r))\n  end\nend\n',
 'defmodule Main do\n'
 '  def total(xs: stream[integer]): integer do Enum.sum(xs) end\n'
 '  def main() do\n'
 'x = if true do 1..3 else [1, 2] end\n'
 'IO.inspect(x)\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n  def total(xs: stream[integer]): integer do Enum.sum(xs) end\n  def main() do\nIO.inspect([1] ++ 2..3)\n  end\nend\n',
 'defmodule Main do\n  def total(xs: stream[integer]): integer do Enum.sum(xs) end\n  def main() do\nr = 1..3\nIO.inspect(r |> total())\n  end\nend\n',
 'defmodule Main do\n'
 '  def main() do\n'
 'IO.inspect(Enum.to_list(Stream.transform(1..10, 0, fn n, total -> if total + n > 6 do none else some({[total + n], total + n}) end end)))\n'
 'IO.inspect(Enum.to_list(Stream.transform(1..5, 0, fn n, acc -> some({[], acc + n}) end)))\n'
 'IO.inspect(Enum.take(Stream.transform(Stream.from_index(), 0, fn n, acc -> some({[n, acc], acc + 1}) end), 5))\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n'
 '  def main() do\n'
 'Stream.run(Stream.each(1..2, fn n -> IO.write(Integer.to_string(n)) end))\n'
 'IO.puts("")\n'
 'IO.inspect(Stream.run([1]))\n'
 '  end\n'
 'end\n',
 'defmodule Main do\n  def main() do\nc = Stream.unfold(1, fn n -> none end)\nx: stream[integer] = c\nIO.inspect(Enum.take(Stream.cycle(x), 5))\n  end\nend\n']


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-streams-') as d:
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
    print(f'PASS streams: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; the stream type, Stream, Enum reading streams and ranges as they give, the order of effects, resources, failures and their traces, for and in, File.stream!, long streams in constant memory')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
