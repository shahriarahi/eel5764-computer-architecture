import tempfile
import unittest
from pathlib import Path

from analysis.analyze_contention import (
    PROBE_BIN_RECORD,
    AnalysisError,
    hit_only_test,
    parse_probe_binary,
    percentile,
)
from analysis.summarize_repeated_contention_v2 import (
    conclusion,
    self_eviction_ok,
    stable_point,
)
from scripts.run_repeated_contention_sweep_v2 import smoke_plan


LABELS = [0, 1] * 4
START, EPOCH, SETS = 100, 1000, 3


def write_probe_file(path: Path, latency=lambda i, s: 40, swap=None) -> None:
    records = []
    for interval in range(len(LABELS)):
        for cache_set in range(SETS):
            records.append((START + interval * EPOCH + 10 * cache_set,
                            latency(interval, cache_set), interval, cache_set))
    if swap is not None:
        records[swap], records[swap + 1] = records[swap + 1], records[swap]
    path.write_bytes(b"".join(PROBE_BIN_RECORD.pack(*r) for r in records))


def parse(path: Path):
    return parse_probe_binary(path, expected_labels=LABELS, start_cycle=START,
                              epoch_cycles=EPOCH, interval_count=len(LABELS),
                              set_count=SETS)


class ProbeBinaryTests(unittest.TestCase):
    def test_round_trip_returns_interval_by_set_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probes.bin"
            write_probe_file(path, latency=lambda i, s: 40 + i + s)
            matrix, labels = parse(path)
        self.assertEqual(labels, LABELS)
        self.assertEqual(matrix[2], [42.0, 43.0, 44.0])

    def test_rejects_out_of_order_records_and_wrong_size(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "probes.bin"
            write_probe_file(path, swap=4)
            with self.assertRaisesRegex(AnalysisError, "expected interval"):
                parse(path)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaisesRegex(AnalysisError, "bytes"):
                parse(path)


class HitOnlyTests(unittest.TestCase):
    def test_percentile_matches_linear_interpolation(self) -> None:
        self.assertEqual(percentile([1.0, 2.0, 3.0, 4.0, 5.0], 50.0), 3.0)
        self.assertAlmostEqual(percentile([0.0, 10.0], 1.0), 0.1)

    def test_misses_are_removed_and_hit_shift_is_detected(self) -> None:
        # Active intervals are 1 cycle slower on hits; set 2 always misses.
        labels = LABELS * 4
        jitter = [0.0, 0.2, 0.4, 0.2] * 8  # same jitter pattern in both labels
        matrix = [[40.0 + label + j, 40.0 + label + j, 200.0]
                  for label, j in zip(labels, jitter)]
        result = hit_only_test(matrix, labels, monitor_ways=1, permutations=200)
        self.assertAlmostEqual(result["all_hit_record_fraction"], 2 / 3)
        self.assertAlmostEqual(result["hit_only_delta_per_line"], 1.0)
        self.assertLess(result["hit_only_p"], 0.05)

    def test_interval_without_hits_is_an_error(self) -> None:
        matrix = [[40.0, 40.0]] * 7 + [[400.0, 400.0]]
        with self.assertRaisesRegex(AnalysisError, "no all-hit"):
            hit_only_test(matrix, LABELS, monitor_ways=1, permutations=10)


class DecisionRuleTests(unittest.TestCase):
    def test_self_eviction_gate_uses_absolute_tolerance(self) -> None:
        control = {"all_hit_record_fraction": 0.99}
        self.assertTrue(self_eviction_ok(control, {"all_hit_record_fraction": 0.981}))
        self.assertFalse(self_eviction_ok(control, {"all_hit_record_fraction": 0.97}))

    def test_conclusion_precedence(self) -> None:
        valid = {"max_set": True, "hit_only": True}
        quiet = {"max_set": False, "hit_only": False}
        self.assertEqual(conclusion(False, valid, quiet), "uninterpretable")
        self.assertEqual(conclusion(True, valid, {"max_set": False, "hit_only": True}),
                         "distinguishable")
        self.assertEqual(conclusion(True, valid, quiet), "indistinguishable")
        self.assertEqual(conclusion(True, {"max_set": True, "hit_only": False}, quiet),
                         "invalid control")

    def test_stable_point_requires_every_larger_split(self) -> None:
        rows = [{"split": "1-15", "c": "x"}, {"split": "2-14", "c": "y"},
                {"split": "3-13", "c": "y"}]
        self.assertEqual(stable_point(rows, "c", "y"), "2-14")
        self.assertIsNone(stable_point(rows, "c", "z"))

    def test_smoke_plan_is_one_matched_pair(self) -> None:
        plan = smoke_plan()
        self.assertEqual([(i.split, i.monitor_ways) for i in plan],
                         [("UNPARTITIONED", 1), ("1-15", 1)])


if __name__ == "__main__":
    unittest.main()
