import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

from analyze import (
    CHECKPOINTS,
    analysis_metadata,
    earliest_divergence,
    exact_effects,
    split_by_window,
    upstream_gaps,
)
from test_trace_analysis import make_event


def run_meta(reset: int = 1000, epoch_cycles: int = 2, intervals: int = 2) -> dict:
    labels = [index % 2 for index in range(intervals)]
    return {
        "reset_tick": reset,
        "measurement_end_tick": reset + epoch_cycles * 500 * intervals,
        "contention": {"epoch_cycles": epoch_cycles, "interval_count": intervals,
                       "activity_labels": labels},
    }


def row(interval: int, label: int, **values: int) -> dict:
    base = {"interval": interval, "label": label, "retry_count": 0,
            "boundary_crossing": False, "llc_path": "hit"}
    base.update(values)
    return base


class MetadataTests(unittest.TestCase):
    def test_derives_tick_schedule_from_cpu_cycles(self) -> None:
        metadata = analysis_metadata(run_meta())
        self.assertEqual(metadata["start_tick"], 1000)
        self.assertEqual(metadata["epoch_ticks"], 1000)
        self.assertEqual(metadata["end_tick"], 3000)
        self.assertEqual(metadata["activity_labels"], [0, 1])

    def test_rejects_measurement_window_mismatch(self) -> None:
        meta = run_meta()
        meta["measurement_end_tick"] += 1
        with self.assertRaisesRegex(ValueError, "whole"):
            analysis_metadata(meta)


class WindowTests(unittest.TestCase):
    def test_counts_warmup_and_post_measurement_timelines(self) -> None:
        timelines = [{"cpu_delivery": make_event("cpu_delivery", tick)}
                     for tick in (999, 1000, 2999, 3000)]
        inside, counts = split_by_window(timelines, analysis_metadata(run_meta()))
        self.assertEqual([t["cpu_delivery"].tick for t in inside], [1000, 2999])
        self.assertEqual(counts, {"before_measurement": 1, "after_measurement": 1})


class EffectTests(unittest.TestCase):
    def test_exact_interval_mean_effects(self) -> None:
        rows = [row(0, 0, admit_to_cpu=10), row(0, 0, admit_to_cpu=11),
                row(1, 1, admit_to_cpu=13)]
        self.assertEqual(exact_effects(rows, ("admit_to_cpu",)),
                         {"admit_to_cpu": Fraction(5, 2)})

    def test_earliest_divergence_skips_zero_effect_checkpoints(self) -> None:
        effects = {name: Fraction(0) for name in CHECKPOINTS}
        effects["cumulative_dequeue"] = Fraction(3)
        effects["cumulative_xbar"] = Fraction(3)
        effects["admit_to_cpu"] = Fraction(3)
        rows = [row(0, 0, **{name: index + 1 for index, name in enumerate(CHECKPOINTS)})]
        result = earliest_divergence(effects, rows)
        self.assertEqual(result["checkpoint"], "cumulative_dequeue")
        self.assertEqual(result["status"], "resolved")

    def test_reports_simultaneous_checkpoints_as_unresolved(self) -> None:
        effects = {name: Fraction(0) for name in CHECKPOINTS}
        effects["cumulative_enqueue"] = Fraction(2)
        rows = [row(0, 0, cumulative_llc_ready=5, cumulative_enqueue=5,
                    cumulative_dequeue=6, cumulative_xbar=7, admit_to_cpu=8)]
        result = earliest_divergence(effects, rows)
        self.assertEqual(result["status"], "unresolved")
        self.assertIn("simultaneous", result["reason"])

    def test_no_divergence_from_admission_points_upstream(self) -> None:
        effects = {name: Fraction(0) for name in CHECKPOINTS}
        result = earliest_divergence(effects, [row(0, 0)])
        self.assertEqual(result["status"], "unresolved")
        self.assertIn("before request_admit", result["reason"])


class UpstreamGapTests(unittest.TestCase):
    def test_gap_runs_from_previous_delivery_to_next_admission(self) -> None:
        timelines = [
            {"request_admit": make_event("request_admit", 10),
             "cpu_delivery": make_event("cpu_delivery", 50)},
            {"request_admit": make_event("request_admit", 70),
             "cpu_delivery": make_event("cpu_delivery", 120)},
        ]
        self.assertEqual(upstream_gaps(timelines), [None, 20])

    def test_rejects_overlapping_requests(self) -> None:
        timelines = [
            {"request_admit": make_event("request_admit", 10),
             "cpu_delivery": make_event("cpu_delivery", 50)},
            {"request_admit": make_event("request_admit", 40),
             "cpu_delivery": make_event("cpu_delivery", 90)},
        ]
        with self.assertRaisesRegex(ValueError, "overlap"):
            upstream_gaps(timelines)


if __name__ == "__main__":
    unittest.main()
