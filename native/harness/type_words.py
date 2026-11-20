#!/usr/bin/env python3
"""Structural types as prefix byte strings: boundaries, children, type lists and merging."""
from pathlib import Path
import random
import re
import sys
import tempfile
from run import ROOT
from self_hosted_components import verify_programs,literal

LIMIT=255
DEPTH=130


def helper(name):
    """A function of the compiler that the type module calls."""
    text=(ROOT/'implementations/alchem/native-compiler.alc').read_text()
    return re.search(r'  def '+name+r'\(.*?\n  end\n',text,re.S).group(0)


def encode(tree):
    tag,children=tree
    return bytes([tag]+([len(children)-(tag==10)] if tag in (5,10) else []))+b''.join(encode(child) for child in children)


def cells(kinds):
    return b''.join(bytes([len(kind)])+kind for kind in kinds)


def merge(a,b):
    """Independent oracle on trees: unknown (9) gives way; functions only merge when equal."""
    if a==b:return a
    if a[0]==9:return b
    if b[0]==9:return a
    if a[0]!=b[0] or a[0] not in (4,5,6,7,8) or len(a[1])!=len(b[1]):return None
    children=[merge(x,y) for x,y in zip(a[1],b[1])]
    return None if None in children else (a[0],children)


def verify(compiler):
    source=(ROOT/'implementations/alchem/native-types.alc').read_text().split('  def nt_type(',1)[0]
    source+=''.join(helper(name) for name in ['nc_slice','nc_join','nc_zeros','nc_half','nc_hi','nc_u16','nc_upper','nc_quot256','nc_quot_high','nc_quot_low','nc_u32','nc_u24','nc_read','nc_cursor','nc_long'])
    # Large types are built in the program: a literal of 255 bytes exceeds a body's tokens.
    source+=('  def repeat(kind: bytes, count: integer): bytes do if count == 0 do b[] else Enum.concat(nt_cell(kind),repeat(kind,count-1)) end end\n'
             '  def six(kind: bytes): bytes do nt_tuple(repeat(kind,6),6) end\n  def wide(): bytes do six(six(b[2])) end\n')
    rng=random.Random(171122)
    def tree(depth,holes=False):
        if depth==0 or rng.randrange(3)==0:return (rng.choice([0,1,2,3,9] if holes else [0,1,2,3]),[])
        tag=rng.choice([4,5,6,7,8,10])
        count=rng.randrange(0,4) if tag==5 else rng.randrange(1,4) if tag==10 else 1 if tag in (4,7) else 2
        return (tag,[tree(depth-1,holes) for _ in range(count)])
    same=lambda expression,kind:(f'nt_same({expression},{literal(list(kind))})',1)
    none=lambda expression:(f'Enum.count({expression})',0)
    tests=[]
    for value in [0,1,255,256,(1<<60)-1,(1<<63)-1]+[rng.randrange(1<<60) for _ in range(6)]:
        tests+=[(f'nt_div({value},{divisor})',value//divisor) for divisor in [1,16,65536]]+[(f'nt_read_word(nt_word({value}),0)',value)]
    seen=set()
    while len(seen)<40:
        shape=tree(4);kind=encode(shape)
        if kind in seen or len(kind)>LIMIT:continue
        seen.add(kind);text=literal(list(kind))
        tests+=[(f'nt_end({text},0)',len(kind)),(f'nt_tag({text})',kind[0]),same(f'nt_read(nt_cell({text}),0)',kind),
                (f'nt_count({text})',len(shape[1])-(kind[0]==10) if kind[0] in (5,10) else 0)]
        tests+=[same(f'nt_child({text},{index})',encode(child)) for index,child in enumerate(shape[1])]
        tests.append(none(f'nt_child({text},{len(shape[1])})'))
        # A truncated type is malformed.
        if len(kind)>1:tests.append((f'nt_end({literal(list(kind[:-1]))},0)',-1))
    # Constructors, at and beyond 255 bytes and 130 levels.
    deep=lambda levels:bytes([7]*levels+[2])
    six=lambda kind:bytes([5,6])+kind*6
    entries=[b'\x00',b'\x07\x02',b'',six(b'\x02')]
    tests+=[same('nt_unary(4,b[2])',b'\x04\x02'),same('nt_binary(6,b[0],b[2])',b'\x06\x00\x02'),none('nt_unary(4,b[])'),none('nt_binary(8,b[2],b[])'),
            same(f'nt_unary(7,{literal(list(deep(DEPTH-2)))})',deep(DEPTH-1)),none(f'nt_unary(7,{literal(list(deep(DEPTH-1)))})'),
            (f'nt_end({literal(list(deep(DEPTH-1)))},0)',DEPTH),(f'nt_end({literal(list(deep(DEPTH)))},0)',-1),
            same('nt_tuple(b[],0)',b'\x05\x00'),same(f'nt_tuple({literal(list(cells([b"\x00",b"\x07\x02"])))},2)',b'\x05\x02\x00\x07\x02'),
            ('Enum.count(wide())',50),('Enum.count(nt_tuple(repeat(wide(),5),5))',252),('nt_end(nt_tuple(repeat(wide(),5),5),0)',252),
            # 255 bytes was the limit: a longer type is whole, and its cell holds the length in four bytes behind a 255.
            ('Enum.count(nt_tuple(repeat(wide(),6),6))',302),('nt_end(nt_tuple(repeat(wide(),6),6),0)',302),
            ('Enum.count(nt_cell(nt_tuple(repeat(wide(),6),6)))',307),('Enum.at(nt_cell(nt_tuple(repeat(wide(),6),6)),0,9)',255),('Enum.at(nt_cell(nt_tuple(repeat(wide(),6),6)),1,9)',46),
            ('Enum.count(nt_read(Enum.concat(b[7],nt_cell(nt_tuple(repeat(wide(),6),6))),1))',302),('nt_after(Enum.concat(b[7],nt_cell(nt_tuple(repeat(wide(),6),6))),1)',308),
            ('nt_items(nc_join(nt_cell(b[2]),nt_cell(nt_tuple(repeat(wide(),6),6)),nt_cell(b[0])),0)',3),same('nt_item(nc_join(nt_cell(b[2]),nt_cell(nt_tuple(repeat(wide(),6),6)),nt_cell(b[0,0])),2)',b'\x00\x00'),
            # A tuple of 300 parts: the count is 255 and three bytes.
            ('Enum.count(nt_tuple(repeat(b[2],300),300))',305),('nt_count(nt_tuple(repeat(b[2],300),300))',300),('Enum.at(nt_tuple(repeat(b[2],300),300),1,0)',255),
            same('nt_child(nt_tuple(Enum.concat(repeat(b[2],299),nt_cell(b[7,0])),300),299)',b'\x07\x00'),('nt_end(nt_tuple(repeat(b[2],300),300),0)',305),
            ('nt_count(nt_function(repeat(b[2],301),300))',300),same('nt_child(nt_function(Enum.concat(repeat(b[2],300),nt_cell(b[3])),300),300)',b'\x03'),
            ('Enum.count(nt_function(Enum.concat(nt_cell(b[2]),repeat(wide(),5)),5))',253),
            ('Enum.count(nt_function(Enum.concat(repeat(b[2],1),repeat(wide(),6)),6))',303),('Enum.count(nt_function(Enum.concat(repeat(b[2],2),repeat(wide(),4)),5))',204),
            same('nt_child(nt_tuple(repeat(wide(),5),5),4)',six(six(b'\x02'))),
            none(f'nt_tuple({literal(list(cells([b"\x00",b""])))},2)'),none('nt_tuple(b[1,0],2)'),
            ('Enum.at(nt_cell(Enum.concat(nt_tuple(repeat(wide(),5),5),b[2,2,2,2])),0,9)',255),('Enum.count(nt_cell(b[2]))',2),none('nt_read(b[2,2],0)'),same('nt_read(b[9,1,2],1)',b'\x02'),
            ('nt_tag(b[])',-1),('nt_same(b[4,2],b[4,3])',0),('nt_same(b[4,2],b[4,2,0])',0),
            (f'nt_items({literal(list(cells(entries)))},0)',4),same(f'nt_item({literal(list(cells(entries)))},1)',entries[1]),same(f'nt_item({literal(list(cells(entries)))},3)',entries[3]),
            none(f'nt_item({literal(list(cells(entries)))},2)'),none(f'nt_item({literal(list(cells(entries)))},4)'),
            same(f'nt_replace({literal(list(cells(entries)))},2,b[4,3])',cells([entries[0],entries[1],b'\x04\x03',entries[3]])),
            same(f'nt_replace({literal(list(cells(entries)))},0,b[7,7,3])',cells([b'\x07\x07\x03',entries[1],b'',entries[3]]))]
    # Merging against an independent oracle.
    merged=0
    while merged<40:
        a=tree(3,True);b=tree(3,True) if rng.randrange(2) else a
        if rng.randrange(2):b=(a[0],[child if rng.randrange(3) else (9,[]) for child in a[1]])
        if max(len(encode(a)),len(encode(b)))>LIMIT:continue
        want=merge(a,b);call=f'nt_merge({literal(list(encode(a)))},{literal(list(encode(b)))})'
        tests.append(none(call) if want is None else same(call,encode(want)));merged+=1
    verify_programs([(source+f'  def main() do if {expression} == {expected} do System.halt(0) else System.halt(1) end end\nend\n',('structural type',number,expression[:80]),0) for number,(expression,expected) in enumerate(tests)],compiler)
    print(f'PASS {len(tests)} structural type cases: prefix encoding, children, type lists, types and counts past 255, the 130-level limit and merging')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
