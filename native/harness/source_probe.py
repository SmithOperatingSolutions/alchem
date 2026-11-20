#!/usr/bin/env python3
"""Verify a pure Alchem function -> IR -> Go/Rust native executable pipeline."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

from run import TARGET


def verify(adapter, compilers):
    cases = [("Enum.at([0,42,255], -2, 7)",42), ("Enum.count([0,42,255])",3), ("42", 42), ("20 + 22", 42), ("(1 + 19) + 22", 42), ("-1", 255),
             ("9223372036854775807 + 1", 0), ("-9223372036854775808", 0), ("84 - 42", 42), ("42 - 84", 214),
             ("6 * 7", 42), ("-6 * 7", 214), ("(100 - 16) * 2 - 126", 42),
             ("9223372036854775807 * 2", 254),
             ("if 1 < 2 do 42 else 7 end", 42),
             ("if 2 < 1 do 42 else 7 end", 7),
             ("defmodule Native do def count(n: integer): integer do if n <= 0 do 42 else count(n-1) end end def answer(): integer do count(10) end end", 42),
             ("defmodule Native do def increment(x: integer): integer do x + 1 end def answer(): integer do increment(41) end end", 42)]
    with tempfile.TemporaryDirectory(prefix="alchem-source-probe-") as directory:
        root = Path(directory)
        for expression, expected in cases:
            source = root / "probe.alc"
            source.write_text(expression if expression.startswith("defmodule") else f"defmodule Native do\n def answer(): integer do\n  {expression}\n end\nend\n")
            command = [str(adapter), "--input", str(source), "--function", "answer"]
            result = subprocess.run(command, capture_output=True, timeout=120)
            assert result.returncode == 0, result.stderr
            repeated = subprocess.run(command, capture_output=True, timeout=120)
            assert repeated.returncode == 0 and repeated.stdout == result.stdout, "nondeterministic source lowering"
            ir = root / "probe.json"
            ir.write_bytes(result.stdout)
            binaries = []
            for index, compiler in enumerate(compilers):
                output = root / f"program-{index}"
                compiled = subprocess.run([str(compiler), "--target", TARGET, "--input", str(ir), "--output", str(output)], capture_output=True, timeout=120)
                assert compiled.returncode == 0, compiled.stderr
                assert os.access(output, os.X_OK), "backend output is not executable"
                executed = subprocess.run([str(output)], capture_output=True, timeout=120)
                assert (executed.returncode, executed.stdout, executed.stderr) == (expected, b"", b""), (expression, executed)
                binaries.append(output.read_bytes())
            assert binaries[0] == binaries[1], "source probe backend bytes differ"
    print(f"PASS {len(cases)} pinned-frontend source probes through Go and Rust")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adapter", type=Path)
    parser.add_argument("go", type=Path)
    parser.add_argument("rust", type=Path)
    args = parser.parse_args()
    verify(args.adapter.resolve(), [args.go.resolve(), args.rust.resolve()])
