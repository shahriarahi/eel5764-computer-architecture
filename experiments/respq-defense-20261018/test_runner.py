import gzip
import tempfile
import unittest
from pathlib import Path

from run_respq import (
    ARMS, build_command, compare_probes, staging_name, tdma_counter_gate,
)


AES_REF = {"command": ["/old/gem5.opt", "-r", "-e", "-d", "/old/.1-15.tmp.abc123",
                       "--stats-file=stats.txt.gz", "/x/experiments/tdma/run_contention_tdma.py",
                       "--baseline-root", "/p", "--tdma-slot-cycles", "4", "--split", "1-15"]}
QUIET_REF = {"command": ["/old/gem5.opt", "-r", "-e", "-d", "/old/.1-15.tmp.abc123",
                         "--stats-file=stats.txt.gz",
                         "/x/experiments/quiet-control-20261016/quiet_adapter.py",
                         "--quiet-binary", "/q/quiet_victim", "--baseline-root", "/p",
                         "--tdma-slot-cycles", "4", "--split", "1-15"]}


class RunnerTests(unittest.TestCase):
    def test_arm_roots_are_new_eight_character_names(self) -> None:
        names = [arm.root for arm in ARMS]
        self.assertEqual(len(set(names)), 4)
        self.assertTrue(all(len(name) == 8 for name in names))
        self.assertEqual([arm.name for arm in ARMS],
                         ["guard-aes", "guard-quiet", "defense-aes", "defense-quiet"])

    def test_guard_command_swaps_only_binary_output_and_adapter(self) -> None:
        command = build_command(AES_REF, Path("/out"), Path("/new/gem5.opt"),
                                Path("/a/run_contention_respq.py"), respq=False)
        self.assertEqual(command[0], str(Path("/new/gem5.opt")))
        self.assertEqual(command[command.index("-d") + 1], str(Path("/out")))
        self.assertIn(str(Path("/a/run_contention_respq.py")), command)
        self.assertNotIn("--respq", command)
        self.assertEqual(command[7:], AES_REF["command"][7:])

    def test_defense_command_keeps_quiet_binary_and_enables_split(self) -> None:
        command = build_command(QUIET_REF, Path("/out"), Path("/new/gem5.opt"),
                                Path("/a/run_contention_respq.py"), respq=True)
        adapter = command.index(str(Path("/a/run_contention_respq.py")))
        self.assertEqual(command[adapter + 1], "--respq")
        self.assertEqual(command[adapter + 2:adapter + 4], ["--quiet-binary", "/q/quiet_victim"])

    def test_staging_name_reproduces_reference_probe_path_length(self) -> None:
        parent = Path("/mnt/c/project/results/updated run/tdma-rda/seed-5764a5e5")
        name = staging_name(parent, 138)
        self.assertEqual(len(str(parent / name / "probes.bin")), 138)

    def test_compare_probes_counts_records_and_intervals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = bytearray(16 * 512), bytearray(16 * 512)
            b[16 * 300] = 1     # record 300 -> interval 300 // (512 // 64) = 37
            b[16 * 301 + 5] = 1
            (root / "a").mkdir(); (root / "b").mkdir()
            (root / "a/probes.bin").write_bytes(a); (root / "b/probes.bin").write_bytes(b)
            result = compare_probes(root / "a", root / "b")
        self.assertEqual(result["records"], 512)
        self.assertEqual(result["differing_records"], 2)
        self.assertEqual(result["differing_intervals"], [37])
        self.assertFalse(result["byte_identical"])

    def test_counter_gate_rejects_violation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory)
            with gzip.open(case / "stats.txt.gz", "wt") as stream:
                stream.write("system.l2bus.tdmaOverruns 2 # x\n")
            with self.assertRaisesRegex(ValueError, "tdmaOverruns"):
                tdma_counter_gate(None, case)


if __name__ == "__main__":
    unittest.main()
