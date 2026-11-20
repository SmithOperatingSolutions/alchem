#!/usr/bin/env python3
"""Real code and source metadata up to the 16 MiB input limit; exact input/overflow boundaries."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import re
import resource
import subprocess
import time
import tempfile
import sys
from self_hosted_components import verify_program

LIMIT=16776191
OVER=b'E_RUNTIME_INPUT: input exceeds byte limit\n'
REJECTED=b'E_COMPILE: invalid or unsupported Alchem function program\n'


def program(padding):
    return 'defmodule M do\n'+('# padding\n'*(padding//10))+'def answer(): integer do value=40\n value+2 end\ndef main() do System.halt(answer()) end\nend\n'


# A call chain through functions spread over the source: a for, an if used as
# a value, a for with two generators and a filter, and a failure after
# two-byte characters on the last function's line. The spacers keep the lines
# of the pinned compiler's generated code inside each function's own stretch.
SPACER='#\n'*24
LATE=['defmodule M do\n',
      'def f3(n: integer): integer do\n text = "late é"\n seen = for x <- [n], y <- [x + 1], x < y do\n  f2(y) + String.length(text)\n end\n Enum.count(seen) + 6\nend\n'+SPACER,
      'def f1(n: integer): integer do\n total = for x <- [n, n + 1] do\n  f0(x) + 1\n end\n Enum.count(total)\nend\n'+SPACER,
      'def f2(n: integer): integer do\n value = if n > 0 do\n  f1(n) + 1\n else\n  0\n end\n value * 2\nend\n'+SPACER,
      'def main() do\n IO.puts("start")\n System.halt(f3(1))\nend\n'+SPACER,
      'def f0(n: integer): integer do\n w = String.length("éé") + div(n, n - n)\n w\nend\n','end\n']
# What the pinned compiler prints for ''.join(LATE), which it accepts (its own limit is 1 MiB).
LATE_TRACE=('<stdin>:124:28: division by zero\n  at M.f0 (<stdin>:124)\n  at M.f1 <closure> (<stdin>:35)\n  at M.f1 <closure> (<stdin>:36)\n'
            '  at M.f1 <closure> (<stdin>:36)\n  at M.f1 (<stdin>:40)\n  at M.f2 <closure> (<stdin>:65)\n  at M.f2 (<stdin>:64)\n'
            '  at M.f3 <closure> (<stdin>:5)\n  at M.f3 <closure> (<stdin>:6)\n  at M.f3 <closure> (<stdin>:9)\n  at M.f3 <closure> (<stdin>:6)\n'
            '  at M.f3 (<stdin>:12)\n  at M.main (<stdin>:97)\n')


def late_program(total):
    """LATE with comment lines between its functions up to total bytes, and the
    trace it must end with: the pinned one with every line moved by the
    padding before it."""
    base=''.join(LATE)
    if not total:return base,LATE_TRACE
    room=total-len(base.encode());gaps=len(LATE)-3;each=room//gaps
    out=[LATE[0]];shift=[0]*LATE[0].count('\n');added=0
    for index,block in enumerate(LATE[1:-1]):
        if index>0:
            size=each if index<gaps else room-each*(gaps-1)
            pad='# padding\n'*(size//10);pad+=' '*(size-len(pad));out.append(pad);added+=pad.count('\n')
        out.append(block);shift+=[added]*block.count('\n')
    out.append(LATE[-1]);shift+=[added]
    text=''.join(out);assert len(text.encode())==total,(len(text.encode()),total)
    return text,re.sub(r'<stdin>:(\d+)',lambda m:'<stdin>:%d'%(int(m.group(1))+shift[int(m.group(1))-1]),LATE_TRACE)


def deep_conds(levels):
    """A for whose body ends in conds of 249 arms nested in their last arms: the
    pinned compiler's generated code puts the generator 249 lines further for each."""
    def cond(level,indent):
        pad=' '*indent
        arms=''.join(f'{pad} x == {1000+i} -> {i}\n' for i in range(248))
        inner=f'{pad}  div(x, x - x)\n' if level==0 else cond(level-1,indent+2)
        return f'{pad}cond do\n{arms}{pad} true ->\n{inner}{pad}end\n'
    return 'defmodule M do\ndef f(n: integer): integer do\n seen = for x <- [n] do\n'+cond(levels-1,2)+' end\n Enum.count(seen)\nend\ndef main() do\n System.halt(f(1))\nend\nend\n'


