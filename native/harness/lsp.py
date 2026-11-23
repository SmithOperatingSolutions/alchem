#!/usr/bin/env python3
"""alchem lsp (tools/alchem-lsp.alc) against the pinned command's language
server: recorded sessions, with the same replies.

Each session of SESSIONS is the files of a project and what a client
writes to the server's standard input: messages, framed as the protocol
frames them, and bytes as they are for what no client should send. ROOT
in a file's text or a message stands for the project's directory.
harness/lsp-cases.json holds, for each session, what the pinned server
answers: its status, its standard error and each message it writes, with
the directory as ROOT again.

    lsp.py COMPILER          the gate: alchem, built by COMPILER, answers the same
    lsp.py --record PINNED   write lsp-cases.json from the pinned command line

The sessions are the pinned server's own tests (lsp/server_test.go and
lsp/edges_test.go of the pinned tree) and more of what an editor sends."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).resolve().parent / 'lsp-cases.json'

GREET = 'defmodule Greet do\n  @doc """\n  Greets someone.\n  """\n  def hello(name: string): string do\n    "Hello, " <> name\n  end\n\n  defp hidden(): integer do\n    1\n  end\nend\n'
MAIN = 'defmodule Main do\n  import "lib/greet.alc"\n\n  struct Point do\n    x: integer\n  end\n\n  def twice(n: integer): integer do\n    n * 2\n  end\n\n  def main() do\n    IO.puts(Greet.hello("Ada"))\n    IO.puts(Integer.to_string(twice(2)))\n    Enum.map([1], fn x -> x end)\n  end\nend\n'
BROKEN = 'defmodule Main do\n  import "lib/greet.alc"\n\n  def main() do\n    IO.puts(Greet.hello(1))\n  end\nend\n'
FIXED = 'defmodule Main do\n  import "lib/greet.alc"\n\n  def main() do\n    IO.puts(Greet.hello("ada"))\n    IO.puts(Enum.join(["a"], ","))\n  end\nend\n'
MESSY = 'defmodule Main do\n  def main() do\n    x = (1 + 2)\n    IO.puts(to_string(x))\n  end\nend\n'
EDGES = 'defmodule Edges do\n  struct Point do\n    x: integer\n  end\n\n  defp hidden(n: integer): integer do\n    n\n  end\n\n  def main() do\n    p = %Point{x: hidden(1)}\n    IO.inspect(p)\n  end\nend\n'
TESTS = 'defmodule GreetTest do\n  import "../lib/greet.alc"\n\n  type Shape do\n    circle(r: integer)\n    square(side: integer)\n  end\n\n  setup do\n    1\n  end\n\n  test "greets", n do\n    assert(Greet.hello("a") == "Hello, a")\n  end\n\n  describe "more" do\n    describe "inner" do\n      test "says \\"hi\\"" do\n        assert(1 == 1)\n      end\n    end\n  end\nend\n'
WIDE = 'defmodule Wide do\n  def größe(wörter: list[string]): integer do\n    length(wörter)\n  end\n\n  def main() do\n    IO.puts("höhe: #{größe(["ä", "ö"])}")\n    IO.puts(nöpe)\n  end\nend\n'
TWO = 'defmodule Two do\n  import "lib/greet.alc"\n  import "lib/other.alc"\n\n  def main() do\n    IO.puts(Greet.hello(Other.name()))\n    IO.puts(Other.)\n  end\nend\n'
OTHER = 'defmodule Other do\n  def name(): string do\n    "other"\n  end\n\n  def count(items: list[a]): integer do\n    length(items)\n  end\nend\n'


LATE = 'defmodule Late do\n  def main() do\n    day = ~N[2026-01-05  13:04:05]\n    IO.puts("late")\n  end\nend\n'


def sized(body, header='Content-Length: %d'):
    """A message as its bytes, under a header of its length."""
    return {'body': body, 'header': header}


def uri(path):
    return 'file://ROOT/' + path


def opened(path, text):
    return {'method': 'textDocument/didOpen', 'params': {'textDocument': {'uri': uri(path), 'languageId': 'alchem', 'version': 1, 'text': text}}}


def changed(path, text):
    return {'method': 'textDocument/didChange', 'params': {'textDocument': {'uri': uri(path), 'version': 2}, 'contentChanges': [{'text': text}]}}


def asked(number, method, path, line=None, character=None):
    params = {'textDocument': {'uri': uri(path)}}
    if line is not None:
        params['position'] = {'line': line, 'character': character}
    return {'id': number, 'method': 'textDocument/' + method, 'params': params}


def closing(number):
    return [{'id': number, 'method': 'shutdown'}, {'method': 'exit'}]


def every(path, places, first=10):
    """Hover, definition and completion at each place."""
    out = []
    for k, (line, character) in enumerate(places):
        for j, method in enumerate(('hover', 'definition', 'completion')):
            out.append(asked(first + 3 * k + j, method, path, line, character))
    return out


SESSIONS = [
    ['a program and what it imports', {'lib/greet.alc': GREET, 'main.alc': MAIN}, [
        {'id': 1, 'method': 'initialize', 'params': {'rootUri': 'file://ROOT'}},
        {'method': 'initialized', 'params': {}},
        opened('main.alc', MAIN),
        *every('main.alc', [(12, 18), (13, 30), (14, 10), (0, 0), (2, 0), (12, 9), (12, 99), (99, 0), (7, 8), (3, 10), (13, 12)]),
        asked(2, 'documentSymbol', 'main.alc'),
        asked(3, 'formatting', 'main.alc'),
        changed('main.alc', MAIN.replace('n * 2', 'n <> 2')),
        changed('main.alc', MAIN.replace('def twice', 'def  twice').replace('    n * 2', 'n*2')),
        asked(4, 'formatting', 'main.alc'),
        changed('main.alc', MAIN.replace('def main() do', 'def main( do')),
        asked(5, 'documentSymbol', 'main.alc'),
        asked(6, 'hover', 'main.alc', 12, 18),
        asked(7, 'completion', 'main.alc', 12, 18),
        asked(8, 'formatting', 'main.alc'),
        {'method': 'textDocument/didSave', 'params': {'textDocument': {'uri': uri('main.alc'), 'text': MAIN}}},
        {'id': 9, 'method': 'nope/nothing', 'params': {}},
        {'method': 'textDocument/didClose', 'params': {'textDocument': {'uri': uri('main.alc')}}},
        *closing(99)]],
    ["the pinned server's test", {'lib/greet.alc': GREET, 'main.alc': BROKEN}, [
        {'id': 1, 'method': 'initialize', 'params': {'rootUri': 'file://ROOT'}},
        {'method': 'initialized', 'params': {}},
        opened('main.alc', BROKEN),
        changed('main.alc', FIXED),
        asked(2, 'hover', 'main.alc', 5, 18),
        asked(3, 'hover', 'main.alc', 4, 20),
        asked(4, 'definition', 'main.alc', 4, 20),
        changed('main.alc', FIXED.replace('Enum.join', 'Enum.', 1)),
        asked(5, 'completion', 'main.alc', 5, 17),
        asked(6, 'completion', 'main.alc', 4, 18),
        changed('main.alc', MESSY),
        {'id': 7, 'method': 'textDocument/formatting', 'params': {'textDocument': {'uri': uri('main.alc')}, 'options': {'tabSize': 2}}},
        asked(8, 'documentSymbol', 'main.alc'),
        *closing(9)]],
    ['what editors send less often', {'edges.alc': EDGES}, [
        {'id': 1, 'method': 'initialize', 'params': {'rootUri': 'file://ROOT'}},
        opened('edges.alc', EDGES),
        {'method': 'textDocument/didSave', 'params': {'textDocument': {'uri': uri('edges.alc')}}},
        {'method': 'textDocument/didChange', 'params': {'textDocument': {'uri': uri('edges.alc')}, 'contentChanges': []}},
        asked(2, 'completion', 'edges.alc', 11, 4),
        asked(3, 'hover', 'edges.alc', 4, 0),
        asked(4, 'definition', 'edges.alc', 10, 19),
        asked(5, 'definition', 'edges.alc', 4, 0),
        asked(6, 'documentSymbol', 'edges.alc'),
        asked(7, 'documentSymbol', 'never-opened.alc'),
        asked(8, 'hover', 'never-opened.alc', 0, 0),
        asked(9, 'formatting', 'never-opened.alc'),
        asked(10, 'completion', 'never-opened.alc', 0, 0),
        {'method': 'workspace/somethingNew', 'params': {}},
        {'id': 11, 'method': 'workspace/unknown', 'params': {}},
        {'id': 'a string', 'method': 'textDocument/hover', 'params': {'textDocument': {'uri': uri('edges.alc')}, 'position': {'line': 10, 'character': 19}}},
        {'id': 12, 'method': 'textDocument/hover'},
        {'method': 'textDocument/didClose', 'params': {'textDocument': {'uri': uri('edges.alc')}}},
        asked(13, 'documentSymbol', 'edges.alc'),
        *closing(14)]],
    ['a test file, wide letters and two imports', {'lib/greet.alc': GREET, 'lib/other.alc': OTHER, 'test/greet_test.alc': TESTS, 'wide.alc': WIDE, 'two.alc': TWO, 'with space.alc': EDGES}, [
        {'id': 1, 'method': 'initialize', 'params': {}},
        opened('test/greet_test.alc', TESTS),
        asked(2, 'documentSymbol', 'test/greet_test.alc'),
        asked(3, 'hover', 'test/greet_test.alc', 13, 20),
        asked(4, 'definition', 'test/greet_test.alc', 13, 20),
        asked(5, 'hover', 'test/greet_test.alc', 13, 6),
        opened('wide.alc', WIDE),
        *every('wide.alc', [(6, 22), (2, 12), (7, 14), (1, 8)], 10),
        asked(6, 'documentSymbol', 'wide.alc'),
        changed('wide.alc', WIDE.replace('    IO.puts(nöpe)\n', '')),
        opened('two.alc', TWO),
        asked(30, 'completion', 'two.alc', 6, 18),
        asked(31, 'completion', 'two.alc', 5, 23),
        asked(32, 'completion', 'two.alc', 4, 2),
        asked(33, 'hover', 'two.alc', 5, 32),
        asked(34, 'definition', 'two.alc', 5, 32),
        # The imported module as its editor holds it, not yet saved.
        opened('lib/other.alc', OTHER.replace('def name(): string', 'def name(): integer').replace('"other"', '7')),
        changed('two.alc', TWO.replace('    IO.puts(Other.)\n', '')),
        asked(35, 'hover', 'two.alc', 5, 32),
        {'method': 'textDocument/didClose', 'params': {'textDocument': {'uri': uri('lib/other.alc')}}},
        changed('two.alc', TWO.replace('    IO.puts(Other.)\n', '    IO.puts("")\n')),
        opened('with%20space.alc', EDGES.replace('hidden(1)', 'hidden("one")')),
        asked(36, 'definition', 'with%20space.alc', 10, 19),
        {'method': 'textDocument/didOpen', 'params': {'textDocument': {'uri': 'untitled:Untitled-1', 'text': EDGES}}},
        {'id': 37, 'method': 'textDocument/documentSymbol', 'params': {'textDocument': {'uri': 'untitled:Untitled-1'}}},
        opened('crlf.alc', EDGES.replace('\n', '\r\n').replace('hidden(1)', 'hiden(1)')),
        asked(38, 'hover', 'crlf.alc', 10, 19),
        *closing(39)]],
    ['a mistake in what is imported', {'lib/greet.alc': GREET.replace('"Hello, " <> name', '"Hello, " <> 1'), 'main.alc': FIXED, 'lib/bad.alc': 'defmodule Bad do\n  def broken( do\nend\n', 'uses.alc': 'defmodule Uses do\n  import "lib/bad.alc"\n  def main() do\n    IO.puts("x")\n  end\nend\n', 'lost.alc': 'defmodule Lost do\n  import "lib/nowhere.alc"\n  def main() do\n    IO.puts("x")\n  end\nend\n'}, [
        {'id': 1, 'method': 'initialize', 'params': {}},
        opened('main.alc', FIXED),
        opened('uses.alc', 'defmodule Uses do\n  import "lib/bad.alc"\n  def main() do\n    IO.puts("x")\n  end\nend\n'),
        opened('lost.alc', 'defmodule Lost do\n  import "lib/nowhere.alc"\n  def main() do\n    IO.puts("x")\n  end\nend\n'),
        asked(2, 'completion', 'uses.alc', 3, 4),
        opened('empty.alc', ''),
        opened('library.alc', 'defmodule Library do\n  def one(): integer do\n    1\n  end\nend\n'),
        opened('wrong.alc', 'defmodule Wrong do\n  def main() do\n    x: integer = "s"\n    undefined_thing(x)\n  end\nend\n'),
        *closing(3)]],
    ['headers and bodies as they come', {'main.alc': MESSY}, [
        sized('{"jsonrpc":"2.0","id":1,"method":"initialize"}     ', 'content-length: %d\r\nContent-Type: application/vscode-jsonrpc; charset=utf-8'),
        sized('not json!'),
        sized('{}'),
        {'raw': 'Content-Length: nine\r\n\r\n'},
        sized('{"jsonrpc":"2.0","id":"s\\u00e9\\ud83d\\ude00\\ud800x","method":"sh\\u0075tdown"}', 'Content-Length:   %d  '),
        sized('{"jsonrpc":"2.0","id":2.5e1,"method":"nope"}'),
        sized('{"jsonrpc":"2.0","id":[1,{"a":null}],"method":"x"}'),
        sized(' {"jsonrpc" : "2.0" , "id" : 3 , "method" : "textDocument/hover" , "params" : {"textDocument":{"uri":"file://ROOT/main.alc"},"position":{"line":1.0,"character":"2"}} } '),
        sized('{"jsonrpc":"2.0","id":4,"method":"textDocument/documentSymbol","params":[1,2]}'),
        sized('{"jsonrpc":"2.0","id":5,"method":"shutdown","id":6}'),
        {'raw': 'X-Other: 1\r\n\r\n{}'}]],
    ['an input that ends inside a message', {}, [
        {'id': 1, 'method': 'initialize', 'params': {}},
        {'raw': 'Content-Length: 200\r\n\r\n{"jsonrpc":"2.0","id":2,"method":"shutdown"}'}]],
    ['an input that ends inside the headers', {}, [
        {'id': 1, 'method': 'shutdown'},
        {'raw': 'Content-Length: 20\r\n'}]],
    ['no input', {}, []],
]


def framed(message, root):
    """A message as the client writes it, in the project at root."""
    if 'raw' in message:
        return message['raw'].encode()
    if 'body' in message:
        data = message['body'].replace('ROOT', root).encode()
        return (message['header'] % len(data)).encode() + b'\r\n\r\n' + data
    data = json.dumps(dict(message, jsonrpc='2.0'), separators=(',', ':'), ensure_ascii=False).replace('ROOT', root).encode()
    return b'Content-Length: %d\r\n\r\n' % len(data) + data


def messages(out, there):
    """The messages a server wrote, with the directory there as ROOT; or
    what it wrote as it is where that is no run of messages."""
    found, rest = [], out
    while rest:
        head, gap, tail = rest.partition(b'\r\n\r\n')
        if not gap or not head.startswith(b'Content-Length: ') or not head[16:].isdigit() or int(head[16:]) > len(tail):
            return [out.replace(there, b'ROOT').decode('utf8', 'replace')]
        size = int(head[16:])
        found.append(tail[:size].replace(there, b'ROOT').decode('utf8', 'replace'))
        rest = tail[size:]
    return found


def session(command, files, sent, pinned=False):
    """What a server answers in a directory of its own, with the directory as ROOT."""
    environment = dict(os.environ, GOTOOLCHAIN='local', GOPROXY='off', GOFLAGS='-mod=mod') if pinned else {'PATH': '/usr/bin:/bin', 'HOME': os.environ.get('HOME', '/')}
    with tempfile.TemporaryDirectory(prefix='alchem-lsp-') as top:
        root = Path(top).resolve() / 'project'
        root.mkdir()
        for name, text in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(text.replace('ROOT', str(root)).encode())
        given = b''.join(framed(message, str(root)) for message in sent)
        run = subprocess.run([str(command), 'lsp'], input=given, capture_output=True, cwd=root, env=environment, timeout=300)
        there = str(root).encode()
        return [run.returncode, run.stderr.replace(there, b'ROOT').decode('utf8', 'replace'), messages(run.stdout, there)]


def record(pinned):
    held = [{'name': name, 'answers': session(pinned, files, sent, True)} for name, files, sent in SESSIONS]
    CASES.write_text(json.dumps(held, indent=1, ensure_ascii=False) + '\n')
    print(f'wrote {CASES.name}: {len(held)} sessions, {sum(len(s["answers"][2]) for s in held)} messages')


def verify(compiler):
    held = json.loads(CASES.read_text())
    assert [s['name'] for s in held] == [name for name, _, _ in SESSIONS], 'harness/lsp-cases.json is not of these sessions: run harness/lsp.py --record'
    spec = spec_from_file_location('build_alchem', ROOT / 'scripts/build-alchem.py')
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    count = 0
    with tempfile.TemporaryDirectory(prefix='alchem-lsp-') as top:
        alchem = Path(top) / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))
        for (name, files, sent), expected in zip(SESSIONS, held):
            seen = session(alchem, files, sent)
            status, said, answers = expected['answers']
            assert seen[:2] == [status, said], (name, seen[:2], [status, said])
            for k, (mine, pinned) in enumerate(zip(seen[2], answers)):
                assert mine == pinned, (name, k, mine, pinned)
            assert len(seen[2]) == len(answers), (name, len(seen[2]), len(answers), seen[2][len(answers):], answers[len(seen[2]):])
            count += len(answers)
        # What only the compiler refuses (here a calendar sigil with two
        # spaces, which the pinned compiler takes) is a diagnostic once the
        # document is as its file is, and none while it is not: the
        # compiler reads files (spec/alchem-commands.md).
        status, said, answers = session(alchem, {'late.alc': LATE}, [
            {'id': 1, 'method': 'initialize', 'params': {}},
            opened('late.alc', LATE),
            changed('late.alc', LATE + '\n'),
            {'method': 'textDocument/didSave', 'params': {'textDocument': {'uri': uri('late.alc'), 'text': LATE}}},
            *closing(2)])
        assert (status, said) == (0, ''), (status, said)
        found = [json.loads(answer)['params']['diagnostics'] for answer in answers if 'publishDiagnostics' in answer]
        assert [len(d) for d in found] == [1, 0, 1], found
        for diagnostics in (found[0], found[2]):
            assert diagnostics[0]['message'] == 'E_COMPILE: the native compiler does not take something in Late.main/0' and diagnostics[0]['range']['start'] == {'line': 1, 'character': 2}, diagnostics
    print(f'PASS lsp: {len(held)} sessions with the language server, {count} messages answered as the pinned server answers them, byte for byte: diagnostics, hover, definition, completion, formatting and symbols; what only the compiler refuses is a diagnostic of a saved document')


if __name__ == '__main__':
    if sys.argv[1] == '--record':
        record(Path(sys.argv[2]).resolve())
    else:
        verify(Path(sys.argv[1]).resolve())
