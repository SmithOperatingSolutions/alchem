#!/usr/bin/env python3
"""String.upcase/downcase over every mapped rune, and String.to_integer."""
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from run import FUNCTION_LIMIT,at_limit

from integer_parse import decode,numbers,parse

ROOT=Path(__file__).resolve().parents[1]
TABLES=json.loads((ROOT/'spec/case-ranges.json').read_text())


def mapping(name):
    out={}
    for start,end,stride,delta in TABLES[name]:
        for rune in range(start,end+1,stride):out[rune]=rune+delta
    # ASCII is handled before the table in Go and here.
    for rune in range(65,91) if name=='lower' else range(97,123):out[rune]=rune+32 if name=='lower' else rune-32
    return out


MAPS={'upper':mapping('upper'),'lower':mapping('lower'),'title':mapping('title')}


def convert(data,name):
    """strings.ToUpper/ToLower: map each rune; each invalid byte becomes U+FFFD."""
    out=bytearray();i=0
    while i<len(data):
        rune,width=decode(data,i)
        out+='�'.encode() if rune is None else chr(MAPS[name].get(rune,rune)).encode()
        i+=width
    return bytes(out)


def literal(data):
    assert len(data)<=128
    return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,35,92) else f'\\x{b:02x}' for b in data)+'"'


def texts(name,rng):
    """Every mapped rune plus the neighbours and stride gaps of every range."""
    runes=set(range(32,127))
    for start,end,stride,_ in TABLES[name]:runes.update(range(max(start-2,128),min(end+3,0x110000)))
    runes={r for r in runes if not 0xd800<=r<=0xdfff}
    ordered=sorted(runes);chunks=[];current=b''
    for rune in ordered:
        encoded=chr(rune).encode()
        if len(current)+len(encoded)>120:chunks.append(current);current=b''
        current+=encoded
    chunks.append(current)
    chunks+=[b'',b'\xff',b'a\xc3',b'\xed\xa0\x80',b'\xef\xbf\xbd',b'\xf0\x9f\x98\x80\xf4\x8f\xbf\xbf',b'x\xe2\x82y\x80z']
    for _ in range(12):chunks.append(b''.join(rng.choice([b'a',b'Z',b'\xc3\xa9',b'\xc3\x89',b'\xff',b'\xc7\x86',b' ']) for _ in range(rng.randrange(1,20))))
    return chunks


def verify(compiler):
    rng=random.Random(909)
    with tempfile.TemporaryDirectory(prefix='alchem-string-case-') as d:
        root=Path(d)
        def build(source):
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stderr)==(0,b''),(source[:300],r.returncode,r.stderr)
            out=root/'out';out.write_bytes(r.stdout);out.chmod(0o700);return out
        def check(calls,wanted,label):
            for first in range(0,len(calls),16):
                source='defmodule M do def main() do\n'+''.join(f'IO.puts({call})\n' for call in calls[first:first+16])+'System.halt(0) end end'
                run=subprocess.run([str(build(source))],capture_output=True,env={'PATH':''},timeout=120)
                want=b''.join(w+b'\n' for w in wanted[first:first+16])
                if (run.returncode,run.stdout,run.stderr)!=(0,want,b''):
                    for call,got,w in zip(calls[first:],run.stdout.split(b'\n'),wanted[first:]):
                        assert got==w,(label,call[:120],got[:120],w[:120])
                    raise AssertionError((label,first,run.returncode))
        cased=0
        for name,function in [('upper','upcase'),('lower','downcase')]:
            chunks=texts(name,rng);cased+=len(chunks)
            check([f'String.{function}({literal(c)})' for c in chunks],[convert(c,name) for c in chunks],function)
        integers=[(data,base) for data,base in numbers(rng) if len(data)<=128]
        good=[(data,base) for data,base in integers if b' is not an integer' not in parse(data,base)]
        bad=[(data,base) for data,base in integers if b' is not an integer' in parse(data,base)]
        call=lambda data,base:f'String.to_integer({literal(data)})' if base is None else f'String.to_integer({literal(data)},{base})'
        check([f'Integer.to_string({call(data,base)})' for data,base in good],[parse(data,base) for data,base in good],'to_integer')
        # The pinned runtime fails the process at the call, with the quoted text or the base rule.
        failures=rng.sample(bad,24)+[(b'1',1),(b'1',37),(b'1',0)]
        for data,base in failures:
            run=subprocess.run([str(build('defmodule M do def main() do System.halt(String.to_integer('+literal(data)+('' if base is None else f',{base}')+')) end end'))],capture_output=True,env={'PATH':''},timeout=120)
            reason=b'base must be between 2 and 36' if base is not None and not 2<=base<=36 else parse(data,base).split(b' is not an integer')[0]+b' is not an integer'
            assert (run.returncode,run.stdout,run.stderr)==(2,b'',b'<stdin>:1:42: '+reason+b'\n  at M.main (<stdin>:1)\n'),(data,base,run)
        # Shared runtimes sit beyond the user functions: the full 65535 may use
        # them (one program calls both, since a compile that large is slow).
        helpers=lambda count:''.join(f'def f{i}(n: integer): integer do n+1 end ' for i in range(count))
        full=at_limit([str(compiler)],input=('defmodule M do '+helpers(FUNCTION_LIMIT-1)+f'def main() do System.halt(f{FUNCTION_LIMIT-2}(byte_size(String.upcase("abc")))+String.to_integer("38")) end end').encode(),capture_output=True,env={'PATH':''},timeout=600)
        assert (full.returncode,full.stderr)==(0,b''),('65535 functions with String.upcase and String.to_integer',full.returncode,full.stderr)
        out=root/'full';out.write_bytes(full.stdout);out.chmod(0o700)
        run=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        assert run.returncode==42,('65535 functions with String.upcase and String.to_integer',run.returncode)
        rejections=['x = String.upcase(1)','x = String.upcase("a","b")','x = String.downcase()','x = String.to_integer(1)','x = String.to_integer("1","2")',
                    'x = String.to_integer("1",2,3)','x: integer = String.upcase("a")','x: string = String.to_integer("1")']
        sources=['defmodule M do def main() do '+statement+'\nSystem.halt(0) end end' for statement in rejections]
        for source in sources:
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(source[-120:],r)
    print(f'PASS String case/to_integer: {cased} strings covering every mapped rune and range neighbour, {len(good)} integers, {len(failures)} failing conversions, 65535 functions with the runtimes, {len(sources)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
