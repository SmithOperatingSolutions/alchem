#!/usr/bin/env python3
"""Check the machine code of processes against its reference.

spec/processes-x86_64.s holds, part by part, the instructions whose bytes
implementations/alchem/native-processes.alc keeps as literals. This
assembles each part (binutils) and fails unless its bytes stand in that
file. Nothing is generated: the literals are written by hand, a few
instructions each; normal builds never run this."""
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def assemble(text):
    with tempfile.TemporaryDirectory() as d:
        source=Path(d)/'part.s';source.write_text('.intel_syntax noprefix\n.text\n'+text+'\n')
        subprocess.run(['as','-o',f'{d}/part.o',str(source)],check=True)
        subprocess.run(['objcopy','-O','binary','-j','.text',f'{d}/part.o',f'{d}/part.bin'],check=True)
        return (Path(d)/'part.bin').read_bytes()


def parts():
    name=None;lines=[]
    for line in (ROOT/'spec/processes-x86_64.s').read_text().split('\n'):
        head=re.fullmatch(r'# == (\w+)',line)
        if head:
            if name:yield name,'\n'.join(lines)
            name=head[1];lines=[]
        elif name and not line.startswith('#'):lines.append(line)
    if name:yield name,'\n'.join(lines)


if __name__=='__main__':
    held=re.sub(r'\s','',(ROOT/'implementations/alchem/native-processes.alc').read_text())
    # As the Linux compiler has it: what only Windows adds is b[] there.
    windows=(ROOT/'implementations/alchem/native-windows.alc').read_text()
    for name in ('nw_stack_keep','nw_stack_teb'):
        assert re.search(r'def '+name+r'\(\): bytes do\n    if nc_win\(\) == 0 do b\[\] else',windows),name
        held=held.replace(f'+Enum.count({name}())','')
        held=re.sub(r'\]\)?,'+name+r'\(\),b\[',',',held)
    held=held.replace('nc_sc()','5')
    for name,text in parts():
        code=','.join(map(str,assemble(text)))
        if code not in held:sys.exit(f'{name}: the bytes {code} are not in native-processes.alc')
        print(f'{name}: {len(code.split(","))} bytes')
