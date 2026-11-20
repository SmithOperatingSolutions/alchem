#!/usr/bin/env python3
"""Compile the compiler's remaining core modules with its self-built binary."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
COMPONENTS=ROOT/'implementations/alchem'


def load_script(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def body(name):
    path=(COMPONENTS/name).resolve()
    if not path.is_relative_to(COMPONENTS.resolve()):raise ValueError('component path escapes source root')
    text=path.read_text();prefix,marker,_=text.partition('  # Native smoke test;')
    if not marker or not prefix.startswith('defmodule '):raise ValueError(f'invalid component envelope: {name}')
    return prefix.split('\n',1)[1]


def source_text(module):
    services=body('core-services.alc');starts=list(re.finditer(r'^  def (\w+)\(',services,re.M));helpers=[];found=set()
    for i,match in enumerate(starts):
        if match.group(1) in module['helpers']:
            found.add(match.group(1));helpers.append(services[match.start():starts[i+1].start() if i+1<len(starts) else len(services)])
    if found!=set(module['helpers']):raise ValueError('core service helper manifest mismatch')
    return 'defmodule NativeCore do\n'+''.join(body(name) for name in module['sources'])+''.join(helpers)+f'  def native_compile(source: bytes): bytes do {module["entry"]}(source) end\n  def main() do System.halt(0) end\nend\n'


def build(compiler,output,arithmetic_output=None):
    manifest=json.loads((COMPONENTS/'core-modules.json').read_text())
    if manifest['schema_version']!=1:raise ValueError('unsupported core manifest')
    output.mkdir(parents=True,exist_ok=True)
    protected=[compiler,Path(__file__)]+list(COMPONENTS.glob('*'))
    targets=[output/m['artifact'] for m in manifest['modules']]+([arithmetic_output] if arithmetic_output is not None else [])
    if any(target.resolve()==p.resolve() for target in targets for p in protected):raise ValueError('output must not overwrite compiler/components')
    publisher=load_script('self_publish',ROOT/'scripts/build-self-hosted.py')
    exporter=load_script('core_export',ROOT/'scripts/emit-alchem-executable.py')
    with tempfile.TemporaryDirectory(prefix='.alchem-core-',dir=output) as directory:
        stage=Path(directory)
        def compile_module(module):
            text=source_text(module).encode()
            built=subprocess.run([str(compiler)],input=text,capture_output=True,env={'PATH':''},timeout=60)
            if built.returncode or built.stderr:raise RuntimeError(f'{module["name"]}: compiler exited {built.returncode}: {built.stderr.decode(errors="replace")}')
            binary=stage/module['artifact'];binary.write_bytes(built.stdout);binary.chmod(0o700)
            data=b'42' if module['name']=='integer' else b'6*7' if module['name'] in ('expression','arithmetic') else b'*' if module['name']=='encoder' else b''
            smoke=subprocess.run([str(binary)],input=data,capture_output=True,env={'PATH':''},timeout=10)
            if smoke.returncode or smoke.stderr:raise RuntimeError(f'{module["name"]}: module smoke failed')
            if module['name'] in ('encoder','arithmetic'):
                target=stage/(module['name']+'-target');target.write_bytes(smoke.stdout);target.chmod(0o700)
                run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=10)
                if (run.returncode,run.stdout,run.stderr)!=(42,b'',b''):raise RuntimeError('module-produced ELF smoke failed')
            elif smoke.stdout!=(b'\x09\0\0' if module['name']=='lexer' else b'42'):raise RuntimeError('module output smoke failed')
            return module,text,built.stdout
        with ThreadPoolExecutor(max_workers=4) as pool:compiled=list(pool.map(compile_module,manifest['modules']))
        digest=lambda data:hashlib.sha256(data).hexdigest()
        result={'schema_version':1,'compiler_sha256':digest(compiler.read_bytes()),'modules':[]}
        for module,text,data in compiled:
            exporter.atomic_save(output/module['artifact'],data)
            publisher.atomic_text(output/(module['name']+'.source.alc'),text.decode())
            result['modules'].append({'name':module['name'],'artifact':module['artifact'],'source_sha256':digest(text),'artifact_sha256':digest(data),'source_bytes':len(text),'artifact_bytes':len(data),'protocol':module['protocol']})
            if module['name']=='arithmetic' and arithmetic_output is not None:exporter.atomic_save(arithmetic_output,data)
        publisher.atomic_text(output/'manifest.json',json.dumps(result,indent=2,sort_keys=True)+'\n')
        return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,default=ROOT/'build/native/alchem-compiler')
    parser.add_argument('--output-directory',type=Path,default=ROOT/'build/native/core')
    parser.add_argument('--arithmetic-output',type=Path)
    args=parser.parse_args()
    try:result=build(args.compiler.resolve(),args.output_directory.resolve(),args.arithmetic_output)
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        print(f'E_CORE_BUILD: {error}',file=sys.stderr);return 1
    print(f'Built {len(result["modules"])} self-hosted core modules')
    return 0


if __name__=='__main__':raise SystemExit(main())
