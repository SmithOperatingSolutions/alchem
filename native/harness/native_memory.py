"""Measure the documented R12/R13 native arena charge at syscall boundaries."""
import ctypes
import os
import resource
import signal
import subprocess
import tempfile


class TraceUnavailable(RuntimeError):pass


class Registers(ctypes.Structure):
    _fields_=[(name,ctypes.c_ulonglong) for name in ('r15','r14','r13','r12','rbp','rbx','r11','r10','r9','r8','rax','rcx','rdx','rsi','rdi','orig_rax','rip','cs','eflags','rsp','ss','fs_base','gs_base','ds','es','fs','gs')]


# An ordinary program reserves ARENA lazily, or the largest half of it the
# system grants down to FLOOR (nc_arena_init).
ARENA=16<<30
FLOOR=4<<20


def floor_arena(executable):
    """A preexec_fn: address space in which the program's reservation halves down to FLOOR.

    The program maps its arena (and one page after it) before its stack. Past
    its image it is granted 7 MiB here: 8 MiB of arena does not fit, 4 MiB
    does, and what is left gives the stack 2 MiB."""
    space=os.path.getsize(executable)+FLOOR+(3<<20)
    return lambda:resource.setrlimit(resource.RLIMIT_AS,(space,space))


def profile(executable,source,arena_bytes=None,limit=None):
    """Exit status, output, errors and the most bytes charged to the arena.

    arena_bytes is the arena's size where the entry maps exactly that much
    (compiler entries, seed programs). An ordinary program's reservation
    depends on what the system grants, so with None the arena is taken from
    the first stop at which R12 is set: it is still the arena's start then,
    R13 its end, and their distance must be a size nc_arena_init can reserve.
    The charge is what R12 has advanced by, whatever was reserved."""
    libc=ctypes.CDLL(None,use_errno=True)
    libc.ptrace.argtypes=[ctypes.c_ulong,ctypes.c_ulong,ctypes.c_void_p,ctypes.c_void_p]
    libc.ptrace.restype=ctypes.c_long
    def trace(request,pid,data=None):
        if libc.ptrace(request,pid,None,data)==-1:raise OSError(ctypes.get_errno(),'ptrace')
    def traceme():
        if libc.ptrace(0,0,None,None)==-1:os._exit(126)
    with tempfile.TemporaryFile() as input_file,tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as errors:
        input_file.write(source);input_file.seek(0)
        def start():
            if limit:limit()
            traceme()
        child=subprocess.Popen([str(executable)],stdin=input_file,stdout=output,stderr=errors,env={'PATH':''},preexec_fn=start)
        peak=0;base=None
        try:
            _,status=os.waitpid(child.pid,0)
            if os.WIFEXITED(status):
                child.returncode=os.waitstatus_to_exitcode(status)
                if child.returncode==126:raise TraceUnavailable('ptrace unavailable')
                raise AssertionError(('trace child exited before exec stop',child.returncode))
            trace(0x4200,child.pid,ctypes.c_void_p(1)) # TRACESYSGOOD
            deliver=0
            while True:
                trace(24,child.pid,ctypes.c_void_p(deliver)) # SYSCALL
                _,status=os.waitpid(child.pid,0)
                if os.WIFEXITED(status) or os.WIFSIGNALED(status):
                    child.returncode=os.waitstatus_to_exitcode(status);break
                stop=os.WSTOPSIG(status);deliver=0
                if stop==(signal.SIGTRAP|0x80):
                    regs=Registers();trace(12,child.pid,ctypes.cast(ctypes.byref(regs),ctypes.c_void_p))
                    if arena_bytes is None:
                        if base is None and regs.r12>65536 and regs.r13>regs.r12:
                            base=regs.r12;size=regs.r13-regs.r12
                            assert FLOOR<=size<=ARENA and size&(size-1)==0,('arena reservation',size)
                        if base is not None and base<=regs.r12<=base+size:peak=max(peak,regs.r12-base)
                    elif regs.r13>=arena_bytes and regs.r13-arena_bytes<=regs.r12<=regs.r13:
                        peak=max(peak,regs.r12-regs.r13+arena_bytes)
                elif stop!=signal.SIGTRAP:deliver=stop
            output.seek(0);errors.seek(0)
            return child.returncode,output.read(),errors.read(),peak
        finally:
            if child.returncode is None:child.kill();child.wait()
