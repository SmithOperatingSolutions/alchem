#!/usr/bin/env python3
"""Native V11 slices match independent byte semantics and keep original inputs."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from bytes_differential import function,constant
from run import TARGET


def program(start,count,arena=4<<20):
 return {'version':11,'arena_bytes':arena,'functions':[function('main',[],[
  {'op':'bytes.const','dest':'b','values':list(range(256))},constant('start',start),constant('count',count),
  {'op':'bytes.slice','dest':'slice','buffer':'b','index':'start','count':'count'},
  {'op':'bytes.write','dest':'w','value':'slice','stream':'stdout'},
  {'op':'bytes.write','dest':'original','value':'b','stream':'stdout'},constant('r',0)],'r')]}


def verify(backends):
 with tempfile.TemporaryDirectory(prefix='alchem-slice-') as directory:
  root=Path(directory);cases=0
  for start in [-(1<<63),-257,-256,-1,0,127,256,(1<<63)-1]:
   for count in [-1,0,1,42,(1<<63)-1]:
    images=[]
    for i,backend in enumerate(backends):
     path=root/'in.json';path.write_text(json.dumps(program(start,count)));out=root/f'out{i}'
     result=subprocess.run([str(backend),'--target',TARGET,'--input',str(path),'--output',str(out)],capture_output=True,timeout=120)
     assert result.returncode==0,result.stderr
     run=subprocess.run([str(out)],capture_output=True,timeout=120)
     if count<0:assert (run.returncode,run.stdout,run.stderr)==(73,b'',b'E_RUNTIME_SLICE: expected nonnegative count\n'),run
     else:
      index=start+256 if start<0 else start
      expected=bytes(range(256))[index:index+min(count,256)] if 0<=index<256 else b''
      assert (run.returncode,run.stdout,run.stderr)==(0,expected+bytes(range(256)),b''),(start,count,run)
     images.append(out.read_bytes())
    assert images[0]==images[1]
    cases+=1
 print(f'PASS {cases} V11 slices: negative/extreme indices and counts, binary data, unchanged input and backend equality')


if __name__=='__main__':verify([Path(p).resolve() for p in sys.argv[1:]])
