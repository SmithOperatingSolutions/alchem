#!/usr/bin/env python3
"""Facts written in more than one place say the same thing everywhere.

A fact of the pinned language that the tools and the compiler each hold a
copy of is read from the pinned compiler's source, and every copy must be
it; a version several files name must be one version.

- The Go module every program of the reference is built from: the go.mod
  files under native/ name one version of it.
- The namespaces of the library (ReservedModule) and the ones a program's
  module may take (RetiringModule), in the front end (tools/) and in the
  compiler (implementations/alchem/native-compiler.alc), where a name is
  the bytes of its letters; the compiler holds the names that can be a
  module's, those without a dot.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import reference  # noqa: E402

MODULE = 'github.com/SmithOperatingSolutions/alchem'


def versions():
    """{go.mod: the version of the reference it names}."""
    found = {}
    for path in sorted(ROOT.glob('adapters/*/go.mod')) + sorted(ROOT.glob('scripts/*/go.mod')):
        named = re.search(re.escape(MODULE) + r' (\S+)', path.read_text())
        if named:
            found[str(path.relative_to(ROOT))] = named.group(1)
    return found


def go_names(text, function):
    """The names of the case of a func NAME(name string) bool that returns true."""
    body = text[text.index(f'func {function}(name string) bool'):]
    case = body[body.index('case ') + 5:body.index(':\n')]
    return re.findall(r'"([^"]+)"', case)


def alchem_list(path, opening):
    """The strings of the list that follows opening in a file of tools/."""
    text = (ROOT / path).read_text()
    assert text.count(opening) == 1, (path, opening, text.count(opening))
    rest = text[text.index(opening) + len(opening):]
    return re.findall(r'"([^"]+)"', rest[:rest.index(']')])


def compiler_words(function):
    """The words a function of the compiler compares with, from their bytes."""
    text = (ROOT / 'implementations/alchem/native-compiler.alc').read_text()
    found = []
    for name in re.findall(r'^  def (' + function + r'(?:_\d+)?)\(source', text, re.M):
        body = text[text.index(f'  def {name}(source'):]
        body = body[:body.index('\n  end')]
        found += [bytes(int(n) for n in word.split(',')).decode() for word in re.findall(r'nc_word\(source,pos,b\[([0-9,]+)\]\)', body)]
    return found


def verify(compiler=None):
    named = versions()
    assert len(named) >= 6 and len(set(named.values())) == 1, f'the go.mod files of native/ name more than one version of the reference: {named}'
    source = (reference.tree() / 'compiler/syntax/builtins.go').read_text()
    reserved, retiring = go_names(source, 'ReservedModule'), go_names(source, 'RetiringModule')
    assert len(reserved) > 40 and len(retiring) >= 1, (reserved, retiring)
    copies = {
        'tools/alchem-check.alc reserved?': (alchem_list('tools/alchem-check.alc', 'def reserved?(name: string): boolean do\n    name in ['), reserved),
        'tools/alchem-typing.alc reserved?': (alchem_list('tools/alchem-typing.alc', 'def reserved?(name: string): boolean do\n    name in ['), reserved),
        'tools/alchem-check.alc retiring?': (alchem_list('tools/alchem-check.alc', 'def retiring?(name: string): boolean do name in ['), retiring),
        'tools/alchem-guide.alc retiring?': (alchem_list('tools/alchem-guide.alc', 'def retiring?(module: string): boolean do\n    module in ['), retiring),
        'tools/alchem-lower.alc retiring': (alchem_list('tools/alchem-lower.alc', 'retiring: module in ['), retiring),
        'the compiler, nc_library_module': (compiler_words('nc_library_module'), [name for name in reserved if '.' not in name]),
        'the compiler, nc_retiring_module': (compiler_words('nc_retiring_module'), retiring),
    }
    for where, (held, pinned) in copies.items():
        assert sorted(held) == sorted(pinned), f'{where} is not the pinned list: only here {sorted(set(held) - set(pinned))}, only pinned {sorted(set(pinned) - set(held))}'
    builtins = source[source.rfind('= map[', 0, source.index('"File.exists":')):source.index('\n}\n', source.index('"File.exists":'))]
    pinned = {(name, 1 + types.count(',')) for name, types in re.findall(r'"([^"]+)":\s*\{\[\]string\{([^}]*)\}', builtins)}
    text = (ROOT / 'implementations/alchem/native-functions.alc').read_text()
    held = set()
    for count, function in ((3, 'nf_simple'), (1, 'nf_simple_one'), (2, 'nf_simple_two')):
        body = text[text.index(f'  def {function}(source'):]
        body = body[:body.index('\n  end')]
        for module, name in re.findall(r'nf_simple_pair\(source,name,last,b\[([0-9,]+)\],b\[([0-9,]+)\]\)', body):
            held.add(('.'.join(bytes(int(n) for n in word.split(',')).decode() for word in (module, name)), count))
    assert held == pinned, f'the compiler, nf_simple: only here {sorted(held - pinned)}, only pinned {sorted(pinned - held)}'
    # The seed (the Go frontend of adapters/alchem) knows a function by its
    # name alone, and only nightly runs start from it.
    spec = spec_from_file_location('bootstrap', ROOT / 'scripts/bootstrap-alchem-compiler.py')
    bootstrap = module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    defined = re.findall(r'^  def (\w+)\(', bootstrap.source_text('functions', False), re.M)
    twice = sorted({name for name in defined if defined.count(name) > 1}) if len(set(defined)) != len(defined) else []
    assert not twice and len(defined) > 3000, f'functions of the compiler defined twice: {twice}'
    print(f'facts: {len(named)} go.mod files name {next(iter(named.values()))}; {len(copies)} copies of the library\'s namespaces are the pinned ones')


if __name__ == '__main__':
    verify()
