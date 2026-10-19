import tempfile
import unittest
from pathlib import Path

from run_sweep import (
    AES_ROOT, QUIET_ROOT, SEEDS, plan_cases, sweep_command, v3_arguments, v3_probe_length,
    tdma_gate_plain,
)

V3_CMD = ("/home/u/gem5/build/RISCV/gem5.opt -r -e -d /mnt/c/P\\ x/results/updated\\ run/"
          "sweep-v3/seed-5764a5e5/.1-15.tmp.C4h9F1 configs/run_contention.py --split 1-15 "
          "--l1d-size 4KiB --monitor-ways 1 --workload-seed 1466213861 --monitor-sink file "
          "--monitor-variant v3 \n")


class SweepTests(unittest.TestCase):
    def test_design_is_three_seeds_by_eight_allocations_per_arm(self) -> None:
        self.assertEqual(SEEDS, (0x5764A5E5, 0x5764A5E6, 0x5764A5E7))
        cases = plan_cases()
        self.assertEqual(len(cases), 48)
        self.assertEqual({c.root for c in cases}, {AES_ROOT, QUIET_ROOT})
        self.assertEqual(sorted({c.split for c in cases}),
                         sorted(f"{w}-{16 - w}" for w in range(1, 9)))
        self.assertEqual((len(AES_ROOT), len(QUIET_ROOT)), (8, 8))

    def test_reuses_v3_treatment_arguments_and_probe_length(self) -> None:
        self.assertEqual(v3_arguments(V3_CMD), [
            "--split", "1-15", "--l1d-size", "4KiB", "--monitor-ways", "1",
            "--workload-seed", "1466213861", "--monitor-sink", "file",
            "--monitor-variant", "v3"])
        expected = len("/mnt/c/P x/results/updated run/sweep-v3/seed-5764a5e5/"
                       ".1-15.tmp.C4h9F1/probes.bin")
        self.assertEqual(v3_probe_length(V3_CMD), expected)

    def test_command_adds_only_the_defense_layers(self) -> None:
        command = sweep_command(Path("/out"), Path("/exe"), Path("/a.py"), Path("/p"),
                                v3_arguments(V3_CMD), quiet=Path("/q"))
        self.assertEqual(command[:5], [str(Path("/exe")), "-r", "-e", "-d", str(Path("/out"))])
        self.assertEqual(command[5:8], [str(Path("/a.py")), "--respq", "--quiet-binary"])
        self.assertIn("--tdma-slot-cycles", command)
        self.assertEqual(command[-12:], v3_arguments(V3_CMD))
        self.assertNotIn("--stats-file=stats.txt.gz", command)
        self.assertNotIn("--stats-per-interval", command)

    def test_plain_stats_counter_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory)
            (case / "stats.txt").write_text("system.l2bus.tdmaOverruns 0 # x\n"
                                            "system.l2bus.tdmaGrants0 5 # x\n")
            self.assertEqual(tdma_gate_plain(case), {"tdma_lines": 2, "violations": 0})
            (case / "stats.txt").write_text("system.l2bus.tdmaDownstreamRefusals 1 # x\n")
            with self.assertRaisesRegex(ValueError, "tdmaDownstreamRefusals"):
                tdma_gate_plain(case)


if __name__ == "__main__":
    unittest.main()
