#!/usr/bin/env python3
"""Bounded local smoke measurements; not a language-performance comparison."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
TARGET = "x86_64-unknown-linux-gnu"


def invoke(command, expected=0):
    start = time.perf_counter_ns()
    result = subprocess.run(command, capture_output=True, timeout=30)
    elapsed = (time.perf_counter_ns() - start) / 1_000_000
    if (result.returncode, result.stdout, result.stderr) != (expected, b"", b""):
        raise RuntimeError(f"unexpected process result: {command}: {result}")
    return elapsed


def distribution(samples):
    return {"median_ms": statistics.median(samples), "min_ms": min(samples), "max_ms": max(samples), "samples_ms": samples}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", type=Path, required=True)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=20)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    compilers = {"go": args.go.resolve(), "rust": args.rust.resolve()}
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("model name")), "unknown")
    results = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "benchmark_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rss_helper_sha256": hashlib.sha256((ROOT / "scripts/measure-rss.c").read_bytes()).hexdigest(),
        "platform": platform.platform(), "cpu": cpu, "python": platform.python_version(),
        "runs": args.runs, "warmups": 2,
        "builds": {"go": "Go default optimized build, -trimpath", "rust": "cargo build --release --locked --offline"},
        "method": "Sequential wall time includes process launch, JSON parse, codegen and output I/O. Runtime includes process launch. RSS measured separately with a small C fork/exec/wait4 helper (KiB), avoiding inherited Python high-water RSS. No CPU pinning or host-load isolation.",
        "toolchains": {name: subprocess.check_output(command, text=True).strip() for name, command in {"go": ["go", "version"], "rust": ["rustc", "--version"], "cargo": ["cargo", "--version"]}.items()},
        "compiler_sha256": {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in compilers.items()},
        "results": [],
    }
    with tempfile.TemporaryDirectory(prefix="alchem-benchmark-") as directory:
        root = Path(directory)
        rss_helper = root / "measure-rss"
        subprocess.run(["cc", "-O2", "-Wall", "-Wextra", "-Werror", str(ROOT / "scripts/measure-rss.c"), "-o", str(rss_helper)], check=True, timeout=30)
        large = json.loads((ROOT / "fixtures/ir/return-42.json").read_text())
        block = large["functions"][0]["blocks"][0]
        block["instructions"] = [{"op": "const.i64", "dest": "v0", "value": 1}] + [{"op": "add.i64", "dest": f"v{i}", "lhs": f"v{i-1}", "rhs": "v0"} for i in range(1, 4096)]
        block["terminator"]["value"] = "v4095"
        generated = root / "4096-values.json"
        generated.write_text(json.dumps(large))
        for fixture, expected in [(ROOT / "fixtures/ir/add-20-22.json", 42), (generated, 0)]:
            reference = None
            for backend, compiler in compilers.items():
                binary = root / f"{backend}-program"
                command = [str(compiler), "--target", TARGET, "--input", str(fixture), "--output", str(binary)]
                for _ in range(2):
                    invoke(command)
                    invoke([str(binary)], expected)
                compile_samples = [invoke(command) for _ in range(args.runs)]
                runtime_samples = [invoke([str(binary)], expected) for _ in range(args.runs)]
                rss_samples = []
                for _ in range(5):
                    measured = subprocess.run([str(rss_helper)] + command, capture_output=True, text=True, check=True, timeout=30)
                    rss_samples.append(int(measured.stdout))
                emitted = binary.read_bytes()
                if reference is not None and reference != emitted:
                    raise RuntimeError("Go/Rust output differs")
                reference = emitted
                results["results"].append({"fixture": fixture.name, "backend": backend,
                    "input_bytes": fixture.stat().st_size, "compiler_bytes": compiler.stat().st_size,
                    "executable_bytes": len(emitted), "executable_sha256": hashlib.sha256(emitted).hexdigest(),
                    "compile": distribution(compile_samples), "runtime_with_launch": distribution(runtime_samples),
                    "compile_peak_rss_kib": rss_samples})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(f"Recorded {len(results['results'])} measurements in {args.output}")


if __name__ == "__main__":
    main()
