#!/usr/bin/env python3
"""Regenerate implementations/alchem/native-prelude-data.alc from library/*.alc.

library/NAME.alc holds the functions of library module NAME that are written
in Alchem. Each starts with a line `#: name/arity` (then `needs name/arity ...`
for the other library functions it calls, `Module.name/arity` in another file) and runs to the next such line.
The compiler appends to a program the functions it mentions, as modules
AlchemNAMEarity: one per number of parameters, since a name may be defined
for several. `#: name/arity form 2` is another definition of the same name and
number for other types (module AlchemNAMEarityv2); a call takes the first
form its arguments fit.

The generated file holds no function per entry. The packed text of each
appended module is one byte string (ny_dN, in parts when it is long), and one
index (ny_index) says what a program's text has to hold for an entry to be
appended. The compiler reads the program once (ny_pick in native-prelude.alc)
and keeps a byte per entry and per flag:

- a trigger found in the text marks its entries, and a marked entry marks the
  entries of its `needs`, and those theirs (ny_mark);
- a flag is a word the text holds: a module's name, or native_compile;
- an entry is appended when it is marked or one of its `extras` flags is set,
  and all of its `homes` flags are set; its module is written when one of
  the module's `guard` flags is set (or it has none) and an entry is appended.

Two places are meant to be extended:

- triggers(entry) says what in a program's text marks an entry. A new kind of
  trigger is a new tuple there; ('raw', text), ('word', text) and
  ('call', module, name, arity or None) are what the index can hold, and a
  further kind needs a kind number in the buckets below and a branch in
  ny_hit.
- assemble(found) runs before the texts are packed: the place to change an
  entry's text as a whole. `#include NAME` in an entry already brings a
  component of the compiler in (included). Nothing bounds an entry's length
  but the u24 fields below: a module's packed text is held in parts.
- An entry that is appended on a condition of its own (the Regex entries)
  gets it as `extras` and `homes` flags where those are worked out in
  generate().

The layout of the index, every offset a u24 from its start:

  0    256 bytes: for each byte value the number of its bucket of texts that
       start with it, 0 for none
  256  u24 entries, u24 groups, u16 number of entries, u16 number of groups,
       u16 number of flags
  268  u24 per bucket: its texts, each `length, text, kind, u24 payload`,
       ended by length 0. kind 0: the text anywhere marks the list at payload;
       1: the text as a whole word marks the list; 2: the word is a library
       module and payload its names
  names of a module: u16 count, then per name in byte order a u32 offset of
       `length, name, u24 list, count, then count times (arity, u24 list)`:
       the list for the name with any arguments, and the lists for a call
       with that many (nh_given)
  a list: u16 count, then u16 numbers: an entry's, or the number of entries
       plus a flag's
  entries, in the order of the appended text, 17 bytes each: u16 group, u24
       offset and u24 length of its packed text in the group's byte string,
       u24 list of the entries it needs, u24 list of its homes, u24 list of
       its extras
  groups, 8 bytes each and one more to end them: u16 first entry, u24 offset
       of `length, name of the appended module`, u24 list of its guard (0
       for none)"""
import base64
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


RESERVED=set('bytes b defmodule def defp do end if else case cond integer list string boolean option some none true false not and or fn in as is on of when with for raise return float atom map tuple result ok error nil rem div abs min max length hd tl elem inspect then tap trunc round floor ceil try rescue catch after throw Enum at count concat slice Regex rx_tt rx_compile'.split())


def included(name):
    """A component of the compiler as library text: implementations/alchem/NAME
    without its module line, its comments and its smoke test, its names
    shortened, and with the tables asked of the library, which holds them
    once (library/Regex.alc)."""
    text=(ROOT/'implementations/alchem'/name).read_text().split('\n',1)[1].partition('  # Native smoke test;')[0]
    text=''.join(line+'\n' for line in text.split('\n') if line.strip() and not line.strip().startswith('#'))
    text=text.replace('rx_tb()','Regex.rx_tt()')
    words={}
    for word in re.findall(r'[A-Za-z_][A-Za-z_0-9]*',text):words[word]=words.get(word,0)+1
    names=sorted(set(words)-RESERVED,key=lambda word:(-words[word],word))
    letters='abcdefghijklmnopqrstuvwxyz'
    short=(a+c for a in ['']+list(letters) for c in letters)
    alias={}
    for word in names:
        new=next(short)
        while new in RESERVED:new=next(short)
        alias[word]=new
    return re.sub(r'[A-Za-z_][A-Za-z_0-9]*',lambda m:alias.get(m[0],m[0]),text)


