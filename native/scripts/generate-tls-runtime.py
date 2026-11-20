#!/usr/bin/env python3
"""Regenerate the checked TLS runtime literal; not used by normal builds."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_parse_runtime',ROOT/'scripts/generate-parse-runtime.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)


def generate():
    raw=shared.assemble((ROOT/'spec/tls-x86_64.s').read_text())
    text=shared.module_text('NativeTlsData','tq',raw,'Generated from spec/tls-x86_64.s.','generated TLS runtime')
    return text,len(raw)


if __name__=='__main__':
    text,size=generate()
    (ROOT/'implementations/alchem/native-tls-data.alc').write_text(text)
    print(f'TLS runtime: {size} bytes')
