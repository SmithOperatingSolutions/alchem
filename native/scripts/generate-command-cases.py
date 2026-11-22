#!/usr/bin/env python3
"""Regenerate harness/commands-cases.json.xz: the scenes of the commands
gate (harness/commands.py, SCENES) with what the pinned command line gives
in each. Not used by normal builds.

    generate-command-cases.py PINNED

PINNED is the pinned command line (build/dev/alchem-upstream.bin). Each
scene is run by it in a directory of its own: the status, standard output
and standard error of every command line are written, and the files the
directory holds at the end."""
from pathlib import Path
import json
import lzma
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'harness'))
import commands


def main(arguments):
    if len(arguments)!=1:raise SystemExit(__doc__)
    pinned=Path(arguments[0]).resolve();scenes=[]
    for name,files,lines in commands.SCENES:
        runs,left=commands.scene(pinned,files,lines)
        scenes.append({'name':name,'files':files,'lines':lines,'runs':runs,'left':left})
    commands.CASES.write_bytes(lzma.compress(json.dumps(scenes,sort_keys=True).encode(),preset=9))
    print(f'wrote {commands.CASES.relative_to(ROOT)}: {sum(len(s["lines"]) for s in scenes)} command lines in {len(scenes)} scenes, {commands.CASES.stat().st_size} bytes')


if __name__=='__main__':main(sys.argv[1:])
