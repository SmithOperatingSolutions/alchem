#!/usr/bin/env python3
"""alchem's commands that print documentation (tools/alchem-guide.alc):
help, syntax, doc, docs, agent-guide and agent-install as the pinned command
line prints them, and version; the flags of build, run, check and new as
the pinned command line reads them; and doc of a source file, of a module
of the project in the current directory and of a package it imports
(tools/alchem-sources.alc); alx, the shell, in sessions; and fmt, which
formats files in place (tools/alchem-format.alc).

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

With --against nothing is built: the scenes of the cases are run by a pinned
command line and by an alchem, both given, and what the two give compared. That is the
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
PROJECT={
'lib/shapes.alc':'''defmodule Shapes do
  @moduledoc """
  Shapes and their areas.

  More about them.
  """

  @typedoc "A shape of the plane."
  type Shape do
    circle(radius: float)
    rect(width: float, height: float)
    empty
  end

  struct Box[t] do
    held: t
    count: integer = 0
  end

  @doc """
  The area of a shape.

      alx> Shapes.area(Shape.empty)
      0.0
  """
  def area(shape: Shape): float do
    case shape do
      Shape.circle(r) -> 3.14 * r * r
      Shape.rect(w, h) -> w * h
      Shape.empty -> 0.0
    end
  end

  def scale(0, shape: Shape): Shape do Shape.empty end
  def scale(n: integer, shape: Shape): Shape do shape end
  def scale(f: float, shape: Shape): Shape do shape end

  @doc "Says a word some times."
  def say(word: string, times: integer \\\\ 2): string do
    String.duplicate(word, times)
  end

  defp hidden(x: integer): integer do x end
end
''',
'lib/version.alc':'''defmodule Version do
  @moduledoc "The project's own versions."
  @doc "Reads a version."
  def parse(text: string): integer do
    String.length(text)
  end
end
''',
'main.alc':'''defmodule Main do
  import "lib/shapes.alc"
  import "example.com/Owner/repo@v1.0.0/lib/thing.alc"

  def helper(): integer do 1 end

  def main() do
    IO.puts("hi")
  end
end
''',
'test/shapes_test.alc':'''defmodule ShapesTest do
  import "../lib/shapes.alc"

  test "area" do
    assert(Shapes.area(Shapes.Shape.empty) == 0.0)
  end
end
''',
'.hidden/x.alc':'defmodule Hidden do\n  def area(): integer do 1 end\nend\n',
'node_modules/y.alc':'defmodule Noded do\n  def area(): integer do 1 end\nend\n',
'vendor/z.alc':'defmodule Vendored do\n  def area(): integer do 1 end\nend\n',
'notes.alc':'just notes, no module\n',
'home/go/pkg/mod/example.com/!owner/repo@v1.0.0/lib/thing.alc':'''defmodule Thing do
  import "util.alc"
  import "../other/far.alc"
  @moduledoc "A thing of a package."
  @doc "Makes an area of things."
  def make(n: integer): integer do Util.twice(n) end
end
''',
'home/go/pkg/mod/example.com/!owner/repo@v1.0.0/lib/util.alc':'defmodule Util do\n  @doc "Twice a number."\n  def twice(n: integer): integer do n * 2 end\nend\n',
'home/go/pkg/mod/example.com/!owner/repo@v1.0.0/other/far.alc':'defmodule Far do\n  def away(): integer do 1 end\nend\n',
}
PROJECT_LINES=[['doc','Shapes'],['doc','shapes'],['doc','Shapes.area'],['doc','shapes.AREA/1'],['doc','Shapes.scale'],['doc','Shapes.nope'],['doc','Shapes.are'],['doc','--json','Shapes'],['doc','--json','Shapes.area'],['doc','--json','Shapes.nope'],
['doc','Version'],['doc','Version.parse'],['doc','Version.compare'],['doc','--json','Version'],['doc','Main'],['doc','ShapesTest'],['doc','Hidden'],['doc','Noded'],['doc','Vendored'],['doc','Thing'],['doc','Thing.make'],['doc','Util'],['doc','Far'],['doc','--json','Util.twice'],
['doc','--search','area'],['doc','--search','version'],['doc','--search','--json','shapes'],['doc','--search','twice'],['doc','Nope'],['doc','lib/shapes.alc'],['doc','--json','lib/shapes.alc'],['doc','--all','Shapes'],['doc','Enum.map'],['doc','--json']]


def tree():
    """Source files of the repository, by path: the files the scene `files`
    documents one by one. Empty where the repository is not there: the
    scene is then as the cases hold it. ALCHEM_REPOSITORY names the
    repository where it is not the directory above this one's."""
    top=Path(os.environ.get('ALCHEM_REPOSITORY',ROOT.parent))
    paths=sorted((top/'examples/kv').rglob('*.alc'))+[top/'tests/fixtures'/name for name in ('protocols.alc','storage_test.alc','closures.alc')]+[top/'benchmarks/alchem/suite/processes.alc']
    return {path.relative_to(top).as_posix():path.read_text() for path in paths if path.exists()}


