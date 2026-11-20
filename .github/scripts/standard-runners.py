#!/usr/bin/env python3
"""Fail when a workflow names a runner other than GitHub's standard hosted
runners. Those are free and unlimited for this public repository; larger
runners are billed, and self-hosted runners are not used.

Every value of runs-on, and of the matrix keys os and runner that runs-on
reads, must be one of STANDARD. Add a label here only after checking that
GitHub lists it as a standard runner for public repositories:
https://docs.github.com/en/actions/reference/runners/github-hosted-runners
"""
from pathlib import Path
import re
import sys

STANDARD = {
    'ubuntu-latest', 'ubuntu-26.04', 'ubuntu-24.04', 'ubuntu-22.04',
    'ubuntu-26.04-arm', 'ubuntu-24.04-arm', 'ubuntu-22.04-arm',
    'windows-latest', 'windows-2025', 'windows-2022',
    'windows-11-arm', 'windows-11-vs2026-arm',
    'macos-latest', 'macos-26', 'macos-15', 'macos-14',
    'macos-15-intel',
}
KEY = re.compile(r'^\s*(?:-\s+)?(runs-on|os|runner):\s*(.*?)\s*(?:#.*)?$')

bad = []
for path in sorted(Path('.github/workflows').glob('*.y*ml')):
    lines = path.read_text().splitlines()
    for number, line in enumerate(lines, 1):
        found = KEY.match(line)
        if not found:
            continue
        key, value = found.groups()
        if value.startswith('${{'):
            continue  # read from a matrix key checked where it is set
        if value == '':
            # A block list: the "- label" lines that follow.
            labels = []
            for following in lines[number:]:
                item = re.match(r'^\s*-\s+([^\s#:]+)\s*(?:#.*)?$', following)
                if not item:
                    break
                labels.append(item.group(1))
            if key == 'runs-on' and not labels:
                # runs-on: {group: ..., labels: ...} picks a runner group,
                # which is how larger and self-hosted runners are chosen.
                bad.append(f'{path}:{number}: runs-on: a runner group or labels mapping')
        else:
            labels = [label.strip().strip('\'"') for label in value.strip('[]').split(',')]
        for label in labels:
            if label and label not in STANDARD:
                bad.append(f'{path}:{number}: {key}: {label}')

if bad:
    sys.exit('Not a standard GitHub-hosted runner:\n' + '\n'.join(bad))
print('every workflow runs on standard GitHub-hosted runners')
