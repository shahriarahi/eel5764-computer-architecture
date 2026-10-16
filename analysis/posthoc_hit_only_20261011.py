#!/usr/bin/env python3
"""POST-HOC, EXPLORATORY re-analysis of the repeated contention study.

This script was written on 2026-10-11, after the repeated study's results were
seen.  It does not replace the predeclared max-set decision rule.  It reads the
raw probe records of the 48 matched runs (read-only) and asks:

  H1  Hit-only interval mean: after removing probe records slower than the
      run's all-hit walk time, does the per-interval mean latency still differ
      between AES-active and AES-idle intervals?
  H2  Set-centred hit-only mean: as H1, but each set's hit latency is first
      centred on that set's own mean, so changing set composition cannot
      create a shift.
  H3  Miss count: does the number of slow (miss) records per interval differ
      between active and idle intervals?
  H4  Unfiltered interval mean (the study's original statistic).

The miss filter uses a run-wide latency threshold that never looks at the
labels, so a label-permutation test on the filtered series remains valid.
Every test uses 10,000 balanced label shuffles from random.Random(5764),
matching analysis/analyze_contention.py, and reports a two-sided p-value.
Fisher combination across seeds and Holm correction across the eight
allocations mirror analysis/summarize_repeated_contention.py.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from pathlib import Path

import numpy as np


PUBLIC_SEEDS = (0x5764A5E5, 0x5764A5E6, 0x5764A5E7)
PERMUTATIONS = 10_000
ANALYSIS_SEED = 5_764
HIT_BAND_CYCLES = 20  # well below one LLC miss (~120 cycles)
INTERVALS = 64
SETS = 256


def load_run(directory: Path) -> tuple[np.ndarray, np.ndarray]:
    meta = json.loads((directory / "run_meta.json").read_text())
    labels = np.array(meta["contention"]["activity_labels"], dtype=int)
    matrix = np.full((INTERVALS, SETS), np.nan)
    for line in (directory / "simout.txt").read_text().splitlines():
        if line.startswith("probe,"):
            _, _, interval, label, cache_set, latency = line.split(",")
            if int(label) != labels[int(interval)]:
                raise SystemExit(f"{directory}: label mismatch")
            matrix[int(interval), int(cache_set)] = int(latency)
    if np.isnan(matrix).any():
        raise SystemExit(f"{directory}: missing probe records")
    return matrix, labels


def permutation_matrix(labels: np.ndarray) -> np.ndarray:
    rng = random.Random(ANALYSIS_SEED)
    shuffled = labels.tolist()
    rows = []
    for _ in range(PERMUTATIONS):
        rng.shuffle(shuffled)
        rows.append(list(shuffled))
    return np.array(rows, dtype=float)


def signed_snr(series: np.ndarray, label_rows: np.ndarray) -> np.ndarray:
    active_n = label_rows.sum(axis=1)
    idle_n = label_rows.shape[1] - active_n
    a_sum = label_rows @ series
    a_sq = label_rows @ (series**2)
    i_sum = series.sum() - a_sum
    i_sq = (series**2).sum() - a_sq
    a_var = (a_sq - a_sum**2 / active_n) / (active_n - 1)
    i_var = (i_sq - i_sum**2 / idle_n) / (idle_n - 1)
    pooled = ((active_n - 1) * a_var + (idle_n - 1) * i_var) / (active_n + idle_n - 2)
    return (a_sum / active_n - i_sum / idle_n) / np.sqrt(pooled)


def test(series: np.ndarray, labels: np.ndarray, perms: np.ndarray) -> tuple[float, float]:
    observed = float(signed_snr(series, labels[None, :].astype(float))[0])
    null = np.abs(signed_snr(series, perms))
    p_value = (1 + int((null >= abs(observed)).sum())) / (PERMUTATIONS + 1)
    return observed, p_value


def fisher(p_values: list[float]) -> float:
    half = -sum(math.log(p) for p in p_values)
    return min(1.0, math.exp(-half) * sum(half**k / math.factorial(k) for k in range(len(p_values))))


def holm(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted, running = {}, 0.0
    for rank, (key, value) in enumerate(ordered):
        running = max(running, (len(ordered) - rank) * value)
        adjusted[key] = min(1.0, running)
    return adjusted


def analyze_run(directory: Path, ways: int, perms_cache: dict) -> dict[str, float]:
    matrix, labels = load_run(directory)
    key = labels.tobytes()
    if key not in perms_cache:
        perms_cache[key] = permutation_matrix(labels)
    perms = perms_cache[key]

    floor = float(np.percentile(matrix, 1))
    hit = matrix <= floor + HIT_BAND_CYCLES
    hit_only = np.array([matrix[i][hit[i]].mean() for i in range(INTERVALS)])
    set_means = np.array([matrix[:, s][hit[:, s]].mean() for s in range(SETS)])
    centred = np.where(hit, matrix - set_means[None, :], np.nan)
    centred_series = np.nanmean(centred, axis=1)
    miss_count = (~hit).sum(axis=1).astype(float)
    unfiltered = matrix.mean(axis=1)

    result: dict[str, float] = {
        "all_hit_walk_cycles": floor,
        "all_hit_record_fraction": float(hit.mean()),
        "mean_record_cycles": float(matrix.mean()),
        "miss_records_per_interval": float(miss_count.mean()),
        "miss_count_period8_repeat_fraction": float(
            np.mean(miss_count[8:] == miss_count[:-8])
        ),
    }
    for name, series in (
        ("h1_hit_only", hit_only),
        ("h2_set_centred", centred_series),
        ("h3_miss_count", miss_count),
        ("h4_unfiltered", unfiltered),
    ):
        snr_value, p_value = test(series, labels, perms)
        delta = series[labels == 1].mean() - series[labels == 0].mean()
        result[f"{name}_snr"] = snr_value
        result[f"{name}_p"] = p_value
        result[f"{name}_delta"] = float(delta if name == "h3_miss_count" else delta / ways)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", type=Path, default=Path("results/contention-repeated-20261001"))
    parser.add_argument("--out", type=Path, default=Path("results/posthoc-20261011"))
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"error: refusing to overwrite existing {args.out}")

    perms_cache: dict = {}
    per_run: list[dict[str, object]] = []
    for seed in PUBLIC_SEEDS:
        for ways in range(1, 9):
            for mode, name in (("control", f"UNPARTITIONED-A{ways}"), ("partitioned", f"{ways}-{16 - ways}")):
                directory = args.results_root / f"seed-{seed:08x}" / name
                row: dict[str, object] = {
                    "seed_hex": f"0x{seed:08x}", "split": f"{ways}-{16 - ways}",
                    "monitor_ways": ways, "mode": mode,
                }
                row.update(analyze_run(directory, ways, perms_cache))
                per_run.append(row)
                print(f"{row['seed_hex']} {row['split']:5s} {mode:11s} "
                      f"hit%={100 * row['all_hit_record_fraction']:5.1f} "
                      f"H1 snr={row['h1_hit_only_snr']:+6.2f} p={row['h1_hit_only_p']:.4f} "
                      f"d={row['h1_hit_only_delta']:+.3f} cyc/line", flush=True)

    summary: list[dict[str, object]] = []
    combined: dict[tuple[str, str], dict[str, float]] = {}
    for mode in ("control", "partitioned"):
        for test_name in ("h1_hit_only", "h2_set_centred", "h3_miss_count", "h4_unfiltered"):
            fisher_p = {
                f"{w}-{16 - w}": fisher([float(r[f"{test_name}_p"]) for r in per_run
                                         if r["mode"] == mode and r["monitor_ways"] == w])
                for w in range(1, 9)
            }
            combined[(mode, test_name)] = {"fisher": fisher_p, "holm": holm(fisher_p)}
    for ways in range(1, 9):
        split = f"{ways}-{16 - ways}"
        for mode in ("control", "partitioned"):
            group = [r for r in per_run if r["mode"] == mode and r["monitor_ways"] == ways]
            row = {"split": split, "mode": mode,
                   "all_hit_record_fraction_mean": float(np.mean([r["all_hit_record_fraction"] for r in group])),
                   "miss_records_per_interval_mean": float(np.mean([r["miss_records_per_interval"] for r in group]))}
            for test_name in ("h1_hit_only", "h2_set_centred", "h3_miss_count", "h4_unfiltered"):
                row[f"{test_name}_snr_mean"] = float(np.mean([r[f"{test_name}_snr"] for r in group]))
                row[f"{test_name}_delta_mean"] = float(np.mean([r[f"{test_name}_delta"] for r in group]))
                row[f"{test_name}_individual_p_lt_0.05"] = sum(float(r[f"{test_name}_p"]) < 0.05 for r in group)
                row[f"{test_name}_fisher_p"] = combined[(mode, test_name)]["fisher"][split]
                row[f"{test_name}_holm_p"] = combined[(mode, test_name)]["holm"][split]
            summary.append(row)

    args.out.mkdir(parents=True)
    for rows, filename in ((per_run, "posthoc_per_run.csv"), (summary, "posthoc_summary.csv")):
        with (args.out / filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (args.out / "posthoc_summary.json").write_text(json.dumps({
        "status": "POST-HOC EXPLORATORY; does not replace the predeclared max-set rule",
        "source_root": str(args.results_root),
        "hit_band_cycles_above_1st_percentile": HIT_BAND_CYCLES,
        "permutations": PERMUTATIONS, "analysis_seed": ANALYSIS_SEED,
        "rows": summary,
    }, indent=2) + "\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
