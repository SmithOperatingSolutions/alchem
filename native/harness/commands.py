#!/usr/bin/env python3
"""alchem's commands that print documentation (tools/alchem-guide.alc):
help, syntax, doc, docs, agent-guide and agent-install as the pinned command
line prints them, and version; and the flags of build, run, check and new
as the pinned command line reads them.

harness/commands-cases.json.xz holds scenes (scripts/generate-command-cases.py
makes it from the pinned command): the files a directory starts with, the
command lines run in it one after another with the status, standard output
and standard error of each, and the files the directory holds at the end.
alchem is built by the compiler under test and run through the same scenes:
the same status and text for every command line, and the same files.

version is not the pinned command's, which names the Go toolchain it builds
with: it is `alchem VERSION SYSTEM/MACHINE`, of the programs the compiler
makes, and the same two as JSON.

    commands.py COMPILER
    commands.py --against PINNED ALCHEM

With --against nothing is built: the scenes are run by a pinned command line
and by an alchem, both given, and what the two give compared. That is the
check on Windows, where the pinned command's paths have its separators."""
from pathlib import Path
import json
import lzma
import os
import subprocess
import sys
import tempfile
from importlib.util import module_from_spec,spec_from_file_location

ROOT=Path(__file__).resolve().parents[1]
CASES=Path(__file__).resolve().parent/'commands-cases.json.xz'

# Scenes: (name, files, command lines). HOME is the directory home of each.
READS=[[],['help'],['-h'],['--help'],['nope'],['help','syntax'],
    ['syntax'],['syntax','--all'],['syntax','--json'],['syntax','case'],['syntax','CASE'],['syntax','nope'],['syntax','cas'],['syntax','--json','case'],['syntax','--json','nope'],
    ['syntax','--group','basics'],['syntax','--group','Basics','--json'],['syntax','--group','zz'],['syntax','--group','data','case'],['syntax','a','b'],['syntax','-zz'],['syntax','-h'],['syntax','--help'],['syntax','--group'],['syntax','-all=maybe'],['syntax','---x'],['syntax','-all=false'],['syntax','-all=1','--'],['syntax','--','case'],['syntax','-','x'],
    ['doc'],['doc','--all'],['doc','--json'],['doc','--all','--json'],['doc','Enum'],['doc','enum'],['doc','--all','Enum'],['doc','Kernel'],['doc','Testing'],['doc','--all','Testing'],['doc','Enum.map'],['doc','enum.MAP/2'],['doc','abs'],['doc','assert'],['doc','--json','Enum.map'],['doc','--json','Enum'],['doc','Nope'],['doc','Enum.mapp'],['doc','Enum.ma'],['doc','IO.ANSI'],['doc','IO.ANSI.red'],['doc','/2'],
    ['doc','--group','text'],['doc','--group','files-and-system'],['doc','--group','Files and system','--json'],['doc','--group','nope'],['doc','--group','text','Enum'],['doc','--search','split'],['doc','--search','split','--json'],['doc','--search','zzzq'],['doc','--search','zzzq','--json'],['doc','--search',' '],['doc','--search','<'],['doc','--search','case'],['doc','--search','ENUM.MAP'],['doc','a','b'],['doc','-h'],['doc','Enum','--json'],['doc','-search'],['doc','-group=text'],
    ['agent-guide'],['agent-guide','--json'],['agent-guide','x'],['agent-guide','-h'],['agent-guide','-json=x'],
    ['agent-install','--list'],['agent-install','--list','--json'],['agent-install'],['agent-install','nope'],['agent-install','a','b'],['agent-install','--scope','zz','claude'],['agent-install','--scope','user','cursor'],['agent-install','-h'],
    ['docs','-h'],['docs','-zz'],['version','x'],['version','-h'],['version','-zz']]
