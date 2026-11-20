#!/usr/bin/env python3
"""Bootstrap an Alchem-written arithmetic or integer/function compiler once."""
import argparse
from collections import Counter
import itertools
import string
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
from importlib.util import spec_from_file_location, module_from_spec

ROOT=Path(__file__).resolve().parents[1]
COMPONENTS=[ROOT/'implementations/alchem'/name for name in ('lexer.alc','encoder.alc','compiler.alc')]
TARGET='x86_64-unknown-linux-gnu'
DIAGNOSTIC=b'E_COMPILE: invalid expression or result outside 0..255\n'


def checked(command,stage):
    result=subprocess.run(command,capture_output=True,timeout=60)
    if result.returncode:raise RuntimeError(f'{stage}: {result.stderr.decode(errors="replace").strip()}')
    return result.stdout


def compact_source(text):
    # Preserve quoted bytes and token/newline boundaries; no semantic rewriting.
    output=[];quoted=False;escaped=False;comment=False;pending=''
    for char in text:
        if comment:
            if char in '\r\n':comment=False;pending+='\n'
        elif quoted:
            output.append(char)
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
        elif char=='#':comment=True
        elif char in ' \t\r\n':pending+=char
        else:
            if output and pending:output.append('\n' if '\n' in pending or '\r' in pending else ' ')
            pending='';output.append(char)
            if char=='"':quoted=True
    return ''.join(output)+('' if quoted or not output or output[-1]=='\n' else '\n')


def compact_identifiers(text):
    # Simultaneous injective alpha-renaming, only for the assembled distribution.
    token=re.compile(r'"(?:\\.|[^"\\])*"|[A-Za-z_][A-Za-z_0-9]*')
    words=Counter(m[0] for m in token.finditer(text) if not m[0].startswith('"'))
    reserved=set('bytes b defmodule def defp do end if else case integer list string boolean option some none true false not and or main native_compile nc_compile fn in as is on of when with for receive after rescue try catch raise throw use alias import require quote unquote cond unless struct enum protocol impl extern type return void float atom map tuple stream result ok error nil module super self while reduce async await spawn send'.split())
    reserved.update(re.findall(r'\.([A-Za-z_][A-Za-z_0-9]*)',text))
    reserved.update(word for word in words if word[0].isupper())
    names=sorted(set(words)-reserved,key=lambda word:(-words[word],word))
    aliases=(''.join(parts) for size in range(1,5) for parts in itertools.product(string.ascii_lowercase,repeat=size) if ''.join(parts) not in reserved)
    mapping={word:next(aliases) for word in names}
    return token.sub(lambda match:mapping.get(match[0],match[0]),text)