def entries():
    found=[]
    for path in sorted((ROOT/'library').glob('*.alc')):
        module=path.stem;current=None
        for line in path.read_text().split('\n'):
            head=re.fullmatch(r'#: (\S+)/(\d+)(?: form (\d+))?( exact)?(?: needs (.*))?',line)
            kind=re.fullmatch(r'#: struct ([\w.]+)(?: also (.*))?',line)
            if kind:
                current={'module':module,'name':kind[1],'arity':0,'form':1,'needs':[],'text':'','struct':True,'also':(kind[2] or '').split()}
                found.append(current);continue
            if head:
                current={'module':module,'name':head[1],'arity':int(head[2]),'form':int(head[3] or 1),'needs':[((n.split('.')[0] if '.' in n else module),n.split('.')[-1].split('/')[0],n.split('/')[1]) for n in (head[5] or '').split()],'text':'','exact':bool(head[4])}
                found.append(current)
            elif current is not None and line.startswith('#include '):current['text']+=included(line.split()[1])
            elif current is not None and not line.startswith('#'):current['text']+=line+'\n'
    for e in found:
        e['text']=e['text'].strip('\n')+'\n'
        assert '"""' not in e['text'],e['name']
        assert e.get('struct') or re.search(r'^  defp? '+re.escape(e['name'])+r'\(',e['text'],re.M),e['name']
        # Indentation and blank lines are for the reader: the compiler's own
        # source, which holds this text as byte literals, has a size limit.
        e['text']=''.join(line.strip()+'\n' for line in e['text'].split('\n') if line.strip())
    return found


def typed(entry,kind):
    """Whether the entry's code, its strings aside, names the type."""
    code=re.sub(r'"(?:\\.|[^"\\])*"','""',entry['text'])
    return re.search(r'(?<![\w.:])'+re.escape(kind)+r'(?![\w(:])',code) is not None


def literal(data):
    """data as b"..." literals of base64, joined by halves. 384 bytes (512
    characters) each: the seed-built compiler, whose calls nest 1024 deep,
    fails on a literal of 1,024 characters and reads one of 768."""
    parts=['b"'+base64.b64encode(bytes(data[i:i+384])).decode()+'"' for i in range(0,len(data),384)] or ['b""']
    while len(parts)>1:parts=[('Enum.concat('+parts[i]+','+parts[i+1]+')' if i+1<len(parts) else parts[i]) for i in range(0,len(parts),2)]
    return parts[0]


def compress(texts):
    """Byte-pair coding: bytes below 128 stand for themselves; a code from 128
    up is a pair of symbols, or (255, byte) for a byte from 128 up. Returns
    the coded texts, the table (two bytes per code from 128) and the order
    in which the symbols are numbered in the texts."""
    raw=sorted({b for t in texts for b in t if b>=128})
    table=[(255,b) for b in raw]
    alias={b:128+i for i,b in enumerate(raw)}
    coded=[[alias.get(b,b) for b in t] for t in texts]
    while len(table)<127:
        counts={}
        for t in coded:
            for pair in zip(t,t[1:]):counts[pair]=counts.get(pair,0)+1
        if not counts:break
        best=max(sorted(counts),key=counts.get)
        if counts[best]<4:break
        code=128+len(table);table.append(best)
        merged=[]
        for t in coded:
            out=[];i=0
            while i<len(t):
                if i+1<len(t) and (t[i],t[i+1])==best:out.append(code);i+=2
                else:out.append(t[i]);i+=1
            merged.append(out)
        coded=merged
    # A byte of the compiler's source costs by its decimal digits, so the
    # symbols are numbered by how often they occur: the commonest ten are
    # one digit. order gives the symbol behind each number.
    counts={}
    for t in coded:
        for v in t:counts[v]=counts.get(v,0)+1
    order=sorted(counts,key=lambda v:(-counts[v],v))
    rank={v:i for i,v in enumerate(order)}
    return [bytes(rank[v] for v in t) for t in coded],bytes(v for pair in table for v in pair),bytes(order)


def joined(items):
    items=list(items)
    while len(items)>1:items=['nc_join('+','.join(items[i:i+3]+['b[]']*(3-len(items[i:i+3])))+')' for i in range(0,len(items),3)]
    return items[0] if items else 'b[]'


def held(name,data):
    """Functions that make name() the byte string data. The seed-built
    compiler reads a function body 16 tokens to a nested call and is allowed
    1024 calls, so a long string is held in parts of 4000 bytes."""
    parts=[data[i:i+4000] for i in range(0,len(data),4000)]
    if len(parts)<2:return [f'  def {name}(): bytes do {literal(data)} end\n']
    return [f'  def {name}_{k}(): bytes do {literal(part)} end\n' for k,part in enumerate(parts)]+[f'  def {name}(): bytes do {joined([f"{name}_{k}()" for k in range(len(parts))])} end\n']


