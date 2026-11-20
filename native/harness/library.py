#!/usr/bin/env python3
"""Library functions written in Alchem (library/*.alc), which the compiler appends to the programs that mention them: every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.all?([true, false])))\n  end\nend\n', 0, b'false\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.all?([2, 4, 6], fn n -> rem(n, 2) == 0 end)))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.any?([1, 2, 3], &(&1 > 2))))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.count([1, 2, 3], &(&1 > 1))))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.reject([1, 2, 3, 4], &(rem(&1, 2) == 0))))\n  end\nend\n', 0, b'[1, 3]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.find([1, 2, 3], &(&1 > 1))))\n  end\nend\n', 0, b'some(2)\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.find([1, 2, 3], 0, &(&1 > 5))))\n  end\nend\n', 0, b'0\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.find_index(["a", "b"], &(&1 == "b"))))\n  end\nend\n', 0, b'some(1)\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.flat_map([1, 2], fn n -> [n, n * 10] end)))\n  end\nend\n', 0, b'[1, 10, 2, 20]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.concat([[1], [2, 3]])))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.intersperse(["a", "b", "c"], "/")))\n  end\nend\n', 0, b'["a", "/", "b", "/", "c"]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.dedup([1, 1, 2, 2, 1])))\n  end\nend\n', 0, b'[1, 2, 1]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.dedup_by([1, 3, 2, 4, 5], &rem(&1, 2))))\n  end\nend\n', 0, b'[1, 2, 5]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.uniq([1, 2, 1, 3])))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.with_index(["a", "b"])))\n  end\nend\n', 0, b'[{"a", 0}, {"b", 1}]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.zip([1, 2, 3], ["a", "b"])))\n  end\nend\n', 0, b'[{1, "a"}, {2, "b"}]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.unzip([{1, "a"}, {2, "b"}])))\n  end\nend\n', 0, b'{[1, 2], ["a", "b"]}\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.take_while([1, 2, 3, 1], &(&1 < 3))))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.drop_while([1, 2, 3, 1], &(&1 < 3))))\n  end\nend\n', 0, b'[3, 1]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.split([1, 2, 3], 2)))\n  end\nend\n', 0, b'{[1, 2], [3]}\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.split([1, 2, 3], -1)))\n  end\nend\n', 0, b'{[1, 2], [3]}\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.split_while([1, 2, 3, 1], &(&1 < 3))))\n  end\nend\n', 0, b'{[1, 2], [3, 1]}\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.split_with([1, 2, 3, 4], &(rem(&1, 2) == 0))))\n  end\nend\n', 0, b'{[2, 4], [1, 3]}\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.chunk_every([10, 20, 30, 40, 50], 2)))\n  end\nend\n', 0, b'[[10, 20], [30, 40], [50]]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.chunk_every([5, 6, 7, 8], 3, 1)))\n  end\nend\n', 0, b'[[5, 6, 7], [6, 7, 8]]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.chunk_every([1, 2, 3, 4, 5, 6, 7], 2, 3)))\n  end\nend\n', 0, b'[[1, 2], [4, 5], [7]]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.chunk_by([1, 3, 2, 4, 5], &(rem(&1, 2) == 1))))\n  end\nend\n', 0, b'[[1, 3], [2, 4], [5]]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.scan([1, 2, 3, 4], &(&1 + &2))))\n  end\nend\n', 0, b'[1, 3, 6, 10]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.scan([1, 2], 10, &(&1 + &2))))\n  end\nend\n', 0, b'[11, 13]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.map_reduce([5, 6, 7], 0, fn n, acc -> {n * 2, acc + n} end)))\n  end\nend\n',
  0,
  b'{[10, 12, 14], 18}\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.flat_map_reduce([1, 2], 0, fn n, acc -> {[n, n], acc + n} end)))\n  end\nend\n',
  0,
  b'{[1, 1, 2, 2], 3}\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.map_every([1, 2, 3, 4, 5], 2, &(&1 * 10))))\n  end\nend\n', 0, b'[10, 2, 30, 4, 50]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.take_every([1, 2, 3, 4, 5], 2)))\n  end\nend\n', 0, b'[1, 3, 5]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.take_every([1, 2, 3], 0)))\n  end\nend\n', 0, b'[]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.drop_every([1, 2, 3, 4, 5], 2)))\n  end\nend\n', 0, b'[2, 4]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.drop_every([1, 2, 3], 0)))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.reverse([1, 2], [9])))\n  end\nend\n', 0, b'[2, 1, 9]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.reverse_slice([10, 20, 30, 40, 50], 1, 3)))\n  end\nend\n', 0, b'[10, 40, 30, 20, 50]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.slide([1, 2, 3, 4], 0, 2)))\n  end\nend\n', 0, b'[2, 3, 1, 4]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.slide([1, 2, 3, 4], 3, 1)))\n  end\nend\n', 0, b'[1, 4, 2, 3]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.into([1, 2], [0])))\n  end\nend\n', 0, b'[0, 1, 2]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.count_until([1, 2, 3], &(&1 > 1), 10)))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.count_until([1, 2, 3], 2)))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.sum_by(["a", "bb"], &String.length(&1))))\n  end\nend\n', 0, b'3\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.product([2, 3, 4])))\n  end\nend\n', 0, b'24\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.product_by([1, 2, 3], &(&1 + 1))))\n  end\nend\n', 0, b'24\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.reduce([1, 2, 3], &(&1 * &2))))\n  end\nend\n', 0, b'6\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.member?([1, 2, 3], 2)))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.find_value([1, 2, 3], fn n -> if n > 1 do some(n * 10) else none end end)))\n  end\nend\n',
  0,
  b'some(20)\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.zip_with([1, 2], [3, 4], fn a, b -> a + b end)))\n  end\nend\n', 0, b'[4, 6]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.map_intersperse([1, 2], "-", &Integer.to_string(&1))))\n  end\nend\n', 0, b'["1", "-", "2"]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.uniq_by(["a", "bb", "c"], &String.length(&1))))\n  end\nend\n', 0, b'["a", "bb"]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect([1, 2, 3] |> Enum.reject(&(&1 == 2)) |> Enum.any?(&(&1 == 3))))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.map_join([1, 2], "+", &Integer.to_string(&1))))\n  end\nend\n', 0, b'"1+2"\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.map_every([1, 2, 3], 0, &(&1 * 10))))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.with_index(["a", "b"], 5)))\n  end\nend\n', 0, b'[{"a", 5}, {"b", 6}]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.all?(Enum.take([true], 0))))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.dedup(Enum.take([1], 0))))\n  end\nend\n', 0, b'[]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.count([1, 2]) + Enum.sum(Enum.reverse([1, 2]))))\n  end\nend\n', 0, b'5\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.sort([5, 3, 9, 1, 3, 8, 2, 7, 7, 0, -4])))\n  end\nend\n',
  0,
  b'[-4, 0, 1, 2, 3, 3, 5, 7, 7, 8, 9]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.sort(["b", "a", "ab", ""])))\n  end\nend\n', 0, b'["", "a", "ab", "b"]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.sort([{1, "b"}, {0, "z"}, {1, "a"}], fn x, y -> elem(x, 0) <= elem(y, 0) end)))\n  end\nend\n',
  0,
  b'[{0, "z"}, {1, "b"}, {1, "a"}]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.sort_by(["ccc", "a", "bb", "dd"], &String.length(&1))))\n  end\nend\n',
  0,
  b'["a", "bb", "dd", "ccc"]\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect({Enum.min([3, 1, 2]), Enum.max(["a", "c", "b"]), Enum.min_max([3, 9, 2])}))\n  end\nend\n',
  0,
  b'{1, "c", {2, 9}}\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect({Enum.min_by(["ccc", "a"], &String.length(&1)), Enum.max_by([1, 2, 3], fn x -> 0 - x end)}))\n  end\nend\n',
  0,
  b'{"a", 1}\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.join([1, 2, 3], ", ") <> Enum.join([4, 5]) <> Enum.join(["a", "b"], "-")))\n  end\nend\n',
  0,
  b'"1, 2, 345a-b"\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(List.sort([3, 1, 2])))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.frequencies(["a", "b", "a"])))\n  end\nend\n', 0, b'%{"a" => 2, "b" => 1}\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.group_by([1, 2, 3, 4], &rem(&1, 2))))\n  end\nend\n', 0, b'%{0 => [2, 4], 1 => [1, 3]}\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(Enum.fetch!([10, 20], 1) + Map.fetch!(%{"a" => 1}, "a")))\n  end\nend\n', 0, b'21\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(1!=2))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect({String.at("héllo", 1), String.at("abc", 9), String.at("abc", -1), String.at("abc", -4)}))\n  end\nend\n',
  0,
  b'{some("\xc3\xa9"), none, some("c"), none}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect({String.contains?("alchemy", ["gold", "my"]), String.contains?("alchemy", "chem"), String.starts_with?("alchemy", ["gold", "alc"]), '
  'String.ends_with?("main.alc", [".ex", ".exs"])}))\n'
  '  end\n'
  'end\n',
  0,
  b'{true, true, true, false}\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(String.join(["a", "b"], "-")))\n  end\nend\n', 0, b'"a-b"\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect({String.split_at("alchemy", 2), String.split_at("abc", -1), String.split_at("abc", 9), String.split_at("héllo", -9)}))\n'
  '  end\n'
  'end\n',
  0,
  b'{{"al", "chemy"}, {"ab", "c"}, {"abc", ""}, {"", "h\xc3\xa9llo"}}\n',
  b''),
 ('defmodule M do\n  def main() do\nIO.puts(inspect(String.graphemes("héy")))\n  end\nend\n', 0, b'["h", "\xc3\xa9", "y"]\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect({String.replace_prefix("unhappy", "un", ""), String.replace_prefix("happy", "un", "x"), String.replace_suffix("main.alc", ".alc", ".go"), '
  'String.replace_suffix("main", ".alc", ".go")}))\n'
  '  end\n'
  'end\n',
  0,
  b'{"happy", "happy", "main.go", "main"}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  'IO.puts(inspect({String.replace_leading("aaab", "a", "x"), String.replace_trailing("abbb", "b", "x"), String.replace_leading("abab!", "ab", "c"), '
  'String.replace_trailing("xyz", "q", "-")}))\n'
  '  end\n'
  'end\n',
  0,
  b'{"xxxb", "axxx", "cc!", "xyz"}\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(binary_part("hello", 1, 3)))\n    IO.puts(inspect(binary_part("hello", 5, -2)))\n  end\nend\n',
  0,
  b'"ell"\n"lo"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(byte_size("héllo")))\n  end\nend\n', 0, b'6\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(concat([1], [2, 3])))\n    IO.puts(inspect([1] ++ [2, 3]))\n  end\nend\n',
  0,
  b'[1, 2, 3]\n[1, 2, 3]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(div(7, 2)))\n    IO.puts(inspect(div(-7, 2)))\n  end\nend\n', 0, b'3\n-3\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(filter([1, 2, 3], fn(n: integer): boolean do n > 1 end)))\n  end\nend\n', 0, b'[2, 3]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(get(%{"a" => 1}, "z", 0)))\n  end\nend\n', 0, b'0\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(has_key(%{"a" => 1}, "a")))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(hd([1, 2, 3])))\n  end\nend\n', 0, b'1\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(length([1, 2, 3])))\n    IO.puts(inspect(length(%{"a" => 1})))\n  end\nend\n', 0, b'3\n1\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(map([1, 2, 3], fn(n: integer): integer do n * 2 end)))\n  end\nend\n', 0, b'[2, 4, 6]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(map_size(%{"a" => 1, "b" => 2})))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(max(3, 9)))\n  end\nend\n', 0, b'9\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(min(3, 9)))\n  end\nend\n', 0, b'3\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(prepend([2, 3], 1)))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(put(%{"x" => 1}, "y", 2)))\n  end\nend\n', 0, b'%{"x" => 1, "y" => 2}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(reduce([1, 2, 3], 0, fn(acc: integer, n: integer): integer do acc + n end)))\n  end\nend\n',
  0,
  b'6\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(rem(7, 2)))\n    IO.puts(inspect(rem(-7, 2)))\n  end\nend\n', 0, b'1\n-1\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(tap(5, fn n -> IO.write(Integer.to_string(n)) end)))\n  end\nend\n', 0, b'55\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(5 |> then(fn n -> n * 2 end)))\n  end\nend\n', 0, b'10\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(tl([1, 2, 3])))\n  end\nend\n', 0, b'[2, 3]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(to_string(42)))\n    IO.puts(inspect(to_string(true)))\n  end\nend\n', 0, b'"42"\n"true"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Bitwise.band(12, 10)))\n  end\nend\n', 0, b'8\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Bitwise.bnot(0)))\n  end\nend\n', 0, b'-1\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Bitwise.bor(12, 10)))\n  end\nend\n', 0, b'14\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Bitwise.bsl(1, 4)))\n  end\nend\n', 0, b'16\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Bitwise.bsr(16, 2)))\n  end\nend\n', 0, b'4\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Bitwise.bxor(12, 10)))\n  end\nend\n', 0, b'6\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.all?([2, 4, 6], fn n -> rem(n, 2) == 0 end)))\n'
  '    IO.puts(inspect(Enum.all?([true, false])))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.any?([1, 2, 3], &(&1 > 2))))\n    IO.puts(inspect(Enum.any?([false, false])))\n  end\nend\n',
  0,
  b'true\nfalse\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.at([10, 20, 30], 1)))\n'
  '    IO.puts(inspect(Enum.at([10, 20, 30], -1)))\n'
  '    IO.puts(inspect(Enum.at([10, 20, 30], 9, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'some(20)\nsome(30)\n0\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.chunk_by([1, 3, 2, 4, 5], &(rem(&1, 2) == 1))))\n  end\nend\n',
  0,
  b'[[1, 3], [2, 4], [5]]\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.chunk_every([10, 20, 30, 40, 50], 2)))\n'
  '    IO.puts(inspect(Enum.chunk_every([5, 6, 7, 8], 3, 1)))\n'
  '  end\n'
  'end\n',
  0,
  b'[[10, 20], [30, 40], [50]]\n[[5, 6, 7], [6, 7, 8]]\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.chunk_while([1, 2, 6, 7, 20], Enum.take([0], 0), fn n, run ->\n'
  '      case run do\n'
  '        [last | _] when n - last > 1 -> {some(Enum.reverse(run)), [n]}\n'
  '        _ -> {none, prepend(run, n)}\n'
  '      end\n'
  '    end, fn run -> if run == [] do none else some(Enum.reverse(run)) end end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[[1, 2], [6, 7], [20]]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.concat([1, 2], 3..4)))\n    IO.puts(inspect(Enum.concat([[1], [2, 3]])))\n  end\nend\n',
  0,
  b'[1, 2, 3, 4]\n[1, 2, 3]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.count([1, 2, 3])))\n    IO.puts(inspect(Enum.count([1, 2, 3], &(&1 > 1))))\n  end\nend\n',
  0,
  b'3\n2\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.dedup([1, 1, 2, 2, 1])))\n  end\nend\n', 0, b'[1, 2, 1]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.dedup_by([1, 3, 2, 4, 5], &rem(&1, 2))))\n  end\nend\n', 0, b'[1, 2, 5]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.drop([1, 2, 3, 4], 1)))\n    IO.puts(inspect(Enum.drop([1, 2, 3, 4], -1)))\n  end\nend\n',
  0,
  b'[2, 3, 4]\n[1, 2, 3]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.drop_every([1, 2, 3, 4, 5], 2)))\n  end\nend\n', 0, b'[2, 4]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.drop_while([1, 2, 3, 1], &(&1 < 3))))\n  end\nend\n', 0, b'[3, 1]\n', b''),
 ('defmodule T do\n  def main() do\n    Enum.each(["a", "b"], fn text -> IO.write(text) end)\n  end\nend\n', 0, b'ab', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.empty?([1])))\n    IO.puts(inspect(Enum.empty?(Enum.filter([1], &(&1 > 5)))))\n  end\nend\n',
  0,
  b'false\ntrue\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.fetch([10, 20], 1)))\n    IO.puts(inspect(Enum.fetch([10, 20], 5)))\n  end\nend\n',
  0,
  b'some(20)\nnone\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.fetch!([10, 20], 0)))\n  end\nend\n', 0, b'10\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.filter([1, 2, 3, 4], fn n -> rem(n, 2) == 0 end)))\n  end\nend\n', 0, b'[2, 4]\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.find([1, 2, 3], &(&1 > 1))))\n'
  '    IO.puts(inspect(Enum.find([1, 2, 3], 0, &(&1 > 5))))\n'
  '  end\n'
  'end\n',
  0,
  b'some(2)\n0\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.find_index(["a", "b"], &(&1 == "b"))))\n  end\nend\n', 0, b'some(1)\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.find_value([1, 2, 3], fn n -> if n > 1, do: some(n * 10), else: none end)))\n'
  '    IO.puts(inspect(Enum.find_value([1, 3], 0, fn n -> if rem(n, 2) == 0, do: some(n), else: none end)))\n'
  '  end\n'
  'end\n',
  0,
  b'some(20)\n0\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.flat_map([1, 2], fn n -> [n, n * 10] end)))\n  end\nend\n', 0, b'[1, 10, 2, 20]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.flat_map_reduce([1, 2], 0, fn n, acc -> {[n, n], acc + n} end)))\n  end\nend\n',
  0,
  b'{[1, 1, 2, 2], 3}\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.frequencies(["a", "b", "a"])))\n  end\nend\n', 0, b'%{"a" => 2, "b" => 1}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.frequencies_by(["aa", "b", "cc"], &String.length(&1))))\n  end\nend\n',
  0,
  b'%{1 => 1, 2 => 2}\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.group_by([1, 2, 3, 4], &rem(&1, 2))))\n'
  '    IO.puts(inspect(Enum.group_by(["ant", "bee", "asp"], &String.slice(&1, 0, 1), &String.length(&1))))\n'
  '  end\n'
  'end\n',
  0,
  b'%{0 => [2, 4], 1 => [1, 3]}\n%{"a" => [3, 3], "b" => [3]}\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.intersperse(["a", "b", "c"], "/")))\n  end\nend\n', 0, b'["a", "/", "b", "/", "c"]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.join([1, 2, 3], ", ")))\n    IO.puts(inspect(Enum.join(["a", "b"])))\n  end\nend\n',
  0,
  b'"1, 2, 3"\n"ab"\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.map([1, 2, 3], fn n -> n * 2 end)))\n'
  '    IO.puts(inspect(Enum.map(%{"a" => 1}, fn {key, value} -> "#{key}=#{value}" end)))\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 4, 6]\n["a=1"]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.map_every([1, 2, 3, 4, 5], 2, &(&1 * 10))))\n  end\nend\n', 0, b'[10, 2, 30, 4, 50]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.map_intersperse([1, 2], "-", &Integer.to_string(&1))))\n  end\nend\n',
  0,
  b'["1", "-", "2"]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.map_join([4, 5, 6], "+", &(&1 * 10))))\n  end\nend\n', 0, b'"40+50+60"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.map_reduce([5, 6, 7], 0, fn n, acc -> {n * 2, acc + n} end)))\n  end\nend\n',
  0,
  b'{[10, 12, 14], 18}\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.max([3, 9, 2])))\n    IO.puts(inspect(Enum.max(Enum.take([1], 0), fn -> 0 end)))\n  end\nend\n',
  0,
  b'9\n0\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.max_by(["a", "ccc", "bb"], &String.length(&1))))\n  end\nend\n', 0, b'"ccc"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.member?([1, 2, 3], 2)))\n    IO.puts(inspect(5 in 1..3))\n  end\nend\n', 0, b'true\nfalse\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.min([3, 9, 2])))\n    IO.puts(inspect(Enum.min(Enum.take([1], 0), fn -> 0 end)))\n  end\nend\n',
  0,
  b'2\n0\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.min_by(["ccc", "a", "bb"], &String.length(&1))))\n  end\nend\n', 0, b'"a"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.min_max([3, 9, 2])))\n  end\nend\n', 0, b'{2, 9}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.min_max_by(["ccc", "a", "bb"], &String.length(&1))))\n  end\nend\n', 0, b'{"a", "ccc"}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.product([2, 3, 4])))\n  end\nend\n', 0, b'24\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.product_by([1, 2, 3], &(&1 + 1))))\n  end\nend\n', 0, b'24\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.reduce([1, 2, 3], 0, fn n, acc -> acc + n end)))\n'
  '    IO.puts(inspect(Enum.reduce([1, 2, 3], &(&1 * &2))))\n'
  '  end\n'
  'end\n',
  0,
  b'6\n6\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.reduce_while(1..100, 0, fn n, acc -> if acc > 5 do halt(acc) else cont(acc + n) end end)))\n'
  '  end\n'
  'end\n',
  0,
  b'6\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.reject([1, 2, 3, 4], &(rem(&1, 2) == 0))))\n  end\nend\n', 0, b'[1, 3]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.reverse([1, 2, 3])))\n    IO.puts(inspect(Enum.reverse([1, 2], [9])))\n  end\nend\n',
  0,
  b'[3, 2, 1]\n[2, 1, 9]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.reverse_slice([10, 20, 30, 40, 50], 1, 3)))\n  end\nend\n', 0, b'[10, 40, 30, 20, 50]\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.scan([1, 2, 3, 4], &(&1 + &2))))\n'
  '    IO.puts(inspect(Enum.scan([1, 2], 10, &(&1 + &2))))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 3, 6, 10]\n[11, 13]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.slide([:a, :b, :c, :d], 0, 2)))\n  end\nend\n', 0, b'[:b, :c, :a, :d]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.sort([3, 1, 2])))\n    IO.puts(inspect(Enum.sort([3, 1, 2], &(&1 >= &2))))\n  end\nend\n',
  0,
  b'[1, 2, 3]\n[3, 2, 1]\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.sort_by(["ccc", "a", "bb"], &String.length(&1))))\n'
  '    IO.puts(inspect(Enum.sort_by(["ccc", "a", "bb"], &String.length(&1), &(&1 >= &2))))\n'
  '  end\n'
  'end\n',
  0,
  b'["a", "bb", "ccc"]\n["ccc", "bb", "a"]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.split([1, 2, 3], 2)))\n  end\nend\n', 0, b'{[1, 2], [3]}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.split_while([1, 2, 3, 1], &(&1 < 3))))\n  end\nend\n', 0, b'{[1, 2], [3, 1]}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.split_with([1, 2, 3, 4], &(rem(&1, 2) == 0))))\n  end\nend\n', 0, b'{[2, 4], [1, 3]}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.sum_by(["a", "bb"], &String.length(&1))))\n  end\nend\n', 0, b'3\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.take([1, 2, 3], 2)))\n    IO.puts(inspect(Enum.take([1, 2, 3], -1)))\n  end\nend\n',
  0,
  b'[1, 2]\n[3]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.take_every([1, 2, 3, 4, 5], 2)))\n  end\nend\n', 0, b'[1, 3, 5]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.take_while([1, 2, 3, 1], &(&1 < 3))))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.to_list(1..3)))\n    IO.puts(inspect(Enum.to_list(%{"a" => 1})))\n  end\nend\n',
  0,
  b'[1, 2, 3]\n[{"a", 1}]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.uniq([1, 2, 1, 3, 2])))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.uniq_by(["a", "bb", "c"], &String.length(&1))))\n  end\nend\n', 0, b'["a", "bb"]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.unzip([{1, "a"}, {2, "b"}])))\n  end\nend\n', 0, b'{[1, 2], ["a", "b"]}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.with_index(["a", "b"])))\n    IO.puts(inspect(Enum.with_index(["a"], 5)))\n  end\nend\n',
  0,
  b'[{"a", 0}, {"b", 1}]\n[{"a", 5}]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.zip([1, 2, 3], ["a", "b"])))\n  end\nend\n', 0, b'[{1, "a"}, {2, "b"}]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.zip_reduce([2, 3], [4, 5], 0, fn a, b, acc -> acc + a * b end)))\n  end\nend\n', 0, b'23\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Enum.zip_with([1, 2], [10, 20], &(&1 + &2))))\n  end\nend\n', 0, b'[11, 22]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.contains([1, 2, 3], 2)))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.delete([1, 2, 1], 1)))\n  end\nend\n', 0, b'[2, 1]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.delete_at([1, 2, 3], -1)))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.drop([1, 2, 3], 2)))\n  end\nend\n', 0, b'[3]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.duplicate("a", 3)))\n  end\nend\n', 0, b'["a", "a", "a"]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.ends_with?([1, 2, 3], [2, 3])))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.first([1, 2])))\n    IO.puts(inspect(List.first(Enum.take([1], 0), 0)))\n  end\nend\n',
  0,
  b'some(1)\n0\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.first!([1, 2])))\n  end\nend\n', 0, b'1\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.flatten([[1], [2, 3]])))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.foldl([1, 2, 3], "", fn n, acc -> acc <> Integer.to_string(n) end)))\n  end\nend\n',
  0,
  b'"123"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.foldr([1, 2, 3], "", fn n, acc -> acc <> Integer.to_string(n) end)))\n  end\nend\n',
  0,
  b'"321"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.insert_at([1, 3], 1, 2)))\n    IO.puts(inspect(List.insert_at([1, 2], -1, 3)))\n  end\nend\n',
  0,
  b'[1, 2, 3]\n[1, 2, 3]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.keydelete([{"red", 4}, {"blue", 5}, {"red", 6}], "red")))\n  end\nend\n',
  0,
  b'[{"blue", 5}, {"red", 6}]\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(List.keyfind([{"a", 1}, {"b", 2}], "b")))\n'
  '    IO.puts(inspect(List.keyfind([{"a", 1}], "z")))\n'
  '  end\n'
  'end\n',
  0,
  b'some({"b", 2})\nnone\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.keymember?([{:x, 1}], :x)))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.keyreplace([{"a", 1}, {"b", 2}], "b", {"b", 20})))\n  end\nend\n',
  0,
  b'[{"a", 1}, {"b", 20}]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.keysort([{3, "c"}, {1, "a"}, {3, "b"}])))\n  end\nend\n',
  0,
  b'[{1, "a"}, {3, "c"}, {3, "b"}]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.keystore([{"a", 1}], "c", {"c", 3})))\n  end\nend\n', 0, b'[{"a", 1}, {"c", 3}]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.keytake([{"a", 1}, {"b", 2}], "a")))\n  end\nend\n', 0, b'some({{"a", 1}, [{"b", 2}]})\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.last([1, 2])))\n  end\nend\n', 0, b'some(2)\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.last!([1, 2])))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.pop_at([1, 2, 3], 1)))\n  end\nend\n', 0, b'{some(2), [1, 3]}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.range(1, 4)))\n  end\nend\n', 0, b'[1, 2, 3, 4]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.replace_at([4, 5, 6], 1, 0)))\n  end\nend\n', 0, b'[4, 0, 6]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.reverse([1, 2, 3])))\n  end\nend\n', 0, b'[3, 2, 1]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.sort([3, 1, 2])))\n  end\nend\n', 0, b'[1, 2, 3]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.starts_with?([1, 2, 3], [1, 2])))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.take([1, 2, 3], 2)))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.update_at([4, 5, 6], 0, &(&1 * 10))))\n  end\nend\n', 0, b'[40, 5, 6]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(List.zip([1, 2], ["a", "b"])))\n  end\nend\n', 0, b'[{1, "a"}, {2, "b"}]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.delete(%{"x" => 1, "y" => 2}, "x")))\n  end\nend\n', 0, b'%{"y" => 2}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.drop(%{"x" => 1, "y" => 2}, ["x"])))\n  end\nend\n', 0, b'%{"y" => 2}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.entries(%{"a" => 1})))\n  end\nend\n', 0, b'[{"a", 1}]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.equal?(%{"a" => 1}, %{"a" => 1})))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.fetch(%{"a" => 1}, "a")))\n  end\nend\n', 0, b'some(1)\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.fetch!(%{"a" => 1}, "a")))\n  end\nend\n', 0, b'1\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.filter(%{"a" => 1, "b" => 9}, fn {_, value} -> value > 5 end)))\n  end\nend\n',
  0,
  b'%{"b" => 9}\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.from_keys(["a", "b"], 0)))\n  end\nend\n', 0, b'%{"a" => 0, "b" => 0}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.get(%{"a" => 1}, "a")))\n    IO.puts(inspect(Map.get(%{"a" => 1}, "z", 0)))\n  end\nend\n',
  0,
  b'some(1)\n0\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.get_and_update(%{"a" => 1}, "a", fn current -> {current, some(5)} end)))\n  end\nend\n',
  0,
  b'{some(1), %{"a" => 5}}\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.get_lazy(%{"a" => 1}, "z", fn -> 99 end)))\n  end\nend\n', 0, b'99\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.has_key?(%{"a" => 1}, "a")))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.intersect(%{"a" => 1, "b" => 2}, %{"b" => 0})))\n  end\nend\n', 0, b'%{"b" => 0}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.keys(%{"b" => 2, "a" => 1})))\n  end\nend\n', 0, b'["a", "b"]\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Map.merge(%{"a" => 1}, %{"a" => 5, "b" => 2})))\n'
  '    IO.puts(inspect(Map.merge(%{"a" => 1}, %{"a" => 5}, fn _, left, right -> left + right end)))\n'
  '  end\n'
  'end\n',
  0,
  b'%{"a" => 5, "b" => 2}\n%{"a" => 6}\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Map.new([{"x", 7}, {"y", 8}])))\n'
  '    IO.puts(inspect(Map.new([1, 2], fn n -> {n, n * n} end)))\n'
  '  end\n'
  'end\n',
  0,
  b'%{"x" => 7, "y" => 8}\n%{1 => 1, 2 => 4}\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.pop(%{"a" => 1}, "a")))\n  end\nend\n', 0, b'{some(1), %{}}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.pop_lazy(%{"a" => 1}, "a", fn -> 0 end)))\n  end\nend\n', 0, b'{1, %{}}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.put(%{"x" => 1}, "y", 2)))\n  end\nend\n', 0, b'%{"x" => 1, "y" => 2}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.put_new(%{"a" => 1}, "a", 9)))\n  end\nend\n', 0, b'%{"a" => 1}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.put_new_lazy(%{"a" => 1}, "b", fn -> 2 end)))\n  end\nend\n', 0, b'%{"a" => 1, "b" => 2}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.reject(%{"a" => 1, "b" => 9}, fn {_, value} -> value > 5 end)))\n  end\nend\n',
  0,
  b'%{"a" => 1}\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.replace(%{"a" => 1}, "z", 9)))\n  end\nend\n', 0, b'%{"a" => 1}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.replace!(%{"a" => 1}, "a", 9)))\n  end\nend\n', 0, b'%{"a" => 9}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.replace_lazy(%{"a" => 1}, "a", fn v -> v + 1 end)))\n  end\nend\n', 0, b'%{"a" => 2}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.split(%{"a" => 1, "b" => 2}, ["a"])))\n  end\nend\n', 0, b'{%{"a" => 1}, %{"b" => 2}}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.split_with(%{"a" => 1, "b" => 9}, fn {_, value} -> value > 5 end)))\n  end\nend\n',
  0,
  b'{%{"b" => 9}, %{"a" => 1}}\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.take(%{"a" => 1, "b" => 2}, ["a", "z"])))\n  end\nend\n', 0, b'%{"a" => 1}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.to_list(%{"a" => 1})))\n  end\nend\n', 0, b'[{"a", 1}]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.update(%{"a" => 1}, "a", 0, &(&1 + 1))))\n  end\nend\n', 0, b'%{"a" => 2}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.update!(%{"a" => 1}, "a", &(&1 * 5))))\n  end\nend\n', 0, b'%{"a" => 5}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Map.values(%{"b" => 2, "a" => 1})))\n  end\nend\n', 0, b'[1, 2]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.at("héllo", 1)))\n    IO.puts(inspect(String.at("abc", 9)))\n  end\nend\n',
  0,
  b'some("\xc3\xa9")\nnone\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.capitalize("hELLO")))\n  end\nend\n', 0, b'"Hello"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.codepoints("héy")))\n  end\nend\n', 0, b'["h", "\xc3\xa9", "y"]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.contains("alchemy", "chem")))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(String.contains?("alchemy", "chem")))\n'
  '    IO.puts(inspect(String.contains?("alchemy", ["gold", "lead", "my"])))\n'
  '    IO.puts(inspect(String.contains?("alchemy", [])))\n'
  '  end\n'
  'end\n',
  0,
  b'true\ntrue\nfalse\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.count("banana", "an")))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.downcase("HeLLo")))\n  end\nend\n', 0, b'"hello"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.duplicate("ab", 3)))\n  end\nend\n', 0, b'"ababab"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.ends_with("main.alc", ".alc")))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(String.ends_with?("main.alc", ".alc")))\n'
  '    IO.puts(inspect(String.ends_with?("main.alc", [".ex", ".exs"])))\n'
  '  end\n'
  'end\n',
  0,
  b'true\nfalse\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.first("abc")))\n    IO.puts(inspect(String.first("")))\n  end\nend\n',
  0,
  b'some("a")\nnone\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.graphemes("abc")))\n  end\nend\n', 0, b'["a", "b", "c"]\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.join(["a", "b"], "-")))\n  end\nend\n', 0, b'"a-b"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.last("abc")))\n  end\nend\n', 0, b'some("c")\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.length("héllo")))\n  end\nend\n', 0, b'5\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.next_codepoint("abc")))\n  end\nend\n', 0, b'some({"a", "bc"})\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.next_grapheme("e\\u0301x")))\n  end\nend\n', 0, b'some({"e\xcc\x81", "x"})\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.pad_leading("7", 3, "0")))\n    IO.puts(inspect(String.pad_leading("ab", 4)))\n  end\nend\n',
  0,
  b'"007"\n"  ab"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.pad_trailing("ab", 4, ".")))\n  end\nend\n', 0, b'"ab.."\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.printable?("abc")))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.replace_leading("aaab", "a", "x")))\n  end\nend\n', 0, b'"xxxb"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.replace_prefix("unhappy", "un", "")))\n  end\nend\n', 0, b'"happy"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.replace_suffix("main.alc", ".alc", ".go")))\n  end\nend\n', 0, b'"main.go"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.replace_trailing("abbb", "b", "x")))\n  end\nend\n', 0, b'"axxx"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.reverse("abc")))\n  end\nend\n', 0, b'"cba"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.split_at("alchemy", 2)))\n  end\nend\n', 0, b'{"al", "chemy"}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.splitter("red,green blue", [",", " "]) |> Enum.to_list()))\n  end\nend\n',
  0,
  b'["red", "green", "blue"]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.starts_with("alchemy", "al")))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(String.starts_with?("alchemy", "al")))\n'
  '    IO.puts(inspect(String.starts_with?("alchemy", ["gold", "alc"])))\n'
  '  end\n'
  'end\n',
  0,
  b'true\ntrue\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.to_integer("42")))\n    IO.puts(inspect(String.to_integer("ff", 16)))\n  end\nend\n',
  0,
  b'42\n255\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.trim("  hi \\n")))\n    IO.puts(inspect(String.trim("xxhixx", "x")))\n  end\nend\n',
  0,
  b'"hi"\n"hi"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.trim_leading("  hi ")))\n  end\nend\n', 0, b'"hi "\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.trim_trailing("  hi ")))\n  end\nend\n', 0, b'"  hi"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.upcase("hello")))\n  end\nend\n', 0, b'"HELLO"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.valid?("héllo")))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.ceil_div(7, 2)))\n  end\nend\n', 0, b'4\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.digits(123)))\n    IO.puts(inspect(Integer.digits(5, 2)))\n  end\nend\n',
  0,
  b'[1, 2, 3]\n[1, 0, 1]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.extended_gcd(99, 78)))\n  end\nend\n', 0, b'{3, -11, 14}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.floor_div(-7, 2)))\n  end\nend\n', 0, b'-4\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.gcd(12, 18)))\n  end\nend\n', 0, b'6\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.is_even(4)))\n  end\nend\n', 0, b'true\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.is_odd(4)))\n  end\nend\n', 0, b'false\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.mod(-7, 3)))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Integer.parse("42")))\n'
  '    IO.puts(inspect(Integer.parse("ff", 16)))\n'
  '    IO.puts(inspect(case Integer.parse("4x") do\n'
  '      ok(_) -> "number"\n'
  '      error(_) -> "not a number"\n'
  '    end))\n'
  '  end\n'
  'end\n',
  0,
  b'ok(42)\nok(255)\n"not a number"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.pow(2, 10)))\n  end\nend\n', 0, b'1024\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.to_string(255)))\n    IO.puts(inspect(Integer.to_string(255, 16)))\n  end\nend\n',
  0,
  b'"255"\n"FF"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Integer.undigits([1, 2, 3])))\n    IO.puts(inspect(Integer.undigits([1, 0, 1], 2)))\n  end\nend\n',
  0,
  b'123\n5\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.decode16("6869")))\n  end\nend\n', 0, b'some("hi")\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.decode16!("6869")))\n  end\nend\n', 0, b'"hi"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.decode32(Base.encode32("hi"))))\n  end\nend\n', 0, b'some("hi")\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.decode32!(Base.encode32("hi"))))\n  end\nend\n', 0, b'"hi"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.decode64("aGk=")))\n    IO.puts(inspect(Base.decode64("!")))\n  end\nend\n',
  0,
  b'some("hi")\nnone\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.decode64!("aGk=")))\n  end\nend\n', 0, b'"hi"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(String.downcase(Base.encode16("hi"))))\n  end\nend\n', 0, b'"6869"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.encode32("hi")))\n  end\nend\n', 0, b'"NBUQ===="\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.encode64("hi")))\n  end\nend\n', 0, b'"aGk="\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.hex_decode32("CO======")))\n  end\nend\n', 0, b'some("f")\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.url_decode64(Base.url_encode64("hi?"))))\n  end\nend\n', 0, b'some("hi?")\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.url_decode64!(Base.url_encode64("hi?"))))\n  end\nend\n', 0, b'"hi?"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Base.url_encode64("hi")))\n  end\nend\n', 0, b'"aGk="\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Path.basename("src/main.alc")))\n'
  '    IO.puts(inspect(Path.basename("src/main.alc", ".alc")))\n'
  '  end\n'
  'end\n',
  0,
  b'"main.alc"\n"main"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Path.dirname("src/app/main.alc")))\n  end\nend\n', 0, b'"src/app"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Path.extname("main.alc")))\n    IO.puts(inspect(Path.extname("README")))\n  end\nend\n',
  0,
  b'".alc"\n""\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Path.join("src", "main.alc")))\n    IO.puts(inspect(Path.join(["a", "b", "c"])))\n  end\nend\n',
  0,
  b'"src/main.alc"\n"a/b/c"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Path.relative_to("/usr/local/bin", "/usr")))\n  end\nend\n', 0, b'"local/bin"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Path.rootname("src/main.alc")))\n    IO.puts(inspect(Path.rootname("main.alc", ".go")))\n  end\nend\n',
  0,
  b'"src/main"\n"main.alc"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Path.safe_relative("a/../b")))\n    IO.puts(inspect(Path.safe_relative("../etc")))\n  end\nend\n',
  0,
  b'some("b")\nnone\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Path.split("src/app/main.alc")))\n  end\nend\n', 0, b'["src", "app", "main.alc"]\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(URI.decode("a%20b")))\n'
  '    IO.puts(inspect(case URI.decode("%zz") do\n'
  '      ok(_) -> "valid"\n'
  '      error(_) -> "malformed"\n'
  '    end))\n'
  '  end\n'
  'end\n',
  0,
  b'ok("a b")\n"malformed"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(URI.decode_query("q=a+b&page=2")))\n  end\nend\n', 0, b'%{"page" => "2", "q" => "a b"}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(URI.decode_www_form("a+b%26c")))\n  end\nend\n', 0, b'ok("a b&c")\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(URI.encode("https://example.com/a b?q=é")))\n  end\nend\n',
  0,
  b'"https://example.com/a%20b?q=%C3%A9"\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(URI.encode_query(%{"q" => "a b", "page" => "2"})))\n  end\nend\n', 0, b'"page=2&q=a+b"\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(URI.encode_www_form("a b&c=d")))\n  end\nend\n', 0, b'"a+b%26c%3Dd"\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(case URI.new("http://example.com/%zz") do\n'
  '      ok(_) -> "valid"\n'
  '      error(_) -> "malformed"\n'
  '    end))\n'
  '  end\n'
  'end\n',
  0,
  b'"malformed"\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    uri = URI.parse("https://ada@example.com:8443/a/b?q=1#top")\n'
  '    IO.puts(inspect({uri.scheme, uri.userinfo, uri.host, uri.port}))\n'
  '    IO.puts(inspect({uri.path, uri.query, uri.fragment}))\n'
  '    IO.puts(inspect(URI.parse("http://example.com").port))\n'
  '    IO.puts(inspect(URI.parse("/only/a/path").host))\n'
  '  end\n'
  'end\n',
  0,
  b'{some("https"), some("ada"), some("example.com"), some(8443)}\n{"/a/b", some("q=1"), some("top")}\nsome(80)\nnone\n',
  b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    ok(v) = Version.parse("2.10.3")\n'
  '    IO.puts(inspect({v.major, v.minor, v.patch}))\n'
  '    ok(pre) = Version.parse("1.0.0-rc.1+build5")\n'
  '    IO.puts(inspect({pre.pre, pre.build}))\n'
  '    IO.puts(inspect(case Version.parse("1.2") do\n'
  '      ok(_) -> "valid"\n'
  '      error(reason) -> reason\n'
  '    end))\n'
  '  end\n'
  'end\n',
  0,
  b'{2, 10, 3}\n{["rc", "1"], some("build5")}\n"invalid version \\"1.2\\""\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Version.parse!("1.2.3").minor))\n  end\nend\n', 0, b'2\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Range.disjoint?(1..5, 6..9)))\n    IO.puts(inspect(Range.disjoint?(1..5, 5..9)))\n  end\nend\n',
  0,
  b'true\nfalse\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Range.new(1, 3)))\n    IO.puts(inspect(Range.new(0, 10, 5) |> Enum.to_list()))\n  end\nend\n',
  0,
  b'1..3\n[0, 5, 10]\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Range.shift(1..3, 2)))\n  end\nend\n', 0, b'3..5\n', b''),
 ('defmodule T do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Range.size(1..10)))\n'
  '    IO.puts(inspect(Range.size(1..10//4)))\n'
  '    IO.puts(inspect(Range.size(1..0//1)))\n'
  '  end\n'
  'end\n',
  0,
  b'10\n3\n0\n',
  b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Range.split(1..10, 3)))\n  end\nend\n', 0, b'{1..3, 4..10}\n', b''),
 ('defmodule T do\n  def main() do\n    IO.puts(inspect(Range.to_list(5..1//-2)))\n  end\nend\n', 0, b'[5, 3, 1]\n', b'')]
# programs the pinned compiler rejects
REJECTS=[]


def generated():
    """The checked-in library source is what scripts/generate-prelude.py makes of library/*.alc."""
    import importlib.util
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('generate_prelude',root/'scripts/generate-prelude.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    text,count=module.generate()
    assert text==(root/'implementations/alchem/native-prelude-data.alc').read_text(),'run scripts/generate-prelude.py'
    return count


def verify(compiler):
    count=generated()
    with tempfile.TemporaryDirectory(prefix='alchem-library-') as d:
        out=Path(d)/'out'
        for source,status,stdout,stderr in RUNS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    print(f'PASS library: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; {count} functions of library/*.alc')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
