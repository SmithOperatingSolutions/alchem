#!/usr/bin/env python3
"""Record warm-cache native self-build process wall time and OS peak RSS."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time


def benchmark(compiler,source,samples,warmups):
    if samples<3 or warmups<0:raise ValueError('need at least3 samples and nonnegative warmups')
    text=source.read_bytes();expected=compiler.read_bytes();records=[]
    before=os.getloadavg()
    with tempfile.TemporaryFile() as input_file,tempfile.TemporaryFile() as output,tempfile.TemporaryFile() as errors:
        input_file.write(text)
        for i in range(warmups+samples):
            input_file.seek(0);output.seek(0);output.truncate();errors.seek(0);errors.truncate()
            start=time.perf_counter_ns()
            child=subprocess.Popen([str(compiler)],stdin=input_file,stdout=output,stderr=errors,env={'PATH':''})
            _,status,usage=os.wait4(child.pid,0);child.returncode=os.waitstatus_to_exitcode(status)
            elapsed=time.perf_counter_ns()-start
            output.seek(0);errors.seek(0)
            if child.returncode or errors.read() or output.read()!=expected:raise RuntimeError('self-build correctness/byte equality failed')
            if i>=warmups:records.append({'wall_ns':elapsed,'user_seconds':usage.ru_utime,'system_seconds':usage.ru_stime,'peak_rss_kib':usage.ru_maxrss})
    cpu='unknown'
    for line in Path('/proc/cpuinfo').read_text().splitlines():
        if line.startswith('model name'):cpu=line.split(':',1)[1].strip();break
    digest=lambda value:hashlib.sha256(value).hexdigest()
    return {'schema_version':1,'recorded_utc':datetime.now(timezone.utc).isoformat(),'kind':'native self-build process, warm OS input/code cache','includes':'Python launch/wait overhead, native process startup, stdin file reads, compilation and stdout file write; byte comparison outside timing','excludes':'bootstrap build and correctness suite; no Go/Rust performance comparison','source_bytes':len(text),'source_sha256':digest(text),'compiler_bytes':len(expected),'compiler_sha256':digest(expected),'warmups':warmups,'samples':records,'median_wall_ns':statistics.median(v['wall_ns'] for v in records),'min_wall_ns':min(v['wall_ns'] for v in records),'max_wall_ns':max(v['wall_ns'] for v in records),'peak_rss_unit':'Linux wait4 ru_maxrss KiB; process high-water mark, not arena charge','os':platform.system(),'kernel':platform.release(),'architecture':platform.machine(),'cpu_model':cpu,'visible_cpu_count':os.cpu_count(),'load_before':list(before),'load_after':list(os.getloadavg()),'child_environment':{'PATH':''}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler',type=Path,required=True);parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--samples',type=int,default=10);parser.add_argument('--warmups',type=int,default=2);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=benchmark(args.compiler.resolve(),args.source.resolve(),args.samples,args.warmups)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(f'Native self-build median {result["median_wall_ns"]/1e6:.2f}ms; {len(result["samples"])} verified samples')


if __name__=='__main__':main()
