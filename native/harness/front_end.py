#!/usr/bin/env python3
"""The front end of alchem (tools/alchem-lexer.alc, tools/alchem-parse.alc)
and its formatter (tools/alchem-format.alc) against the pinned compiler's
lexer, parser and formatter (spec/alchem-front-end.md).

harness/front-end-cases.json.xz holds source texts and, for each, the
SHA-256 of what the pinned lexer, parser and formatter give for it as
JSON: the tokens and comments, the tree ParseSyntax gives or its message,
the text Format gives or its message, and the tree ParseModule lowers for
the checker or its message (scripts/generate-front-end-cases.py
makes the file). The texts are the repository's source files as they were
when the file was made, broken copies of them (a line dropped, the text cut
short, a sign put in, two lines swapped, a few characters taken out), and
copies written otherwise than the formatter writes them (indentation taken
out, or added with spaces at the ends of lines and none after commas, or
blank lines moved and operators spaced). scripts/lexer-dump.alc,
scripts/parser-dump.alc, scripts/format-dump.alc and scripts/module-dump.alc,
built by an alchem the
compiler under test builds, must give the same bytes for every text."""
from pathlib import Path
import hashlib
import json
import lzma
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[1]
CASES = Path(__file__).resolve().parent / 'front-end-cases.json.xz'
# Programs written for what the checker's walk follows, with what the
# pinned `check` says of each (scripts/generate-front-end-probes.py).
PROBES = Path(__file__).resolve().parent / 'front-end-probes.json'


def cases():
    return json.loads(lzma.decompress(CASES.read_bytes()))


def lines(program, paths):
    """What a dump gives for each file, by the file's name."""
    out = subprocess.run([str(program)] + [str(p) for p in paths], capture_output=True, timeout=1800, check=True).stdout
    found = {}
    for line in out.split(b'\n'):
        if line.startswith(b'["'):
            found[json.loads(line.decode('utf8', 'replace'))[0]] = line
    return found


def digest(line, path):
    """The SHA-256 of a dump's line with the file's name taken out."""
    return hashlib.sha256(line.replace(json.dumps(str(path)).encode(), b'"FILE"', 1)).hexdigest()


def loaded(command, texts, pinned=False):
    """The program the loader gives the checker for each text as the file
    x.alc of a directory of its own (scripts/loaded-dump.alc, or the pinned
    loader of scripts/pinned-loaded.py), with the directory as D."""
    environment = dict(os.environ, GOTOOLCHAIN='local', GOPROXY='off', GOFLAGS='-mod=mod') if pinned else {'PATH': '/usr/bin:/bin', 'HOME': os.environ.get('HOME', '/')}
    with tempfile.TemporaryDirectory(prefix='alchem-loaded-') as top:
        def one(k):
            directory = Path(top).resolve() / f'{k:05d}' / 'x'
            directory.mkdir(parents=True)
            (directory / 'x.alc').write_bytes(texts[k].encode('utf8', 'surrogateescape'))
            run = subprocess.run([str(command), 'x.alc'], cwd=directory, capture_output=True, env=environment, timeout=600)
            said = run.stdout.replace(str(directory).encode(), b'D').replace(str(directory.parent).encode(), b'P')
            return hashlib.sha256(said.replace(str(Path(top).resolve()).encode(), b'T')).hexdigest()
        with ThreadPoolExecutor(os.cpu_count() or 2) as pool:
            return list(pool.map(one, range(len(texts))))


def checked(command, texts, pinned=False, flags=()):
    """What `check` says of each text as the file x.alc of a directory of
    its own: the status and the standard error, with the directory as D,
    the one above it as P and the one above that as T.
    The pinned command is given the Go toolchain, kept from the network."""
    environment = dict(os.environ, GOTOOLCHAIN='local', GOPROXY='off', GOFLAGS='-mod=mod') if pinned else {'PATH': '/usr/bin:/bin', 'HOME': os.environ.get('HOME', '/')}
    with tempfile.TemporaryDirectory(prefix='alchem-check-') as top:
        def one(k):
            directory = Path(top).resolve() / f'{k:05d}' / 'x'
            directory.mkdir(parents=True)
            (directory / 'x.alc').write_bytes(texts[k].encode('utf8', 'surrogateescape'))
            run = subprocess.run([str(command), 'check', *flags, 'x.alc'], cwd=directory, capture_output=True, env=environment, timeout=600)
            said = run.stderr.decode('utf8', 'replace').replace(str(directory), 'D').replace(str(directory.parent), 'P')
            return [run.returncode, said.replace(str(Path(top).resolve()), 'T').replace(top, 'T')]
        with ThreadPoolExecutor(os.cpu_count() or 2) as pool:
            return list(pool.map(one, range(len(texts))))


