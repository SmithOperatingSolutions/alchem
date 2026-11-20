#!/usr/bin/env python3
"""IO.read_line/read_all against the pinned runtime's line and UTF-8 rules."""
import re
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
from native_memory import floor_arena

MAX_LINE=1048576
SHOW='def show(o: option[string]): string do case o do some(s) -> s none -> "<none>" end end '


def valid(data):
    try:data.decode('utf-8');return True
    except UnicodeDecodeError:return False


def expected(data,reads):
    """Go ReadSlice('\\n'), TrimSuffix \\n then \\r; read_all takes the rest."""
    out=bytearray();rest=data
    for kind in reads:
        if kind=='line':
            end=rest.find(b'\n')
            line,rest=(rest,b'') if end<0 else (rest[:end],rest[end+1:])
            if not line and end<0:out+=b'<none>\n';continue
            if line.endswith(b'\r'):line=line[:-1]
            if len(line)>MAX_LINE:return bytes(out),b'input line exceeds 1048576 bytes'
            if not valid(line):return bytes(out),b'input is not valid UTF-8'
            out+=line+b'\n'
        else:
            if not valid(rest):return bytes(out),b'input is not valid UTF-8'
            out+=rest;rest=b''
    return bytes(out),0


def program(reads):
    body=''.join('IO.puts(show(IO.read_line()))\n' if kind=='line' else 'IO.write(IO.read_all())\n' for kind in reads)
    return 'defmodule M do '+SHOW+'def main() do\n'+body+'System.halt(0) end end'


def build(compiler,source,root,name):
    r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
    assert (r.returncode,r.stderr)==(0,b''),(source,r.returncode,r.stderr)
    again=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
    assert again.stdout==r.stdout,'IO input determinism'
    out=root/name;out.write_bytes(r.stdout);out.chmod(0o700);return out


