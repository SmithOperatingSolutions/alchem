#!/usr/bin/env python3
"""Exercise V4 counter restoration and stack guards with generated frames."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from run import TARGET

MESSAGE = b"E_RUNTIME_LIMIT: native call/stack budget exceeded\n"


def verify(compilers):
    def function(name, params, instructions, result):
        return {"name": name, "params": [{"name": p, "type": "i64"} for p in params], "return_type": "i64", "blocks": [{"label": "entry", "instructions": instructions, "terminator": {"op": "ret", "value": result}}]}

    def call(dest, callee, args):
        return {"op": "call", "dest": dest, "callee": callee, "args": args}

    constants = [{"op": "const.i64", "dest": f"v{i}", "value": i} for i in range(4096)]
    # This finite chain stays below the depth cap. Without the byte guard it
    # would return 42, so a depth failure cannot mask a broken stack guard.
    large_recursive = function("large", ["x", "n"], constants + [
        {"op":"le.i64","dest":"done","lhs":"n","rhs":"v0"},
        {"op":"if.i64","dest":"result","cond":"done","then":{"instructions":[],"value":"x"},
         "else":{"instructions":[{"op":"sub.i64","dest":"next","lhs":"n","rhs":"v1"},call("child","large",["x","next"])],"value":"child"}},
    ], "result")
    large_return = function("large", ["x"], constants, "x")
    argument = {"op": "const.i64", "dest": "arg", "value": 42}
    cases = [
        ("stack-budget", [function("main", [], [argument, {"op":"const.i64","dest":"depth","value":40}, call("result", "large", ["arg","depth"])], "result"), large_recursive], 70, MESSAGE),
        ("stack-restoration", [function("main", [], [argument] + [call(f"r{i}", "large", ["arg"]) for i in range(40)], "r39"), large_return], 42, b""),
        ("depth-restoration", [function("main", [], [argument] + [call(f"r{i}", "identity", ["arg"]) for i in range(300)], "r299"), function("identity", ["x"], [], "x")], 42, b""),
    ]
    with tempfile.TemporaryDirectory(prefix="alchem-runtime-") as directory:
        root = Path(directory)
        for name, functions, expected, diagnostic in cases:
            source = root / "program.json"
            source.write_text(json.dumps({"version": 4, "functions": functions}))
            binaries = []
            for index, compiler in enumerate(compilers):
                output = root / f"program-{index}"
                result = subprocess.run([str(compiler), "--target", TARGET, "--input", str(source), "--output", str(output)], capture_output=True, timeout=120)
                assert result.returncode == 0, (name, result.stderr)
                executed = subprocess.run([str(output)], capture_output=True, timeout=120)
                assert (executed.returncode, executed.stdout, executed.stderr) == (expected, b"", diagnostic), (name, index, executed)
                binaries.append(output.read_bytes())
            assert binaries[0] == binaries[1], f"{name}: backend bytes differ"
    print("PASS 3 runtime-budget programs: stack limit, frame restoration, 300 shallow calls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("go", type=Path)
    parser.add_argument("rust", type=Path)
    args = parser.parse_args()
    verify([args.go.resolve(), args.rust.resolve()])