# alx: sessions, each the input of one run (an argument that begins with <
# is the input of its command line). No input here is refused by the
# compiler, whose message is not the pinned compiler's.
ALX=[['alx','<1 + 1\nx = 5\nx * 2\n{a, b} = {1, "two"}\nb\nIO.puts("hello")\ndef triple(n: integer): integer do\n  n * 3\nend\ntriple(x)\nimport "lib.alc"\nLib.twice(21)\n'
              'names: list[string] = ["a", "b"]\nEnum.map(names, fn n ->\n  String.upcase(n)\nend)\nh Enum.at\nh(Lib.twice)\nh Nope.nope\ndiv(1, 0)\nx\n\n:reset\n1.5 * 2.0\n:quit\nnot read\n'],
     ['alx','<struct Point do\n  x: integer\n  y: integer\nend\np = %Point{x: 1, y: 2}\np.x + p.y\ncase p do\n  %Point{x: 1} -> "one"\n  _ -> "other"\nend\n[1, 2, 3] |> Enum.map(fn n -> n * n end) |> Enum.sum()\n"a" <> "b"\nexit\n'],
     ['alx','<text = "a = b"\nString.length(text)\nlist = [1, 2]\n[first | rest] = list\nfirst\nrest\nraise("stopped here")\nfirst + 1\n'],
     ['alx','-h'],['alx','-zz']]
TREE=tree()
# fmt: files formatted and not, one the parser refuses, and directories with
# .git and artifacts, which are passed over; the command lines change the
# files one after another.
UNFORMATTED='\n'.join(line.lstrip(' ') for line in PROJECT['lib/shapes.alc'].split('\n')).replace(', ',',')
FORMATTING={'p/a.alc':PROJECT['lib/version.alc'],'p/b.alc':UNFORMATTED,'p/sub/c.alc':UNFORMATTED,'p/sub/deep/d.alc':PROJECT['main.alc'].replace('  ','    '),
    'p/sub/notes.txt':'not source\n','p/.git/e.alc':UNFORMATTED,'p/artifacts/f.alc':UNFORMATTED,'empty/notes.txt':'x\n','broken.alc':'defmodule X do\n  def f( do\nend\n',
    'ugly.alc':UNFORMATTED,'library.alc':'def twice(n: integer): integer do n * 2 end\n'}
FORMAT=[['fmt'],['fmt','-h'],['fmt','-zz','p'],['fmt','--check'],['fmt','missing.alc'],['fmt','empty'],['fmt','library.alc'],['fmt','--check','p'],['fmt','-check','p/a.alc'],
    ['fmt','-check','broken.alc','p'],['fmt','p/sub'],['fmt','--check','p'],['fmt','./p/'],['fmt','--check','p'],['fmt','p','p/b.alc'],['fmt','-check=false','ugly.alc'],['fmt','--check','.'],['fmt','.'],['fmt','--','ugly.alc']]
