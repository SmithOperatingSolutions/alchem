#!/usr/bin/env python3
"""Grapheme count/slice compatibility against the exact pinned Go runtime."""
import hashlib
import json
import os
from pathlib import Path
from source_syntax import native_bytes
import random
import subprocess
import sys
import tempfile
from run import ROOT
from self_hosted_components import verify_legacy_program as verify_program


def literal(data):
    if len(data)<=128:return '"'+''.join(f'\\x{v:02x}' for v in data)+'"'
    middle=len(data)//2
    return '('+literal(data[:middle])+' <> '+literal(data[middle:])+')'


def reference(root):
    go=os.environ.get('ALCHEM_FRONTEND_GO','go')
    module=subprocess.run([go,'list','-m','-f','{{.Dir}}','github.com/SmithOperatingSolutions/alchem'],cwd=ROOT/'adapters/alchem',capture_output=True,text=True,timeout=120)
    assert module.returncode==0,module.stderr
    text=(Path(module.stdout.strip())/'compiler/library.go.txt').read_text()
    section=text[text.index('type graphemeClass uint8'):text.index('func strGraphemes(')]
    snapshot=json.loads((ROOT/'spec/grapheme-ranges.json').read_text())
    assert hashlib.sha256(section.encode()).hexdigest()==snapshot['reference_sha256'],'pinned grapheme runtime changed'
    source=root/'oracle.go'
    main='''
func main(){
 if len(os.Args)>1 {out:=[][3]int{};start,prev:=0,0;for r:=0;r<=0x110000;r++{c:=0;if r<0x110000{c=int(graphemeClassOf(rune(r)));if c==12||c==13{c=0}};if c!=prev{if prev!=0{out=append(out,[3]int{start,r-1,prev})};start=r;prev=c}};json.NewEncoder(os.Stdout).Encode(map[string]any{"unicode":unicode.Version,"ranges":out});return}
 scanner:=bufio.NewScanner(os.Stdin);for scanner.Scan(){b,e:=hex.DecodeString(scanner.Text());if e!=nil{panic(e)};s:=string(b);bounds:=[]int{};at:=0;for len(s)>0{n:=graphemeLen(s);at+=n;bounds=append(bounds,at);s=s[n:]};json.NewEncoder(os.Stdout).Encode(bounds)}
}
'''
    source.write_text('package main\nimport("unicode";"unicode/utf8";"encoding/json";"encoding/hex";"os";"bufio")\n'+section+main)
    binary=root/'oracle';built=subprocess.run([go,'build','-o',str(binary),str(source)],capture_output=True,timeout=120)
    assert built.returncode==0,built.stderr
    result=subprocess.run([str(binary),'--tables'],capture_output=True,timeout=120);table=json.loads(result.stdout)
    assert table['unicode']==snapshot['unicode'] and table['ranges']==snapshot['ranges'],'Unicode property snapshot differs'
    return binary,snapshot


def verify(compiler):
    rng=random.Random(171120)
    base=['','hello','\r\n','A\r\nB','e\u0301','\u0600A','\u1100\u1161\u11a8','각','🇺🇸🇨🇦🇬','👩🏽\u200d🚀','👨\u200d👩\u200d👧\u200d👦','क्ष','a\u200cb','©\ufe0f','\u0915\u093e']
    cases=[s.encode() for s in base]+[bytes([v]) for v in range(256)]+[b'\xf0\x90\x80',b'\xed\xa0\x80',b'\xe0\x80\x80',b'\xf4\x90\x80\x80']
    pieces=[s.encode() for s in base]+[bytes([0xff]),b'\0']
    cases += [b''.join(rng.choice(pieces) for _ in range(rng.randrange(1,7))) for _ in range(64)]
    cases += [('a'+'\u0301'*200).encode(),b'a'*1024]
    cases += [(chr(block+offset)+'\u1160').encode() for block in [0xac00,0xb000,0xd780] for offset in range(28)]
    cases += [bytes(rng.randrange(256) for _ in range(rng.randrange(40))) for _ in range(128)]
    with tempfile.TemporaryDirectory(prefix='alchem-graphemes-') as d:
        root=Path(d);oracle,snapshot=reference(root)
        # Exercise every property-range boundary inside a cluster-sensitive context.
        for start,end,_ in snapshot['ranges']:
            for value in {start,end}:
                if 0xd800<=value<=0xdfff:continue
                cp=chr(value).encode();cases.append(b'A'+cp+'\u0301\u200d👩'.encode())
        result=subprocess.run([str(oracle)],input=b'\n'.join(data.hex().encode() for data in cases)+b'\n',capture_output=True,timeout=120)
        assert result.returncode==0,result.stderr
        bounds=[json.loads(line) for line in result.stdout.splitlines()];assert len(bounds)==len(cases)
        for first in range(0,len(cases),4):
            helpers=[];checks=[]
            for j,(data,ends) in enumerate(zip(cases[first:first+4],bounds[first:first+4])):
                helpers.append(f'def probe{j}(): integer do if String.length({literal(data)}) == {len(ends)} do 1 else 0 end end ')
                checks.append(f'probe{j}()')
            source='defmodule M do '+''.join(helpers)+'def main() do if '+' * '.join(checks)+' == 1 do System.halt(0) else System.halt(1) end end end'
            verify_program(source,compiler,root,('grapheme length',first))
        slices=0
        for data,ends in zip(cases[:80],bounds[:80]):
            edges=[0]+ends
            for start,count in [(0,0),(0,1),(1,2),(len(ends),1),(len(ends)+1,3),(0,(1<<63)-1)]:
                expected=data[edges[min(start,len(ends))]:edges[min(start+count,len(ends))]]
                source=('defmodule M do def main() do IO.puts(String.slice('+literal(data)+f',{start},{count})) System.halt(0) end end').encode()
                built=subprocess.run([str(compiler)],input=native_bytes(source),capture_output=True,env={'PATH':''},timeout=120)
                assert built.returncode==0,(source,built.returncode,built.stderr)
                target=root/'slice';target.unlink(missing_ok=True);target.write_bytes(built.stdout);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
                assert (run.returncode,run.stdout,run.stderr)==(0,expected+b'\n',b''),(data,start,count,run,expected)
                slices+=1
        option_calls=0
        for data,ends in list(zip(cases[:80],bounds[:80]))+list(zip(cases[-30:],bounds[-30:])):
            for name in ['first','last']:
                expected=(data[:ends[0]] if name=='first' else data[([0]+ends)[-2]:]) if ends else b'NONE'
                source=('defmodule M do def text(v: option[string]): string do case v do some(s) -> s none -> "NONE" end end def main() do IO.puts(text(String.'+name+'('+literal(data)+'))) System.halt(0) end end').encode()
                built=subprocess.run([str(compiler)],input=native_bytes(source),capture_output=True,env={'PATH':''},timeout=120)
                assert built.returncode==0,(name,built.returncode,built.stderr)
                target=root/'option';target.unlink(missing_ok=True);target.write_bytes(built.stdout);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
                assert (run.returncode,run.stdout,run.stderr)==(0,expected+b'\n',b''),(name,data,run,expected)
                option_calls+=1
        for expression in ['String.slice("x",-1,1)','String.slice("x",0,-1)']:
            verify_program('defmodule M do def main() do s='+expression+'\nSystem.halt(0) end end',compiler,root,expression,(2,b'slice bounds must be nonnegative'))
    print(f'PASS {len(cases)} grapheme counts and {slices} slices and {option_calls} first/last options against pinned Unicode {snapshot["unicode"]} runtime')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
