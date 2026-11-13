"""build.sh and build_manifest.json."""
import hashlib
import json
import re
import unittest

from tests import _helpers as h

BINARIES = [
    "victim_leak_r1_scrub", "victim_leak_r1_noscrub",
    "victim_leak_full_scrub", "victim_leak_full_noscrub",
    "victim_leak_tvla", "monitor_leak",
]
N = 8


def cflags_of(script):
    match = re.search(r'CFLAGS="((?:[^"\\]|\\.|\\\n)*)"',
                      script.read_text(), re.S)
    return " ".join(match.group(1).replace("\\\n", " ").split())


class FlagsMatchTheFrozenBuild(unittest.TestCase):
    def test_cflags_equal_workloads_build_sh(self):
        frozen = cflags_of(h.WORKLOADS / "build.sh")
        ours = cflags_of(h.EXP / "build.sh")
        self.assertEqual(ours, frozen)

    def test_helper_flags_equal_workloads_build_sh(self):
        self.assertEqual(" ".join(h.RISCV_CFLAGS),
                         cflags_of(h.WORKLOADS / "build.sh"))


@h.skip_unless_tool(h.RISCV_CC)
class BuildManifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = h.fake_clock_build(N)
        cls.manifest = json.loads((cls.build / "build_manifest.json").read_text())

    def test_every_binary_exists_and_hash_matches(self):
        self.assertEqual(sorted(self.manifest["binaries"]), sorted(BINARIES))
        for name in BINARIES:
            data = (self.build / name).read_bytes()
            self.assertEqual(self.manifest["binaries"][name]["sha256"],
                             hashlib.sha256(data).hexdigest(), name)
            self.assertEqual(self.manifest["binaries"][name]["bytes"], len(data))

    def test_manifest_records_schedule_and_defines(self):
        self.assertEqual(self.manifest["n_win"], N)
        self.assertEqual(self.manifest["schedule"]["N_WIN"], N)
        self.assertEqual(self.manifest["schedule"]["T0"], 2_000_000)
        self.assertIn("-DLEAK_FAKE_CLOCK", self.manifest["defines"])
        self.assertEqual(self.manifest["key_hex"],
                         "f1e2d3c4b5a69788796a5b4c3d2e1f10")

    def test_victim_tables_are_line_aligned_with_expected_sizes(self):
        for name in BINARIES[:-1]:
            symbols = self.manifest["symbols"][name]
            for table, size in (("te0", 1024), ("te1", 1024), ("te2", 1024),
                                ("te3", 1024), ("sbox", 256)):
                self.assertEqual(symbols[table]["size"], size, (name, table))
                self.assertEqual(symbols[table]["addr"] % 64, 0, (name, table))

    def test_table_layout_describes_the_68_line_range(self):
        for name in BINARIES[:-1]:
            layout = self.manifest["table_layout"][name]
            self.assertEqual(layout["table_lines"], 68)
            self.assertGreaterEqual(layout["trace_lines"], 68)
            self.assertEqual(layout["trace_size"], layout["trace_lines"] * 64)
            # every table starts on its recorded line offset inside the range
            for table, info in layout["tables"].items():
                self.assertEqual(
                    layout["trace_base"] + 64 * info["line_offset"],
                    info["addr"], table)

    def test_monitor_exports_probe_lines(self):
        probe = self.manifest["symbols"]["monitor_leak"]["probe_lines"]
        self.assertEqual(probe["size"], 16 * 256 * 64)
        self.assertEqual(probe["addr"] % 64, 0)


@h.skip_unless_tool(h.RISCV_CC, "riscv64-linux-gnu-nm")
class ScrubBufferSize(unittest.TestCase):
    """The scrub walk must flush the 4 KiB 4-way L1D without flooding the LLC.

    P0 showed that an 8 KiB walk (128 lines) allocates enough LLC lines, in an
    LLC full of the monitor's own lines, to push the monitor's prime pass past
    its deadline (LRU cascade).  64 consecutive lines put 4 lines in each of
    the 16 L1D sets, which replaces every line under LRU.
    """

    def scrub_buffer_size(self, *defines):
        with h.tmpdir() as tmp:
            out = h.Path(tmp) / "victim"
            proc = h.riscv_build(
                [h.EXP / "victim_leak.c", h.EXP / "aes_leak_ext.c"], out,
                defines=["N_WIN=4", "LEAK_FAKE_CLOCK"] + list(defines))
            self.assertEqual(proc.returncode, 0, proc.stderr)
            nm = h.run(["riscv64-linux-gnu-nm", "-S", "--defined-only", out])
            for line in nm.stdout.splitlines():
                fields = line.split()
                if len(fields) == 4 and fields[3] == "scrub_buffer":
                    return int(fields[1], 16)
            return None

    def test_default_scrub_buffer_is_exactly_the_l1d_size(self):
        self.assertEqual(self.scrub_buffer_size("LEAK_SCRUB=1"), 4096)

    def test_size_can_be_overridden_at_build_time(self):
        self.assertEqual(
            self.scrub_buffer_size("LEAK_SCRUB=1", "LEAK_SCRUB_BYTES=8192UL"), 8192)

    def test_a_noscrub_build_has_no_scrub_buffer(self):
        self.assertIsNone(self.scrub_buffer_size("LEAK_SCRUB=0"))


if __name__ == "__main__":
    unittest.main()
