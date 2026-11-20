#!/usr/bin/env python3
"""Check signed comparisons, nested branches and calls against Python values."""
import argparse
import json
import operator
from pathlib import Path
import random
import subprocess
import tempfile
from run import TARGET


def verify(compilers, count=64):
    rng = random.Random(0xB12A)
    comparisons = {"eq.i64": operator.eq, "ne.i64": operator.ne, "lt.i64": operator.lt, "le.i64": operator.le, "gt.i64": operator.gt, "ge.i64": operator.ge}
    arithmetic = {"add.i64": operator.add, "sub.i64": operator.sub, "mul.i64": operator.mul}
    mask = (1 << 64) - 1

    def signed(value):
        value &= mask
        return value - (1 << 64) if value >= 1 << 63 else value

    with tempfile.TemporaryDirectory(prefix="alchem-flow-differential-") as directory:
        root = Path(directory)
        for case in range(count):
            counter = 0

            def name():
                nonlocal counter
                counter += 1
                return f"v{counter}"

            def branch(depth):
                constant, called = name(), name()
                instructions = [{"op": "const.i64", "dest": constant, "value": rng.randrange(-(1 << 63), 1 << 63)}, {"op": "call", "dest": called, "callee": "increment", "args": [rng.choice(["x", "y", constant])]}]
                if depth:
                    condition, result = name(), name()
                    instructions.append({"op": rng.choice(list(comparisons)), "dest": condition, "lhs": called, "rhs": constant})
                    instructions.append({"op": "if.i64", "dest": result, "cond": condition, "then": branch(depth-1), "else": branch(depth-1)})
                else:
                    result = name()
                    instructions.append({"op": rng.choice(list(arithmetic)), "dest": result, "lhs": called, "rhs": constant})
                return {"instructions": instructions, "value": result}

            def function(name, params, instructions, result):
                return {"name": name, "params": [{"name": p, "type": "i64"} for p in params], "return_type": "i64", "blocks": [{"label": "entry", "instructions": instructions, "terminator": {"op": "ret", "value": result}}]}

            condition, yes, no, flag, selected = [name() for _ in range(5)]
            choose = [{"op": list(comparisons)[case % 6], "dest": condition, "lhs": "x", "rhs": "y"}, {"op": "if.bool", "dest": flag, "cond": condition, "then": {"instructions": [{"op": "const.bool", "dest": yes, "value": bool(case % 2)}], "value": yes}, "else": {"instructions": [{"op": "const.bool", "dest": no, "value": not bool(case % 2)}], "value": no}}]
            negated = name()
            choose.append({"op": "not.bool", "dest": negated, "value": flag})
            choose.append({"op": "if.i64", "dest": selected, "cond": negated, "then": branch(2), "else": branch(2)})
            edges = [-(1 << 63), (1 << 63)-1, -1, 0, 1]
            a, b = (rng.choice(edges), rng.choice(edges)) if case < 20 else (rng.randrange(-(1 << 63), 1 << 63), rng.randrange(-(1 << 63), 1 << 63))
            functions = [function("increment", ["x"], [{"op": "const.i64", "dest": "one", "value": 1}, {"op": "add.i64", "dest": "result", "lhs": "x", "rhs": "one"}], "result"), function("choose", ["x", "y"], choose, selected), function("main", [], [{"op": "const.i64", "dest": "a", "value": a}, {"op": "const.i64", "dest": "b", "value": b}, {"op": "call", "dest": "result", "callee": "choose", "args": ["a", "b"]}], "result")]
            rng.shuffle(functions)
            table = {f["name"]: f for f in functions}

            def evaluate_instructions(instructions, values):
                for instruction in instructions:
                    op = instruction["op"]
                    if op.startswith("const."):
                        value = instruction["value"]
                    elif op in arithmetic:
                        value = signed(arithmetic[op](values[instruction["lhs"]], values[instruction["rhs"]]))
                    elif op in comparisons:
                        value = comparisons[op](values[instruction["lhs"]], values[instruction["rhs"]])
                    elif op == "not.bool":
                        value = not values[instruction["value"]]
                    elif op == "call":
                        value = call(instruction["callee"], [values[arg] for arg in instruction["args"]])
                    else:
                        selected_branch = instruction["then"] if values[instruction["cond"]] else instruction["else"]
                        local = dict(values)
                        evaluate_instructions(selected_branch["instructions"], local)
                        value = local[selected_branch["value"]]
                    values[instruction["dest"]] = value

            def call(name, args):
                f = table[name]
                values = {p["name"]: value for p, value in zip(f["params"], args)}
                block = f["blocks"][0]
                evaluate_instructions(block["instructions"], values)
                return values[block["terminator"]["value"]]

            expected = call("main", []) & 255
            source = root / "input.json"
            source.write_text(json.dumps({"version": 3, "functions": functions}))
            binaries = []
            for index, compiler in enumerate(compilers):
                output = root / f"program-{index}"
                compiled = subprocess.run([str(compiler), "--target", TARGET, "--input", str(source), "--output", str(output)], capture_output=True, timeout=120)
                assert compiled.returncode == 0, f"flow case {case}: {compiled.stderr!r}"
                result = subprocess.run([str(output)], capture_output=True, timeout=120)
                assert (result.returncode, result.stdout, result.stderr) == (expected, b"", b""), f"flow case {case}: backend {index} disagrees with signed oracle"
                binaries.append(output.read_bytes())
            assert binaries[0] == binaries[1], f"flow case {case}: backend bytes differ"
    print(f"PASS {count} seeded typed-flow programs: signed comparisons, boolean merges, nested branches and calls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("go", type=Path)
    parser.add_argument("rust", type=Path)
    args = parser.parse_args()
    verify([args.go.resolve(), args.rust.resolve()])
