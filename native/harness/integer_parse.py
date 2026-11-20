#!/usr/bin/env python3
"""Integer.parse results/errors against independent Go ParseInt/Quote oracles."""
from bisect import bisect_right
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from native_memory import floor_arena
from run import FUNCTION_LIMIT,at_limit

ROOT=Path(__file__).resolve().parents[1]
PRINT=json.loads((ROOT/'spec/print-ranges.json').read_text())['ranges']
STARTS=[start for start,_ in PRINT]
ESCAPES={7:'a',8:'b',9:'t',10:'n',11:'v',12:'f',13:'r'}


def printable(rune):
    if rune<128:return 32<=rune<127
    index=bisect_right(STARTS,rune)-1
    return index>=0 and rune<=PRINT[index][1]


def decode(data,i):
    # Go accepts exactly the strict UTF-8 sequences; anything else is one byte.
    first=data[i]
    width=1 if first<0x80 else 2 if 0xc2<=first<=0xdf else 3 if 0xe0<=first<=0xef else 4 if 0xf0<=first<=0xf4 else 0
    if width:
        try:return ord(data[i:i+width].decode('utf-8')),width
        except UnicodeDecodeError:pass
    return None,1


def quote(data):
    out=bytearray(b'"');i=0
    while i<len(data):
        rune,width=decode(data,i)
        if rune is None:out+=b'\\x%02x'%data[i]
        elif rune in (34,92):out+=b'\\'+bytes([rune])
        elif printable(rune):out+=data[i:i+width]
        elif rune in ESCAPES:out+=b'\\'+ESCAPES[rune].encode()
        elif rune<32 or rune==127:out+=b'\\x%02x'%rune
        elif rune<0x10000:out+=b'\\u%04x'%rune
        else:out+=b'\\U%08x'%rune
        i+=width
    return bytes(out+b'"')


def parse(data,base=None):
    radix=10 if base is None else base
    text=data[1:] if data[:1] in (b'+',b'-') else data
    value=0
    for byte in text:
        digit=byte-48 if 48<=byte<=57 else (byte|32)-87 if 97<=(byte|32)<=122 else 99
        if digit>=radix:value=None;break
        value=value*radix+digit
    if text and value is not None:
        if data[:1]==b'-':value=-value
        if -(1<<63)<=value<(1<<63):return str(value).encode()
    suffix=b'' if base is None else b' in base %d'%base
    return quote(data)+b' is not an integer'+suffix


def literal(data):
    assert len(data)<=128
    return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,35,92) else f'\\x{b:02x}' for b in data)+'"'


def numbers(rng):
    cases=[]
    edges=[0,1,-1,42,(1<<63)-1,-(1<<63),1<<63,-(1<<63)-1,(1<<64)-1,1<<64,10**30,-(10**30)]
    for base in [2,3,8,10,16,36]:
        for value in edges+[rng.randrange(-(1<<63),1<<63) for _ in range(6)]:
            digits='';magnitude=abs(value)
            while True:
                magnitude,digit=divmod(magnitude,base);digits='0123456789abcdefghijklmnopqrstuvwxyz'[digit]+digits
                if not magnitude:break
            digits=''.join(c.upper() if rng.random()<0.5 else c for c in digits)
            sign='-' if value<0 else rng.choice(['','+'])
            cases.append(((sign+digits).encode(),base))
            if base==10:cases.append(((sign+digits).encode(),None))
    for text in [b'',b'+',b'-',b'--1',b'+-1',b' 1',b'1 ',b'1_0',b'0x1f',b'0b1',b'1e3',b'1.0',b'00042',b'-0',b'+0',b'9'*19,b'9'*20,b'1'*64,b'1'*65,b'z',b'Z',b'[',b'@',b'`',b'{',b'/',b':']:
        for base in [None,2,10,16,36]:cases.append((text,base))
    return cases


def texts(rng):
    cases=[(bytes([b]),None) for b in range(256)]
    cases+=[(bytes([b,48]),16) for b in range(0,256,7)]
    for raw in [b'\xc0\x80',b'\xc1\xbf',b'\xe0\x80\x80',b'\xe0\x9f\xbf',b'\xed\xa0\x80',b'\xed\xbf\xbf',b'\xf0\x8f\xbf\xbf',b'\xf4\x90\x80\x80',
                b'\xf5\x80\x80\x80',b'\xe2\x82',b'\xf0\x9f\x98',b'\xc3',b'\xef\xbf\xbd',b'\xef\xbf\xbe',b'\xef\xbb\xbf',b'\xf4\x8f\xbf\xbf',b'\xc2\x80\xc2\x9f\xc2\xa0\xc2\xad']:
        cases.append((raw,None));cases.append((b'1'+raw+b'1',10))
    # Range boundaries and their neighbours exercise the packed printable table.
    for start,end in rng.sample(PRINT,120)+PRINT[:4]+PRINT[-4:]:
        runes=[start-1,start,end,end+1]
        data=b''.join(chr(r).encode('utf-8','surrogatepass') for r in runes if r<=0x10ffff)
        cases.append((data,rng.choice([None,10,36])))
    for _ in range(80):
        runes=[rng.choice([rng.randrange(32,127),rng.randrange(0x80,0x800),rng.randrange(0x800,0x10000),rng.randrange(0x10000,0x110000),rng.randrange(0,32)]) for _ in range(rng.randrange(1,10))]
        data=b''.join(chr(r).encode('utf-8','surrogatepass') for r in runes)
        if rng.random()<0.3:data=bytes(rng.randrange(256) for _ in range(rng.randrange(1,12)))
        cases.append((data[:128],rng.choice([None,2,16,36])))
    return cases


