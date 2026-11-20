#!/usr/bin/env python3
"""Compare bounded six-argument recursion with a signed i64 Python oracle."""
import argparse
import json
from pathlib import Path
import random
import subprocess
import tempfile
from run import TARGET


def verify(compilers, count=64):
    rng = random.Random(0xB0A1D)
    mask = (1 << 64) - 1

    def signed(value):
        value &= mask
        return value - (1 << 64) if value >= 1 << 63 else value

    def constant(dest, value):
        return {"op": "const.i64", "dest": dest, "value": value}

    def binary(op, dest, lhs, rhs):
        return {"op": op, "dest": dest, "lhs": lhs, "rhs": rhs}

    def function(name, params, instructions, result):
        return {"name": name, "params": [{"name": p, "type": "i64"} for p in params], "return_type": "i64", "blocks": [{"label": "entry", "instructions": instructions, "terminator": {"op": "ret", "value": result}}]}

    with tempfile.TemporaryDirectory(prefix="alchem-recursive-differential-") as directory:
        root = Path(directory)
        for case in range(count):
            depth = [0, 1, 254, -1][case] if case < 4 else rng.randrange(180)
            args = [depth] + [rng.randrange(-(1 << 63), 1 << 63) for _ in range(5)]
            operation = rng.choice(["add.i64", "sub.i64", "mul.i64"])
            yes = {"instructions": [binary("add.i64", "base1", "acc", "left"), binary("sub.i64", "base2", "base1", "right"), binary("add.i64", "base", "base2", "bias")], "value": "base"}
            no = {"instructions": [binary("sub.i64", "next", "n", "one"), binary(operation, "updated", "acc", "step"), {"op": "call", "dest": "child", "callee": "walk", "args": ["next", "updated", "step", "left", "right", "bias"]}, binary("mul.i64", "live", "n", "acc"), binary("add.i64", "result", "child", "live")], "value": "result"}
            walk = function("walk", ["n", "acc", "step", "left", "right", "bias"], [constant("zero", 0), constant("one", 1), binary("le.i64", "done", "n", "zero"), {"op": "if.i64", "dest": "answer", "cond": "done", "then": yes, "else": no}], "answer")
            main = function("main", [], [constant(f"a{i}", v) for i, v in enumerate(args)] + [{"op": "call", "dest": "r", "callee": "walk", "args": [f"a{i}" for i in range(6)]}], "r")
            functions = [main, walk]
            rng.shuffle(functions)

            def oracle(n, acc, step, left, right, bias):
                if n <= 0:
                    return signed(acc + left - right + bias)
                updated = signed(acc + step if operation == "add.i64" else acc - step if operation == "sub.i64" else acc * step)
                return signed(oracle(n-1, updated, step, left, right, bias) + signed(n * acc))

            expected = oracle(*args) & 255
            source = root / "input.json"
            source.write_text(json.dumps({"version": 4, "functions": functions}))
            binaries = []
            for index, compiler in enumerate(compilers):
                output = root / f"program-{index}"
                compiled = subprocess.run([str(compiler), "--target", TARGET, "--input", str(source), "--output", str(output)], capture_output=True, timeout=120)
                assert compiled.returncode == 0, (case, compiled.stderr)
                result = subprocess.run([str(output)], capture_output=True, timeout=120)
                assert (result.returncode, result.stdout, result.stderr) == (expected, b"", b""), (case, index, result)
                binaries.append(output.read_bytes())
            assert binaries[0] == binaries[1], f"recursive case {case}: backend bytes differ"
    print(f"PASS {count} recursive differential programs: six arguments, live values, signed arithmetic and depth 256")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("go", type=Path)
    parser.add_argument("rust", type=Path)
    args = parser.parse_args()
    verify([args.go.resolve(), args.rust.resolve()])
