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
import time

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
    # A string that is appended to in a loop and read between appends by what
    # copies: what was read before never changes (spec/alchem-memory.md).
    'defmodule A do\n  def keep(out: string, kept: list[string], k: integer): list[string] do\n    if k == 0 do [out | kept] else\n      piece = if byte_size(out) > 2 do binary_part(out, 0, 3) else "abc" end\n      keep(out <> piece, [piece | kept], k - 1)\n    end\n  end\n\n  def whole(out: string, kept: list[string], k: integer): list[string] do\n    if k == 0 do kept else\n      all = binary_part(out, 0, byte_size(out))\n      whole(out <> "y", [all | kept], k - 1)\n    end\n  end\n\n  def mixed(out: string, kept: list[string], k: integer): list[string] do\n    if k == 0 do kept else\n      held = if rem(k, 3) == 0 do [out | kept] else kept end\n      b = if byte_size(out) > 0 do Binary.at(out, 0) else 1 end\n      mixed(out <> Binary.from_list([65 + rem(b + k, 26)]), held, k - 1)\n    end\n  end\n\n  def self(out: string, k: integer): string do\n    if k == 0 do out else self(out <> binary_part(out, 0, byte_size(out)), k - 1) end\n  end\n\n  def inner(out: string, k: integer): string do\n    if k == 0 do out else inner(out <> binary_part(out <> "!", byte_size(out), 1), k - 1) end\n  end\n\n  def caught(out: string, k: integer): string do\n    if k == 0 do out else\n      got = try do\n        binary_part(out, 5, 100000)\n      rescue\n        _ -> "r"\n      end\n      caught(out <> got, k - 1)\n    end\n  end\n\n  def lists(out: string, all: list[list[integer]], k: integer): list[list[integer]] do\n    if k == 0 do all else lists(out <> "q", [Binary.to_list(out) | all], k - 1) end\n  end\n\n  def sums(out: string, all: list[integer], k: integer): list[integer] do\n    if k == 0 do all else sums(out <> "q", [Crypto.crc32(out), Crypto.crc32(out) | all], k - 1) end\n  end\n\n  def main() do\n    IO.inspect(Enum.take(keep("", [], 400), 5) |> Enum.map(fn s -> byte_size(s) end))\n    ws = whole("s", [], 300)\n    IO.inspect(Enum.all?(Enum.with_index(Enum.reverse(ws)), fn {w, i} -> byte_size(w) == i + 1 and w == "s" <> String.duplicate("y", i) end))\n    ms = mixed("", [], 300)\n    IO.inspect(Enum.map(ms, fn s -> Crypto.crc32(s) end) |> Enum.sum())\n    IO.inspect(Enum.all?(Enum.zip(ms, tl(ms)), fn {long, short} -> String.starts_with?(long, short) end))\n    IO.inspect(byte_size(self("ab", 12)))\n    IO.inspect(inner("a", 50))\n    IO.inspect(caught("a", 20))\n    IO.inspect(Enum.map(lists("", [], 60), fn l -> length(l) end) |> Enum.sum())\n    IO.inspect(Enum.sum(sums("", [], 500)))\n    start = "base"\n    a = self(start, 3)\n    b = keep(start, [], 4)\n    IO.inspect({start, byte_size(a), Enum.count(b)})\n    folded = Enum.reduce(1..200, "", fn i, acc -> acc <> (if byte_size(acc) > 4 do binary_part(acc, byte_size(acc) - 2, 2) else to_string(i) end) end)\n    IO.inspect(Crypto.crc32(folded))\n  end\nend\n',
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
        # 400,000 appends with a read before each: a copy at each of them
        # would take most of a minute.
        (Path(top) / 'loop.alc').write_text('defmodule M do\n  def at(out: string, sum: integer, k: integer): integer do\n    if k == 0 do sum else at(out <> "x", sum + (if byte_size(out) > 0 do Binary.at(out, byte_size(out) - 1) + byte_size(binary_part(out, 0, 1)) else 0 end), k - 1) end\n  end\n\n  def main() do\n    IO.inspect(at("", 0, 400000))\n  end\nend\n')
        started = time.monotonic()
        loop = subprocess.run([str(alchem), 'run', 'loop.alc'], capture_output=True, text=True, cwd=top, env={'PATH': '/usr/bin:/bin', 'HOME': top}, timeout=600)
        assert (loop.returncode, loop.stdout) == (0, f'{399999 * 121}\n') and time.monotonic() - started < 15, (loop, time.monotonic() - started)
    print(f'binary: {len(held)} programs give what the pinned command gives, and the fixture\'s 5 tests pass')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--record':
        record(Path(sys.argv[2]).resolve())
    else:
        verify(Path(sys.argv[1]).resolve())
