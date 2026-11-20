#!/usr/bin/env python3
"""Regenerate the collector's literal from spec/memory-x86_64.s; optional development step only."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def generate():
    with tempfile.TemporaryDirectory(prefix='alchem-memory-runtime-') as d:
        root=Path(d);obj=root/'runtime.o';binary=root/'runtime.bin'
        # --stress: the testing variant (see STRESS in the source); never committed.
        stress=['--defsym','STRESS=1'] if '--stress' in sys.argv else []
        subprocess.run(['as','--64',*stress,'-o',str(obj),str(ROOT/'spec/memory-x86_64.s')],check=True)
        subprocess.run(['objcopy','-O','binary','-j','.text',str(obj),str(binary)],check=True)
        data=binary.read_bytes()
        # The twelve jumps the entry's words address must be five bytes each.
        assert all(data[i]==0xe9 for i in range(0,60,5)),data[:60]
        parts=[data[i:i+128] for i in range(0,len(data),128)]
        pieces=['defmodule NativeMemoryData do\n  # Generated from spec/memory-x86_64.s by scripts/generate-memory-runtime.py.\n']
        for index,part in enumerate(parts):
            pieces.append(f'  def gm_part_{index}(): bytes do b['+','.join(map(str,part))+'] end\n')
        def join(first,stop):
            if stop-first==1:return f'gm_part_{first}()'
            middle=(first+stop)//2
            return 'Enum.concat('+join(first,middle)+','+join(middle,stop)+')'
        pieces.append('  def gm_blob(): bytes do '+join(0,len(parts))+' end\n')
        pieces.append('  # Native smoke test; generated collector.\n  def main() do System.halt(0) end\nend\n')
        return ''.join(pieces),len(data)


def generate_arm64():
    """The ARM64 collector (spec/arm64.md), native-memory-data-arm64.alc."""
    sys.path.insert(0,str(ROOT/'scripts'))
    import arm64_runtime
    data,symbols=arm64_runtime.assemble_with_symbols((ROOT/'spec/memory-x86_64.s').read_text(),['STRESS'] if '--stress' in sys.argv else [])
    # The twelve branches the entry's words address, four bytes each.
    assert all(data[i+3]&0xfc==0x14 for i in range(0,48,4)),data[:48]
    # Its x86-64 system call routine, which translated functions call too
    # (the word at 0x400420, spec/arm64.md).
    return arm64_runtime.module_text('NativeMemoryDataArm64','ga_blob',data,'spec/memory-x86_64.s',[('ga_syscall',symbols['x86_syscall'])]),len(data)


def generate_darwin():
    """The collector for macOS (spec/darwin-arm64.md), native-memory-data-darwin.alc:
    its system call routine calls libSystem."""
    sys.path.insert(0,str(ROOT/'scripts'))
    import arm64_runtime
    data,symbols=arm64_runtime.assemble_with_symbols((ROOT/'spec/memory-x86_64.s').read_text(),['PIC','DARWIN'])
    assert all(data[i+3]&0xfc==0x14 for i in range(0,48,4)),data[:48]
    return arm64_runtime.module_text('NativeMemoryDataDarwin','gd_blob',data,'spec/memory-x86_64.s',[('gd_syscall',symbols['x86_syscall'])]),len(data)


if __name__=='__main__' and '--darwin' in sys.argv:
    text,size=generate_darwin()
    (ROOT/'implementations/alchem/native-memory-data-darwin.alc').write_text(text)
    print(f'{size} bytes (macOS)')
elif __name__=='__main__':
    text,size=generate()
    (ROOT/'implementations/alchem/native-memory-data.alc').write_text(text)
    print(f'{size} bytes')
    text,size=generate_arm64()
    (ROOT/'implementations/alchem/native-memory-data-arm64.alc').write_text(text)
    print(f'{size} bytes (ARM64)')