# Refusals the pinned compiler's loader gives, across files: an import
# missing, a private function, the arity of another module's function, main
# in an imported module, a protocol declared twice (AlchemCheck.merged).
LIBRARY='defmodule Lib do\n  def twice(n: integer): integer do n * 2 end\n  defp hidden(n: integer): integer do n end\n  def two(a: integer): integer do a end\n  def two(a: integer, b: integer): integer do a + b end\nend\n'
def entry(body, imports=('lib.alc',)):
    return 'defmodule Main do\n' + ''.join(f'  import "{i}"\n' for i in imports) + '  def main() do\n' + body + '  end\nend\n'
REFUSING={'lib.alc':LIBRARY,
    'missing.alc':entry('    IO.puts(Integer.to_string(Lib.twice(2)))\n', ()),
    'private.alc':entry('    IO.puts(Integer.to_string(Lib.hidden(2)))\n'),
    'arity.alc':entry('    IO.puts(Integer.to_string(Lib.two(1, 2, 3)))\n'),
    'reference.alc':entry('    f = &Lib.two\n    IO.puts("x")\n'),
    'fits.alc':entry('    IO.puts(Integer.to_string(Lib.two(1, 2)))\n'),
    'inner/main.alc':'defmodule Inner do\n  def main() do\n    IO.puts("x")\n  end\nend\n',
    'twomains.alc':entry('    IO.puts("y")\n', ('inner/main.alc',)),
    'a.alc':'defmodule A do\n  defprotocol Show do\n    def show(x)\n  end\nend\n',
    'b.alc':'defmodule B do\n  defprotocol Show do\n    def show(x)\n  end\nend\n',
    'protocols.alc':entry('    IO.puts("y")\n', ('a.alc', 'b.alc')),
    'deep/lib.alc':'defmodule Deep do\n  def f(n: integer): integer do Other.g(n) end\nend\n',
    'deep.alc':entry('    IO.puts(Integer.to_string(Deep.f(1)))\n', ('deep/lib.alc',)),
    'syntax.alc':entry('    x = [1, 2\n'),
    'gone.alc':entry('    IO.puts("x")\n', ('nothere.alc',))}
REFUSALS=[line for name in ('missing', 'private', 'arity', 'reference', 'fits', 'twomains', 'protocols', 'deep', 'syntax', 'gone') for line in (['check', name + '.alc'], ['check', '--json', name + '.alc'])]
SCENES=[
    ('alx',{'lib.alc':'defmodule Lib do\n  @doc "Twice a number."\n  def twice(n: integer): integer do n * 2 end\nend\n'},ALX),
    ('reads',{},READS),
    ('project',PROJECT,PROJECT_LINES),
    ('files',TREE,[line for path in TREE for line in (['doc',path],['doc','--json',path])]+[['doc','Protocol'],['doc','--search','subscribe'],['doc','--search','--json','reply']]),
    ('flags',{'lib.alc':'defmodule Lib do\n  def twice(n: integer): integer do n * 2 end\nend\n'},FLAGS),
    ('install',{'.clinerules/alchem.md':'mine\n','AGENTS.md':'# Agents\n\nRead the code.\n','.github/copilot-instructions.md':'a\n<!-- BEGIN alchem agent guide -->\nno end\n'},
     [['agent-install','claude'],['agent-install','claude'],['agent-install','--json','cursor'],['agent-install','--json','cursor'],['agent-install','windsurf'],
      ['agent-install','cline'],['agent-install','--force','cline'],['agent-install','--force','cline'],['agent-install','copilot'],['agent-install','agents'],['agent-install','agents'],
      ['agent-install','--scope','user','claude'],['agent-install','--scope=user','--json','agents'],['agent-install','--dir','sub/deep','claude'],['agent-install','--dir','./other/','--scope','user','agents'],
      ['agent-install','--scope','project','--dir','sub','windsurf']]),
    ('blocks',{'AGENTS.md':'before\n'+BLOCK+'\nafter\n','.github/copilot-instructions.md':BLOCK,'one/AGENTS.md':'\n\n','two/AGENTS.md':'x\n<!-- END alchem agent guide -->\n<!-- BEGIN alchem agent guide -->\n','three/AGENTS.md':'no newline at the end'},
     [['agent-install','agents'],['agent-install','copilot'],['agent-install','--dir','one','agents'],['agent-install','--dir','two','agents'],['agent-install','--dir','three','agents'],['agent-install','--dir','three','--json','agents']]),
    ('fmt',FORMATTING,FORMAT),
    ('refusals',REFUSING,REFUSALS),
    ('docs',{'held/cli-reference.md':'old\n'},
     [['docs','--check'],['docs'],['docs'],['docs','--check'],['docs','--dir','out/ref'],['docs','--dir','./dot/'],['docs','--check','--dir','held'],['docs','--dir','held'],['docs','-check=false','-dir=held'],['docs','x']]),
]