def compile_program(compiler,source,root,name='out'):
    result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
    assert (result.returncode,result.stderr)==(0,b''),(source[:200],result.returncode,result.stderr)
    again=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
    assert again.stdout==result.stdout,'Integer.parse determinism'
    output=root/name;output.unlink(missing_ok=True);output.write_bytes(result.stdout);output.chmod(0o700)
    return output


SHOW='def show(r: result[integer,string]): string do case r do ok(n) -> Integer.to_string(n) error(e) -> e end end '


def verify(compiler):
    rng=random.Random(20261117)
    cases=numbers(rng)+texts(rng)
    with tempfile.TemporaryDirectory(prefix='alchem-integer-parse-') as d:
        root=Path(d)
        for first in range(0,len(cases),16):
            batch=cases[first:first+16]
            calls=[f'Integer.parse({literal(data)})' if base is None else f'Integer.parse({literal(data)},{base})' for data,base in batch]
            source='defmodule M do '+SHOW+'def main() do\n'+''.join(f'IO.puts(show({call}))\n' for call in calls)+'System.halt(0) end end'
            run=subprocess.run([str(compile_program(compiler,source,root))],capture_output=True,env={'PATH':''},timeout=120)
            expected=b''.join(parse(data,base)+b'\n' for data,base in batch)
            if (run.returncode,run.stdout,run.stderr)!=(0,expected,b''):
                lines=run.stdout.split(b'\n')
                for (data,base),got in zip(batch,lines):
                    assert got==parse(data,base),(data,base,got,parse(data,base))
                raise AssertionError(('Integer.parse batch',first,run.returncode,run.stderr))
        statuses=[
            # Explicit bases outside 2..36, including 0, fail after both arguments evaluate.
            ('System.halt(byte_size(show(Integer.parse("1",0))))',2),('System.halt(byte_size(show(Integer.parse("1",1))))',2),
            ('System.halt(byte_size(show(Integer.parse("x",37))))',2),('System.halt(byte_size(show(Integer.parse("1",-9223372036854775808))))',2),
            # Quoting expands \x01 to four bytes: about 2MB fits the arena at its 4 MiB floor, which
            # these runs are held to (floor_arena), and 4.4MB exhausts it.
            ('System.halt(byte_size(show(Integer.parse(String.duplicate("\\x01",500000))))-2000000)',20),
            ('System.halt(byte_size(show(Integer.parse(String.duplicate("\\x01",1100000)))))',71),
            ('System.halt(case Integer.parse("-42") do ok(n) -> 0-n error(e) -> 1 end)',42),
            ('System.halt(case Integer.parse("2a",16) do ok(n) -> n error(e) -> 1 end)',42),
            ('r = Integer.parse("4x")\nSystem.halt(case r do ok(n) -> 1 error(e) -> byte_size(e) end)',22),
        ]
        for body,status in statuses:
            source='defmodule M do '+SHOW+'def main() do '+body+' end end'
            built=compile_program(compiler,source,root)
            run=subprocess.run([str(built)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(built))
            # A base outside 2..36 fails at the call, as in the pinned runtime.
            assert (run.returncode,run.stdout)==(status,b'') and (run.stderr==b'' if status!=2 else run.stderr.split(b': ',1)[1]==b'base must be between 2 and 36\n  at M.main (<stdin>:1)\n'),(body,run)
        # Shared runtimes use table slots beyond the user functions, so a program
        # with the full 65535 functions can still call them.
        full=''.join(f'def f{i}(n: integer): integer do n+1 end ' for i in range(FUNCTION_LIMIT-1))
        source='defmodule M do '+full+f'def main() do System.halt(case Integer.parse("41") do ok(n) -> f{FUNCTION_LIMIT-2}(n) error(e) -> 1 end) end end'
        result=at_limit([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=600)
        assert (result.returncode,result.stderr)==(0,b''),('65535 functions calling Integer.parse',result.returncode,result.stderr)
        output=root/'full';output.unlink(missing_ok=True);output.write_bytes(result.stdout);output.chmod(0o700)
        run=subprocess.run([str(output)],capture_output=True,env={'PATH':''},timeout=120)
        assert run.returncode==42,('65535 functions calling Integer.parse',run.returncode)
        rejections=['Integer.parse(1)','Integer.parse("1","2")','Integer.parse("1",true)','Integer.parse()','Integer.parse("1",10,1)','Integer.parse(b[49])']
        for call in rejections:
            source='defmodule M do '+SHOW+'def main() do IO.puts(show('+call+'))\nSystem.halt(0) end end'
            result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (result.returncode,result.stdout)==(65,b''),(call,result)
    print(f'PASS Integer.parse: {len(cases)} results/errors vs Go ParseInt/Quote oracles, {len(statuses)} status programs, 65535 functions with the runtime, {len(rejections)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
