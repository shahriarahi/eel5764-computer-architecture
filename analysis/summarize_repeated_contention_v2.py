#!/usr/bin/env python3
"""Aggregate the record-free (v2) repeated contention sweep.

Predeclared in PREREGISTRATION_V2_20261011.md.  Differences from v1
(analysis/summarize_repeated_contention.py, which is unchanged):

* Two co-primary statistics: max-set SNR (as in v1) and the hit-only
  interval mean.  Fisher combines the three seeds; Holm corrects across all
  16 tests (8 allocations x 2 statistics), separately for controls and
  treatments.
* Self-eviction gate: in every matched pair the treatment's all-hit record
  fraction must be within SELF_EVICTION_TOLERANCE of its control's.  A
  failing allocation is "uninterpretable", never "indistinguishable".
* Effect size: hit-only active-minus-idle cycles per probed line, with a 90%
  bootstrap CI.  An allocation is "equivalent" only if that CI lies inside
  +/- EQUIVALENCE_MARGIN (two one-sided tests at alpha 0.05).
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from pathlib import Path

# Allow `python3 analysis/summarize_repeated_contention_v2.py` from the root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.summarize_repeated_contention import (  # noqa: E402
    fisher_combined_p,
    holm_adjust,
    percent_cost,
)


PUBLIC_SEEDS = (0x5764A5E5, 0x5764A5E6, 0x5764A5E7)
ALPHA = 0.05
STATISTICS = ("max_set", "hit_only")
SELF_EVICTION_TOLERANCE = 0.01  # all-hit fraction, absolute
EQUIVALENCE_MARGIN = 0.02       # cycles per probed line
BOOTSTRAP_REPLICATES = 2_000
BOOTSTRAP_SEED = 5_764
CI_LEVEL = 0.90


class SummaryError(RuntimeError):
    """Raised when inputs cannot support the predeclared analysis."""


def statistic_fields(record: dict[str, object], name: str) -> tuple[float, bool]:
    """Return (p-value, individually distinguishable) for one statistic."""
    if name == "max_set":
        return float(record["empirical_p"]), bool(record["distinguishable"])
    return float(record["hit_only_p"]), bool(record["hit_only_distinguishable"])


def self_eviction_ok(control: dict[str, object], treatment: dict[str, object]) -> bool:
    return abs(
        float(treatment["all_hit_record_fraction"])
        - float(control["all_hit_record_fraction"])
    ) <= SELF_EVICTION_TOLERANCE


def conclusion(
    pairs_valid: bool, control_valid: dict[str, bool], treatment_sig: dict[str, bool]
) -> str:
    """Apply the predeclared allocation-level decision rule."""
    if not pairs_valid:
        return "uninterpretable"
    if any(control_valid[s] and treatment_sig[s] for s in STATISTICS):
        return "distinguishable"
    if all(control_valid[s] for s in STATISTICS):
        return "indistinguishable"
    return "invalid control"


def stable_point(rows: list[dict[str, object]], key: str, value: object) -> str | None:
    """First split whose `key` equals `value` at it and at every larger split."""
    for index, row in enumerate(rows):
        if all(later[key] == value for later in rows[index:]):
            return str(row["split"])
    return None


def interval_delta(means: list[float], labels: list[int]) -> float:
    active = [v for v, label in zip(means, labels) if label == 1]
    idle = [v for v, label in zip(means, labels) if label == 0]
    return statistics.mean(active) - statistics.mean(idle)


def bootstrap_ci(
    runs: list[tuple[list[float], list[int], int]], rng: random.Random
) -> tuple[float, float]:
    """CI of the seed-averaged per-line effect; resamples intervals per label."""
    estimates = []
    for _ in range(BOOTSTRAP_REPLICATES):
        per_seed = []
        for means, labels, ways in runs:
            active = [v for v, label in zip(means, labels) if label == 1]
            idle = [v for v, label in zip(means, labels) if label == 0]
            a = [rng.choice(active) for _ in active]
            i = [rng.choice(idle) for _ in idle]
            per_seed.append((statistics.mean(a) - statistics.mean(i)) / ways)
        estimates.append(statistics.mean(per_seed))
    estimates.sort()
    tail = (1.0 - CI_LEVEL) / 2.0
    return (
        estimates[int(tail * BOOTSTRAP_REPLICATES)],
        estimates[int((1.0 - tail) * BOOTSTRAP_REPLICATES) - 1],
    )


def load_pair(root: Path, seed: int, ways: int) -> tuple[dict, dict, list[int]]:
    seed_root = root / f"seed-{seed:08x}"
    split = f"{ways}-{16 - ways}"
    loaded = []
    for directory, expected_split in ((f"UNPARTITIONED-A{ways}", "off"), (split, split)):
        path = seed_root / directory / "analysis.json"
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise SummaryError(f"cannot read valid {path}: {exc}") from exc
        checks = {
            "monitor_sink": record.get("monitor_sink") == "file",
            "workload_seed": record.get("workload_seed") == seed,
            "monitor_ways": record.get("monitor_ways") == ways,
            "split": record.get("split") == expected_split,
            "mapping": record.get("probe_mapping_validation") == "PASS congruent",
            "hit_only": record.get("hit_only_error") is None
            and "hit_only_p" in record,
        }
        if expected_split != "off":
            checks["disjoint"] = (
                record.get("isolation_validation") == "PASS disjoint"
                and record.get("isolation_violations") == 0
            )
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            raise SummaryError(f"{path}: failed checks {failed}")
        loaded.append(record)
    meta = json.loads((seed_root / split / "run_meta.json").read_text())
    labels = [int(v) for v in meta["contention"]["activity_labels"]]
    return loaded[0], loaded[1], labels


def aggregate(root: Path) -> tuple[list[dict], list[dict]]:
    per_seed: list[dict[str, object]] = []
    pairs: dict[int, list[tuple[dict, dict, list[int]]]] = {}
    for ways in range(1, 9):
        pairs[ways] = [load_pair(root, seed, ways) for seed in PUBLIC_SEEDS]

    fisher = {arm: {} for arm in ("control", "treatment")}
    for ways in range(1, 9):
        split = f"{ways}-{16 - ways}"
        for s in STATISTICS:
            for arm, index in (("control", 0), ("treatment", 1)):
                fisher[arm][f"{split}|{s}"] = fisher_combined_p(
                    [statistic_fields(pair[index], s)[0] for pair in pairs[ways]]
                )
    holm = {arm: holm_adjust(values) for arm, values in fisher.items()}

    rng = random.Random(BOOTSTRAP_SEED)
    rows: list[dict[str, object]] = []
    for ways in range(1, 9):
        split = f"{ways}-{16 - ways}"
        group = pairs[ways]
        for seed, (control, treatment, labels) in zip(PUBLIC_SEEDS, group):
            row: dict[str, object] = {
                "seed_hex": f"0x{seed:08x}", "split": split, "monitor_ways": ways,
                "control_all_hit_fraction": control["all_hit_record_fraction"],
                "treatment_all_hit_fraction": treatment["all_hit_record_fraction"],
                "self_eviction_ok": self_eviction_ok(control, treatment),
            }
            for s in STATISTICS:
                for arm, record in (("control", control), ("treatment", treatment)):
                    p, passed = statistic_fields(record, s)
                    row[f"{arm}_{s}_p"] = p
                    row[f"{arm}_{s}_distinguishable"] = passed
            row["control_max_set_snr"] = control["observed_max_snr"]
            row["treatment_max_set_snr"] = treatment["observed_max_snr"]
            row["control_hit_only_snr"] = control["hit_only_snr"]
            row["treatment_hit_only_snr"] = treatment["hit_only_snr"]
            row["control_delta_per_line"] = control["hit_only_delta_per_line"]
            row["treatment_delta_per_line"] = treatment["hit_only_delta_per_line"]
            row["monitor_ipc_cost_pct"] = percent_cost(
                float(control["ipc_core0"]), float(treatment["ipc_core0"]), higher_is_better=True)
            row["aes_ipc_cost_pct"] = percent_cost(
                float(control["ipc_core1"]), float(treatment["ipc_core1"]), higher_is_better=True)
            row["monitor_llc_miss_delta_pp"] = 100.0 * (
                float(treatment["llc_miss_rate_core0"]) - float(control["llc_miss_rate_core0"]))
            row["aes_llc_miss_delta_pp"] = 100.0 * (
                float(treatment["llc_miss_rate_core1"]) - float(control["llc_miss_rate_core1"]))
            row["aes_cycles_per_encryption_cost_pct"] = percent_cost(
                float(control["aes_cycles_per_encryption"]),
                float(treatment["aes_cycles_per_encryption"]), higher_is_better=False)
            per_seed.append(row)

        pairs_valid = all(self_eviction_ok(c, t) for c, t, _ in group)
        control_valid = {
            s: all(statistic_fields(c, s)[1] for c, _, _ in group)
            and holm["control"][f"{split}|{s}"] < ALPHA
            for s in STATISTICS
        }
        treatment_sig = {s: holm["treatment"][f"{split}|{s}"] < ALPHA for s in STATISTICS}
        runs = [(t["hit_only_interval_means"], labels, ways) for _, t, labels in group]
        low, high = bootstrap_ci(runs, rng)
        control_effect = statistics.mean(float(c["hit_only_delta_per_line"]) for c, _, _ in group)
        treatment_effect = statistics.mean(float(t["hit_only_delta_per_line"]) for _, t, _ in group)
        seed_rows = [r for r in per_seed if r["split"] == split]
        summary: dict[str, object] = {
            "split": split, "monitor_ways": ways, "aes_ways": 16 - ways,
            "self_eviction_pairs_ok": sum(self_eviction_ok(c, t) for c, t, _ in group),
            "control_all_hit_fraction_mean": statistics.mean(
                float(c["all_hit_record_fraction"]) for c, _, _ in group),
            "treatment_all_hit_fraction_mean": statistics.mean(
                float(t["all_hit_record_fraction"]) for _, t, _ in group),
        }
        for s in STATISTICS:
            summary[f"control_{s}_fisher_p"] = fisher["control"][f"{split}|{s}"]
            summary[f"control_{s}_holm_p"] = holm["control"][f"{split}|{s}"]
            summary[f"control_{s}_valid"] = control_valid[s]
            summary[f"treatment_{s}_fisher_p"] = fisher["treatment"][f"{split}|{s}"]
            summary[f"treatment_{s}_holm_p"] = holm["treatment"][f"{split}|{s}"]
            summary[f"treatment_{s}_significant"] = treatment_sig[s]
        summary.update({
            "control_effect_per_line": control_effect,
            "treatment_effect_per_line": treatment_effect,
            "treatment_effect_ci90_low": low,
            "treatment_effect_ci90_high": high,
            "effect_retained_fraction": (
                treatment_effect / control_effect if control_effect else float("nan")),
            "equivalent_within_margin": -EQUIVALENCE_MARGIN < low and high < EQUIVALENCE_MARGIN,
            "conclusion": conclusion(pairs_valid, control_valid, treatment_sig),
        })
        for field in ("monitor_ipc_cost_pct", "aes_ipc_cost_pct", "monitor_llc_miss_delta_pp",
                      "aes_llc_miss_delta_pp", "aes_cycles_per_encryption_cost_pct"):
            values = [float(r[field]) for r in seed_rows]
            summary[f"{field}_mean"] = statistics.mean(values)
            summary[f"{field}_stdev"] = statistics.stdev(values)
        rows.append(summary)
    return per_seed, rows


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot(rows: list[dict[str, object]], per_seed: list[dict[str, object]], root: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = list(range(1, 9))
    labels = [str(r["split"]) for r in rows]
    figure, axes = plt.subplots(2, 1, figsize=(8.2, 7.2), sharex=True, constrained_layout=True)
    for arm, marker in (("control", "o"), ("treatment", "s")):
        means = [statistics.mean(float(r[f"{arm}_delta_per_line"]) for r in per_seed
                                 if r["split"] == split) for split in labels]
        axes[0].plot(x, means, marker=marker,
                     label="Matched unpartitioned control" if arm == "control" else "Partitioned treatment")
    low = [float(r["treatment_effect_ci90_low"]) for r in rows]
    high = [float(r["treatment_effect_ci90_high"]) for r in rows]
    axes[0].fill_between(x, low, high, alpha=0.2, label="Treatment 90% bootstrap CI")
    axes[0].axhspan(-EQUIVALENCE_MARGIN, EQUIVALENCE_MARGIN, color="grey", alpha=0.15,
                    label=f"Equivalence margin +/-{EQUIVALENCE_MARGIN}")
    axes[0].axhline(0, color="black", linewidth=0.8)
    axes[0].set_ylabel("Active - idle hit latency\n(cycles per probed line)")
    axes[0].legend(fontsize=8)
    axes[0].grid(axis="y", alpha=0.3)
    for s, marker in (("max_set", "o"), ("hit_only", "s")):
        axes[1].plot(x, [max(float(r[f"treatment_{s}_holm_p"]), 1e-12) for r in rows],
                     marker=marker, label=f"Treatment, {s.replace('_', '-')}")
    axes[1].axhline(ALPHA, color="black", linestyle="--", label="Holm alpha = 0.05")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Fisher combined, Holm-adjusted p")
    axes[1].set_xlabel("LLC allocation (monitor/AES ways)")
    axes[1].set_xticks(x, labels)
    axes[1].legend(fontsize=8)
    axes[1].grid(axis="y", alpha=0.3)
    figure.savefig(root / "repeated_v2.pdf")
    figure.savefig(root / "repeated_v2.png", dpi=300)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", required=True, type=Path)
    args = parser.parse_args()
    per_seed, rows = aggregate(args.results_root)
    write_csv(per_seed, args.results_root / "per_seed_matched_v2.csv")
    write_csv(rows, args.results_root / "summary_v2.csv")
    summary = {
        "public_workload_seeds": list(PUBLIC_SEEDS),
        "statistics": list(STATISTICS),
        "combination": "Fisher across three workload seeds",
        "multiple_testing": "Holm across 8 allocations x 2 statistics, per arm",
        "alpha": ALPHA,
        "self_eviction_tolerance": SELF_EVICTION_TOLERANCE,
        "equivalence_margin_cycles_per_line": EQUIVALENCE_MARGIN,
        "ci_level": CI_LEVEL,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "stable_collapse_point": stable_point(rows, "conclusion", "indistinguishable"),
        "stable_equivalence_point": stable_point(rows, "equivalent_within_margin", True),
        "rows": rows,
    }
    (args.results_root / "summary_v2.json").write_text(json.dumps(summary, indent=2) + "\n")
    plot(rows, per_seed, args.results_root)
    for row in rows:
        print(f"{row['split']:5s} {row['conclusion']:16s} gate={row['self_eviction_pairs_ok']}/3 "
              f"trt_holm max-set={float(row['treatment_max_set_holm_p']):.3g} "
              f"hit-only={float(row['treatment_hit_only_holm_p']):.3g} "
              f"effect={float(row['treatment_effect_per_line']):+.3f} "
              f"[{float(row['treatment_effect_ci90_low']):+.3f},{float(row['treatment_effect_ci90_high']):+.3f}]")
    print(f"stable_collapse_point={summary['stable_collapse_point']}")
    print(f"stable_equivalence_point={summary['stable_equivalence_point']}")


if __name__ == "__main__":
    try:
        main()
    except SummaryError as exc:
        raise SystemExit(f"error: {exc}") from exc
