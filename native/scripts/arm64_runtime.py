"""The ARM64 version of a runtime routine (spec/arm64.md): its x86-64 source
translated by scripts/x86-to-arm64.py, assembled by the GNU assembler of
build/arm64-tools, and written as base64 byte literals for the compiler."""
import base64
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
# The system's when it has one (the container), else the one
# scripts/fetch-arm64-tools.sh unpacks.
TOOLS = Path(shutil.which('aarch64-linux-gnu-as') or ROOT / 'build/arm64-tools/bin/aarch64-linux-gnu-as').parent


def translator():
    spec = spec_from_file_location('x86_to_arm64', ROOT / 'scripts/x86-to-arm64.py')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assemble(source, defines=()):
    """The bytes of the .text of x86-64 assembly source, as ARM64."""
    return assemble_with_symbols(source, defines)[0]


def assemble_with_symbols(source, defines=()):
    """The ARM64 bytes and {symbol: offset} of the labels in .text."""
    text = translator().translate(source, defines)
    with tempfile.TemporaryDirectory(prefix='alchem-arm64-runtime-') as d:
        root = Path(d)
        (root / 'runtime.s').write_text(text)
        subprocess.run([str(TOOLS / 'aarch64-linux-gnu-as'), '-march=armv8-a+crypto', '-o', str(root / 'runtime.o'), str(root / 'runtime.s')], check=True)
        subprocess.run([str(TOOLS / 'aarch64-linux-gnu-objcopy'), '-O', 'binary', '-j', '.text', str(root / 'runtime.o'), str(root / 'runtime.bin')], check=True)
        listing = subprocess.run([str(TOOLS / 'aarch64-linux-gnu-objdump'), '-t', str(root / 'runtime.o')], capture_output=True, text=True, check=True).stdout
        symbols = {}
        for line in listing.split('\n'):
            fields = line.split()
            if len(fields) >= 4 and fields[-2] != '*ABS*' and '.text' in line:
                symbols[fields[-1]] = int(fields[0], 16)
        return (root / 'runtime.bin').read_bytes(), symbols


def module_text(module, name, data, source, words=()):
    """A module whose function name() is data: base64 literals of 384 bytes,
    joined by halves."""
    parts = ['b"' + base64.b64encode(data[i:i + 384]).decode() + '"' for i in range(0, len(data), 384)] or ['b""']
    def join(first, stop):
        if stop - first == 1:
            return parts[first]
        middle = (first + stop) // 2
        return 'Enum.concat(' + join(first, middle) + ',' + join(middle, stop) + ')'
    return (f'defmodule {module} do\n  # Generated from {source} by scripts/x86-to-arm64.py and the ARM64\n'
            f'  # assembler (scripts/arm64_runtime.py): its ARM64 version (spec/arm64.md).\n'
            f'  def {name}(): bytes do {join(0, len(parts))} end\n'
            + ''.join(f'  def {word}(): integer do {value} end\n' for word, value in words)
            + '  # Native smoke test; generated ARM64 runtime.\n  def main() do System.halt(0) end\nend\n')
