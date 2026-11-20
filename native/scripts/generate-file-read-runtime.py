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
    raw,_=shared.assemble_sites(asm)
    # The Windows compiler's has errors in Windows' words (WINDOWS defined,
    # spec/windows.md); the Linux one stays as it was.
    windows,found=shared.assemble_sites('.set WINDOWS,1\n'+asm)
    def parts(prefix,code):
        text=shared.module_text('NativeFileData',prefix,code,'','')
        body=text[text.index('\n',text.index('\n')+1)+1:text.index(f'  def {prefix}_blob()')]
        top=text[text.index(f'  def {prefix}_blob(): bytes do ')+len(f'  def {prefix}_blob(): bytes do '):]
        return body,top[:top.index(' end\n')]
    linux_body,linux_top=parts('fr',raw)
    windows_body,windows_top=parts('frw',windows)
    text=('defmodule NativeFileData do\n  # Generated from spec/file-read-x86_64.s and spec/errno-messages.json.\n'
          +linux_body+windows_body
          +f'  def fr_blob(): bytes do if nc_win() == 1 do {shared.windows_sites.wrap(windows_top,found)} else {linux_top} end end\n'
          '  # Native smoke test; generated File.read runtime.\n  def main() do System.halt(0) end\nend\n')
    return text,len(raw)


if __name__=='__main__':
    text,size=generate()
    (ROOT/'implementations/alchem/native-file-data.alc').write_text(text)
    print(f'File.read runtime: {size} bytes')
