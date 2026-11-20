#!/usr/bin/env python3
"""Check exact static byte budgets and rejected-output preservation."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from bytes_differential import function, constant
from run import TARGET


def verify(compilers):
    maximum=1<<20
    with tempfile.TemporaryDirectory(prefix="alchem-byte-limits-") as directory:
        root=Path(directory)
        # Version 11, which builds the compiler, holds 16 MiB of byte data.
        for name,lengths,error,version in [
            ("literal-boundary",[maximum],False,5),
            ("literal-overflow",[maximum+1],True,5),
            ("total-boundary",[maximum]*3+[maximum-32],False,5),
            ("total-overflow",[maximum]*3+[maximum-31],True,5),
            ("v10-total-overflow",[maximum]*3+[maximum-31],True,10),
            ("v11-literal-overflow",[maximum+1],True,11),
            ("v11-total-boundary",[maximum]*15+[maximum-128],False,11),
            ("v11-total-overflow",[maximum]*15+[maximum-127],True,11),
        ]:
            ops=[{"op":"bytes.const","dest":f"b{i}","values":[0]*(length-1)+[42]} for i,length in enumerate(lengths)]
            ops += [constant("last",-1),constant("fallback",7),{"op":"bytes.get","dest":"r","buffer":f"b{len(lengths)-1}","index":"last","default":"fallback"}]
            source=root/"program.json";source.write_text(json.dumps({"version":version,**({"arena_bytes":64<<20} if version==11 else {}),"functions":[function("main",[],ops,"r")]}))
            binaries=[]
            for index,compiler in enumerate(compilers):
                output=root/f"program-{index}";output.write_bytes(b"existing output")
                result=subprocess.run([str(compiler),"--target",TARGET,"--input",str(source),"--output",str(output)],capture_output=True,timeout=120)
                if error:
                    assert result.returncode!=0 and b"E_UNSUPPORTED" in result.stderr,(name,index,result)
                    assert output.read_bytes()==b"existing output",name
                else:
                    assert result.returncode==0,(name,index,result.stderr)
                    executed=subprocess.run([str(output)],capture_output=True,timeout=120)
                    assert (executed.returncode,executed.stdout,executed.stderr)==(42,b"",b""),(name,index,executed)
                    binaries.append(output.read_bytes())
            if not error: assert binaries[0]==binaries[1],name
    print("PASS 8 byte-storage budget programs: exact 1 MiB literal / 4 MiB total (16 MiB in IR V11) boundaries and preservation")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("go",type=Path);parser.add_argument("rust",type=Path)
    args=parser.parse_args();verify([args.go.resolve(),args.rust.resolve()])
