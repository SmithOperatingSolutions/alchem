#!/usr/bin/env python3
"""Regenerate native library literals; optional development step only."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
NAMES=['na_base','na_digits','na_undigits','na_duplicate','na_join','na_clock','na_pid','na_filter','na_write','na_read_all','na_read_line','na_argv','na_get_env','na_str_eq','na_count','na_split','na_replace','na_valid','na_trim','na_trim_leading','na_trim_trailing','na_str_cmp','na_pad']


def generate():
    with tempfile.TemporaryDirectory(prefix='alchem-collection-runtime-') as d:
        root=Path(d);obj=root/'runtime.o'
        subprocess.run(['as','--64','-o',str(obj),str(ROOT/'spec/library-x86_64.s')],check=True)
        pieces=['defmodule NativeLibraryData do\n']
        for name in NAMES:
            binary=root/(name+'.bin')
            subprocess.run(['objcopy','-O','binary','--only-section=.text.'+name,str(obj),str(binary)],check=True)
            data=binary.read_bytes()
            assert 0<len(data)<=1024,(name,len(data))
            method=name+('_blob' if name=='nl_pack' else '_emit')
            def literal(raw):
                if len(raw)<=128:return 'b['+','.join(map(str,raw))+']'
                middle=len(raw)//2
                return 'Enum.concat('+literal(raw[:middle])+','+literal(raw[middle:])+')'
            # A body holds at most 1024 tokens, about 500 literal bytes; longer
            # routines are joined from separate part functions.
            # na_pad holds data among its code: the ARM64 compiler emits the
            # version with the marker its translation reads (scripts/generate-marked-fragments.py).
            if name=='na_pad':pieces.append(f'  def {method}(): bytes do if nc_arm() == 1 do na_pad_emit_marked() else na_pad_emit_plain() end end\n');method='na_pad_emit_plain'
            if len(data)<=448:pieces.append(f'  def {method}(): bytes do '+literal(data)+' end\n')
            else:
                parts=[data[i:i+384] for i in range(0,len(data),384)]
                for index,part in enumerate(parts):pieces.append(f'  def {name}_part_{index}(): bytes do '+literal(part)+' end\n')
                calls=[f'{name}_part_{index}()' for index in range(len(parts))]
                while len(calls)>1:calls=['Enum.concat('+calls[0]+','+calls[1]+')']+calls[2:]
                pieces.append(f'  def {method}(): bytes do '+calls[0]+' end\n')
        pieces.append('  # Native smoke test; generated native library runtime.\n  def main() do System.halt(0) end\nend\n')
        return ''.join(pieces)


if __name__=='__main__':(ROOT/'implementations/alchem/native-library-data.alc').write_text(generate())
