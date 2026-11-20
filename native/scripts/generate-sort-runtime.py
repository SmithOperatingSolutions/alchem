#!/usr/bin/env python3
"""Regenerate the checked sort runtime literals; not used by normal builds.

spec/sort-stable-x86_64.s and spec/sort-unstable-x86_64.s are the reference
(gcc's output for spec/sort-runtime.c, with -DSTABLE for the first; the
flags are in the files' headers). Only binutils is needed here."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_parse_runtime',ROOT/'scripts/generate-parse-runtime.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)


def body(text):
    return ''.join(line+'\n' for line in text.split('\n') if line.startswith('  def ') and 'def main()' not in line)


def generate():
    stable=shared.assemble((ROOT/'spec/sort-stable-x86_64.s').read_text())
    unstable=shared.assemble((ROOT/'spec/sort-unstable-x86_64.s').read_text())
    text=('defmodule NativeSortData do\n  # Generated from spec/sort-stable-x86_64.s and spec/sort-unstable-x86_64.s.\n'
          +body(shared.module_text('X','so',stable,'',''))+body(shared.module_text('X','sp',unstable,'',''))
          +'  # Native smoke test; generated sort runtime.\n  def main() do System.halt(0) end\nend\n')
    return text,len(stable),len(unstable)


if __name__=='__main__':
    text,stable,unstable=generate()
    (ROOT/'implementations/alchem/native-sort-data.alc').write_text(text)
    print(f'Sort runtime: {stable} and {unstable} bytes')
