import json
import tempfile
import unittest
from pathlib import Path

from analysis.summarize_contention import (
    ORDER,
    SummaryError,
    first_indistinguishable,
    load_analyses,
)


def analysis_record(split: str, decision: str = "PASS") -> dict[str, object]:
    monitor_ways = None if split == "UNPARTITIONED" else int(split.split("-")[0])
    return {
        "split": "off" if split == "UNPARTITIONED" else split,
        "l1d_size": "4KiB",
        "statistic": "max-set",
        "observed_max_snr": 2.0,
        "null_max_snr_95th": 1.0,
        "empirical_p": 0.01,
        "decision": decision,
        "ipc_core0": 0.5,
        "ipc_core1": 0.6,
        "llc_miss_rate_core0": 0.2,
        "llc_miss_rate_core1": 0.1,
        **({} if monitor_ways is None else {
            "isolation_validation": "PASS disjoint",
            "isolation_violations": 0,
        }),
    }


class SummaryTests(unittest.TestCase):
    def make_results(self, missing: str | None = None) -> Path:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for split in reversed(ORDER):
            if split == missing:
                continue
            directory = root / split
            directory.mkdir()
            (directory / "analysis.json").write_text(
                json.dumps(analysis_record(split))
            )
        return root

    def test_load_analyses_returns_declared_order(self) -> None:
        rows = load_analyses(self.make_results())

        self.assertEqual([row["display_split"] for row in rows], ORDER)

    def test_missing_configuration_is_rejected(self) -> None:
        with self.assertRaisesRegex(SummaryError, "missing.*8-8"):
            load_analyses(self.make_results(missing="8-8"))

    def test_first_indistinguishable_uses_first_partitioned_failure(self) -> None:
        rows = [
            {**analysis_record(split), "display_split": split}
            for split in ORDER
        ]
        rows[0]["decision"] = "FAIL"
        rows[4]["decision"] = "FAIL"
        rows[6]["decision"] = "FAIL"

        collapse = first_indistinguishable(rows)

        self.assertIsNotNone(collapse)
        self.assertEqual(collapse["display_split"], "4-12")


if __name__ == "__main__":
    unittest.main()