def verify(compiler):
    rng=random.Random(1117)
    inputs=[b'',b'\n',b'\r',b'\r\n',b'a',b'a\n',b'a\r\n',b'a\r\r\n',b'a\rb\n',b'\n\n\n',b'first\r\nsecond\n\nrest \xc3\xa9\nmore',
            b'\xe4\xb8\xad\xf0\x9f\x98\x80\n\xef\xbf\xbd',b'ok\xff\n',b'ok\n\xff',b'\xed\xa0\x80\n',b'\xc0\x80',b'x\n\xe2\x82',b'\x00\x01\n\x7f']
    for _ in range(40):
        pieces=[rng.choice([b'\n',b'\r',b'\r\n',b'a',b'xyz',b'\xc3\xa9',b'\xf0\x9f\x98\x80',b'\x00',b'\xff',b' '])for _ in range(rng.randrange(0,24))]
        inputs.append(b''.join(pieces))
    inputs+=[b'x'*MAX_LINE+b'\n',b'x'*MAX_LINE+b'\r\n',b'x'*(MAX_LINE+1)+b'\n',b'x'*(MAX_LINE+1),b'y'*3000000]
    shapes=[['line','line','line','all','line'],['all','line'],['line']*5]
    checked=0
    with tempfile.TemporaryDirectory(prefix='alchem-io-input-') as d:
        root=Path(d)
        binaries=[build(compiler,program(reads),root,f'p{i}') for i,reads in enumerate(shapes)]
        for data in inputs:
            for reads,binary in zip(shapes,binaries):
                want,status=expected(data,reads)
                r=subprocess.run([str(binary)],input=data,capture_output=True,env={'PATH':''},timeout=120)
                # A read that fails ends the program at the call with the pinned runtime's message.
                if status==0:assert (r.returncode,r.stdout,r.stderr)==(0,want,b''),(data[:80],reads,r.returncode,r.stdout[:200],want[:200])
                else:assert (r.returncode,r.stdout)==(2,want) and re.fullmatch(rb'<stdin>:\d+:\d+: '+status+rb'\n  at M\.main \(<stdin>:\d+\)\n',r.stderr),(data[:80],reads,r.returncode,r.stdout[:200],r.stderr)
                checked+=1
        line_then_rest=build(compiler,'defmodule M do '+SHOW+'def main() do IO.puts(show(IO.read_line()))\nSystem.halt(0) end end',root,'one')
        # A line read must not consume input after its newline.
        source=root/'input';source.write_bytes(b'first\nsecond\nthird')
        with open(source,'rb') as stdin:
            r=subprocess.run(['/bin/sh','-c','"$0"; cat',str(line_then_rest)],stdin=stdin,capture_output=True,timeout=120)
        assert (r.returncode,r.stdout)==(0,b'first\nsecond\nthird'),r
        # Data delivered in small delayed chunks is still read to end of input.
        reader=binaries[1]
        p=subprocess.Popen([str(reader)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env={'PATH':''})
        for chunk in [b'ab',b'c\xc3',b'\xa9\nd',b'e']:p.stdin.write(chunk);p.stdin.flush()
        p.stdin.close();out=p.stdout.read();p.wait(timeout=120)
        assert (p.returncode,out,p.stderr.read())==(0,b'abc\xc3\xa9\nde<none>\n',b''),(p.returncode,out)
        statuses=[(b'z'*5000000,binaries[1],71)]
        for data,binary,status in statuses:
            # Input past the arena, here its 4 MiB floor (floor_arena).
            r=subprocess.run([str(binary)],input=data,capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(binary))
            assert (r.returncode,r.stdout,r.stderr)==(status,b'',b''),('arena',r.returncode)
        # The pinned runtime reads at most 16,777,216 bytes of standard input.
        sized=build(compiler,'defmodule M do\n  def main() do\n    IO.puts(Integer.to_string(byte_size(IO.read_all())))\n  end\nend\n',root,'sized')
        for size,want in [(16777216,(0,b'16777216\n',b'')),(16777217,(2,b'',b'<stdin>:3:41: input exceeds 16777216 bytes\n  at M.main (<stdin>:3)\n'))]:
            r=subprocess.run([str(sized)],input=b'z'*size,capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout,r.stderr)==want,('input limit',size,r.returncode,r.stdout[:80],r.stderr[:200])
        # A closed standard input reads as an empty one, and a read that fails
        # is the end of input for read_line and a failure of read_all.
        for binary,want in [(binaries[1],b'<none>\n'),(binaries[2],b'<none>\n'*5)]:
            r=subprocess.run([str(binary)],capture_output=True,preexec_fn=lambda:os.close(0),timeout=120)
            assert (r.returncode,r.stdout,r.stderr)==(0,want,b''),('closed stdin',r)
        directory=os.open('/',os.O_RDONLY)
        if True:
            r=subprocess.run([str(binaries[1])],stdin=directory,capture_output=True,timeout=120)
            assert (r.returncode,r.stdout,r.stderr)==(2,b'',b'<stdin>:2:10: cannot read standard input\n  at M.main (<stdin>:2)\n'),('directory',r)
            r=subprocess.run([str(binaries[2])],stdin=directory,capture_output=True,timeout=120)
            assert (r.returncode,r.stdout,r.stderr)==(0,b'<none>\n'*5,b''),('directory lines',r)
        os.close(directory)
        injected=0;tracer=shutil.which('strace')
        if tracer:
            for binary,rule,want in [(binaries[1],'error=EINTR:when=1',(0,b'ab\ncd<none>\n')),(binaries[2],'error=EINTR:when=2',(0,b'ab\ncd\n<none>\n<none>\n<none>\n')),(binaries[1],'error=EIO:when=2',(2,b'',b'<stdin>:2:10: cannot read standard input\n  at M.main (<stdin>:2)\n'))]:
                r=subprocess.run([tracer,'-qq','-o',str(root/'trace'),'-e','inject=read:'+rule,str(binary)],input=b'ab\ncd',capture_output=True,timeout=120)
                if b'ptrace' in r.stderr and b'Operation not permitted' in r.stderr:print('SKIP IO input injection: ptrace unavailable');continue
                assert (r.returncode,r.stdout,r.stderr)==(*want,b'')[:3],(rule,r)
                injected+=1
        else:print('SKIP IO input injection: strace unavailable')
        rejections=['x = IO.read_all(1)','x = IO.read_line(1)','x: integer = IO.read_all()','x: string = IO.read_line()','x = IO.read_bytes()','x = IO.read_all']
        for statement in rejections:
            source='defmodule M do def main() do '+statement+'\nSystem.halt(0) end end'
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(statement,r)
    print(f'IO input syscall injections: {injected}/3')
    print(f'PASS IO.read_line/read_all: {checked} input/shape runs vs Go ReadSlice/TrimSuffix/utf8.Valid oracle, no over-read, chunked pipe, arena/closed-stdin errors, {len(rejections)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