def source_text(language="arithmetic",compact=True):
    # Local component assembly only: discard module envelopes and smoke mains.
    # Parsing, validation, evaluation and ELF writing remain in the Alchem bodies.
    bodies=[]
    components=COMPONENTS if language=="arithmetic" else COMPONENTS[:1]+[ROOT/"implementations/alchem/native-compiler.alc",ROOT/"implementations/alchem/native-runtime.alc",ROOT/"implementations/alchem/native-memory.alc",ROOT/"implementations/alchem/native-memory-data.alc",ROOT/"implementations/alchem/native-strings.alc",ROOT/"implementations/alchem/native-booleans.alc",ROOT/"implementations/alchem/native-graphemes.alc",ROOT/"implementations/alchem/native-grapheme-data.alc",ROOT/"implementations/alchem/native-options.alc",ROOT/"implementations/alchem/native-types.alc",ROOT/"implementations/alchem/native-structures.alc",ROOT/"implementations/alchem/native-records.alc",ROOT/"implementations/alchem/native-equality.alc",ROOT/"implementations/alchem/native-ordering.alc",ROOT/"implementations/alchem/native-sort-data.alc",ROOT/"implementations/alchem/native-patterns.alc",ROOT/"implementations/alchem/native-clauses.alc",ROOT/"implementations/alchem/native-generics.alc",ROOT/"implementations/alchem/native-blocks.alc",ROOT/"implementations/alchem/native-operators.alc",ROOT/"implementations/alchem/native-floats.alc",ROOT/"implementations/alchem/native-float-data.alc",ROOT/"implementations/alchem/native-crypto-data.alc",ROOT/"implementations/alchem/native-tls-data.alc",ROOT/"implementations/alchem/native-json.alc",ROOT/"implementations/alchem/native-testing.alc",ROOT/"implementations/alchem/native-comprehensions.alc",ROOT/"implementations/alchem/native-sigils.alc",ROOT/"implementations/alchem/native-macros.alc",ROOT/"implementations/alchem/native-protocols.alc",ROOT/"implementations/alchem/native-templates.alc",ROOT/"implementations/alchem/native-regex.alc",ROOT/"implementations/alchem/native-regex-data.alc",ROOT/"implementations/alchem/native-sets.alc",ROOT/"implementations/alchem/native-processes.alc",ROOT/"implementations/alchem/native-network.alc",ROOT/"implementations/alchem/native-system.alc",ROOT/"implementations/alchem/native-try.alc",ROOT/"implementations/alchem/native-failures.alc",ROOT/"implementations/alchem/native-described.alc",ROOT/"implementations/alchem/native-tail.alc",ROOT/"implementations/alchem/native-inspect.alc",ROOT/"implementations/alchem/native-prelude.alc",ROOT/"implementations/alchem/native-prelude-data.alc",ROOT/"implementations/alchem/native-trace.alc",ROOT/"implementations/alchem/native-trace-data.alc",ROOT/"implementations/alchem/native-collections.alc",ROOT/"implementations/alchem/native-collection-data.alc",ROOT/"implementations/alchem/native-maps.alc",ROOT/"implementations/alchem/native-library.alc",ROOT/"implementations/alchem/native-library-data.alc",ROOT/"implementations/alchem/native-parse-data.alc",ROOT/"implementations/alchem/native-file-data.alc",ROOT/"implementations/alchem/native-case-data.alc",ROOT/"implementations/alchem/native-functions.alc",ROOT/"implementations/alchem/native-nodes.alc",ROOT/"implementations/alchem/native-enumerable.alc",ROOT/"implementations/alchem/native-enumerable-data.alc",ROOT/"implementations/alchem/native-needs.alc",ROOT/"implementations/alchem/native-speed.alc",ROOT/"implementations/alchem/native-arms.alc",ROOT/"implementations/alchem/native-scope.alc",ROOT/"implementations/alchem/native-arm64.alc",ROOT/"implementations/alchem/native-macho.alc",ROOT/"implementations/alchem/native-memory-data-arm64.alc",ROOT/"implementations/alchem/native-memory-data-darwin.alc",ROOT/"implementations/alchem/native-x86arm.alc",ROOT/"implementations/alchem/native-runtimes-arm64.alc",ROOT/"implementations/alchem/native-marked-data.alc"]
    for component in components:
        text=component.read_text()
        prefix,marker,_=text.partition('  # Native smoke test;')
        if not marker or not prefix.startswith('defmodule '):raise ValueError(f'invalid component envelope: {component}')
        body=prefix.split('\n',1)[1]
        if language!='arithmetic' and component.name=='lexer.alc':
            core={'is_digit','is_letter','is_space','punctuation','classify_ascii','byte_at','is_identifier_continue','decimal_status','decimal_digits'}
            starts=list(re.finditer(r'^  def (\w+)\(',body,re.M));selected=[];found=set()
            for i,match in enumerate(starts):
                if match.group(1) in core:
                    found.add(match.group(1));selected.append(body[match.start():starts[i+1].start() if i+1<len(starts) else len(body)])
            if found!=core:raise ValueError('lexer core manifest mismatch')
            body=''.join(selected)
        bodies.append(body)
    module="NativeArithmeticCompiler" if language=="arithmetic" else "NativeSourceCompiler"
    entry='' if language=='arithmetic' else '  def native_compile(source: bytes): bytes do nc_compile(source) end\n'
    text=f'defmodule {module} do\n'+''.join(bodies)+entry+'  def main() do System.halt(0) end\nend\n'
    return compact_identifiers(compact_source(text)) if compact and language!='arithmetic' else text


