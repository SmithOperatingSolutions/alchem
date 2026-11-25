#!/usr/bin/env python3
"""Typed options, extraction scopes and option-returning native APIs."""
from pathlib import Path
from source_syntax import native_bytes
import subprocess
import random
from native_memory import profile,TraceUnavailable
import sys
import tempfile
from self_hosted_components import verify_legacy_program as verify_program


def verify(compiler):
    valid=[
        ('','value=some(42)\nSystem.halt(case value do some(answer) -> answer none -> 7 end)',42),
        ('defp empty(): option[integer] do none end ','System.halt(case empty() do some(answer) -> answer none -> 42 end)',42),
        ('def pick(v: option[integer]): integer do case v do some(x) -> x none -> 42 end end ','System.halt(pick(none))',42),
        ('def f(n: integer): option[integer] do if n == 0 do some(42) else f(n-1) end end ','System.halt(case f(20) do some(x) -> x none -> 1 end)',42),
        ('def f(a: boolean): option[integer] do if a do none else some(42) end end ','System.halt(case f(false) do some(x) -> x none -> 1 end)',42),
        ('def f(): option[boolean] do some(false) end ','x=case f() do some(value) -> not value none -> false end\nif x do System.halt(42) else System.halt(1) end',42),
        ('def f(): option[list[integer]] do some([42]) end ','value=case f() do some(x) -> x none -> [] end\nSystem.halt(Enum.at(value,0,0))',42),
        ('def f(): option[string] do some("Alchem") end ','s=case f() do some(x) -> x none -> "" end\nSystem.halt(byte_size(s)+36)',42),
    ]
    valid += [('','System.halt(case some(7) do none -> 42 some(x) -> x end)',7),('def empty(): option[integer] do none end ','System.halt(case empty() do none -> 42 some(x) -> x end)',42)]
    for data,index,expected in [('[]',0,42),('[7]',0,7),('[0]',0,0),('[255]',0,255),('[0,42]',1,42),('[42]',-1,42),('[42]',-2,42),('[42]',-(1<<63),42),('[42]',(1<<63)-1,42)]:
        valid.append(('',f'System.halt(case Enum.at({data},{index}) do some(value) -> value none -> 42 end)',expected))
    for name in ['first','last']:
        for data,expected in [('[]',42),('[7]',7),('[7,9]',7 if name=='first' else 9)]:
            valid.append(('',f'System.halt(case List.{name}({data}) do some(value) -> value none -> 42 end)',expected))
            valid.append(('',f'System.halt(List.{name}({data},42))',expected))
    valid.append(('', 'System.halt(case Enum.fetch([7],0) do some(value) -> value none -> 42 end)',7))
    rng=random.Random(171121)
    for value in [0,-(1<<63),(1<<63)-1]+[rng.randrange(-(1<<63),(1<<63)) for _ in range(48)]:
        valid.append(('',f'System.halt(case some({value}) do some(x) -> if x == {value} do 0 else 1 end none -> 2 end)',0))
    for _ in range(48):
        data=[rng.randrange(256) for _ in range(rng.randrange(12))];index=rng.randrange(-15,15);normal=index+len(data) if index<0 else index
        expected=data[normal] if 0<=normal<len(data) else 99
        valid.append(('',f'System.halt(case Enum.at({data},{index}) do some(x) -> x none -> 99 end)',expected))
    with tempfile.TemporaryDirectory(prefix='alchem-options-') as d:
        root=Path(d)
        for number,(helpers,body,status) in enumerate(valid):verify_program('defmodule M do '+helpers+'def main() do '+body+' end end',compiler,root,('option',number),status)
        bad=[
            ('def f(): option[integer] do some("x") end ','System.halt(0)'),
            ('def f(): integer do none end ','System.halt(0)'),
            ('def f(v: option[integer]): integer do 0 end ','System.halt(f(some(false)))'),
            ('','System.halt(case some(1) do some(x) -> x none -> true end)'),
            ('','System.halt(case some(1) do some(x) -> x none -> x end)'),
            ('','System.halt(case some(1) do some(x) -> x end)'),
            ('','if some(false) do System.halt(0) else System.halt(1) end'),
            ('','System.halt(case none do some(x) -> x none -> 0 end)'),
        ]
        for helpers,body in bad:
            result=subprocess.run([str(compiler)],input=native_bytes(('defmodule M do '+helpers+'def main() do '+body+' end end').encode()),capture_output=True,env={'PATH':''},timeout=15)
            assert result.returncode==65 and not result.stdout,('option rejection',helpers,body,result.returncode,result.stderr)
        measured=0
        for expression,charge in [(': option[integer] = none',0),('some(0)',16),('some(false)',16),(': option[list[integer]] = some([])',16),('Enum.at([7],0)',32),('Enum.at([7],1)',16),(': option[integer] = List.first([])',8),('String.first("")',0),('String.first("a")',32),('String.length("e\\xcc\\x81")',0),('String.slice("abc",0,0)',8)]:
            # A value of open type takes it from the binding's annotation.
            source=('defmodule M do def main() do value'+(expression if expression.startswith(':') else '='+expression)+'\nSystem.halt(0) end end').encode()
            built=subprocess.run([str(compiler)],input=native_bytes(source),capture_output=True,env={'PATH':''},timeout=120)
            assert built.returncode==0,built.stderr
            target=root/'arena';target.unlink(missing_ok=True);target.write_bytes(built.stdout);target.chmod(0o700)
            try:
                status,data,errors,charged=profile(target,b'')
                assert (status,data,errors,charged)==(0,b'',b'',charge),(expression,charged,charge)
                measured+=1
            except TraceUnavailable:print('SKIP option/grapheme arena: ptrace unavailable')
    print(f'Option/grapheme arena measurements: {measured}/11')
    print(f'PASS {len(valid)} typed option programs and {len(bad)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
