#!/usr/bin/env python3
"""Every file made from other files is what its generator makes of them today.

    verify-derived.py          compare; a difference, or a generator that
                               fails, is reported and ends with status 1
    verify-derived.py --write  regenerate the files that differ
    verify-derived.py NAME...  only the generators named

Each generator runs in a copy of the tree as it is, so one is never hidden
by another's output and nothing here is changed (but with --write). The
machine code depends on the assembler and on the C compiler (the Windows
layer), so this runs where they are the pinned ones, in the container, which
scripts/linux-container.sh starts:

    scripts/linux-container.sh python3 scripts/verify-derived.py

Every script named generate-* must be in GENERATORS or in RECORDED, which
says why its output is not made again here, and every file that says it is
generated must be one a generator here writes: a new one cannot be left out.
"""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
HELD = ('implementations', 'library', 'tools', 'spec')
COPIED = HELD + ('scripts', 'adapters')
LINKED = ('.cache', 'build/arm64-tools')


def python(name, *arguments):
    return lambda root: [sys.executable, str(root / f'scripts/generate-{name}.py'), *arguments]


def go(name):
    return lambda root: ['go', 'run', str(root / f'scripts/generate-{name}.go')]


# name: (the command in a tree, the files it writes). A command of Go prints
# its file. One that writes no file checks what is written by hand.
GENERATORS = {
    'case-ranges': (go('case-ranges'), ['spec/case-ranges.json']),
    'errno-messages': (go('errno-messages'), ['spec/errno-messages.json']),
    'print-ranges': (go('print-ranges'), ['spec/print-ranges.json']),
    'regex-tables': (go('regex-tables'), ['spec/regex-tables.json']),
    'print-data': (lambda root: ['go', 'run', '.'], ['tools/alchem-print-data.alc']),
    'normalization': (python('normalization'), ['library/String.alc']),
    'tzdata': (python('tzdata'), ['library/Date.alc']),
    'check-data': (python('check-data'), ['tools/alchem-check-data.alc']),
    'enumerable-params': (python('enumerable-params'), ['implementations/alchem/native-enumerable-data.alc']),
    'case-runtime': (python('case-runtime'), ['implementations/alchem/native-case-data.alc']),
    'collection-runtime': (python('collection-runtime'), ['implementations/alchem/native-collection-data.alc']),
    'crypto-runtime': (python('crypto-runtime'), ['implementations/alchem/native-crypto-data.alc']),
    'file-read-runtime': (python('file-read-runtime'), ['implementations/alchem/native-file-data.alc']),
    'float-runtime': (python('float-runtime'), ['implementations/alchem/native-float-data.alc']),
    'grapheme-runtime': (python('grapheme-runtime'), ['implementations/alchem/native-grapheme-data.alc']),
    'library-runtime': (python('library-runtime'), ['implementations/alchem/native-library-data.alc']),
    'marked-fragments': (python('marked-fragments'), ['implementations/alchem/native-marked-data.alc']),
    'memory-runtime': (python('memory-runtime'), ['implementations/alchem/native-memory-data.alc', 'implementations/alchem/native-memory-data-arm64.alc']),
    'memory-runtime-darwin': (python('memory-runtime', '--darwin'), ['implementations/alchem/native-memory-data-darwin.alc']),
    'parse-runtime': (python('parse-runtime'), ['implementations/alchem/native-parse-data.alc']),
    'prelude': (python('prelude'), ['implementations/alchem/native-prelude-data.alc']),
    'process-runtime': (python('process-runtime'), []),
    'regex-data': (python('regex-data'), ['implementations/alchem/native-regex-data.alc']),
    'sort-runtime': (python('sort-runtime'), ['implementations/alchem/native-sort-data.alc']),
    'tls-runtime': (python('tls-runtime'), ['implementations/alchem/native-tls-data.alc']),
    'trace-runtime': (python('trace-runtime'), ['implementations/alchem/native-trace-data.alc']),
    'windows-runtime': (python('windows-runtime'), ['implementations/alchem/native-windows-data.alc']),
    'arm64-runtimes': (python('arm64-runtimes'), ['implementations/alchem/native-runtimes-arm64.alc']),
    'guide-data': (None, ['tools/alchem-guide-data.alc']),
}
# What a pinned program said once, held as a gate's expectations: made again
# by hand when the reference moves, and compared with every build meanwhile.
RECORDED = {
    'command-cases': 'harness/commands.py',
    'front-end-cases': 'harness/front_end.py',
    'front-end-probes': 'harness/front_end.py',
    'gaps-cases': 'harness/gaps.py (chosen from random programs)',
    'list-cases': 'harness/lists.py (chosen from random programs)',
    'nil-forms-cases': 'harness/nil_forms.py (chosen from random programs)',
    'ordering-cases': 'harness/ordering.py (chosen from random programs)',
    'program-cases': 'harness/programs.py (random programs)',
    'test-driver-cases': 'harness/test_driver.py',
    'written-cases': 'harness/written.py (programs written by hand)',
}


