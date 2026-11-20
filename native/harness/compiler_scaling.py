#!/usr/bin/env python3
"""Compile larger modules and byte packs through the saved Alchem compiler."""
from pathlib import Path
from source_syntax import native_bytes
import struct
import subprocess
import sys
import tempfile
from run import ROOT


def fixtures():
    many='defmodule M do '+''.join(f'def f{i}(x: integer): integer do x+1 end ' for i in range(32))+'def main() do System.halt(f31(41)) end end'
    padding=''.join('# '+('padding '*10)+'\n' for _ in range(64))
    pack='defmodule M do def pack(x: integer): list[integer] do ['+','.join('x' for _ in range(128))+'] end def main() do System.halt(Enum.count(pack(1))-86) end end'
    # Nonconstant pack values force substantial native code; constants may optimize.
    wide='defmodule M do '+''.join(f'def f{i}(x: integer): list[integer] do ['+','.join('x' for _ in range(128))+'] end ' for i in range(24))+'def main() do System.halt(Enum.count(f23(1))-86) end end'
    return [('larger-source',many+padding,False),('pack128',pack,False),('wide-ELF',wide,True)]


def verify(frontend,backends):
    with tempfile.TemporaryDirectory(prefix='alchem-scaling-') as directory:
        root=Path(directory);images=[]
        for index,backend in enumerate(backends):
            compiler=root/f'compiler-{index}'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap-alchem-compiler.py'),'--language','functions','--frontend',str(frontend),'--backend',str(backend),'--output',str(compiler)],capture_output=True,timeout=120)
            assert result.returncode==0,result.stderr
            images.append(compiler.read_bytes())
            for name,source,wide in fixtures():
                result=subprocess.run([str(compiler)],input=native_bytes(source.encode()),capture_output=True,env={'PATH':''},timeout=120)
                assert result.returncode==0 and not result.stderr,(name,len(source),result.returncode,result.stderr)
                data=result.stdout
                assert struct.unpack_from('<Q',data,96)[0]==len(data),(name,'file size')
                if wide:assert len(data)>65535,(name,len(data))
                target=root/'target';target.write_bytes(data);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
                assert (run.returncode,run.stdout,run.stderr)==(42,b'',b''),(name,run)
                repeat=subprocess.run([str(compiler)],input=native_bytes(source.encode()),capture_output=True,env={'PATH':''},timeout=120)
                assert repeat.stdout==data,(name,'determinism')
        assert images[0]==images[1],'backend mismatch'
    print('PASS compiler scaling: larger source/functions, computed128 pack and ELF beyond64KiB per backend')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve(),[Path(p).resolve() for p in sys.argv[2:]])
