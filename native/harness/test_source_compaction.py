import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('bootstrap',Path(__file__).resolve().parents[1]/'scripts/bootstrap-alchem-compiler.py')
bootstrap=importlib.util.module_from_spec(spec);spec.loader.exec_module(bootstrap)


class SourceCompactionTests(unittest.TestCase):
    def test_preserves_string_contents_and_escapes(self):
        source='  def main() do # outside\n    IO.puts("  # end \\\" \\\\ ") # tail\n    System.halt(0)\n  end\n'
        expected='def main() do\nIO.puts("  # end \\\" \\\\ ")\nSystem.halt(0)\nend\n'
        self.assertEqual(bootstrap.compact_source(source),expected)

    def test_keeps_token_and_statement_boundaries(self):
        self.assertEqual(bootstrap.compact_source('  a = 1  # c\n\n b = a + 2\n x < > y\n'),'a = 1\nb = a + 2\nx < > y\n')

    def test_identifier_compaction_preserves_public_entries_and_text(self):
        source='defmodule M do def nc_compile(source: list[integer]): list[integer] do Enum.concat(source,[]) end def native_compile(source: list[integer]): list[integer] do nc_compile(source) end def main() do IO.puts("nc_compile source # text") System.halt(0) end end'
        compact=bootstrap.compact_identifiers(source)
        self.assertIn('def nc_compile(',compact)
        self.assertIn('def native_compile(',compact)
        self.assertIn('def main(',compact)
        self.assertIn('Enum.concat(',compact)
        self.assertIn('"nc_compile source # text"',compact)
        self.assertNotIn('(source:',compact)

    def test_identifier_compaction_keeps_builtin_names(self):
        # A variable named for a builtin is refused; renamed, it would pass
        # in the compacted source and nowhere else.
        source='defmodule M do def pad(length: integer, put: integer): integer do length+put end end'
        compact=bootstrap.compact_identifiers(source)
        self.assertIn('(length: integer, put: integer)',compact)
        self.assertIn('length+put',compact)

    def test_cr_only_comment_boundaries(self):
        self.assertEqual(bootstrap.compact_source('a=1 # comment\rb=2\r'),'a=1\nb=2\n')

    def test_idempotent_and_smaller(self):
        raw=bootstrap.source_text('functions',compact=False)
        compact=bootstrap.compact_identifiers(bootstrap.compact_source(raw))
        self.assertEqual(bootstrap.compact_source(compact),compact)
        self.assertEqual(bootstrap.source_text('functions'),compact)
        self.assertLess(len(compact),len(raw)*0.9)


if __name__=='__main__':unittest.main()