# The pinned compiler's trace for deep_conds(3): the generator stands 745 lines
# past the body's last statement and the function 749, more than the 127 a
# 32-bit immediate holds above a 24-bit position.
DEEP_TRACE=('<stdin>:754:9: division by zero\n  at M.f <closure> (<stdin>:754)\n  at M.f <closure> (<stdin>:1499)\n'
            '  at M.f <closure> (<stdin>:5)\n  at M.f (<stdin>:1503)\n  at M.main (<stdin>:762)\n')


def deep(compiler,root,total):
    source=deep_conds(3);source=' '*(total-len(source))+source
    built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=300)
    assert (built.returncode,built.stderr)==(0,b''),('deep line count compile',total,built.returncode,built.stderr)
    out=root/f'deep-{total}';out.unlink(missing_ok=True);out.write_bytes(built.stdout);out.chmod(0o700)
    run=started(out)
    assert (run.returncode,run.stdout,run.stderr.decode())==(2,b'',DEEP_TRACE),('deep line count',total,run.returncode,run.stderr)


def started(out):
    """Run a program this process has just written. Another thread's fork may
    still hold the file open for writing for a moment (ETXTBSY)."""
    for attempt in range(200):
        try:return subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        except OSError as error:
            if error.errno!=26 or attempt==199:raise
            time.sleep(0.02)


