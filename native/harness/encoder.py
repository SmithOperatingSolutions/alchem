#!/usr/bin/env python3
"""Validate and execute complete ELF artifacts constructed by Alchem itself."""
import argparse
import json
import os
from pathlib import Path
import struct
import sys
import subprocess
import tempfile
from run import ROOT,TARGET

MESSAGE=b'E_RUNTIME_BYTE: expected byte value 0..255\n'


def validate_elf(data,value):
    assert len(data)==140 and data[:16]==b'\x7fELF\x02\x01\x01'+b'\0'*9,'invalid ELF identification/size'
    assert struct.unpack_from('<HHIQQQIHHHHHH',data,16)==(2,62,1,0x400080,64,0,0,64,56,1,0,0,0),'invalid ELF header'
    assert struct.unpack_from('<IIQQQQQQ',data,64)==(1,5,0,0x400000,0x400000,140,140,4096),'invalid load segment'
    assert data[120:128]==b'\0'*8,'invalid header padding'
    expected=b'\xbf'+value.to_bytes(4,'little')+b'\xb8\x3c\0\0\0\x0f\x05'
    assert data[128:]==expected,'invalid process-entry code'


def verify(frontend,rust,go):
    component=(ROOT/'implementations/alchem/encoder.alc').read_text()
    prefix=component.split('  # Native smoke test;',1)[0]
    values=list(range(256))+[-1,256,-(1<<63),(1<<63)-1]
    with tempfile.TemporaryDirectory(prefix='alchem-encoder-') as directory:
        root=Path(directory)
        for value in values:
            source=prefix+f'  def main() do code=emit_elf_exit({value})\n System.halt(Enum.count(code)-140) end\nend\n'
            path=root/'encoder.alc';path.write_text(source)
            lowered=subprocess.run([str(frontend),'--input',str(path),'--program'],capture_output=True,timeout=120)
            assert lowered.returncode==0,(value,lowered.stderr)
            ir=json.loads(lowered.stdout);assert ir['version']==9
            main=next(f for f in ir['functions'] if f['name']=='main')
            instructions=main['blocks'][0]['instructions']
            call=next(i for i in instructions if i.get('callee')=='fn.emit_elf_exit')
            instructions.append({'op':'bytes.write','dest':'observed_output','value':call['dest'],'stream':'stdout'})
            ir_path=root/'observed.json';ir_path.write_text(json.dumps(ir))
            binaries=[]
            for index,compiler in enumerate([rust,go]):
                output=root/f'encoder-{index}'
                built=subprocess.run([str(compiler),'--target',TARGET,'--input',str(ir_path),'--output',str(output)],env=dict(os.environ,PATH=''),capture_output=True,timeout=120)
                assert built.returncode==0,(value,built.stderr)
                result=subprocess.run([str(output)],capture_output=True,timeout=120)
                if 0<=value<=255:
                    assert result.returncode==0 and result.stderr==b'',(value,index,result)
                    validate_elf(result.stdout,value)
                    executable=root/'artifact';executable.write_bytes(result.stdout);executable.chmod(0o700)
                    run=subprocess.run([str(executable)],capture_output=True,timeout=120)
                    assert (run.returncode,run.stdout,run.stderr)==(value,b'',b''),(value,index,'encoded fragment failed')
                else:assert (result.returncode,result.stdout,result.stderr)==(72,b'',MESSAGE),(value,index,result)
                binaries.append(output.read_bytes())
            assert binaries[0]==binaries[1],value
        driver=ROOT/'scripts/emit-alchem-executable.py'
        output=root/'standalone image'
        base=[sys.executable,str(driver),'--frontend',str(frontend),'--compiler',str(rust),'--output',str(output)]
        for value in [0,42,255]:
            save=['--save-emitter',str(root/'saved-emitter')] if value==42 else []
            result=subprocess.run(base+['--status',str(value)]+save,env=dict(os.environ,PATH=''),capture_output=True,timeout=120)
            assert result.returncode==0,result.stderr
            validate_elf(output.read_bytes(),value)
            assert output.stat().st_mode & 0o777==0o700
            result=subprocess.run([str(output)],env=dict(os.environ,PATH=''),capture_output=True,timeout=120)
            assert (result.returncode,result.stdout,result.stderr)==(value,b'',b'')
        reused=subprocess.run([str(root/'saved-emitter')],env=dict(os.environ,PATH=''),capture_output=True,timeout=120)
        assert reused.returncode==0 and reused.stderr==b''
        validate_elf(reused.stdout,42)
        output.write_bytes(reused.stdout);output.chmod(0o700)
        run=subprocess.run([str(output)],env=dict(os.environ,PATH=''),capture_output=True,timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(42,b'',b'')
        output.write_bytes(b'existing image')
        result=subprocess.run(base+['--status','256'],capture_output=True,timeout=120)
        assert result.returncode!=0 and b'E_RUNTIME_BYTE' in result.stderr and output.read_bytes()==b'existing image','failed emitter replaced output'
        original=(ROOT/'implementations/alchem/encoder.alc').read_bytes()
        result=subprocess.run(base[:-1]+[str(ROOT/'implementations/alchem/encoder.alc')],capture_output=True,timeout=120)
        assert result.returncode!=0 and b'overwrite' in result.stderr
        assert (ROOT/'implementations/alchem/encoder.alc').read_bytes()==original
    print('PASS 260 Alchem ELF-writer cases: all 256 complete images executed, 4 invalid immediates rejected; driver export/preservation/empty-PATH checks pass')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frontend',type=Path);parser.add_argument('rust',type=Path);parser.add_argument('go',type=Path)
    args=parser.parse_args();verify(args.frontend.resolve(),args.rust.resolve(),args.go.resolve())