BLOCK='<!-- BEGIN alchem agent guide -->\nold text\n<!-- END alchem agent guide -->\n'
# The flags of build, run, check and new, and what each says before it
# builds anything: no command line here needs a compiler to answer.
FLAGS=[['build','-h'],['run','-h'],['check','-h'],['new','-h'],['run','--help'],['build'],['run'],['check'],['new'],['new','a','b'],['new','-x','a'],
    ['build','-zz','ok.alc'],['run','-zz','ok.alc'],['check','-zz','ok.alc'],['build','-o'],['build','-trace=maybe','ok.alc'],['build','-timeout','x','ok.alc'],['build','-timeout','1.5','ok.alc'],
    ['build','-max-call-depth','x','ok.alc'],['build','-max-call-depth=1.5','ok.alc'],['build','-target','x','ok.alc'],['build','-target','a/b/c','ok.alc'],['build','ok.alc','lib.alc'],['build','ok.txt'],
    ['build','nothere.alc'],['build','-json','nothere.alc'],['build','-race','-trace=false','-timeout','1m30s','-shutdown-timeout','.5s','-max-call-depth','10','lib.alc'],['build','lib.alc'],['build','--','-lib.alc'],
    ['run','-timeout','x','ok.alc'],['run','-shutdown-timeout','1','ok.alc'],['run','-json','ok.alc'],['run','nothere.alc','a'],['run','-locked','-race','lib.alc'],['run','ok.txt'],
    ['check','a.alc','b.alc'],['check','nothere.alc'],['check','-json','nothere.alc'],['check','-json=maybe','lib.alc'],
    ['new','proj'],['new','proj'],['new','sub/my-app_2'],['new','9lives'],['new','--','-odd']]
SCENES=[
    ('reads',{},READS),
    ('flags',{'lib.alc':'defmodule Lib do\n  def twice(n: integer): integer do n * 2 end\nend\n'},FLAGS),
    ('install',{'.clinerules/alchem.md':'mine\n','AGENTS.md':'# Agents\n\nRead the code.\n','.github/copilot-instructions.md':'a\n<!-- BEGIN alchem agent guide -->\nno end\n'},
     [['agent-install','claude'],['agent-install','claude'],['agent-install','--json','cursor'],['agent-install','--json','cursor'],['agent-install','windsurf'],
      ['agent-install','cline'],['agent-install','--force','cline'],['agent-install','--force','cline'],['agent-install','copilot'],['agent-install','agents'],['agent-install','agents'],
      ['agent-install','--scope','user','claude'],['agent-install','--scope=user','--json','agents'],['agent-install','--dir','sub/deep','claude'],['agent-install','--dir','./other/','--scope','user','agents'],
      ['agent-install','--scope','project','--dir','sub','windsurf']]),
    ('blocks',{'AGENTS.md':'before\n'+BLOCK+'\nafter\n','.github/copilot-instructions.md':BLOCK,'one/AGENTS.md':'\n\n','two/AGENTS.md':'x\n<!-- END alchem agent guide -->\n<!-- BEGIN alchem agent guide -->\n','three/AGENTS.md':'no newline at the end'},
     [['agent-install','agents'],['agent-install','copilot'],['agent-install','--dir','one','agents'],['agent-install','--dir','two','agents'],['agent-install','--dir','three','agents'],['agent-install','--dir','three','--json','agents']]),
    ('docs',{'held/cli-reference.md':'old\n'},
     [['docs','--check'],['docs'],['docs'],['docs','--check'],['docs','--dir','out/ref'],['docs','--dir','./dot/'],['docs','--check','--dir','held'],['docs','--dir','held'],['docs','-check=false','-dir=held'],['docs','x']]),
]


def cases():
    return json.loads(lzma.decompress(CASES.read_bytes()))


def lay(files,root):
    for path,text in files.items():
        (root/path).parent.mkdir(parents=True,exist_ok=True);(root/path).write_bytes(text.encode())


def held(root):
    """The files under a directory, by path."""
    return {p.relative_to(root).as_posix():p.read_bytes().decode('utf8','replace') for p in sorted(root.rglob('*')) if p.is_file()}