# What is said of a program the native compiler or bundler refuses that the
# front end does not explain (spec/alchem-commands.md).
UNEXPLAINED = ('E_COMPILE: ', 'E_BUNDLE: ')
# How many of the texts the pinned compiler refuses check explains as it
# does, at the least: the count may only grow.
EXPLAINED = 2005
# And of the probes, how many check answers as the pinned command does.
PROBED = 268


def verify(compiler):
    held = cases()
    spec = spec_from_file_location('build_alchem', ROOT / 'scripts/build-alchem.py')
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix='alchem-front-end-') as top:
        base = Path(top)
        alchem = base / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))
        for name in ('lexer-dump', 'parser-dump', 'format-dump', 'module-dump', 'loaded-dump'):
            subprocess.run([str(alchem), 'build', '-o', str(base / name), name + '.alc'], cwd=ROOT / 'scripts', check=True, timeout=1800)
        paths = []
        for k, case in enumerate(held):
            path = base / 'texts' / f'{k:05d}.alc'
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(case['text'].encode('utf8', 'surrogateescape'))
            paths.append(path)
        tokens, trees, formats, modules = (lines(base / name, paths) for name in ('lexer-dump', 'parser-dump', 'format-dump', 'module-dump'))
        refused = 0
        for path, case in zip(paths, held):
            assert digest(tokens.get(str(path), b''), path) == case['tokens'], ('tokens', case['name'])
            assert digest(trees.get(str(path), b''), path) == case['tree'], ('tree', case['name'])
            assert digest(formats.get(str(path), b''), path) == case['format'], ('format', case['name'])
            assert digest(modules.get(str(path), b''), path) == case['module'], ('module', case['name'])
            refused += case['refused']
        # The program the loader gives the checker, for every text the
        # loader is followed to its end for here: the pinned one, byte for
        # byte.
        followed = 0
        for case, seen in zip(held, loaded(base / 'loaded-dump', [case['text'] for case in held])):
            if seen != case['skipped']:
                assert seen == case['loaded'], ('loaded', case['name'])
                followed += 1
        # check: the pinned message for every text the pinned compiler
        # refuses, and with --json its diagnostic, or none where the front
        # end does not reach the reason.
        refusing = [case for case in held if case['check'][0] != 0]
        explained = 0
        texts = [case['text'] for case in refusing]
        for case, seen, described in zip(refusing, checked(alchem, texts), checked(alchem, texts, flags=('--json',))):
            if seen == case['check']:
                explained += 1
                assert described == case['described'], ('check --json', case['name'], described, case['described'])
            else:
                assert seen[0] == 0 or any(word in seen[1] for word in UNEXPLAINED), ('check', case['name'], seen, case['check'])
        assert explained >= EXPLAINED, f'check explains {explained} of the {len(refusing)} refused texts, fewer than {EXPLAINED}'
        # And no text the pinned compiler accepts is refused with a reason.
        accepting = [case for case in held if case['check'][0] == 0]
        for case, seen in zip(accepting, checked(alchem, [case['text'] for case in accepting])):
            assert seen[0] == 0 or any(word in seen[1] for word in UNEXPLAINED), ('check of an accepted text', case['name'], seen)
        # The probes: the pinned answer, or none.
        probes = json.loads(PROBES.read_text())
        answered = 0
        for probe, seen in zip(probes, checked(alchem, [probe['text'] for probe in probes])):
            if seen == probe['check']:
                answered += 1
            else:
                assert seen[0] == 0 or any(word in seen[1] for word in UNEXPLAINED), ('check of a probe', probe['text'], seen, probe['check'])
        assert answered >= PROBED, f'check answers {answered} of the {len(probes)} probes as the pinned command does, fewer than {PROBED}'
    print(f'PASS front_end: {len(held)} texts lexed, parsed, formatted and lowered as the pinned compiler lexes, parses, formats and lowers them, byte for byte; {refused} of them refused with its message; {followed} loaded as its loader loads them; check gives the pinned message and --json diagnostic for {explained} of the {len(refusing)} texts the pinned compiler refuses, and no other message, and refuses none of the {len(accepting)} it accepts; {answered} of {len(probes)} probes of the walk over function bodies answered as the pinned command answers them')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
