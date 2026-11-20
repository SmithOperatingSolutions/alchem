"""Regression tests for the shared runner's compiler-output checks."""
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from run import run_case


CASE = {
    "source": "fixtures/ir/return-42.json",
    "expect": {"exit_code": 42, "stdout": "", "stderr": ""},
}


class AcceptanceTests(unittest.TestCase):
    def compiler(self, *, executable=True, deterministic=True):
        compilations = []

        def invoke(command, **kwargs):
            if "--output" in command:
                binary = Path(command[command.index("--output") + 1])
                compilations.append(binary)
                suffix = b"" if deterministic else bytes([len(compilations)])
                binary.write_bytes(b"\x7fELF" + suffix)
                binary.chmod(0o700 if executable else 0o600)
                return subprocess.CompletedProcess(command, 0, "", "")
            return subprocess.CompletedProcess(command, 42, "", "")

        return invoke, compilations

    def test_rejects_nonexecutable_output(self):
        invoke, _ = self.compiler(executable=False)
        with patch("run.subprocess.run", side_effect=invoke):
            with self.assertRaisesRegex(AssertionError, "executable"):
                run_case(CASE, Path("/compiler"), 10)

    def test_rejects_nondeterministic_output(self):
        invoke, _ = self.compiler(deterministic=False)
        with patch("run.subprocess.run", side_effect=invoke):
            with self.assertRaisesRegex(AssertionError, "deterministic"):
                run_case(CASE, Path("/compiler"), 10)

    def test_compiles_twice_to_distinct_paths(self):
        invoke, compilations = self.compiler()
        with patch("run.subprocess.run", side_effect=invoke):
            run_case(CASE, Path("/compiler"), 10)
        self.assertEqual(len(compilations), 2)
        self.assertNotEqual(compilations[0], compilations[1])
