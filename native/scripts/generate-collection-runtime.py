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
        # With PIC defined: what a position-independent program (nc_pic)
        # runs where the two differ (spec/darwin-arm64.md).
        pic=root/'pic.o'
        subprocess.run(['as','--64','-o',str(obj),str(ROOT/'spec/collections-x86_64.s')],check=True)
        subprocess.run(['as','--64','--defsym','PIC=1','-o',str(pic),str(ROOT/'spec/collections-x86_64.s')],check=True)
        def section(source,name):
            binary=root/(name+'.bin')
            subprocess.run(['objcopy','-O','binary','--only-section=.text.'+name,str(source),str(binary)],check=True)
            data=binary.read_bytes()
            assert 0<len(data)<=1024,(name,len(data))
            return data
        def literal(raw):
            if len(raw)<=128:return 'b['+','.join(map(str,raw))+']'
            middle=len(raw)//2
            return 'Enum.concat('+literal(raw[:middle])+','+literal(raw[middle:])+')'
        pieces=['defmodule NativeCollectionData do\n']
        for name in NAMES:
            data=section(obj,name);moved=section(pic,name)
            method=name+('_blob' if name=='nl_pack' else '_emit')
            made=literal(data) if moved==data else f'if nc_pic() == 1 do {literal(moved)} else {literal(data)} end'
            pieces.append(f'  def {method}(): bytes do '+made+' end\n')
        pieces.append('  # Native smoke test; generated native word-collection runtime.\n  def main() do System.halt(0) end\nend\n')
        return ''.join(pieces)


if __name__=='__main__':(ROOT/'implementations/alchem/native-collection-data.alc').write_text(generate())
