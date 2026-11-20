#!/usr/bin/env python3
"""String.reverse/capitalize/pad_leading/pad_trailing against the pinned grapheme
runtime's cluster boundaries and Go's case and rune rules."""
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from native_memory import floor_arena
from run import FUNCTION_LIMIT,at_limit

from graphemes import reference
from integer_parse import decode
from string_case import convert


def literal(data):
    if len(data)<=128:return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,35,92) else f'\\x{b:02x}' for b in data)+'"'
    middle=len(data)//2
    return '('+literal(data[:middle])+' <> '+literal(data[middle:])+')'


def runes(data):
    """[]rune(s): each invalid byte is one U+FFFD."""
    out=[];i=0
    while i<len(data):
        rune,width=decode(data,i);out.append('�'.encode() if rune is None else data[i:i+width]);i+=width
    return out


def padding(count,width,fill):
    """The pinned padding(): the first width-count runes of the fill repeated."""
    missing=width-count
    if missing<=0 or not fill:return b''
    units=runes(fill)
    return b''.join(units[i%len(units)] for i in range(missing))


def expected(kind,data,bounds,width,fill):
    clusters=[data[a:b] for a,b in zip([0]+bounds,bounds)]
    if kind=='reverse':return b''.join(reversed(clusters))
    if kind=='capitalize':
        first=bounds[0] if bounds else 0
        return convert(data[:first],'title')+convert(data[first:],'lower')
    pad=padding(len(clusters),width,b' ' if fill is None else fill)
    return pad+data if kind=='pad_leading' else data+pad


def call(kind,data,width,fill):
    if kind in ('reverse','capitalize'):return f'String.{kind}({literal(data)})'
    return f'String.{kind}({literal(data)},{width})' if fill is None else f'String.{kind}({literal(data)},{width},{literal(fill)})'


def cases(rng):
    base=['','hello','hELLO wÖRLD','\r\n','A\r\nB','école','؀A','각','각','🇺🇸🇨🇦🇬','👩🏽‍🚀x','क्ष','a‌b','©️','ǆungla','ßtraße','ŉa','ﬁsh','İstanbul','ΣΑΣ']
    texts=[s.encode() for s in base]+[b'\xffAB',b'a\xc3',b'\xed\xa0\x80x',b'x\x80y',b'\xe2\x82']
    pieces=[s.encode() for s in base[1:]]+[b'\xff',b'a',b'Z',b' ']
    texts+=[b''.join(rng.choice(pieces) for _ in range(rng.randrange(1,5)))[:100] for _ in range(60)]
    fills=[None,b' ',b'ab',b'-',b'\xc3\xa9',b'\xc3\xa9\xff',b'\xff',b'e\xcc\x81',b'',b'\xf0\x9f\x98\x80x']
    out=[]
    for data in texts:
        out.append(('reverse',data,0,None));out.append(('capitalize',data,0,None))
        out.append((rng.choice(['pad_leading','pad_trailing']),data,rng.randrange(-2,14),rng.choice(fills)))
    return out


def verify(compiler):
    rng=random.Random(5151)
    all_cases=cases(rng)
    with tempfile.TemporaryDirectory(prefix='alchem-string-graphemes-') as d:
        root=Path(d);oracle,_=reference(root)
        texts=sorted({data for _,data,_,_ in all_cases})
        result=subprocess.run([str(oracle)],input=b'\n'.join(data.hex().encode() for data in texts)+b'\n',capture_output=True,timeout=120)
        assert result.returncode==0,result.stderr
        bounds=dict(zip(texts,[json.loads(line) for line in result.stdout.splitlines()]))
        def build(source):
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stderr)==(0,b''),(source[:300],r.returncode,r.stderr)
            out=root/'out';out.unlink(missing_ok=True);out.write_bytes(r.stdout);out.chmod(0o700);return out
        for first in range(0,len(all_cases),16):
            batch=all_cases[first:first+16]
            source='defmodule M do def main() do\n'+''.join(f'IO.puts({call(kind,data,width,fill)})\n' for kind,data,width,fill in batch)+'System.halt(0) end end'
            run=subprocess.run([str(build(source))],capture_output=True,env={'PATH':''},timeout=120)
            want=b''.join(expected(kind,data,bounds[data],width,fill)+b'\n' for kind,data,width,fill in batch)
            if (run.returncode,run.stdout,run.stderr)!=(0,want,b''):
                for kind,data,width,fill in batch:
                    one=subprocess.run([str(build('defmodule M do def main() do IO.puts('+call(kind,data,width,fill)+')\nSystem.halt(0) end end'))],capture_output=True,env={'PATH':''},timeout=120)
                    assert one.stdout==expected(kind,data,bounds[data],width,fill)+b'\n',(kind,data,width,fill,one.stdout,expected(kind,data,bounds[data],width,fill))
                raise AssertionError(('grapheme string batch',first,run.returncode))
        # A fill larger than the arena (here its 4 MiB floor, floor_arena) exits71 without looping;
        # many calls share one runtime.
        many=''.join(f'IO.puts(String.pad_leading(String.reverse(String.capitalize("x{i}")),4,"."))\n' for i in range(14))
        # A fill past 2^48 bytes is a panic of the pinned runtime (alchem-failures.md); one the arena cannot hold exits 71.
        for body,status,stdout in [('IO.puts(String.pad_leading("a",9223372036854775807))\nSystem.halt(0)',2,b''),
                                   ('IO.puts(String.pad_leading("a",200000000000))\nSystem.halt(0)',71,b''),
                                   ('IO.puts(String.pad_trailing("a",5000000,"é"))\nSystem.halt(0)',71,b''),
                                   (many+'System.halt(0)',0,b''.join(b'.%sX\n'%str(i)[::-1].encode() if i>9 else b'..%dX\n'%i for i in range(14)))]:
            built=build('defmodule M do def main() do '+body+' end end')
            run=subprocess.run([str(built)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(built))
            assert (run.returncode,run.stdout,run.stderr)==(status,stdout,b'<runtime>: panic: runtime error: makeslice: len out of range\n' if status==2 else b''),(body[:80],run.returncode,run.stdout[:200])
        # Shared runtimes sit beyond the user functions: the full 65535 may use them.
        helpers=lambda count:''.join(f'def f{i}(n: integer): integer do n+1 end ' for i in range(count))
        full=at_limit([str(compiler)],input=('defmodule M do '+helpers(FUNCTION_LIMIT-1)+f'def main() do System.halt(f{FUNCTION_LIMIT-2}(String.length("e\\xcc\\x81"))+40) end end').encode(),capture_output=True,env={'PATH':''},timeout=600)
        assert (full.returncode,full.stderr)==(0,b''),('65535 functions with String.length',full.returncode,full.stderr)
        out=root/'full';out.unlink(missing_ok=True);out.write_bytes(full.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert run.returncode==42,('65535 functions with String.length',run.returncode)
        rejections=['x = String.reverse(1)','x = String.reverse("a","b")','x = String.capitalize()','x = String.capitalize("a","b")','x = String.pad_leading("a")',
                    'x = String.pad_leading("a","b")','x = String.pad_trailing("a",1,2)','x = String.pad_trailing("a",1,"b","c")','x: integer = String.reverse("a")']
        sources=['defmodule M do def main() do '+statement+'\nSystem.halt(0) end end' for statement in rejections]
        for source in sources:
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(source[-100:],r.returncode)
    print(f'PASS grapheme strings: {len(all_cases)} reverse/capitalize/pad cases vs the pinned grapheme oracle and Go case/rune rules, arena limits, shared runtime reuse, 65535 functions with the runtime, {len(sources)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