def cases():
    return json.loads(lzma.decompress(CASES.read_bytes()))


def lay(files,root):
    for path,text in files.items():
        (root/path).parent.mkdir(parents=True,exist_ok=True);(root/path).write_bytes(text.encode())


# What the pinned command's Go toolchain leaves in the home directory.
TOOLCHAIN=('home/.cache/','home/.config/go/','home/go/pkg/mod/cache/','home/AppData/')


def held(root):
    """The files under a directory, by path, but for the Go toolchain's own."""
    return {p.relative_to(root).as_posix():p.read_bytes().decode('utf8','replace') for p in sorted(root.rglob('*')) if p.is_file() and not p.relative_to(root).as_posix().startswith(TOOLCHAIN)}


def scene(command,files,lines,pinned=False):
    """A scene run by a command: what each command line gave, and the files
    left. The pinned command finds a package with the Go toolchain, which it
    is given (pinned); alchem is given none."""
    with tempfile.TemporaryDirectory(prefix='alchem-commands-') as d:
        root=Path(d).resolve();lay(files,root);(root/'home').mkdir(exist_ok=True)
        runs=[]
        for arguments in lines:
            given=''.join(a[1:] for a in arguments if a.startswith('<')).encode()
            run=subprocess.run([str(command)]+[a for a in arguments if not a.startswith('<')],input=given,capture_output=True,cwd=root,env=surroundings(root/'home',pinned,arguments[:1]==['alx']),timeout=900)
            runs.append([run.returncode]+[text.decode('utf8','replace').replace(str(root)+os.sep,'.'+os.sep).replace(json.dumps(str(root)+os.sep)[1:-1],json.dumps('.'+os.sep)[1:-1]) for text in (run.stdout,run.stderr)])
        return runs,held(root)


def surroundings(home,pinned=False,building=False):
    """The environment of a command line: the home directory, on Windows
    what a program needs to start, and for the pinned command the Go
    toolchain, kept from the network. Where the pinned command builds (alx)
    it has the surroundings of this program, with the packages its
    programs are made of."""
    if pinned and building:return dict(os.environ,HOME=str(home),USERPROFILE=str(home),GOTELEMETRY='off',GOCACHE=os.environ.get('GOCACHE',str(Path.home()/'.cache/go-build')),GOMODCACHE=os.environ.get('GOMODCACHE',str(ROOT/'.cache/gomod')),GOFLAGS='-mod=mod',GOTOOLCHAIN='local')
    go={'GOPROXY':'off','GOFLAGS':'-mod=mod','GOTOOLCHAIN':'local','GOTELEMETRY':'off'} if pinned else {}
    if os.name!='nt':return {'PATH':os.environ.get('PATH','/usr/bin:/bin') if pinned else '/usr/bin:/bin','HOME':str(home),**go}
    return {**{name:os.environ[name] for name in ('SystemRoot','SystemDrive','TEMP','TMP','PATH') if name in os.environ},'USERPROFILE':str(home),**go}


