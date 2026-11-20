#!/usr/bin/env python3
"""Report the `needs` an entry of a library file lacks.

    scripts/check-library-needs.py library/Process.alc ...

An entry `#: name/arity` must name, after `needs`, every function of the
library written in Alchem that its body calls as Module.name(arguments),
counted by its arguments (scripts/generate-prelude.py; a missing one is a
bare compile error in the programs that reach the entry and in no others).
This reads the files named, or every library file, and prints what is
missing; it changes nothing and fails when something is. Calls through
pipes and references by & are not looked for, and a name the compiler has
code of its own for beside the library's (some of Enum) is reported though
it needs no entry: name the files you keep clean."""
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
HEAD=re.compile(r'#: (\S+)/(\d+)((?: form \d+)?(?: exact)?)(?: needs (.*))?')


def count(text,start):
    """The number of arguments between the ( at start and its )."""
    depth=0;commas=0;empty=True;i=start
    while i<len(text):
        c=text[i]
        if c=='"':
            i+=1
            while text[i]!='"':
                if text[i]=='\\':i+=1
                elif text[i]=='#' and text[i+1]=='{':
                    nest=1;i+=2
                    while nest:
                        nest+=(text[i]=='{')-(text[i]=='}');i+=1
                    continue
                i+=1
            empty=False
        elif c in '([{':
            if depth>=1:empty=False
            depth+=1
        elif c in ')]}':
            depth-=1
            if depth==0:return 0 if empty else commas+1
        elif c==',' and depth==1:commas+=1
        elif not c.isspace() and depth>=1:empty=False
        i+=1
    raise ValueError('unclosed call')


def entries(path):
    found=[];current=None
    for line in path.read_text().split('\n'):
        head=HEAD.fullmatch(line)
        if head:
            current={'name':head[1],'arity':int(head[2]),'needs':set((head[4] or '').split()),'text':''};found.append(current)
        elif line.startswith('#: '):current=None
        elif current is not None and not line.lstrip().startswith('#'):current['text']+=line+'\n'
    return found


if __name__=='__main__':
    files=sorted((ROOT/'library').glob('*.alc'))
    known={(path.stem,e['name'],e['arity']) for path in files for e in entries(path)}
    named=[Path(name).resolve() for name in sys.argv[1:]] or files
    missing=0
    for path in named:
        module=path.stem
        for e in entries(path):
            for m in re.finditer(r'(?<![\w.])([A-Z]\w*)\.(\w+[?!]?)\(',e['text']):
                key=(m[1],m[2],count(e['text'],m.end()-1))
                need=(m[2] if m[1]==module else m[1]+'.'+m[2])+'/'+str(key[2])
                if key in known and key!=(module,e['name'],e['arity']) and need not in e['needs']:
                    e['needs'].add(need);missing+=1
                    print(f'{path.name}: {e["name"]}/{e["arity"]} needs {need}')
    sys.exit(1 if missing else 0)
