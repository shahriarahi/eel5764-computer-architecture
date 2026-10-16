import json
from pathlib import Path
import tempfile
import unittest

from scripts.run_repeated_contention_sweep import (
    PUBLIC_SEEDS,
    RunItem,
    build_plan,
    completed_result_is_valid,
)


class RepeatedSweepPlanTests(unittest.TestCase):
    def test_plan_has_exactly_fifty_fresh_gem5_processes(self) -> None:
        plan = build_plan()

        self.assertEqual(PUBLIC_SEEDS, (0x5764A5E5, 0x5764A5E6, 0x5764A5E7))
        self.assertEqual(len(plan), 50)
        self.assertEqual(sum(item.role == "matched" for item in plan), 48)
        self.assertEqual(sum(item.role == "diagnostic" for item in plan), 2)

    def test_each_seed_has_eight_complete_matched_pairs(self) -> None:
        plan = [item for item in build_plan() if item.role == "matched"]

        for seed in PUBLIC_SEEDS:
            seed_items = [item for item in plan if item.seed == seed]
            self.assertEqual(len(seed_items), 16)
            for ways in range(1, 9):
                pair = [item for item in seed_items if item.monitor_ways == ways]
                self.assertEqual({item.split for item in pair}, {"UNPARTITIONED", f"{ways}-{16-ways}"})

    def test_resume_only_accepts_analysis_for_the_exact_planned_case(self) -> None:
        item = RunItem(PUBLIC_SEEDS[0], "1-15", 1, "matched")
        valid = {
            "split": "1-15",
            "monitor_ways": 1,
            "workload_seed": PUBLIC_SEEDS[0],
            "probe_mapping_validation": "PASS congruent",
            "isolation_validation": "PASS disjoint",
            "stats_blocks": 2,
        }
        with tempfile.TemporaryDirectory() as temporary:
            result_dir = Path(temporary)
            (result_dir / "analysis.json").write_text(json.dumps(valid))
            self.assertTrue(completed_result_is_valid(result_dir, item))

            valid["workload_seed"] = PUBLIC_SEEDS[1]
            (result_dir / "analysis.json").write_text(json.dumps(valid))
            self.assertFalse(completed_result_is_valid(result_dir, item))


if __name__ == "__main__":
    unittest.main()
