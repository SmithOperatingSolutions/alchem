#!/usr/bin/env python3
"""String ==/!=/ordering, split, replace, count, valid?, trims and bare predicate
names against independent Go strings/unicode oracles."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from native_memory import floor_arena

from integer_parse import decode

SPACES={9,10,11,12,13,32,0x85,0xa0,0x1680,*range(0x2000,0x200b),0x2028,0x2029,0x202f,0x205f,0x3000}
PIECES=[b'a',b'b',b',',b'--',b' ',b'\t',b'\n',b'\xc2\xa0',b'\xc2\x85',b'\xe3\x80\x80',b'\xe2\x80\x8a',b'\xe2\x80\x8b',b'\xe1\x9a\x80',
        b'\xe2\x81\x9f',b'\xc3\xa9',b'\xff',b'\xe2\x80',b'\x80',b'\xf0\x9f\x98\x80',b'ab',b'']


def literal(data):
    return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,35,92) else f'\\x{b:02x}' for b in data)+'"'


def last_rune(data):
    """utf8.DecodeLastRune: the last rune start within four bytes, else one invalid byte."""
    start=len(data)-1
    while start>max(len(data)-4,0) and data[start]&0xc0==0x80:start-=1
    rune,width=decode(data,start)
    return (rune,width) if rune is not None and start+width==len(data) else (None,1)


def trim_leading(data):
    i=0
    while i<len(data):
        rune,width=decode(data,i)
        if rune not in SPACES:break
        i+=width
    return data[i:]


def trim_trailing(data):
    while data:
        rune,width=last_rune(data)
        if rune not in SPACES:break
        data=data[:-width]
    return data


def trim(data):return trim_trailing(trim_leading(data))


def replace(data,old,new):
    if old:return data.replace(old,new)
    out=bytearray(new);i=0
    while i<len(data):
        width=decode(data,i)[1];out+=data[i:i+width]+new;i+=width
    return bytes(out)


def valid(data):
    try:data.decode('utf-8');return True
    except UnicodeDecodeError:return False


def flag(value):return b'T' if value else b'F'


def cases(rng):
    def text(limit=6):return b''.join(rng.choice(PIECES) for _ in range(rng.randrange(0,limit)))
    out=[]
    for _ in range(260):
        a,b,c=text(),text(3),text(3)
        kind=rng.choice(['eq','ne','lt','le','gt','ge','split','replace','count','valid','trim','triml','trimr','contains','starts','ends'])
        if kind=='split' and not b:b=b','
        out.append((kind,a,b,c))
    out+=[('eq',b'',b'',b''),('eq',b'a',b'',b''),('ne',b'abc',b'abd',b''),('split',b'',b',',b''),('split',b',,',b',',b''),('split',b'abc',b'abc',b''),
          ('replace',b'',b'',b'x'),('replace',b'\xff\xc3',b'',b'.'),('replace',b'aaaa',b'aa',b''),('count',b'aaaa',b'aa',b''),('count',b'abc',b'',b''),
          ('trim',b' \t\n',b'',b''),('trim',b'\xe2\x80\x8b x \xe2\x80\x8b',b'',b''),('trim',b'x\x80\xc2\xa0',b'',b''),('trim',b'\xc2\xa0\xc2',b'',b''),
          ('valid',b'\xed\xa0\x80',b'',b''),('valid',b'\xf4\x8f\xbf\xbf',b'',b''),('lt',b'a',b'ab',b''),('lt',b'ab',b'a',b''),('le',b'',b'',b''),('gt',b'\xff',b'z',b''),('ge',b'a\x00',b'a',b''),('lt',b'\xc3\xa9',b'z',b''),
          ('triml',b' \t',b'',b''),('trimr',b'x\x80\xc2\xa0',b'',b''),('triml',b'\xc2\xa0\xc2',b'',b''),('trimr',b'\xe2\x80\x8a\xe3\x80\x80',b'',b''),('contains',b'abc',b'',b''),('starts',b'',b'',b''),('ends',b'a',b'ab',b'')]
    return out


def expression(kind,a,b,c):
    A,B,C=literal(a),literal(b),literal(c)
    return {'eq':f'flag({A} == {B})','ne':f'flag({A} != {B})','lt':f'flag({A} < {B})','le':f'flag({A} <= {B})','gt':f'flag({A} > {B})','ge':f'flag({A} >= {B})',
            'triml':f'"[" <> String.trim_leading({A}) <> "]"','trimr':f'"[" <> String.trim_trailing({A}) <> "]"','split':f'Enum.join(String.split({A},{B}),"|")',
            'replace':f'String.replace({A},{B},{C})','count':f'Integer.to_string(String.count({A},{B}))','valid':f'flag(String.valid?({A}))',
            'trim':f'"[" <> String.trim({A}) <> "]"','contains':f'flag(String.contains({A},{B}))','starts':f'flag(String.starts_with({A},{B}))',
            'ends':f'flag(String.ends_with({A},{B}))'}[kind]


def expected(kind,a,b,c):
    return {'eq':lambda:flag(a==b),'ne':lambda:flag(a!=b),'lt':lambda:flag(a<b),'le':lambda:flag(a<=b),'gt':lambda:flag(a>b),'ge':lambda:flag(a>=b),
            'triml':lambda:b'['+trim_leading(a)+b']','trimr':lambda:b'['+trim_trailing(a)+b']','split':lambda:b'|'.join(a.split(b)),'replace':lambda:replace(a,b,c),
            'count':lambda:str(a.count(b) if b else 0).encode(),'valid':lambda:flag(valid(a)),'trim':lambda:b'['+trim(a)+b']',
            'contains':lambda:flag(b in a),'starts':lambda:flag(a.startswith(b)),'ends':lambda:flag(a.endswith(b))}[kind]()


FLAG='def flag(x: boolean): string do if x do "T" else "F" end end '


def verify(compiler):
    rng=random.Random(4242)
    all_cases=cases(rng)
    with tempfile.TemporaryDirectory(prefix='alchem-string-ops-') as d:
        root=Path(d)
        def build(source):
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stderr)==(0,b''),(source[:300],r.returncode,r.stderr)
            out=root/'out';out.write_bytes(r.stdout);out.chmod(0o700);return out
        for first in range(0,len(all_cases),16):
            batch=all_cases[first:first+16]
            source='defmodule M do '+FLAG+'def main() do\n'+''.join(f'IO.puts({expression(*case)})\n' for case in batch)+'System.halt(0) end end'
            run=subprocess.run([str(build(source))],capture_output=True,env={'PATH':''},timeout=120)
            want=b''.join(expected(*case)+b'\n' for case in batch)
            if (run.returncode,run.stdout,run.stderr)!=(0,want,b''):
                for case,got in zip(batch,run.stdout.split(b'\n')):
                    assert got==expected(*case),(case,got,expected(*case))
                raise AssertionError(('string batch',first,run.returncode))
        for body,status in [('IO.puts(Enum.join(String.split("a",""),"|"))\nSystem.halt(0)',2),
                            ('IO.puts(String.replace(String.duplicate("ab",500000),"","..."))\nSystem.halt(0)',71),
                            # String <> has no 1MiB payload cap: 1.4MB fits, 2.8MB more exhausts the arena
                            # at its 4 MiB floor, which these runs are held to (floor_arena).
                            ('a = String.duplicate("a",700000)\nb = a <> a\nSystem.halt(byte_size(b)-1400000+42)',42),
                            ('a = String.duplicate("a",700000)\nb = a <> a\nc = b <> b\nSystem.halt(byte_size(c))',71)]:
            built=build('defmodule M do def main() do '+body+' end end')
            run=subprocess.run([str(built)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(built))
            # An empty separator fails at the call, as in the pinned runtime.
            assert (run.returncode,run.stdout,run.stderr)==(status,b'',b'<stdin>:1:48: separator must not be empty\n  at M.main (<stdin>:1)\n' if status==2 else b''),(body,run)
        # Without that limit the arena is 16 GiB reserved lazily: the same 5.6 MB of strings fit.
        built=build('defmodule M do def main() do a = String.duplicate("a",700000)\nb = a <> a\nc = b <> b\nSystem.halt(rem(byte_size(c),251)) end end')
        run=subprocess.run([str(built)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(2800000%251,b'',b''),('strings past 4 MiB',run)
        rejections=['x = "a" < 1','x = "a" == 1','x = String.trim_leading(1)','x = "a" == b[97]','x = String.split("a","b","c")','x = String.replace("a","b")',
                    'x = String.count("a",1)','x = String.valid?(1)','x = String.contains("a")','x = String.trim(1)']
        for statement in rejections:
            source='defmodule M do def main() do '+statement+'\nSystem.halt(0) end end'
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(statement,r)
    print(f'PASS string operations: {len(all_cases)} ==/!=/ordering/split/replace/count/valid?/trim/predicate cases vs Go strings oracles, empty separator and arena errors, {len(rejections)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
