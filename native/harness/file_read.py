#!/usr/bin/env python3
"""File.read/File.write results and reasons against the pinned runtime's os rules."""
import errno
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
from native_memory import floor_arena

ROOT=Path(__file__).resolve().parents[1]
MESSAGES=[m.encode() for m in json.loads((ROOT/'spec/errno-messages.json').read_text())['messages']]
SHOW='def show(r: result[string,string]): string do case r do ok(s) -> "ok:" <> s error(e) -> "error:" <> e end end '


def reason(code):
    return MESSAGES[code] if code<len(MESSAGES) else b'errno %d'%code


def expected(path):
    """os.Open(O_RDONLY|O_CLOEXEC), io.ReadAll, utf8.Valid, as in the pinned fileRead."""
    if b'\0' in path:return b'error:open '+path+b': '+reason(errno.EINVAL)
    try:fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC)
    except OSError as e:return b'error:open '+path+b': '+reason(e.errno)
    data=b''
    try:
        while chunk:=os.read(fd,1<<20):data+=chunk
    except OSError as e:return b'error:read '+path+b': '+reason(e.errno)
    finally:os.close(fd)
    try:data.decode('utf-8')
    except UnicodeDecodeError:return b'error:file is not valid UTF-8'
    return b'ok:'+data


def write_failure(path,content):
    """os.WriteFile(path,content,0644) for a path expected to fail; returns its reason."""
    if b'\0' in path:return b'error:open '+path+b': '+reason(errno.EINVAL)
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC|os.O_CLOEXEC,0o644)
    except OSError as e:return b'error:open '+path+b': '+reason(e.errno)
    try:
        os.write(fd,content)
    except OSError as e:return b'error:write '+path+b': '+reason(e.errno)
    finally:os.close(fd)
    raise AssertionError(('expected a failing write',path))


def literal(data):
    # String literals hold at most 128 bytes; longer paths are concatenated.
    if len(data)>128:return '('+literal(data[:128])+' <> '+literal(data[128:])+')'
    return '"'+''.join(chr(b) if 32<=b<127 and b not in (34,35,92) else f'\\x{b:02x}' for b in data)+'"'


