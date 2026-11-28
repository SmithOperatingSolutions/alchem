#!/usr/bin/env python3
"""Alchem-emitted compiler IO entry accepts runtime bytes without a host wrapper."""
from pathlib import Path
from source_syntax import native_bytes
import os
import shutil
import subprocess
import sys
import tempfile
from run import ROOT

SOURCE=b'defmodule C do def native_compile(s: list[integer]): list[integer] do if Enum.count(s) == 0 do [0,255] else s end end def main() do System.halt(0) end end'


def verify(frontend,backends):
 with tempfile.TemporaryDirectory(prefix='alchem-compiler-entry-') as directory:
  root=Path(directory);images=[];injected=0
  for i,backend in enumerate(backends):
   compiler=root/f'compiler{i}'
   built=subprocess.run([sys.executable,str(ROOT/'scripts/bootstrap-alchem-compiler.py'),'--language','functions','--frontend',str(frontend),'--backend',str(backend),'--output',str(compiler)],capture_output=True,timeout=120)
   assert built.returncode==0,built.stderr
   result=subprocess.run([str(compiler)],input=native_bytes(SOURCE),capture_output=True,env={'PATH':''},timeout=120)
   assert result.returncode==0,result
   output=root/f'pipeline{i}';output.unlink(missing_ok=True);output.write_bytes(result.stdout);output.chmod(0o700);images.append(result.stdout)
   for data in [b'',b'abc',bytes(range(256)),b'x'*65535,b'x'*65536,b'x'*1048575,b'x'*1048576,bytes(range(256))*16383+bytes(range(255)),b'x'*4194304,bytes(range(256))*65531+bytes(range(255))]:
    run=subprocess.run([str(output)],input=data,capture_output=True,env={'PATH':''},timeout=120)
    assert (run.returncode,run.stdout,run.stderr)==(0,data if data else b'\0\xff',b''),run
   # More than a compiler entry's limit of 1 GiB less 1 KiB is refused as it is
   # read (written as it is taken, until it takes no more).
   child=subprocess.Popen([str(output)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':''})
   try:
    for _ in range(1024):child.stdin.write(b'x'*(1<<20))
    child.stdin.close()
   except (BrokenPipeError,OSError):pass
   said=(child.stdout.read(),child.stderr.read());status=child.wait(timeout=300)
   assert (status,said)==(65,(b'',b'E_RUNTIME_INPUT: input exceeds byte limit\n')),(status,said[1][:200])
   run=subprocess.run([str(output)],capture_output=True,preexec_fn=lambda:os.close(0),timeout=120)
   assert (run.returncode,run.stdout,run.stderr)==(74,b'',b'E_RUNTIME_IO: input read failed\n'),run
   with open('/dev/full','wb') as full:
    run=subprocess.run([str(output)],input=b'abc',stdout=full,stderr=subprocess.PIPE,env={'PATH':''},timeout=120)
    assert (run.returncode,run.stderr)==(74,b'E_RUNTIME_IO: output write failed\n'),run
   tracer=shutil.which('strace')
   if tracer:
    for operation in ['read','write']:
     run=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e',f'inject={operation}:error=EINTR:when=1',str(output)],input=b'abc',capture_output=True,timeout=120)
     if b'ptrace' in run.stderr and b'Operation not permitted' in run.stderr:print('SKIP compiler entry EINTR: ptrace unavailable')
     else:
      assert (run.returncode,run.stdout,run.stderr)==(0,b'abc',b''),run
      injected+=1
   invalid=SOURCE.replace(b'def native_compile',b'defp native_compile')
   run=subprocess.run([str(compiler)],input=native_bytes(invalid),capture_output=True,env={'PATH':''},timeout=120)
   assert run.returncode==65 and not run.stdout and run.stderr,run
  assert images[0]==images[1]
  # A compiler source past the pinned parser's 1 MiB is lowered in parts: the IR
  # made in parts is the IR of the whole source (or, once the source is past that
  # limit, the IR made in other parts).
  from importlib.util import spec_from_file_location,module_from_spec
  spec=spec_from_file_location('alchem_bootstrap',ROOT/'scripts/bootstrap-alchem-compiler.py');boot=module_from_spec(spec);spec.loader.exec_module(boot)
  text=boot.source_text('functions',seed=True);size=len(text.encode())
  whole=boot.frontend_ir(text,frontend)
  for limit in [size//2+300000,size//3+300000]:
   assert limit<size and boot.frontend_ir(text,frontend,limit)==whole,('compiler source lowered in parts differs',limit)
 print(f'Compiler-entry read/write EINTR injection: {injected}/{len(backends)*2}')
 print('PASS Alchem-emitted compiler entry: binary/empty/exact input up to 4 MiB, overflow past 1 GiB, public signature, backend equality and the compiler source lowered in parts')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve(),[Path(p).resolve() for p in sys.argv[2:]])
