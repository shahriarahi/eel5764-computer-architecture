"""Tests for the crossbar mechanism study (2026-10-14)."""

import gzip
import tempfile
import unittest
from pathlib import Path

from analysis.summarize_mechanism import (
    EXPECTED_MECHANISM, KEYS, SETTINGS, classify, pearson, read_stats_blocks, spearman,
)
from scripts.run_mechanism import (
    SETTINGS as RUNNER_SETTINGS, build_plan, case_directory, gem5_command, setting_root,
)


class RunnerPlanTests(unittest.TestCase):
    def test_full_plan_has_48_unique_cases(self) -> None:
        plan = build_plan()
        self.assertEqual(len(plan), 48)
        self.assertEqual(len({case_directory(i) for i in plan}), 48)

    def test_roots_match_the_v3_sweep_path_length(self) -> None:
        # Equal length keeps the monitor's probe-file argument, and so its stack
        # layout, identical to the v3 sweep.
        for setting in RUNNER_SETTINGS:
            self.assertEqual(len(setting_root(setting).name), len("sweep-v3"))

    def test_commands_use_v3_per_interval_stats_and_setting_knobs(self) -> None:
        item = next(i for i in build_plan(("ide",)) if i.role == "treatment" and i.monitor_ways == 8)
        command = gem5_command(item, Path("/tmp/x"))
        self.assertIn("--stats-file=stats.txt.gz", command)
        for flag in ("--monitor-variant", "v3", "--stats-per-interval", "--split", "8-8",
                     "--l2bus-width", "512", "--l2bus-header-latency", "0", "--l2bus-clock", "cpu"):
            self.assertIn(flag, command)
        control = next(i for i in build_plan(("std",)) if i.role == "control")
        command = gem5_command(control, Path("/tmp/x"))
        self.assertIn("off", command)
        self.assertNotIn("--l2bus-width", command)

    def test_runner_and_analysis_agree_on_settings(self) -> None:
        self.assertEqual(tuple(RUNNER_SETTINGS), SETTINGS)
        self.assertEqual(set(EXPECTED_MECHANISM), set(SETTINGS))


class AnalysisHelperTests(unittest.TestCase):
    def test_reads_every_gzipped_stats_block(self) -> None:
        block = ("\n---------- Begin Simulation Statistics ----------\n"
                 f"{KEYS['occupancy']} {{}} # occupancy\n"
                 "system.cpu0.ipc 0.5 # ignored\n"
                 "---------- End Simulation Statistics   ----------\n")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stats.txt.gz"
            with gzip.open(path, "wt") as stream:
                for value in (10, 20, 30):
                    stream.write(block.format(value))
            blocks = read_stats_blocks(path)
        self.assertEqual([b[KEYS["occupancy"]] for b in blocks], [10.0, 20.0, 30.0])
        self.assertNotIn("system.cpu0.ipc", blocks[0])

    def test_rank_and_linear_correlation(self) -> None:
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [10, 20, 25, 90]), 1.0)
        self.assertAlmostEqual(spearman([1, 2, 3, 4], [4, 3, 2, 1]), -1.0)
        self.assertAlmostEqual(pearson([1, 2, 3], [2, 4, 6]), 1.0)

    def test_preregistered_outcome_classes(self) -> None:
        self.assertEqual(classify(True, True, [0.95, 0.97]), "confirmed")
        self.assertEqual(classify(True, False, [0.6, 0.7]), "partial")
        self.assertEqual(classify(True, False, [0.6, 0.3]), "not supported")
        self.assertEqual(classify(False, True, [0.99, 0.99]), "not supported")


if __name__ == "__main__":
    unittest.main()
