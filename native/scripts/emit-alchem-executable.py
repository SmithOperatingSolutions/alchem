#!/usr/bin/env python3
"""Bootstrap an Alchem ELF emitter and save its bytes without a host ELF writer."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
COMPONENT=ROOT/'implementations/alchem/encoder.alc'


def checked(command,stage):
    result=subprocess.run(command,capture_output=True,timeout=30)
    if result.returncode:
        raise RuntimeError(f'{stage} exited {result.returncode}: {result.stderr.decode("utf-8",errors="replace").strip()}')
    return result.stdout


def emit(status,output,frontend,compiler,save_emitter=None):
    if not -(1<<63)<=status<(1<<63):raise ValueError('status must fit i64')
    protected=[COMPONENT,Path(__file__),frontend,compiler]
    targets=[output]+([save_emitter] if save_emitter is not None else [])
    if any(target.resolve()==path.resolve() for target in targets for path in protected):raise ValueError('output must not overwrite source or bootstrap tools')
    if save_emitter is not None and output.resolve()==save_emitter.resolve():raise ValueError('image and emitter paths must differ')
    component=COMPONENT.read_text();prefix=component.split('  # Native smoke test;',1)[0]
    source=prefix+f'  def main() do image=emit_elf_exit({status})\n System.halt(Enum.count(image)-140) end\nend\n'
    with tempfile.TemporaryDirectory(prefix='alchem-elf-emitter-') as directory:
        root=Path(directory);path=root/'emitter.alc';path.write_text(source)
        ir=json.loads(checked([str(frontend),'--input',str(path),'--program'],'frontend'))
        main=next(f for f in ir['functions'] if f['name']=='main')
        instructions=main['blocks'][0]['instructions']
        result=next(i['dest'] for i in instructions if i.get('callee')=='fn.emit_elf_exit')
        # A temporary observation bridge until source binary IO is supported.
        # Header, padding and code bytes are all constructed by Alchem itself.
        instructions.append({'op':'bytes.write','dest':'exported_image','value':result,'stream':'stdout'})
        ir_path=root/'emitter.json';ir_path.write_text(json.dumps(ir))
        executable=root/'emitter'
        checked([str(compiler),'--target','x86_64-unknown-linux-gnu','--input',str(ir_path),'--output',str(executable)],'bootstrap backend')
        image=checked([str(executable)],'Alchem emitter')
        emitter=executable.read_bytes()
        if len(image)!=140 or image[:4]!=b'\x7fELF':raise RuntimeError('Alchem emitter returned an invalid image')
    atomic_save(output,image)
    if save_emitter is not None:atomic_save(save_emitter,emitter)
    return len(image)


def atomic_save(output,data):
    temporary=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.alchem-image-',dir=output.parent,delete=False) as file:
            temporary=Path(file.name)
            file.write(data)
            os.fchmod(file.fileno(),0o700)
        os.replace(temporary,output)
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status',type=int,default=42)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--save-emitter',type=Path,help='retain the Alchem emitter executable for standalone reuse')
    parser.add_argument('--frontend',type=Path,default=ROOT/'build/native/alchem-source-probe')
    parser.add_argument('--compiler',type=Path,default=ROOT/'build/native/alchem-native')
    args=parser.parse_args()
    try:
        size=emit(args.status,args.output,args.frontend.resolve(),args.compiler.resolve(),args.save_emitter)
    except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired,StopIteration,KeyError) as error:
        print(f'E_EMIT: {error}',file=sys.stderr)
        return 1
    print(f'Wrote {size} Alchem-generated ELF bytes to {args.output}')
    return 0


if __name__=='__main__':raise SystemExit(main())
