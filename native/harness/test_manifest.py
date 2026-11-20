import json
from pathlib import Path
import unittest
from run import ROOT, load_manifest

class ManifestTests(unittest.TestCase):
    def test_fixture_manifest_is_valid(self):
        cases = load_manifest(ROOT / "fixtures/manifest.json")
        self.assertGreaterEqual(len(cases), 3)
        self.assertTrue(any("expect_compile_error" in case for case in cases))
        self.assertTrue(any("expect" in case for case in cases))

    def test_positive_ir_fixtures_have_version(self):
        for case in load_manifest(ROOT / "fixtures/manifest.json"):
            if "expect_compile_error" in case:
                continue
            ir = json.loads((ROOT / case["source"]).read_text())
            self.assertIn(ir["version"], (1, 2, 3, 4, 5, 6, 7, 8, 9))
            self.assertTrue(ir["functions"])

if __name__ == "__main__":
    unittest.main()
