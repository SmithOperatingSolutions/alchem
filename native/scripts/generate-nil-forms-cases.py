#!/usr/bin/env python3
"""Regenerate harness/nil-forms-cases.json.xz: the programs of the nil_forms
gate with what the pinned compiler makes of each. Not used by normal builds.

The programs are the hand-written probes of harness/nil-forms-hand.json.xz
(spec/alchem-failures.md, "nil" and "Calls that are no statements and
values that are none"): every way a program reads the nil a receive that
ran out of time leaves for an option, a result, a sum type and the structs
and tuples that hold them (inspect, ==, case, clauses, with, for, pattern
bindings, the library's functions that take an option from a function,
JSON, sending it on), and the forms the pinned compiler rejects: Kernel.
before what is no function, elem and put_elem and a variant as a statement,
and a call that gives no value used as one.

Every program is run by build/dev/alchem-upstream (its answers are kept in
build/dev/nil-forms-upstream.json) and by build/dev/A2. A case is the
source, then the status, standard output and standard error of the run with
the file named <stdin>; a program the pinned compiler rejects has status
null. Only programs the native compiler agrees on are written, since the
gate has to pass; the others are printed."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import hashlib
import importlib.util
import json
import lzma
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('gaps_cases',ROOT/'scripts/generate-gaps-cases.py')
gaps=importlib.util.module_from_spec(spec);spec.loader.exec_module(gaps)


def main():
    programs=list(dict.fromkeys(json.loads(lzma.decompress((ROOT/'harness/nil-forms-hand.json.xz').read_bytes()))))
    kept_path=ROOT/'build/dev/nil-forms-upstream.json'
    kept=json.loads(kept_path.read_text()) if kept_path.exists() else {}
    key=lambda s:hashlib.sha1(s.encode()).hexdigest()
    todo=[s for s in programs if key(s) not in kept]
    with ThreadPoolExecutor(4) as pool:
        for s,r in zip(todo,pool.map(gaps.upstream,todo)):kept[key(s)]=r
    kept_path.write_text(json.dumps(kept))
    with ThreadPoolExecutor(4) as pool:ours=list(pool.map(gaps.native,programs))
    cases=[];differ=[];unanswered=0
    for s,n in zip(programs,ours):
        u=kept[key(s)]
        if u[0] in ('timeout','resources') or u[0]==-9:unanswered+=1;continue
        same=(u[0] is None and n[0] is None) or (u[0] is not None and u==n)
        if same:cases.append([s,u[0],u[1],u[2] if u[0] is not None else ''])
        else:differ.append((s,u,n))
    (ROOT/'harness/nil-forms-cases.json.xz').write_bytes(lzma.compress(json.dumps(cases).encode(),preset=9))
    for s,u,n in differ:print('DIFFERS',repr(s[-300:]),'| pinned',u[0],repr(u[1][-80:]),repr(u[2][-160:]),'| native',n[0],repr(n[1][-80:]),repr(n[2][-80:]))
    print(len(cases),'cases written,',sum(1 for c in cases if c[1] is None),'of them rejections;',len(differ),'programs differ and are left out;',unanswered,'had no answer from the pinned compiler within its ceiling')


if __name__=='__main__':main()
