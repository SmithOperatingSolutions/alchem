#!/usr/bin/env python3
"""Regenerate harness/test-driver-cases.json.xz: the projects of the
test_driver gate with what the pinned command line prints in each. Not used
by normal builds.

harness/test-driver-projects.json.xz holds the projects (name -> path ->
text): made-up ones (tests that pass and fail, a file that does not
compile, one that ends before its tests are over, tags, fixtures with their
expected output, a program to run and build), the libraries whose coverage
was compared form by form, and the pinned tree's own examples/testing and
examples/kv. RUNS below are the command lines; each is run by
build/dev/alchem-upstream in a copy of its project, and by alchem
(scripts/build-alchem.py) built by build/dev/A2. For every test file of COVERS
the cover file the pinned runner's program writes under --cover is kept
(the runner removes it: a hard link is made as it appears) and compared
with the native program's. Only what the two agree on is written, since the
gate has to pass; the rest is printed."""
from pathlib import Path
import ctypes
import json
import lzma
import os
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'harness'))
import test_driver

UPSTREAM=ROOT/'build/dev/alchem-upstream'
NATIVE=ROOT/'build/dev/A2'
ENV=dict(os.environ,GOTOOLCHAIN='local',GOPROXY='off',GOFLAGS='-mod=mod',GOMODCACHE=str(ROOT/'.cache/gomod'))

# (project, command, arguments, standard input)
RUNS=[
    ('plain','test',['--seed','7','--cover','test'],''),
    ('plain','test',['--seed','3','--only','adds','--trace','test/calc_test.alc','test/sub'],''),
    ('plain','test',['--seed','3','-trace=false','--only','sum','test'],''),
    ('plain','test',['nothere'],''),
    ('plain','test',['lib'],''),
    ('plain','test',['--seed','5','--cover','--cover-min','90','test/calc_test.alc'],''),
    ('plain','test',['--seed','5','--cover','--cover-min','60.5','test/calc_test.alc'],''),
    ('plain','test',['--seed','5','-cover','-cover-min=100','test/calc_test.alc'],''),
    ('plain','test',['-zz','test'],''),
    ('plain','test',[],''),
    ('plain','test',['-seed'],''),
    ('plain','test',['-seed','x','test'],''),
    ('plain','test',['-cover=maybe','t'],''),
    ('plain','test',['-timeout','5','t'],''),
    ('plain','test',['-receive-timeout','1.5x','t'],''),
    ('plain','test',['-jobs','1.5','t'],''),
    ('plain','test',['-cover-min','x','t'],''),
    ('plain','test',['---seed','1','t'],''),
    ('plain','test',['-h'],''),
    ('plain','test',['--seed=11','--tag','slow','test/calc_test.alc'],''),
    ('plain','test',['--seed=11','--exclude','slow','--max-failures','1','test/sub','test/calc_test.alc'],''),
    ('plain','test',['--seed','12','test/crash_test.alc'],''),
    ('plain','test',['--seed','4','--timeout','1m30s','--receive-timeout','50ms','--jobs','2','test/calc_test.alc','test/calc_test.alc','test/./calc_test.alc'],''),
    ('plain','test',['--seed','18446744073709551615','test/calc_test.alc'],''),
    ('plain','test',['--seed','18446744073709551616','test/calc_test.alc'],''),
    ('plain','test',['--seed','9','--','test/calc_test.alc','lib/calc.alc'],''),
    ('plain','test',['--seed','9','lib/calc.alc'],''),
    ('plain','test',['--seed','21','--cover','.'],''),
    ('shapes','test',['--seed','7','--cover','.'],''),
    ('forms','test',['--seed','7','--cover','test'],''),
    ('more','test',['--seed','7','--cover','.'],''),
    ('lam','test',['--seed','7','--cover','.'],''),
    ('deep','test',['--seed','7','--cover','test'],''),
    ('deep','test',['--seed','8','--trace','test'],''),
    ('cart','test',['--seed','7','--cover','test'],''),
    ('cart','test',['--seed','9','.'],''),
    ('kv','test',['--seed','7','--cover','test/store_test.alc','test/protocol_test.alc'],''),
    ('fixtures','test',['.'],''),
    ('fixtures','test',['-timeout','0s','.'],''),
    ('mismatch','test',['.'],''),
    ('program','run',['main.alc','a','b'],'line1\n'),
    ('program','run',['main.alc'],''),
    ('program','run',['main.alc','--','x'],'one\ntwo\n'),
    ('program','run',[],''),
    ('program','run',['main.txt'],''),
    ('program','build',['-o','built','main.alc'],''),
    ('program','build',['-o','x','a.alc','b.alc'],''),
    ('program','build',['main.txt'],''),
    ('program','build',[],''),
    ('program','build',['-o'],''),
    ('program','build',['-zz','main.alc'],''),
    ('program','check',['main.alc'],''),
    ('program','check',['lib/util.alc'],''),
    ('kv','check',['main.alc'],''),
    ('kv','check',['lib/store.alc'],''),
    ('kv','check',['lib/web.alc'],''),
    ('kv','check',['lib/connection.alc'],''),
    ('kv','check',['test/store_test.alc'],''),
    ('kv','check',['test/server_test.alc'],''),
    ('kv','build',['-o','built','lib/store.alc'],''),
    ('program','check',[],''),
    ('program','check',['main.txt'],''),
    ('program','new',['my-app'],''),
    ('program','new',['sub/dir/Some_thing2'],''),
    ('program','new',['9bad'],''),
    ('program','new',['lib'],''),
    ('program','new',[],''),
    ('program','new',['a','b'],''),
    ('plain','test',['--max-failures','99999999999999999999','test'],''),
    ('plain','test',['--cover-min','1e999','test'],''),
    ('plain','test',['--jobs','-9223372036854775808','--seed','2','test/calc_test.alc'],''),
]
# (project, test file)
COVERS=[('plain','test/calc_test.alc'),('shapes','test/shapes_test.alc'),('forms','test/forms_test.alc'),('more','test/more_test.alc'),('lam','test/lam_test.alc'),('deep','test/deep_test.alc'),
        ('cart','test/cart_test.alc'),('kv','test/store_test.alc'),('kv','test/protocol_test.alc')]


