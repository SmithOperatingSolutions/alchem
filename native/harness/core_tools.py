#!/usr/bin/env python3
"""Native core tools must be built by Alchem and serve all existing oracles."""
import ast
import hashlib
import stat
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from run import ROOT
from lexer import cases as lexer_cases,token
from integers import MIN,MAX
from expressions import cases as expression_cases
from encoder import validate_elf


def run(path,data,status=0):
    result=subprocess.run([str(path)],input=data,capture_output=True,env={'PATH':''},timeout=120)
    assert result.returncode==status,(path.name,data,result.returncode,result.stderr)
    if status:assert not result.stdout and result.stderr,(path.name,'rejection output')
    else:assert not result.stderr,(path.name,result.stderr)
    return result.stdout


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-core-tools-') as directory:
        root=Path(directory);output=root/'core'
        built=subprocess.run([sys.executable,str(ROOT/'scripts/build-core-modules.py'),'--compiler',str(compiler),'--output-directory',str(output)],capture_output=True,timeout=120)
        assert built.returncode==0,built.stderr
        manifest=json.loads((output/'manifest.json').read_text());assert len(manifest['modules'])==5
        counts={'lexer':0,'integers':0,'expressions':0,'encoder':0,'arithmetic':0}
        seen=set()
        for _,text,_ in lexer_cases():
            data=bytes(ast.literal_eval(text))
            if data in seen:continue
            seen.add(data);expected=[];cursor=0;valid=True
            if len(data)>128:valid=False
            while valid:
                start,kind,stop,error=token(data,cursor)
                if error:valid=False;break
                expected.extend([kind,start,stop])
                if kind==9:break
                cursor=stop
            result=run(output/'alchem-lexer',data,0 if valid else 65)
            if valid:assert result==bytes(expected),(data,result,expected)
            counts['lexer']+=1
        for value in [MIN,MAX,0,1,-1,42,-42]+[int.from_bytes(bytes([n])*8,'little',signed=True) for n in range(0,256,3)]:
            text=(' '+('+' if value>=0 else '-')+'00'+str(abs(value))+' \n').encode()
            assert run(output/'alchem-integer',text)==str(value).encode(),value
            counts['integers']+=1
        for text in [b'',b'1x',b'9223372036854775808',b'-9223372036854775809',b'--42',b'\0',b'0'*129]:run(output/'alchem-integer',text,65);counts['integers']+=1
        for data,error,value in expression_cases():
            result=run(output/'alchem-expression',bytes(data),65 if error else 0)
            if not error:assert result==str(value).encode(),(data,result,value)
            image=run(output/'alchem-arithmetic',bytes(data),0 if not error and 0<=value<=255 else 65)
            if not error and 0<=value<=255:validate_elf(image,value)
            counts['expressions']+=1;counts['arithmetic']+=1
        for status in range(256):
            image=run(output/'alchem-elf-emitter',bytes([status]));validate_elf(image,status)
            target=root/'target';target.unlink(missing_ok=True);target.write_bytes(image);target.chmod(0o700)
            executed=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
            assert (executed.returncode,executed.stdout,executed.stderr)==(status,b'',b'')
            counts['encoder']+=1
        for data in [b'',b'xx']:run(output/'alchem-elf-emitter',data,65)
        before={p.name:p.read_bytes() for p in output.iterdir()}
        for module in manifest['modules']:
            artifact=output/module['artifact'];source=output/(module['name']+'.source.alc')
            assert stat.S_IMODE(artifact.stat().st_mode)==0o700,'core executable permissions'
            assert hashlib.sha256(artifact.read_bytes()).hexdigest()==module['artifact_sha256']
            assert hashlib.sha256(source.read_bytes()).hexdigest()==module['source_sha256']
        repeated=subprocess.run([sys.executable,str(ROOT/'scripts/build-core-modules.py'),'--compiler',str(compiler),'--output-directory',str(output)],capture_output=True,timeout=120)
        assert repeated.returncode==0 and before=={p.name:p.read_bytes() for p in output.iterdir()},'nondeterministic core publication'
        failed=subprocess.run([sys.executable,str(ROOT/'scripts/build-core-modules.py'),'--compiler','/bin/false','--output-directory',str(output)],capture_output=True,timeout=120)
        assert failed.returncode!=0 and before=={p.name:p.read_bytes() for p in output.iterdir()},'failed core build replaced files'
    print('PASS self-hosted core tools:',counts)


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
