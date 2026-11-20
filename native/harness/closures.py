#!/usr/bin/env python3
"""Anonymous functions, captured bindings and calls through function values."""
from pathlib import Path
import subprocess
import sys
import tempfile

# (helpers, main body, stdout, status): outcomes equal the pinned upstream `alchem run`.
CASES=[
    ('def adder(offset: integer): fn[integer, integer] do fn(value: integer): integer do value + offset end end '
     'def twice(f: fn[integer, integer], x: integer): integer do f(f(x)) end def inc(n: integer): integer do n + 1 end ',
     'add_ten = adder(10)\nIO.puts(Integer.to_string(add_ten(5)))\nIO.puts(Integer.to_string(add_ten.(7)))\nIO.puts(Integer.to_string(twice(add_ten, 1)))\n'
     'IO.puts(Integer.to_string(twice(&inc, 40)))\nSystem.halt(0)',b'15\n17\n21\n42\n',0),
    ('def greeter(greeting: string): fn[string, string] do punctuation = "!"\n fn(name: string): string do greeting <> ", " <> name <> punctuation end end ',
     'hello = greeter("hello")\nbye = greeter("bye")\nIO.puts(hello("world"))\nIO.puts(bye("now"))\nIO.puts(hello("again"))\nSystem.halt(0)',b'hello, world!\nbye, now!\nhello, again!\n',0),
    ('','scale = 3\nIO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2, 3], fn(n: integer): integer do n * scale end))))\n'
     'IO.puts(Integer.to_string(Enum.reduce([1, 2, 3], 0, fn(n: integer, acc: integer): integer do acc + n * scale end)))\nSystem.halt(0)',b'18\n18\n',0),
    # Unannotated lambdas take parameter types from the callee and the result from the body.
    ('def adder(offset: integer): fn[integer, integer] do fn value -> value + offset end end def label(n: integer): string do if n < 0 do "negative" else "other" end end ',
     'add = adder(10)\nIO.puts(Integer.to_string(add(5)))\nIO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2, 3], fn n -> n * n end))))\n'
     'IO.puts(Integer.to_string(Enum.reduce([1, 2, 3], 0, fn n, acc -> acc + n end)))\nIO.puts(Integer.to_string(Enum.sum(Enum.filter([1, 2, 3, 4], fn n -> n > 2 end))))\n'
     'IO.puts(Enum.join(Enum.map([0, -3, 7], fn n -> label(n) end), ","))\nIO.puts(Enum.join(Enum.map(["a", "bb"], fn s -> s <> "!" end), " "))\nSystem.halt(0)',
     b'15\n14\n6\n7\nother,negative,other\na! bb!\n',0),
    ('def apply(value: integer, f: fn[integer, integer]): integer do f(value) end def both(a: integer, b: integer, f: fn[integer, integer, integer]): integer do f(a, b) end ',
     'scale = 5\nIO.puts(Integer.to_string(apply(8, fn x -> x * scale end)))\nIO.puts(Integer.to_string(both(3, 4, fn a, b -> a * b + scale end)))\n'
     'IO.puts(Integer.to_string(apply(1, fn x ->\n doubled = x * 2\n if doubled > 1 do doubled + 40 else 0 end\n end)))\nSystem.halt(0)',b'40\n17\n42\n',0),
    # Lambdas nest, capture through each other and may run output statements.
    ('','base = 100\nnested = Enum.map([1, 2], fn n -> Enum.sum(Enum.map([10, 20], fn m -> m * n + base end)) end)\nIO.puts(Integer.to_string(Enum.sum(nested)))\n'
     'loud = fn(n: integer): integer do\n IO.puts("called")\n n + base\n end\nIO.puts(Integer.to_string(loud(1) + loud(2)))\nSystem.halt(0)',b'490\ncalled\ncalled\n203\n',0),
    ('def make(a: integer, b: string, c: boolean): fn[integer] do fn(): integer do if c do a + byte_size(b) else 0 end end end ',
     'thunk = make(40, "ab", true)\nSystem.halt(thunk())',b'',42),
    ('def six(f: fn[integer, integer, integer, integer, integer, integer, integer]): integer do f(1, 2, 3, 4, 5, 6) end ',
     'offset = 21\nSystem.halt(six(fn a, b, c, d, e, f -> a + b + c + d + e + f + offset end))',b'',42),
    # A function value passed on, stored and returned keeps its captures.
    ('def compose(f: fn[integer, integer], g: fn[integer, integer]): fn[integer, integer] do fn(x: integer): integer do g(f(x)) end end ',
     'k = 2\ndouble = fn(x: integer): integer do x * k end\nplus = fn(x: integer): integer do x + k end\nboth = compose(double, plus)\nagain = compose(both, both)\n'
     'IO.puts(Integer.to_string(both(5)))\nIO.puts(Integer.to_string(again(5)))\nSystem.halt(0)',b'12\n26\n',0),
    ('def count(n: integer, f: fn[integer, integer]): integer do if n == 0 do 0 else f(n) + count(n - 1, f) end end ',
     'step = 2\nSystem.halt(count(6, fn n -> n * step end))',b'',42),
    # Captures: &(...) and &name(...) with &1.. as parameters; references with an arity.
    ('def adder(offset: integer): fn[integer, integer] do &(&1 + offset) end def inc(n: integer): integer do n + 1 end def pair(a: integer, b: integer): integer do a * 10 + b end '
     'def label(n: integer): string do Integer.to_string(n) end defp hid(n: integer): integer do n + 7 end def zero(): integer do 7 end def call0(f: fn[integer]): integer do f() end ',
     'IO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2], &(&1 * 2)))))\nIO.puts(Integer.to_string(Enum.reduce([1, 2, 3], 0, &(&1 + &2))))\n'
     'IO.puts(Integer.to_string(Enum.sum(Enum.map(["a", "bb"], &String.length(&1)))))\nIO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2], &inc(&1) + 5))))\n'
     'IO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2], &inc/1)) + Enum.sum(Enum.map([1, 2], &M.inc)) + Enum.sum(Enum.map([1, 2], &M.inc(&1)))))\n'
     'IO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2], &hid/1))))\nIO.puts(Integer.to_string(Enum.reduce([1, 2, 3], 0, &pair(&2, &1))))\n'
     'IO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2], &(& 1 * &1)))))\nIO.puts(Integer.to_string(Enum.sum(Enum.filter([1, 2, 3, 4], &(&1 > 2)))))\n'
     'IO.puts(Enum.join(Enum.map(["a", "b"], &(&1 <> "&2")), ","))\nIO.puts(Enum.join(Enum.map([1, 2], &label(&1 * 2) <> "x"), ","))\n'
     'IO.puts(Integer.to_string(Enum.reduce([1, 2, 3], 10, &(if &1 > 1 do &2 + &1 else &2 end))))\nIO.puts(Integer.to_string(call0(&zero/0) + call0(&zero) + call0(fn -> 5 end)))\n'
     'g = adder(1)\nIO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2], &g.(&1))) + Enum.sum(Enum.map([1, 2], &g(&1))) + Enum.sum(Enum.map([1, 2], adder(5)))))\nSystem.halt(0)',
     b'6\n6\n3\n15\n15\n17\n123\n5\n7\na&2,b&2\n2x,4x\n15\n19\n23\n',0),
    ('def six(f: fn[integer, integer, integer, integer, integer, integer, integer]): integer do f(1, 2, 3, 4, 5, 6) end ',
     'offset = 21\nSystem.halt(six(&(&1 + &2 + &3 + &4 + &5 + &6 + offset)))',b'',42),
    # Library functions and builtins by arity: &String.length/1 is &String.length(&1).
    ('def lens(): fn[string, integer] do &String.length/1 end ',
     'f = lens()\ng: fn[string, integer] = &String.length/1\npad: fn[string, integer, string] = &String.pad_leading/2\npid: fn[string] = &System.pid/0\nsep = "x"\n'
     'IO.puts(Integer.to_string(Enum.sum(Enum.map(["a", "bb"], &String.length/1)) + f("abc") + g("abcd") + Enum.sum(Enum.map(["a", "bb"], &byte_size/1))))\n'
     'IO.puts(Enum.join(Enum.map([1, 22], &Integer.to_string/1), ",") <> pad("a", 3))\nIO.puts(Integer.to_string(Enum.sum(Enum.map([[1], [2, 3]], &Enum.sum/1))))\n'
     'IO.puts(Enum.join(Enum.map(["a", "b"], &String.upcase / 1), sep))\n'
     'IO.puts(Integer.to_string(Enum.sum(Enum.map([["a"], ["bb"]], fn l -> Enum.sum(Enum.map(l, &String.length/1)) end))))\nSystem.halt(if pid() == "" do 1 else 0 end)',
     b'13\n1,22  a\n6\nAxB\n3\n',0),
    # A capture may hold a fn, and a fn a capture.
    ('','IO.puts(Integer.to_string(Enum.sum(Enum.map([[1], [2]], &(Enum.sum(Enum.map(&1, fn x -> x * 2 end)))))))\n'
     'IO.puts(Integer.to_string(Enum.sum(Enum.map([[1], [2]], fn l -> Enum.sum(Enum.map(l, &(&1 * 2))) end))))\nSystem.halt(0)',b'6\n6\n',0),
    # Lambdas in any argument position; arguments still run left to right.
    ('def apply(f: fn[integer, integer], x: integer): integer do f(x) end def both(f: fn[integer, integer], g: fn[integer, integer], x: integer): integer do g(f(x)) end '
     'def mixed(f: fn[integer, integer], s: string, g: fn[string, string]): string do g(s) <> Integer.to_string(f(1)) end def inc(n: integer): integer do n + 1 end ',
     'k = 5\nIO.puts(Integer.to_string(apply(fn x -> x + 1 end, 1) + apply(&(&1 + 1), 1)))\nIO.puts(Integer.to_string(both(fn x -> x + 1 end, &(&1 * 3), 1)))\n'
     'IO.puts(Integer.to_string(both(&(&1 * k), fn x -> x + k end, inc(1))))\nIO.puts(mixed(&(&1 + 1), "s" <> "t", fn s -> s <> "!" end))\n'
     'IO.puts(mixed(fn x -> x * 9 end, String.upcase("ab"), &String.reverse(&1)))\n'
     'IO.puts(Integer.to_string(both(fn x ->\n IO.puts("f")\n x + 1 end, fn x ->\n IO.puts("g")\n x * 2 end, apply(fn x ->\n IO.puts("arg")\n x end, 3))))\n'
     'h = fn(f: fn[integer, integer], x: integer): integer do f(x) end\nIO.puts(Integer.to_string(h(&(&1 * 4), 2) + h.(fn x -> x end, 1)))\nSystem.halt(0)',
     b'4\n6\n15\nst!2\nBA9\narg\nf\ng\n8\n9\n',0),
    # A function-valued call result is called at once.
    ('def adder(offset: integer): fn[integer, integer] do fn value -> value + offset end end def mk(): fn[integer, fn[integer, integer]] do fn a -> fn b -> a * b end end end ',
     'm = mk()\nIO.puts(Integer.to_string(adder(10)(5) + adder(10).(5)))\nIO.puts(Integer.to_string(mk()(6)(7)))\nIO.puts(Integer.to_string(m(6).(7) + m.(2)(3)))\n'
     'IO.puts(Integer.to_string(adder(1)(adder(2)(3))))\nSystem.halt(0)',b'30\n42\n48\n6\n',0),
    # Annotated bindings; the annotation gives a lambda its types.
    ('def adder(offset: integer): fn[integer, integer] do fn value -> value + offset end end ',
     'x: integer = 41\ny: string = "s"\nz: option[integer] = none\nl: list[integer] = []\nf: fn[integer, integer] = fn n -> n + 1 end\ng: fn[integer, integer] = &(&1 * 2)\n'
     'h: fn[integer, integer] = adder(3)\ni: fn[integer, integer] = &adder(1).(&1)\nIO.puts(Integer.to_string(x + 1 + Enum.count(l)) <> y)\n'
     'IO.puts(Integer.to_string(f(1) + g(2) + h(1) + i(1)))\nIO.puts(Integer.to_string(if true do\n w: integer = 4\n w + 1 else 0 end))\nSystem.halt(0)',b'42s\n12\n5\n',0),
]
# Rejected natively, as the pinned compiler does, except one native limit:
# lambdas take at most six parameters.
REJECTIONS=[
    ('','f = fn x -> x + 1 end\nSystem.halt(f(1))','unannotated lambda without a typed context'),
    ('','f = &(&1 + 1)\nSystem.halt(f(1))','capture without a typed context'),
    ('','f = fn(x: integer): integer do x end\nSystem.halt(f("a"))','wrong argument type'),
    ('','f = fn(x: integer): integer do x end\nSystem.halt(f(1, 2))','wrong argument count'),
    ('','f = fn(x: integer): string do x end\nSystem.halt(0)','body does not match the declared result'),
    ('','x = 1\nSystem.halt(x(1))','calling a non-function'),
    ('','n = 100\nsame = fn(n: integer): integer do n + 1 end\nSystem.halt(same(1))','parameter shadows an outer binding'),
    ('','System.halt(Enum.sum(Enum.map([1, 2], fn s -> missing(s) end)))','undefined function in a lambda body'),
    ('def apply(x: integer, f: fn[integer, integer]): integer do f(x) end ','System.halt(apply(1, fn a, b -> a end))','wrong lambda arity'),
    ('def apply(f: fn[integer, integer], x: integer): integer do f(x) end ','System.halt(apply(fn a, b -> a end, 1))','wrong arity in the first argument'),
    ('def apply(f: integer, x: integer): integer do f + x end ','System.halt(apply(fn a -> a end, 1))','lambda for a parameter that is not a function'),
    ('','System.halt(Enum.sum(Enum.map([1, 2], fn s -> byte_size(s) end)))','lambda body mistyped for the element'),
    ('def make(): fn[integer, integer] do fn(s: string): integer do 1 end end ','System.halt(0)','lambda does not match the declared function type'),
    ('','System.halt(Enum.sum(Enum.map([1, 2], &(&2))))','placeholder beyond the expected parameters'),
    ('','System.halt(Enum.reduce([1, 2, 3], 0, &(&1)))','capture with too few placeholders'),
    ('','System.halt(Enum.sum(Enum.map([1, 2], &(7))))','capture without a placeholder'),
    ('','System.halt(Enum.sum(Enum.map([[1], [2]], &(Enum.sum(Enum.map(&1, &(&1 * 2)))))))','nested captures'),
    ('','System.halt(Enum.sum(Enum.map([1, 2], &(Enum.sum(Enum.map([1], fn x -> x * &1 end))))))','placeholder inside a nested fn'),
    ('','System.halt(Enum.sum(Enum.map([[1], [2]], &(Enum.sum(Enum.map(&1, fn x -> Enum.sum(Enum.map([x], &(&1 * 3))) end))))))','capture inside a fn inside a capture'),
    ('','System.halt(&1)','placeholder outside a capture'),
    ('def inc(n: integer): integer do n + 1 end ','System.halt(Enum.sum(Enum.map([1, 2], &inc/2)))','reference with the wrong arity'),
    ('def inc(n: integer): integer do n + 1 end ','x = &inc(5)\nSystem.halt(0)','capture call without a placeholder'),
    ('','System.halt(Enum.sum(Enum.map([1, 2], &missing/1)))','reference to an undefined function'),
    ('','x = some(fn x -> x end)\nSystem.halt(0)','lambda where no function type is expected'),
    ('','x = some(&(&1))\nSystem.halt(0)','capture where no function type is expected'),
    ('def adder(offset: integer): fn[integer, integer] do fn value -> value + offset end end ','f = adder(10)\n(5)\nSystem.halt(f(1))','call parenthesis on the next line'),
    ('def adder(offset: integer): fn[integer, integer] do fn value -> value + offset end end ','System.halt(adder(10)(5, 6))','wrong count calling a call result'),
    ('','x: integer = "a"\nSystem.halt(0)','annotated binding of another type'),
    ('','f: integer = fn x -> x + 1 end\nSystem.halt(0)','lambda bound to a non-function annotation'),
    ('','f: fn[integer, string] = fn x -> x + 1 end\nSystem.halt(0)','lambda result against its annotation'),
    ('','x = 1\nx: integer = 2\nSystem.halt(0)','annotated rebinding'),
    ('','f = &String.length/1\nSystem.halt(f("abc"))','library reference without a typed context'),
    ('','System.halt(Enum.sum(Enum.map(["a", "bb"], &String.length/2)))','library reference with another arity than expected'),
    ('','System.halt(byte_size(Enum.reduce(["a", "bb"], "", &String.replace/3)))','library reference with more parameters than expected'),
    ('','System.halt(Enum.sum(Enum.map(["a"], &String.nope/1)))','reference to an unknown library function'),
    ('','System.halt(Enum.sum(Enum.map(["a"], &String.length)))','library reference without an arity'),
    ('','System.halt(Enum.sum(Enum.map([["a"], ["bb"]], &(Enum.sum(Enum.map(&1, &String.length/1))))))','library reference inside a capture'),
]