def scene(command,files,lines):
    """A scene run by a command: what each command line gave, and the files left."""
    with tempfile.TemporaryDirectory(prefix='alchem-commands-') as d:
        root=Path(d).resolve();lay(files,root);(root/'home').mkdir()
        runs=[]
        for arguments in lines:
            run=subprocess.run([str(command)]+arguments,stdin=subprocess.DEVNULL,capture_output=True,cwd=root,env=surroundings(root/'home'),timeout=300)
            runs.append([run.returncode]+[text.decode('utf8','replace').replace(str(root)+os.sep,'.'+os.sep) for text in (run.stdout,run.stderr)])
        return runs,held(root)


def surroundings(home):
    """The environment of a command line: the home directory, and on Windows what a program needs to start."""
    if os.name!='nt':return {'PATH':'/usr/bin:/bin','HOME':str(home)}
    return {**{name:os.environ[name] for name in ('SystemRoot','SystemDrive','TEMP','TMP','PATH') if name in os.environ},'USERPROFILE':str(home)}


def against(pinned,alchem):
    count=0
    for name,files,lines in SCENES:
        theirs,left=scene(pinned,files,lines);ours,kept=scene(alchem,files,lines)
        for arguments,seen,expected in zip(lines,ours,theirs):
            assert seen==expected,(name,arguments,seen,expected)
            count+=1
        assert kept==left,(name,{path:(kept.get(path),left.get(path)) for path in set(kept)|set(left) if kept.get(path)!=left.get(path)})
    runs,_=scene(alchem,{},[['version'],['version','--json']])
    assert runs[0][0]==0 and runs[0][1].startswith('alchem ') and runs[0][2]=='' and set(json.loads(runs[1][1]))=={'version','platform'},runs
    print(f'PASS commands: {count} command lines of help, syntax, doc, docs, agent-guide, agent-install and the flags of build, run, check and new in {len(SCENES)} scenes as {pinned.name} prints them, with the files they write; {runs[0][1].strip()}')


def platform(compiler):
    spec=spec_from_file_location('build_alchem',ROOT/'scripts/build-alchem.py');builder=module_from_spec(spec);spec.loader.exec_module(builder)
    return builder,builder.platform_of(compiler)


def verify(compiler):
    known=cases()
    assert [[name,files,lines] for name,files,lines in SCENES]==[[s['name'],s['files'],s['lines']] for s in known],'harness/commands-cases.json.xz is not of these scenes: run scripts/generate-command-cases.py'
    builder,target=platform(compiler)
    with tempfile.TemporaryDirectory(prefix='alchem-commands-') as top:
        alchem=Path(top)/'alchem';builder.build(compiler,alchem,target.startswith('darwin/'),version='v9.8.7-test')
        count=0
        for expected in known:
            runs,left=scene(alchem,expected['files'],expected['lines'])
            for arguments,seen,pinned in zip(expected['lines'],runs,expected['runs']):
                assert seen==pinned,(expected['name'],arguments,seen,pinned)
                count+=1
            assert left==expected['left'],(expected['name'],{path:(left.get(path),expected['left'].get(path)) for path in set(left)|set(expected['left']) if left.get(path)!=expected['left'].get(path)})
        runs,_=scene(alchem,{},[['version'],['--version'],['version','--json'],['version','-json']])
        text=f'alchem v9.8.7-test {target}\n';data=json.dumps({'version':'v9.8.7-test','platform':target},indent=2)+'\n'
        assert runs==[[0,text,''],[0,text,''],[0,data,''],[0,data,'']],runs
    print(f'PASS commands: {count} command lines of help, syntax, doc, docs, agent-guide, agent-install and the flags of build, run, check and new in {len(known)} scenes as the pinned command line prints them, with the files they write; version for {target}')


if __name__=='__main__':
    if sys.argv[1]=='--against':against(Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve())
    else:verify(Path(sys.argv[1]).resolve())
