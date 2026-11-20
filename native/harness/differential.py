#!/usr/bin/env python3
"""Compare Go/Rust ELF output and execution against seeded i64 arithmetic."""
import argparse
import json
import operator
from pathlib import Path
import random
import subprocess
import tempfile

from run import TARGET


def verify(compilers, count=64):
    rng = random.Random(0xA1C4E)
    edges = [0, 1, -1, -(1 << 63), (1 << 63) - 1]
    with tempfile.TemporaryDirectory(prefix="alchem-differential-") as directory:
        root = Path(directory)
        for case in range(count):
            instructions = []
            values = []
            for i in range(12):
                dest = f"v{i}"
                if i < 2 or rng.randrange(3) == 0:
                    value = rng.choice(edges) if case < 16 else rng.randrange(-(1 << 63), 1 << 63)
                    instructions.append({"op": "const.i64", "dest": dest, "value": value})
                else:
                    lhs, rhs = rng.randrange(i), rng.randrange(i)
                    op = rng.choice(["add.i64", "sub.i64", "mul.i64"])
                    operation = {"add.i64": operator.add, "sub.i64": operator.sub, "mul.i64": operator.mul}[op]
                    value = operation(values[lhs], values[rhs]) & ((1 << 64) - 1)
                    instructions.append({"op": op, "dest": dest, "lhs": f"v{lhs}", "rhs": f"v{rhs}"})
                values.append(value)
            program = {"version": 1, "functions": [{"name": "main", "params": [], "return_type": "i64", "blocks": [{"label": "entry", "instructions": instructions, "terminator": {"op": "ret", "value": "v11"}}]}]}
            source = root / "input.json"
            source.write_text(json.dumps(program))
            binaries = []
            for index, compiler in enumerate(compilers):
                output = root / f"program-{index}"
                result = subprocess.run([str(compiler), "--target", TARGET, "--input", str(source), "--output", str(output)], capture_output=True, timeout=120)
                assert result.returncode == 0, f"case {case}: compiler {index}: {result.stderr!r}"
                executed = subprocess.run([str(output)], capture_output=True, timeout=120)
                assert (executed.returncode, executed.stdout, executed.stderr) == (values[-1] & 255, b"", b""), f"case {case}: incorrect arithmetic from compiler {index}"
                binaries.append(output.read_bytes())
            assert binaries[0] == binaries[1], f"case {case}: Go/Rust executable bytes differ"
    print(f"PASS {count} seeded differential programs: byte-identical ELF and oracle exit results")


def verify_calls(compilers, count=64):
    rng = random.Random(0xCA115)
    mask = (1 << 64) - 1
    operations = {"add.i64": operator.add, "sub.i64": operator.sub, "mul.i64": operator.mul}
    with tempfile.TemporaryDirectory(prefix="alchem-call-differential-") as directory:
        root = Path(directory)
        for case in range(count):
            arities = [rng.randrange(7) for _ in range(4)]
            functions = []
            for index, arity in enumerate(arities):
                names = [f"p{i}" for i in range(arity)]
                instructions = [{"op": "const.i64", "dest": "v0", "value": rng.randrange(-(1 << 63), 1 << 63)}]
                names.append("v0")
                for i in range(1, 10):
                    dest = f"v{i}"
                    if i in (2, 6) and index < 3:
                        instruction = {"op": "call", "dest": dest, "callee": f"f{index+1}", "args": [rng.choice(names) for _ in range(arities[index+1])]}
                    else:
                        instruction = {"op": rng.choice(list(operations)), "dest": dest, "lhs": rng.choice(names), "rhs": rng.choice(names)}
                    instructions.append(instruction)
                    names.append(dest)
                functions.append({"name": f"f{index}", "params": [{"name": f"p{i}", "type": "i64"} for i in range(arity)], "return_type": "i64", "blocks": [{"label": "entry", "instructions": instructions, "terminator": {"op": "ret", "value": "v9"}}]})
            arguments = [{"op": "const.i64", "dest": f"a{i}", "value": rng.randrange(-(1 << 63), 1 << 63)} for i in range(6)]
            main = {"name": "main", "params": [], "return_type": "i64", "blocks": [{"label": "entry", "instructions": arguments + [{"op": "call", "dest": "r", "callee": "f0", "args": [f"a{i}" for i in range(arities[0])]}, {"op": "add.i64", "dest": "result", "lhs": "r", "rhs": "a0"}], "terminator": {"op": "ret", "value": "result"}}]}
            functions.append(main)
            rng.shuffle(functions)
            table = {f["name"]: f for f in functions}

            def evaluate(name, args):
                function = table[name]
                values = {parameter["name"]: value for parameter, value in zip(function["params"], args)}
                block = function["blocks"][0]
                for instruction in block["instructions"]:
                    op = instruction["op"]
                    if op == "const.i64":
                        value = instruction["value"]
                    elif op == "call":
                        value = evaluate(instruction["callee"], [values[arg] for arg in instruction["args"]])
                    else:
                        value = operations[op](values[instruction["lhs"]], values[instruction["rhs"]])
                    values[instruction["dest"]] = value & mask
                return values[block["terminator"]["value"]]

            expected = evaluate("main", []) & 255
            source = root / "input.json"
            source.write_text(json.dumps({"version": 2, "functions": functions}))
            binaries = []
            for index, compiler in enumerate(compilers):
                output = root / f"program-{index}"
                compiled = subprocess.run([str(compiler), "--target", TARGET, "--input", str(source), "--output", str(output)], capture_output=True, timeout=120)
                assert compiled.returncode == 0, f"call case {case}: {compiled.stderr!r}"
                result = subprocess.run([str(output)], capture_output=True, timeout=120)
                assert (result.returncode, result.stdout, result.stderr) == (expected, b"", b""), f"call case {case}: backend {index} differs from oracle"
                binaries.append(output.read_bytes())
            assert binaries[0] == binaries[1], f"call case {case}: Go/Rust bytes differ"
    print(f"PASS {count} seeded call programs: 0-6 arguments, shuffled symbols, nested calls and live values")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("go", type=Path)
    parser.add_argument("rust", type=Path)
    args = parser.parse_args()
    compilers = [args.go.resolve(), args.rust.resolve()]
    verify(compilers)
    verify_calls(compilers)
