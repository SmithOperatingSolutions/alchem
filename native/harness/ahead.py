"""A gate's programs compiled ahead of the gate, several at a time.

Most gates compile a program, run it, look, and go on to the next: one
processor works. The runners (scripts/verify-quick.py, verify-darwin.py)
install this before a gate: its programs are given to the compiler on other
processors, and the gate's own subprocess.run of the compiler is answered
with what came out. Every program is still compiled by the compiler the gate
was given, once, and is still run by the gate, one at a time, as before.

The programs are those the gate compiled the last time it passed here
(build/gate-sources), else those of its RUNS, REJECTS and cases(). One the
gate does not ask for is a compile wasted; one that is not among them is
compiled when the gate asks.
"""
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import lzma
import multiprocessing
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
KEPT = ROOT / 'build/gate-sources'
# How many programs are compiled before the gate asks for them, at most.
WINDOW = 48


def compile_one(compiler, text):
    try:
        done = subprocess.run([compiler], input=text, capture_output=True, env={'PATH': ''}, timeout=900)
    except subprocess.TimeoutExpired:
        return None
    return done.returncode, done.stdout, done.stderr


def sources(module):
    """The texts of the programs a gate holds in lists, in the gate's order."""
    found = []

    def take(items):
        for item in items:
            text = item[0] if isinstance(item, (tuple, list)) and item else item
            if isinstance(text, str) and 'defmodule' in text:
                found.append(text.encode('utf8', 'surrogateescape'))
    try:
        if hasattr(module, 'cases') and 'RUNS' in vars(module):
            for part in module.cases():
                take(part)
        else:
            take(getattr(module, 'RUNS', []))
            take(getattr(module, 'REJECTS', []))
    except (TypeError, ValueError, AttributeError):
        pass
    return found


def install(compiler, name, module, workers=None):
    """Answer the gate's compiles; returns what is called when it has passed."""
    kept = KEPT / (name + '.json.xz')
    asked = []
    try:
        planned = [text.encode('latin-1') for text in json.loads(lzma.decompress(kept.read_bytes()))]
    except (OSError, ValueError, lzma.LZMAError):
        planned = sources(module)
    plan, planned = iter(planned), None
    real = subprocess.run
    # Processes of their own: a fork of the gate's process, made by a thread
    # while the gate writes a program, holds that file open, and the program
    # cannot be run ("text file busy").
    pool = ProcessPoolExecutor(workers or max(2, (os.cpu_count() or 2) // 3), mp_context=multiprocessing.get_context('spawn'))
    made, given = {}, set()

    def fill():
        while len(made) < WINDOW:
            text = next(plan, None)
            if text is None:
                return
            key = hashlib.sha256(text).digest()
            if key not in given:
                given.add(key)
                made[key] = pool.submit(compile_one, str(compiler), text)

    def run(*args, **options):
        command = args[0] if len(args) == 1 else None
        text = options.get('input')
        if command != [str(compiler)] or not isinstance(text, bytes) or options.get('env') != {'PATH': ''} \
                or set(options) - {'input', 'capture_output', 'env', 'timeout'} or not options.get('capture_output'):
            return real(*args, **options)
        asked.append(text)
        key = hashlib.sha256(text).digest()
        waiting = made.pop(key, None)
        given.add(key)
        fill()
        answer = waiting.result() if waiting else None
        if answer is None:
            return real(*args, **options)
        return subprocess.CompletedProcess([str(compiler)], *answer)

    subprocess.run = run
    fill()

    def passed():
        subprocess.run = real
        pool.shutdown(wait=False, cancel_futures=True)
        if asked and sum(map(len, asked)) < 64 << 20:
            KEPT.mkdir(parents=True, exist_ok=True)
            staged = kept.with_suffix(f'.{os.getpid()}')
            staged.write_bytes(lzma.compress(json.dumps([text.decode('latin-1') for text in asked]).encode(), preset=1))
            staged.replace(kept)
    return passed
