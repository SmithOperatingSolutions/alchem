#!/usr/bin/env python3
"""Run a command under a ceiling on memory and time, where the system keeps
none (macOS has no address-space limit and no cgroups).

    bounded.py [--memory BYTES] [--seconds N] COMMAND [ARGS...]

The command runs in a process group of its own. Every 10 milliseconds the
memory it is charged for (its physical footprint, which counts compressed
pages too) is read, and every 200 that of every process of its group; past
the ceiling, or the time, the group is killed and the status is 137.
ALCHEM_MEMORY (6G, 512M, bytes) and ALCHEM_SECONDS give the defaults.
"""
import ctypes
import os
import signal
import subprocess
import sys
import time

LIBPROC = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True) if sys.platform == 'darwin' else None


def size(text):
    units = {'K': 1 << 10, 'M': 1 << 20, 'G': 1 << 30}
    return int(float(text[:-1]) * units[text[-1].upper()]) if text[-1].upper() in units else int(text)


def footprint(pid):
    """The bytes process pid is charged for; 0 when it is gone."""
    if LIBPROC is None:
        try:
            with open(f'/proc/{pid}/statm') as held:
                return int(held.read().split()[1]) * os.sysconf('SC_PAGE_SIZE')
        except OSError:
            return 0
    # struct rusage_info_v2: a uuid of 16 bytes, then 64-bit words, the
    # eighth of which is ri_phys_footprint.
    buffer = (ctypes.c_uint64 * 40)()
    if LIBPROC.proc_pid_rusage(pid, 2, ctypes.byref(buffer)) != 0:
        return 0
    return buffer[9]


def members(group):
    done = subprocess.run(['ps', '-axo', 'pid=,pgid='], capture_output=True, text=True)
    return [int(line.split()[0]) for line in done.stdout.splitlines() if len(line.split()) == 2 and line.split()[1] == str(group)]


def run(command, memory, seconds, **given):
    """The command's status, 137 when it was killed for memory or time;
    given goes to Popen (stdin, stdout, stderr, cwd, env)."""
    child = subprocess.Popen(command, start_new_session=True, **given)
    started = time.monotonic()
    others, looked, why = [], 0.0, ''
    while child.poll() is None:
        now = time.monotonic()
        if now - looked > 0.2:
            others, looked = [pid for pid in members(child.pid) if pid != child.pid], now
        used = footprint(child.pid) + sum(footprint(pid) for pid in others)
        if used > memory:
            why = f'memory: {used >> 20} MB past {memory >> 20} MB'
        elif now - started > seconds:
            why = f'time: past {seconds} s'
        if why:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            print(f'bounded: killed for {why}: {" ".join(map(str, command))[:200]}', file=sys.stderr)
            return 137
        time.sleep(0.01)
    try:
        os.killpg(child.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    return child.returncode if child.returncode >= 0 else 128 - child.returncode


def main(args):
    memory, seconds = size(os.environ.get('ALCHEM_MEMORY', '6G')), float(os.environ.get('ALCHEM_SECONDS', '600'))
    while args and args[0] in ('--memory', '--seconds'):
        if args[0] == '--memory':
            memory = size(args[1])
        else:
            seconds = float(args[1])
        args = args[2:]
    return run(args, memory, seconds)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
