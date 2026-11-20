#!/usr/bin/env python3
"""Regenerate native word-collection literals; optional development step only."""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
NAMES=['nl_pack','nl_at','nl_concat','nl_slice','nl_reverse','nl_sum','nl_map','nl_reduce','nl_cons','nm_get','nm_put','nm_delete','nm_entries','nm_new']


def generate():
    with tempfile.TemporaryDirectory(prefix='alchem-collection-runtime-') as d:
        root=Path(d);obj=root/'runtime.o'
        subprocess.run(['as','--64','-o',str(obj),str(ROOT/'spec/collections-x86_64.s')],check=True)
        pieces=['defmodule NativeCollectionData do\n']
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
            pieces.append(f'  def {method}(): bytes do '+literal(data)+' end\n')
        pieces.append('  # Native smoke test; generated native word-collection runtime.\n  def main() do System.halt(0) end\nend\n')
        return ''.join(pieces)


if __name__=='__main__':(ROOT/'implementations/alchem/native-collection-data.alc').write_text(generate())
