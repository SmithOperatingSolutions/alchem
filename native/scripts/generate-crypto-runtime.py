#!/usr/bin/env python3
"""Regenerate the checked crypto runtime literal; not used by normal builds."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_parse_runtime',ROOT/'scripts/generate-parse-runtime.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)


def generate():
    raw=shared.assemble((ROOT/'spec/crypto-x86_64.s').read_text())
    text=shared.module_text('NativeCryptoData','kr',raw,'Generated from spec/crypto-x86_64.s.','generated crypto runtime')
    return text,len(raw)


if __name__=='__main__':
    text,size=generate()
    (ROOT/'implementations/alchem/native-crypto-data.alc').write_text(text)
    print(f'Crypto runtime: {size} bytes')
