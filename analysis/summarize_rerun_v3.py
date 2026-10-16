#!/usr/bin/env python3
"""Combined updated-run summary after deviation D2.

* Allocations 1/15..6/10: the updated-run sweep (v2 monitor), read only.
* Allocations 7/9 and 8/8: the v3 rerun (way count and fd in registers).
* Self-eviction gate (D2): fraction of probe walks more than MISS_BAND_CYCLES
  above the run's 1st-percentile walk time (a full LLC miss adds ~120
  cycles); |treatment - control| <= SELF_EVICTION_TOLERANCE in every seed
  pair.  The original 20-cycle proxy also counted AES-driven 20-100 cycle
  contention delays, i.e. the signal being measured.  Both gates are reported.
* Everything else is the preregistered v2 rule: two co-primary statistics,
  Fisher across seeds, Holm across 8 allocations x 2 statistics per arm,
  90% bootstrap CI and +/-0.02 cycles/line equivalence margin.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.analyze_contention import PROBE_BIN_RECORD, percentile  # noqa: E402
from analysis.summarize_repeated_contention import (  # noqa: E402
    fisher_combined_p, holm_adjust, percent_cost,
)
from analysis.summarize_repeated_contention_v2 import (  # noqa: E402
    ALPHA, BOOTSTRAP_SEED, EQUIVALENCE_MARGIN, PUBLIC_SEEDS, STATISTICS,
    SELF_EVICTION_TOLERANCE, bootstrap_ci, conclusion, load_pair,
    self_eviction_ok, stable_point, statistic_fields,
)

MISS_BAND_CYCLES = 100
RERUN_WAYS = (7, 8)


def miss_walk_fraction(run_dir: Path) -> float:
    data = (run_dir / "probes.bin").read_bytes()
    latencies = [PROBE_BIN_RECORD.unpack_from(data, offset)[1]
                 for offset in range(0, len(data), PROBE_BIN_RECORD.size)]
    floor = percentile([float(v) for v in latencies], 1.0)
    return sum(v > floor + MISS_BAND_CYCLES for v in latencies) / len(latencies)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sweep-root", type=Path, default=Path("results/updated run/sweep"))
    parser.add_argument("--rerun-root", type=Path, default=Path("results/updated run/rerun-7-9-8-8"))
    args = parser.parse_args()

    pairs, source, miss = {}, {}, {}
    for ways in range(1, 9):
        root = args.rerun_root if ways in RERUN_WAYS else args.sweep_root
        source[ways] = "v3 rerun" if ways in RERUN_WAYS else "v2 sweep"
        pairs[ways] = [load_pair(root, seed, ways) for seed in PUBLIC_SEEDS]
        miss[ways] = [
            (miss_walk_fraction(root / f"seed-{s:08x}" / f"UNPARTITIONED-A{ways}"),
             miss_walk_fraction(root / f"seed-{s:08x}" / f"{ways}-{16 - ways}"))
            for s in PUBLIC_SEEDS
        ]

    fisher = {"control": {}, "treatment": {}}
    for ways in range(1, 9):
        split = f"{ways}-{16 - ways}"
        for s in STATISTICS:
            for arm, index in (("control", 0), ("treatment", 1)):
                fisher[arm][f"{split}|{s}"] = fisher_combined_p(
                    [statistic_fields(pair[index], s)[0] for pair in pairs[ways]])
    holm = {arm: holm_adjust(values) for arm, values in fisher.items()}

    rng = random.Random(BOOTSTRAP_SEED)
    rows, per_seed = [], []
    for ways in range(1, 9):
        split = f"{ways}-{16 - ways}"
        group = pairs[ways]
        new_gate = [abs(t - c) <= SELF_EVICTION_TOLERANCE for c, t in miss[ways]]
        old_gate = [self_eviction_ok(c, t) for c, t, _ in group]
        for seed, (c, t, _), (mc, mt), ng, og in zip(PUBLIC_SEEDS, group, miss[ways], new_gate, old_gate):
            per_seed.append({
                "seed_hex": f"0x{seed:08x}", "split": split, "source": source[ways],
                "control_miss_walk_fraction": mc, "treatment_miss_walk_fraction": mt,
                "gate_d2_ok": ng,
                "control_all_hit_fraction": c["all_hit_record_fraction"],
                "treatment_all_hit_fraction": t["all_hit_record_fraction"],
                "gate_original_ok": og,
                **{f"{arm}_{s}_p": statistic_fields(r, s)[0]
                   for s in STATISTICS for arm, r in (("control", c), ("treatment", t))},
                "control_delta_per_line": c["hit_only_delta_per_line"],
                "treatment_delta_per_line": t["hit_only_delta_per_line"],
                "monitor_ipc_cost_pct": percent_cost(float(c["ipc_core0"]), float(t["ipc_core0"]), higher_is_better=True),
                "aes_cycles_per_encryption_cost_pct": percent_cost(
                    float(c["aes_cycles_per_encryption"]), float(t["aes_cycles_per_encryption"]), higher_is_better=False),
            })
        control_valid = {s: all(statistic_fields(c, s)[1] for c, _, _ in group)
                         and holm["control"][f"{split}|{s}"] < ALPHA for s in STATISTICS}
        treatment_sig = {s: holm["treatment"][f"{split}|{s}"] < ALPHA for s in STATISTICS}
        low, high = bootstrap_ci([(t["hit_only_interval_means"], labels, ways)
                                  for _, t, labels in group], rng)
        ce = statistics.mean(float(c["hit_only_delta_per_line"]) for c, _, _ in group)
        te = statistics.mean(float(t["hit_only_delta_per_line"]) for _, t, _ in group)
        row = {
            "split": split, "source": source[ways],
            "gate_d2_pairs_ok": sum(new_gate), "gate_original_pairs_ok": sum(old_gate),
            "control_miss_walk_fraction_mean": statistics.mean(c for c, _ in miss[ways]),
            "treatment_miss_walk_fraction_mean": statistics.mean(t for _, t in miss[ways]),
        }
        for s in STATISTICS:
            row[f"control_{s}_holm_p"] = holm["control"][f"{split}|{s}"]
            row[f"control_{s}_valid"] = control_valid[s]
            row[f"treatment_{s}_holm_p"] = holm["treatment"][f"{split}|{s}"]
        row.update({
            "control_effect_per_line": ce, "treatment_effect_per_line": te,
            "treatment_effect_ci90_low": low, "treatment_effect_ci90_high": high,
            "effect_retained_fraction": te / ce,
            "equivalent_within_margin": -EQUIVALENCE_MARGIN < low and high < EQUIVALENCE_MARGIN,
            "conclusion_d2_gate": conclusion(all(new_gate), control_valid, treatment_sig),
            "conclusion_original_gate": conclusion(all(old_gate), control_valid, treatment_sig),
            "monitor_ipc_cost_pct_mean": statistics.mean(
                float(r["monitor_ipc_cost_pct"]) for r in per_seed if r["split"] == split),
            "aes_cycles_per_encryption_cost_pct_mean": statistics.mean(
                float(r["aes_cycles_per_encryption_cost_pct"]) for r in per_seed if r["split"] == split),
        })
        rows.append(row)

    out = args.rerun_root
    for data, name in ((rows, "summary_combined.csv"), (per_seed, "per_seed_combined.csv")):
        with (out / name).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(data[0]))
            writer.writeheader()
            writer.writerows(data)
    summary = {
        "status": "updated run after deviation D2 (see PREREGISTRATION_V2_20261011.md)",
        "sources": {"1-15..6-10": str(args.sweep_root), "7-9, 8-8": str(args.rerun_root)},
        "gate_d2": f"|treatment - control| fraction of walks > floor+{MISS_BAND_CYCLES} cycles <= {SELF_EVICTION_TOLERANCE}",
        "stable_collapse_point": stable_point(rows, "conclusion_d2_gate", "indistinguishable"),
        "stable_equivalence_point": stable_point(rows, "equivalent_within_margin", True),
        "rows": rows,
    }
    (out / "summary_combined.json").write_text(json.dumps(summary, indent=2) + "\n")
    for r in rows:
        print(f"{r['split']:5s} {r['source']:8s} gateD2={r['gate_d2_pairs_ok']}/3 "
              f"(orig {r['gate_original_pairs_ok']}/3) miss c/t={100*r['control_miss_walk_fraction_mean']:.3f}/"
              f"{100*r['treatment_miss_walk_fraction_mean']:.3f}% trt holm ms={r['treatment_max_set_holm_p']:.2g} "
              f"ho={r['treatment_hit_only_holm_p']:.2g} eff {r['control_effect_per_line']:+.3f}->"
              f"{r['treatment_effect_per_line']:+.3f} [{r['treatment_effect_ci90_low']:+.3f},"
              f"{r['treatment_effect_ci90_high']:+.3f}] -> {r['conclusion_d2_gate']}")
    print(f"stable_collapse_point={summary['stable_collapse_point']}")
    print(f"stable_equivalence_point={summary['stable_equivalence_point']}")


if __name__ == "__main__":
    main()
