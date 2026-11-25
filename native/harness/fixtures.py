#!/usr/bin/env python3
"""The repository's own programs: alchem takes each the Go compiler takes.

tests/fixtures, the suite the Go compiler's CI runs, passes under `alchem
test`. Every program of tests/fixtures and examples that imports nothing is
accepted by `alchem check`, but those the fixtures hold to be refused. And a
reference to a builtin of one type (&String.reverse, Builtins of
compiler/syntax/builtins.go) needs neither its arity nor an expected type.
"""
from concurrent.futures import ThreadPoolExecutor
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
TESTS = 125
# A reference, a call of it, and what inspect writes of the result.
REFERENCES = [
    ('String.reverse', '"ab"', '"ba"'), ('Float.from_integer', '1', '1.0'), ('Float.to_string', '1.5', '"1.5"'),
    ('Float.floor', '1.5', '1.0'), ('Float.ceil', '1.5', '2.0'), ('Float.parse', '"1.5"', 'ok(1.5)'),
    ('File.exists', '"nope"', 'false'), ('System.env', '"ALCHEM_NOPE"', 'none'), ('String.starts_with', '"ab", "a"', 'true'),
    ('File.remove', '"nope"', 'error("remove nope: no such file or directory")'), ('File.list', '"nope"', 'error("open nope: no such file or directory")'),
    ('File.write', '"nope/x", "y"', 'error("open nope/x: no such file or directory")'), ('File.append', '"nope/x", "y"', 'error("open nope/x: no such file or directory")'),
    ('String.ends_with', '"ab", "b"', 'true'), ('String.replace', '"ab", "a", "c"', '"cb"')]


# A regex goes through generic functions, in a list, a map and a struct.
REGEXES = '''defmodule M do
  struct R do
    r: regex
  end

  def id(a: a): a do
    a
  end

  def main() do
    IO.inspect(Enum.any?([~r/a/, ~r/b/], fn r -> Regex.match?(r, "b") end))
    IO.inspect(Regex.source(List.first!([~r/x+/])))
    IO.inspect(Regex.match?(Map.fetch!(%{"k" => ~r/a/}, "k"), "cat"))
    IO.inspect(Regex.source(id(~r/y/)))
    IO.inspect(Regex.source(id(%R{r: ~r/z/}).r))
    IO.inspect(Enum.map([~r/a/, ~r/b/], &Regex.source/1))
  end
end
'''


def verify(compiler):
    spec = spec_from_file_location('build_alchem', ROOT / 'scripts/build-alchem.py')
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix='alchem-fixtures-') as top:
        base = Path(top).resolve()
        alchem = base / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(base)}

        def check(path):
            done = subprocess.run([str(alchem), 'check', str(path)], capture_output=True, text=True, env=env, timeout=600)
            return path, done.returncode, done.stdout + done.stderr
        alone = [path for folder in ('tests/fixtures', 'examples') for path in sorted((REPOSITORY / folder).rglob('*.alc')) if 'import "' not in path.read_text()]
        assert len(alone) > 80, len(alone)
        with ThreadPoolExecutor(4) as pool:
            for path, status, said in pool.map(check, alone):
                assert status == 0, (str(path), said)
        work = base / 'references'
        work.mkdir()
        for name, arguments, shown in REFERENCES:
            body = [f'f = &{name}', f'IO.inspect(f({arguments}))', f'g = &{name}/{1 + arguments.count(", ")}', f'IO.inspect(g({arguments}))']
            (work / 'm.alc').write_text('defmodule M do\n  def main() do\n' + ''.join(f'    {line}\n' for line in body) + '  end\nend\n')
            done = subprocess.run([str(alchem), 'run', 'm.alc'], capture_output=True, text=True, cwd=work, env=env, timeout=600)
            assert (done.returncode, done.stdout, done.stderr) == (0, f'{shown}\n{shown}\n', ''), (name, done)
        # A branch with a list that starts with none takes its type from the
        # other branch.
        held = ['a = if true do [none, some(1)] else [some(2)] end', 'b = case 1 do\n      1 -> [none]\n      _ -> [some(2)]\n    end',
                'c = cond do\n      true -> [none, some(1.5)]\n      true -> [some(1.0)]\n    end', 'd = try do\n      [none]\n    rescue\n      _ -> [some("x")]\n    end',
                'e = if false do [some(:a)] else [none] end', 'IO.inspect({a, b, c, d, e})']
        (work / 'm.alc').write_text('defmodule M do\n  def main() do\n' + ''.join(f'    {line}\n' for line in held) + '  end\nend\n')
        done = subprocess.run([str(alchem), 'run', 'm.alc'], capture_output=True, text=True, cwd=work, env=env, timeout=600)
        assert (done.returncode, done.stdout, done.stderr) == (0, '{[none, some(1)], [none], [none, some(1.5)], [none], [none]}\n', ''), done
        (work / 'm.alc').write_text(REGEXES)
        done = subprocess.run([str(alchem), 'run', 'm.alc'], capture_output=True, text=True, cwd=work, env=env, timeout=600)
        assert (done.returncode, done.stdout, done.stderr) == (0, 'true\n"x+"\ntrue\n"y"\n"z"\n["a", "b"]\n', ''), done
        shutil.copytree(REPOSITORY / 'tests/fixtures', base / 'fixtures')
        tests = subprocess.run([str(alchem), 'test', 'fixtures'], capture_output=True, text=True, cwd=base, env=env, timeout=1800)
        counted = re.search(r'^(\d+) tests, 0 failures$', tests.stdout, re.M)
        assert tests.returncode == 0 and counted and int(counted.group(1)) >= TESTS, (tests.returncode, tests.stdout[-3000:], tests.stderr[-1000:])
    print(f'fixtures: {counted.group(1)} tests pass, {len(alone)} programs are accepted, {len(REFERENCES)} builtins are referred to')


if __name__ == '__main__':
    import sys
    verify(Path(sys.argv[1]).resolve())
