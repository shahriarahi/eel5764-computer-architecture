import json
import tempfile
import unittest
from pathlib import Path

from analysis.summarize_matched_contention import (
    MatchedSummaryError,
    load_matched_pairs,
    paired_rows,
    stable_collapse_point,
)


def record(split: str, monitor_ways: int, distinguishable: bool) -> dict[str, object]:
    return {
        "split": split,
        "monitor_ways": monitor_ways,
        "l1d_size": "4KiB",
        "statistic": "max-set",
        "distinguishable": distinguishable,
        "observed_max_snr": 2.0 if distinguishable else 0.5,
        "null_max_snr_95th": 1.0,
        "empirical_p": 0.01 if distinguishable else 0.5,
        "ipc_core0": 0.5,
        "ipc_core1": 0.6,
        "llc_miss_rate_core0": 0.2,
        "llc_miss_rate_core1": 0.1,
        "probe_mapping_validation": "PASS congruent",
        "aes_encryptions": 100,
        "aes_cycles_per_encryption": 10.0,
        **({} if split == "off" else {
            "isolation_validation": "PASS disjoint",
            "isolation_violations": 0,
        }),
    }


class MatchedSummaryTests(unittest.TestCase):
    def make_results(self, bad_control: int | None = None) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for ways in range(1, 9):
            control = root / f"UNPARTITIONED-A{ways}"
            treatment = root / f"{ways}-{16 - ways}"
            control.mkdir()
            treatment.mkdir()
            (control / "analysis.json").write_text(json.dumps(record(
                "off", ways, ways != bad_control
            )))
            (treatment / "analysis.json").write_text(json.dumps(record(
                f"{ways}-{16 - ways}", ways, False
            )))
        return root

    def test_loads_eight_depth_matched_control_treatment_pairs(self) -> None:
        pairs = load_matched_pairs(self.make_results())

        self.assertEqual(len(pairs), 8)
        self.assertEqual(pairs[0]["monitor_ways"], 1)
        self.assertEqual(pairs[-1]["monitor_ways"], 8)

    def test_rejects_partition_when_its_matched_control_is_not_detectable(self) -> None:
        with self.assertRaisesRegex(MatchedSummaryError, "A=3.*not distinguishable"):
            load_matched_pairs(self.make_results(bad_control=3))

    def test_rows_use_each_depths_own_control_for_cost_and_decision(self) -> None:
        pairs = load_matched_pairs(self.make_results())

        rows = paired_rows(pairs)

        self.assertEqual(rows[0]["paired_conclusion"], "signal suppressed")
        self.assertEqual(rows[0]["monitor_ipc_cost_pct"], 0.0)
        self.assertEqual(rows[0]["aes_ipc_cost_pct"], 0.0)

    def test_stable_collapse_requires_all_later_splits_to_stay_suppressed(self) -> None:
        rows = paired_rows(load_matched_pairs(self.make_results()))
        self.assertEqual(stable_collapse_point(rows), "1-15")

        rows[-1]["paired_conclusion"] = "signal remains"
        self.assertIsNone(stable_collapse_point(rows))


if __name__ == "__main__":
    unittest.main()
