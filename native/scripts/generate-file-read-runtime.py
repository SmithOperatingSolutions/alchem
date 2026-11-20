#!/usr/bin/env python3
"""Regenerate the checked File.read runtime literal; not used by normal builds."""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_parse_runtime',ROOT/'scripts/generate-parse-runtime.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)


def generate():
    messages=[m.encode() for m in json.loads((ROOT/'spec/errno-messages.json').read_text())['messages']]
    assert all(len(m)<256 for m in messages)
    packed=b''.join(bytes([len(m)])+m for m in messages)
    library=(ROOT/'spec/library-x86_64.s').read_text()
    # The UTF-8 width macro is shared with the stdin readers.
    macro=library[library.index('.macro utf8_width'):]
    macro=macro[:macro.index('.endm')+len('.endm')]
    asm=(ROOT/'spec/file-read-x86_64.s').read_text()
    assert 'ERRNO_COUNT' in asm and '# ERRNO_DATA' in asm and '# UTF8_WIDTH' in asm
    asm=asm.replace('# UTF8_WIDTH',macro).replace('ERRNO_COUNT',str(len(messages)))
    asm=asm.replace('# ERRNO_DATA','\n'.join(' .byte '+','.join(map(str,packed[i:i+32])) for i in range(0,len(packed),32)))
    raw,found=shared.assemble_sites(asm)
    text=shared.module_text('NativeFileData','fr',raw,'Generated from spec/file-read-x86_64.s and spec/errno-messages.json.','generated File.read runtime',found)
    return text,len(raw)


if __name__=='__main__':
    text,size=generate()
    (ROOT/'implementations/alchem/native-file-data.alc').write_text(text)
    print(f'File.read runtime: {size} bytes')