def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-closures-') as d:
        root=Path(d)
        def compiled(helpers,body):
            return subprocess.run([str(compiler)],input=('defmodule M do '+helpers+'def main() do '+body+' end end').encode(),capture_output=True,env={'PATH':''},timeout=120)
        for helpers,body,stdout,status in CASES:
            result=compiled(helpers,body)
            assert (result.returncode,result.stderr)==(0,b''),(body[:120],result.returncode,result.stderr)
            assert compiled(helpers,body).stdout==result.stdout,'closure determinism'
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,b''),(body[:120],run)
        # Closure records come from the arena; unbounded recursion through a value stops at the call depth limit
        # (0 + spin: a call that is the function's whole value would loop instead).
        for helpers,body,status in [
            ('def grow(n: integer, acc: integer): integer do if n == 0 do acc else f = fn(x: integer): integer do x + n end\n grow(n - 1, f(acc)) end end ','System.halt(grow(200, 0) - 20058)',42),
            ('def spin(n: integer, f: fn[integer, integer]): integer do 0 + spin(f(n), f) end ','System.halt(spin(0, fn x -> x + 1 end))',2)]:
            result=compiled(helpers,body)
            assert (result.returncode,result.stderr)==(0,b''),(body,result.returncode)
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(result.stdout);out.chmod(0o700)
            run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout)==(status,b''),(body,run.returncode)
            assert run.stderr==b'' if status!=2 else run.stderr.split(b'\n')[:2]==[b'<stdin>:1:138: call depth exceeded',b'  at M.spin (<stdin>:1)'],(body,run.stderr[:120])
        for helpers,body,label in REJECTIONS:
            result=compiled(helpers,body)
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
    print(f'PASS closures: {len(CASES)} programs with annotated and inferred lambdas, & captures and references, lambdas in any argument, calls of call results, annotated bindings, arena and frame limits, {len(REJECTIONS)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
