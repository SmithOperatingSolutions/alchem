#!/usr/bin/env python3
"""Run every example of the pinned compiler's syntax and library references
through the pinned compiler and the native one and count the examples whose
output agrees. Not a gate: the count says how much of the pinned language the
native compiler covers and what to build next.

usage: upstream-examples.py [--only PREFIX] [--show N] [--compiler PATH] [--refresh]

  --only PREFIX    examples whose name starts with it: syntax/, lib/Enum/
  --show N         print the first N failures with what was expected
  --compiler PATH  the native compiler (default build/dev/A2, which
                   scripts/verify-quick.py --build-only builds)
  --refresh        run the pinned compiler again for the examples chosen,
                   in place of what is kept (an answer kept from a run in a
                   directory that was not empty stays wrong until then: the
                   File.mkdir and File.rmdir examples were such)

The pinned compiler is built once from the module cache into
build/dev/alchem-upstream, and what it prints is kept in
build/dev/upstream-examples.json. A syntax example that is not a module is
wrapped in one; a library session becomes one program that prints inspect()
of each line that shows a value. Every program runs in an empty directory.
"""
import subprocess,os,sys,re,json,hashlib,tempfile,collections,time,resource
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
REPO=str(Path(__file__).resolve().parents[1])
CACHE=REPO+'/.cache/gomod'
U=str(next(Path(CACHE+'/github.com/!smith!operating!solutions').glob('alchem@*')))
HERE=REPO+'/build/dev'
UP=HERE+'/alchem-upstream'
env=dict(os.environ,GOTOOLCHAIN='local',GOPROXY='off',GOFLAGS='-mod=mod',GOMODCACHE=CACHE)
def build_upstream():
    # The pinned compiler is the binary alchem-upstream.bin; alchem-upstream is
    # a wrapper that runs it under scripts/limited, because a program it runs
    # has no memory ceiling of its own (an endless stream collected into a
    # list took 58 GB and the machine with it).
    real=UP+'.bin'
    if not os.path.exists(real):
        os.makedirs(HERE,exist_ok=True)
        subprocess.run(['go','build','-o',real,'./cmd/alchem'],cwd=U,env=env,check=True)
    wrapper='#!/usr/bin/env bash\nexport ALCHEM_MEMORY="${ALCHEM_MEMORY:-4G}" ALCHEM_SECONDS="${ALCHEM_SECONDS:-120}"\nexec "'+REPO+'/scripts/limited" "'+real+'" "$@"\n'
    if not os.path.exists(UP) or open(UP,'rb').read()!=wrapper.encode():
        if os.path.exists(UP):os.remove(UP)
        open(UP,'w').write(wrapper);os.chmod(UP,0o755)
def wrap(body):
    return 'defmodule T do\n  def main() do\n'+''.join('    '+l+'\n' for l in body.split('\n'))+'  end\nend\n'
def cases():
    out=[]
    # syntax reference: fenced blocks per section
    sec=None;n=0;block=None
    for line in open(U+'/docs/syntax-reference.md').read().split('\n'):
        if block is None and line.startswith('## '):sec=line[3:];n=0
        elif line.startswith('```elixir') and block is None:block=[]
        elif line=='```' and block is not None:
            src='\n'.join(block);n+=1
            out.append((f'syntax/{sec}/{n}',src+'\n' if re.search(r'^defmodule ',src,re.M) else wrap(src)));block=None
        elif block is not None:block.append(line)
    # library reference: alx> examples
    mod=fn=None;block=None;n=0
    for line in open(U+'/docs/library-reference.md').read().split('\n'):
        if block is None and line.startswith('## '):mod=line[3:]
        elif block is None and line.startswith('### '):fn=line[4:];n=0
        elif line.startswith('```elixir') and block is None:block=[]
        elif line=='```' and block is not None:
            entries=[]
            for l in block:
                if l.startswith('alx> '):entries.append([l[5:],False])
                elif l.startswith('...> ') and entries:entries[-1][0]+='\n'+l[5:]
                elif l.strip() and entries:entries[-1][1]=True
            body='\n'.join('IO.puts(inspect('+e+'))' if shown else e for e,shown in entries)
            if entries:n+=1;out.append((f'lib/{mod}/{fn}/{n}',wrap(body)))
            block=None
        elif block is not None:block.append(line)
    return out
