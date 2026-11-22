#!/usr/bin/env python3
"""What a running Windows process has committed, by allocation: a tool for
finding what a native Windows program commits (issue #104). Windows only.

    windows-commit-map.py [--most MIB] SECONDS PROGRAM.exe [ARGS...] [< INPUT]

The program is started, left to run SECONDS (its standard input is a pipe
held open, so a program that reads it waits there), and its address space
is walked with VirtualQueryEx: each allocation that holds committed
private memory is listed with its base, the size reserved, the size
committed and its protection, largest first, then the total. The program
is then ended. With --most, a total of more than MIB MiB is a failure:
the Windows job checks so that a program commits about what it uses."""
import ctypes
from ctypes import wintypes
import subprocess
import sys
import time

MEM_COMMIT, MEM_PRIVATE = 0x1000, 0x20000


class Basic(ctypes.Structure):
    _fields_ = [('BaseAddress', ctypes.c_void_p), ('AllocationBase', ctypes.c_void_p), ('AllocationProtect', wintypes.DWORD),
                ('PartitionId', wintypes.WORD), ('RegionSize', ctypes.c_size_t), ('State', wintypes.DWORD),
                ('Protect', wintypes.DWORD), ('Type', wintypes.DWORD)]


def commit_map(handle):
    """{allocation base: [reserved, committed, protections]} of a process."""
    query = ctypes.windll.kernel32.VirtualQueryEx
    query.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(Basic), ctypes.c_size_t]
    query.restype = ctypes.c_size_t
    found, address, info = {}, 0, Basic()
    while address < 0x7FFFFFFF0000 and query(handle, ctypes.c_void_p(address), ctypes.byref(info), ctypes.sizeof(info)):
        size = info.RegionSize
        if info.Type == MEM_PRIVATE and info.AllocationBase:
            entry = found.setdefault(info.AllocationBase, [0, 0, set()])
            entry[0] += size
            if info.State == MEM_COMMIT:
                entry[1] += size
                entry[2].add(hex(info.Protect))
        address = (info.BaseAddress or 0) + size
    return found


def main(arguments):
    most = None
    if arguments[:1] == ['--most']:
        most, arguments = float(arguments[1]), arguments[2:]
    if len(arguments) < 2:
        raise SystemExit(__doc__)
    seconds, command = float(arguments[0]), arguments[1:]
    given = sys.stdin.buffer.read() if not sys.stdin.isatty() else b''
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if given:
        process.stdin.write(given)
        process.stdin.flush()
    time.sleep(seconds)
    if process.poll() is not None:
        raise SystemExit(f'{command[0]} ended (status {process.returncode}) before it was measured')
    found = commit_map(int(process._handle))
    process.kill()
    process.wait()
    mib = 1 << 20
    total = 0
    for base, (reserved, committed, protections) in sorted(found.items(), key=lambda item: -item[1][1]):
        if committed:
            total += committed
            print(f'{base:#014x}  reserved {reserved / mib:9.1f} MiB  committed {committed / mib:9.1f} MiB  {",".join(sorted(protections))}')
    print(f'total committed private memory of {command[0]}: {total / mib:.1f} MiB in {sum(1 for v in found.values() if v[1])} allocations')
    if most is not None and total > most * mib:
        raise SystemExit(f'{command[0]} commits {total / mib:.1f} MiB, more than {most:.0f} MiB')


if __name__ == '__main__':
    main(sys.argv[1:])
