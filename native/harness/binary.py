#!/usr/bin/env python3
"""Binary, Crypto.crc32 and File.sync (issue #130).

tests/fixtures/binary_test.alc, which the Go compiler's own tests run, is run
by `alchem test`, and each program here gives the status, the output and the
message the pinned command gives (harness/binary-cases.json).

    binary.py --record PINNED   write binary-cases.json from the pinned command line
"""
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'harness/binary-cases.json'
FIXTURE = ROOT.parent / 'tests/fixtures/binary_test.alc'


def main_of(*lines):
    return 'defmodule Main do\n  def main() do\n' + ''.join(f'    {line}\n' for line in lines) + '  end\nend\n'


PROGRAMS = [
    # Every byte, every size and order, the numbers at their edges.
    main_of('every = Enum.to_list(0..255)', 'data = Binary.from_list(every)', 'IO.inspect(byte_size(data))',
            'IO.inspect(Binary.to_list(data) == every)', 'IO.inspect(Enum.sum(Enum.map(every, fn i -> Binary.at(data, i) end)))'),
    main_of('Enum.each([1, 2, 4, 8], fn size ->', '  Enum.each([:big, :little], fn order ->',
            '    Enum.each([0, 1, 2, 127, 128, 254, 255], fn n ->', '      IO.inspect(Binary.to_list(Binary.encode(n, size, order)))',
            '      IO.inspect(Binary.decode("ab" <> Binary.encode(n, size, order) <> "c", 2, size, order))', '    end)', '  end)', 'end)'),
    main_of('Enum.each([9223372036854775807, -9223372036854775807 - 1, -1, -256, 72623859790382856], fn n ->',
            '  IO.inspect(Binary.to_list(Binary.encode(n, 8, :big)))', '  IO.inspect(Binary.to_list(Binary.encode(n, 8, :little)))',
            '  IO.inspect(Binary.decode(Binary.encode(n, 8, :big), 0, 8, :big))',
            '  IO.inspect(Binary.decode(Binary.encode(n, 8, :big), 0, 8, :little))', 'end)'),
    main_of('IO.inspect(Binary.encode(65535, 2, :big))', 'IO.inspect(Binary.encode(4294967295, 4, :little))',
            'IO.inspect(Binary.decode("\\xff\\xff\\xff\\xff", 0, 4, :big))', 'IO.inspect(Binary.decode("\\xff\\xfe", 0, 2, :little))'),
    main_of('IO.inspect(Binary.from_list(65..70))', 'IO.inspect(Binary.from_list(Stream.map([1, 2], fn n -> n + 64 end)))',
            'IO.inspect(Binary.from_list([]))', 'IO.inspect(Binary.to_list(""))', 'IO.inspect(Enum.map(Binary.to_list("hé"), fn b -> b end))'),
    # What fails, each with its message and trace.
    *[main_of('IO.puts("before")', f'IO.inspect({call})') for call in (
        'Binary.at("abc", 3)', 'Binary.at("abc", -1)', 'Binary.at("", 0)', 'Binary.from_list([1, 256])', 'Binary.from_list([-1])',
        'Binary.encode(256, 1, :big)', 'Binary.encode(-1, 4, :big)', 'Binary.encode(4294967296, 4, :little)', 'Binary.encode(1, 3, :big)',
        'Binary.encode(1, 2, :middle)', 'Binary.decode("abc", 2, 2, :big)', 'Binary.decode("abc", -1, 1, :big)',
        'Binary.decode("abc", 9223372036854775807, 8, :big)', 'Binary.decode("abc", 0, 0, :big)', 'Binary.decode("abc", 0, 1, :none)')],
    # What the checker refuses.
    *[main_of(f'IO.inspect({call})') for call in ('Binary.at(1, 1)', 'Binary.from_list(["a"])', 'Binary.encode(1, 2, "big")', 'Binary.size("a")', 'File.sync(1)')],
    'defmodule Binary do\n  def main() do\n    IO.puts("x")\n  end\nend\n',
    main_of('IO.inspect(Crypto.crc32(""))', 'IO.inspect(Crypto.crc32("123456789"))', 'IO.inspect(Crypto.crc32(String.duplicate("\\x00\\xff", 5000)))',
            'IO.inspect(Enum.map(0..255, fn b -> Crypto.crc32(Binary.from_list([b])) end) |> Enum.sum())'),
    main_of('File.write!("a.txt", "kept")', 'IO.inspect(File.sync("a.txt"))', 'IO.inspect(File.sync("."))', 'IO.inspect(File.sync("none.txt"))',
            'ok(file) = File.open("a.txt", [:write])', 'IO.write(file, "new")', 'IO.inspect(File.sync(file))', 'IO.inspect(File.close(file))',
            'IO.inspect(File.sync(file))', 'IO.inspect(File.read("a.txt"))'),
]


def run(command, text, pinned=False):
    """[status, output, message] of `command run main.alc`."""
    with tempfile.TemporaryDirectory(prefix='alchem-binary-') as top:
        root = Path(top).resolve()
        (root / 'home').mkdir()
        (root / 'main.alc').write_text(text)
        env = dict(os.environ, HOME=str(root / 'home')) if pinned else {'PATH': '/usr/bin:/bin', 'HOME': str(root / 'home')}
        done = subprocess.run([str(command), 'run', 'main.alc'], capture_output=True, cwd=root, env=env, timeout=600)
        return [done.returncode] + [out.decode('utf8', 'replace').replace(str(root) + os.sep, '') for out in (done.stdout, done.stderr)]


def record(pinned):
    held = [run(pinned, text, True) for text in PROGRAMS]
    CASES.write_text(json.dumps(held, indent=1) + '\n')
    print(f'wrote {CASES.name}: {len(held)} programs, {sum(1 for h in held if h[0])} fail or are refused')


def verify(compiler):
    held = json.loads(CASES.read_text())
    assert len(held) == len(PROGRAMS), 'harness/binary-cases.json is not of these programs: run harness/binary.py --record'
    spec = spec_from_file_location('build_alchem', ROOT / 'scripts/build-alchem.py')
    builder = module_from_spec(spec)
    spec.loader.exec_module(builder)
    with tempfile.TemporaryDirectory(prefix='alchem-binary-') as top:
        alchem = Path(top).resolve() / 'alchem'
        builder.build(compiler, alchem, builder.platform_of(compiler).startswith('darwin/'))
        for text, expected in zip(PROGRAMS, held):
            seen = run(alchem, text)
            assert seen == expected, (text, seen, expected)
        (Path(top) / 'binary_test.alc').write_bytes(FIXTURE.read_bytes())
        tests = subprocess.run([str(alchem), 'test', 'binary_test.alc'], capture_output=True, text=True, cwd=top, env={'PATH': '/usr/bin:/bin', 'HOME': top}, timeout=600)
        assert tests.returncode == 0 and '\n5 tests, 0 failures\n' in tests.stdout, tests
    print(f'binary: {len(held)} programs give what the pinned command gives, and the fixture\'s 5 tests pass')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--record':
        record(Path(sys.argv[2]).resolve())
    else:
        verify(Path(sys.argv[1]).resolve())
