#!/usr/bin/env python3
"""Regenerate the checked String.upcase/downcase/capitalize runtime literal; not used by normal builds."""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_parse_runtime',ROOT/'scripts/generate-parse-runtime.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)


def packed(ranges):
    out=bytearray();previous=-1
    for start,end,stride,delta in ranges:
        assert previous<=start<=end<=0x10ffff and end-start<256 and stride in (1,2) and (end-start)%stride==0 and -65536<=delta<65536,(start,end,stride,delta)
        out.extend((start|((end-start)<<21)|((stride-1)<<29)|((delta+65536)<<30)).to_bytes(6,'little'));previous=start
    return bytes(out)


def data(raw):
    return '\n'.join(' .byte '+','.join(map(str,raw[i:i+32])) for i in range(0,len(raw),32))


def generate():
    tables=json.loads((ROOT/'spec/case-ranges.json').read_text())
    library=(ROOT/'spec/library-x86_64.s').read_text()
    # The UTF-8 width macro is shared with the stdin readers.
    macro=library[library.index('.macro utf8_width'):]
    macro=macro[:macro.index('.endm')+len('.endm')]
    asm=(ROOT/'spec/case-map-x86_64.s').read_text()
    for marker in ['# UTF8_WIDTH','UPPER_COUNT','LOWER_COUNT','TITLE_COUNT','# UPPER_DATA','# LOWER_DATA','# TITLE_DATA']:assert marker in asm,marker
    asm=asm.replace('# UTF8_WIDTH',macro).replace('UPPER_COUNT',str(len(tables['upper']))).replace('LOWER_COUNT',str(len(tables['lower']))).replace('TITLE_COUNT',str(len(tables['title'])))
    # Lookup reads eight bytes per six-byte entry.
    asm=asm.replace('# UPPER_DATA',data(packed(tables['upper']))).replace('# LOWER_DATA',data(packed(tables['lower']))).replace('# TITLE_DATA',data(packed(tables['title'])+b'\0\0'))
    raw=shared.assemble(asm)
    text=shared.module_text('NativeCaseData','cm',raw,'Generated from spec/case-map-x86_64.s and spec/case-ranges.json.','generated String case runtime')
    return text,len(raw)


if __name__=='__main__':
    text,size=generate()
    (ROOT/'implementations/alchem/native-case-data.alc').write_text(text)
    print(f'String case runtime: {size} bytes')
