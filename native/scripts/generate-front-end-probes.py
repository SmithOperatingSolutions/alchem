#!/usr/bin/env python3
"""Regenerate harness/front-end-probes.json for the front_end gate
(harness/front_end.py). Not used by normal builds.

    generate-front-end-probes.py PINNED

The probes are small programs written for what the checker's walk
(tools/alchem-typing.alc) follows that the repository's own files reach
seldom or not at all: try with its rescue, catch, else and after arms, the
calendar sigils with the forms Go's time.Parse takes and refuses, the
other sigils, a branch whose type a later branch settles, a function
whose every path raises, and a builtin struct's defaults. Each is written
twice, with a mistake after the construct, which the walk reaches only by
following the construct, and without it. For each, what `check` of the
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
]


def main(arguments):
    if len(arguments) != 1:
        raise SystemExit(__doc__)
    texts = []
    for body, extra in bodies:
        texts.append(prog(body, extra, True))
        texts.append(prog(body, extra, False))
    checks = front_end.checked(Path(arguments[0]).resolve(), texts, True)
    front_end.PROBES.write_text(json.dumps([{'text': text, 'check': check} for text, check in zip(texts, checks)], indent=0) + '\n')
    print(f'wrote {front_end.PROBES.name}: {len(texts)} probes, {sum(check[0] != 0 for check in checks)} refused')


if __name__ == '__main__':
    main(sys.argv[1:])
