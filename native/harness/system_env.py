#!/usr/bin/env python3
"""System.argv/get_env against Go os.Args/ToValidUTF8 and LookupEnv oracles."""
import ctypes
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
from native_memory import floor_arena

from integer_parse import decode

KEYS=[b'HOME',b'DUP',b'EMPTY',b'A',b'A=B',b'',b'NOEQ',b'K0',b'K1',b'k1',b'\xc3\x84',b'LONG']
SHOW='def show(o: option[string]): string do case o do some(s) -> "some:" <> s none -> "none" end end '


def literal(data):
    return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,35,92) else f'\\x{b:02x}' for b in data)+'"'


def valid_utf8(data):
    """strings.ToValidUTF8(s, "\\uFFFD"): each run of invalid bytes becomes one U+FFFD."""
    out=bytearray();i=0;invalid=False
    while i<len(data):
        rune,width=decode(data,i)
        if rune is None:
            if not invalid:out+='\ufffd'.encode()
            invalid=True
        else:out+=data[i:i+width];invalid=False
        i+=width
    return bytes(out)


def lookup(envp,key):
    """os.LookupEnv: the first entry whose text before its first '=' equals key."""
    if not key:return None
    for entry in envp:
        name,equals,value=entry.partition(b'=')
        if equals and name==key:return value
    return None


def expected(argv,envp):
    args=[valid_utf8(a) for a in argv[1:]]
    out=b'\0'.join(args)+b'\n'+str(len(args)).encode()+b'\n'
    for key in KEYS:
        value=lookup(envp,key)
        out+=(b'none' if value is None else b'some:'+value)+b'\n'
    out+=(lookup(envp,b'K0') or b'fallback')+b'\n'
    return out


def execute(path,argv,envp,limit=None):
    # Exact argv/envp byte strings: duplicates, entries without '=', invalid UTF-8.
    read,write=os.pipe();pid=os.fork()
    if pid==0:
        try:
            os.dup2(write,1);os.close(read)
            libc=ctypes.CDLL(None,use_errno=True)
            args=(ctypes.c_char_p*(len(argv)+1))(*argv,None);env=(ctypes.c_char_p*(len(envp)+1))(*envp,None)
            if limit:limit()
            libc.execve(str(path).encode(),args,env)
        finally:os._exit(127)
    os.close(write);out=b''
    while chunk:=os.read(read,65536):out+=chunk
    os.close(read);_,status=os.waitpid(pid,0)
    return os.waitstatus_to_exitcode(status),out


def build(compiler,source,root,name):
    r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
    assert (r.returncode,r.stderr)==(0,b''),(source[:200],r.returncode,r.stderr)
    out=root/name;out.unlink(missing_ok=True);out.write_bytes(r.stdout);out.chmod(0o700);return out


def verify(compiler):
    rng=random.Random(2026)
    body='IO.puts(Enum.join(System.argv(),"\\x00"))\nIO.puts(Integer.to_string(Enum.count(System.argv())))\n'
    body+=''.join(f'IO.puts(show(System.get_env({literal(key)})))\n' for key in KEYS)
    body+='IO.puts(System.get_env("K0","fallback"))\nSystem.halt(0)'
    cases=[([b'prog'],[]),([],[b'HOME=h']),([b'prog',b''],[b'HOME=/home/x',b'DUP=first',b'DUP=second',b'EMPTY=',b'A=B=C',b'NOEQ',b'K0=0']),
           ([b'p',b'\xff\xfe',b'x\xc3',b'\xed\xa0\x80z',b'\xe2\x82\xac',b'a\xffb\xfe\xfdc'],[b'K1=\xff\n',b'k1=lower',b'\xc3\x84=umlaut',b'=empty',b'LONG='+b'v'*100000])]
    pieces=[b'a',b'=',b'\xff',b'\xc3\xa9',b'\xc3',b'\xf0\x9f\x98\x80',b' ',b'\n',b'K0',b'DUP']
    for _ in range(40):
        argv=[b''.join(rng.choice(pieces) for _ in range(rng.randrange(0,6))) for _ in range(rng.randrange(0,6))]
        envp=[rng.choice(KEYS[:5]+KEYS[7:]+[b'X'])+rng.choice([b'=',b'',b'=='])+b''.join(rng.choice(pieces) for _ in range(rng.randrange(0,4))) for _ in range(rng.randrange(0,10))]
        cases.append((argv,envp))
    with tempfile.TemporaryDirectory(prefix='alchem-system-env-') as d:
        root=Path(d)
        program=build(compiler,'defmodule M do '+SHOW+'def main() do\n'+body+' end end',root,'env')
        for argv,envp in cases:
            status,out=execute(program,argv,envp)
            assert (status,out)==(0,expected(argv,envp)),(argv,envp,status,out[:300],expected(argv,envp)[:300])
        # Every call copies; repeated large argv copies that are all held exhaust the arena at
        # its 4 MiB floor (24 MB of copies; the 16 GiB an unlimited run reserves holds them).
        # (They were held by the frames of the calls alone, which no longer keep what a call
        # has done with: spec/alchem-memory.md, "Frames".)
        deep='def f(n: integer, held: list[list[string]]): integer do if n == 0 do Enum.count(held)-200 else f(n-1,[System.argv()|held]) end end '
        program=build(compiler,'defmodule M do '+deep+'def main() do none: list[list[string]] = []\nSystem.halt(f(200,none)) end end',root,'deep')
        assert execute(program,[b'p',b'x'],[])==(0,b''),'small repeated argv'
        assert execute(program,[b'p',b'\xffa'*60000],[])==(0,b''),'large repeated argv'
        assert execute(program,[b'p',b'\xffa'*60000],[],floor_arena(program))[0]==71,'argv arena exhaustion'
        rejections=['x = System.argv(1)','x = System.get_env()','x = System.get_env(1)','x = System.get_env("a",1)','x = System.get_env("a","b","c")','x = System.get_env(b[65])','x = System.argv']
        for statement in rejections:
            source='defmodule M do def main() do '+statement+'\nSystem.halt(0) end end'
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(statement,r)
    print(f'PASS System.argv/get_env: {len(cases)} raw argv/envp runs vs Go os.Args/ToValidUTF8/LookupEnv oracles, arena exhaustion, {len(rejections)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
