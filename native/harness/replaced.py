#!/usr/bin/env python3
"""A program's module that takes the place of a library module (issue #129).

The pinned language lets a program have a module named DiskStore, WebSocket,
Version or OptionParser (RetiringModule): its functions are the ones the
program's calls reach, its types take the place of the library's, and the
type of its own name is written by that name in every module. Each program
here is run by `alchem run main.alc`, and gives the status, the output and
the message the pinned command gives (harness/replaced-cases.json).

The library's own modules are appended to a program under names a program
cannot have (nc_ours), so a program's module of any name beginning with
Alchem is the program's: the last program has one named as the library's
module of types was (issue #102).

    replaced.py --record PINNED   write replaced-cases.json from the pinned command line
"""
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'harness/replaced-cases.json'

PROGRAMS = [
    ('a module of its own name with main', {
        'main.alc': 'defmodule Version do\n  def match?(a: string, b: string): string do\n    "mine #{a} #{b}"\n  end\n\n  def main() do\n    IO.puts(Version.match?("1", "2"))\n    IO.puts(match?("3", "4"))\n  end\nend\n',
    }),
    ('types of the module, written from another', {
        'main.alc': 'defmodule Main do\n  import "version.alc"\n\n  def main() do\n    v = Version.parse("1.4")\n    IO.inspect(v)\n    IO.inspect(Version.requirement("~> 1"))\n    IO.inspect(Version.compare(v, Version.parse("1.4")))\n    IO.inspect(v.major + v.minor)\n    w: Version = %Version{major: 2, minor: 0}\n    IO.inspect(Version.compare(v, w))\n    case w do\n      %Version{major: m} -> IO.inspect(m)\n    end\n  end\nend\n',
        'version.alc': 'defmodule Version do\n  struct Version do\n    major: integer\n    minor: integer\n  end\n\n  struct Requirement do\n    text: string\n  end\n\n  def parse(text: string): Version do\n    [a, b] = String.split(text, ".")\n    %Version{major: String.to_integer(a), minor: String.to_integer(b)}\n  end\n\n  def requirement(text: string): Requirement do\n    %Requirement{text: text}\n  end\n\n  def compare(a: Version, b: Version): atom do\n    if a.major == b.major and a.minor == b.minor do :eq else :ne end\n  end\nend\n',
    }),
    ('a sum type and a struct beside the library', {
        'main.alc': 'defmodule Main do\n  import "web_socket.alc"\n\n  def main() do\n    case WebSocket.connect("ws://x") do\n      ok(s) ->\n        IO.puts(WebSocket.describe(WebSocket.next(s)))\n      error(m) -> IO.puts(m)\n    end\n    IO.inspect(WebSocket.connect("http://x"))\n    IO.inspect(URI.parse("http://example.com/a").path)\n  end\nend\n',
        'web_socket.alc': 'defmodule WebSocket do\n  type Event = message(body: string) | closed\n\n  struct WebSocket do\n    id: integer\n  end\n\n  def connect(url: string): result[WebSocket, string] do\n    if String.starts_with?(url, "ws://") do ok(%WebSocket{id: 7}) else error("bad url " <> url) end\n  end\n\n  def next(socket: WebSocket): Event do\n    if socket.id == 7 do message("hello") else closed end\n  end\n\n  def describe(event: Event): string do\n    case event do\n      message(body) -> body\n      closed -> "closed"\n    end\n  end\nend\n',
    }),
    ('a type of the name outside the module', {
        'main.alc': 'defmodule M do\n  struct Version do\n    x: integer\n  end\n\n  def main() do\n    IO.puts("x")\n  end\nend\n',
    }),
    ('one module taken, another left to the library', {
        'main.alc': 'defmodule Main do\n  import "option_parser.alc"\n\n  def main() do\n    IO.inspect(OptionParser.parse(["--a", "--b"]))\n    IO.inspect(Version.match?("1.4.2", "~> 1.4"))\n  end\nend\n',
        'option_parser.alc': 'defmodule OptionParser do\n  def parse(args: list[string]): map[string, string] do\n    Enum.reduce(args, %{}, fn a, acc -> Map.put(acc, a, "yes") end)\n  end\nend\n',
    }),
    ('a struct of the module updated and inspected', {
        'disk_store.alc': 'defmodule DiskStore do\n  struct DiskStore do\n    path: string\n    entries: map[string, string]\n  end\n\n  def open(path: string): result[DiskStore, string] do\n    ok(%DiskStore{path: path, entries: %{}})\n  end\n\n  def put(store: DiskStore, key: string, value: string): DiskStore do\n    %DiskStore{store | entries: Map.put(store.entries, key, value)}\n  end\n\n  def get(store: DiskStore, key: string): option[string] do\n    Map.get(store.entries, key)\n  end\nend\n',
        'main.alc': 'defmodule Main do\n  import "disk_store.alc"\n\n  def main() do\n    case DiskStore.open("x.db") do\n      ok(store) ->\n        next = DiskStore.put(store, "k", "v")\n        IO.inspect(DiskStore.get(next, "k"))\n        IO.inspect(DiskStore.get(next, "z"))\n        IO.inspect(next)\n      error(m) -> IO.puts(m)\n    end\n  end\nend\n',
    }),
    ('a type named after another library module, inside', {
        'main.alc': 'defmodule Version do\n  struct Enum do\n    n: integer\n  end\n\n  def main() do\n    IO.inspect(%Enum{n: 1})\n  end\nend\n',
    }),
    ('a struct named after a library module that is not given up', {
        'main.alc': 'defmodule M do\n  struct Registry do\n    x: integer\n  end\n\n  def main() do\n    IO.puts("x")\n  end\nend\n',
    }),
    ('a module named after a library module that is not given up', {
        'main.alc': 'defmodule HTTP do\n  def main() do\n    IO.puts("x")\n  end\nend\n',
    }),
    ('the name in a comment and a string takes nothing', {
        'main.alc': 'defmodule Main do\n  # defmodule Version do\n  def main() do\n    IO.puts("defmodule Version do")\n    IO.inspect(Version.match?("1.4.2", "~> 1.4"))\n  end\nend\n',
    }),
    ("a module named as the library's own module of types was (issue #102)", {
        'main.alc': 'defmodule M do\n  import "t2.alc"\n\n  def main() do\n    IO.inspect(Date.utc_today().year > 2000)\n    IO.puts(inspect(AlchemTypes.valid?("integer")))\n    IO.inspect(~D[2026-01-05])\n    IO.inspect(AlchemTypes.shape(3))\n    IO.inspect(Enum.map([1, 2], fn x -> x * 2 end))\n  end\nend\n',
        't2.alc': 'defmodule AlchemTypes do\n  struct Shape do\n    n: integer\n  end\n\n  def valid?(t: string): boolean do\n    t == "integer"\n  end\n\n  def shape(n: integer): Shape do\n    %Shape{n: n}\n  end\nend\n',
    }),
    *[(f'what only the library may call, {call}', {
        'main.alc': 'defmodule AlchemX do\n  def main() do\n    IO.inspect(' + call + ')\n  end\nend\n',
    }) for call in ('Sys.call(39, 0, 0, 0, 0, 0, 0)', 'Sys.peek(4194304)', 'HTTP._k()', 'TLS._hex("00")', 'Process._g()')],
]


