#!/usr/bin/env python3
"""Exact word-collection/library arena charges, with independent expected sizes."""
from pathlib import Path
import subprocess
import sys
import tempfile
from native_memory import profile,floor_arena,TraceUnavailable


def verify(compiler):
    # A list of n elements takes 24+16n bytes (alchem-lists.md): the word that
    # closes its block below, one of padding, a count and an element per
    # element, and the count 0 that ends it. [] is a constant and takes none.
    cases=[
        (': list[integer] = []',0),('[1000]',40),('[1000,2000]',56),('["a"]',40),
        ('Enum.concat([1000],[2000])',136),('Enum.reverse([1000,2000])',112),
        ('Enum.slice([1000,2000],0,1)',96),('Enum.slice([1000,2000],1,1)',56),('Enum.drop([1000,2000],1)',56),
        ('Enum.map([1,2],&add)',112),('Enum.filter([1,2],&keep)',112),('Enum.reduce([1,2],0,&sum)',56),
        ('[1000 | [2000]]',160),('[1000, 3000 | [2000]]',160),(': list[integer] = [1000 | []]',88),
        (': map[integer, integer] = %{}',8),(': map[integer, integer] = Map.put(%{},1,2)',32),('Map.new([{1,2}])',88),('%{1 => 2}',88),
        ('Map.get(%{1 => 2},1)',104),('Map.get(%{1 => 2},3)',88),
        ('Map.keys(%{1 => 2})',128),('Map.to_list(%{1 => 2})',152),('Map.delete(%{1 => 2},1)',96),
        ('Integer.digits(123)',72),('Integer.undigits([])',0),
        ('String.duplicate("ab",3)',16),('String.duplicate("",0)',8),
        ('Enum.join(["a","b"],",")',72),('Enum.join(["a","b"])',72),('System.system_time()',0),
    ]
    helpers='def add(n: integer): integer do n+1 end def keep(n: integer): boolean do n > 1 end def sum(n: integer,a: integer): integer do n+a end '
    measured=0
    with tempfile.TemporaryDirectory(prefix='alchem-collection-memory-') as d:
        root=Path(d)
        for expression,expected in cases:
            # A value of open type takes it from the binding's annotation.
            source=('defmodule M do '+helpers+'def main() do value'+(expression if expression.startswith(':') else '='+expression)+'\nSystem.halt(0) end end').encode()
            r=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
            assert (r.returncode,r.stderr)==(0,b''),(expression,r.returncode,r.stderr)
            target=root/'out';target.write_bytes(r.stdout);target.chmod(0o700)
            try:
                status,data,errors,charged=profile(target,b'')
                assert (status,data,errors,charged)==(0,b'',b'',expected),(expression,status,errors,charged,expected)
                measured+=1
            except TraceUnavailable:print('SKIP collection arena measurement: ptrace unavailable')
        # The arena is reserved, not held: 16 GiB lazily, or the largest half of that the
        # system grants down to 4 MiB. A program is charged what it takes of it, the same
        # in either: a turn takes 65,568 bytes (the string of 65536 with its length 65544,
        # {a, b} 24; the literal "x" lies in the image and is charged nothing), 1000 turns
        # 65,568,000. An ordinary run held all of it and the floor exited 71 in the 64th
        # turn. No string stays in use past its turn, so both now run to the end
        # (spec/alchem-memory.md): the ordinary run collects each time 8 MiB were taken
        # and never has more than those and a window's megabyte charged, the floor
        # collects when its 4 MiB are full. keep, below, holds on to every string and
        # still exits 71 at the floor in its 64th turn.
        # fill's call to itself is its whole value: a jump, so the turns take no stack.
        fill='def fill(n: integer, total: integer): integer do if n == 0 do total else {a, b} = {String.duplicate("x",65536), n}\nfill(b-1,total+byte_size(a)) end end '
        source=('defmodule M do '+fill+'def main() do System.halt(rem(fill(1000,0),251)) end end').encode()
        r=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
        assert (r.returncode,r.stderr)==(0,b''),('fill',r.returncode,r.stderr)
        target=root/'fill';target.write_bytes(r.stdout);target.chmod(0o700)
        run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(65536000%251,b'',b''),('65 MB of strings',run)
        run=subprocess.run([str(target)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(target))
        assert (run.returncode,run.stdout,run.stderr)==(65536000%251,b'',b''),('65 MB of strings in 4 MiB',run)
        keep='def keep(n: integer, held: list[string]): integer do if n == 0 do Enum.count(held) else keep(n-1,[String.duplicate("x",65536) | held]) end end '
        source=('defmodule M do '+keep+'def main() do System.halt(rem(keep(1000,[]),251)) end end').encode()
        r=subprocess.run([str(compiler)],input=source,capture_output=True,env={'PATH':''},timeout=120)
        assert (r.returncode,r.stderr)==(0,b''),('keep',r.returncode,r.stderr)
        kept=root/'keep';kept.write_bytes(r.stdout);kept.chmod(0o700)
        run=subprocess.run([str(kept)],capture_output=True,env={'PATH':''},timeout=120)
        assert (run.returncode,run.stdout,run.stderr)==(1000%251,b'',b''),('65 MB of strings kept',run)
        run=subprocess.run([str(kept)],capture_output=True,env={'PATH':''},timeout=120,preexec_fn=floor_arena(kept))
        assert (run.returncode,run.stdout,run.stderr)==(71,b'',b''),('65 MB of strings kept in 4 MiB',run)
        reserved=0
        try:
            status,data,errors,charged=profile(target,b'')
            # What is charged where the program stops for the system (R12 there; it has left
            # the arena's start and is no longer the sum of all that was taken).
            assert (status,data,errors)==(65536000%251,b'',b'') and 0<charged<=10<<20,('charge with collections',status,charged)
            status,data,errors,charged=profile(target,b'',limit=floor_arena(target))
            assert (status,data,errors)==(65536000%251,b'',b'') and 0<charged<=4<<20,('charge at the floor',status,charged)
            status,data,errors,charged=profile(kept,b'',limit=floor_arena(kept))
            assert (status,data,errors)==(71,b'',b'') and charged<=4<<20,('charge of kept strings at the floor',status,charged)
            reserved=2
        except TraceUnavailable:print('SKIP arena reservation measurement: ptrace unavailable')
    print(f'Collection/library arena measurements: {measured}/{len(cases)}; reservation measurements: {reserved}/2')


if __name__=='__main__':verify(Path(sys.argv[1]).resolve())
