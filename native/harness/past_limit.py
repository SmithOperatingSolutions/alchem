#!/usr/bin/env python3
"""Programs of more than 65,535 functions (spec/source-capacity.md, "Limits
that remain"). A record of the compiler's table was named by a number of
two bytes, in the record of its module, in an environment and in the plans
the compiler's parts hand each other; it is three bytes now. Each program
here has 66,000 functions before its own, so that every function, struct
and sum type it declares has a number past the old limit, and does what it
does without them:

- calls, a function of several clauses, a struct and a sum type made,
  matched and printed, a fn that holds a binding, a reference, a generic
  function and library calls, in one module;
- a module declared after the 66,000, imported and called, so that the
  number of a record's module is past the limit too;
- a macro expanded in such a program: a program with a macro, a template
  or a protocol took memory by the square of its functions (the arena at
  32,000) and nested calls three deep for each;
- a file of tests with more records than two bytes count is refused, where
  it ended the compiler.
"""
from pathlib import Path
import subprocess
import sys
import tempfile

from run import at_limit

FILL = 66000

ONE = '''  struct P do
    x: integer
    y: integer
  end
  type Shape do
    circle(r: integer)
    rect(w: integer, h: integer)
  end
  def add(a: integer, b: integer): integer do
    a + b
  end
  def fact(0): integer do
    1
  end
  def fact(n: integer): integer do
    n * fact(n - 1)
  end
  def area(s: Shape): integer do
    case s do
      Shape.circle(r) -> r * r * 3
      Shape.rect(w, h) -> w * h
    end
  end
  def pair(a: a, b: b): tuple[b, a] do
    {b, a}
  end
  def main() do
    p = %P{x: 1, y: 2}
    f = fn(v: integer): integer do add(v, p.x) end
    IO.puts(Integer.to_string(add(3, 4) + zz65999() + fact(5) + f(10)))
    IO.inspect(Enum.map([1, 2], &add(&1, p.y)))
    IO.inspect(Enum.map([1, 2], &fact/1))
    IO.inspect(%P{p | y: 5})
    IO.inspect({area(Shape.circle(2)), area(Shape.rect(2, 3)), pair(1, "a")})
    IO.inspect(Enum.sort(Map.keys(%{"b" => 1, "a" => 2})))
    case p do
      %P{x: 1, y: y} -> IO.puts("y is #{y}")
      _ -> IO.puts("other")
    end
  end
'''
ONE_OUT = b'66137\n[3, 4]\n[1, 2]\n%P{x: 1, y: 5}\n{12, 6, {"a", 1}}\n["a", "b"]\ny is 2\n'

MACRO = '''  defmacro twice(e) do
    quote do
      unquote(e) + unquote(e)
    end
  end
  def main() do
    IO.puts(Integer.to_string(twice(zz65999() + 1)))
  end
'''


def fill(indent='  '):
    return ''.join(f'{indent}def zz{i}(): integer do\n{indent}  {i}\n{indent}end\n' for i in range(FILL))


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-past-limit-') as top:
        def ran(source, what):
            built = at_limit([str(compiler)], input=source.encode(), capture_output=True, env={'PATH': ''}, timeout=900)
            assert (built.returncode, built.stderr) == (0, b''), (what, built.returncode, built.stderr[:200])
            program = Path(top) / 'program'
            program.unlink(missing_ok=True)
            program.write_bytes(built.stdout)
            program.chmod(0o700)
            done = subprocess.run([str(program)], capture_output=True, env={'PATH': ''}, timeout=120)
            return done.returncode, done.stdout, done.stderr
        assert ran('defmodule M do\n' + fill() + ONE + 'end\n', 'one module') == (0, ONE_OUT, b''), 'one module'
        two = ('defmodule App do\n  import "module:Late"\n' + fill() + '  def main() do\n    IO.puts(Integer.to_string(Late.twice(zz65999()) + Late.one()))\n  end\nend\n'
               'defmodule Late do\n  def twice(n: integer): integer do\n    n * 2\n  end\n  def one(): integer do\n    1\n  end\nend\n')
        assert ran(two, 'a module after them') == (0, b'%d\n' % (65999 * 2 + 1), b''), 'a module after them'
        assert ran('defmodule M do\n' + fill() + MACRO + 'end\n', 'a macro') == (0, b'%d\n' % (66000 * 2), b''), 'a macro'
        tests = 'defmodule T do\n' + ''.join(f'  test "t{i}" do\n    assert(1 == 1)\n  end\n' for i in range(FILL)) + 'end\n'
        refused = at_limit([str(compiler)], input=tests.encode(), capture_output=True, env={'PATH': ''}, timeout=900)
        assert (refused.returncode, refused.stdout) == (65, b''), ('66,000 tests', refused.returncode)
    print(f'PASS past the limit: {FILL} functions before a program of one module, of two, and of one with a macro; {FILL} tests in a file refused')


if __name__ == '__main__':
    verify(Path(sys.argv[1]).resolve())
