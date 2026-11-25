#!/usr/bin/env python3
"""Fast incremental check: one fixpoint compiler, stage gates run in parallel.

A0 is the released compiler pinned-compiler.json names (downloaded once and
checked against its sum; scripts/pinned-compiler.py), which builds A1 from
the current source, and A1 builds A2: A1==A2 is required. Neither Go nor
Rust is needed for that. With --seed, A0 is instead the seed the Go frontend
and the Rust backend make of the source, and the gates that take those two
run as well. Every self-hosted stage gate then runs once against A2 instead of once
per A1/A2/A3. This is an iteration aid, not a substitute for the full suite:
it skips the second seed backend, Go/Rust backend comparison, legacy component
gates, publication preservation and core tools. Run `mise run verify` before
committing.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/dev'
# Module name -> call. Stage gates take one compiler; the two older gates
# take frontend/backends plus saved compilers.
GATES={
    'alchem_compiler':'verify(frontend,[backend]*2,[compiler]*2)',
    'alchem_byte_compiler':'verify(frontend,[backend]*2,[compiler]*2)',
    'enum_library':'verify(compiler)',
    'string_library':'verify(compiler)',
    'boolean_library':'verify(compiler)',
    'options':'verify(compiler)',
    'structural_types':'verify(compiler)',
    'general_collections':'verify(compiler)',
    'maps':'verify(compiler)',
    'library_expansion':'verify(compiler)',
    'integer_parse':'verify(compiler)',
    'io_input':'verify(compiler)',
    'system_env':'verify(compiler)',
    'effect_helpers':'verify(compiler)',
    'file_read':'verify(compiler)',
    'string_ops':'verify(compiler)',
    'string_case':'verify(compiler)',
    'string_graphemes':'verify(compiler)',
    'modules':'verify(compiler)',
    'closures':'verify(compiler)',
    'pipes':'verify(compiler)',
    'records':'verify(compiler)',
    'equality':'verify(compiler)',
    'patterns':'verify(compiler)',
    'generics':'verify(compiler)',
    'inference':'verify(compiler)',
    'long_bodies':'verify(compiler)',
    'statements':'verify(compiler)',
    'traces':'verify(compiler)',
    'packages':'verify(compiler)',
    'fetch':'verify(compiler)',
    'literals':'verify(compiler)',
    'wide':'verify(compiler)',
    'operators':'verify(compiler)',
    'inspection':'verify(compiler)',
    'library':'verify(compiler)',
    'forms':'verify(compiler)',
    'atoms':'verify(compiler)',
    'speed':'verify(compiler)',
    'failures':'verify(compiler)',
    'tail_calls':'verify(compiler)',
    'memory_reclaim':'verify(compiler)',
    'lists':'verify(compiler)',
    'ordering':'verify(compiler)',
    'processes':'verify(compiler)',
    'network':'verify(compiler)',
    'diskstore':'verify(compiler)',
    'sets':'verify(compiler)',
    'streams':'verify(compiler)',
    'exceptions':'verify(compiler)',
    'system':'verify(compiler)',
    'ranges':'verify(compiler)',
    'sigils':'verify(compiler)',
    'regex':'verify(compiler)',
    'macros':'verify(compiler)',
    'protocols':'verify(compiler)',
    'templates':'verify(compiler)',
    'parsing':'verify(compiler)',
    'crypto':'verify(compiler)',
    'json_library':'verify(compiler)',
    'time_zones':'verify(compiler)',
    'logger':'verify(compiler)',
    'gen':'verify(compiler)',
    'nodes':'verify(compiler)',
    'tls':'verify(compiler)',
    'gaps':'verify(compiler)',
    'described':'verify(compiler)',
    'nil_forms':'verify(compiler)',
    'test_driver':'verify(compiler)',
    'commands':'verify(compiler)',
    'lsp':'verify(compiler)',
    'replaced':'verify(compiler)',
    'binary':'verify(compiler)',
    'facts':'verify(compiler)',
    'front_end':'verify(compiler)',
    'testing':'verify(compiler)',
    'clauses':'verify(compiler)',
    'comprehensions':'verify(compiler)',
    'floats':'verify(compiler)',
    'collection_memory':'verify(compiler)',
    'type_words':'verify(compiler)',
    'source_capacity':'verify(compiler)',
    'grown_compiler':'verify(frontend,backend,compiler)',
    'graphemes':'verify(compiler)',
    'arm64':'verify(compiler)',
    'x86_to_arm64':'verify(150, compiler=compiler)',
    'arm64_floats':'verify(compiler)',
}


def step(label,command,**options):
    started=time.monotonic()
    result=subprocess.run(command,capture_output=True,**options)
    if result.returncode!=0:
        sys.stderr.write(result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        sys.exit(f'FAIL {label}')
    print(f'{time.monotonic()-started:6.2f}s {label}',flush=True)
    return result


def load(name):
    spec=importlib.util.spec_from_file_location(name.replace('-','_'),ROOT/'scripts'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def build(from_source=False):
    """A0, then A1 and A2 from the current source. A0 is the pinned release
    of the compiler (pinned-compiler.json); with from_source it is the seed
    the Go frontend and the Rust backend make of the source, as it was
    before there was a release to start from."""
    WORK.mkdir(parents=True,exist_ok=True)
    source=load('bootstrap-alchem-compiler').source_text('functions').encode()
    (WORK/'compiler-source.alc').write_bytes(source)
    seed=WORK/'A0'
    frontend=backend=None
    if from_source:
        env=dict(os.environ,GOTOOLCHAIN='local',GOPROXY='off',GOSUMDB='off',GOWORK='off')
        frontend=WORK/'alchem-source-probe'
        target=Path(env.setdefault('CARGO_TARGET_DIR',str(ROOT/'implementations/rust/target')))
        backend=target/'debug/alchem-native-rust'
        step('frontend (go build)',['go','build','-mod=readonly','-trimpath','-o',str(frontend),'.'],cwd=ROOT/'adapters/alchem',env=env)
        step('backend (cargo build)',['cargo','build','--locked','--offline','--quiet','--manifest-path',str(ROOT/'implementations/rust/Cargo.toml'),'--bin','alchem-native-rust'],env=env)
        step('A0 (seed)',[sys.executable,str(ROOT/'scripts/bootstrap-alchem-compiler.py'),'--language','functions','--frontend',str(frontend),'--backend',str(backend),'--output',str(seed)])
    else:
        started=time.monotonic()
        try:pinned=load('pinned-compiler').fetch('linux-x86_64')
        except (OSError,ValueError,RuntimeError,KeyError) as error:sys.exit(f'FAIL A0 (pinned release): {error}')
        seed.unlink(missing_ok=True);seed.write_bytes(pinned.read_bytes());seed.chmod(0o700)
        print(f'{time.monotonic()-started:6.2f}s A0 (pinned release, {pinned.parent.name})',flush=True)
    previous=seed
    for stage in (1,2):
        image=WORK/f'A{stage}'
        result=step(f'A{stage} (self-build, empty PATH)',[str(previous)],input=source,env={'PATH':''},timeout=120)
        if result.stderr:sys.exit(f'FAIL A{stage}: unexpected stderr {result.stderr!r}')
        image.write_bytes(result.stdout);image.chmod(0o700);previous=image
    if (WORK/'A1').read_bytes()!=(WORK/'A2').read_bytes():sys.exit('FAIL A1/A2 fixpoint mismatch')
    print(f'A1==A2: {len(source):,} source bytes -> {(WORK/"A2").stat().st_size:,} compiler bytes',flush=True)
    return frontend,backend,WORK/'A2'


def run_gate(name,frontend,backend,compiler):
    code=(f'import sys;from pathlib import Path;sys.path.insert(0,{str(ROOT/"harness")!r});import {name} as m;'
          f'frontend,backend,compiler=Path({str(frontend)!r}),Path({str(backend)!r}),Path({str(compiler)!r});m.{GATES[name]}')
    started=time.monotonic()
    result=subprocess.run([sys.executable,'-c',code],capture_output=True,cwd=ROOT/'harness')
    output=result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace')
    return name,result.returncode,time.monotonic()-started,output


def limited():
    """Re-run under scripts/limited: the gates run side by side and a compile may reserve 16 GiB."""
    if os.environ.get('ALCHEM_VERIFY_LIMITED')=='1':return
    env=dict(os.environ,ALCHEM_VERIFY_LIMITED='1',ALCHEM_MEMORY=os.environ.get('ALCHEM_VERIFY_MEMORY','24G'),ALCHEM_SECONDS=os.environ.get('ALCHEM_VERIFY_SECONDS','1800'))
    os.execve(str(ROOT/'scripts/limited'),[str(ROOT/'scripts/limited'),sys.executable]+sys.argv,env)


def main():
    limited()
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('gates',nargs='*',help='substring filters on gate names (default: all)')
    parser.add_argument('--list',action='store_true',help='list gate names and exit')
    parser.add_argument('--jobs',type=int,default=os.cpu_count(),help='parallel gates (default: CPU count)')
    parser.add_argument('--build-only',action='store_true',help='stop after the A1==A2 fixpoint')
    parser.add_argument('--seed',action='store_true',help='start from the seed the Go frontend and the Rust backend make, not from the pinned release; the gates that take the two run only so')
    args=parser.parse_args()
    if args.list:print('\n'.join(GATES));return
    # The seed and the compiler are x86-64 executables. An ARM64 host runs
    # them through binfmt_misc and QEMU (qemu-user-static), and the ARM64
    # gates' programs directly.
    x86=os.uname().machine=='x86_64' or Path('/proc/sys/fs/binfmt_misc/qemu-x86_64').exists()
    if sys.platform!='linux' or not x86:sys.exit('Requires Linux x86-64, or ARM64 with qemu-user-static; use mise run linux:quick')
    selected=[name for name in GATES if not args.gates or any(f in name for f in args.gates)]
    # The gates that compare with the seed's frontend and backend need them.
    seeded=[name for name in selected if 'frontend' in GATES[name] or 'backend' in GATES[name]]
    if not args.seed:
        selected=[name for name in selected if name not in seeded]
        if seeded:print(f'not run without --seed (they take the Go frontend and the Rust backend): {", ".join(seeded)}',flush=True)
    if not selected and not args.build_only:sys.exit(f'No gate matches {args.gates}; see --list')
    started=time.monotonic()
    frontend,backend,compiler=build(args.seed)
    if args.build_only:return
    failed=[];skipped=[]
    with ThreadPoolExecutor(max_workers=max(1,args.jobs)) as pool:
        futures=[pool.submit(run_gate,name,frontend,backend,compiler) for name in selected]
        for future in as_completed(futures):
            name,status,elapsed,output=future.result()
            if status!=0:failed.append(name);print(f'{elapsed:6.2f}s FAIL {name}\n{output}',flush=True)
            elif 'SKIP' in output:skipped.append(name);print(f'{elapsed:6.2f}s SKIP {name}\n'+'\n'.join(l for l in output.splitlines() if 'SKIP' in l),flush=True)
            else:print(f'{elapsed:6.2f}s pass {name}',flush=True)
    total=time.monotonic()-started
    if failed or skipped:sys.exit(f'Quick check FAILED in {total:.1f}s: failed {failed} skipped {skipped} (skips are not passes)')
    print(f'Quick check passed: {len(selected)} gates on A2 in {total:.1f}s (not a full verification; run mise run verify before committing)')


if __name__=='__main__':main()
