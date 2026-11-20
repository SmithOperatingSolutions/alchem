#!/usr/bin/env python3
"""Multi-module programs: bundled imports, qualified calls and their rules."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
from run import FUNCTION_LIMIT,at_limit

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_bundle',ROOT/'scripts/bundle-alchem.py')
bundler=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundler)

UTIL='defmodule Util do\n  def twice(n: integer): integer do\n    n * 2\n  end\n\n  defp hidden(n: integer): integer do\n    n\n  end\nend\n'
MATH='defmodule Math do\n  import "util.alc"\n\n  def double(n: integer): integer do\n    Util.twice(n)\n  end\n\n  defp secret(n: integer): integer do\n    n\n  end\n\n  def helper(n: integer): integer do\n    secret(n) + 1\n  end\nend\n'


def app(imports,body,extra=''):
    lines=''.join(f'  import "{path}"\n' for path in imports)
    return 'defmodule App do\n'+lines+extra+'  def main() do\n'+''.join(f'    {line}\n' for line in body)+'    System.halt(0)\n  end\nend\n'


def padded(text,size):
    """text with a comment line that makes it size bytes."""
    return text+'#'*(size-len(text)-1)+'\n'


# (files, stdout): outcomes confirmed against the pinned upstream `alchem run`.
PROJECTS=[
    ({'app.alc':app(['lib/math.alc'],['IO.puts(Integer.to_string(Math.double(21)))','IO.puts(Integer.to_string(double(1)))','IO.puts(Integer.to_string(Math.helper(1)))'],
                    '  def double(n: integer): integer do\n    n + 100\n  end\n\n'),'lib/math.alc':MATH,'lib/util.alc':UTIL},b'42\n101\n2\n'),
    ({'app.alc':app(['lib/math.alc','lib/math.alc','lib/util.alc'],['IO.puts(Integer.to_string(Math.double(1) + Util.twice(1)))']),'lib/math.alc':MATH,'lib/util.alc':UTIL},b'4\n'),
    ({'app.alc':app(['util.alc'],['IO.puts(Integer.to_string(App.f(1) + Util.twice(1)))'],'  def f(n: integer): integer do\n    n\n  end\n\n'),'util.alc':UTIL},b'3\n'),
    # Imports may follow functions, and paths are relative to the importing file.
    ({'src/app.alc':'defmodule App do\n  def f(n: integer): integer do\n    Util.twice(n)\n  end\n\n  import "../shared/util.alc"\n\n  def main() do\n    IO.puts(Integer.to_string(f(1)))\n    System.halt(0)\n  end\nend\n',
      'shared/util.alc':UTIL},b'2\n'),
    # References and captures of imported functions.
    ({'app.alc':app(['util.alc'],['IO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2], &Util.twice)) + Enum.sum(Enum.map([1, 2], &Util.twice/1))))',
                                  'IO.puts(Integer.to_string(Enum.sum(Enum.map([1, 2], &Util.twice(&1 + 1))) + Enum.sum(Enum.map([1, 2], &twice/1))))','f = &Util.twice/1','IO.puts(Integer.to_string(f(4)))'],
                    '  def twice(n: integer): integer do\n    n + 100\n  end\n\n'),'util.alc':UTIL},b'12\n213\n8\n'),
    # Generic functions of an imported module, called and referenced with and without arity.
    ({'app.alc':app(['kept.alc'],['f: fn[string, string] = &Kept.keep/1','g: fn[list[integer], list[integer], boolean] = &Kept.equal','IO.puts(f("q") <> Kept.keep("k") <> Integer.to_string(Kept.keep(7)))',
                                 'IO.puts(if g([1], [1]) and Kept.equal("a", "a") and Kept.equal({1, "x"}, {1, "y"}) == false do "yes" else "no" end)']),
      'kept.alc':'defmodule Kept do\n  def keep(x: t): t do\n    x\n  end\n\n  def equal(x: t, y: t): boolean do\n    x == y\n  end\n\n  defp secret(x: t): t do\n    x\n  end\nend\n'},b'qk7\nyes\n'),
    # A diamond: both branches import the same file, which is bundled once.
    ({'app.alc':app(['a.alc','b.alc'],['IO.puts(A.name() <> B.name())']),
      'a.alc':'defmodule A do\n  import "tagger.alc"\n\n  def name(): string do\n    "a" <> Tagger.tag()\n  end\nend\n',
      'b.alc':'defmodule B do\n  import "tagger.alc"\n\n  def name(): string do\n    "b" <> Tagger.tag()\n  end\nend\n',
      'tagger.alc':'defmodule Tagger do\n  def tag(): string do\n    "!"\n  end\nend\n'},b'a!b!\n'),
    # A file of exactly 1 MiB is read; one byte more is not (UNBUNDLED).
    ({'app.alc':app(['big.alc'],['IO.puts(Integer.to_string(Util.twice(1)))']),'big.alc':padded(UTIL,1048576)},b'2\n'),
]
# Compiler rejections (exit65) for bundles that break a visibility rule.
REJECTED=[
    ({'app.alc':app(['lib/math.alc'],['IO.puts(Integer.to_string(Math.secret(1)))']),'lib/math.alc':MATH,'lib/util.alc':UTIL},'private function'),
    ({'app.alc':app(['lib/math.alc'],['IO.puts(Integer.to_string(helper(1)))']),'lib/math.alc':MATH,'lib/util.alc':UTIL},'unqualified imported function'),
    ({'app.alc':app(['lib/math.alc'],['IO.puts(Integer.to_string(Util.twice(1)))']),'lib/math.alc':MATH,'lib/util.alc':UTIL},'transitive import'),
    ({'app.alc':app([],['IO.puts(Integer.to_string(Math.double(1)))'])},'module not imported'),
    ({'app.alc':app(['util.alc'],['IO.puts(Integer.to_string(Util.twice(1, 2)))']),'util.alc':UTIL},'wrong arity'),
    ({'app.alc':app(['util.alc'],['IO.puts(Util.twice(1))']),'util.alc':UTIL},'wrong type'),
    ({'app.alc':app(['lib/math.alc'],['IO.puts(Integer.to_string(Enum.sum(Enum.map([1], &Math.secret/1))))']),'lib/math.alc':MATH,'lib/util.alc':UTIL},'reference to a private function'),
    ({'app.alc':app(['lib/math.alc'],['IO.puts(Integer.to_string(Enum.sum(Enum.map([1], &Util.twice/1))))']),'lib/math.alc':MATH,'lib/util.alc':UTIL},'reference through a transitive import'),
    ({'app.alc':app(['util.alc'],['IO.puts(Integer.to_string(Enum.sum(Enum.map([1], &Util.twice/2))))']),'util.alc':UTIL},'reference with the wrong arity'),
]
# Bundler errors, as the pinned compiler reports them before compiling.
UNBUNDLED=[
    ({'app.alc':app(['nope.alc'],['IO.puts("x")'])},'No such file'),
    ({'app.alc':app(['lib/cyc.alc'],['IO.puts("x")']),'lib/cyc.alc':'defmodule Cyc do\n  import "../app.alc"\n\n  def f(n: integer): integer do\n    n\n  end\nend\n'},'import cycle'),
    ({'app.alc':app(['util.alc','other.alc'],['IO.puts("x")']),'util.alc':UTIL,'other.alc':UTIL},'duplicate module Util'),
    ({'app.alc':app(['tool.alc'],['IO.puts("x")']),'tool.alc':'defmodule Tool do\n  def main() do\n    System.halt(1)\n  end\nend\n'},'imported modules cannot define main'),
    # The pinned compiler reads no file over 1 MiB, imported or the entry.
    ({'app.alc':app(['big.alc'],['IO.puts("x")']),'big.alc':padded(UTIL,1048577)},'read source: source exceeds 1048576 bytes'),
    ({'app.alc':padded(app([],['IO.puts("x")']),1048577)},'read source: source exceeds 1048576 bytes'),
]
ONE='defmodule Util do def twice(n: integer): integer do n * 2 end end'
# Raw bundle text the compiler must reject.
INVALID=[
    'defmodule App do def main() do System.halt(1) end end '+ONE+' '+ONE,
    'defmodule App do def main() do System.halt(1) end end defmodule B do def main() do System.halt(2) end end',
    ONE,
    'defmodule App do\nimport "util.alc"\n def main() do System.halt(1) end end',
    'defmodule App do def main() do System.halt(1) end\nimport "module:Util"\n end '+ONE,
    'defmodule App do def main() do System.halt(1) end end defmodule String do def f(n: integer): integer do n end end',
    'defmodule App do def main() do System.halt(1) end end defmodule DiskStore do def f(n: integer): integer do n end end',
    'defmodule Path do def main() do System.halt(1) end end',
    'defmodule App do def main() do System.halt(1) end end junk',
    'defmodule App do def main() do System.halt(App.main()) end end',
    'defmodule App do\nimport "module:Nope"\n def main() do System.halt(Nope.f(1)) end end',
    'defmodule App do\nimport "module:Util"\n def main() do System.halt(Util.twice) end end '+ONE,
    'defmodule App do\nimport "module:"\n def main() do System.halt(1) end end',
]


# What tools/alchem-bundle.alc reports on standard error for each UNBUNDLED project.
NATIVE_ERRORS=['no such file or directory','import cycle','duplicate module Util','imported modules cannot define main','big.alc: read source: source exceeds 1048576 bytes','app.alc: read source: source exceeds 1048576 bytes']


def native_bundler(compiler,base):
    """tools/alchem-bundle.alc built by the compiler under test: the same bundles
    as the Python bundler for every project and path spelling, and its errors."""
    built=subprocess.run([str(compiler)],input=(ROOT/'tools/alchem-bundle.alc').read_bytes(),capture_output=True,env={'PATH':''},timeout=120)
    assert (built.returncode,built.stderr)==(0,b''),('bundler build',built.returncode,built.stderr)
    tool=base/'alchem-bundle';tool.write_bytes(built.stdout);tool.chmod(0o700)
    bundles=0
    for index,(files,_) in enumerate(PROJECTS+REJECTED):
        entry=write(base/f'native{index}',files)
        want=bundler.bundle(entry)
        for argument,cwd in [(str(entry),None),(entry.name,entry.parent),('./'+entry.name,entry.parent),('../'+entry.parent.name+'/'+entry.name,entry.parent)]:
            done=subprocess.run([str(tool),argument],capture_output=True,cwd=cwd,env={'PATH':''},timeout=120)
            assert (done.returncode,done.stdout,done.stderr)==(0,want,b''),('native bundle',index,argument,done.returncode,done.stderr)
            bundles+=1
    for index,((files,_),message) in enumerate(zip(UNBUNDLED,NATIVE_ERRORS)):
        done=subprocess.run([str(tool),str(write(base/f'nativebad{index}',files))],capture_output=True,env={'PATH':''},timeout=120)
        assert (done.returncode,done.stdout)==(1,b'') and done.stderr.startswith(b'E_BUNDLE: ') and message.encode() in done.stderr,('native bundler error',message,done)
    for arguments in [[],['a.alc','b.alc'],['--locked']]:
        done=subprocess.run([str(tool)]+arguments,capture_output=True,env={'PATH':''},timeout=120)
        assert (done.returncode,done.stdout,done.stderr)==(2,b'',b'Usage: alchem-bundle [--locked] ENTRY.alc\n'),('native bundler usage',done)
    # Header forms: a name containing "do", a one-line module, a comment before the header, CRLF lines.
    odd={'app.alc':'# defmodule lower do\r\ndefmodule Window do\r\n  import "domino.alc"\r\n  def main() do\r\n    System.halt(Domino.double(21))\r\n  end\r\nend\r\n',
         'domino.alc':'defmodule Domino do def double(n: integer): integer do n * 2 end end'}
    entry=write(base/'nativeodd',odd)
    done=subprocess.run([str(tool),str(entry)],capture_output=True,env={'PATH':''},timeout=120)
    assert (done.returncode,done.stdout,done.stderr)==(0,bundler.bundle(entry),b''),('native bundle header forms',done)
    return tool,bundles+1


def write(root,files):
    for name,text in files.items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    return root/next(iter(files))


def verify(compiler):
    with tempfile.TemporaryDirectory(prefix='alchem-modules-') as d:
        base=Path(d)
        def compiled(source):
            return subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
        def run(source,label):
            result=compiled(source)
            assert (result.returncode,result.stderr)==(0,b''),(label,result.returncode,result.stderr)
            assert compiled(source).stdout==result.stdout,(label,'determinism')
            out=base/'out';out.write_bytes(result.stdout);out.chmod(0o700)
            return subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=120)
        tool,bundles=native_bundler(compiler,base)
        for index,(files,stdout) in enumerate(PROJECTS):
            entry=write(base/f'project{index}',files)
            done=run(bundler.bundle(entry),('project',index))
            assert (done.returncode,done.stdout,done.stderr)==(0,stdout,b''),('project',index,done)
            # The same project with no Python between source files and executable.
            done=run(subprocess.run([str(tool),str(entry)],capture_output=True,env={'PATH':''},timeout=120).stdout,('native project',index))
            assert (done.returncode,done.stdout,done.stderr)==(0,stdout,b''),('native project',index,done)
        for index,(files,label) in enumerate(REJECTED):
            result=compiled(bundler.bundle(write(base/f'rejected{index}',files)))
            assert (result.returncode,result.stdout)==(65,b''),(label,result.returncode)
        for index,(files,message) in enumerate(UNBUNDLED):
            try:bundler.bundle(write(base/f'unbundled{index}',files))
            except bundler.BundleError as error:assert message in str(error),(message,str(error))
            else:raise AssertionError(('bundler accepted',message))
        for source in INVALID:
            result=compiled(source.encode())
            assert (result.returncode,result.stdout)==(65,b''),(source[:90],result.returncode)
        # An unused import of an absent module is harmless; same names coexist.
        done=run(('defmodule App do\nimport "module:Nope"\nimport "module:Util"\n def twice(n: integer): integer do n end def main() do System.halt(twice(1)+Util.twice(20)+1) end end '+ONE).encode(),'names')
        assert done.returncode==42,('same names in two modules',done.returncode)
        # 200 modules in a chain: each imports and calls the next, one frame per module.
        chain=['defmodule App do\nimport "module:M0"\n def main() do System.halt(M0.next(0)-157) end end\n']
        for i in range(200):
            last=i==199
            imports='' if last else f'import "module:M{i+1}"\n'
            following='n' if last else f'M{i+1}.next(n+1)'
            chain.append(f'defmodule M{i} do\n{imports} def next(n: integer): integer do {following} end defp unused(n: integer): integer do n end end\n')
        done=run(''.join(chain).encode(),'chain')
        assert done.returncode==42,('200-module chain',done.returncode)
        wide=''.join(f'defmodule W{i} do def f(n: integer): integer do n+{i} end end\n' for i in range(300))
        imports=''.join(f'import "module:W{i}"\n' for i in range(0,300,37))
        calls='+'.join(f'W{i}.f(0)' for i in range(0,300,37))
        done=run((f'defmodule App do\n{imports} def main() do System.halt({calls}-{sum(range(0,300,37))}+42) end end\n'+wide).encode(),'wide')
        assert done.returncode==42,('300 modules',done.returncode)
        # Five files of about a megabyte each: no file is over the 1 MiB a file may
        # have, and the program is over the 4 MiB positions once held. The pinned
        # compiler runs it (168427).
        n=0;big={}
        for m in range(5):
            lines=[f'defmodule M{m} do']
            while sum(len(l)+1 for l in lines)<1_000_000:
                body=''.join(f'    y{k} = x + {k} * {n}\n' for k in range(12))
                lines.append(f'  def f{n}(x: integer): integer do\n{body}    y0 + y11\n  end');n+=1
            lines.append('end');big[f'm{m}.alc']='\n'.join(lines)+'\n'
        imports=''.join(f'  import "m{m}.alc"\n' for m in range(5))
        big={'main.alc':'defmodule Main do\n'+imports+f'  def main() do IO.puts(Integer.to_string(M4.f{n-1}(1) + M0.f0(2))) end\nend\n',**big}
        source=bundler.bundle(write(base/'five',big))
        assert len(source)>5_000_000,len(source)
        done=run(source,'five megabytes')
        assert (done.returncode,done.stdout,done.stderr)==(0,b'168427\n',b''),('five files of a megabyte',done)
        # A table holds 65536 records and a module's header is one: 64 modules
        # of 1023 functions fill it, and one function more is rejected.
        def spread(extra):
            parts=[];each=(FUNCTION_LIMIT+1)//64-1
            for m in range(64):
                count=each if m else each-1+extra
                functions=''.join(f'def f{i}(n: integer): integer do n+1 end ' for i in range(count))
                if m==0:parts.append('defmodule App do\nimport "module:P63"\n '+functions+f'def main() do System.halt(P63.f{each-1}(f0(40))) end end\n')
                else:parts.append(f'defmodule P{m} do '+functions+'end\n')
            return ''.join(parts).encode()
        result=at_limit([str(compiler)],input=spread(0),capture_output=True,env={'PATH':''},timeout=600)
        assert (result.returncode,result.stderr)==(0,b''),('spread',result.returncode,result.stderr)
        out=base/'out';out.write_bytes(result.stdout);out.chmod(0o700)
        done=subprocess.run([str(out)],capture_output=True,env={'PATH':''},timeout=10)
        assert done.returncode==42,('65472 functions in 64 modules',done.returncode)
        result=at_limit([str(compiler)],input=spread(1),capture_output=True,env={'PATH':''},timeout=600)
        assert (result.returncode,result.stdout)==(65,b''),('65473 functions in 64 modules',result.returncode)
    print(f'PASS modules: {len(PROJECTS)} bundled projects, {bundles} bundles by the Alchem-written bundler identical to the Python one and its {len(NATIVE_ERRORS)} errors, {len(REJECTED)} visibility rejections, {len(UNBUNDLED)} bundler errors, {len(INVALID)} invalid bundles, 300-module programs, a 5 MB program of five 1 MB files, 65472/65473 functions across 64 modules (65536/65537 table records)')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