def against(pinned,alchem):
    count=0
    for name,files,lines in [(s['name'],s['files'],s['lines']) for s in cases()]:
        theirs,left=scene(pinned,files,lines,True);ours,kept=scene(alchem,files,lines)
        for arguments,seen,expected in zip(lines,ours,theirs):
            assert seen==expected,(name,arguments,seen,expected)
            count+=1
        assert kept==left,(name,{path:(kept.get(path),left.get(path)) for path in set(kept)|set(left) if kept.get(path)!=left.get(path)})
    runs,_=scene(alchem,{},[['version'],['version','--json']])
    assert runs[0][0]==0 and runs[0][1].startswith('alchem ') and runs[0][2]=='' and set(json.loads(runs[1][1]))=={'version','platform'},runs
    print(f'PASS commands: {count} command lines of help, syntax, doc (the library, files, a project and its packages), docs, agent-guide, agent-install, alx, fmt, the refusals of check and the flags of build, run, check and new in {len(cases())} scenes as {pinned.name} prints them, with the files they write; {runs[0][1].strip()}')


def platform(compiler):
    spec=spec_from_file_location('build_alchem',ROOT/'scripts/build-alchem.py');builder=module_from_spec(spec);spec.loader.exec_module(builder)
    return builder,builder.platform_of(compiler)


def verify(compiler):
    known=cases()
    # Where the repository is not there the scene of its files is the cases'.
    mine=[[name,files,lines] for name,files,lines in SCENES if name!='files' or TREE]
    assert mine==[[s['name'],s['files'],s['lines']] for s in known if s['name']!='files' or TREE],'harness/commands-cases.json.xz is not of these scenes: run scripts/generate-command-cases.py'
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
        # A refusal names the function the compiler could not make and where
        # it is: not the pinned compiler's message, so not of the scenes.
        refused={'lib/lib.alc':'defmodule Lib do\n  def ok(n: integer): integer do n end\n\n  def twice(n: integer): integer do\n    nope_here(n) * 2\n  end\nend\n',
                 'a.alc':'defmodule Main do\n  import "lib/lib.alc"\n  def main() do\n    IO.puts(Integer.to_string(Lib.twice(2)))\n  end\nend\n',
                 'b.alc':'defmodule Main do\n  def helper(x: integer): string do\n    x <> "a"\n  end\n  def main() do\n    IO.puts(helper(1))\n  end\nend\n'}
        runs,_=scene(alchem,refused,[['check','a.alc'],['build','b.alc'],['alx','<x = 1\nString.to_charlist("a")\ndef f(n: integer): string do\n  n <> "a"\nend\nx\n']])
        compiler='E_COMPILE: the native compiler does not take something in '
        assert runs[0]==[1,'',f'.{os.sep}lib{os.sep}lib.alc:4:3: {compiler}Lib.twice/1\n'],runs[0]
        assert runs[1]==[1,'',f'.{os.sep}b.alc:2:3: {compiler}Main.helper/1\n'],runs[1]
        assert f'alx(2)> ** {compiler}this input\nalx(3)> ...(3)> ...(3)> ** line 1: {compiler}f/1\nalx(4)> 1\n' in runs[2][1],runs[2]
        runs,_=scene(alchem,{},[['version'],['--version'],['version','--json'],['version','-json']])
        text=f'alchem v9.8.7-test {target}\n';data=json.dumps({'version':'v9.8.7-test','platform':target},indent=2)+'\n'
        assert runs==[[0,text,''],[0,text,''],[0,data,''],[0,data,'']],runs
    print(f'PASS commands: {count} command lines of help, syntax, doc (the library, files, a project and its packages), docs, agent-guide, agent-install, alx, fmt, the refusals of check and the flags of build, run, check and new in {len(known)} scenes as the pinned command line prints them, with the files they write; version for {target}; a refusal named by its function and place')


if __name__=='__main__':
    if sys.argv[1]=='--against':against(Path(sys.argv[2]).resolve(),Path(sys.argv[3]).resolve())
    else:verify(Path(sys.argv[1]).resolve())
