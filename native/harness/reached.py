#!/usr/bin/env python3
"""What the compiler has that no other gate reached (scripts/compiler-reach.py
--gates, .github/workflows/reach.yml): the report of every gate's programs,
compiled for every system, listed these functions as never run. Each
program here runs one of them, and prints what the pinned command prints
for it.

PROGRAMS: (what it reaches, its files, status, standard output, standard
error). The entry is app.alc. REFUSED: programs the compiler refuses, as
the pinned command does."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('alchem_bundle', ROOT / 'scripts/bundle-alchem.py')
bundler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundler)

PROGRAMS = [('a module the program declares with the name of one of the library that is going (ny_masked, ny_declared)',
  {'app.alc': 'defmodule App do\n'
              '  import "version.alc"\n'
              '  import "option_parser.alc"\n'
              '\n'
              '  def main() do\n'
              '    IO.puts(Version.show(2))\n'
              '    IO.puts(Integer.to_string(OptionParser.twice(4)))\n'
              '  end\n'
              'end\n',
   'option_parser.alc': 'defmodule OptionParser do\n  def twice(n: integer): integer do\n    n * 2\n  end\nend\n',
   'version.alc': 'defmodule Version do\n  def show(n: integer): string do\n    "v" <> Integer.to_string(n)\n  end\nend\n'},
  0,
  b'v2\n8\n',
  b''),
 ('JSON.decode_as at the end of a pipe takes its type from the binding, the function and the fn it is the value of (jn_annotated)',
  {'app.alc': 'defmodule M do\n'
              '  struct Point do\n'
              '    x: integer\n'
              '    y: integer\n'
              '  end\n'
              '  def read(text: string): result[Point, string] do\n'
              '    text |> String.trim() |> JSON.decode_as()\n'
              '  end\n'
              '  def main() do\n'
              '    v: result[map[string, integer], string] = "{\\"a\\":1}" |> String.trim() |> JSON.decode_as()\n'
              '    IO.inspect(v)\n'
              '    IO.inspect(read(" {\\"x\\":1,\\"y\\":2} "))\n'
              '    f = fn(t: string): result[Point, string] do t |> JSON.decode_as() end\n'
              '    IO.inspect(f.("{\\"x\\":3,\\"y\\":4}"))\n'
              '  end\n'
              'end\n'},
  0,
  b'ok(%{"a" => 1})\nok(%Point{x: 1, y: 2})\nok(%Point{x: 3, y: 4})\n',
  b''),
 ('a fn that is the value of a key takes its types from the list it is in (nf_valued)',
  {'app.alc': 'defmodule M do\n'
              '  def main() do\n'
              '    hs: list[tuple[atom, fn[integer, integer]]] = [double: fn x -> x * 2 end, inc: fn x -> x + 1 end]\n'
              '    IO.inspect(Enum.map(hs, fn {name, f} -> {name, f(20)} end))\n'
              '  end\n'
              'end\n'},
  0,
  b'[double: 40, inc: 21]\n',
  b''),
 ('a struct made of the one a function was given, its strings going on in it, in a call of the function to itself and in a reduce (gm_update, gm_again)',
  {'app.alc': 'defmodule M do\n'
              '  struct Acc do\n'
              '    text: string\n'
              '    count: integer\n'
              '  end\n'
              '  def grow(acc: Acc, n: integer): Acc do\n'
              '    if n == 0 do acc else grow(%Acc{acc | text: acc.text <> "x", count: acc.count + 1}, n - 1) end\n'
              '  end\n'
              '  def main() do\n'
              '    a = grow(%Acc{text: "", count: 0}, 5)\n'
              '    IO.puts(a.text <> Integer.to_string(a.count))\n'
              '    b = Enum.reduce([1, 2, 3], %Acc{text: "", count: 0}, fn i, acc -> %Acc{acc | text: acc.text <> Integer.to_string(i), count: acc.count + i} '
              'end)\n'
              '    IO.puts(b.text <> Integer.to_string(b.count))\n'
              '  end\n'
              'end\n'},
  0,
  b'xxxxx5\n1236\n',
  b''),
 ('the same, a field made of another field of the struct',
  {'app.alc': 'defmodule M do\n'
              '  struct Acc do\n'
              '    text: string\n'
              '    more: string\n'
              '  end\n'
              '  def grow(acc: Acc, n: integer): Acc do\n'
              '    if n == 0 do acc else grow(%Acc{acc | text: acc.text <> "x", more: acc.more <> acc.text}, n - 1) end\n'
              '  end\n'
              '  def main() do\n'
              '    a = grow(%Acc{text: "", more: ""}, 4)\n'
              '    IO.puts(a.text <> "/" <> a.more)\n'
              '    b = Enum.reduce([1, 2, 3], %Acc{text: "", more: ""}, fn i, acc -> %Acc{acc | text: acc.text <> "a", more: acc.more <> acc.text} end)\n'
              '    IO.puts(b.text <> "/" <> b.more)\n'
              '  end\n'
              'end\n'},
  0,
  b'xxxx/xxxxxx\naaa/aaa\n',
  b''),
 ('a time written with an offset that puts it on the day before or after (sg_before, sg_after)',
  {'app.alc': 'defmodule M do\n'
              '  def main() do\n'
              '    IO.inspect(~U[2024-03-01 00:30:00+02:00])\n'
              '    IO.inspect(~U[2023-12-31 23:30:00-02:00])\n'
              '    IO.inspect(~U[2024-01-01 00:10:00+05:30])\n'
              '    IO.inspect(~U[2024-12-31 22:00:00-03:00])\n'
              '    IO.inspect(~U[2023-03-01 01:00:00+03:00])\n'
              '  end\n'
              'end\n'},
  0,
  b'~U[2024-02-29T22:30:00Z]\n~U[2024-01-01T01:30:00Z]\n~U[2023-12-31T18:40:00Z]\n~U[2025-01-01T01:00:00Z]\n~U[2023-02-28T22:00:00Z]\n',
  b''),
 ('a reference to a library function of floats where nothing says its types (nf_simple_words)',
  {'app.alc': 'defmodule M do\n'
              '  def main() do\n'
              '    IO.inspect(Enum.map([1.5, 2.5], &Float.round/1))\n'
              '    g = &Float.from_integer/1\n'
              '    IO.inspect(g(2))\n'
              '    xs = [&Float.floor/1, &Float.ceil/1]\n'
              '    IO.inspect(Enum.map(xs, fn f -> f(2.5) end))\n'
              '  end\n'
              'end\n'},
  0,
  b'[2.0, 3.0]\n2.0\n[2.0, 3.0]\n',
  b''),
 ('Binary: to_list, from_list, at, encode and decode, and their failures',
  {'app.alc': 'defmodule M do\n'
              '  def main() do\n'
              '    IO.inspect(Binary.to_list("hi"))\n'
              '    IO.inspect(Binary.from_list([104, 105]))\n'
              '    IO.inspect(byte_size(Binary.from_list([0, 255])))\n'
              '    IO.inspect(Binary.at("abc", 1))\n'
              '    IO.inspect(Binary.to_list(Binary.encode(258, 2, :big)))\n'
              '    IO.inspect(Binary.to_list(Binary.encode(258, 4, :little)))\n'
              '    IO.inspect(Binary.to_list(Binary.encode(-1, 8, :big)))\n'
              '    IO.inspect(Binary.to_list(Binary.encode(7, 1, :big)))\n'
              '    IO.inspect(Binary.decode(Binary.from_list([9, 1, 2]), 1, 2, :big))\n'
              '    IO.inspect(Binary.decode(Binary.from_list([1, 2]), 0, 2, :little))\n'
              '    IO.inspect(Binary.decode(Binary.encode(-5, 8, :little), 0, 8, :little))\n'
              '    IO.puts(try do\n'
              '      Integer.to_string(Binary.at("abc", 3))\n'
              '    rescue\n'
              '      m -> m\n'
              '    end)\n'
              '    IO.puts(try do\n'
              '      Binary.from_list([256])\n'
              '    rescue\n'
              '      m -> m\n'
              '    end)\n'
              '    IO.puts(try do\n'
              '      Binary.encode(256, 1, :big)\n'
              '    rescue\n'
              '      m -> m\n'
              '    end)\n'
              '    IO.puts(try do\n'
              '      Integer.to_string(Binary.decode("ab", 1, 2, :big))\n'
              '    rescue\n'
              '      m -> m\n'
              '    end)\n'
              '  end\n'
              'end\n'},
  0,
  b'[104, 105]\n"hi"\n2\n98\n[1, 2]\n[2, 1, 0, 0]\n[255, 255, 255, 255, 255, 255, 255, 255]\n[7]\n258\n513\n-5\nBinary.at: the position is outside the stri'
  b'ng\nBinary.from_list: a byte is a number from 0 to 255\nBinary.encode: the number does not fit in the size\nBinary.decode: the bytes are outside the string'
  b'\n',
  b''),
 ('Duration: add, multiply and subtract',
  {'app.alc': 'defmodule M do\n'
              '  def main() do\n'
              '    IO.puts(Duration.add(Duration.months(1), Duration.days(10)) |> Duration.to_iso8601())\n'
              '    IO.inspect(Duration.multiply(Duration.hours(2), 3).hour)\n'
              '    IO.inspect(Duration.subtract(Duration.days(10), Duration.days(3)).day)\n'
              '    IO.puts(Duration.to_iso8601(Duration.subtract(Duration.add(Duration.hours(5), Duration.minutes(90)), '
              'Duration.multiply(Duration.minutes(20), 2))))\n'
              '  end\n'
              'end\n'},
  0,
  b'P1M10D\n6\n7\nPT5H50M\n',
  b''),
 ('Function.identity, Keyword.update with a default, URI.merge of a string and of a URI, Date.utc_today and NaiveDateTime.utc_now',
  {'app.alc': 'defmodule M do\n'
              '  def main() do\n'
              '    IO.inspect(Enum.map([1, 2], &Function.identity(&1)))\n'
              '    IO.puts(Function.identity("same"))\n'
              '    IO.inspect(Keyword.update([a: 1], :a, 0, &(&1 + 1)))\n'
              '    IO.inspect(Keyword.update([a: 1], :b, 0, &(&1 + 1)))\n'
              '    IO.inspect(Keyword.update([a: 1, b: 2, a: 5], :a, 0, fn v -> v * 10 end))\n'
              '    IO.puts(URI.to_string(URI.merge("http://a.com/x/y", "../z?q=1")))\n'
              '    IO.puts(URI.to_string(URI.merge(URI.parse("http://a.com/x/y"), "w")))\n'
              '    IO.puts(URI.to_string(URI.merge("http://a.com/x/y?k=1#f", "//b.org/p")))\n'
              '    IO.puts(URI.to_string(URI.merge("http://a.com/x/y", "#top")))\n'
              '    IO.inspect(Date.after?(Date.utc_today(), ~D[2020-01-01]))\n'
              '    IO.inspect(NaiveDateTime.after?(NaiveDateTime.utc_now(), ~N[2020-01-01 00:00:00]))\n'
              '  end\n'
              'end\n'},
  0,
  b'[1, 2]\nsame\n[a: 2]\n[a: 1, b: 0]\n[a: 10, b: 2, a: 5]\nhttp://a.com/z?q=1\nhttp://a.com/x/w\nhttp://b.org/p\nhttp://a.com/x/y#top\ntrue\ntrue\n',
  b''),
 ('IO.ANSI.cursor and IO.ANSI.format',
  {'app.alc': 'defmodule M do\n'
              '  def main() do\n'
              '    IO.inspect(IO.ANSI.cursor(2, 5))\n'
              '    IO.inspect(IO.ANSI.format([red: "", text: "alert"], false))\n'
              '    IO.inspect(IO.ANSI.format([bright: "", text: "x"], true))\n'
              '    IO.inspect(IO.ANSI.format([text: "a", red: "", text: "b", reset: "", text: "c"], true))\n'
              '  end\n'
              'end\n'},
  0,
  b'"\\x1b[2;5H"\n"alert"\n"\\x1b[1mx\\x1b[0m"\n"a\\x1b[31mb\\x1b[0mc\\x1b[0m"\n',
  b''),
 ('File.sync of a path, of a directory, of a file that is not there and of an open file',
  {'app.alc': 'defmodule M do\n'
              '  def main() do\n'
              '    File.write!("reached_sync.txt", "kept")\n'
              '    IO.inspect(File.sync("reached_sync.txt"))\n'
              '    IO.inspect(File.sync("."))\n'
              '    IO.inspect(File.sync("reached_none.txt"))\n'
              '    ok(f) = File.open("reached_sync.txt", [:append])\n'
              '    IO.inspect(File.sync(f))\n'
              '    IO.inspect(File.close(f))\n'
              '    File.rm!("reached_sync.txt")\n'
              '  end\n'
              'end\n'},
  0,
  b'ok({})\nok({})\nerror("open reached_none.txt: no such file or directory")\nok({})\ntrue\n',
  b'')]

# A statement that does not compile in a block of more than ninety
# bindings is compiled once more with every binding in reach before the
# block is refused (ev_again, ev_whole, spec/source-capacity.md): a fn whose
# parameter has no type from anywhere, which the pinned command refuses
# with "cannot infer the parameter types of this function here".
REFUSED = [('a fn of no types after 130 bindings', 'defmodule M do\n  def main() do\n' + ''.join(f'    x{i} = {i}\n' for i in range(130)) + '    f = fn a -> a + x1 end\n    IO.puts(Integer.to_string(x2))\n  end\nend\n')]


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-reached-') as top:
        for index, (what, files, status, stdout, stderr) in enumerate(PROGRAMS):
            place = Path(top) / f'p{index}'
            place.mkdir()
            for name, text in files.items():
                (place / name).write_text(text)
            built = subprocess.run([str(compiler)], input=bundler.bundle(place / 'app.alc'), capture_output=True, env={'PATH': ''}, timeout=300)
            assert (built.returncode, built.stderr) == (0, b''), (what, built.returncode, built.stderr[:200])
            program = place / 'app'
            program.write_bytes(built.stdout)
            program.chmod(0o700)
            run = subprocess.run([str(program)], capture_output=True, stdin=subprocess.DEVNULL, cwd=place, env={'PATH': ''}, timeout=120)
            seen = (run.returncode, run.stdout, run.stderr.replace(str(place).encode() + b'/', b''))
            assert seen == (status, stdout, stderr), (what, seen, (status, stdout, stderr))
        for what, text in REFUSED:
            built = subprocess.run([str(compiler)], input=text.encode(), capture_output=True, env={'PATH': ''}, timeout=300)
            assert (built.returncode, built.stdout) == (65, b''), (what, built.returncode)
    print(f'PASS reached: {len(PROGRAMS)} programs of what no other gate reached, as the pinned command runs them; {len(REFUSED)} refused')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
