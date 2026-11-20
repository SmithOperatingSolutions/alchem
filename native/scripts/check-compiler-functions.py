#!/usr/bin/env python3
"""Find compiler functions the native profile rejects.

Compiles each function of the assembled compiler source on its own, with every
other function replaced by a stub of the same signature, and prints the ones a
given compiler rejects. Development aid for profile limits such as 16 live
slots or 1024 body tokens: check-compiler-functions.py COMPILER [NAME...]
"""
import importlib.util
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
STUB={'bytes':'b[]','integer':'0','boolean':'true','string':'""'}


def functions(text):
    starts=list(re.finditer(r'^  defp? (\w+)\((.*?)\)(?:: ([\w\[\],]+))? do',text,re.M))
    out=[]
    for i,match in enumerate(starts):
        end=starts[i+1].start() if i+1<len(starts) else text.rindex('\nend')
        out.append((match.group(1),match.group(2),match.group(3),text[match.start():end]))
    return out


def main():
    compiler=Path(sys.argv[1]).resolve();wanted=set(sys.argv[2:])
    spec=importlib.util.spec_from_file_location('alchem_bootstrap',ROOT/'scripts/bootstrap-alchem-compiler.py')
    bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)
    found=functions(bootstrap.source_text('functions',compact=False))
    names=[name for name,_,_,_ in found]
    duplicates=sorted({name for name in names if names.count(name)>1})
    if duplicates:print('DUPLICATE',*duplicates);return 1
    stubs={name:f'  def {name}({params}): {kind} do {STUB[kind]} end\n' for name,params,kind,_ in found if kind in STUB}
    rejected=[]
    for name,params,kind,body in found:
        if name=='main' or kind not in STUB or (wanted and name not in wanted):continue
        source='defmodule Check do\n'+''.join(text for other,text in stubs.items() if other!=name)+body.rstrip()+'\n  def main() do System.halt(0) end\nend\n'
        result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''})
        if result.returncode!=0:rejected.append(name);print('REJECTED',name,flush=True)
    print(f'{len(found)} functions, {len(rejected)} rejected')
    return 1 if rejected else 0


if __name__=='__main__':sys.exit(main())