def bridge(language="arithmetic"):
    entry="fn.compile_expression" if language=="arithmetic" else "fn.nc_compile"
    limit=128 if language=="arithmetic" else 16776191
    diagnostic=DIAGNOSTIC if language=="arithmetic" else b"E_COMPILE: invalid or unsupported Alchem function program\n"
    instructions=[
        {'op':'bytes.read','dest':'source','limit':limit},
        {'op':'call','dest':'image','callee':entry,'args':['source']},
        {'op':'bytes.len','dest':'length','value':'image'},
        {'op':'const.i64','dest':'zero','value':0},
        {'op':'eq.i64','dest':'rejected','lhs':'length','rhs':'zero'},
        {'op':'if.i64','dest':'status','cond':'rejected',
         'then':{'instructions':[
             {'op':'bytes.const','dest':'diagnostic','values':list(diagnostic)},
             {'op':'bytes.write','dest':'error_count','value':'diagnostic','stream':'stderr'},
             {'op':'const.i64','dest':'failure','value':65}], 'value':'failure'},
         'else':{'instructions':[
             {'op':'bytes.write','dest':'count','value':'image','stream':'stdout'}], 'value':'zero'}},
    ]
    return {'name':'main','params':[],'return_type':'i64','blocks':[{'label':'entry','instructions':instructions,'terminator':{'op':'ret','value':'status'}}]}


# The seed frontend is the pinned parser, which reads at most 1 MiB of source.
FRONTEND_LIMIT=1<<20
SIGNATURE=re.compile(r'def (\w+)\(([^)]*)\)(?:: (bytes|integer))? do')


