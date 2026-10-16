#!/usr/bin/env python3
"""Compare the October 1 (v1) and record-free (v2) repeated studies.

Reads only:
  results/contention-repeated-20261001/summary_repeated.csv   (v1, predeclared)
  results/posthoc-20261011/posthoc_summary.csv                (v1, post-hoc hit-only)
  results/updated run/sweep/summary_v2.csv                    (v2, preregistered)
Writes only under results/updated run/comparison/.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def build_rows(v1: Path, posthoc: Path, v2: Path) -> list[dict[str, object]]:
    v1_rows = {r["split"]: r for r in read_csv(v1)}
    ph = {(r["split"], r["mode"]): r for r in read_csv(posthoc)}
    v2_rows = {r["split"]: r for r in read_csv(v2)}
    rows = []
    for ways in range(1, 9):
        split = f"{ways}-{16 - ways}"
        a, b = v1_rows[split], v2_rows[split]
        c1, t1 = ph[(split, "control")], ph[(split, "partitioned")]
        rows.append({
            "split": split,
            "v1_control_all_hit": float(c1["all_hit_record_fraction_mean"]),
            "v1_treatment_all_hit": float(t1["all_hit_record_fraction_mean"]),
            "v2_control_all_hit": float(b["control_all_hit_fraction_mean"]),
            "v2_treatment_all_hit": float(b["treatment_all_hit_fraction_mean"]),
            "v2_self_eviction_pairs_ok": int(b["self_eviction_pairs_ok"]),
            "v1_monitor_llc_miss_delta_pp": float(a["monitor_llc_miss_delta_pp_mean"]),
            "v2_monitor_llc_miss_delta_pp": float(b["monitor_llc_miss_delta_pp_mean"]),
            "v1_control_max_set_holm_p": float(a["control_holm_p"]),
            "v2_control_max_set_holm_p": float(b["control_max_set_holm_p"]),
            "v1_treatment_max_set_holm_p": float(a["partitioned_holm_p"]),
            "v2_treatment_max_set_holm_p": float(b["treatment_max_set_holm_p"]),
            "v1_posthoc_treatment_hit_only_holm_p": float(t1["h1_hit_only_holm_p"]),
            "v2_treatment_hit_only_holm_p": float(b["treatment_hit_only_holm_p"]),
            "v1_control_effect_per_line": float(c1["h1_hit_only_delta_mean"]),
            "v1_treatment_effect_per_line": float(t1["h1_hit_only_delta_mean"]),
            "v2_control_effect_per_line": float(b["control_effect_per_line"]),
            "v2_treatment_effect_per_line": float(b["treatment_effect_per_line"]),
            "v2_treatment_effect_ci90": (
                f"[{float(b['treatment_effect_ci90_low']):+.3f}, "
                f"{float(b['treatment_effect_ci90_high']):+.3f}]"),
            "v1_conclusion_max_set_rule": a["conclusion"],
            "v2_conclusion": b["conclusion"],
            "v2_equivalent_within_margin": b["equivalent_within_margin"],
            "v1_monitor_ipc_cost_pct": float(a["monitor_ipc_cost_pct_mean"]),
            "v2_monitor_ipc_cost_pct": float(b["monitor_ipc_cost_pct_mean"]),
            "v1_aes_cycles_per_encryption_cost_pct": float(a["aes_cycles_per_encryption_cost_pct_mean"]),
            "v2_aes_cycles_per_encryption_cost_pct": float(b["aes_cycles_per_encryption_cost_pct_mean"]),
        })
    return rows


def plot(rows: list[dict[str, object]], out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = list(range(1, 9))
    labels = [str(r["split"]) for r in rows]
    fig, axes = plt.subplots(3, 1, figsize=(8.2, 10), sharex=True, constrained_layout=True)
    for key, name, style in (("v1_treatment_all_hit", "v1 treatment", "s--"),
                             ("v2_treatment_all_hit", "v2 treatment", "s-"),
                             ("v1_control_all_hit", "v1 control", "o--"),
                             ("v2_control_all_hit", "v2 control", "o-")):
        axes[0].plot(x, [100 * float(r[key]) for r in rows], style, label=name)
    axes[0].set_ylabel("All-hit probe walks (%)")
    axes[0].set_title("Self-eviction: share of probe walks with no LLC miss")
    for key, name, style in (("v1_control_effect_per_line", "v1 control", "o--"),
                             ("v1_treatment_effect_per_line", "v1 treatment (post-hoc)", "s--"),
                             ("v2_control_effect_per_line", "v2 control", "o-"),
                             ("v2_treatment_effect_per_line", "v2 treatment", "s-")):
        axes[1].plot(x, [float(r[key]) for r in rows], style, label=name)
    axes[1].axhline(0, color="black", linewidth=0.8)
    axes[1].set_ylabel("Active - idle hit latency\n(cycles per probed line)")
    axes[1].set_title("Hit-timing signal")
    for key, name, style in (("v1_treatment_max_set_holm_p", "v1 treatment, max-set", "s--"),
                             ("v2_treatment_max_set_holm_p", "v2 treatment, max-set", "s-"),
                             ("v1_posthoc_treatment_hit_only_holm_p", "v1 treatment, hit-only (post-hoc)", "^--"),
                             ("v2_treatment_hit_only_holm_p", "v2 treatment, hit-only", "^-")):
        axes[2].plot(x, [max(float(r[key]), 1e-12) for r in rows], style, label=name)
    axes[2].axhline(0.05, color="black", linestyle=":", label="alpha = 0.05")
    axes[2].set_yscale("log")
    axes[2].set_ylabel("Fisher + Holm p")
    axes[2].set_title("Treatment tests")
    axes[2].set_xlabel("LLC allocation (monitor/AES ways)")
    axes[2].set_xticks(x, labels)
    for ax in axes:
        ax.grid(axis="y", alpha=0.3)
        ax.legend(fontsize=7)
    fig.savefig(out / "comparison_v1_v2.png", dpi=200)
    fig.savefig(out / "comparison_v1_v2.pdf")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--v1", type=Path, default=Path("results/contention-repeated-20261001/summary_repeated.csv"))
    parser.add_argument("--posthoc", type=Path, default=Path("results/posthoc-20261011/posthoc_summary.csv"))
    parser.add_argument("--v2", type=Path, default=Path("results/updated run/sweep/summary_v2.csv"))
    parser.add_argument("--out", type=Path, default=Path("results/updated run/comparison"))
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"error: refusing to overwrite existing {args.out}")
    rows = build_rows(args.v1, args.posthoc, args.v2)
    args.out.mkdir(parents=True)
    with (args.out / "comparison_v1_v2.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    plot(rows, args.out)
    for r in rows:
        print(f"{r['split']:5s} all-hit trt v1={100*r['v1_treatment_all_hit']:.1f}% v2={100*r['v2_treatment_all_hit']:.2f}% | "
              f"effect ctrl v1={r['v1_control_effect_per_line']:+.3f} v2={r['v2_control_effect_per_line']:+.3f} "
              f"trt v1={r['v1_treatment_effect_per_line']:+.3f} v2={r['v2_treatment_effect_per_line']:+.3f} {r['v2_treatment_effect_ci90']} | "
              f"{r['v1_conclusion_max_set_rule']} -> {r['v2_conclusion']}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