def assemble(found):
    """The entries as they are packed. An extension point: an entry whose
    text comes from other files, or is too long for one piece, is put
    together or split here."""
    return found


def triggers(e):
    """What in a program's text marks the entry (see the top of the file).
    A struct is wanted wherever the name of its file's module, its own name
    (the part after a dot) or a text after `also` in its header stands,
    inside a longer word too: a file may hold several types under one entry,
    and a date sigil names no type. A Kernel function is called by its bare
    name. A program cannot mention Sys, the library's own module. `exact` in
    an entry's line: only a call with its number of arguments mentions it
    (IO.puts of two, beside the compiler's own)."""
    if e.get('struct'):return [('raw',text) for text in sorted({e['module'],e['name'].split('.')[-1],*e.get('also',[])})]
    if e['module']=='Sys':return []
    if e['module']=='Kernel':
        assert not e.get('exact'),e['name']
        return [('word',e['name'])]
    return [('call',e['module'],e['name'],e['arity'] if e.get('exact') else None)]


def generate():
    found=assemble(entries());key=lambda e:(e['module'],e['name'],str(e['arity']),e['form'])
    by_call={}
    for e in found:by_call.setdefault(key(e)[:3],[]).append(e)
    def closure(e,seen):
        for module,name,arity in e['needs']:
            for other in by_call[(module,name,arity)]:
                assert not other.get('struct'),(e['name'],other['name'])
                if key(other) not in seen:seen.add(key(other));closure(other,seen)
        return seen
    # The mentions that reach an entry: its own and those of every entry
    # that needs it, however far. Only the rules below read them; the
    # compiler follows `needs` itself.
    users={key(e):set() for e in found}
    for e in found:
        mention=(e['module'],e['name'],e['arity']) if e.get('exact') else (e['module'],e['name'])
        users[key(e)].add(mention)
        for k in closure(e,set()):users[k].add(mention)
    packed,table,order=compress([e['text'].encode() for e in found])
    for e,text in zip(found,packed):e['packed']=text
    groups={}
    # Every struct a library file declares lives in one module, AlchemTypes,
    # where the compiler looks a type name up that the using module does not
    # declare.
    for e in found:groups.setdefault(('~Types',0,1) if e.get('struct') else (e['module'],e['arity'],e['form']),[]).append(e)
    groups=sorted(groups.items())
    ordered=[e for _,members in groups for e in members]
    for number,e in enumerate(ordered):e['id']=number
    assert len(ordered)<60000 and len(groups)<65536
    # Flags are numbered as they are first asked for, in an order that does not change from run to run.
    flags={'native_compile':0}
    def flag(word):return len(ordered)+flags.setdefault(word,len(flags))
    for e in ordered:
        e['after']={other['id'] for module,name,arity in e['needs'] for other in by_call[(module,name,arity)]}
        e['extras']=set();e['homes']=set()
    for e in ordered:
        if e.get('struct'):
            # A function of another module that names the type needs it too.
            for o in ordered:
                if not o.get('struct') and o['module']!=e['module'] and typed(o,e['name']):o['after'].add(e['id'])
            continue
        # A Sys function that needs only Sys functions and that many
        # functions of one module need comes with any mention of that module.
        if e['module']=='Sys' and all(k[0]=='Sys' for k in closure(e,set())):
            wanted={u for u in users[key(e)] if u[0]!='Sys'}
            e['extras']={flag(u[0]) for u in sorted(wanted) if u[0]!='IO' and sum(1 for other in wanted if other[0]==u[0])>3}
        # Only IO has forms told apart by another module's type (IO.puts of
        # a file needs File); elsewhere a function that names a type of
        # another file (Time's are in Date) is wanted on its own mention alone.
        if e['module']=='IO':e['homes']={flag(s['module']) for s in ordered if s.get('struct') and s['module']!=e['module'] and typed(e,s['name'])}
        # What matches a regular expression is of use to every program that
        # holds one (sg_hints names Regex in it) and to no other, whatever
        # needs it; the forms of other modules that take one only to such a
        # program; the component that compiles one only to a program that
        # compiles one as it runs.
        if e['module']=='Regex' and e['name'] not in ('rx_compile','compile','compile!'):e['extras']={flag('Regex')};e['homes']=e['homes']|{flag('Regex')}
        if e['module']!='Regex' and any(module=='Regex' for module,_,_ in e['needs']):e['homes']=e['homes']|{flag('Regex')}
    # A module is of use when a module that needs one of its functions is mentioned.
    guards=[]
    for place,members in groups:
        modules={u[0] for e in members for u in users[key(e)] if u[0]!='Sys'} or {'Sys'}
        guards.append(None if 'Kernel' in modules or place[0]=='~Types' else {flag(module) for module in sorted(modules)})
    u16=lambda v:bytes((v%256,v//256));u24=lambda v:bytes((v%256,v//256%256,v//65536));u32=lambda v:u24(v)+b'\0'
    raw={};words={word:[number] for word,number in ((w,len(ordered)+n) for w,n in flags.items())};calls={}
    for e in ordered:
        for trigger in triggers(e):
            if trigger[0]=='raw':raw.setdefault(trigger[1],[]).append(e['id'])
            elif trigger[0]=='word':words.setdefault(trigger[1],[]).append(e['id'])
            else:calls.setdefault(trigger[1],{}).setdefault(trigger[2],{}).setdefault(trigger[3],[]).append(e['id'])
    firsts=sorted({text.encode()[0] for text in [*raw,*words,*calls]})
    blob=bytearray(256+12+3*len(firsts))
    def place(data):
        at=len(blob);blob.extend(data);return at
    lists={}
    def listed(ids):
        ids=tuple(sorted(ids))
        if ids not in lists:lists[ids]=place(u16(len(ids))+b''.join(u16(i) for i in ids))
        return lists[ids]
    patterns=[(text.encode(),0,listed(ids)) for text,ids in sorted(raw.items())]+[(word.encode(),1,listed(ids)) for word,ids in sorted(words.items())]
    for module,names in sorted(calls.items()):
        records=[]
        for name,by_count in names.items():
            exact=sorted((count,ids) for count,ids in by_count.items() if count is not None)
            assert len(name.encode())<256 and len(exact)<256 and all(count<256 for count,_ in exact)
            records.append((name.encode(),place(bytes([len(name.encode())])+name.encode()+u24(listed(by_count.get(None,[])))+bytes([len(exact)])+b''.join(bytes([count])+u24(listed(ids)) for count,ids in exact))))
        patterns.append((module.encode(),2,place(u16(len(records))+b''.join(u32(at) for _,at in sorted(records)))))
    buckets={}
    for text,kind,payload in patterns:
        assert 0<len(text)<256 and text[0] not in b' \t\r\n#',text
        buckets.setdefault(text[0],[]).append(bytes([len(text)])+text+bytes([kind])+u24(payload))
    assert len(buckets)<256 and sorted(buckets)==firsts
    for number,(first,items) in enumerate(sorted(buckets.items())):
        blob[first]=number+1;blob[268+3*number:271+3*number]=u24(place(b''.join(items)+b'\0'))
    out=[];records=[];heads=[]
    for g,(((module,arity,form),members),guard) in enumerate(zip(groups,guards)):
        data=b''
        for e in members:
            records.append(u16(g)+u24(len(data))+u24(len(e['packed']))+u24(listed(e['after']))+u24(listed(e['homes']))+u24(listed(e['extras'])));data+=e['packed']
        name=('Alch\x7fmTypes' if module=='~Types' else f'Alch\x7fm{module}{arity}'+('' if form==1 else f'v{form}')).encode()
        heads.append(u16(members[0]['id'])+u24(place(bytes([len(name)])+name))+u24(0 if guard is None else listed(guard)))
        assert len(data)<1<<24
        out.extend(held(f'ny_d{g}',data))
    heads.append(u16(len(ordered))+bytes(6))
    assert len(ordered)+len(flags)<65536
    blob[256:268]=u24(place(b''.join(records)))+u24(place(b''.join(heads)))+u16(len(ordered))+u16(len(groups))+u16(len(flags))
    assert len(blob)<1<<24
    def choose(first,stop):
        if stop-first==1:return f'ny_d{first}()'
        middle=(first+stop)//2
        return f'if group < {middle} do {choose(first,middle)} else {choose(middle,stop)} end'
    out.append(f'  # The packed text of the members of appended module number group.\n  def ny_data(group: integer): bytes do {choose(0,len(groups))} end\n')
    out.append(f'  # The pairs behind the codes from 128 up of the packed library text.\n  def ny_pairs(): bytes do {literal(table)} end\n  # The symbol behind each number of the packed text, the commonest first.\n  def ny_order(): bytes do {literal(order)} end\n')
    out.append('  # What marks each library function, what it needs and where its text is (scripts/generate-prelude.py).\n')
    out.extend(held('ny_index',bytes(blob)))
    text=('defmodule NativePreludeData do\n  # Generated from library/*.alc by scripts/generate-prelude.py.\n'+''.join(out)+
          '  # Native smoke test; generated library source.\n  def main() do System.halt(0) end\nend\n')
    return text,len(found)


if __name__=='__main__':
    text,count=generate()
    (ROOT/'implementations/alchem/native-prelude-data.alc').write_text(text)
    print(f'Library functions written in Alchem: {count}')