def pinned(root,temporary,command,arguments,given):
    run=subprocess.run([str(UPSTREAM),command]+arguments,input=given.encode(),capture_output=True,cwd=root,env=dict(ENV,TMPDIR=str(temporary)),timeout=900)
    return [run.returncode,test_driver.shown(run.stdout.decode('utf8','replace'),root),test_driver.shown(run.stderr.decode('utf8','replace'),root)]


def pinned_cover(root,temporary,test):
    """The cover file of the pinned runner's program for one test file: linked as it appears, before the runner removes it."""
    work=Path(tempfile.mkdtemp(dir=temporary));keep=Path(tempfile.mkdtemp(dir=temporary))
    libc=ctypes.CDLL('libc.so.6',use_errno=True);made=0x100|0x8|0x80
    fd=libc.inotify_init();watched={libc.inotify_add_watch(fd,str(work).encode(),made):str(work)};stop=[False]
    def link(path,name):
        try:
            if (keep/name).exists():(keep/name).unlink()
            os.link(path,keep/name)
        except OSError:pass
    def watch():
        while not stop[0]:
            ready,_,_=select.select([fd],[],[],0.05)
            if not ready:continue
            data=os.read(fd,65536);at=0
            while at<len(data):
                descriptor,mask,_,size=struct.unpack_from('iIII',data,at);name=data[at+16:at+16+size].split(b'\0')[0].decode();at+=16+size
                base=watched.get(descriptor)
                if base is None:continue
                if mask&0x40000000:
                    added=libc.inotify_add_watch(fd,(base+'/'+name).encode(),made)
                    if added>=0:watched[added]=base+'/'+name
                    try:
                        for found in os.listdir(base+'/'+name):
                            if found.endswith('.cover'):link(base+'/'+name+'/'+found,found)
                    except OSError:pass
                elif name.endswith('.cover'):link(base+'/'+name,name)
    watcher=threading.Thread(target=watch);watcher.start()
    subprocess.run([str(UPSTREAM),'test','--jobs','1','--cover','--seed','7',test],capture_output=True,cwd=root,env=dict(ENV,TMPDIR=str(work)),timeout=900)
    stop[0]=True;watcher.join();os.close(fd)
    text=''.join((keep/name).read_text() for name in sorted(os.listdir(keep)))
    shutil.rmtree(work,ignore_errors=True);shutil.rmtree(keep,ignore_errors=True)
    return text.replace(str(root)+'/','')


def main():
    projects=json.loads(lzma.decompress((ROOT/'harness/test-driver-projects.json.xz').read_bytes()))
    runs=[];covers=[];differ=0
    with tempfile.TemporaryDirectory(prefix='alchem-test-driver-cases-') as top:
        base=Path(top);made=test_driver.tools(NATIVE,base);temporary=base/'tmp';temporary.mkdir()
        def fresh(name):
            root=base/'work'/name
            if root.exists():shutil.rmtree(root)
            root.mkdir(parents=True);test_driver.lay(projects[name],root)
            return root
        for project,command,arguments,given in RUNS:
            theirs=pinned(fresh(project),temporary,command,arguments,given)
            ours=test_driver.driven(NATIVE,made,fresh(project),temporary,command,arguments,given)
            if theirs==ours:runs.append([project,command,arguments,given]+theirs)
            else:differ+=1;print('DIFFERS',project,command,arguments,'\n  pinned',theirs,'\n  native',ours)
        for project,test in COVERS:
            theirs=pinned_cover(fresh(project),temporary,test)
            ours=test_driver.covered(NATIVE,made,fresh(project),temporary,test)
            if theirs==ours and theirs:covers.append([project,test,theirs])
            else:
                differ+=1;print('COVER DIFFERS',project,test)
                mine=ours.split('\n');yours=theirs.split('\n')
                for i in range(max(len(mine),len(yours))):
                    if i>=len(mine) or i>=len(yours) or mine[i]!=yours[i]:print('  line',i+1,'pinned',yours[i:i+3],'native',mine[i:i+3]);break
    used={run[0] for run in runs}|{cover[0] for cover in covers}
    (ROOT/'harness/test-driver-cases.json.xz').write_bytes(lzma.compress(json.dumps({'projects':{name:files for name,files in projects.items() if name in used},'runs':runs,'covers':covers}).encode(),preset=9))
    print(len(runs),'runs and',len(covers),'cover files written;',differ,'differ and are left out')


if __name__=='__main__':main()