def build(compiler,source,root,name='out'):
    r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
    assert (r.returncode,r.stderr)==(0,b''),(source[:300],r.returncode,r.stderr)
    out=root/name;out.write_bytes(r.stdout);out.chmod(0o700);return out


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-file-read-') as d:
        root=Path(d);base=bytes(root)
        files={b'text':'hello\nwörld 中 😀\r\n'.encode(),b'empty':b'',b'nul':b'a\0b',b'bad':b'ok\xff',b'surrogate':b'\xed\xa0\x80',
               b'trunc':b'x\xe2\x82',b'\xc3\xa9name':b'accent',b'raw\xffname':b'raw',b'big':b'y'*500000}
        for name,data in files.items():(root/os.fsdecode(name)).write_bytes(data)
        (root/'dir').mkdir();(root/'locked').write_bytes(b'secret');(root/'locked').chmod(0)
        os.symlink('loop',root/'loop');os.symlink('text',root/'link')
        paths=[base+b'/'+name for name in files]+[base+b'/dir',base+b'/locked',base+b'/missing',base+b'/text/child',base+b'/loop',base+b'/link',
               base+b'/'+b'n'*300,b'',b'a\0b',base+b'/text\0',b'/dev/null',base+b'/dir/',base+b'/text/']
        if os.geteuid()==0:paths.remove(base+b'/locked')
        checked=0
        for first in range(0,len(paths),12):
            batch=paths[first:first+12]
            source='defmodule M do '+SHOW+'def main() do\n'+''.join(f'IO.puts(show(File.read({literal(p)})))\n' for p in batch)+'System.halt(0) end end'
            run=subprocess.run([str(build(compiler,source,root))],capture_output=True,env={'PATH':''},timeout=120)
            want=b''.join(expected(p)+b'\n' for p in batch)
            if (run.returncode,run.stdout,run.stderr)!=(0,want,b''):
                for p in batch:
                    single='defmodule M do '+SHOW+f'def main() do IO.puts(show(File.read({literal(p)})))\nSystem.halt(0) end end'
                    one=subprocess.run([str(build(compiler,single,root,'one'))],capture_output=True,env={'PATH':''},timeout=120)
                    assert (one.returncode,one.stdout)==(0,expected(p)+b'\n'),(p,one.returncode,one.stdout[:200],expected(p)[:200])
                raise AssertionError(('File.read batch',run.returncode))
            checked+=len(batch)
        # A file is bounded by the arena alone (16 GiB reserved lazily): 5 MB is read.
        # Larger than the arena, here its 4 MiB floor: exit71, as for IO.read_all.
        (root/'huge').write_bytes(b'z'*5000000)
        source='defmodule M do '+SHOW+f'def main() do x = File.read({literal(base+b"/huge")})\nSystem.halt(case x do ok(text) -> rem(byte_size(text),251) error(e) -> 1 end) end end'
        huge=build(compiler,source,root)
        run=subprocess.run([str(huge)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(5000000%251,b'',b''),('File.read past 4 MiB',run)
        run=subprocess.run([str(huge)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(huge))
        assert (run.returncode,run.stdout,run.stderr)==(71,b'',b''),('File.read arena',run)
        # The pinned runtime reads a file of at most 16,777,216 bytes.
        (root/'most').write_bytes(b'z'*16777216);(root/'more').write_bytes(b'z'*16777217)
        size=lambda name:'IO.puts(case File.read('+literal(base+b'/'+name)+') do ok(text) -> Integer.to_string(byte_size(text)) error(e) -> e end)\n'
        run=subprocess.run([str(build(compiler,'defmodule M do def main() do '+size(b'most')+size(b'more')+'System.halt(0) end end',root))],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(0,b'16777216\nfile exceeds 16777216 bytes\n',b''),('File.read limit',run.returncode,run.stdout[:200],run.stderr[:200])
        # Every read closes its descriptor: 200 reads under a 16-descriptor limit.
        loop=f'def f(n: integer): integer do if n == 0 do 0 else case File.read({literal(base+b"/text")}) do ok(s) -> byte_size(s) error(e) -> 1000 end + f(n-1) end end '
        program=build(compiler,'defmodule M do '+loop+'def main() do System.halt(f(200)-200*'+str(len(files[b'text']))+'+42) end end',root,'reuse')
        limit=lambda:resource.setrlimit(resource.RLIMIT_NOFILE,(16,16))
        run=subprocess.run([str(program)],capture_output=True,env={'PATH':''},preexec_fn=limit,timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(42,b'',b''),('descriptor reuse',run)
        # File.write: successes checked on disk, failures against os.WriteFile's reasons.
        unit='def done(r: result[tuple[],string]): string do case r do ok(u) -> "ok" error(e) -> "error:" <> e end end '
        (root/'old').write_bytes(b'previous longer contents');(root/'keepmode').write_bytes(b'x');(root/'keepmode').chmod(0o600)
        (root/'readonly').write_bytes(b'r');(root/'readonly').chmod(0o400);os.symlink('target',root/'wlink')
        successes=[(b'new','héllo\n'.encode()),(b'old',b'short'),(b'blank',b''),(b'binary',b'\x00\xff\xfe'),(b'w\xffname',b'raw name'),(b'wlink',b'through link'),(b'keepmode',b'kept')]
        failures=[base+b'/nodir/file',base+b'/dir',base+b'/text/child',base+b'/loop',base+b'/'+b'n'*300,b'',b'a\0b',b'/dev/full']
        if os.geteuid()!=0:failures.append(base+b'/readonly')
        body=''.join(f'IO.puts(done(File.write({literal(base+b"/"+name)},{literal(data)})))\n' for name,data in successes)
        run=subprocess.run([str(build(compiler,'defmodule M do '+unit+'def main() do\n'+body+'System.halt(0) end end',root))],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(0,b'ok\n'*len(successes),b''),('File.write successes',run)
        for name,data in successes:
            assert (root/os.fsdecode(name)).read_bytes()==data,('written contents',name)
        assert (root/'target').read_bytes()==b'through link' and (root/'wlink').is_symlink()
        umask=os.umask(0);os.umask(umask)
        assert (root/'new').stat().st_mode&0o777==0o644&~umask and (root/'keepmode').stat().st_mode&0o777==0o600,'File.write modes'
        body=''.join(f'IO.puts(done(File.write({literal(path)},"data")))\n' for path in failures)
        run=subprocess.run([str(build(compiler,'defmodule M do '+unit+'def main() do\n'+body+'System.halt(0) end end',root))],capture_output=True,env={'PATH':''},timeout=120)
        want=b''.join(write_failure(path,b'data')+b'\n' for path in failures)
        assert (run.returncode,run.stdout,run.stderr)==(0,want,b''),('File.write failures',run.stdout[:400],want[:400])
        # File.append creates or extends; File.remove unlinks files and empty directories.
        (root/'emptydir').mkdir();(root/'fulldir').mkdir();(root/'fulldir/child').write_bytes(b'c');(root/'gone').write_bytes(b'g')
        steps=[('append',b'log',b'one\n',b'ok'),('append',b'log',b'two\n',b'ok'),('append',b'appended',b'!',b'ok'),('append',b'dir',b'x',None),('append',b'nodir/f',b'x',None),
               ('remove',b'gone',None,b'ok'),('remove',b'gone',None,None),('remove',b'emptydir',None,b'ok'),('remove',b'fulldir',None,None),('remove',b'text/child',None,None),('remove',b'a\0b',None,None)]
        def failure(kind,path):
            if kind=='append':
                try:os.close(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_CLOEXEC,0o644))
                except OSError as e:return b'error:open '+path+b': '+reason(e.errno)
                raise AssertionError(('expected a failing append',path))
            # os.Remove: unlink, then rmdir; rmdir's error unless it is ENOTDIR.
            if b'\0' in path:return b'error:remove '+path+b': '+reason(errno.EINVAL)
            try:os.unlink(path)
            except OSError as first:
                try:os.rmdir(path)
                except OSError as second:return b'error:remove '+path+b': '+reason(first.errno if second.errno==errno.ENOTDIR else second.errno)
            raise AssertionError(('expected a failing remove',path))
        calls=[f'File.append({literal(base+b"/"+name)},{literal(data)})' if kind=='append' else f'File.remove({literal(name if b"\0" in name else base+b"/"+name)})' for kind,name,data,_ in steps]
        run=subprocess.run([str(build(compiler,'defmodule M do '+unit+'def main() do\n'+''.join(f'IO.puts(done({call}))\n' for call in calls)+'System.halt(0) end end',root))],capture_output=True,env={'PATH':''},timeout=120)
        want=b''.join((outcome or failure(kind,name if b'\0' in name else base+b'/'+name))+b'\n' for kind,name,_,outcome in steps)
        assert (run.returncode,run.stdout,run.stderr)==(0,want,b''),('File.append/remove',run.stdout[:500],want[:500])
        assert (root/'log').read_bytes()==b'one\ntwo\n' and (root/'appended').read_bytes()==b'!' and (root/'big').read_bytes()==files[b'big']
        assert not (root/'gone').exists() and not (root/'emptydir').exists() and (root/'fulldir/child').exists(),'File.remove effects'
        rewrite=f'def f(n: integer): integer do if n == 0 do 0 else case File.write({literal(base+b"/again")},"x") do ok(u) -> 1 error(e) -> 1000 end + f(n-1) end end '
        program=build(compiler,'defmodule M do '+rewrite+'def main() do System.halt(f(200)-158) end end',root,'rewrite')
        run=subprocess.run([str(program)],capture_output=True,env={'PATH':''},preexec_fn=limit,timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(42,b'',b''),('write descriptor reuse',run)
        writer=build(compiler,'defmodule M do '+unit+f'def main() do IO.puts(done(File.write({literal(base+b"/traced")},"traced data")))\nSystem.halt(0) end end',root,'writer')
        injected=0;tracer=shutil.which('strace')
        program=build(compiler,'defmodule M do '+SHOW+f'def main() do IO.puts(show(File.read({literal(base+b"/text")})))\nSystem.halt(0) end end',root,'trace')
        if tracer:
            for rule in ['open:error=EINTR:when=1','read:error=EINTR:when=1']:
                r=subprocess.run([tracer,'-qq','-o',str(root/'trace.log'),'-e','inject='+rule,str(program)],capture_output=True,timeout=120)
                if b'ptrace' in r.stderr and b'Operation not permitted' in r.stderr:print('SKIP File.read injection: ptrace unavailable');continue
                assert (r.returncode,r.stdout,r.stderr)==(0,expected(base+b'/text')+b'\n',b''),(rule,r)
                injected+=1
            r=subprocess.run([tracer,'-qq','-o',str(root/'trace.log'),'-e','inject=read:error=EIO:when=1',str(program)],capture_output=True,timeout=120)
            if not (b'ptrace' in r.stderr and b'Operation not permitted' in r.stderr):
                assert (r.returncode,r.stdout,r.stderr)==(0,b'error:read '+base+b'/text: input/output error\n',b''),r
                injected+=1
            # The first write is the file's; IO.puts follows. close has one caller.
            for rule,want in [('write:error=EINTR:when=1',b'ok\n'),('write:error=EIO:when=1',b'error:write '+base+b'/traced: input/output error\n'),
                              ('close:error=EIO:when=1',b'error:close '+base+b'/traced: input/output error\n')]:
                r=subprocess.run([tracer,'-qq','-o',str(root/'trace.log'),'-e','inject='+rule,str(writer)],capture_output=True,timeout=120)
                if b'ptrace' in r.stderr and b'Operation not permitted' in r.stderr:print('SKIP File.write injection: ptrace unavailable');continue
                assert (r.returncode,r.stdout,r.stderr)==(0,want,b''),(rule,r)
                injected+=1
        else:print('SKIP File.read/write injection: strace unavailable')
        rejections=['x = File.read(1)','x = File.read()','x = File.read("a","b")','x = File.read(b[97])','x = File.read','x = File.write("a")',
                    'x = File.write(1,"a")','x = File.write("a",1)','x = File.write("a","b","c")','x: string = File.write("a","b")','x = File.rename("a")','x = File.append("a")','x = File.remove("a","b")','x = File.remove(1)']
        for statement in rejections:
            source='defmodule M do def main() do '+statement+'\nSystem.halt(0) end end'
            r=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stdout)==(65,b''),(statement,r)
    print(f'File syscall injections: {injected}/6')
    print(f'PASS File.read/write: {checked} read paths vs os.Open/ReadAll/utf8.Valid oracle, {len(successes)} writes checked on disk, {len(failures)} write failures vs os.WriteFile reasons, {len(steps)} append/remove steps, arena limit, descriptor reuse, {len(rejections)} rejections')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
