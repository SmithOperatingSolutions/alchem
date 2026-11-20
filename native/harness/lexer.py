#!/usr/bin/env python3
"""Compare the Alchem-written expression lexer to an independent byte oracle."""
import argparse
import os
from pathlib import Path
import random
import subprocess
import tempfile
from run import ROOT, TARGET

LIMIT=128
SPACES={9,10,13,32}
PUNCT={43:4,45:5,42:6,40:7,41:8}


def letter(value):
    return 65<=value<=90 or 97<=value<=122 or value==95


def token(data,cursor):
    if len(data)>LIMIT: return -1,0,-1,3
    if not 0<=cursor<=len(data): return -1,0,-1,2
    start=cursor
    while start<len(data) and data[start] in SPACES: start+=1
    if start==len(data): return start,9,start,0
    value=data[start]
    if letter(value):
        end=start+1
        while end<len(data) and (letter(data[end]) or 48<=data[end]<=57): end+=1
        return start,2,end,0
    if 48<=value<=57:
        end=start+1
        while end<len(data) and 48<=data[end]<=57: end+=1
        return start,3,end,0
    kind=PUNCT.get(value,0)
    return start,kind,start+1,0 if kind else 1


def stream(data,cursor):
    count=0
    while True:
        start,kind,end,error=token(data,cursor)
        if error: return -1,start if error==1 else -error
        if kind==9: return count,-1
        assert end>cursor
        count+=1;cursor=end


def checks(data,cursors=None,whole=True):
    literal='['+','.join(map(str,data))+']'
    # A named parameter gives the empty literal its expected list[integer] type.
    result=[]
    if cursors is None:
        cursors=[];cursor=0
        while True:
            cursors.append(cursor)
            _,kind,end,error=token(data,cursor)
            if error or kind==9: break
            cursor=end
    for cursor in cursors:
        start,kind,end,error=token(data,cursor)
        for name,expected in [('token_start',start),('token_kind',kind),('token_end',end),('token_error',error)]:
            result.append(f'match_kind({name}(values, {cursor}), {expected})')
    if whole:
        count,error=stream(data,0)
        result += [f'match_kind(token_count(values, 0), {count})',f'match_kind(first_error(values, 0), {error})']
    return literal,result


def cases():
    fixed=[b'',b' \t\n\r',b'alpha_12 + 0042*(x-7)',b'12abc',b'_9',b'A',b'0',b'000',b'()',b'+-*',b'good\x00bad',b'a \xff',b'\x80',b'"str"',b'#comment',b'_'*128,b'0'*128,b' '*128,b'+'*128,b'1'*129]
    for i,data in enumerate(fixed): yield f'fixed-{i}',*checks(list(data))
    for cursor in [-9223372036854775808,-1,0,3,4,9223372036854775807]:
        literal,result=checks([32,65,48],[cursor],False)
        count,error=stream([32,65,48],cursor)
        result += [f'match_kind(token_count(values, {cursor}), {count})',f'match_kind(first_error(values, {cursor}), {error})']
        yield f'cursor-{cursor}',literal,result
    yield 'oversize-before-cursor',*checks([65]*129,[-1],False)
    for byte in range(256): yield f'byte-{byte}',*checks([byte])
    rng=random.Random(0x1EAE2)
    alphabet=list(b'abcXYZ_0123456789+-*() \t\n\r')+[0,64,128,255]
    for case in range(64):
        data=[rng.choice(alphabet) for _ in range(rng.randrange(1,40))]
        # Check every cursor as well as stream termination, including recovery
        # after an error and cursor positions inside existing tokens.
        yield f'seeded-{case}',*checks(data,list(range(len(data)+1)))


def verify(frontend,rust,go):
    original=(ROOT/'implementations/alchem/lexer.alc').read_text()
    prefix=original.split('  # Native smoke test;',1)[0]
    environment=dict(os.environ,PATH='')
    count=0
    with tempfile.TemporaryDirectory(prefix='alchem-lexer-') as directory:
        root=Path(directory)
        for name,literal,assertions in cases():
            # Keep failures local to small groups of checks. Whole-stream
            # summaries remain independent probes; all comparisons use full
            # i64 values inside the generated Alchem program.
            local=[item for item in assertions if 'token_count(' not in item and 'first_error(' not in item]
            summaries=[item for item in assertions if 'token_count(' in item or 'first_error(' in item]
            chunks=[local[i:i+24] for i in range(0,len(local),24)]+[[item] for item in summaries]
            for part,selected in enumerate(chunks):
                source=prefix+'  def verify(values: list[integer]): integer do\n    '+ ' * '.join(selected)+'\n  end\n  def main() do\n    if verify('+literal+') == 1 do System.halt(0) else System.halt(1) end\n  end\nend\n'
                path=root/'lexer.alc';path.write_text(source)
                ir_result=subprocess.run([str(frontend),'--input',str(path),'--program'],capture_output=True,timeout=120)
                assert ir_result.returncode==0,(name,part,ir_result.stderr)
                ir=root/'lexer.json';ir.write_bytes(ir_result.stdout)
                binaries=[]
                for index,compiler in enumerate([rust,go]):
                    output=root/f'lexer-{index}'
                    command=[str(compiler),'--target',TARGET,'--input',str(ir),'--output',str(output)]
                    compiled=subprocess.run(command,env=environment,capture_output=True,timeout=120)
                    assert compiled.returncode==0,(name,compiled.stderr)
                    assert output.stat().st_mode & 0o777==0o700
                    binaries.append(output.read_bytes())
                    executed=subprocess.run([str(output)],capture_output=True,timeout=120)
                    assert (executed.returncode,executed.stdout,executed.stderr)==(0,b'',b''),(name,part,index,executed)
                assert binaries[0]==binaries[1],f'{name}: backend bytes differ'
                repeat=root/'repeat'
                repeated=subprocess.run([str(rust),'--target',TARGET,'--input',str(ir),'--output',str(repeat)],env=environment,capture_output=True,timeout=120)
                assert repeated.returncode==0 and repeat.read_bytes()==binaries[0],name
                count+=1
        assert (ROOT/'implementations/alchem/lexer.alc').read_text()==original
    print(f'PASS {count} Alchem lexer oracle programs: all 256 bytes, 64 seeded streams, token spans/errors, EOF and 128-byte limit')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('frontend',type=Path);parser.add_argument('rust',type=Path);parser.add_argument('go',type=Path)
    args=parser.parse_args();verify(args.frontend.resolve(),args.rust.resolve(),args.go.resolve())
