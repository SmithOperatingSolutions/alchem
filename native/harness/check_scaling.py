#!/usr/bin/env python3
"""alchem check and alchem fmt take a large file in time and memory that
grow as the file does (spec/source-capacity.md, "The alchem command").

A module of 4,000 functions and one of 16,000, each function calling the
one before it, a note above every third and an @doc on every fifth, written
as the formatter writes it:

- `alchem fmt --check` finds nothing to change, so every function, note and
  @doc is where it was written: the parser gathers them last first and
  turns them round;
- `alchem check` takes both, and `alchem run` of the smaller prints its sum;
- four times the functions take less than eight times the time (they took
  fourteen times: lists were searched and copied for every function, in
  the parser, the checker's passes and the formatter), and 16,000 take
  less than 2.5 GiB (they took 4.5; 1.2 now).
"""
import os
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def module(count):
    parts = ['defmodule Many do\n']
    for i in range(count):
        if i:
            parts.append('\n')
        if i % 3 == 0:
            parts.append(f'  # The sum up to {i}.\n')
        if i % 5 == 0:
            parts.append(f'  @doc """\n  Adds {i}.\n  """\n')
        parts.append(f'  def f{i}(n: integer): integer do\n    {f"f{i - 1}(n) + {i}" if i else "n"}\n  end\n')
    parts.append(f'\n  def main() do\n    IO.puts(Integer.to_string(f{count - 1}(1)))\n  end\nend\n')
    return ''.join(parts)


def verify(compiler):
    spec = spec_from_file_location('build_alchem', ROOT / 'scripts/build-alchem.py')
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix='alchem-check-scaling-') as top:
        alchem = Path(top) / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))

        def run(*arguments):
            """(status, standard output and error, seconds, the most memory in bytes)."""
            started = time.monotonic()
            child = subprocess.Popen([str(alchem), *arguments], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=top, env={'PATH': '', 'HOME': top})
            said = child.stdout.read()
            _, status, usage = os.wait4(child.pid, 0)
            return os.waitstatus_to_exitcode(status), said, time.monotonic() - started, usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024)

        taken = {}
        for count in (4000, 16000):
            file = Path(top) / f'many{count}.alc'
            file.write_text(module(count))
            status, said, _, _ = run('fmt', '--check', file.name)
            assert (status, said) == (0, b''), (count, 'fmt --check', status, said[:200])
            status, said, seconds, memory = run('check', file.name)
            assert (status, said) == (0, b''), (count, 'check', status, said[:200])
            taken[count] = (seconds, memory)
        status, said, _, _ = run('run', 'many4000.alc')
        assert (status, said) == (0, b'%d\n' % (1 + sum(range(4000)))), ('run', status, said[:200])
        (small, _), (large, memory) = taken[4000], taken[16000]
        assert large < 8 * small + 2, f'16,000 functions took {large:.1f} s and 4,000 {small:.1f} s: more than eight times'
        assert memory < 5 << 29, f'16,000 functions took {memory >> 20} MiB'
    print(f'PASS check scaling: alchem fmt and check of 4,000 and 16,000 functions with notes and @doc; check {small:.1f} s and {large:.1f} s, {memory >> 20} MiB')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
