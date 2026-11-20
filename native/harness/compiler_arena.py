#!/usr/bin/env python3
"""V11 explicit compiler arena budgets; earlier profiles keep their fixed arena."""
import json
import resource
from pathlib import Path
import subprocess
import sys
import tempfile
from bytes_differential import function,constant
from run import TARGET


def program(size,packs):
    return {'version':11,'arena_bytes':size,'functions':[function('main',[],[{'op':'bytes.pack','dest':f'b{i}','args':[]} for i in range(packs)]+[constant('r',0)],'r')]}


def verify(backends):
    with tempfile.TemporaryDirectory(prefix='alchem-compiler-arena-') as directory:
        root=Path(directory)
        for size,packs,status in [(8,1,0),(8,2,71),(16,2,0),(16,3,71),(16<<20,1,0),(64<<20,1,0),(1<<30,1,0),((1<<30)+8,1,0),(4<<30,1,0),(1<<34,1,0)]:
            binaries=[]
            for index,backend in enumerate(backends):
                path=root/'input.json';path.write_text(json.dumps(program(size,packs)));output=root/f'program-{index}'
                result=subprocess.run([str(backend),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
                assert result.returncode==0,result.stderr
                run=subprocess.run([str(output)],capture_output=True,timeout=120)
                assert run.returncode==status,(size,packs,run)
                binaries.append(output.read_bytes())
            assert binaries[0]==binaries[1]
        # A budget past 1 GiB is halved until the system grants it: with 3 GiB of
        # address space 16 GiB becomes 2 GiB; with 512 MiB not even 1 GiB is granted.
        for index,backend in enumerate(backends):
            output=root/f'program-{index}'
            for space,status,message in [(3<<30,0,b''),(512<<20,71,b'E_RUNTIME_ALLOC: byte allocation failed or limit exceeded\n')]:
                run=subprocess.run([str(output)],capture_output=True,timeout=120,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_AS,(space,space)))
                assert (run.returncode,run.stdout,run.stderr)==(status,b'',message),('arena under an address-space limit',space,run)
        invalid=[program(v,1) for v in [0,7,9,(1<<30)+4,(1<<34)+8,None,True,1.5,'8']]
        missing=program(8,1);del missing['arena_bytes'];invalid.append(missing)
        old=program(8,1);old['version']=10;invalid.append(old)
        for backend in backends:
            for p in invalid:
                path=root/'bad.json';path.write_text(json.dumps(p));output=root/'preserved';output.write_bytes(b'preserve')
                result=subprocess.run([str(backend),'--target',TARGET,'--input',str(path),'--output',str(output)],capture_output=True,timeout=120)
                assert result.returncode!=0 and b'E_INVALID_IR' in result.stderr and output.read_bytes()==b'preserve',(p,result)
    print('PASS V11 compiler arena: exact charging, 8-byte..16GiB budgets and invalid/older-profile preservation')


if __name__=='__main__':verify([Path(p).resolve() for p in sys.argv[1:]])
