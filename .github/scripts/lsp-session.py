#!/usr/bin/env python3
"""An editor's session with a released alchem, on the machine it is for.

    lsp-session.py ALCHEM

Writes a small project into a directory of its own and speaks the Language
Server Protocol to `ALCHEM lsp` about it, with the paths and file
addresses of this system: a document with a mistake gets its diagnostic
where the mistake is, and without it none; hover and definition reach a
function of an imported file; completion offers it; formatting and the
document's symbols answer; the server ends when told to. What each reply
is, byte for byte, the lsp gate of native/ checks against the pinned
server (native/harness/lsp.py); this is that the server works wherever a
release runs."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

GREET = 'defmodule Greet do\n  @doc """\n  Greets someone.\n  """\n  def hello(name: string): string do\n    "Hello, " <> name\n  end\nend\n'
BROKEN = 'defmodule Main do\n  import "lib/greet.alc"\n\n  def main() do\n    IO.puts(Greet.hello(1))\n  end\nend\n'
FIXED = BROKEN.replace('Greet.hello(1)', 'Greet.hello("Ada")')
MESSY = FIXED.replace('    IO.puts(', 'IO.puts( ')


def framed(message):
    data = json.dumps(dict(message, jsonrpc='2.0')).encode()
    return b'Content-Length: %d\r\n\r\n' % len(data) + data


def messages(out):
    found = []
    while out:
        head, _, tail = out.partition(b'\r\n\r\n')
        size = int(head.split(b':')[1])
        found.append(json.loads(tail[:size]))
        out = tail[size:]
    return found


def main(alchem):
    with tempfile.TemporaryDirectory(prefix='alchem-lsp-') as top:
        root = Path(top).resolve() / 'a project'
        (root / 'lib').mkdir(parents=True)
        (root / 'lib' / 'greet.alc').write_bytes(GREET.encode())
        (root / 'main.alc').write_bytes(BROKEN.encode())
        uri = (root / 'main.alc').as_uri()
        document = {'textDocument': {'uri': uri}}
        at = dict(document, position={'line': 4, 'character': 20})
        sent = [
            {'id': 1, 'method': 'initialize', 'params': {'rootUri': root.as_uri()}},
            {'method': 'textDocument/didOpen', 'params': {'textDocument': {'uri': uri, 'text': BROKEN}}},
            {'method': 'textDocument/didChange', 'params': {'textDocument': {'uri': uri}, 'contentChanges': [{'text': FIXED}]}},
            {'id': 2, 'method': 'textDocument/hover', 'params': at},
            {'id': 3, 'method': 'textDocument/definition', 'params': at},
            {'id': 4, 'method': 'textDocument/completion', 'params': dict(document, position={'line': 4, 'character': 18})},
            {'id': 5, 'method': 'textDocument/documentSymbol', 'params': document},
            {'method': 'textDocument/didChange', 'params': {'textDocument': {'uri': uri}, 'contentChanges': [{'text': MESSY}]}},
            {'id': 6, 'method': 'textDocument/formatting', 'params': document},
            {'id': 7, 'method': 'shutdown'},
            {'method': 'exit'},
        ]
        run = subprocess.run([alchem, 'lsp'], input=b''.join(framed(m) for m in sent), capture_output=True, cwd=root, timeout=300)
        assert (run.returncode, run.stderr) == (0, b''), (run.returncode, run.stderr)
        got = messages(run.stdout)
    answers = {m['id']: m for m in got if 'id' in m}
    published = [m['params'] for m in got if m.get('method') == 'textDocument/publishDiagnostics']
    assert answers[1]['result']['capabilities']['hoverProvider'] is True, answers[1]
    assert [p['uri'] for p in published] == [uri] * 3, published
    first = published[0]['diagnostics']
    assert len(first) == 1 and first[0]['range']['start'] == {'line': 4, 'character': 24} and 'string' in first[0]['message'], first
    assert published[1]['diagnostics'] == [] and published[2]['diagnostics'] == [], published
    assert 'def hello(name: string): string' in answers[2]['result']['contents']['value'] and 'Greets someone.' in answers[2]['result']['contents']['value'], answers[2]
    assert answers[3]['result']['uri'] == (root / 'lib' / 'greet.alc').as_uri() and answers[3]['result']['range']['start']['line'] == 4, (answers[3], (root / 'lib' / 'greet.alc').as_uri())
    assert 'hello' in [item['label'] for item in answers[4]['result']], answers[4]
    assert [symbol['name'] for symbol in answers[5]['result']] == ['main'], answers[5]
    assert len(answers[6]['result']) == 1 and answers[6]['result'][0]['newText'] == FIXED, answers[6]
    assert answers[7]['result'] is None, answers[7]
    print(f'{len(got)} messages from alchem lsp: diagnostics, hover, definition, completion, symbols and formatting, in {root.as_uri()[:8]}... addresses')


if __name__ == '__main__':
    main(str(Path(sys.argv[1]).resolve()))
