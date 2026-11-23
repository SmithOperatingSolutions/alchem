#!/usr/bin/env python3
"""Regenerate harness/front-end-probes.json for the front_end gate
(harness/front_end.py). Not used by normal builds.

    generate-front-end-probes.py PINNED

The probes are small programs written for what the checker's walk
(tools/alchem-typing.alc) follows that the repository's own files reach
seldom or not at all: try with its rescue, catch, else and after arms, the
calendar sigils with the forms Go's time.Parse takes and refuses, the
other sigils, a branch whose type a later branch settles (with what a
constructor shows of it), a function whose every path raises, a builtin
struct's defaults, with and its else, setup blocks and the contexts they
give, and protocols. Most are written twice, with a mistake after the
construct, which the walk reaches only by following the construct, and
without it. For each, what `check` of the
pinned command line PINNED (build/dev/alchem-upstream.bin) says of it as
a file of its own is written: front_end.checked."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
import front_end

BAD = '    bad: integer = "s"\n'


def prog(body, extra, trailer):
    """A program whose main is the lines given, with a mistake after them or without."""
    lines = ''.join('    ' + l + '\n' for l in body)
    return 'defmodule Main do\n' + extra + '  def main() do\n' + lines + (BAD if trailer else '') + '    IO.puts("done")\n  end\nend\n'


EXC = '  defexception Oops do\n    message: string\n    code: integer\n  end\n  struct Plain do\n    n: integer\n  end\n'
SIG = '  def sigil_x(text: string, modifiers: string): integer do\n    String.length(text) + String.length(modifiers)\n  end\n'
PARSE = '  def parse(text: string): result[integer, string] do\n    Integer.parse(text)\n  end\n  def find(n: integer): option[integer] do\n    if n > 0 do some(n) else none end\n  end\n'
bodies = [
 # try
 (['x = try do', '  1', 'rescue', '  _ -> 2', 'end'], ''),
 (['x = try do', '  nope(1)', 'rescue', '  _ -> 2', 'end'], ''),
 (['x = try do', '  1', 'rescue', '  e in Plain -> 2', 'end'], EXC),
 (['x = try do', '  1', 'rescue', '  e in Oops -> e.code', 'end'], EXC),
 (['x = try do', '  1', 'rescue', '  e in Oops -> e.nothing', 'end'], EXC),
 (['x = try do', '  1', 'rescue', '  %Oops{code: c} -> c', 'end'], EXC),
 (['x = try do', '  1', 'rescue', '  %Plain{n: c} -> c', 'end'], EXC),
 (['x = try do', '  1', 'rescue', '  m: integer -> m', 'end'], ''),
 (['x = try do', '  1', 'rescue', '  m -> String.length(m)', 'end'], ''),
 (['x = try do', '  1', 'rescue', '  m -> m', 'end'], ''),
 (['x: integer = try do', '  1', 'rescue', '  _ -> "a"', 'end'], ''),
 (['x = try do', '  IO.puts("a")', 'rescue', '  _ -> 1', 'end'], ''),
 (['x = try do', '  1', 'rescue', '  _ -> 2', 'else', '  n -> n + 1', 'end'], ''),
 (['x = try do', '  IO.puts("a")', 'rescue', '  _ -> 2', 'else', '  n -> n + 1', 'end'], ''),
 (['x = try do', '  "a"', 'rescue', '  _ -> 2', 'else', '  n -> n + 1', 'end'], ''),
 (['x = try do', '  1', 'rescue', '  _ -> 2', 'after', '  IO.puts("t")', 'end'], ''),
 (['x = try do', '  1', 'rescue', '  _ -> 2', 'after', '  nope(2)', 'end'], ''),
 (['x = try do', '  throw(5)', '  1', 'catch', '  v: integer -> v', 'end'], ''),
 (['x = try do', '  throw(5)', '  1', 'catch', '  v: nothing -> 2', 'end'], ''),
 (['x = try do', '  throw(5)', '  1', 'catch', '  v: string -> v', 'end'], ''),
 (['x = try do', '  throw(5)', '  1', 'catch', '  v -> v', 'end'], ''),
 (['try do', '  IO.puts("a")', 'rescue', '  _ -> IO.puts("b")', 'end'], ''),
 (['try do', '  IO.puts("a")', 'rescue', '  _ -> nope(3)', 'end'], ''),
 (['try do', '  1', 'rescue', '  m -> m', 'end'], ''),
 (['x = try do', '  raise("boom")', 'rescue', '  m -> m', 'end', 'y: integer = x'], ''),
 (['x = try do', '  []', 'rescue', '  _ -> [1]', 'end', 'y: integer = x'], ''),
 (['x = try do', '  []', 'rescue', '  _ -> []', 'end'], ''),
 (['x = try do', '  raise("boom")', 'rescue', '  _ -> raise("again")', 'end'], ''),
 (['x = try do', '  1', 'rescue', '  m when String.length(m) > 2 -> 2', '  _ -> 3', 'end'], ''),
 (['x = try do', '  1', 'rescue', '  m when m -> 2', '  _ -> 3', 'end'], ''),
 (['x = try do', '  if 1 > 2 do', '    return 5', '  end', '  1', 'rescue', '  _ -> 2', 'end'], ''),
 # calendar
] + [([f'd = ~{k}[{v}]'], '') for k, v in [
 ('D','2026-02-30'),('D','2024-02-29'),('D','2023-02-29'),('D','1900-02-29'),('D','2000-02-29'),('D',' 2026-01-05 '),('D','2026-1-05'),('D','2026-13-01'),('D','2026-00-10'),('D','2026-01-00'),('D','0000-01-01'),('D','2026-01-05x'),('D','26-01-05'),('D','2026/01/05'),('D',''),
 ('T','10:00:00.123456'),('T','1:02:03'),('T','24:00:00'),('T','23:59:59'),('T','10:00:60'),('T','10:60:00'),('T','10:00:00,5'),('T','10:00:00.'),('T','10:0:00'),('T','10:00:0'),('T','10:00'),('T','10:00:00.1234567890123'),('T','10:00:00.5x'),
 ('N','2026-01-05 13:04:05'),('N','2026-01-05T13:04:05'),('N','2026-01-05  13:04:05'),('N','2026-01-0513:04:05'),('N','2026-01-05t13:04:05'),('N','2026-01-05 13:04:05Z'),('N','2026-01-05 13:04:05.25'),('N','2026-01-05'),
 ('U','2026-01-05T13:04:05Z'),('U','2026-01-05 13:04:05Z'),('U','2026-01-05 13:04:05+02:00'),('U','2026-01-05T13:04:05.5-07:00'),('U','2026-01-05T13:04:05'),('U','2026-01-05T13:04:05+25:00'),('U','2026-01-05T13:04:05z'),('U','2026-01-05T13:04:05+24:60'),('U','2026-01-05T13:04:05+0200'),('U','2026-01-05T13:04:05+02'),('U','2026-01-05T13:04:05 Z'),('U','2026-01-05T3:04:05Z'),('U','2026-01-05T13:04:05*02:00'),('U','2026-01-05T13:04:05+2:00'),('U','2026-01-05T13:04:05+02:61'),('U','2026-01-03T0:0:00:00Z'),('U','2026-01-05T13:04:05,123Z'),
]] + [
 (['d: Time = ~D[2026-01-01]'], ''),
 (['d = ~D[2026-01-01]', 'y = d.year + d.nothing'], ''),
 (['d = ~U[2026-01-01T00:00:00Z]', 'z: integer = d.time_zone'], ''),
 # other sigils
 (['c = ~c"abc"', 'n: string = c'], ''),
 (['c: list[string] = ~c"ab"'], ''),
 (['c = ~c""', 'n: string = c'], ''),
 (['c = ~C"a#{1}"', 'n: string = c'], ''),
 (['n = 1', 'c = ~c"a#{n}"'], ''),
 (['h = ~h"<b>x</b>"', 'n: string = h'], ''),
 (['w = "x"', 'h = ~h"<b>#{w}</b>"', 'n: string = h'], ''),
 (['w = {1, 2}', 'h = ~h"<b>#{w}</b>"'], ''),
 (['w = [1]', 'h = ~h"<b>#{w}</b>"'], ''),
 (['w = 1.5', 'h = ~h"<b>#{w}</b>#{:a}#{1}"', 'n: string = h'], ''),
 (['h = ~h"x"i'], ''),
 (['h = ~H"x#{1}"', 'n: string = h'], ''),
 (['h = ~H"x"q'], ''),
 (['h = ~h"<i>#{nope}</i>"'], ''),
 (['v = ~x"abc"', 'n: string = v'], SIG),
 (['v = ~x"abc"ab', 'n: string = v'], SIG),
 (['w = "q"', 'v = ~x"a#{w}c"', 'n: string = v'], SIG),
 (['v = ~q"abc"'], SIG),
 (['w = "q"', 'v = ~q"a#{w}c"'], SIG),
 (['r = ~r/a b #c/x', 'n: string = r'], ''),
 (['r = ~r/a [ #]b/xi', 'n: string = r'], ''),
 (['r = ~r/a/q'], ''),
 (['w = "q"', 'r = ~r/a#{w}/', 'n: string = r'], ''),
 (['w = "q"', 'r = ~r/a#{w}/i', 'n: string = r'], ''),
 (['w = "q"', 'r = ~r/a#{w}/q'], ''),
 (['w = 1', 'r = ~r/a#{w}/', 'n: string = r'], ''),
 (['w = {1}', 'r = ~r/a#{w}/'], ''),
 # retries
 (['v = Enum.map([1, 2], fn x -> raise("no") end)', 'n: string = v'], ''),
 (['assert_raise("boom", fn -> raise("boom") end)'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  if x > 1 do', '    raise("no")', '  else', '    raise("never")', '  end', 'end)', 'n: string = v'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  if x > 1 do', '    raise("no")', '  else', '    x', '  end', 'end)', 'n: string = v'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  if x > 1 do', '    []', '  else', '    [x]', '  end', 'end)', 'n: string = v'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  if x > 1 do', '    []', '  else', '    []', '  end', 'end)'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  if x > 1 do', '    []', '  else', '    x', '  end', 'end)'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  case x do', '    1 -> []', '    2 -> none', '    _ -> [x]', '  end', 'end)'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  case x do', '    1 -> []', '    2 -> raise("two")', '    _ -> [x]', '  end', 'end)', 'n: string = v'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  case x do', '    1 -> []', '    _ -> []', '  end', 'end)'], ''),
 (['a = 1', 'v = if a > 0 do', '  []', 'else', '  [1]', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = if a > 0 do', '  []', 'else', '  1', 'end'], ''),
 (['a = 1', 'v = if a > 0 do', '  []', 'else', '  []', 'end'], ''),
 (['a = 1', 'v = case a do', '  1 -> none', '  _ -> some(2)', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = case a do', '  1 -> raise("x")', '  _ -> 2', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = case a do', '  1 -> raise("x")', '  2 -> %{}', '  _ -> %{"a" => 1}', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = case a do', '  1 -> raise("x")', '  _ -> raise("y")', 'end'], ''),
 (['a = 1', 'v = if a > 0 do', '  ok(1)', 'else', '  error("x")', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = if a > 0 do', '  if a > 1 do', '    []', '  else', '    [2]', '  end', 'else', '  [1]', 'end', 'n: string = v'], ''),
 # builtin defaults
 (['v = %Version{major: 1, minor: 2, patch: 3}', 'n: string = v'], ''),
 (['v = %Version{major: 1, minor: 2}'], ''),
 (['v = %Version{major: 1, minor: 2, patch: 3, pre: ["rc"], build: some("b")}', 'n: string = v.pre'], ''),
 (['v = %Version{major: 1, minor: 2, patch: 3, pre: [1]}'], ''),
 (['v = %HTTP.Response{status: 200, headers: [], body: ""}', 'n: string = v.chunks'], ''),
 # branches that show part of a type
 (['a = 1', 'v = if a > 0 do', '  error("x")', 'else', '  ok(1)', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = case a do', '  1 -> none', '  2 -> some(1)', '  _ -> none', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = case a do', '  1 -> error("a")', '  2 -> error(2)', '  _ -> ok(1)', 'end'], ''),
 (['a = 1', 'v = case a do', '  1 -> error("a")', '  2 -> ok(1)', '  _ -> error("b")', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = case a do', '  1 -> ok(1)', '  2 -> ok(2)', '  _ -> error("b")', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = case a do', '  1 -> ok(1)', '  2 -> ok("two")', '  _ -> error("b")', 'end'], ''),
 (['a = 1', 'v = if a > 0 do', '  ok(1)', 'else', '  ok(2)', 'end'], ''),
 (['a = 1', 'v = if a > 0 do', '  none', 'else', '  none', 'end'], ''),
 (['a = 1', 'v = if a > 0 do', '  ok(1)', 'else', '  [1]', 'end'], ''),
 (['a = 1', 'v = if a > 0 do', '  ok(1)', 'else', '  none', 'end'], ''),
 (['a = 1', 'v = if a > 0 do', '  none', 'else', '  error("x")', 'end'], ''),
 (['a = 1', 'v = if a > 0 do', '  if a > 1 do', '    none', '  else', '    none', '  end', 'else', '  some(1)', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = if a > 0 do', '  if a > 1 do', '    ok(1)', '  else', '    error("x")', '  end', 'else', '  ok(3)', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = if a > 0 do', '  some(none)', 'else', '  some(some(1))', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = if a > 0 do', '  {none, 1}', 'else', '  {some(1), 2}', 'end'], ''),
 (['a = 1', 'v = if a > 0 do', '  ok(none)', 'else', '  error("x")', 'end'], ''),
 (['a = 1', 'v = try do', '  none', 'rescue', '  _ -> some(1)', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = try do', '  ok(a)', 'rescue', '  m -> error(m)', 'end', 'n: string = v'], ''),
 (['a = 1', 'v = if a > 0 do', '  try do', '    ok(a)', '  rescue', '    _ -> ok(2)', '  end', 'else', '  error("x")', 'end', 'n: string = v'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  w = if x > 1 do', '    none', '  else', '    some(x)', '  end', '  w', 'end)', 'n: string = v'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  if x > 1 do', '    none', '  else', '    some(x)', '  end', 'end)', 'n: string = v'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  if x > 1 do', '    ok(x)', '  else', '    error("small")', '  end', 'end)'], ''),
 (['v = Enum.map([1, 2], fn x ->', '  w = if x > 1 do', '    ok(x)', '  else', '    error("small")', '  end', '  w', 'end)', 'n: string = v'], ''),
 (['a = 1', 'if a > 0 do', '  none', 'else', '  some(1)', 'end'], ''),
 (['a = 1', 'v = for x <- [1, 2] do', '  if x > a do', '    none', '  else', '    some(x)', '  end', 'end', 'n: string = v'], ''),
 # catch arms that name no type
 (['x = try do', '  throw(5)', '  throw("s")', '  1', 'catch', '  v -> 2', 'end'], ''),
 (['x = try do', '  1', 'catch', '  v -> 2', 'end'], ''),
 (['x = try do', '  1', 'catch', '  :done -> 2', 'end'], ''),
 (['x = try do', '  1', 'catch', '  7 -> 2', 'end'], ''),
 (['x = try do', '  throw(:stop)', '  1', 'catch', '  :stop -> 2', '  _ -> 3', 'end'], ''),
 (['x = try do', '  throw({1, "a"})', '  1', 'catch', '  {a, b} -> a', 'end'], ''),
 (['x = try do', '  throw({1, "a"})', '  1', 'catch', '  {a, b} -> b', 'end'], ''),
 (['x = try do', '  Enum.each([1, 2], fn n -> throw(n) end)', '  1', 'catch', '  v -> v', 'end'], ''),
 (['x = try do', '  try do', '    throw("inner")', '    1', '  catch', '    s -> String.length(s)', '  end', 'catch', '  v -> 2', 'end'], ''),
 (['x = try do', '  try do', '    throw("inner")', '    1', '  rescue', '    _ -> 3', '  end', 'catch', '  v -> String.length(v)', 'end'], ''),
 (['x = try do', '  if 1 > 2 do', '    throw(1.5)', '  end', '  throw(2.5)', '  1', 'catch', '  v -> round(v)', 'end'], ''),
 (['x = try do', '  throw(elem({1, "a"}, 0))', '  1', 'catch', '  v -> v', 'end'], ''),
 (['x = try do', '  throw(5)', '  1', 'catch', '  v -> v', 'rescue', '  _ -> 3', 'end'], ''),
 (['x = try do', '  throw(%Plain{n: 1})', '  1', 'catch', '  %Plain{n: n} -> n', 'end'], EXC),
 (['x = try do', '  1', 'catch', '  %Plain{n: n} -> n', 'end'], EXC),
 # with and its else
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  error(_) -> 0', 'end'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  error(m) -> String.length(m)', 'end', 'n: string = v'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  ok(b) -> b', 'end'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  ok(b) -> b', '  error(_) -> 0', 'end'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  none -> 0', 'end'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  error(_) -> nope(1)', 'end'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  error(_) -> "zero"', 'end'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  error("bad") -> 0', 'end'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  error("bad") -> 0', '  error(_) -> 1', '  error(m) -> 2', 'end'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  error(m) when String.length(m) > 2 -> 0', '  error(_) -> 1', 'end'], PARSE),
 (['v = with ok(a) <- parse("1") do', '  a', 'else', '  error(m) when String.length(m) > 2 -> 0', 'end'], PARSE),
 (['v = with ok(a) <- parse("1"),', '         some(b) <- find(a) do', '  a + b', 'else', '  error(_) -> 0', '  none -> 1', 'end', 'n: string = v'], PARSE),
 (['v = with ok(a) <- parse("1"),', '         some(b) <- find(a) do', '  a + b', 'else', '  error(_) -> 0', 'end'], PARSE),
 (['v = with ok(a) <- parse("1"),', '         some(b) <- find(a) do', '  a + b', 'else', '  _ -> 0', 'end', 'n: string = v'], PARSE),
 (['v = with [a, b] <- String.split("a:b", ":") do', '  a <> b', 'else', '  parts -> Integer.to_string(length(parts))', 'end', 'n: integer = v'], PARSE),
 (['with ok(a) <- parse("1") do', '  IO.puts(Integer.to_string(a))', 'else', '  error(m) -> IO.puts(m)', 'end'], PARSE),
 (['with ok(a) <- parse("1") do', '  IO.puts(Integer.to_string(a))', 'else', '  error(m) -> IO.puts(a)', 'end'], PARSE),
]


def tests(lines):
    """A test file of the lines given."""
    return 'defmodule ProbeTest do\n' + ''.join('  ' + line + '\n' for line in lines) + 'end\n'


def module(lines):
    """A program of the lines given and a main."""
    return 'defmodule Main do\n' + ''.join('  ' + line + '\n' for line in lines) + '  def main() do\n    IO.puts("done")\n  end\nend\n'


USES = ['test "uses it", given do', '  assert(given == %s)', 'end']
SHAPES = ['struct Circle do', '  radius: float', 'end', 'struct Rect do', '  width: float', '  height: float', 'end', 'defprotocol Shape do', '  def area(shape): float', '  def describe(shape, unit): string', 'end']
CIRCLE = ['defimpl Shape, for: Circle do', '  def area(circle: Circle): float do', '    3.0 * circle.radius', '  end', '  def describe(circle: Circle, unit: string): string do', '    "circle" <> unit', '  end', 'end']
SHOW = ['defprotocol Show do', '  def show(value): string', 'end', 'defimpl Show, for: integer do', '  def show(n: integer): string do', '    "int #{n}"', '  end', 'end', 'defimpl Show, for: list[a] do', '  def show(items: list[a]): string do', '    "#{length(items)} items"', '  end', 'end']
programs = [
 # setup blocks and the contexts they give
 tests(['setup do', '  5', 'end'] + [line % '5' if '%s' in line else line for line in USES]),
 tests(['setup do', '  5', 'end'] + [line % '"five"' if '%s' in line else line for line in USES]),
 tests(['setup do', '  IO.puts("ready")', 'end'] + [line % '5' if '%s' in line else line for line in USES]),
 tests([line % '5' if '%s' in line else line for line in USES]),
 tests(['setup do', '  nope(1)', 'end', 'test "plain" do', '  assert(1 == 1)', 'end']),
 tests(['setup do', '  {1, "a"}', 'end', 'test "takes both", {n, text} do', '  assert(n == 1 and text == "a")', 'end']),
 tests(['setup do', '  {1, "a"}', 'end', 'test "takes both", {n, text} do', '  assert(n == text)', 'end']),
 tests(['setup do', '  {1, "a"}', 'end', 'test "takes three", {n, text, more} do', '  assert(n == 1)', 'end']),
 tests(['setup_all do', '  1', 'end', 'setup n do', '  n + 1', 'end', 'test "second", m do', '  assert(m == 2)', 'end']),
 tests(['setup_all do', '  1', 'end', 'setup n do', '  Integer.to_string(n)', 'end', 'test "second", m do', '  assert(m == 2)', 'end']),
 tests(['setup n do', '  n + 1', 'end', 'test "none above" do', '  assert(1 == 1)', 'end']),
 tests(['setup do', '  1', 'end', 'describe "inner" do', '  setup n do', '    [n]', '  end', '  test "list", items do', '    assert(items == [1])', '  end', 'end', 'test "outer", n do', '  assert(n == [1])', 'end']),
 tests(['describe "inner" do', '  setup do', '    "inner"', '  end', '  test "has it", text do', '    assert(text == "inner")', '  end', 'end', 'test "outside", text do', '  assert(text == "inner")', 'end']),
 tests(['setup do', '  1', 'end', 'setup n do', '  IO.puts(Integer.to_string(n))', 'end', 'test "keeps the first", n do', '  assert(n == "one")', 'end']),
 tests(['setup do', '  if 1 > 2 do', '    1', '  else', '    "two"', '  end', 'end', 'test "plain" do', '  assert(1 == 1)', 'end']),
 tests(['setup do', '  raise("no")', 'end', 'test "takes it", n do', '  assert(n == 1)', 'end']),
 tests(['setup do', '  {}', 'end', 'test "takes it", n do', '  assert(n == {})', 'end']),
 tests(['setup do', '  none', 'end', 'test "plain" do', '  assert(1 == 1)', 'end']),
 # protocols
 module(SHAPES + CIRCLE + ['def size(): float do', '  Shape.area(%Circle{radius: 1.0})', 'end']),
 module(SHAPES + CIRCLE + ['def size(): string do', '  Shape.area(%Circle{radius: 1.0})', 'end']),
 module(SHAPES + CIRCLE + ['def size(): float do', '  Shape.area(%Rect{width: 1.0, height: 2.0})', 'end']),
 module(SHAPES + CIRCLE + ['def size(): float do', '  Shape.area()', 'end']),
 module(SHAPES + CIRCLE + ['def size(): float do', '  Shape.area(nope)', 'end']),
 module(SHAPES + CIRCLE + ['def size(): string do', '  Shape.describe(%Circle{radius: 1.0}, 2)', 'end']),
 module(SHAPES + CIRCLE + ['def size(): string do', '  Shape.describe(%Circle{radius: 1.0})', 'end']),
 module(SHAPES + CIRCLE[:4] + ['end']),
 module(SHAPES + CIRCLE + CIRCLE),
 module(SHAPES + [line.replace('Shape,', 'Solid,') for line in CIRCLE]),
 module(SHAPES + CIRCLE + ['defimpl Shape, for: Rect do', '  def area(rect: Rect): float do', '    rect.width', '  end', '  def describe(rect: Rect, unit: string): string do', '    unit', '  end', '  def corners(rect: Rect): integer do', '    4', '  end', 'end']),
 module(SHAPES + [line.replace('(circle: Circle): float', '(circle: Circle): integer').replace('3.0 * circle.radius', '3') for line in CIRCLE]),
 module(SHAPES + [line.replace('(circle: Circle, unit: string)', '(circle: Circle)').replace('"circle" <> unit', '"circle"') for line in CIRCLE]),
 module(SHAPES + [line.replace('3.0 * circle.radius', 'circle.side') for line in CIRCLE]),
 module(SHOW + ['def all(): string do', '  Show.show(1) <> Show.show([1, 2]) <> Show.show(["a"])', 'end']),
 module(SHOW + ['def all(): string do', '  Show.show(1.5)', 'end']),
 module(SHOW + ['def all(items: list[b], one: b): string do', '  Show.show(items) <> Show.show(one)', 'end']),
 module(SHOW + ['def all(): integer do', '  Show.show(1)', 'end']),
 module(SHOW + ['def all(): list[string] do', '  Enum.map([1, 2], fn n -> Show.show(n) end)', 'end']),
 module(SHOW + ['def all(): list[string] do', '  Enum.map(["a"], fn n -> Show.show(n) end)', 'end']),
]


def texts():
    """Every probe: each body with the mistake after it and without, then the whole programs."""
    out = []
    for body, extra in bodies:
        out.append(prog(body, extra, True))
        out.append(prog(body, extra, False))
    return out + programs


def main(arguments):
    if len(arguments) != 1:
        raise SystemExit(__doc__)
    probes = texts()
    checks = front_end.checked(Path(arguments[0]).resolve(), probes, True)
    front_end.PROBES.write_text(json.dumps([{'text': text, 'check': check} for text, check in zip(probes, checks)], indent=0) + '\n')
    print(f'wrote {front_end.PROBES.name}: {len(probes)} probes, {sum(check[0] != 0 for check in checks)} refused')


if __name__ == '__main__':
    main(sys.argv[1:])
