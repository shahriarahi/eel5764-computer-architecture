#!/usr/bin/env python3
"""Summarize the full v3 sweep (deviation D3): one root, one monitor build.

Decision rule = preregistered v2 rule with the D2 self-eviction gate:
fraction of probe walks more than 100 cycles above the run's 1st-percentile
walk, |treatment - control| <= 0.01 in every seed pair.  The original 20-cycle
gate is reported alongside.  Two co-primary statistics, Fisher across seeds,
Holm across 8 allocations x 2 statistics per arm, 90% bootstrap CI,
+/-0.02 cycles/line equivalence margin.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.summarize_repeated_contention import (  # noqa: E402
    fisher_combined_p, holm_adjust, percent_cost,
)
from analysis.summarize_repeated_contention_v2 import (  # noqa: E402
    ALPHA, BOOTSTRAP_SEED, EQUIVALENCE_MARGIN, PUBLIC_SEEDS, STATISTICS,
    SELF_EVICTION_TOLERANCE, SummaryError, bootstrap_ci, conclusion, load_pair,
    plot, self_eviction_ok, stable_point, statistic_fields,
)
from analysis.summarize_rerun_v3 import MISS_BAND_CYCLES, miss_walk_fraction  # noqa: E402

COST_FIELDS = {
    "monitor_ipc_cost_pct": ("ipc_core0", True),
    "aes_ipc_cost_pct": ("ipc_core1", True),
    "aes_cycles_per_encryption_cost_pct": ("aes_cycles_per_encryption", False),
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", type=Path, default=Path("results/updated run/sweep-v3"))
    args = parser.parse_args()
    root = args.results_root

    pairs, miss = {}, {}
    for ways in range(1, 9):
        pairs[ways] = [load_pair(root, seed, ways) for seed in PUBLIC_SEEDS]
        miss[ways] = []
        for seed in PUBLIC_SEEDS:
            dirs = [root / f"seed-{seed:08x}" / name
                    for name in (f"UNPARTITIONED-A{ways}", f"{ways}-{16 - ways}")]
            for d in dirs:
                if json.loads((d / "run_meta.json").read_text()).get("monitor_variant") != "v3":
                    raise SummaryError(f"{d}: not a v3 monitor run")
            miss[ways].append(tuple(miss_walk_fraction(d) for d in dirs))

    fisher = {"control": {}, "treatment": {}}
    for ways in range(1, 9):
        split = f"{ways}-{16 - ways}"
        for s in STATISTICS:
            for arm, index in (("control", 0), ("treatment", 1)):
                fisher[arm][f"{split}|{s}"] = fisher_combined_p(
                    [statistic_fields(p[index], s)[0] for p in pairs[ways]])
    holm = {arm: holm_adjust(v) for arm, v in fisher.items()}

    rng = random.Random(BOOTSTRAP_SEED)
    rows, per_seed = [], []
    for ways in range(1, 9):
        split = f"{ways}-{16 - ways}"
        group = pairs[ways]
        gate = [abs(t - c) <= SELF_EVICTION_TOLERANCE for c, t in miss[ways]]
        orig = [self_eviction_ok(c, t) for c, t, _ in group]
        seed_rows = []
        for seed, (c, t, _), (mc, mt), g, o in zip(PUBLIC_SEEDS, group, miss[ways], gate, orig):
            row = {"seed_hex": f"0x{seed:08x}", "split": split,
                   "control_miss_walk_fraction": mc, "treatment_miss_walk_fraction": mt,
                   "gate_d2_ok": g,
                   "control_all_hit_fraction": c["all_hit_record_fraction"],
                   "treatment_all_hit_fraction": t["all_hit_record_fraction"],
                   "gate_original_ok": o}
            for s in STATISTICS:
                for arm, r in (("control", c), ("treatment", t)):
                    row[f"{arm}_{s}_p"] = statistic_fields(r, s)[0]
            row["control_delta_per_line"] = c["hit_only_delta_per_line"]
            row["treatment_delta_per_line"] = t["hit_only_delta_per_line"]
            for name, (field, higher) in COST_FIELDS.items():
                row[name] = percent_cost(float(c[field]), float(t[field]), higher_is_better=higher)
            row["monitor_llc_miss_delta_pp"] = 100 * (float(t["llc_miss_rate_core0"]) - float(c["llc_miss_rate_core0"]))
            row["aes_llc_miss_delta_pp"] = 100 * (float(t["llc_miss_rate_core1"]) - float(c["llc_miss_rate_core1"]))
            seed_rows.append(row)
        per_seed.extend(seed_rows)

        valid = {s: all(statistic_fields(c, s)[1] for c, _, _ in group)
                 and holm["control"][f"{split}|{s}"] < ALPHA for s in STATISTICS}
        sig = {s: holm["treatment"][f"{split}|{s}"] < ALPHA for s in STATISTICS}
        low, high = bootstrap_ci([(t["hit_only_interval_means"], labels, ways)
                                  for _, t, labels in group], rng)
        ce = statistics.mean(float(c["hit_only_delta_per_line"]) for c, _, _ in group)
        te = statistics.mean(float(t["hit_only_delta_per_line"]) for _, t, _ in group)
        summary = {"split": split, "monitor_ways": ways, "aes_ways": 16 - ways,
                   "gate_d2_pairs_ok": sum(gate), "gate_original_pairs_ok": sum(orig),
                   "control_miss_walk_fraction_mean": statistics.mean(c for c, _ in miss[ways]),
                   "treatment_miss_walk_fraction_mean": statistics.mean(t for _, t in miss[ways]),
                   "control_all_hit_fraction_mean": statistics.mean(float(r["control_all_hit_fraction"]) for r in seed_rows),
                   "treatment_all_hit_fraction_mean": statistics.mean(float(r["treatment_all_hit_fraction"]) for r in seed_rows)}
        for s in STATISTICS:
            summary[f"control_{s}_fisher_p"] = fisher["control"][f"{split}|{s}"]
            summary[f"control_{s}_holm_p"] = holm["control"][f"{split}|{s}"]
            summary[f"control_{s}_valid"] = valid[s]
            summary[f"treatment_{s}_fisher_p"] = fisher["treatment"][f"{split}|{s}"]
            summary[f"treatment_{s}_holm_p"] = holm["treatment"][f"{split}|{s}"]
            summary[f"treatment_{s}_significant"] = sig[s]
        summary.update({
            "control_effect_per_line": ce, "treatment_effect_per_line": te,
            "treatment_effect_ci90_low": low, "treatment_effect_ci90_high": high,
            "effect_retained_fraction": te / ce if ce else float("nan"),
            "equivalent_within_margin": -EQUIVALENCE_MARGIN < low and high < EQUIVALENCE_MARGIN,
            "conclusion": conclusion(all(gate), valid, sig),
            "conclusion_original_gate": conclusion(all(orig), valid, sig),
        })
        for name in list(COST_FIELDS) + ["monitor_llc_miss_delta_pp", "aes_llc_miss_delta_pp"]:
            values = [float(r[name]) for r in seed_rows]
            summary[f"{name}_mean"] = statistics.mean(values)
            summary[f"{name}_stdev"] = statistics.stdev(values)
        rows.append(summary)

    for data, name in ((rows, "summary_v3.csv"), (per_seed, "per_seed_matched_v3.csv")):
        with (root / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    result = {
        "status": "full v3 sweep (deviation D3, PREREGISTRATION_V2_20261011.md)",
        "gate": f"|treatment - control| fraction of walks > floor+{MISS_BAND_CYCLES} cycles <= {SELF_EVICTION_TOLERANCE}",
        "stable_collapse_point": stable_point(rows, "conclusion", "indistinguishable"),
        "stable_equivalence_point": stable_point(rows, "equivalent_within_margin", True),
        "rows": rows,
    }
    (root / "summary_v3.json").write_text(json.dumps(result, indent=2) + "\n")
    plot(rows, per_seed, root)  # writes repeated_v2.{pdf,png}; renamed below
    for ext in ("pdf", "png"):
        os.replace(root / f"repeated_v2.{ext}", root / f"repeated_v3.{ext}")
    for r in rows:
        print(f"{r['split']:5s} {r['conclusion']:16s} gate={r['gate_d2_pairs_ok']}/3 "
              f"(orig {r['gate_original_pairs_ok']}/3) trt holm ms={r['treatment_max_set_holm_p']:.2g} "
              f"ho={r['treatment_hit_only_holm_p']:.2g} eff {r['control_effect_per_line']:+.3f}->"
              f"{r['treatment_effect_per_line']:+.3f} [{r['treatment_effect_ci90_low']:+.3f},"
              f"{r['treatment_effect_ci90_high']:+.3f}] ret={r['effect_retained_fraction']:.2f}")
    print(f"stable_collapse_point={result['stable_collapse_point']}")
    print(f"stable_equivalence_point={result['stable_equivalence_point']}")


if __name__ == "__main__":
    try:
        main()
    except SummaryError as exc:
        raise SystemExit(f"error: {exc}") from exc
