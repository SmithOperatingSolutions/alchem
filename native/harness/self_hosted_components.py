"""Shared source rendering and independent native component verification."""
import os
from pathlib import Path
import subprocess
import tempfile


def product(values):
    if not values:return '1'
    if len(values)==1:return values[0]
    middle=len(values)//2
    return f'({product(values[:middle])} * {product(values[middle:])})'


def literal(values):
    if len(values)<=128:return 'b['+','.join(map(str,values))+']'
    middle=len(values)//2
    return f'Enum.concat({literal(values[:middle])},{literal(values[middle:])})'


def verify_program(source,compiler,root,label,status=0):
    result=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
    assert result.returncode==0 and not result.stderr,(label,'self-host compile',result.returncode,result.stderr)
    assert result.stdout[:4]==b'\x7fELF',(label,'not ELF')
    repeated=subprocess.run([str(compiler)],input=source.encode(),capture_output=True,env={'PATH':''},timeout=120)
    assert (repeated.returncode,repeated.stdout,repeated.stderr)==(0,result.stdout,b''),(label,'self-host determinism')
    output=Path(root)/'self-hosted-component';output.unlink(missing_ok=True);output.write_bytes(result.stdout);output.chmod(0o700)
    # Status 71 is an exhausted arena: the run is held to the arena's 4 MiB floor
    # (an unlimited run reserves 16 GiB lazily and would take that much first).
    from native_memory import floor_arena
    # Status 2 is a program stopped by the runtime: calls nested too deep, or
    # the reason given with the status as (2, reason).
    reason=b'call depth exceeded'
    if isinstance(status,tuple):status,reason=status
    run=subprocess.run([str(output)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(output) if status==71 else None)
    stopped=run.stderr.split(b'\n')[0].endswith(b': '+reason) if status==2 else run.stderr==b''
    assert (run.returncode,run.stdout)==(status,b'') and stopped,(label,'self-host execution',run.returncode,run.stderr[:200])


def _one(item):
    source,compiler,label,status=item
    with tempfile.TemporaryDirectory(prefix='alchem-many-') as directory:
        try:verify_program(source,compiler,directory,label,status)
        except AssertionError as error:return error.args
    return None


def verify_programs(items,compiler):
    """verify_program for many (source, label, status) at once, in processes of their own."""
    import multiprocessing
    with multiprocessing.get_context('fork').Pool(os.cpu_count() or 4) as pool:
        for failure in pool.imap(_one,[(source,compiler,label,status) for source,label,status in items],chunksize=4):
            assert failure is None,failure


def verify_legacy_program(source,compiler,root,label,status=0):
    # Old byte-profile fixtures migrate explicitly; new collection tests use
    # verify_program directly, without rewriting their list syntax.
    from source_syntax import native_bytes
    return verify_program(native_bytes(source),compiler,root,label,status)