def upstream(src):
    with tempfile.TemporaryDirectory(dir=HERE) as d:
        open(d+'/p.alc','w').write(src)
        try:u=subprocess.run([UP,'run',d+'/p.alc'],capture_output=True,env=env,timeout=120,stdin=subprocess.DEVNULL,cwd=d)
        except subprocess.TimeoutExpired:return [124,'','timeout']
        return [u.returncode,u.stdout.decode('utf8','replace'),u.stderr.decode('utf8','replace').replace(d+'/p.alc','<stdin>')]
def native(src,comp):
    with tempfile.TemporaryDirectory(dir=HERE) as d:
        try:n=subprocess.run([comp],input=src.encode(),capture_output=True,env={'PATH':''},timeout=60)
        except subprocess.TimeoutExpired:return ['compile-timeout',0,'','']
        if n.returncode:return ['reject',n.returncode,'','']
        open(d+'/p','wb').write(n.stdout);os.chmod(d+'/p',0o700)
        for attempt in range(50):
            # Another thread's fork may still hold the file open for writing.
            # A native program reserves its arena lazily, up to 16 GiB: under an
            # address-space limit it settles for less, so a runaway example
            # cannot take the machine's memory.
            try:r=subprocess.run([d+'/p'],capture_output=True,timeout=20,stdin=subprocess.DEVNULL,cwd=d,preexec_fn=lambda:resource.setrlimit(resource.RLIMIT_AS,(3<<30,3<<30)));break
            except subprocess.TimeoutExpired:return ['run-timeout',0,'','']
            except OSError as error:
                if error.errno!=26 or attempt==49:raise
                time.sleep(0.01)
        return ['ran',r.returncode,r.stdout.decode('utf8','replace'),r.stderr.decode('utf8','replace')]
DROPPED={'syntax/extern'}
def main():
    build_upstream()
    a=sys.argv[1:];only='';show=0;comp=REPO+'/build/dev/A2';refresh=False
    while a:
        f=a.pop(0)
        if f=='--only':only=a.pop(0)
        elif f=='--show':show=int(a.pop(0))
        elif f=='--compiler':comp=a.pop(0)
        elif f=='--refresh':refresh=True
    cs=[c for c in cases() if c[0].startswith(only)]
    cache_path=HERE+'/upstream-examples.json'
    cache=json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    key=lambda s:hashlib.sha1(s.encode()).hexdigest()
    todo=[c for c in cs if refresh or key(c[1]) not in cache]
    with ThreadPoolExecutor(8) as ex:
        for c,r in zip(todo,ex.map(lambda c:upstream(c[1]),todo)):cache[key(c[1])]=r
    if todo:json.dump(cache,open(cache_path,'w'))
    with ThreadPoolExecutor(14) as ex:res=list(ex.map(lambda c:native(c[1],comp),cs))
    tot=collections.Counter();ok=collections.Counter();fails=[];skipped=0;dropped=0
    for (name,src),r in zip(cs,res):
        u=cache[key(src)]
        g='/'.join(name.split('/')[:2])
        # extern binds a function to a Go function by name; a native program has
        # no Go runtime to call, and extern is dropped in favour of running
        # external processes, so its examples are not counted.
        if g in DROPPED:dropped+=1;continue
        if u[0]!=0:skipped+=1;continue   # example needs context upstream itself does not accept standalone
        tot[g]+=1
        if r[0]=='ran' and r[1]==0 and r[2]==u[1]:ok[g]+=1
        else:fails.append((name,src,u,r))
    for g in sorted(tot):print(f'{g:28} {ok[g]:4}/{tot[g]:4}')
    print(f'TOTAL {sum(ok.values())}/{sum(tot.values())}  (upstream itself fails standalone: {skipped}; dropped by decision: {dropped})')
    json.dump([(n,s,u,r) for n,s,u,r in fails],open(HERE+'/upstream-examples-failures.json','w'),indent=0)
    for n,s,u,r in fails[:show]:print('---',n,r[0],r[1],'\n'+s,'want',repr(u[1][:200]),'got',repr(r[2][:200]),repr(r[3][:200]))
if __name__=='__main__':main()
