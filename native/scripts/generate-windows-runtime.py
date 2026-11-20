#!/usr/bin/env python3
"""Regenerate native-windows-data.alc from spec/windows-x86_64.s: the PE
headers and the Windows layer that come before a Windows program's image
(spec/windows.md). Optional development step; normal builds never run it.

The file holds nw_prefix(), the bytes before the image, the image's RVA,
and the offsets of the three header fields that depend on the image's
size, which the compiler fills in (nw_pe)."""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x3C0000
CODE = 0x1000           # the layer's code and import tables, RX
DATA = 0x10000          # its data and the import address table, RW
IMAGE = 0x40000         # the program's image, at 0x400000, RX
SECTION_ALIGN = 0x1000
FILE_ALIGN = 0x200


def up(n, a):
    return (n + a - 1) // a * a


def assemble():
    with tempfile.TemporaryDirectory(prefix='alchem-windows-runtime-') as d:
        root = Path(d)
        subprocess.run(['as', '--64', '-o', root / 'w.o', ROOT / 'spec/windows-x86_64.s'], check=True)
        subprocess.run(['ld', '-o', root / 'w.elf', '-e', 'start', '--no-warn-rwx-segments',
                        '-Ttext', hex(BASE + CODE), '-Tdata', hex(BASE + DATA), root / 'w.o'], check=True)
        for name in ('text', 'data'):
            subprocess.run(['objcopy', '-O', 'binary', '-j', '.' + name, root / 'w.elf', root / (name + '.bin')], check=True)
        symbols = {}
        for line in subprocess.run(['nm', root / 'w.elf'], capture_output=True, text=True, check=True).stdout.splitlines():
            parts = line.split()
            if len(parts) == 3:
                symbols[parts[2]] = int(parts[0], 16)
        return (root / 'text.bin').read_bytes(), (root / 'data.bin').read_bytes(), symbols


def prefix():
    code, data, symbols = assemble()
    assert symbols['start'] == BASE + CODE, hex(symbols['start'])
    assert BASE + IMAGE == 0x400000
    assert len(code) <= DATA - CODE, len(code)
    data_size = symbols['data_end'] - (BASE + DATA)
    assert data_size <= IMAGE - DATA and len(data) <= data_size, (len(data), data_size)
    # The zeros at the end of the data are left to the loader.
    data = data.rstrip(b'\0')
    code_raw, data_raw = up(len(code), FILE_ALIGN), up(len(data), FILE_ALIGN)
    image_ptr = FILE_ALIGN + code_raw + data_raw

    dos = bytearray(64)
    dos[0:2] = b'MZ'
    dos[0x3C:0x40] = struct.pack('<I', 64)
    # Relocations stripped, executable, large-address aware.
    coff = struct.pack('<HHIIIHH', 0x8664, 3, 0, 0, 0, 240, 0x0001 | 0x0002 | 0x0020)
    directories = [(0, 0)] * 16
    directories[1] = (symbols['imports'] - BASE, symbols['imports_end'] - symbols['imports'])
    directories[12] = (symbols['iat'] - BASE, symbols['iat_end'] - symbols['iat'])
    optional = struct.pack('<HBBIIIII', 0x20B, 14, 0, code_raw, data_raw, 0, CODE, CODE)
    # No DYNAMIC_BASE: the image stays at its fixed addresses. NX compatible,
    # no SEH handlers, terminal-server aware; a console program.
    optional += struct.pack('<QIIHHHHHHIIIIHHQQQQII', BASE, SECTION_ALIGN, FILE_ALIGN, 6, 0, 0, 0, 6, 0, 0,
                            0, FILE_ALIGN, 0, 3, 0x0100 | 0x0400 | 0x8000,
                            0x100000, 0x10000, 0x100000, 0x1000, 0, 16)
    for address, size in directories:
        optional += struct.pack('<II', address, size)
    assert len(optional) == 240

    def section(name, vsize, rva, raw, pointer, flags):
        return name.ljust(8, b'\0') + struct.pack('<IIIIIIHHI', vsize, rva, raw, pointer, 0, 0, 0, 0, flags)
    # Windows loads only sections that follow one another in memory without
    # a gap (Wine is not so strict), so each reaches to the next.
    sections = section(b'.wtext', DATA - CODE, CODE, code_raw, FILE_ALIGN, 0x60000020)
    sections += section(b'.wdata', IMAGE - DATA, DATA, data_raw, FILE_ALIGN + code_raw, 0xC0000040)
    sections += section(b'.text', 0, IMAGE, 0, image_ptr, 0x60000020)
    head = bytes(dos) + b'PE\0\0' + coff + optional + sections
    assert len(head) <= FILE_ALIGN
    optional_at = 64 + 4 + 20
    image_section = optional_at + 240 + 2 * 40
    fields = {
        'nw_image_rva': IMAGE,
        'nw_size_of_image': optional_at + 56,
        'nw_image_vsize': image_section + 8,
        'nw_image_raw': image_section + 16,
    }
    out = head.ljust(FILE_ALIGN, b'\0') + code.ljust(code_raw, b'\0') + data.ljust(data_raw, b'\0')
    assert len(out) == image_ptr
    return out, fields


def literal(raw):
    if len(raw) <= 128:
        return 'b[' + ','.join(map(str, raw)) + ']'
    middle = len(raw) // 2
    return 'Enum.concat(' + literal(raw[:middle]) + ',' + literal(raw[middle:]) + ')'


def module_text(out, fields):
    pieces = ['defmodule NativeWindowsData do\n',
              '  # Generated from spec/windows-x86_64.s by scripts/generate-windows-runtime.py.\n']
    names = []
    for i in range(0, len(out), 384):
        name = f'nw_part_{i // 384}'
        names.append(name)
        pieces.append(f'  def {name}(): bytes do {literal(out[i:i + 384])} end\n')
    level = 0
    while len(names) > 1:
        merged = []
        for i in range(0, len(names), 3):
            group = names[i:i + 3]
            name = f'nw_group_{level}_{i // 3}'
            merged.append(name)
            args = [part + '()' for part in group] + ['b[]'] * (3 - len(group))
            pieces.append(f'  def {name}(): bytes do nc_join({",".join(args)}) end\n')
        names = merged
        level += 1
    pieces.append(f'  def nw_prefix(): bytes do {names[0]}() end\n')
    for name, at in fields.items():
        pieces.append(f'  def {name}(): integer do {at} end\n')
    pieces.append('  # Native smoke test; generated Windows layer.\n  def main() do System.halt(0) end\nend\n')
    return ''.join(pieces)


if __name__ == '__main__':
    out, fields = prefix()
    (ROOT / 'implementations/alchem/native-windows-data.alc').write_text(module_text(out, fields))
    print(f'Windows layer: {len(out)} bytes before the image', file=sys.stderr)
