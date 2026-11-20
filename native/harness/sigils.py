#!/usr/bin/env python3
"""Sigils, index syntax, literal patterns in bindings, references to library
functions written in Alchem and lambdas typed by an earlier lambda's result:
every program runs as the pinned compiler runs it."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (program, status, standard output, standard error) as the pinned compiler runs it
RUNS=[('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(inspect(~w(red green blue)))\n'
  '    IO.puts(inspect(~w()))\n'
  '    IO.puts(inspect(~w(  a   b  )))\n'
  '    IO.puts(inspect(~w[a b]a))\n'
  '    IO.puts(inspect(~w/a b/c))\n'
  '    IO.puts(inspect(~w|x y|))\n'
  '    IO.puts(inspect(~w"x y"))\n'
  "    IO.puts(inspect(~w'x y'))\n"
  '    IO.puts(inspect(~w{x y}))\n'
  '    IO.puts(inspect(~w<x y>))\n'
  '    IO.puts(~s(say "hi"))\n'
  '    IO.puts(~s(a\\nb))\n'
  '    IO.puts(~s(a\\)b))\n'
  '    IO.puts(~s(a\\\\b))\n'
  '    IO.puts(~S(raw #{name} \\n))\n'
  '    IO.puts(~S[a\\]b])\n'
  '    IO.puts(~s[a]b)\n'
  '    name = "ada"\n'
  '    IO.puts(~s(hello #{name}))\n'
  '    IO.puts(~s(hello #{name} and #{1 + 2} #{true} #{:at}!))\n'
  '    IO.puts(inspect(~w(#{name} lovelace)))\n'
  '    IO.puts(inspect(~w(  #{name}#{name}   x  )))\n'
  '    IO.puts(inspect(~c(hi!)))\n'
  '    IO.puts(inspect(~C(hi #{x})))\n'
  '    IO.puts(inspect(~c(é€😀)))\n'
  '    IO.puts(inspect(~c()))\n'
  '    IO.puts(~s(#{String.upcase(name)}) <> ~s[#{"]"}])\n'
  '    IO.puts(~s(a\\#{name}))\n'
  '    IO.puts(~s(#{"a)b"} (x\\)))\n'
  '    IO.puts(~s(100% #) <> ~s(#) <> ~s({#}))\n'
  '    IO.puts(inspect(length(~w(a b c))))\n'
  '    IO.puts(inspect(~w(a b) ++ ~w(c)))\n'
  '    IO.puts(inspect(~w(a b) == ["a", "b"]))\n'
  '    IO.puts(inspect(Enum.map(~w(a bb), fn w -> String.length(w) end)))\n'
  '    IO.puts(~s(tab\tin) <> ~s(é"\'))\n'
  '    IO.puts(inspect(~s(q"q)))\n'
  '    IO.puts(inspect(~w(a\\ b c\\)d)))\n'
  '    IO.puts(inspect(~w(a b c)))\n'
  '    IO.puts(~s(#{name |> String.upcase()}) <> ~s(#{%{"k" => "v}"}["k"]}))\n'
  '  end\n'
  'end\n',
  0,
  b'["red", "green", "blue"]\n[]\n["a", "b"]\n["a", "b"]\n["a", "b"]\n["x", "y"]\n["x", "y"]\n["x", "y"]\n["x", "y"]\n["x", "y"]\nsay "hi"\na\\nb\na)'
  b'b\na\\\\b\nraw #{name} \\n\na]b\na\nhello ada\nhello ada and 3 true at!\n["ada", "lovelace"]\n["adaada", "x"]\n[104, 105, 33]\n[104, 105, 32, 35,'
  b' 123, 120, 125]\n[233, 8364, 128512]\n[]\nADA]\na\\ada\na)b (x)\n100% ##{#}\n3\n["a", "b", "c"]\ntrue\n[1, 2]\ntab\tin\xc3\xa9"\'\n"q\\"q"\n["a'
  b'\\\\", "b", "c)d"]\n["a", "b", "c"]\nADAv}\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(~s"""\n'
  '    hello #{1 + 1}\n'
  '      "quoted" \\t tab\n'
  '    """)\n'
  '    IO.puts(~S"""\n'
  '    raw #{x} \\n\n'
  '      "quoted"\n'
  '    """)\n'
  '    IO.puts(inspect(~w"""\n'
  '    a b\n'
  '    c\n'
  '    """))\n'
  '    IO.puts(inspect(~c"""\n'
  '    ab\n'
  '    """))\n'
  '    x = "v"\n'
  '    IO.puts(inspect(~w"""\n'
  '    a #{x}\n'
  '    c\n'
  '    """))\n'
  '  end\n'
  'end\n',
  0,
  b'hello 2\n  "quoted" \t tab\n\nraw #{x} \\n\n  "quoted"\n\n["a", "b", "c"]\n[97, 98, 10]\n["a", "v", "c"]\n',
  b''),
 ('defmodule Example do\n'
  '  def sigil_p(text: string, modifiers: string): list[string] do\n'
  '    parts = String.split(text, "/")\n'
  '    if modifiers == "r" do\n'
  '      Enum.reverse(parts)\n'
  '    else\n'
  '      parts\n'
  '    end\n'
  '  end\n'
  '  def sigil_X(text: string, modifiers: string): string do\n'
  '    text <> "|" <> modifiers\n'
  '  end\n'
  '\n'
  '  def main() do\n'
  '    assert(~c(hi!) == [104, 105, 33])\n'
  '    assert(~p(usr/local/bin) == ["usr", "local", "bin"])\n'
  '    root = "opt"\n'
  '    assert(~p(#{root}/bin)r == ["bin", "opt"])\n'
  '    IO.puts(~X(a #{root})abU)\n'
  '    IO.puts(inspect(~p"""\n'
  '    a/b\n'
  '    """))\n'
  '    IO.puts(inspect(~p(a/b)r |> Enum.join("-")))\n'
  '  end\n'
  'end\n',
  0,
  b'a #{root}|abU\n["a", "b\\n"]\n"b-a"\n',
  b''),
 ('defmodule M do\n  def main() do\n    IO.puts(inspect(~w(a\u3000b c d e f)))\n    IO.puts(inspect(~c(a\\xffb)))\n  end\nend\n',
  0,
  b'["a", "b", "c", "d", "e", "f"]\n[97, 92, 120, 102, 102, 98]\n',
  b''),
 ('defmodule M do\n'
  '  def f(a: string, b: list[string] \\\\ ~w(d e)): string do a <> Enum.join(b, "") end\n'
  '  def main() do\n'
  '    IO.puts(f(~s(x)))\n'
  '    IO.puts(f("y", ~w(z)))\n'
  '    t = ~s(ab)\n'
  '    case t do\n'
  '      "ab" -> IO.puts("m")\n'
  '      _ -> IO.puts("n")\n'
  '    end\n'
  '    IO.puts(~s[#{~s(#{~s<deep>})}])\n'
  '  end\n'
  'end\n',
  0,
  b'xde\nyz\nm\ndeep\n',
  b''),
 ('defmodule M do\n'
  '  def f(a: string \\\\ ~s(x#{1 + 1})): string do a end\n'
  '  def g(a: list[integer] \\\\ ~c(ab), b: list[string] \\\\ ~w(p q)): integer do length(a) + length(b) end\n'
  '  def main() do\n'
  '    IO.puts(f() <> inspect(g()))\n'
  '  end\n'
  'end\n',
  0,
  b'x24\n',
  b''),
 ('defmodule M do\n'
  '  def sigil_u(t: string, m: string): string do t <> m end\n'
  '  def f(a: string \\\\ ~u(x)): string do a end\n'
  '  def main() do\n'
  '    IO.puts(f())\n'
  '  end\n'
  'end\n',
  0,
  b'x\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(~s"""\n'
  '    plain\n'
  '    """ <> ~S"""\n'
  '      keep #{this}\n'
  '        indent\n'
  '      """)\n'
  '    x = ~w"""\n'
  '      alpha beta\n'
  '      gamma\n'
  '    """\n'
  '    IO.puts(inspect(x))\n'
  '  end\n'
  'end\n',
  0,
  b'plain\nkeep #{this}\n  indent\n\n["alpha", "beta", "gamma"]\n',
  b''),
 ('defmodule M do\n  def main() do\n    IO.puts(~S"""\n    a\n  """)\n  end\nend\n', 0, b'  a\n\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(inspect(~w(a b)c ++ ["d"]))\n'
  '    IO.puts(inspect(~s(é)))\n'
  '    IO.puts(inspect(~c(\\)\\\\n)))\n'
  '  end\n'
  'end\n',
  0,
  b'["a", "b", "d"]\n"\xc3\xa9"\n[41, 92, 92, 110]\n',
  b''),
 ('defmodule M do\n'
  '  @a ~s(plain)\n'
  '  @b ~w(x y)\n'
  '  @c ~c(ab)\n'
  '  @d ~S(raw)\n'
  '  def main() do\n'
  '    IO.puts(@a <> inspect(@b) <> inspect(@c) <> @d)\n'
  '  end\n'
  'end\n',
  0,
  b'plain["x", "y"][97, 98]raw\n',
  b''),
 ('defmodule M do\n  def sigil_u(t: string, m: string): string do t <> m end\n  @a ~u(x)\n  def main() do\n    IO.puts(@a)\n  end\nend\n',
  0,
  b'x\n',
  b''),
 ('defmodule M do\n  def main() do\n    m = %{"a" => 1}\n    IO.puts(inspect(m["zz"]))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:22: map key not found\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def f(l: list[integer], i: integer): integer do\n'
  '    l[i]\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f([1, 2], 1)))\n'
  '    IO.puts(inspect(f([1, 2], 2)))\n'
  '  end\n'
  'end\n',
  2,
  b'2\n',
  b'<stdin>:3:6: list index out of bounds\n  at M.f (<stdin>:3)\n  at M.main (<stdin>:7)\n'),
 ('defmodule M do\n  def main() do\n    l = [1, 2]\n    x = 5 +\n      l[-1]\n    IO.puts(inspect(x))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:5:8: list index out of bounds\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\n    l: list[integer] = []\n    IO.puts(inspect(l[0]))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:22: list index out of bounds\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  '    l = [1, 2]\n'
  '    y = l\n'
  '    [a, b] = y\n'
  '    IO.puts(inspect(a + b))\n'
  '    z = l [0]\n'
  '    IO.puts(inspect(z))\n'
  '  end\n'
  'end\n',
  0,
  b'3\n1\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    l = [1, 2, 3]\n'
  '    case l[0] do\n'
  '      1 -> IO.puts("one")\n'
  '      _ -> IO.puts("other")\n'
  '    end\n'
  '    if l[1] == 2 do IO.puts("two") end\n'
  '    t = l[9223372036854775807]\n'
  '    IO.puts(inspect(t))\n'
  '  end\n'
  'end\n',
  2,
  b'one\ntwo\n',
  b'<stdin>:9:10: list index out of bounds\n  at M.main (<stdin>:9)\n'),
 ('defmodule M do\n  def main() do\n    l = [[1, 2], [3]]\n    IO.puts(inspect(l[1][5]))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:25: list index out of bounds\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\n    m = %{"a" => [1]}\n    IO.puts(inspect(m["b"][0]))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:22: map key not found\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  '    flags = [false, true]\n'
  '    x = cond do\n'
  '      flags[0] -> 1\n'
  '      flags[1] -> 2\n'
  '      true -> 3\n'
  '    end\n'
  '    IO.puts(inspect(x))\n'
  '    l = [[1], [2]]\n'
  '    y = case l[1] do\n'
  '      [a] -> a\n'
  '      _ -> 0\n'
  '    end\n'
  '    IO.puts(inspect(y))\n'
  '    z = case 1 do\n'
  '      1 -> l [0]\n'
  '      _ -> [5]\n'
  '    end\n'
  '    IO.puts(inspect(z))\n'
  '    w = case [1] do\n'
  '      [1] -> flags [1]\n'
  '      _ -> false\n'
  '    end\n'
  '    IO.puts(inspect(w))\n'
  '  end\n'
  'end\n',
  0,
  b'2\n2\n[1]\ntrue\n',
  b''),
 ('defmodule M do\n  def main() do\n    l = [[1], [2]]\n    z = l [a] = [5]\n    IO.puts(inspect(z))\n  end\nend\n', 0, b'[[1], [2]]\n', b''),
 ('defmodule M do\n'
  '  def h(l: list[t]): t do\n'
  '    l[0]\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(h(["z"])) <> inspect(h([[1]])[0]))\n'
  '    x = [1, 2]\n'
  '    y = %{:a => x}\n'
  '    IO.puts(inspect(y[:a][1] + x[0]))\n'
  '    IO.puts(inspect([[1, 2], [3]][0][1]))\n'
  '    t = {[1, 2], %{"k" => {3, 4}}}\n'
  '    IO.puts(inspect(t[0][1] + t[1]["k"][1]))\n'
  '    q = %{"a" => 1}\n'
  '    k = "a"\n'
  '    IO.puts(inspect(q[k] + q["a"]))\n'
  '    IO.puts(inspect(q[k <> ""]))\n'
  '  end\n'
  'end\n',
  0,
  b'"z"1\n3\n2\n6\n2\n1\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    p = {:a, 1}\n'
  '    :a = elem(p, 0)\n'
  '    true = (1 == 1)\n'
  '    x = 1\n'
  '    1 = x\n'
  '    "s" = "s"\n'
  '    -1 = 0 - x\n'
  '    ^x = 1\n'
  '    false = x == 2\n'
  '    :ok = if x == 1 do :ok else :no end\n'
  '    0 = x - 1\n'
  '    IO.puts("ok")\n'
  '  end\n'
  'end\n',
  0,
  b'ok\n',
  b''),
 ('defmodule M do\n  def main() do\n    x = 2\n    1 = x\n    IO.puts("ok")\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:5: pattern match failed\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\n    x = "b"\n    "a" = x\n  end\nend\n', 2, b'', b'<stdin>:4:5: pattern match failed\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\n    x = :b\n    :a = x\n  end\nend\n', 2, b'', b'<stdin>:4:5: pattern match failed\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\n    x = 1\n    -1 = x\n  end\nend\n', 2, b'', b'<stdin>:4:5: pattern match failed\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\n    x = 2\n    true = x == 3\n    IO.puts("y")\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:5: pattern match failed\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n  def main() do\n    x = 1\n    ^x = 2\n  end\nend\n', 2, b'', b'<stdin>:4:5: pattern match failed\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def f(n: integer): atom do\n'
  '    :ok = if n > 0 do :ok else :bad end\n'
  '    1 = n\n'
  '    :done\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(f(1)))\n'
  '    IO.puts(inspect(f(2)))\n'
  '  end\n'
  'end\n',
  2,
  b':done\n',
  b'<stdin>:4:5: pattern match failed\n  at M.f (<stdin>:4)\n  at M.main (<stdin>:9)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  '    {1, :a, "s", true, x} = {1, :a, "s", true, 5}\n'
  '    [1, y] = [1, 2]\n'
  '    %{:k => 3} = %{:k => 3}\n'
  '    some(4) = Enum.at([4], 0)\n'
  '    IO.puts(inspect(x + y))\n'
  '    {1, 2} = {1, 3}\n'
  '  end\n'
  'end\n',
  2,
  b'7\n',
  b'<stdin>:8:5: pattern match failed\n  at M.main (<stdin>:8)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.map([[1, 2], [3]], &Enum.count/1)))\n'
  '    IO.puts(inspect(Enum.map(["a", "b"], &String.to_atom/1)))\n'
  '  end\n'
  'end\n',
  0,
  b'[2, 1]\n[:a, :b]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.map(["a,b", "c"], &String.split(&1, ","))))\n'
  '    IO.puts(inspect(Enum.map([[1, 1]], &Enum.dedup(&1))))\n'
  '    IO.puts(inspect(Enum.map([1, 2], &Integer.pow(&1, 2))))\n'
  '  end\n'
  'end\n',
  0,
  b'[["a", "b"], ["c"]]\n[[1]]\n[1, 4]\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.map([1, 2], &Integer.to_string/1) |> Enum.map(&String.length/1)))\n'
  '    IO.puts(inspect(Enum.sort_by(["bb", "a"], &String.length/1)))\n'
  '    IO.puts(inspect(Enum.map([[1, 2], [3]], &Enum.max/1)))\n'
  '    IO.puts(inspect(Enum.flat_map([[1, 1], [2, 2]], &Enum.dedup/1)))\n'
  '    IO.puts(inspect(Enum.map(["a-b"], &Path.basename/1)))\n'
  '    IO.puts(inspect(Enum.map([1, 2], &Integer.is_even/1)))\n'
  '  end\n'
  'end\n',
  0,
  b'[1, 1]\n["a", "bb"]\n[2, 3]\n[1, 2]\n["a-b"]\n[false, true]\n',
  b''),
 ('defmodule M do\n  def main() do\n    IO.puts(inspect(Enum.map([1, 2], &Integer.is_even/1)))\n  end\nend\n', 0, b'[false, true]\n', b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.all?([2, 4], &Integer.is_even/1)))\n'
  '    IO.puts(inspect(Enum.map([[1, 2], [3]], &Enum.max/1)))\n'
  '    IO.puts(inspect(Enum.map(["Ab"], &String.downcase/1)))\n'
  '    IO.puts(inspect(Enum.map(["a b"], &String.split/1)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n[2, 3]\n["ab"]\n[["a", "b"]]\n',
  b''),
 ('defmodule T do\n'
  '  def by(items: list[a], f: fn[a, b], s: fn[b, b, boolean]): boolean do\n'
  '    s(f(hd(items)), f(hd(items)))\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(by(["bb"], fn a -> String.length(a) end, fn a, b -> a >= b end)))\n'
  '  end\n'
  'end\n',
  0,
  b'true\n',
  b''),
 ('defmodule T do\n'
  '  def wrap(x: a, f: fn[a, b], g: fn[b, list[b]]): list[b] do g(f(x)) end\n'
  '  def pick(x: a, f: fn[a, option[b]], g: fn[b, c], d: c): c do\n'
  '    case f(x) do\n'
  '      some(v) -> g(v)\n'
  '      none -> d\n'
  '    end\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(wrap(1, fn x -> {x, "s"} end, fn t -> [t, t] end)))\n'
  '    IO.puts(inspect(pick([7], fn l -> Enum.at(l, 0) end, fn v -> v * 2 end, 0)))\n'
  '    IO.puts(inspect(pick([7], fn l -> Enum.at(l, 3) end, fn v -> v * 2 end, 0)))\n'
  '    IO.puts(inspect(pick("k", fn s -> Map.fetch(%{"k" => [1]}, s) end, fn v -> length(v) end, 0)))\n'
  '  end\n'
  'end\n',
  0,
  b'[{1, "s"}, {1, "s"}]\n14\n0\n1\n',
  b''),
 ('defmodule T do\n'
  '  def pipe3(x: a, f: fn[a, b], g: fn[b, c]): c do g(f(x)) end\n'
  '  def main() do\n'
  '    r: option[integer] = pipe3(1, fn x -> [x] end, fn o -> Enum.at(o, 0) end)\n'
  '    IO.puts(inspect(r))\n'
  '    s: list[integer] = pipe3(1, fn x -> x end, fn o -> [] end)\n'
  '    IO.puts(inspect(s))\n'
  '  end\n'
  'end\n',
  0,
  b'some(1)\n[]\n',
  b''),
 ('defmodule T do\n'
  '  struct Pair[a, b] do\n'
  '    left: a\n'
  '    right: b\n'
  '  end\n'
  '  def fold(p: Pair[a, b], f: fn[a, c], g: fn[c, b, d]): d do g(f(p.left), p.right) end\n'
  '  def main() do\n'
  '    IO.puts(inspect(fold(%Pair{left: 1, right: "r"}, fn l -> Integer.to_string(l) end, fn s, r -> s <> r end)))\n'
  '  end\n'
  'end\n',
  0,
  b'"1r"\n',
  b''),
 ('defmodule M do\n'
  '  def apply1(f: fn[list[integer], list[integer]], l: list[integer]): list[integer] do f(l) end\n'
  '  def main() do\n'
  '    IO.puts(inspect(Enum.map([[1, 1, 2], [3, 3]], &Enum.dedup/1)))\n'
  '    IO.puts(inspect(Enum.map([:a, :b], &Atom.to_string/1)))\n'
  '    IO.puts(inspect(Enum.map(["a", "bcd"], &String.length/1)))\n'
  '    IO.puts(inspect(apply1(&Enum.reverse/1, [1, 2, 3])))\n'
  '    IO.puts(inspect(apply1(&Enum.dedup/1, [1, 1, 2])))\n'
  '    f: fn[list[integer], list[integer]] = &Enum.uniq/1\n'
  '    IO.puts(inspect(f.([1, 2, 1])))\n'
  '    g: fn[list[string], string, string] = &Enum.join/2\n'
  '    IO.puts(g.(["a", "b"], "-"))\n'
  '    IO.puts(inspect(Enum.map([[3, 1], [2]], &Enum.sort/1)))\n'
  '    IO.puts(inspect(Enum.map([["b", "a"], ["c"]], &Enum.sort/1)))\n'
  '    IO.puts(inspect(Enum.map([1, 2], &Integer.to_string/1)))\n'
  '    IO.puts(inspect(Enum.map(["a b", "c"], &String.split/1)))\n'
  '    IO.puts(inspect(Enum.reduce([1, 2, 3], 0, &Kernel.max/2)))\n'
  '    IO.puts(inspect(Enum.map([[1, 2], [3]], &Enum.sum/1)))\n'
  '    IO.puts(inspect(Enum.map([1, -2], &abs/1)))\n'
  '    IO.puts(inspect(Enum.map([[1, 2], [3]], &List.first/1)))\n'
  '    IO.puts(inspect(Enum.map([[1, 2], [3]], &hd/1)))\n'
  '    IO.puts(inspect(Enum.map(["x", "y"], &String.upcase/1)))\n'
  '    IO.puts(inspect(Enum.map([%{1 => 2}], &Map.keys/1)))\n'
  '    IO.puts(inspect(Enum.filter([[1], []], &Enum.empty?/1)))\n'
  '    IO.puts(inspect(Enum.map([[1, 2], [3, 4]], &Enum.reverse/1) |> Enum.map(&List.last/1)))\n'
  '  end\n'
  'end\n',
  0,
  b'[[1, 2], [3]]\n["a", "b"]\n[1, 3]\n[3, 2, 1]\n[1, 2]\n[1, 2]\na-b\n[[1, 3], [2]]\n[["a", "b"], ["c"]]\n["1", "2"]\n[["a", "b"], ["c"]]\n3\n[3, 3'
  b']\n[1, 2]\n[some(1), some(3)]\n[1, 3]\n["X", "Y"]\n[[1]]\n[[]]\n[some(1), some(3)]\n',
  b''),
 ('defmodule T do\n'
  '  def id2(x: a, f: fn[a, b]): b do f(x) end\n'
  '  def id3(x: a, f: fn[a, integer]): integer do f(x) end\n'
  '  def main() do\n'
  '    IO.puts(inspect(id3("ab", &String.length/1)))\n'
  '    IO.puts(inspect(id2(1, &Integer.to_string(&1))))\n'
  '    y: string = id2(1, &Integer.to_string/1)\n'
  '    IO.puts(y)\n'
  '    z: list[integer] = id2([1, 1], &Enum.dedup/1)\n'
  '    IO.puts(inspect(z))\n'
  '    IO.puts(inspect(id3([1, 1], &Enum.count/1)))\n'
  '    IO.puts(inspect(id3([1, 1], &Enum.sum/1)))\n'
  '    IO.puts(inspect(id3([1, 1], &hd/1)))\n'
  '  end\n'
  'end\n',
  0,
  b'2\n"1"\n1\n[1]\n2\n2\n1\n',
  b''),
 ('defmodule M do\n'
  '  @zero 0\n'
  '  @one (1)\n'
  '  def main() do\n'
  '    t = {1, "a", [3]}\n'
  '    IO.puts(inspect({t[(0)], t[-0], t[@zero], t[@one], t[ 2 ][0], t[((1))]}))\n'
  '    IO.puts(inspect([5, 6][@zero] + [5, 6][(1)]))\n'
  '    f: fn[string] = &IO.ANSI.red/0\n'
  '    IO.puts(inspect(f.()))\n'
  '    IO.puts(inspect(Enum.map([1], &IO.ANSI.color/1)))\n'
  '    IO.puts(inspect(Enum.map(["a"], &IO.inspect/1)))\n'
  '    IO.puts(inspect(Enum.map([-1], &Kernel.abs/1)))\n'
  '    IO.puts(inspect(~w(a b c d e f g h i j k l m n o p q r s t u v w x y z)))\n'
  '    IO.puts(inspect(~c(abcdefghijklmnopqrstuvwxyz)))\n'
  '    IO.puts(inspect(length(~w(a b c d e f g h i j k l m n o p q r s t u v w x y z a b c d e f g h i j k l m n o p q r s t u v w x y z a b c d e f '
  'g h i j k l m n o p q r s t u v w x y z))))\n'
  '  end\n'
  'end\n',
  0,
  b'{1, 1, 1, "a", 3, "a"}\n11\n"\\x1b[31m"\n["\\x1b[38;5;1m"]\n"a"\n["a"]\n[1]\n["a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n'
  b'", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z"]\n[97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113'
  b', 114, 115, 116, 117, 118, 119, 120, 121, 122]\n78\n',
  b''),
 ('defmodule M do\n'
  '  @other 1\n'
  '  @v0 %{"k" => [1, -2]}\n'
  '  @v1 [a: 1, b: 2]\n'
  '  @v2 not true\n'
  '  @v3 (1 + 2) * 3\n'
  '  @v4 1 < 2 and 3 >= 3 or false\n'
  '  @v5 "a" <> "b"\n'
  '  @v6 [1] ++ [2]\n'
  '  @v7 2 ** 3\n'
  '  @v8 :atom\n'
  '  @v9 [1 | [2]]\n'
  '  @v10 7 % 2\n'
  '  @v11 true && false\n'
  '  @v12 ~s(a) <> ~S(b)\n'
  '  @v13 {}\n'
  '  @v14 @other + 1\n'
  '  @v15 [@other, 2]\n'
  '  @v16 ~w(a b)\n'
  '  @v17 {:a, [1, 2]}\n'
  '  @v18 [1,\n'
  '    2]\n'
  '  @v19 1 +\n'
  '    2\n'
  '  @v20 "x" == "y"\n'
  '  @v21 ~c(ab)\n'
  '  @doc "plain"\n'
  '  def main() do\n'
  '    IO.puts(inspect(@v0))\n'
  '    IO.puts(inspect(@v1))\n'
  '    IO.puts(inspect(@v2))\n'
  '    IO.puts(inspect(@v3))\n'
  '    IO.puts(inspect(@v4))\n'
  '    IO.puts(inspect(@v5))\n'
  '    IO.puts(inspect(@v6))\n'
  '    IO.puts(inspect(@v7))\n'
  '    IO.puts(inspect(@v8))\n'
  '    IO.puts(inspect(@v9))\n'
  '    IO.puts(inspect(@v10))\n'
  '    IO.puts(inspect(@v11))\n'
  '    IO.puts(inspect(@v12))\n'
  '    IO.puts(inspect(@v13))\n'
  '    IO.puts(inspect(@v14))\n'
  '    IO.puts(inspect(@v15))\n'
  '    IO.puts(inspect(@v16))\n'
  '    IO.puts(inspect(@v17))\n'
  '    IO.puts(inspect(@v18))\n'
  '    IO.puts(inspect(@v19))\n'
  '    IO.puts(inspect(@v20))\n'
  '    IO.puts(inspect(@v21))\n'
  '  end\n'
  'end\n',
  0,
  b'%{"k" => [1, -2]}\n[a: 1, b: 2]\nfalse\n9\ntrue\n"ab"\n[1, 2]\n8\n:atom\n[1, 2]\n1\nfalse\n"ab"\n{}\n2\n[1, 2]\n["a", "b"]\n{:a, [1, 2]}\n[1, '
  b'2]\n3\nfalse\n[97, 98]\n',
  b''),
 ('defmodule M do\n  @moduledoc false\n  @doc """\n  Says k.\n  """\n  def main() do\n    IO.puts("k")\n  end\nend\n', 0, b'k\n', b''),
 ('defmodule M do\n'
  '  def pick(l: list[integer], i: integer): integer do\n'
  '    x = if i > 100 do 0 else l[i] + 1 end\n'
  '    x\n'
  '  end\n'
  '  def deep(m: map[string, list[integer]], k: string, i: integer): integer do\n'
  '    pick(m[k], i)\n'
  '  end\n'
  '  def main() do\n'
  '    m = %{"a" => [1, 2, 3], "b" => []}\n'
  '    IO.puts(inspect(deep(m, "a", 2)))\n'
  '    IO.puts(inspect(Enum.map([0, 1], fn i -> m["a"][i] * 2 end)))\n'
  '    IO.puts(inspect(deep(m, "b", 0)))\n'
  '  end\n'
  'end\n',
  2,
  b'4\n[2, 4]\n',
  b'<stdin>:3:31: list index out of bounds\n  at M.pick <closure> (<stdin>:3)\n  at M.pick (<stdin>:3)\n  at M.deep (<stdin>:7)\n  at M.main (<stdin'
  b'>:13)\n'),
 ('defmodule M do\n'
  '  def main() do\n'
  '    t = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20}\n'
  '    IO.puts(inspect(t[0] + t[15] + t[16] + t[19]))\n'
  '    l = [10, 20, 30]\n'
  '    m = %{"a" => 5, "b" => 7}\n'
  '    IO.puts(inspect(l[0] + l[1] * m["a"] - m["b"]))\n'
  '    IO.puts(inspect([l[2], l[0]]))\n'
  '    IO.puts(inspect({m["a"], l[1]}))\n'
  '    IO.puts(inspect(%{l[0] => m["b"]}))\n'
  '    IO.puts(inspect(Enum.sum([l[0], l[1], l[2]])))\n'
  '    n = [[1, 2], [3, 4]]\n'
  '    IO.puts(inspect(n[1][0] + n[0][1]))\n'
  '    IO.puts(inspect(Enum.map(n, fn row -> row[1] end)))\n'
  '    case l do\n'
  '      [a | _] when l[1] > a -> IO.puts("guard")\n'
  '      _ -> IO.puts("no")\n'
  '    end\n'
  '    ix = 2\n'
  '    IO.puts(inspect(l[ix - 1] == l[1]))\n'
  '    IO.puts("#{l[0]} and #{m["a"]}")\n'
  '    s = ["x", "y"]\n'
  '    IO.puts(s[1] <> s[0])\n'
  '    am = %{:k => [%{"z" => {1, [2, 3]}}]}\n'
  '    IO.puts(inspect(am[:k][0]["z"][1][1]))\n'
  '    o = [some(1), none]\n'
  '    IO.puts(inspect(o[1]) <> inspect(o[0]))\n'
  '    IO.puts(inspect(l[9]))\n'
  '  end\n'
  'end\n',
  2,
  b'54\n103\n[30, 10]\n{5, 20}\n%{10 => 7}\n60\n5\n[2, 4]\nguard\ntrue\n10 and 5\nyx\n3\nnonesome(1)\n',
  b'<stdin>:28:22: list index out of bounds\n  at M.main (<stdin>:28)\n'),
 ('defmodule M do\n  def main() do\n    l = [10, 20, 30]\n    IO.puts(inspect(l[0 - 1]))\n  end\nend\n',
  2,
  b'',
  b'<stdin>:4:22: list index out of bounds\n  at M.main (<stdin>:4)\n'),
 ('defmodule M do\n'
  '  def idx(): integer do\n'
  '    IO.puts("index")\n'
  '    0\n'
  '  end\n'
  '  def lst(): list[integer] do\n'
  '    IO.puts("list")\n'
  '    [4]\n'
  '  end\n'
  '  def key(): string do\n'
  '    IO.puts("key")\n'
  '    "k"\n'
  '  end\n'
  '  def mp(): map[string, integer] do\n'
  '    IO.puts("map")\n'
  '    %{"k" => 9}\n'
  '  end\n'
  '  def main() do\n'
  '    IO.puts(inspect(lst()[idx()] + mp()[key()]))\n'
  '  end\n'
  'end\n',
  0,
  b'list\nindex\nmap\nkey\n13\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    t = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20}\n'
  '    IO.puts(inspect(t))\n'
  '    IO.puts(inspect(elem(t, 0) + elem(t, 15) + elem(t, 16) + elem(t, 19)))\n'
  '    IO.puts(inspect(t == t))\n'
  '    {a, _, _, _, _, _, _, _, _, _, _, _, _, _, _, p, q, _, _, z} = t\n'
  '    IO.puts(inspect(a + p + q + z))\n'
  '    u = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 21}\n'
  '    IO.puts(inspect(t == u) <> inspect(t[14] + t[15]))\n'
  '  end\n'
  'end\n',
  0,
  b'{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20}\n54\ntrue\n54\nfalse31\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(inspect(~w(a)))\n'
  '    IO.puts(inspect(~w(  a  )))\n'
  '    IO.puts(inspect(~w(a bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb)))\n'
  '    IO.puts(inspect(~w(a b c d e f g hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh)))\n'
  '    IO.puts(inspect(~w(aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa b c d)))\n'
  '    IO.puts(inspect(~w(日本 語 \u3000x\u3000y é€ 😀😀)))\n'
  '    IO.puts(inspect(~w(a\u3000b c d e f)))\n'
  '    IO.puts(inspect(~w(a\u3000\u3000\u3000b\u3000c d e f\u3000)))\n'
  '    IO.puts(inspect(~c(日本語é€😀abcdefghijklmnop😀)))\n'
  '    IO.puts(inspect(~c(a)))\n'
  '    IO.puts(inspect(~w(\ttab\tsep )))\n'
  '    IO.puts(inspect(length(~w(w0 w1 w2 w3 w4 w5 w6 w7 w8 w9 w10 w11 w12 w13 w14 w15 w16 w17 w18 w19 w20 w21 w22 w23 w24 w25 w26 w27 w28 w29 w30 '
  'w31 w32 w33 w34 w35 w36 w37 w38 w39 w40 w41 w42 w43 w44 w45 w46 w47 w48 w49 w50 w51 w52 w53 w54 w55 w56 w57 w58 w59 w60 w61 w62 w63 w64 w65 w66 '
  'w67 w68 w69 w70 w71 w72 w73 w74 w75 w76 w77 w78 w79 w80 w81 w82 w83 w84 w85 w86 w87 w88 w89 w90 w91 w92 w93 w94 w95 w96 w97 w98 w99 w100 w101 '
  'w102 w103 w104 w105 w106 w107 w108 w109 w110 w111 w112 w113 w114 w115 w116 w117 w118 w119 w120 w121 w122 w123 w124 w125 w126 w127 w128 w129 w130 '
  'w131 w132 w133 w134 w135 w136 w137 w138 w139 w140 w141 w142 w143 w144 w145 w146 w147 w148 w149 w150 w151 w152 w153 w154 w155 w156 w157 w158 w159 '
  'w160 w161 w162 w163 w164 w165 w166 w167 w168 w169 w170 w171 w172 w173 w174 w175 w176 w177 w178 w179 w180 w181 w182 w183 w184 w185 w186 w187 w188 '
  'w189 w190 w191 w192 w193 w194 w195 w196 w197 w198 w199 w200 w201 w202 w203 w204 w205 w206 w207 w208 w209 w210 w211 w212 w213 w214 w215 w216 w217 '
  'w218 w219 w220 w221 w222 w223 w224 w225 w226 w227 w228 w229 w230 w231 w232 w233 w234 w235 w236 w237 w238 w239 w240 w241 w242 w243 w244 w245 w246 '
  'w247 w248 w249 w250 w251 w252 w253 w254 w255 w256 w257 w258 w259 w260 w261 w262 w263 w264 w265 w266 w267 w268 w269 w270 w271 w272 w273 w274 w275 '
  'w276 w277 w278 w279 w280 w281 w282 w283 w284 w285 w286 w287 w288 w289 w290 w291 w292 w293 w294 w295 w296 w297 w298 w299 w300 w301 w302 w303 w304 '
  'w305 w306 w307 w308 w309 w310 w311 w312 w313 w314 w315 w316 w317 w318 w319 w320 w321 w322 w323 w324 w325 w326 w327 w328 w329 w330 w331 w332 w333 '
  'w334 w335 w336 w337 w338 w339 w340 w341 w342 w343 w344 w345 w346 w347 w348 w349 w350 w351 w352 w353 w354 w355 w356 w357 w358 w359 w360 w361 w362 '
  'w363 w364 w365 w366 w367 w368 w369 w370 w371 w372 w373 w374 w375 w376 w377 w378 w379 w380 w381 w382 w383 w384 w385 w386 w387 w388 w389 w390 w391 '
  'w392 w393 w394 w395 w396 w397 w398 w399 w400 w401 w402 w403 w404 w405 w406 w407 w408 w409 w410 w411 w412 w413 w414 w415 w416 w417 w418 w419 w420 '
  'w421 w422 w423 w424 w425 w426 w427 w428 w429 w430 w431 w432 w433 w434 w435 w436 w437 w438 w439 w440 w441 w442 w443 w444 w445 w446 w447 w448 w449 '
  'w450 w451 w452 w453 w454 w455 w456 w457 w458 w459 w460 w461 w462 w463 w464 w465 w466 w467 w468 w469 w470 w471 w472 w473 w474 w475 w476 w477 w478 '
  'w479 w480 w481 w482 w483 w484 w485 w486 w487 w488 w489 w490 w491 w492 w493 w494 w495 w496 w497 w498 w499 w500 w501 w502 w503 w504 w505 w506 w507 '
  'w508 w509 w510 w511 w512 w513 w514 w515 w516 w517 w518 w519 w520 w521 w522 w523 w524 w525 w526 w527 w528 w529 w530 w531 w532 w533 w534 w535 w536 '
  'w537 w538 w539 w540 w541 w542 w543 w544 w545 w546 w547 w548 w549 w550 w551 w552 w553 w554 w555 w556 w557 w558 w559 w560 w561 w562 w563 w564 w565 '
  'w566 w567 w568 w569 w570 w571 w572 w573 w574 w575 w576 w577 w578 w579 w580 w581 w582 w583 w584 w585 w586 w587 w588 w589 w590 w591 w592 w593 w594 '
  'w595 w596 w597 w598 w599))))\n'
  '    '
  'IO.puts(inspect(Enum.sum(~c(aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀aé€😀))))\n'
  '    '
  'IO.puts(inspect(String.length(~s(01234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789012345678901234567890123456789))))\n'
  '  end\n'
  'end\n',
  0,
  b'["a"]\n["a"]\n["a", "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]\n["a", "b", "c", "d", "e", "f", "g",'
  b' "hhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhhh"]\n["aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
  b'aaaaaaaaaaaaa", "b", "c", "d"]\n["\xe6\x97\xa5\xe6\x9c\xac", "\xe8\xaa\x9e", "x", "y", "\xc3\xa9\xe2\x82\xac", "\xf0\x9f\x98\x80\xf0\x9f\x98'
  b'\x80"]\n["a", "b", "c", "d", "e", "f"]\n["a", "b", "c", "d", "e", "f"]\n[26085, 26412, 35486, 233, 8364, 128512, 97, 98, 99, 100, 101, 102, 10'
  b'3, 104, 105, 106, 107, 108, 109, 110, 111, 112, 128512]\n[97]\n["tab", "sep"]\n600\n41161800\n5000\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    IO.puts(~S"""\n'
  '      deep\n'
  '    mid\n'
  '\t  tabbed\n'
  '    #{no} \\n end\n'
  '    """)\n'
  '    IO.puts(inspect(~w"""\n'
  '    a  b\n'
  '      c\n'
  '    """))\n'
  '    IO.puts(~s(a\\)b\\\\c\\)) <> ~S[x\\]y\\\\] <> ~s|p\\|q|)\n'
  '  end\n'
  'end\n',
  0,
  b'  deep\nmid\n\t  tabbed\n#{no} \\n end\n\n["a", "b", "c"]\na)b\\\\c)x]y\\\\p|q\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    flags = [false, true]\n'
  '    xs = [1, 2]\n'
  '    x = cond do\n'
  '      flags[0] -> 1\n'
  '      flags[1] -> 2\n'
  '      true -> 3\n'
  '    end\n'
  '    IO.puts(inspect(x))\n'
  '    y = case xs do [] -> xs [h | _] -> [h] end\n'
  '    IO.puts(inspect(y))\n'
  '    z = case xs do\n'
  '      [a, _] when flags[1] -> a\n'
  '      [a, _] when xs[0] > 5 -> a + 1\n'
  '      _ -> 0\n'
  '    end\n'
  '    IO.puts(inspect(z))\n'
  '    w = cond do flags[0] -> 1 flags[1] -> 2 true -> 3 end\n'
  '    IO.puts(inspect(w))\n'
  '    v = case xs do [] -> xs [0] -> xs [_ | _] -> [9] end\n'
  '    IO.puts(inspect(v))\n'
  '    u = case xs do n when Enum.any?(n, fn e -> flags[1] end) -> 1 _ -> 2 end\n'
  '    IO.puts(inspect(u))\n'
  '  end\n'
  'end\n',
  0,
  b'2\n[1]\n1\n2\n[9]\n1\n',
  b''),
 ('defmodule M do\n'
  '  def main() do\n'
  '    xs = [1, 2]\n'
  '    i = 0\n'
  '    r = case xs do [_, _, _] -> xs [k] -> [k + i] _ -> [6] end\n'
  '    IO.puts(inspect(r))\n'
  '  end\n'
  'end\n',
  0,
  b'[6]\n',
  b''),
 ('#alchem-bundle 2\n'
  '# 138 /work/main.alc\n'
  '# 281 /work/sig.alc\n'
  'defmodule Main do import "module:Sig"\n'
  '\n'
  '  def main() do\n'
  '    IO.puts(~q(hi)ab)\n'
  '    IO.puts(Sig.use_it())\n'
  '    IO.puts(Sig.use_k())\n'
  '  end\n'
  'end\n'
  'defmodule Sig do\n'
  '  def sigil_q(text: string, mods: string): string do\n'
  '    "<" <> text <> ":" <> mods <> ">"\n'
  '  end\n'
  '  def use_it(): string do\n'
  '    ~q(inner)\n'
  '  end\n'
  '  defp sigil_k(text: string, mods: string): string do\n'
  '    "k" <> text\n'
  '  end\n'
  '  def use_k(): string do\n'
  '    ~k(x)\n'
  '  end\n'
  'end\n',
  0,
  b'<hi:ab>\n<inner:>\nkx\n',
  b''),
 ('#alchem-bundle 2\n'
  '# 85 /work/main3.alc\n'
  '# 281 /work/sig.alc\n'
  'defmodule Main do import "module:Sig"\n'
  '\n'
  '  def main() do\n'
  '    IO.puts(~k(hi))\n'
  '  end\n'
  'end\n'
  'defmodule Sig do\n'
  '  def sigil_q(text: string, mods: string): string do\n'
  '    "<" <> text <> ":" <> mods <> ">"\n'
  '  end\n'
  '  def use_it(): string do\n'
  '    ~q(inner)\n'
  '  end\n'
  '  defp sigil_k(text: string, mods: string): string do\n'
  '    "k" <> text\n'
  '  end\n'
  '  def use_k(): string do\n'
  '    ~k(x)\n'
  '  end\n'
  'end\n',
  0,
  b'khi\n',
  b''),
 ('#alchem-bundle 2\n'
  '# 126 /work/main5.alc\n'
  '# 281 /work/sig.alc\n'
  'defmodule Main do import "module:Sig"\n'
  '\n'
  '  def main() do\n'
  '    IO.puts(Sig.sigil_q("a", "b"))\n'
  '    IO.puts(Sig.use_it())\n'
  '  end\n'
  'end\n'
  'defmodule Sig do\n'
  '  def sigil_q(text: string, mods: string): string do\n'
  '    "<" <> text <> ":" <> mods <> ">"\n'
  '  end\n'
  '  def use_it(): string do\n'
  '    ~q(inner)\n'
  '  end\n'
  '  defp sigil_k(text: string, mods: string): string do\n'
  '    "k" <> text\n'
  '  end\n'
  '  def use_k(): string do\n'
  '    ~k(x)\n'
  '  end\n'
  'end\n',
  0,
  b'<a:b>\n<inner:>\n',
  b''),
 ('#alchem-bundle 2\n'
  '# 88 /work/main7.alc\n'
  '# 129 /work/sig3.alc\n'
  'defmodule Main do import "module:Sig3"\n'
  '\n'
  '  def main() do\n'
  '    IO.puts(~q(hi)ab)\n'
  '  end\n'
  'end\n'
  'defmodule Sig3 do\n'
  '  defp sigil_q(text: string, mods: string): string do\n'
  '    "3" <> text\n'
  '  end\n'
  '  def f(): string do ~q(z) end\n'
  'end\n',
  0,
  b'3hi\n',
  b''),
 ('#alchem-bundle 2\n'
  '# 88 /work/main8.alc\n'
  '# 129 /work/sig3.alc\n'
  'defmodule Main do import "module:Sig3"\n'
  '\n'
  '  def main() do\n'
  '    IO.puts(Sig3.f())\n'
  '  end\n'
  'end\n'
  'defmodule Sig3 do\n'
  '  defp sigil_q(text: string, mods: string): string do\n'
  '    "3" <> text\n'
  '  end\n'
  '  def f(): string do ~q(z) end\n'
  'end\n',
  0,
  b'3z\n',
  b'')]
