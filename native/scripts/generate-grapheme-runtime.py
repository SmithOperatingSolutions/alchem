#!/usr/bin/env python3
"""Regenerate checked Alchem runtime literals; not used by normal builds."""
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def generate():
    data=json.loads((ROOT/'spec/grapheme-ranges.json').read_text());ranges=data['ranges']
    packed=bytearray()
    for start,end,kind in ranges:
        assert 0<=start<=end<=0x10ffff and 0<kind<16 and end-start<2048
        packed.extend((start+(kind<<21)+((end-start)<<25)).to_bytes(5,'little'))
    packed.extend(b'\0'*3)
    asm=(ROOT/'spec/graphemes-x86_64.s').read_text()
    assert 'mov r9d,613' in asm and len(ranges)==613
    asm=asm.replace('# GRAPHEME_DATA','\n'.join('.byte '+','.join(map(str,packed[i:i+32])) for i in range(0,len(packed),32)))
    with tempfile.TemporaryDirectory(prefix='alchem-grapheme-generation-') as d:
        root=Path(d);source=root/'runtime.s';obj=root/'runtime.o';binary=root/'runtime.bin';source.write_text(asm)
        subprocess.run(['as','--64','-o',str(obj),str(source)],check=True)
        subprocess.run(['objcopy','-O','binary','-j','.text',str(obj),str(binary)],check=True)
        raw=binary.read_bytes()
    pieces=[];names=[]
    for i in range(0,len(raw),384):
        name=f'ng_part_{i//384}';names.append(name);items=[]
        for j in range(i,min(i+384,len(raw)),128):items.append('b['+','.join(map(str,raw[j:min(j+128,i+384)]))+']')
        expression=items[0] if len(items)==1 else 'nc_join('+','.join(items+['b[]']*(3-len(items)))+')'
        pieces.append(f'  def {name}(): bytes do {expression} end\n')
    level=0
    while len(names)>1:
        merged=[]
        for i in range(0,len(names),3):
            group=names[i:i+3];name=f'ng_group_{level}_{i//3}';merged.append(name)
            args=[part+'()' for part in group]+['b[]']*(3-len(group))
            pieces.append(f'  def {name}(): bytes do nc_join('+','.join(args)+') end\n')
        names=merged;level+=1
    pieces.append('  def ng_blob(): bytes do '+names[0]+'() end\n')
    target=ROOT/'implementations/alchem/native-grapheme-data.alc'
    target.write_text('defmodule NativeGraphemeData do\n  # Generated Unicode 17.0.0 runtime; regenerate with scripts/generate-grapheme-runtime.py.\n'+''.join(pieces)+'  # Native smoke test; assembled with the compiler.\n  def main() do System.halt(0) end\nend\n')
    print('Generated',len(raw),'runtime bytes in',len(pieces),'Alchem functions')


if __name__=='__main__':generate()
