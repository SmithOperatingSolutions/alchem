#!/usr/bin/env python3
"""An Alchem-written compiler must parse source and emit real native calls."""
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
from run import ROOT,FUNCTION_LIMIT,at_limit


def verify(frontend,backends,saved_compilers=None):
    basic='defmodule Example do\n def scale(x: integer): integer do x*6 end\n def main() do System.halt(scale(7)) end\nend\n'
    rng=random.Random(1717)
    valid=[(basic,42),('defmodule M do def main() do System.halt(42) end end',42)]
    for _ in range(32):
        a,b=rng.randrange(1,15),rng.randrange(1,15)
        valid.append((f'defmodule M do def f(x: integer, y: integer): integer do z=x*y\n z+1 end def main() do System.halt(f({a},{b})) end end',a*b+1))
    valid += [
        ('defmodule M do def f(x: integer): integer do if x < 0 do -x else x end end def main() do System.halt(f(-42)) end end',42),
        ('defmodule M do def f(x: integer): integer do if x == 7 do y=x*6\n y else z=x+1\n z end end def main() do System.halt(f(7)) end end',42),
        ('defmodule M do def f(a: integer,b: integer,c: integer,d: integer,e: integer,f: integer): integer do a-b+c-d+e-f end def main() do System.halt(f(90,10,3,2,1,40)) end end',42),
        ('defmodule M do def f(x: integer): integer do x*2 end def g(x: integer): integer do f(x)+f(x+1) end def main() do System.halt(g(10)) end end',42),
    ]
    valid += [
        ('defmodule M do def f(x: integer): integer do if x > 0 do f(x-1)+1 else 0 end end def main() do System.halt(f(42)) end end',42),
        ('defmodule M do def f(x: integer): integer do g(x)*2 end def g(x: integer): integer do x+1 end def main() do System.halt(f(20)) end end',42),
        ('defmodule M do def even(x: integer): integer do if x == 0 do 1 else odd(x-1) end end def odd(x: integer): integer do if x == 0 do 0 else even(x-1) end end def main() do System.halt(even(20)+41) end end',42),
    ]
    valid += [
        ('defmodule M do def main() do System.halt(f(7)) end def f(x: integer): integer do x*6 end end',42),
        ('# module comment\ndefmodule M do # header\n defp f(x: integer): integer do x*6 # body\n end def main() do System.halt(f(7)) end end # end\n',42),
    ]
    valid += [
        ('defmodule M do def main() do x=7\n if x < 8 do y=x*6\n System.halt(y) else System.halt(1) end end end',42),
        ('defmodule M do def f(x: integer): integer do if x == 0 do 42 else f(x-1) end end def main() do System.halt(f(254)) end end',42),
        ('defmodule M do '+''.join(f'def f{i}(): integer do 9223372036854775807 end ' for i in range(255))+'def main() do System.halt(f254()-9223372036854775765) end end',42),
    ]
    valid += [
        ('defmodule M do def main() do '+''.join(f'x{i}={i}\n' for i in range(16))+'System.halt(x15+27) end end',42),
        ('defmodule M do def f(x: integer): integer do if x == 0 do 42 else f(x) end end def main() do System.halt(f(0)) end end',42),
    ]
    for op in ['==','!=','<','<=','>','>=']:
        for a,b in [(-1,1),(1,-1),(42,42)]:
            expected=42 if eval(f'{a}{op}{b}') else 7
            valid.append((f'defmodule M do def f(x: integer,y: integer): integer do if x {op} y do 42 else 7 end end def main() do System.halt(f({a},{b})) end end',expected))
    with tempfile.TemporaryDirectory(prefix='alchem-source-compiler-') as directory:
        root=Path(directory);images=[]
        for index,backend in enumerate(backends):
            compiler=root/f'compiler-{index}'
            if saved_compilers is None:
                bootstrap=subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap-alchem-compiler.py'),'--language','functions','--frontend',str(frontend),'--backend',str(backend),'--output',str(compiler)],capture_output=True,timeout=120)
                assert bootstrap.returncode==0,bootstrap.stderr
            else:compiler=saved_compilers[index]
            images.append(compiler.read_bytes())
            for case,(source,expected) in enumerate(valid):
                result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==0 and not result.stderr,(source,result.returncode,result.stderr)
                assert result.stdout[:4]==b'\x7fELF' and len(result.stdout)>140,'expected generated function code'
                assert struct.unpack_from('<Q',result.stdout,96)[0]==len(result.stdout),'ELF size mismatch'
                target=root/'target';target.unlink(missing_ok=True);target.write_bytes(result.stdout);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
                assert (run.returncode,run.stdout,run.stderr)==(expected,b'',b''),(source,run.returncode,run.stderr)
                repeated=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
                assert repeated.stdout==result.stdout,'nondeterministic output'
                if index == 0:
                    # Independent upstream parser/types and existing native lowering.
                    source_path=root/'reference.alc';source_path.write_text(source)
                    lowered=subprocess.run([str(frontend),'--input',str(source_path),'--program'],capture_output=True,timeout=120)
                    assert lowered.returncode==0,('upstream source oracle',case,lowered.stderr)
                    ir=root/'reference.json';ir.write_bytes(lowered.stdout)
                    built=subprocess.run([str(backend),'--target','x86_64-unknown-linux-gnu','--input',str(ir),'--output',str(root/'reference')],capture_output=True,timeout=120)
                    assert built.returncode==0,built.stderr
                    reference=subprocess.run([str(root/'reference')],capture_output=True,timeout=120)
                    assert reference.returncode==expected,('upstream result oracle',case,reference)
            # The self-hosted profile exceeds the reference IR's 256-function cap.
            # Check its independent 65535-function boundary by executing the ELF.
            boundary='defmodule M do '+''.join(f'def f{i}(): integer do 9223372036854775807 end ' for i in range(FUNCTION_LIMIT-1))+f'def main() do System.halt(f{FUNCTION_LIMIT-2}()-9223372036854775765) end end'
            # (Once for each distinct compiler: these are the longest compiles of the gate.)
            fresh=images[-1] not in images[:-1]
            result=at_limit([str(compiler)],input=boundary.encode() if fresh else basic.encode(),capture_output=True,env={'PATH':''},timeout=600)
            assert result.returncode==0 and not result.stderr,('65535 functions',result.stderr)
            target=root/'boundary';target.unlink(missing_ok=True);target.write_bytes(result.stdout);target.chmod(0o700)
            run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
            assert (run.returncode,run.stdout,run.stderr)==(42,b'',b''),('65535 functions execution',run)
            repeated=at_limit([str(compiler)],input=boundary.encode() if fresh else basic.encode(),capture_output=True,env={'PATH':''},timeout=600)
            assert repeated.stdout==result.stdout,'65535 functions determinism'
            invalid=[basic.replace('scale(7)','missing(7)'),basic.replace('x*6','y*6'),basic.replace('scale(7)','scale()'),basic.replace('x: integer','x: boolean'),basic+'trailing',basic.replace(' end\nend','\nend'),basic.replace('System.halt(scale(7))','System.halt(9223372036854775808)')]
            invalid += [
                basic.replace('x: integer','x: integer, x: integer'),
                basic.replace('def main()','defp main()'),
                basic.replace('def main()','def main(x: integer)'),
                basic.replace('x*6','if x == 7 do 42 else missing(x) end'),
                basic.replace('x*6','if x do 42 else 1 end'),
                basic.replace('x*6','if x == 7 do y=42\n y else 1 end\n y'),
                basic.replace('x*6','if x == 7 do true else 1 end'),
                basic.replace('x*6','if x == 7 do 42 end'),
                basic.replace('x*6','x=1\n x'),
                basic.replace('x*6','if=1\n x'),
                basic.replace('x*6','main=1\n x'),
                basic.replace('scale(7)','scale(7,)'),
            ]
            for source in invalid:
                if len(source)>1000000 and not fresh:continue
                result=at_limit([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=600) if len(source)>1000000 else subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==65 and not result.stdout and result.stderr,(source,result)
            errors=[
                'defmodule M do def main() do System.halt(256) end end',
                'defmodule M do def main() do System.halt(-1) end end',
                'defmodule M do def f(x: integer): integer do if x == 0 do 42 else 0+f(x+1) end end def main() do System.halt(f(1)) end end',
            ]
            for source in errors:
                result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==0 and not result.stderr,result
                target=root/'limited';target.unlink(missing_ok=True);target.write_bytes(result.stdout);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
                # A status outside 0..255 and calls nested past the depth limit stop
                # (0+f(x+1): a call that is the function's whole value would loop, harness/tail_calls.py)
                # the program with status 2 and a trace, as in the pinned runtime.
                want=b'<stdin>:1:20: call depth exceeded\n  at M.f (<stdin>:1)\n' if 'f(x+1)' in source else b'<stdin>:1:30: exit status must be between 0 and 255\n  at M.main (<stdin>:1)\n'
                assert (run.returncode,run.stdout)==(2,b'') and run.stderr.startswith(want),run
        assert images[0]==images[1],'bootstrap backend mismatch'
    print(f'PASS Alchem-written source compiler: {len(valid)} programs, {len(invalid)} rejections, {len(errors)} runtime limits per backend; real helpers/parameters/locals, deterministic native ELF, empty PATH')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve(),[Path(p).resolve() for p in sys.argv[2:]])