def frontend_ir(text,frontend,limit=FRONTEND_LIMIT):
    """The seed IR of the compiler's source. A source past the pinned parser's
    limit is lowered in parts: each part is the whole module with the bodies of
    the functions outside it replaced by a constant of their type, so every
    call is still checked against the real signature, and each function's IR
    is taken from the part that holds its body. The result is the IR the
    whole source would give (harness/compiler_entry.py checks that)."""
    def lower(source):
        with tempfile.TemporaryDirectory(prefix='alchem-compiler-frontend-') as directory:
            path=Path(directory)/'compiler.alc';path.write_text(source)
            return json.loads(checked([str(frontend),'--input',str(path),'--program'],'frontend'))
    if len(text.encode())<=limit:
        try:return lower(text)
        except RuntimeError as error:
            # The frontend measures the source after its byte spelling is translated.
            if 'source exceeds' not in str(error):raise
    head,rest=text.split('\n',1)
    if not head.startswith('defmodule ') or not rest.endswith('end\n'):raise ValueError('compiler source is not one module')
    body=rest[:-4];starts=[m.start() for m in re.finditer(r'^def ',body,re.M)]
    if not starts or starts[0]!=0:raise ValueError('compiler source does not start with a function')
    parts=[body[a:b] for a,b in zip(starts,starts[1:]+[len(body)])]
    signatures=[SIGNATURE.match(part) for part in parts]
    if not all(signatures):raise ValueError('compiler function without a plain signature')
    names=[m.group(1) for m in signatures]
    if names[-1]!='main' or len(set(names))!=len(names) or any(m.group(3) is None for m in signatures[:-1]):raise ValueError('compiler source needs typed functions and a final main')
    # A stub that slices keeps every part in IR version 11, as the whole source is.
    stubs=[f'{m.group(0)} {"Enum.slice(b[],0,0)" if m.group(3)=="bytes" else "0"} end\n' for m in signatures[:-1]]+[parts[-1]]
    size=lambda value:len(value.encode())
    fixed=size(head)+1+sum(map(size,stubs))+4;groups=[];current=[];extra=0
    for index in range(len(parts)-1):
        grow=size(parts[index])-size(stubs[index])
        if fixed+grow>limit:raise ValueError('a compiler function does not fit the seed frontend beside the signatures of the others')
        if current and fixed+extra+grow>limit:groups.append(current);current=[];extra=0
        current.append(index);extra+=grow
    groups.append(current)
    lowered=[];pending=groups;groups=[]
    while pending:
        group=pending.pop(0);chosen=set(group)
        try:ir=lower(head+'\n'+''.join(parts[i] if i in chosen else stubs[i] for i in range(len(parts)))+'end\n')
        except RuntimeError as error:
            # The frontend measures the source after its byte spelling is translated.
            if 'source exceeds' not in str(error) or len(group)==1:raise
            pending[:0]=[group[:len(group)//2],group[len(group)//2:]];continue
        groups.append(group);lowered.append((ir,{f['name']:f for f in ir['functions']}))
    first,_=lowered[0];real={'main':lowered[0][1]['main']}
    for group,(ir,found) in zip(groups,lowered):
        if {key:value for key,value in ir.items() if key!='functions'}!={key:value for key,value in first.items() if key!='functions'} or [f['name'] for f in ir['functions']]!=[f['name'] for f in first['functions']]:raise ValueError('compiler source parts disagree')
        for index in group:real['fn.'+names[index]]=found['fn.'+names[index]]
    return dict(first,functions=[real[f['name']] for f in first['functions']])


def bootstrap(output,frontend,backend,language="arithmetic"):
    protected=list((ROOT/'implementations/alchem').glob('*.alc'))+[Path(__file__),ROOT/'scripts/emit-alchem-executable.py',frontend,backend]
    if any(output.resolve()==p.resolve() for p in protected):raise ValueError('output must not overwrite source or bootstrap tools')
    with tempfile.TemporaryDirectory(prefix='alchem-compiler-bootstrap-') as directory:
        root=Path(directory)
        ir=frontend_ir(source_text(language),frontend)
        target=next(f for f in ir['functions'] if f['name']==('fn.compile_expression' if language=='arithmetic' else 'fn.nc_compile'))
        if target['return_type']!='bytes' or target['params']!=[{'name':'p0','type':'bytes'}]:raise ValueError('compiler entry must take and return bytes')
        ir['version']=10 if language=='arithmetic' else 11
        if language!='arithmetic':ir['arena_bytes']=1<<34
        ir['functions']=[bridge(language) if f['name']=='main' else f for f in ir['functions']]
        path=root/'compiler.json';path.write_text(json.dumps(ir));executable=root/'compiler'
        checked([str(backend),'--target',TARGET,'--input',str(path),'--output',str(executable)],'backend')
        # Validate the bootstrapped executable before replacing an existing one.
        result=subprocess.run([str(executable)],input=(b'6*7' if language=='arithmetic' else b'defmodule M do def main() do System.halt(42) end end'),capture_output=True,timeout=10,env={'PATH':''})
        size_ok=len(result.stdout)==140 if language=='arithmetic' else len(result.stdout)>320
        if result.returncode!=0 or result.stderr or not size_ok or result.stdout[:4]!=b'\x7fELF':raise RuntimeError('compiler smoke test failed')
        spec=spec_from_file_location('alchem_export',ROOT/'scripts/emit-alchem-executable.py')
        exporter=module_from_spec(spec);spec.loader.exec_module(exporter)
        exporter.atomic_save(output,executable.read_bytes())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--language',choices=['arithmetic','functions'],default='arithmetic')
    parser.add_argument('--output',type=Path,default=None)
    parser.add_argument('--frontend',type=Path,default=ROOT/'build/native/alchem-source-probe')
    parser.add_argument('--backend',type=Path,default=ROOT/'build/native/alchem-native')
    args=parser.parse_args()
    output=args.output or ROOT/"build/native"/("alchem-arithmetic" if args.language=="arithmetic" else "alchem-compiler")
    try:bootstrap(output,args.frontend.resolve(),args.backend.resolve(),args.language)
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired,StopIteration,KeyError) as error:
        print(f'E_BOOTSTRAP: {error}',file=sys.stderr);return 1
    print(f'Built Alchem {args.language} compiler: {output}')
    return 0


if __name__=='__main__':raise SystemExit(main())
