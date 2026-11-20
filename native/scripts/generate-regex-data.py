#!/usr/bin/env python3
"""Regenerate implementations/alchem/native-regex-data.alc from spec/regex-tables.json; not used by normal builds.

The tables regexp/syntax takes from Go's unicode package, packed for
native-regex.alc (rx_tb). A number is written seven bits to a byte, the low
ones first, with 128 added to every byte but the last.

  0  the names of \\p{...}, hashed (name_hash), four bytes each: the 30
     general categories by how often their runs occur, the 8 that are unions
     of them, the scripts in the order of their names, Any, Ascii
  1  the other names, hashed, each with the number of the table it means;
     254 for Assigned, which is all but Cn
  2  the pairs unicode.SimpleFold exchanges: per run its first character less
     the first of the run before, twice its count less two plus one when it
     takes every other character, and how far away the partners are
  3  the characters that fold in threes and fours: per group its size, then
     its characters, three bytes each
  4  every code point's general category, as runs: a byte holds a run's
     length less one (7 when the length less eight follows as a number)
     plus eight times its category
  5  for each union of categories a byte per category, 1 when it is part;
     then the number of the category Nd
  6  the scripts: per script the size of what follows as a number, then per
     range its first character less the last of the range before and its
     length less one
"""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('alchem_parse_runtime',ROOT/'scripts/generate-parse-runtime.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
UNIONS=['C','L','LC','M','N','P','S','Z']
MODULUS=4294967291


def number(value):
    out=[]
    while True:
        low=value&127;value>>=7
        if value:out.append(low|128)
        else:out.append(low);return out


def canonical(name):
    """Go's regexp/syntax canonicalName."""
    out='';first=True
    for char in name:
        if char in '_- ':continue
        out+=char.upper() if first else char.lower();first=False
    return out


def name_hash(name):
    value=7
    for byte in canonical(name).encode():value=(value*31+byte)%MODULUS
    return value


def runs(categories):
    owner=[None]*0x110000
    for name,ranges in categories.items():
        for first,last in ranges:
            for point in range(first,last+1):
                assert owner[point] is None;owner[point]=name
    assert None not in owner
    out=[];start=0
    for point in range(1,0x110001):
        if point==0x110000 or owner[point]!=owner[start]:out.append((owner[start],point-start));start=point
    return out


def tables():
    data=json.loads((ROOT/'spec/regex-tables.json').read_text())
    partition=runs(data['categories'])
    count={}
    for name,_ in partition:count[name]=count.get(name,0)+1
    leaves=sorted(data['categories'],key=lambda name:(-count[name],name))
    assert len(leaves)==30 and sorted(data['unions'])==UNIONS
    scripts=sorted(data['scripts'])
    names=leaves+UNIONS+scripts+['Any','Ascii']
    index={name:i for i,name in enumerate(names)}
    hashes=[name_hash(name) for name in names]
    aliases=[(name_hash(alias),index[actual]) for alias,actual in sorted(data['aliases'].items())]+[(name_hash('Assigned'),254)]
    # A name is known by its hash alone: no two may share one, nor may the
    # hash of no name at all be one of them.
    every=hashes+[h for h,_ in aliases]
    assert len(set(every))==len(every) and 7 not in every and index['Cn']==0 and index['LC']==32 and index['L']==31
    section0=b''.join(h.to_bytes(4,'little') for h in hashes)
    section1=b''.join(h.to_bytes(4,'little')+bytes([i]) for h,i in aliases)
    partner={}
    for first,last,stride,delta in data['fold']:
        for point in range(first,last+1,stride):partner[point]=point+delta
    groups=[]
    for point in sorted(partner):
        orbit=[point];other=partner[point]
        while other!=point:orbit.append(other);other=partner[other]
        if len(orbit)>2 and min(orbit)==point:groups.append(sorted(orbit))
    grouped={point for group in groups for point in group}
    # The pairs, as runs of one distance; upper and lower case often
    # alternate, so a pair may continue the run before the last.
    pairs=[]
    for point in sorted(partner):
        delta=partner[point]-point
        if delta<0 or point in grouped:continue
        assert partner[point+delta]==point
        for run in pairs[-2:][::-1]:
            if run[3]!=delta:continue
            gap=point-run[1]
            if run[0]==run[1] and gap<=2:run[1],run[2]=point,gap;break
            if gap==run[2]:run[1]=point;break
        else:pairs.append([point,point,1,delta])
    assert len(partner)==2*sum(len(range(first,last+1,stride)) for first,last,stride,_ in pairs)+len(grouped)
    section2=bytearray();previous=0
    for first,last,stride,delta in pairs:
        section2+=bytes(number(first-previous)+number((last-first)//stride*2+stride-1)+number(delta));previous=first
    section3=b''.join(bytes([len(group)])+b''.join(point.to_bytes(3,'little') for point in group) for group in groups)
    section4=bytearray()
    for name,length in partition:
        section4+=bytes([min(length-1,7)+8*leaves.index(name)]+(number(length-8) if length>=8 else []))
    section5=bytes(1 if leaf in data['unions'][union] else 0 for union in UNIONS for leaf in leaves)+bytes([leaves.index('Nd')])
    section6=bytearray()
    for name in scripts:
        body=bytearray();previous=0
        for first,last in data['scripts'][name]:body+=bytes(number(first-previous)+number(last-first));previous=last
        section6+=bytes(number(len(body)))+body
    sections=[section0,section1,bytes(section2),section3,bytes(section4),section5,bytes(section6)]
    # The one character regexp/syntax leaves out of a class under (?i):
    # native-regex.alc takes it out of LC by its number.
    assert data['unfolded']=={'LC':[837]}
    offsets=[];place=3*(len(sections)+1)
    for section in sections:offsets.append(place);place+=len(section)
    offsets.append(place)
    return b''.join(o.to_bytes(3,'little') for o in offsets)+b''.join(sections),index


def generate():
    raw,_=tables()
    text=shared.module_text('NativeRegexData','rx_tb',raw,'Generated from spec/regex-tables.json by scripts/generate-regex-data.py.','generated tables of regular expressions')
    # The tables are one value, rx_tb(): eight offsets, then the sections.
    return text.replace('def rx_tb_blob()','def rx_tb()'),len(raw)


if __name__=='__main__':
    text,size=generate()
    (ROOT/'implementations/alchem/native-regex-data.alc').write_text(text)
    print(f'Tables of regular expressions: {size} bytes')
