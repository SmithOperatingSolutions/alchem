#!/usr/bin/env python3
"""Regenerate tools/alchem-guide-data.alc: what the documentation commands of
`alchem` print from (version, help, syntax, doc, docs, agent-guide and
agent-install in tools/alchem-guide.alc). Not used by normal builds.

    generate-guide-data.py PINNED [--check]

PINNED is the pinned command line (the Go `alchem` of the release the
compiler follows). Everything is taken from what it prints, so the native
command describes the language and the library the pinned one describes:

  agent-guide --json      the commands with their flags, the differences
  agent-guide             the first program
  COMMAND -h              the usage of each command
  syntax --json           the topics
  doc --all --json        the modules and their functions
  doc --group GROUP       the examples a group is introduced with
  agent-install           the agents, and the file written for each
  docs                    the note at the head of a generated file

The module holds one string per table. A table is records divided by
U+001E, a record is fields divided by U+001F, and a field that is a list is
items divided by U+001D, whose parts are divided by U+001C: none of the four
occurs in the text. --check fails when the file is not what would be
written."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'tools/alchem-guide-data.alc'
RECORD, FIELD, ITEM, PART = '\x1e', '\x1f', '\x1d', '\x1c'


def literal(text):
    """An Alchem string literal of the text."""
    out = []
    for ch in text:
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '#':
            out.append('\\#')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\t':
            out.append('\\t')
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append('\\u{%X}' % ord(ch))
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


def table(records):
    def field(value):
        if isinstance(value, str):
            return value
        return ITEM.join(part if isinstance(part, str) else PART.join(part) for part in value)
    text = RECORD.join(FIELD.join(field(value) for value in record) for record in records)
    return text


def between(text, before, after):
    start = text.index(before) + len(before)
    return text[start:text.index(after, start)]


def data(pinned):
    def said(*arguments, cwd=None, status=0):
        result = subprocess.run([str(pinned), *arguments], capture_output=True, text=True, cwd=cwd, timeout=120)
        if result.returncode != status:
            raise SystemExit(f'{" ".join(arguments)}: status {result.returncode}: {result.stderr}')
        return result.stdout, result.stderr

    guide = json.loads(said('agent-guide', '--json')[0])
    guide_text = said('agent-guide')[0]
    commands = [(c['name'], c['usage'], c['summary'],
                 [(f['name'], f.get('default', ''), f['summary']) for f in c.get('flags', [])],
                 said(c['name'], '-h')[1]) for c in guide['commands']]
    topics = [(t['name'], t['group'], t['summary'], t['notes'] or [], t.get('see') or [],
               [(e['title'], e['source']) for e in t['examples'] or []]) for t in json.loads(said('syntax', '--json')[0])]
    modules, functions, groups = [], [], []
    for module in json.loads(said('doc', '--all', '--json')[0]):
        modules.append((module['name'], module['group'], module['summary']))
        if module['group'] not in groups:
            groups.append(module['group'])
        for f in module['functions'] or []:
            functions.append((f['name'], f['module'], f['signatures'], f.get('requires') or [], f['summary'], f.get('examples', '')))
    # As the pinned command orders them where it looks through every
    # function: by module, then by the name within it.
    functions.sort(key=lambda f: (f[1], f[0][len(f[1]) + 1:] if f[0].startswith(f[1] + '.') else f[0]))
    examples = []
    for group in groups:
        text = said('doc', '--group', group)[0]
        mark = '\nExamples\n\n'
        examples.append((group, text[text.index(mark) + len(mark):] if mark in text else ''))
    targets = []
    skill = None
    with tempfile.TemporaryDirectory() as d:
        listed = json.loads(said('agent-install', '--list', '--json')[0])
        written = {}
        for target in listed:
            said('agent-install', '--dir', str(Path(d) / target['name']), target['name'])
            written[target['name']] = (Path(d) / target['name'] / target['path']).read_text()
        # A file of alchem's own is a heading and the text; a shared file
        # is the text between two marks.
        plain = [written[t['name']] for t in listed if not t['shared']]
        skill = min(plain, key=len)
        for target in listed:
            header = ''
            if not target['shared']:
                if not written[target['name']].endswith(skill):
                    raise SystemExit('the file of ' + target['name'] + ' does not end in the text')
                header = written[target['name']][:-len(skill)]
            targets.append((target['name'], target['summary'], target['path'], target.get('user_path', ''), 'shared' if target['shared'] else '', header))
        said('docs', '--dir', str(Path(d) / 'docs'))
        generated = between((Path(d) / 'docs/library-reference.md').read_text(), '# Library reference\n\n', 'Every library function')
    tables = {
        'commands': table(commands),
        'differences': table([(line,) for line in guide['differences_from_elixir']]),
        'topics': table(topics),
        'modules': table(modules),
        'functions': table(functions),
        'examples': table(examples),
        'targets': table(targets),
        'skill': skill,
        'generated': generated,
        'hello': between(guide_text, '## A first program\n\n```elixir\n', '```\n'),
    }
    for name, text in tables.items():
        if name in ('skill', 'generated', 'hello'):
            if any(mark in text for mark in (RECORD, FIELD, ITEM, PART)):
                raise SystemExit(name + ' holds a dividing character')
    return tables


def module(tables):
    lines = ['defmodule AlchemGuideData do',
             '  # Generated by scripts/generate-guide-data.py from what the pinned',
             '  # command line prints; edit nothing here.']
    for name, text in tables.items():
        lines += ['', f'  def {name}(): string do', '    ' + literal(text), '  end']
    return '\n'.join(lines) + '\nend\n'


def main(arguments):
    check = '--check' in arguments
    paths = [a for a in arguments if a != '--check']
    if len(paths) != 1:
        raise SystemExit(__doc__)
    text = module(data(Path(paths[0]).resolve()))
    if check:
        if OUTPUT.read_text() != text:
            raise SystemExit('tools/alchem-guide-data.alc is not what the pinned command gives; run scripts/generate-guide-data.py')
        print('tools/alchem-guide-data.alc is current')
        return
    OUTPUT.write_text(text)
    print(f'wrote {OUTPUT.relative_to(ROOT)}: {len(text)} bytes')


if __name__ == '__main__':
    main(sys.argv[1:])