def traced(compiler,root,total):
    source,trace=late_program(total)
    built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=300)
    assert (built.returncode,built.stderr)==(0,b''),('late trace compile',total,built.returncode,built.stderr)
    out=root/f'late-{total}';out.unlink(missing_ok=True);out.write_bytes(built.stdout);out.chmod(0o700)
    run=started(out)
    assert (run.returncode,run.stdout,run.stderr.decode())==(2,b'start\n',trace),('late trace',total,run.returncode,run.stdout,run.stderr,trace)
    return trace


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-source-capacity-') as d:
        root=Path(d)
        for size in [65520,65540,131072,262144]:
            source=program(size)
            verify_program(source,compiler,root,('source capacity',len(source)),42)
        base=program(0);remaining=LIMIT-len(base.encode());prefix='# padding\n'*(remaining//10)+' '*(remaining%10)
        exact=base.replace('def answer()',prefix+'def answer()',1)
        assert len(exact.encode())==LIMIT
        def exact_runs():
            built=subprocess.run([str(compiler)],input=exact.encode(),capture_output=True,env={'PATH':''},timeout=300)
            assert (built.returncode,built.stderr)==(0,b''),('exact limit compile',built.returncode,built.stderr)
            out=root/'exact';out.unlink(missing_ok=True);out.write_bytes(built.stdout);out.chmod(0o700)
            run=started(out)
            assert (run.returncode,run.stdout,run.stderr)==(42,b'',b''),('exact limit run',run)
        def refused(bad,message):
            result=subprocess.run([str(compiler)],input=bad.encode(),capture_output=True,env={'PATH':''},timeout=300)
            assert (result.returncode,result.stdout,result.stderr)==(65,b'',message),('capacity rejection',len(bad),result.returncode,result.stderr)
        # The large sources are compiled side by side: each takes seconds. Positions
        # past 1, 2, 3, 4, 8 and 12 MiB carry bits 20 to 23, all of a position's
        # 24 (a value's flags are a byte of their own); the trace word keeps a
        # for's lines above bit 23.
        with ThreadPoolExecutor(4) as pool:
            jobs=[pool.submit(traced,compiler,root,total) for total in [0,1048575,1048577,2097200,3200000,4194305,8388609,12582913,LIMIT]]
            jobs+=[pool.submit(deep,compiler,root,0),pool.submit(deep,compiler,root,LIMIT),pool.submit(exact_runs),pool.submit(refused,exact+' ',OVER),pool.submit(refused,exact+'x'*4096,OVER),
                   pool.submit(refused,exact.replace('value+2','missing',1),REJECTED)]
            results=[job.result() for job in jobs]
        last=results[8]
        assert last.startswith('<stdin>:1677672:28: division by zero\n  at M.f0 (<stdin>:1677672)\n') and last.endswith('  at M.main (<stdin>:1258258)\n'),last
        # The compiler's arena is every program's: 16 GiB reserved lazily, halved
        # until the system grants it down to 4 MiB, and collected, so a small
        # address space is enough for a small program: 3 GiB and 32 MiB are,
        # 6 MiB is not (exit 71).
        for space,status in [(3<<30,0),(32<<20,0),(6<<20,71)]:
            result=subprocess.run([str(compiler)],input=program(0).encode(),capture_output=True,env={'PATH':''},timeout=120,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_AS,(space,space)))
            assert result.returncode==status and bool(result.stdout)==(status==0),('arena under an address-space limit',space,result.returncode,result.stderr)
        source=program(65540).replace('value=40\n value+2','text="é"\n if String.length(text) == 1 do 42 else 7 end')
        verify_program(source,compiler,root,'late Unicode/source cursor',42)
        # An image beyond 16 MiB whose one function holds more than 16 MiB of code
        # (lengths and the image size are 32-bit fields): 140000 statements
        # (a string literal is no longer copied where it is used, so each is 128 bytes).
        lines=140000
        source='defmodule M do\ndef f(n: integer): integer do\n if n == 0 do 5 else\n'+'IO.puts("7")\n'*lines+' 1 end\nend\ndef g(n: integer): integer do n * 2 end\ndef main() do System.halt(f(0) + g(f(0))) end\nend\n'
        built=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=300)
        assert (built.returncode,built.stderr)==(0,b''),('large image',built.returncode,built.stderr)
        assert len(built.stdout)>(16<<20)+1000000,('large image size',len(built.stdout))
        out=root/'large';out.unlink(missing_ok=True);out.write_bytes(built.stdout);out.chmod(0o700)
        run=started(out)
        assert (run.returncode,run.stdout,run.stderr)==(15,b'',b''),('large image run',run.returncode,len(run.stdout))
        # 100 functions of about 13KB each (100 statements of 128 bytes), the last ones called above the 1 MiB mark.
        count=100;lines=100
        body=lambda i:f'def f{i}(n: integer): integer do if n == 0 do {i} else\n'+f'IO.puts("{i}")\n'*lines+' 1 end end\n'
        source='defmodule M do\n'+''.join(body(i) for i in range(count))+f'def main() do System.halt(f{count-1}(0) + f0(0) + f{count-1}(1) - {count-42}) end\nend\n'
        small=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
        assert (small.returncode,small.stderr)==(0,b''),('1 MiB image',small.returncode,small.stderr)
        assert len(small.stdout)>(1<<20)+200000,('1 MiB image size',len(small.stdout))
        assert subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120).stdout==small.stdout,'image determinism'
        out=root/'calls';out.unlink(missing_ok=True);out.write_bytes(small.stdout);out.chmod(0o700)
        run=started(out)
        assert (run.returncode,run.stdout,run.stderr)==(42,f'{count-1}\n'.encode()*lines,b''),('1 MiB image run',run.returncode,len(run.stdout))
    print(f'PASS widened source cursors: declarations, bindings, calls, Unicode and failure traces up to the {LIMIT}-byte limit, refusal past it; a {len(built.stdout)}-byte image with one function above 16 MiB')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
