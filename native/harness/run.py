#!/usr/bin/env python3
"""Shared black-box compiler acceptance runner (Python standard library only).

Compiler contract:
  <compiler> --target x86_64-unknown-linux-gnu --input FILE --output FILE
Success: exit 0 and produce an ELF executable.
Failure: nonzero exit and diagnostic containing E_* code on stderr.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
# How an ARM64 program is run: directly on an ARM64 host, else under QEMU's
# user mode from scripts/fetch-arm64-tools.sh.
ARM64_RUN = [] if os.uname().machine == 'aarch64' else [str(ROOT / 'build/arm64-tools/bin/qemu-aarch64-static')]
# The native compiler took 65,535 functions and no more (it takes more now:
# harness/past_limit.py). A program that large compiles in about twenty
# seconds and three gigabytes, and several gates hold one, so at most three
# such compiles run at a time across all gate processes.
FUNCTION_LIMIT = 65535


def at_limit(command, **options):
    """subprocess.run for a compile at the function limit, in one of three slots."""
    import fcntl, time
    while True:
        for slot in range(3):
            handle = open(Path(tempfile.gettempdir()) / f"alchem-function-limit-{os.getuid()}-{slot}.lock", "w")
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                handle.close()
                continue
            try:
                return subprocess.run(command, **options)
            finally:
                handle.close()
        time.sleep(0.2)
TARGET = "x86_64-unknown-linux-gnu"
ELF_MAGIC = b"\x7fELF"


def load_manifest(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or data.get("target") != TARGET:
        raise ValueError("unsupported fixture manifest version or target")
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("manifest must contain cases")
    ids = set()
    for case in cases:
        name = case["id"]
        if name in ids:
            raise ValueError(f"duplicate case id: {name}")
        ids.add(name)
        source = ROOT / case["source"]
        if not source.is_file() or not source.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError(f"missing or unsafe fixture: {source}")
        json.loads(source.read_text(encoding="utf-8"))
        if ("expect" in case) == ("expect_compile_error" in case):
            raise ValueError(f"case {name} needs exactly one expectation")
    return cases


def run_case(case, compiler, timeout):
    with tempfile.TemporaryDirectory(prefix="alchem-native-") as directory:
        binary = Path(directory) / "program"
        source = ROOT / case["source"]
        command = [str(compiler), "--target", TARGET, "--input", str(source), "--output", str(binary)]
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        if "expect_compile_error" in case:
            code = case["expect_compile_error"]
            assert result.returncode != 0, f"expected compiler rejection {code}"
            assert code in result.stderr, f"missing diagnostic {code}: {result.stderr!r}"
            assert not binary.exists(), "invalid IR emitted an executable"
            return
        assert result.returncode == 0, f"compiler failed: {result.stderr}"
        assert binary.is_file(), "compiler did not emit executable"
        assert binary.read_bytes()[:4] == ELF_MAGIC, "output is not ELF"
        assert os.access(binary, os.X_OK), "output is not executable"
        repeated = Path(directory) / "program-repeat"
        repeat_command = command[:-1] + [str(repeated)]
        repeated_result = subprocess.run(repeat_command, capture_output=True, text=True, timeout=timeout, check=False)
        assert repeated_result.returncode == 0, f"repeat compilation failed: {repeated_result.stderr}"
        assert repeated.is_file(), "repeat compilation did not emit executable"
        assert os.access(repeated, os.X_OK), "repeat output is not executable"
        assert binary.read_bytes() == repeated.read_bytes(), "output is not deterministic"
        executed = subprocess.run([str(binary)], capture_output=True, text=True, timeout=timeout, check=False)
        expected = case["expect"]
        for field, actual in (("exit_code", executed.returncode), ("stdout", executed.stdout), ("stderr", executed.stderr)):
            assert actual == expected[field], f"{field}: expected {expected[field]!r}, got {actual!r}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compiler", type=Path, required=True, help="absolute path to a Go or Rust backend binary")
    parser.add_argument("--manifest", type=Path, default=ROOT / "fixtures/manifest.json")
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    if sys.platform != "linux":
        parser.error("execution harness currently requires Linux")
    if not args.compiler.is_file():
        parser.error(f"compiler not found: {args.compiler}")
    cases = load_manifest(args.manifest)
    failures = 0
    for case in cases:
        try:
            run_case(case, args.compiler.resolve(), args.timeout)
            print(f"PASS {case['id']}")
        except (AssertionError, OSError, subprocess.TimeoutExpired) as error:
            failures += 1
            print(f"FAIL {case['id']}: {error}", file=sys.stderr)
    print(f"{len(cases)-failures}/{len(cases)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
