#!/usr/bin/env python3
"""Exercise packed byte data, branch lifetimes and mixed recursive arguments."""
import argparse
import json
from pathlib import Path
import random
import subprocess
import tempfile
from run import TARGET


def function(name, params, ops, result):
    return {"name":name,"params":[{"name":n,"type":t} for n,t in params],"return_type":"i64","blocks":[{"label":"entry","instructions":ops,"terminator":{"op":"ret","value":result}}]}


def constant(dest, value):
    return {"op":"const.i64","dest":dest,"value":value}


def binary(op, dest, lhs, rhs):
    return {"op":op,"dest":dest,"lhs":lhs,"rhs":rhs}


def verify(compilers, count=64):
    rng = random.Random(0xB17E5)
    mask = (1 << 64)-1
    with tempfile.TemporaryDirectory(prefix="alchem-bytes-") as directory:
        root=Path(directory)
        for case in range(count):
            length = [0,1,120][case] if case<3 else rng.randrange(120)
            data=[rng.randrange(256) for _ in range(length)]
            alt=[rng.randrange(256) for _ in range(rng.randrange(1,120))]
            fallback=rng.choice([-1,42,-(1<<63),(1<<63)-1])
            acc=rng.randrange(-(1<<63),1<<63)
            yes={"instructions":[],"value":"acc"}
            no={"instructions":[
                binary("sub.i64","negative","zero","n"),binary("sub.i64","from_end","negative","one"),
                {"op":"bytes.get","dest":"a","buffer":"b","index":"n","default":"fallback"},
                {"op":"bytes.get","dest":"z","buffer":"alt","index":"from_end","default":"fallback"},
                binary("add.i64","step","acc","a"),binary("sub.i64","next","n","one"),
                {"op":"call","dest":"child","callee":"walk","args":["b","next","step","alt","one","fallback"]},
                {"op":"bytes.len","dest":"live_len","value":"b"},
                binary("add.i64","partial","child","z"),binary("add.i64","result","partial","live_len"),
            ],"value":"result"}
            walk=function("walk",[("b","bytes"),("n","i64"),("acc","i64"),("alt","bytes"),("one","i64"),("fallback","i64")],[constant("zero",0),binary("lt.i64","done","n","zero"),{"op":"if.i64","dest":"answer","cond":"done","then":yes,"else":no}],"answer")
            main=function("main",[],[
                {"op":"const.bool","dest":"flag","value":case%2==0},
                {"op":"if.bytes","dest":"b","cond":"flag","then":{"instructions":[{"op":"bytes.const","dest":"yes","values":data}],"value":"yes"},"else":{"instructions":[{"op":"bytes.const","dest":"no","values":list(reversed(data))}],"value":"no"}},
                {"op":"bytes.const","dest":"alt","values":alt},constant("n",length-1),constant("acc",acc),constant("one",1),constant("fallback",fallback),
                {"op":"call","dest":"r","callee":"walk","args":["b","n","acc","alt","one","fallback"]},
            ],"r")
            if case%2: data.reverse()
            expected=acc
            for n in range(length):
                index=-n-1
                other=alt[index] if -len(alt)<=index<0 else fallback
                expected=(expected+data[n]+other+length)&mask
            functions=[main,walk];rng.shuffle(functions)
            source=root/"program.json";source.write_text(json.dumps({"version":5,"functions":functions}))
            binaries=[]
            for index,compiler in enumerate(compilers):
                output=root/f"program-{index}"
                result=subprocess.run([str(compiler),"--target",TARGET,"--input",str(source),"--output",str(output)],capture_output=True,timeout=120)
                assert result.returncode==0,(case,result.stderr)
                executed=subprocess.run([str(output)],capture_output=True,timeout=120)
                assert (executed.returncode,executed.stdout,executed.stderr)==(expected&255,b"",b""),(case,index,expected,executed)
                binaries.append(output.read_bytes())
            assert binaries[0]==binaries[1],f"byte case {case}: backend bytes differ"
    print(f"PASS {count} byte-buffer differential programs: mixed six-argument recursion, branch data and live references")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("go",type=Path);parser.add_argument("rust",type=Path)
    args=parser.parse_args();verify([args.go.resolve(),args.rust.resolve()])
