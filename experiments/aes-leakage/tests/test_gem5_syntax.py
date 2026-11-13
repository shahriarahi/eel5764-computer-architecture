"""Syntax/type check of the tracing extension against the real gem5 headers.

This is NOT a gem5 build: gem5_syntax_check.sh runs `g++ -fsyntax-only` on the
one translation unit, with hand-made stand-ins for the two generated headers
that depend on the new parameters.  It catches typos and type errors in the
(otherwise uncompiled) tracing patch before the Phase B build.  Skipped when
the gem5 tree or g++ is not present.
"""
import os
import unittest

from tests import _helpers as h

GEM5 = h.Path(os.environ.get("GEM5_TREE", h.Path.home() / "eel5764" / "gem5"))


@h.skip_unless_tool("g++")
@unittest.skipUnless((GEM5 / "build" / "RISCV" / "params").is_dir(),
                     "SKIPPED: no built gem5 tree at %s (set GEM5_TREE)" % GEM5)
class TracingSourcesTypeCheck(unittest.TestCase):
    def test_original_and_patched_sources_both_compile_syntax_only(self):
        proc = h.run(["bash", h.EXP / "gem5_syntax_check.sh"],
                     env=dict(os.environ, GEM5_TREE=str(GEM5)), timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("CONTROL", proc.stdout)
        self.assertIn("PATCHED", proc.stdout)
        self.assertIn("syntax check PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()