def run(command, files, pinned=False):
    """[status, output, message] of `command run main.alc` among the files."""
    with tempfile.TemporaryDirectory(prefix='alchem-replaced-') as top:
        root = Path(top).resolve()
        (root / 'home').mkdir()
        for name, text in files.items():
            (root / name).write_text(text)
        env = dict(os.environ, HOME=str(root / 'home')) if pinned else {'PATH': '/usr/bin:/bin', 'HOME': str(root / 'home')}
        done = subprocess.run([str(command), 'run', 'main.alc'], capture_output=True, cwd=root, env=env, timeout=600)
        return [done.returncode] + [text.decode('utf8', 'replace').replace(str(root) + os.sep, '') for text in (done.stdout, done.stderr)]


def record(pinned):
    held = [{'name': name, 'gives': run(pinned, files, True)} for name, files in PROGRAMS]
    CASES.write_text(json.dumps(held, indent=1) + '\n')
    print(f'wrote {CASES.name}: {len(held)} programs, {sum(1 for h in held if h["gives"][0])} refused')


def verify(compiler):
    held = json.loads(CASES.read_text())
    assert [h['name'] for h in held] == [name for name, _ in PROGRAMS], 'harness/replaced-cases.json is not of these programs: run harness/replaced.py --record'
    spec = spec_from_file_location('build_alchem', ROOT / 'scripts/build-alchem.py')
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix='alchem-replaced-') as top:
        alchem = Path(top) / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))
        for (name, files), expected in zip(PROGRAMS, held):
            seen = run(alchem, files)
            assert seen == expected['gives'], (name, seen, expected['gives'])
    print(f'replaced: {len(held)} programs give what the pinned command gives')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--record':
        record(Path(sys.argv[2]).resolve())
    else:
        verify(Path(sys.argv[1]).resolve())
