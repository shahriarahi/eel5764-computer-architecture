"""gem5_ext copy: only the victim-table tracing additions may differ.

The frozen ../../gem5_ext must stay byte-identical (preserve.py checks that);
the experiment's copy adds optional tracing that is OFF by default, so a run
without the new parameters behaves exactly like the original.
"""
import difflib
import re
import unittest

from tests import _helpers as h

FROZEN = h.REPO / "gem5_ext"
COPY = h.EXP / "gem5_ext"
FILES = ["RequestorPartitionManager.py", "SConscript",
         "requestor_partition_manager.cc", "requestor_partition_manager.hh"]

# The only original line that may change: the last ADD_STAT initialiser gets a
# trailing comma because new ADD_STATs follow it.
CHANGED_ORIGINAL_LINES = {
    '             "Observed physical-set minus logical-set rotation")',
}
# Added lines that do not mention the victim tracing by name.
GENERIC_ADDED_LINES = {
    '#include "sim/cur_tick.hh"',
    '             "Observed physical-set minus logical-set rotation"),',
}


def read(path):
    return path.read_text().splitlines()


class CopyDiffersOnlyByTracing(unittest.TestCase):
    def test_same_set_of_files(self):
        self.assertEqual(sorted(p.name for p in COPY.iterdir() if p.is_file()),
                         sorted(FILES))
        self.assertEqual(sorted(p.name for p in FROZEN.iterdir() if p.is_file()),
                         sorted(FILES))

    def test_no_original_line_is_removed_except_the_allowed_one(self):
        for name in FILES:
            matcher = difflib.SequenceMatcher(
                None, read(FROZEN / name), read(COPY / name), autojunk=False)
            original = read(FROZEN / name)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag in ("delete", "replace"):
                    for line in original[i1:i2]:
                        self.assertIn(line, CHANGED_ORIGINAL_LINES,
                                      "%s: original line removed: %r" % (name, line))

    def test_every_added_line_is_about_the_victim_tracing(self):
        for name in FILES:
            original = read(FROZEN / name)
            new = read(COPY / name)
            matcher = difflib.SequenceMatcher(None, original, new, autojunk=False)
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag not in ("insert", "replace"):
                    continue
                block = new[j1:j2]
                joined = "\n".join(block)
                for line in block:
                    if not line.strip() or line in GENERIC_ADDED_LINES:
                        continue
                    # Comment/continuation lines are judged with their block.
                    self.assertTrue(
                        re.search(r"[Vv]ictim|VictimTable", line) or
                        re.search(r"[Vv]ictim", joined),
                        "%s: added line unrelated to tracing: %r" % (name, line))

    def test_tracing_is_disabled_by_default(self):
        text = (COPY / "RequestorPartitionManager.py").read_text()
        self.assertRegex(text, r'victim_requestor_name = Param\.String\(\s*""')
        self.assertRegex(text, r"victim_vaddr_base = Param\.Addr\(0,")
        self.assertRegex(text, r"victim_vaddr_size = Param\.Addr\(0,")
        self.assertRegex(text, r"victim_set_count = Param\.Unsigned\(\s*256")

    def test_tracing_only_runs_when_a_victim_range_is_configured(self):
        cc = (COPY / "requestor_partition_manager.cc").read_text()
        self.assertIn("victimVaddrSize != 0 &&\n            pkt->req->requestorId() == victimRequestorId", cc)

    def test_debug_flag_and_stats_are_declared(self):
        self.assertIn('DebugFlag("VictimTable"', (COPY / "SConscript").read_text())
        cc = (COPY / "requestor_partition_manager.cc").read_text()
        for stat in ("victimTableFills", "victimTableLineSetPlusOne",
                     "victimTableSetMismatches", "victimTableMissingVaddr"):
            self.assertIn("ADD_STAT(%s," % stat, cc)
        self.assertIn('"victim_fill line=%u set=%u vaddr=%#x paddr=%#x\\n"', cc)

    def test_includes_still_use_the_gem5_ext_prefix(self):
        # The sources include "gem5_ext/..."; the directory must keep that name.
        self.assertEqual(COPY.name, "gem5_ext")
        self.assertIn('#include "gem5_ext/requestor_partition_manager.hh"',
                      (COPY / "requestor_partition_manager.cc").read_text())

    def test_reference_patch_still_applies_to_the_frozen_sources(self):
        import shutil
        import tempfile
        if not h.have("patch"):
            self.skipTest("SKIPPED: missing tool 'patch'")
        with tempfile.TemporaryDirectory(prefix="aesleak-patch-") as tmp:
            target = h.Path(tmp) / "gem5_ext"
            shutil.copytree(FROZEN, target)
            proc = h.run(["patch", "-p2", "--dry-run", "-d", str(target),
                          "-i", str(h.EXP / "victim_table_trace.patch")])
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
