#!/usr/bin/env python3
"""V11 bootstrap symbol capacity; older IR limits and atomic rejection remain."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from bytes_differential import function,constant
from run import TARGET


def program(count,version):
    result={'version':version,'functions':[function('main',[],[{'op':'call','dest':'r','callee':f'f{count-1}','args':[]}],'r')] + [function(f'f{i}',[],[constant('r',42 if i==count-1 else 0)],'r') for i in range(1,count)]}
    if version==11:result['arena_bytes']=4<<20
    return result


def verify(backends):
    with tempfile.TemporaryDirectory(prefix='alchem-function-capacity-') as d:
        root=Path(d)
        for version,count,accepted in [(10,256,True),(10,257,False),(11,256,True),(11,257,True),(11,512,True),(11,513,True),(11,4096,True),(11,4097,True),(11,65535,True),(11,65536,False)]:
            images=[]
            for i,backend in enumerate(backends):
                source=root/'in.json';source.write_text(json.dumps(program(count,version)))
                output=root/f'out{i}';output.write_bytes(b'keep-existing-output');output.chmod(0o640)
                r=subprocess.run([str(backend),'--target',TARGET,'--input',str(source),'--output',str(output)],capture_output=True,timeout=300)
                if accepted:
                    assert (r.returncode,r.stderr)==(0,b''),(version,count,r.returncode,r.stderr)
                    run=subprocess.run([str(output)],capture_output=True,timeout=120,env={'PATH':''})
                    assert (run.returncode,run.stdout,run.stderr)==(42,b'',b''),(version,count,run)
                    images.append(output.read_bytes())
                else:
                    assert r.returncode!=0 and b'E_UNSUPPORTED' in r.stderr,(version,count,r)
                    assert output.read_bytes()==b'keep-existing-output' and output.stat().st_mode&0o777==0o640
            if accepted:assert len(set(images))==1,(version,count,'backend difference')
    print('PASS V11 65535/65536 function boundary, V10 256/257 preservation and backend equality')


if __name__=='__main__':verify([Path(p).resolve() for p in sys.argv[1:]])
