#!/usr/bin/env python3
"""Alternate two native compilers on identical source and verify every ELF."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'harness'))
from native_memory import profile,TraceUnavailable


def benchmark(before,after,source,samples=10,warmups=2,before_commit=None,arena_bytes=None):
    if samples<3 or warmups<0:raise ValueError('need at least3 pairs and nonnegative warmups')
    text=source.read_bytes();expected=after.read_bytes();compilers={'before':before,'after':after};records=[]
    load_before=list(os.getloadavg())
    with tempfile.TemporaryFile() as input_file,tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as errors:
        input_file.write(text)
        for pair in range(warmups+samples):
            order=['before','after'] if pair%2==0 else ['after','before'];record={}
            for name in order:
                input_file.seek(0);output.seek(0);output.truncate();errors.seek(0);errors.truncate()
                start=time.perf_counter_ns()
                child=subprocess.Popen([str(compilers[name])],stdin=input_file,stdout=output,stderr=errors,env={'PATH':''})
                _,status,usage=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status)
                elapsed=time.perf_counter_ns()-start;output.seek(0);errors.seek(0)
                if child.returncode or errors.read() or output.read()!=expected:raise RuntimeError(f'{name}: compilation/equality failed')
                record[name]={'wall_ns':elapsed,'peak_rss_kib':usage.ru_maxrss}
            if pair>=warmups:records.append({'order':order,**record})
    arena={}
    for name,path in compilers.items():
        if arena_bytes is None:arena[name]=None;continue
        try:
            status,data,errors,charge=profile(path,text,arena_bytes[name])
            if (status,data,errors)!=(0,expected,b''):raise RuntimeError('traced compilation/equality failed')
            arena[name]=charge
        except TraceUnavailable:arena[name]=None
    digest=lambda data:hashlib.sha256(data).hexdigest()
    return {'schema_version':1,'kind':'alternating native compiler processes on identical source and expected ELF','recorded_utc':datetime.now(timezone.utc).isoformat(),'source_bytes':len(text),'source_sha256':digest(text),'expected_elf_sha256':digest(expected),'before_commit':before_commit,'compiler_sha256':{name:digest(path.read_bytes()) for name,path in compilers.items()},'warmup_pairs':warmups,'pairs':records,'median_wall_ns':{name:statistics.median(row[name]['wall_ns'] for row in records) for name in compilers},'traced_arena_bytes':arena,'arena_budget_bytes':arena_bytes,'tracing':'after timing, only with explicit budgets; not included in wall samples','includes':'Python launch/wait, native startup, stdin read, compile and stdout write; equality comparison outside timing','rss_unit':'Linux wait4 KiB high-water mark, not traced arena charge','cpu_model':next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),'unknown'),'visible_cpu_count':os.cpu_count(),'os':platform.system(),'kernel':platform.release(),'machine':platform.machine(),'load_before':load_before,'load_after':list(os.getloadavg()),'limits':'single shared cloud session; alternating order but no CPU isolation; no Go/Rust comparison','child_environment':{'PATH':''}}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--samples',type=int,default=10);p.add_argument('--warmups',type=int,default=2);p.add_argument('--before-commit');p.add_argument('--before-arena-mib',type=int);p.add_argument('--after-arena-mib',type=int)
    args=p.parse_args()
    if (args.before_arena_mib is None)!=(args.after_arena_mib is None):p.error('provide both arena budgets or neither')
    if args.before_arena_mib is not None and not all(1<=v<=64 for v in [args.before_arena_mib,args.after_arena_mib]):p.error('arena budgets must be 1..64MiB')
    budgets=None if args.before_arena_mib is None else {'before':args.before_arena_mib<<20,'after':args.after_arena_mib<<20}
    result=benchmark(args.before.resolve(),args.after.resolve(),args.source.resolve(),args.samples,args.warmups,args.before_commit,budgets)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('Paired medians ms:',{name:round(value/1e6,3) for name,value in result['median_wall_ns'].items()},'arena bytes:',result['traced_arena_bytes'])


if __name__=='__main__':main()