# programs the pinned compiler rejects
REJECTS=['defmodule M do\n  def main() do\n    IO.puts(inspect(~q(a)))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect(~c(a#{1})))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect(~W(a b)))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(~s(a #{1) )\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(~s(a \n  b))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(~s(a #{[1]} b))\n  end\nend\n',
 'defmodule M do\n  def sigil_z(text: string): string do text end\n  def main() do\n    IO.puts(~z(a))\n  end\nend\n',
 'defmodule M do\n  def sigil_z(text: integer, m: string): string do m end\n  def main() do\n    IO.puts(~z(a))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    x = ~s(a)\n    y = x ~s(b)\n  end\nend\n',
 'defmodule M do\n'
 '  @words ~w(one two)\n'
 '  def pick(n: integer): string do\n'
 '    case n do\n'
 '      1 -> ~s(end # not a comment)\n'
 '      2 -> ~S(do " fn -> )\n'
 '      _ -> ~s(other)\n'
 '    end\n'
 '  end\n'
 '  def words(): list[string] do\n'
 '    ~w(a b c)\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(pick(1) <> pick(2) <> pick(3))\n'
 '    f = fn(x: string): string do x <> ~s( end) end\n'
 '    IO.puts(f.(~s(x)))\n'
 '    IO.puts(inspect(@words) <> inspect(@day))\n'
 '    IO.puts(inspect(Enum.map(words(), fn w -> ~s(<#{w}>) end)))\n'
 '    y = if true do ~w(yes) else ~w(no) end\n'
 '    IO.puts(inspect(y))\n'
 '    z = cond do\n'
 '      length(y) == 1 -> ~s(one)\n'
 '      true -> ~s(many)\n'
 '    end\n'
 '    IO.puts(z)\n'
 '    ~w(a b) |> Enum.join("+") |> IO.puts()\n'
 '    IO.puts(inspect({~s(a), ~c(b), ~w(c)}))\n'
 '    IO.puts(inspect(%{~s(k) => ~w(v)}))\n'
 '    IO.puts(inspect([~s(a), ~s(b)]))\n'
 '    IO.puts(inspect(~s(a) <> ~s(b) == "ab"))\n'
 '    IO.puts(inspect(~s(a) in ~w(a b)))\n'
 '    for w <- ~w(p q) do\n'
 '      IO.puts(w)\n'
 '    end\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def h(): string do "h" end\n'
 '  def f(a: string \\\\ ~s(x#{h()})): string do a end\n'
 '  def main() do\n'
 '    IO.puts(f())\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  @greeting ~s(hello #{1 + 2})\n'
 '  @list ~w(a b)a\n'
 '  def main() do\n'
 '    IO.puts(@greeting <> inspect(@list))\n'
 '    x = ~s(one)\n'
 '    IO.puts(x)\n'
 '    y = ~s(a) <> ~S(b) <>\n'
 '      ~s(c)\n'
 '    IO.puts(y)\n'
 '    IO.puts(inspect(~w(a b)\n'
 '    ))\n'
 '    IO.puts(inspect([~w(a), ~w(b c)]))\n'
 '    IO.puts(inspect(~s(x) == ~S(x)))\n'
 '    case ~s(k) do\n'
 '      "k" -> IO.puts("yes")\n'
 '      _ -> IO.puts("no")\n'
 '    end\n'
 '    z = if ~s(a) == "a", do: ~s(t), else: ~s(f)\n'
 '    IO.puts(z)\n'
 '    IO.puts(~s())\n'
 '    IO.puts(inspect(~s()))\n'
 '    IO.puts(inspect(String.length(~s(日本語))))\n'
 '    IO.puts(inspect(~w(日本 語)))\n'
 '    IO.puts(~s<a>b> <> ~s{a\\}b} <> ~s|a\\|b| <> ~s/a\\/b/ <> ~s\'a\\\'b\' <> ~s"a\\"b")\n'
 '    IO.puts(~S<a\\>b> <> ~S(\\) <> ~s(\\) <> ~s(\\\\) <> ~s(\\t))\n'
 '    IO.puts(~s(#{~s(#{1})}#{2}))\n'
 '    IO.puts(~s(a#{"}"}b#{"#{1}{"}))\n'
 '    IO.puts(inspect(~w(#{"a b"} c)))\n'
 '    IO.puts(inspect(~w(#{1}#{:x})))\n'
 '    IO.puts(inspect(~w(#{""})))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\n    IO.puts(~s(a#{{1, 2}}b))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(~s(unterminated)\n    IO.puts(~s(x\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(~s(a #{1 +\n      2}))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(~s(a)~s(b))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(~s(a).length)\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(~S""" a\n    b\n    """)\n  end\nend\n',
 'defmodule M do\n  @a "x#{1 + 2}"\n  def main() do\n    IO.puts(@a)\n  end\nend\n',
 'defmodule M do\n  @a ~s(x#{1})\n  def main() do\n    IO.puts(@a)\n  end\nend\n',
 'defmodule M do\n  @n 4\n  @a ~w(x#{@n} y)\n  def main() do\n    IO.puts(inspect(@a))\n  end\nend\n',
 'defmodule M do\n  @a [1, 2, 3][0]\n  @m %{"k" => 1}["k"]\n  def main() do\n    IO.puts(inspect(@a + @m))\n  end\nend\n',
 'defmodule M do\n'
 '  struct Box do\n'
 '    items: list[integer]\n'
 '    names: map[string, list[integer]]\n'
 '  end\n'
 '  def get(): list[integer] do [7, 8, 9] end\n'
 '  def main() do\n'
 '    m = %{"a" => 1, "b" => 2}\n'
 '    IO.puts(inspect(m["a"] + m["b"]))\n'
 '    l = [10, 20, 30]\n'
 '    IO.puts(inspect(l[0] + l[2]))\n'
 '    counts = %{:blue => 3, :red => 1}\n'
 '    IO.puts(inspect(counts[:blue]))\n'
 '    n = %{"a" => [5, 6]}\n'
 '    IO.puts(inspect(n["a"][1]))\n'
 '    nested: list[list[integer]] = [[], [1, 2]]\n'
 '    IO.puts(inspect(nested[1][0]))\n'
 '    pair = {1, {2, "x"}}\n'
 '    IO.puts(inspect(pair[0]) <> inspect(pair[1][1]))\n'
 '    i = 1\n'
 '    IO.puts(inspect(l[i]) <> inspect(l[i + 1]) <> inspect(l[l[0] - 10]))\n'
 '    b = %Box{items: [4, 5], names: %{"k" => [1]}}\n'
 '    IO.puts(inspect(b.items[1]) <> inspect(b.names["k"][0]))\n'
 '    IO.puts(inspect(get()[2]))\n'
 '    IO.puts(inspect([1, 2, 3][1]))\n'
 '    IO.puts(inspect(%{1 => "one"}[1]))\n'
 '    IO.puts(inspect({5, 6}[1]))\n'
 '    fs = [fn x -> x + 1 end, fn x -> x * 2 end]\n'
 '    IO.puts(inspect(fs[1](5)) <> inspect(fs[0].(5)))\n'
 '    IO.puts(inspect(-l[0]) <> inspect(l[0] * l[1]) <> inspect(l[0] == 10) <> inspect(not (l[0] == 10)))\n'
 '    bm = %{true => "t"}\n'
 '    IO.puts(bm[true])\n'
 '    s = ["a", "b"]\n'
 '    IO.puts(s[0] <> s[1] <> "#{s[1]}")\n'
 '    IO.puts(inspect(Enum.map([0, 1], fn k -> l[k] end)))\n'
 '    bs = [%Box{items: [1], names: %{}}]\n'
 '    IO.puts(inspect(bs[0].items[0]))\n'
 '    IO.puts(inspect((l)[1]))\n'
 '    IO.puts(inspect(elem(pair, 1)[0]))\n'
 '    IO.puts(inspect(l[0] |> Integer.to_string()))\n'
 '    IO.puts(inspect(hd(l)[0]))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\n    p = {1, 2}\n    IO.puts(inspect(p[2]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    p = {1, 2}\n    i = 0\n    IO.puts(inspect(p[i]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect("abc"[0]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    m = %{"a" => 1}\n    IO.puts(inspect(m[1]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    l = [1]\n    IO.puts(inspect(l["a"]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    l = [1, 2]\n    x = l\n    [0]\n    IO.puts(inspect(x))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect((1..3)[0]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect([][0]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    m = %{"a" => none}\n    x: option[integer] = m["a"]\n    IO.puts(inspect(x))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    m = %{{1, 2} => "t", {3, 4} => "u"}\n'
 '    IO.puts(m[{3, 4}])\n'
 '    o = %{[1] => 5}\n'
 '    IO.puts(inspect(o[[1]]))\n'
 '    e: map[string, integer] = %{}\n'
 '    IO.puts(inspect(e["x"]))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    l = [1, 2, 3]\n'
 '    r = case l do\n'
 '      [a | _] -> a [9]\n'
 '      _ -> 0\n'
 '    end\n'
 '    IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\n    l = [1, 2, 3]\n    IO.puts(inspect(l[0][1]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    l = [1, 2, 3]\n    IO.puts(inspect(l[true]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    l = [1, 2, 3]\n    IO.puts(inspect(l [1] ++ [l[2]]))\n    IO.puts(inspect(Enum.at(l, 1)[0]))\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    l = [[1], [2]]\n'
 '    z = case 1 do\n'
 '      2 -> l [_] -> [5]\n'
 '      _ -> [6]\n'
 '    end\n'
 '    IO.puts(inspect(z))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    flags = [false, true]\n'
 '    x = cond do\n'
 '      false -> flags [1] -> 5\n'
 '      true -> 3\n'
 '    end\n'
 '    IO.puts(inspect(x))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def h(l: list[t]): t do\n'
 '    l[0]\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(inspect(h(["z"])))\n'
 '    l = [1, 2, 3]\n'
 '    IO.puts(inspect(l[1] ++ [l[2]]))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\n    1 = "a"\n  end\nend\n',
 'defmodule M do\n  def main() do\n    x = 5\n    true = x\n  end\nend\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    f = fn n ->\n'
 '      1 = n\n'
 '      :one\n'
 '    end\n'
 '    IO.puts(inspect(f.(1)))\n'
 '    case 2 do\n'
 '      n ->\n'
 '        2 = n\n'
 '        IO.puts("two")\n'
 '    end\n'
 '    if true do\n'
 '      "a" = "a"\n'
 '      IO.puts("a")\n'
 '    end\n'
 '    IO.puts(inspect(f.(3)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\n    x = 1\n    1 = x; IO.puts("z")\n  end\nend\n',
 'defmodule M do\n  def main() do\n    1 == 1\n    IO.puts("z")\n  end\nend\n',
 'defmodule M do\n  def g(): integer do\n    3 = 3\n  end\n  def main() do\n    IO.puts(inspect(g()))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    "a#{1}" = "a1"\n    IO.puts("i")\n  end\nend\n',
 'defmodule M do\n  def main() do\n    1 + 1 = 2\n    IO.puts("i")\n  end\nend\n',
 'defmodule M do\n'
 '  def apply1(f: fn[list[integer], list[integer]], l: list[integer]): list[integer] do f(l) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(Enum.map([[1, 1, 2], [3, 3]], &Enum.dedup/1)))\n'
 '    IO.puts(inspect(Enum.map([:a, :b], &Atom.to_string/1)))\n'
 '    IO.puts(inspect(Enum.map(["a", "bcd"], &String.length/1)))\n'
 '    IO.puts(inspect(apply1(&Enum.reverse/1, [1, 2, 3])))\n'
 '    IO.puts(inspect(apply1(&Enum.dedup/1, [1, 1, 2])))\n'
 '    f: fn[list[integer], list[integer]] = &Enum.uniq/1\n'
 '    IO.puts(inspect(f.([1, 2, 1])))\n'
 '    g: fn[list[string], string, string] = &Enum.join/2\n'
 '    IO.puts(g.(["a", "b"], "-"))\n'
 '    IO.puts(inspect(Enum.map([[3, 1], [2]], &Enum.sort/1)))\n'
 '    IO.puts(inspect(Enum.map([["b", "a"], ["c"]], &Enum.sort/1)))\n'
 '    IO.puts(inspect(Enum.map([1, 2], &Integer.to_string/1)))\n'
 '    IO.puts(inspect(Enum.map(["a b", "c"], &String.split/1)))\n'
 '    IO.puts(inspect(Enum.reduce([1, 2, 3], 0, &Kernel.max/2)))\n'
 '    IO.puts(inspect(Enum.map([[1, 2], [3]], &Enum.sum/1)))\n'
 '    IO.puts(inspect(Enum.map([[1, 2], [3]], &length/1)))\n'
 '    IO.puts(inspect(Enum.map([1, -2], &abs/1)))\n'
 '    IO.puts(inspect(Enum.map([[1, 2], [3]], &List.first/1)))\n'
 '    IO.puts(inspect(Enum.map([[1, 2], [3]], &hd/1)))\n'
 '    IO.puts(inspect(Enum.map(["x", "y"], &String.upcase/1)))\n'
 '    IO.puts(inspect(Enum.map([%{1 => 2}], &Map.keys/1)))\n'
 '    IO.puts(inspect(Enum.filter([[1], []], &Enum.empty?/1)))\n'
 '    IO.puts(inspect(Enum.map([[1, 2], [3, 4]], &Enum.reverse/1) |> Enum.map(&List.last/1)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect(Enum.map([[1, 1]], &Enum.dedup/2)))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect(Enum.map([[1, 1]], &Enum.nothing/1)))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    f = &Enum.dedup/1\n    IO.puts(inspect(f.([1, 1])))\n  end\nend\n',
 'defmodule M do\n'
 '  def gen(items: list[list[t]]): list[list[t]] do\n'
 '    Enum.map(items, &Enum.dedup/1)\n'
 '  end\n'
 '  def twice(f: fn[string, string], s: string): string do f(f(s)) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(gen([["a", "a", "b"]])))\n'
 '    IO.puts(inspect(Enum.map([[1]], &some/1)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def gen(items: list[list[t]]): list[list[t]] do\n'
 '    Enum.map(items, &Enum.dedup/1)\n'
 '  end\n'
 '  def twice(f: fn[string, string], s: string): string do f(f(s)) end\n'
 '  def pair(f: fn[integer, integer, integer]): integer do f(3, 4) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(gen([["a", "a", "b"]])))\n'
 '    IO.puts(twice(&String.capitalize/1, "abc"))\n'
 '    IO.puts(twice(&String.trim/1, "  abc "))\n'
 '    IO.puts(inspect(pair(&max/2)) <> inspect(pair(&Integer.gcd/2)) <> inspect(pair(&Bitwise.bor/2)))\n'
 '    IO.puts(inspect(Enum.map([[1, 2], [3]], &tl/1)))\n'
 '    IO.puts(inspect(Enum.map([1, 2], &then(&1, fn x -> x + 1 end))))\n'
 '    fs = [&String.upcase/1, &String.reverse/1]\n'
 '    IO.puts(inspect(Enum.map(fs, fn f -> f.("ab") end)))\n'
 '    IO.puts(inspect(Enum.map([[1, 2, 3]], &Enum.reverse/1)))\n'
 '    IO.puts(inspect(Enum.map(["a", "b"], &String.duplicate(&1, 2))))\n'
 '    IO.puts(inspect([1, 2, 3] |> Enum.map(&Integer.to_string/1) |> Enum.map(&String.to_integer/1)))\n'
 '    IO.puts(inspect(Enum.map([{1, "a"}], &inspect/1)))\n'
 '    IO.puts(inspect(Enum.map([%{"a" => 1}], &Map.values/1)))\n'
 '    IO.puts(inspect(Enum.map([[1, 2]], &Enum.member?(&1, 2))))\n'
 '    IO.puts(inspect(Enum.reduce([[1], [2]], [], &Enum.concat/2)))\n'
 '    IO.puts(inspect(Enum.map([[1, 2]], &List.wrap/1)))\n'
 '    IO.puts(inspect(Enum.map(["a/b"], &Path.dirname/1)))\n'
 '    IO.puts(inspect(Enum.map([3], &Range.new(1, &1))))\n'
 '    IO.puts(inspect(Enum.map([:a], &Atom.to_string/1) |> Enum.map(&String.to_atom/1)))\n'
 '    IO.puts(inspect(Enum.map([[{:a, 1}]], &Keyword.keys/1)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect(Enum.map([[1]], &concat/2)))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect(Enum.map([1, 2], &tap/2)))\n  end\nend\n',
 'defmodule T do\n'
 '  def by(items: list[a], f: fn[a, b], s: fn[b, b, boolean]): boolean do\n'
 '    s(f(hd(items)), f(hd(items)))\n'
 '  end\n'
 '  def chain(x: a, f: fn[a, b], g: fn[b, c], h: fn[c, d]): d do h(g(f(x))) end\n'
 '  def rev(s: fn[b, b, boolean], items: list[a], f: fn[a, b]): boolean do\n'
 '    s(f(hd(items)), f(hd(items)))\n'
 '  end\n'
 '  def two(f: fn[a, b], x: a, g: fn[b, a]): a do g(f(x)) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(by(["bb"], fn a -> String.length(a) end, fn a, b -> a >= b end)))\n'
 '    IO.puts(inspect(by([1], &Integer.to_string/1, fn a, b -> a == b end)))\n'
 '    IO.puts(inspect(by([1], &(&1 + 1), &(&1 > &2))))\n'
 '    IO.puts(inspect(chain(1, fn x -> x + 1 end, fn y -> Integer.to_string(y) end, fn z -> z <> "!" end)))\n'
 '    IO.puts(inspect(chain("a", &String.length/1, &(&1 * 2), fn z -> [z] end)))\n'
 '    IO.puts(inspect(Enum.sort_by(["bb", "a"], fn s -> String.length(s) end, fn x, y -> x >= y end)))\n'
 '    IO.puts(inspect(Enum.sort_by(["bb", "a", "ccc"], &String.length/1, &(&1 >= &2))))\n'
 '    IO.puts(inspect(Enum.min_by(["bb", "a"], fn s -> String.length(s) end, fn x, y -> x <= y end)))\n'
 '    IO.puts(inspect(two(fn x -> [x] end, 5, fn l -> hd(l) + 1 end)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def rev(s: fn[b, b, boolean], items: list[a], f: fn[a, b]): boolean do\n'
 '    s(f(hd(items)), f(hd(items)))\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(inspect(rev(fn a, b -> a >= b end, ["bb"], fn a -> String.length(a) end)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def two(f: fn[a, b], g: fn[b, a], x: a): a do g(f(x)) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(two(fn x -> [x] end, fn l -> hd(l) + 1 end, 5)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def k(f: fn[a, b], g: fn[b, c]): integer do 1 end\n'
 '  def main() do\n'
 '    IO.puts(inspect(k(fn x -> x end, fn y -> y end)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def by(items: list[a], f: fn[a, b], s: fn[b, b, boolean]): boolean do\n'
 '    s(f(hd(items)), f(hd(items)))\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(inspect(by(["bb"], fn a -> String.length(a) end, fn a, b -> a <> b == "x" end)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def id2(x: a, f: fn[a, b]): b do f(x) end\n'
 '  def id3(x: a, f: fn[a, integer]): integer do f(x) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(id2(1, &Integer.to_string/1)))\n'
 '    IO.puts(inspect(id3("ab", &String.length/1)))\n'
 '    IO.puts(inspect(id2(1, &Integer.to_string(&1))))\n'
 '    y: string = id2(1, &Integer.to_string/1)\n'
 '    IO.puts(y)\n'
 '    IO.puts(inspect(id2([1, 1], &Enum.dedup/1)))\n'
 '    z: list[integer] = id2([1, 1], &Enum.dedup/1)\n'
 '    IO.puts(inspect(z))\n'
 '    IO.puts(inspect(id3([1, 1], &Enum.count/1)))\n'
 '    IO.puts(inspect(id3([1, 1], &Enum.sum/1)))\n'
 '    IO.puts(inspect(id3([1, 1], &hd/1)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def say(x: integer): integer do\n'
 '    IO.puts("say " <> inspect(x))\n'
 '    x\n'
 '  end\n'
 '  def mix(a: integer, f: fn[t, u], b: t, g: fn[u, v], c: integer, h: fn[v, u, w]): w do\n'
 '    IO.puts(inspect(a + c))\n'
 '    h(g(f(b)), f(b))\n'
 '  end\n'
 '  def pipe3(x: a, f: fn[a, b], g: fn[b, c]): c do g(f(x)) end\n'
 '  def main() do\n'
 '    k = 10\n'
 '    r = mix(say(1), fn s -> String.length(s) + k end, "abc", fn n -> [n, k] end, say(2), fn l, n -> {l, n, k} end)\n'
 '    IO.puts(inspect(r))\n'
 '    IO.puts(inspect(pipe3(3, fn x -> x * k end, fn y -> pipe3(y, fn z -> z + 1 end, fn w -> Integer.to_string(w) end) end)))\n'
 '    IO.puts(inspect(Enum.sort_by(["bb", "a", "ccc"], fn s -> String.length(s) end, fn x, y -> x >= y end)))\n'
 '    IO.puts(inspect(Enum.sort_by([{2, "b"}, {1, "a"}], fn t -> elem(t, 0) end, fn x, y -> x <= y end)))\n'
 '    IO.puts(inspect(Enum.min_by(["bb", "a"], fn s -> String.length(s) end, fn x, y -> x <= y end)))\n'
 '    IO.puts(inspect(Enum.max_by(["bb", "a"], fn s -> String.length(s) end, fn x, y -> x >= y end)))\n'
 '    q: list[string] = pipe3([1, 2], fn l -> Enum.map(l, fn e -> e + k end) end, fn m -> Enum.map(m, &Integer.to_string/1) end)\n'
 '    IO.puts(inspect(q))\n'
 '    3 |> pipe3(fn x -> [x] end, fn l -> l ++ l end) |> inspect() |> IO.puts()\n'
 '    IO.puts(inspect(pipe3("s", &(&1 <> "!"), &String.length(&1))))\n'
 '    IO.puts(inspect(pipe3(some(1), fn o -> o end, fn o ->\n'
 '      case o do\n'
 '        some(v) -> v\n'
 '        none -> 0\n'
 '      end\n'
 '    end)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def pipe3(x: a, f: fn[a, b], g: fn[b, c]): c do g(f(x)) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(pipe3(1, fn x -> none end, fn o -> 1 end)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def pipe3(x: a, f: fn[a, b], g: fn[b, c]): c do g(f(x)) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(pipe3(1, fn x -> [] end, fn o -> length(o) end)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def pipe3(x: a, f: fn[a, b], g: fn[b, c]): c do g(f(x)) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(pipe3(1, fn x -> x end, fn o -> o <> "a" end)))\n'
 '  end\n'
 'end\n',
 'defmodule T do\n'
 '  def by(items: list[a], f: fn[a, b], s: fn[b, b, boolean]): boolean do\n'
 '    s(f(hd(items)), f(hd(items)))\n'
 '  end\n'
 '  def chain(x: a, f: fn[a, b], g: fn[b, c], h: fn[c, d]): d do h(g(f(x))) end\n'
 '  def rev(s: fn[b, b, boolean], items: list[a], f: fn[a, b]): boolean do\n'
 '    s(f(hd(items)), f(hd(items)))\n'
 '  end\n'
 '  def two(f: fn[a, b], x: a, g: fn[b, a]): a do g(f(x)) end\n'
 '  def main() do\n'
 '    IO.puts(inspect(by(["bb"], fn a -> String.length(a) end, fn a, b -> a >= b end)))\n'
 '    IO.puts(inspect(by([1], &(&1 + 1), &(&1 > &2))))\n'
 '    IO.puts(inspect(chain(1, fn x -> x + 1 end, fn y -> Integer.to_string(y) end, fn z -> z <> "!" end)))\n'
 '    IO.puts(inspect(Enum.sort_by(["bb", "a"], fn s -> String.length(s) end, fn x, y -> x >= y end)))\n'
 '    IO.puts(inspect(Enum.sort_by(["bb", "a", "ccc"], &String.length/1, &(&1 >= &2))))\n'
 '    IO.puts(inspect(Enum.min_by(["bb", "a"], fn s -> String.length(s) end, fn x, y -> x <= y end)))\n'
 '    IO.puts(inspect(two(fn x -> [x] end, 5, fn l -> hd(l) + 1 end)))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n  def main() do\n    t = {1, 2}\n    IO.puts(inspect(t[1 - 1]))\n  end\nend\n',
 'defmodule M do\n  @two 1 + 1\n  def main() do\n    t = {1, 2, 3}\n    IO.puts(inspect(t[@two]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    t = {1, 2, 3}\n    IO.puts(inspect(t[-1]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    t = {1, 2, 3}\n    IO.puts(inspect(t[3]))\n  end\nend\n',
 'defmodule M do\n  def main() do\n    Enum.each(["a"], &IO.puts/1)\n  end\nend\n',
 'defmodule M do\n  def main() do\n    IO.puts(inspect(Enum.map([1], &IO.ANSI.nothing/1)))\n  end\nend\n',
 'defmodule M do\n  @v 1..3\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v 1 in [1]\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v some(1)\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v rem(5, 2)\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v 5 |> div(2)\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v if true do 1 else 2 end\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v &(&1 + 1)\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v String.length("a")\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v "#{1}"\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v abs(-1)\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v [1, 2][0]\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v {1, 2}[0]\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v %{1 => 2}[1]\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v ~s(a#{1})\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @v ~w(#{1} b)\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @doc "x #{1}"\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @moduledoc "x #{1}"\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @doc 5\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n  @doc "a" <> "b"\n  def main() do\n    IO.puts("k")\n  end\nend\n',
 'defmodule M do\n'
 '  def deep(m: map[string, list[integer]], k: string, i: integer): integer do\n'
 '    m[k][i]\n'
 '  end\n'
 '  def main() do\n'
 '    m = %{"a" => [1, 2, 3], "b" => []}\n'
 '    f = fn k -> deep(m, k, 0) end\n'
 '    IO.puts(inspect(f.("a")))\n'
 '    IO.puts(inspect(f.("zz")))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    xs = [[1], [2]]\n'
 '    v = case xs do [] -> xs [[1] | _] -> xs [0] _ -> [9] end\n'
 '    IO.puts(inspect(v))\n'
 '    r = case 1 do\n'
 '      1 -> xs [0]\n'
 '      _ -> [5]\n'
 '    end\n'
 '    IO.puts(inspect(r))\n'
 '  end\n'
 'end\n',
 'defmodule M do\n'
 '  def main() do\n'
 '    flags = [false, true]\n'
 '    x = cond do\n'
 '      false -> flags [1] -> 5\n'
 '      true -> 3\n'
 '    end\n'
 '    IO.puts(inspect(x))\n'
 '  end\n'
 'end\n',
 '#alchem-bundle 2\n'
 '# 192 /work/main2.alc\n'
 '# 281 /work/sig.alc\n'
 'defmodule Main do import "module:Sig"\n'
 '\n'
 '  def sigil_q(text: string, mods: string): string do\n'
 '    "main:" <> text\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(~q(hi)ab)\n'
 '    IO.puts(Sig.use_it())\n'
 '  end\n'
 'end\n'
 'defmodule Sig do\n'
 '  def sigil_q(text: string, mods: string): string do\n'
 '    "<" <> text <> ":" <> mods <> ">"\n'
 '  end\n'
 '  def use_it(): string do\n'
 '    ~q(inner)\n'
 '  end\n'
 '  defp sigil_k(text: string, mods: string): string do\n'
 '    "k" <> text\n'
 '  end\n'
 '  def use_k(): string do\n'
 '    ~k(x)\n'
 '  end\n'
 'end\n',
 '#alchem-bundle 3\n'
 '# 107 /work/main4.alc\n'
 '# 281 /work/sig.alc\n'
 '# 97 /work/sig2.alc\n'
 'defmodule Main do import "module:Sig" import "module:Sig2"\n'
 '\n'
 '\n'
 '  def main() do\n'
 '    IO.puts(~q(hi))\n'
 '  end\n'
 'end\n'
 'defmodule Sig do\n'
 '  def sigil_q(text: string, mods: string): string do\n'
 '    "<" <> text <> ":" <> mods <> ">"\n'
 '  end\n'
 '  def use_it(): string do\n'
 '    ~q(inner)\n'
 '  end\n'
 '  defp sigil_k(text: string, mods: string): string do\n'
 '    "k" <> text\n'
 '  end\n'
 '  def use_k(): string do\n'
 '    ~k(x)\n'
 '  end\n'
 'end\n'
 'defmodule Sig2 do\n'
 '  def sigil_q(text: string, mods: string): string do\n'
 '    "2" <> text\n'
 '  end\n'
 'end\n',
 '#alchem-bundle 2\n'
 '# 167 /work/main6.alc\n'
 '# 97 /work/sig2.alc\n'
 'defmodule Main do import "module:Sig2"\n'
 '\n'
 '  def sigil_q(text: string, mods: string): string do\n'
 '    "main:" <> text\n'
 '  end\n'
 '  def main() do\n'
 '    IO.puts(~q(hi)ab)\n'
 '  end\n'
 'end\n'
 'defmodule Sig2 do\n'
 '  def sigil_q(text: string, mods: string): string do\n'
 '    "2" <> text\n'
 '  end\n'
 'end\n']


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-sigils-') as d:
        out=Path(d)/'out'
        for source,status,stdout,stderr in RUNS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
            out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,stderr),(source,run)
        for source in REJECTS:
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(source,result.returncode)
    print(f'PASS sigils: {len(RUNS)} programs run as the pinned compiler runs them, {len(REJECTS)} rejected; text sigils and sigils of the program, value[index], literal and pinned patterns in bindings, the values of module constants, references to library functions written in Alchem, lambdas typed by an earlier lambda, tuples past fifteen fields')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
