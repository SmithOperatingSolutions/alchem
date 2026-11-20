#!/usr/bin/env python3
"""Regenerate the checked Integer.parse runtime literal; not used by normal builds."""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def packed_ranges():
    ranges=json.loads((ROOT/'spec/print-ranges.json').read_text())['ranges']
    packed=bytearray();previous=127
    for start,end in ranges:
        assert previous<start<=end<=0x10ffff and end-start<(1<<17),(start,end)
        packed.extend((start|((end-start)<<21)).to_bytes(5,'little'));previous=end
    # Lookup reads eight bytes per entry.
    return len(ranges),bytes(packed)+b'\0'*3


def assemble(asm):
    with tempfile.TemporaryDirectory(prefix='alchem-runtime-generation-') as d:
        root=Path(d);source=root/'runtime.s';obj=root/'runtime.o';binary=root/'runtime.bin';source.write_text(asm)
        subprocess.run(['as','--64','-o',str(obj),str(source)],check=True)
        subprocess.run(['objcopy','-O','binary','-j','.text',str(obj),str(binary)],check=True)
        return binary.read_bytes()


def module_text(module,prefix,raw,comment,smoke):
    """Checked literals in grouped functions; PREFIX_blob() returns the whole routine."""
    pieces=[];names=[]
    for i in range(0,len(raw),384):
        name=f'{prefix}_part_{i//384}';names.append(name)
        items=['b['+','.join(map(str,raw[j:min(j+128,i+384)]))+']' for j in range(i,min(i+384,len(raw)),128)]
        expression=items[0] if len(items)==1 else 'nc_join('+','.join(items+['b[]']*(3-len(items)))+')'
        pieces.append(f'  def {name}(): bytes do {expression} end\n')
    level=0
    while len(names)>1:
        merged=[]
        for i in range(0,len(names),3):
            group=names[i:i+3];name=f'{prefix}_group_{level}_{i//3}';merged.append(name)
            args=[part+'()' for part in group]+['b[]']*(3-len(group))
            pieces.append(f'  def {name}(): bytes do nc_join('+','.join(args)+') end\n')
        names=merged;level+=1
    return (f'defmodule {module} do\n  # {comment}\n'+''.join(pieces)+
            f'  def {prefix}_blob(): bytes do '+names[0]+'() end\n'
            f'  # Native smoke test; {smoke}.\n  def main() do System.halt(0) end\nend\n')


def generate():
    count,packed=packed_ranges()
    asm=(ROOT/'spec/integer-parse-x86_64.s').read_text()
    assert 'PRINT_RANGE_COUNT' in asm and '# PRINT_DATA' in asm
    asm=asm.replace('PRINT_RANGE_COUNT',str(count)).replace('# PRINT_DATA','\n'.join(' .byte '+','.join(map(str,packed[i:i+32])) for i in range(0,len(packed),32)))
    raw=assemble(asm)
    return module_text('NativeParseData','ip',raw,'Generated from spec/integer-parse-x86_64.s and spec/print-ranges.json.','generated Integer.parse runtime'),len(raw)


if __name__=='__main__':
    text,size=generate()
    (ROOT/'implementations/alchem/native-parse-data.alc').write_text(text)
    print(f'Integer.parse runtime: {size} bytes')
