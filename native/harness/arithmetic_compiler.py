#!/usr/bin/env python3
"""Compile once; runtime Alchem parses new source and emits executable ELF."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from encoder import validate_elf
from run import ROOT

COMPILE=b'E_COMPILE: invalid expression or result outside 0..255\n'
LIMIT=b'E_RUNTIME_INPUT: input exceeds byte limit\n'


def verify(frontend,compilers):
    with tempfile.TemporaryDirectory(prefix='alchem-arithmetic-compiler-') as directory:
        root=Path(directory);binaries=[]
        for index,backend in enumerate(compilers):
            compiler=root/f'compiler-{index}'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap-alchem-compiler.py'),'--frontend',str(frontend),'--backend',str(backend),'--output',str(compiler)],capture_output=True,timeout=120)
            assert result.returncode==0,result.stderr
            binaries.append(compiler.read_bytes())
            assert compiler.stat().st_mode&0o111,'compiler is not executable'
            rng=random.Random(17017)
            valid=[(str(v).encode(),v) for v in range(256)]
            valid += [(b'6*7\n',42),(b'(5+2)*6',42),(b'100-60-1',39),(b'2+3*4',14),(b'-(-42)',42),(b'9223372036854775807+9223372036854775807+44',42),(b'0'+b' '*127,0)]
            for _ in range(64):
                a,b=rng.randrange(1,16),rng.randrange(1,16)
                valid.append((f'({a}+{b})*3'.encode(),(a+b)*3))
            before=compiler.read_bytes()
            for source,expected in valid:
                result=subprocess.run([str(compiler)],input=source,capture_output=True,timeout=120,env={'PATH':''})
                assert (result.returncode,result.stderr)==(0,b''),(source,result.returncode,result.stderr)
                validate_elf(result.stdout,expected)
                repeat=subprocess.run([str(compiler)],input=source,capture_output=True,timeout=120,env={'PATH':''})
                assert result.stdout==repeat.stdout,'nondeterministic image'
                target=root/'program';target.unlink(missing_ok=True);target.write_bytes(result.stdout);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,timeout=120,env={'PATH':''})
                assert (run.returncode,run.stdout,run.stderr)==(expected,b'',b''),(source,run)
            invalid=[b'',b' ',b'1+',b'1 2',b'nope',b'1/2',b'256',b'-1',b'9223372036854775808',b'\0',b'\xff',b'('*17+b'1'+b')'*17]
            for source in invalid+[b'0'+b' '*128]:
                result=subprocess.run([str(compiler)],input=source,capture_output=True,timeout=120,env={'PATH':''})
                diagnostic=LIMIT if len(source)>128 else COMPILE
                assert (result.returncode,result.stdout,result.stderr)==(65,b'',diagnostic),(source,result)
            assert compiler.read_bytes()==before,'compiler modified itself'
            # A failed bootstrap never replaces an existing compiler artifact.
            failed=subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap-alchem-compiler.py'),'--frontend',str(frontend),'--backend','/bin/false','--output',str(compiler)],capture_output=True,timeout=120)
            assert failed.returncode!=0 and compiler.read_bytes()==before,'failed bootstrap replaced compiler'
            component=ROOT/'implementations/alchem/compiler.alc';original=component.read_bytes()
            failed=subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap-alchem-compiler.py'),'--frontend',str(frontend),'--backend',str(backend),'--output',str(component)],capture_output=True,timeout=120)
            assert failed.returncode!=0 and component.read_bytes()==original,'source overwrite not rejected'
        assert binaries[0]==binaries[1],'Go/Rust bootstrap differs'
    print(f'PASS standalone Alchem compiler: {len(valid)} runtime inputs and {len(invalid)+1} rejections per backend; deterministic ELF executed with empty PATH')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve(),[Path(p).resolve() for p in sys.argv[2:]])
