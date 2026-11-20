#!/usr/bin/env python3
"""Publish an Alchem-built compiler only after reproducible A1/A2/A3 rebuilds."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def load_script(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def atomic_text(path,text):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.alchem-self-',dir=path.parent,delete=False,mode='w') as file:
            temporary=Path(file.name);file.write(text);os.fchmod(file.fileno(),0o600)
        os.replace(temporary,path)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def build(frontend,backend,output):
    bootstrap=load_script('alchem_bootstrap',ROOT/'scripts/bootstrap-alchem-compiler.py')
    exporter=load_script('alchem_export',ROOT/'scripts/emit-alchem-executable.py')
    output.mkdir(parents=True,exist_ok=True)
    source=bootstrap.source_text('functions').encode()
    with tempfile.TemporaryDirectory(prefix='.alchem-self-build-',dir=output) as directory:
        root=Path(directory);seed=root/'A0'
        bootstrap.bootstrap(seed,frontend,backend,'functions')
        previous=seed;stages=[]
        for stage in range(1,4):
            result=subprocess.run([str(previous)],input=source,capture_output=True,env={'PATH':''},timeout=120)
            if result.returncode or result.stderr:raise RuntimeError(f'A{stage} rebuild exited {result.returncode}: {result.stderr.decode(errors="replace")}')
            path=root/f'A{stage}';path.write_bytes(result.stdout);path.chmod(0o700)
            if result.stdout[:4]!=b'\x7fELF':raise RuntimeError('rebuild did not emit ELF')
            stages.append(result.stdout);previous=path
        if not stages[0]==stages[1]==stages[2]:raise RuntimeError('A1/A2/A3 bytes differ')
        fixture=(ROOT/'examples/alchem-byte-compiler-demo.alc').read_bytes()
        compiled=subprocess.run([str(previous)],input=fixture,capture_output=True,env={'PATH':''},timeout=30)
        if compiled.returncode or compiled.stderr:raise RuntimeError('self-built compiler smoke failed')
        target=root/'target';target.write_bytes(compiled.stdout);target.chmod(0o700)
        run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=10)
        if (run.returncode,run.stdout,run.stderr)!=(42,b'',b''):raise RuntimeError('self-built target smoke failed')
        digest=lambda data:hashlib.sha256(data).hexdigest()
        manifest={'schema_version':1,'source_bytes':len(source),'source_sha256':digest(source),'bootstrap_sha256':digest(seed.read_bytes()),'stage_sha256':[digest(data) for data in stages],'compiler_bytes':len(stages[2]),'compiler_sha256':digest(stages[2]),'compiler_arena_bytes':64<<20,'target':'x86_64-unknown-linux-gnu'}
        # Publish only after rebuild equality and executable smoke pass. Each file
        # is atomic; the four outputs are not a multi-file transaction.
        exporter.atomic_save(output/'alchem-compiler',stages[2])
        exporter.atomic_save(output/'alchem-compiler-bootstrap',seed.read_bytes())
        atomic_text(output/'compiler-source.alc',source.decode())
        atomic_text(output/'self-host.json',json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frontend',type=Path,default=ROOT/'build/native/alchem-source-probe')
    parser.add_argument('--backend',type=Path,default=ROOT/'build/native/alchem-native')
    parser.add_argument('--output-directory',type=Path,default=ROOT/'build/native')
    args=parser.parse_args()
    try:manifest=build(args.frontend.resolve(),args.backend.resolve(),args.output_directory.resolve())
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as error:
        print(f'E_SELF_HOST: {error}',file=sys.stderr);return 1
    print(f'Built self-hosted Alchem compiler ({manifest["compiler_bytes"]} bytes); A1/A2/A3 match')
    return 0


if __name__=='__main__':raise SystemExit(main())