def unlisted():
    """What the tables above leave out."""
    wrong = []
    for path in sorted((ROOT / 'scripts').glob('generate-*')):
        name = path.stem[len('generate-'):]
        if name not in GENERATORS and name not in RECORDED:
            wrong.append(f'scripts/{path.name} is in neither GENERATORS nor RECORDED')
    written = {path for _, outputs in GENERATORS.values() for path in outputs}
    for folder in HELD:
        for path in sorted((ROOT / folder).rglob('*.alc')):
            name = str(path.relative_to(ROOT))
            says = re.search(r'^\s*#.*\bgenerated (by|from|Unicode)\b', path.read_text(), re.M | re.I)
            if says and name not in written:
                wrong.append(f'{name} says it is generated, and no generator here writes it')
    return wrong


def copy_of_tree(top):
    root = Path(top) / 'native'
    root.mkdir()
    for name in COPIED:
        shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns('__pycache__'))
    for name in LINKED:
        if (ROOT / name).exists():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).symlink_to(ROOT / name)
    return root


def pinned_command(top):
    """The pinned command line, built from its module."""
    sys.path.insert(0, str(ROOT / 'scripts'))
    import reference
    return reference.command(Path(top) / 'alchem-pinned')


def files(root):
    return {path.relative_to(root): path.read_bytes() for folder in HELD for path in (root / folder).rglob('*') if path.is_file() and '__pycache__' not in path.parts}


def made(name):
    """({file: bytes} that the generator writes otherwise than the tree has
    it, what it says when it fails)."""
    command, outputs = GENERATORS[name]
    with tempfile.TemporaryDirectory(prefix='alchem-derived-') as top:
        root = copy_of_tree(top)
        before = files(root)
        if name == 'guide-data':
            arguments = [sys.executable, str(root / 'scripts/generate-guide-data.py'), str(pinned_command(top))]
        else:
            arguments = command(root)
        prints = arguments[0] == 'go'
        where = root / 'scripts/pinned-print' if name == 'print-data' else root
        run = subprocess.run(arguments, cwd=where, capture_output=True, timeout=1800)
        if run.returncode:
            return {}, (run.stderr or run.stdout).decode(errors='replace').strip()[-1500:] or f'status {run.returncode}'
        if prints:
            (root / outputs[0]).write_bytes(run.stdout)
        after = files(root)
        changed = {path: data for path, data in after.items() if before.get(path) != data}
        stray = sorted(str(path) for path in changed if str(path) not in outputs)
        return changed, f'it also writes {", ".join(stray)}' if stray else ''


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--write', action='store_true')
    parser.add_argument('names', nargs='*', metavar='NAME')
    args = parser.parse_args()
    unknown = [name for name in args.names if name not in GENERATORS]
    if unknown:
        parser.error(f'no generator {", ".join(unknown)}')
    failed = unlisted()
    for problem in failed:
        print(f'FAIL {problem}')
    for name in args.names or GENERATORS:
        changed, said = made(name)
        if said:
            failed.append(name)
            print(f'FAIL {name}: {said}', flush=True)
        elif changed and args.write:
            for path, data in changed.items():
                (ROOT / path).write_bytes(data)
            print(f'wrote {name}: {", ".join(map(str, changed))}', flush=True)
        elif changed:
            failed.append(name)
            print(f'FAIL {name}: {", ".join(map(str, changed))} is not what it makes', flush=True)
        else:
            print(f'PASS {name}', flush=True)
    if failed:
        print(f'{len(failed)} derived files or generators are not as they should be (scripts/verify-derived.py --write in the container regenerates files)')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
