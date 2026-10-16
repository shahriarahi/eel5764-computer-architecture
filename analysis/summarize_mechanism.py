#!/usr/bin/env python3
"""Analyze the crossbar mechanism study (PREREGISTRATION_MECHANISM_20261014.md).

Hypothesis H-xbar: the active-minus-idle hit-latency shift travels through
the shared L1-to-LLC crossbar request layer (system.l2bus.reqLayer0).

Reads `results/updated run/mech-{std,wid,clk,ide}/` (never writes there) and
writes to --out:

* per_run_mechanism.csv: validation, hit-only effect, occupancy test per run
* per_interval_mechanism.csv: interval occupancy, packets, hit-only mean
* summary_mechanism.csv/.json: per (setting, A, arm) effects with 90% CIs,
  predictions P1-P3, and the preregistered outcome
* mechanism.{png,pdf}: dose-response and per-interval figures

Statistics are the v3 study's, unchanged: the hit-only statistic and its
permutation test (analysis/analyze_contention.py), Fisher across the three
seeds, Holm, and the 90% bootstrap CI with seed 5764
(analysis/summarize_repeated_contention_v2.py).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.analyze_contention import (  # noqa: E402
    BEGIN_STATS, hit_only_test, parse_probe_binary, partition_evidence, permutation_test,
)
from analysis.summarize_repeated_contention import fisher_combined_p, holm_adjust  # noqa: E402
from analysis.summarize_repeated_contention_v2 import (  # noqa: E402
    ALPHA, BOOTSTRAP_SEED, EQUIVALENCE_MARGIN, PUBLIC_SEEDS, bootstrap_ci,
)
from analysis.summarize_rerun_v3 import miss_walk_fraction  # noqa: E402

SETTINGS = ("std", "wid", "clk", "ide")
EXPECTED_MECHANISM = {
    "std": {"stats_per_interval": True},
    "wid": {"l2bus_width": 128, "stats_per_interval": True},
    "clk": {"l2bus_clock": "cpu", "stats_per_interval": True},
    "ide": {"l2bus_width": 512, "l2bus_header_latency": 0, "l2bus_clock": "cpu",
            "stats_per_interval": True},
}
WAYS = (1, 8)
ARMS = ("control", "treatment")
INTERVALS = 64
INTERVAL_TICKS = 1_000_000_000
PARTIAL_REDUCTION = 0.5          # P3 fallback: "partial" needs >= 50% reduction
P2_MIN_SPEARMAN = 0.8
XBAR = "system.l2bus."
PM = "system.llc.partitioning_manager."
KEYS = {
    "occupancy": XBAR + "reqLayer0.occupancy",
    "aes_packets": XBAR + "pktCount_system.cpu1.dcache.mem_side_port::system.llc.cpu_side_port",
    "monitor_packets": XBAR + "pktCount_system.cpu0.dcache.mem_side_port::system.llc.cpu_side_port",
    "writebacks": XBAR + "transDist::WritebackDirty",
}


class MechanismError(RuntimeError):
    pass


def read_stats_blocks(path: Path) -> list[dict[str, float]]:
    """All statistics blocks of a (gzipped) gem5 stats file, numeric values only."""
    opener = gzip.open if path.suffix == ".gz" else open
    blocks: list[dict[str, float]] = []
    current: dict[str, float] | None = None
    with opener(path, "rt") as stream:
        for line in stream:
            if line.startswith(BEGIN_STATS):
                current = {}
                continue
            if line.startswith("---------- End Simulation Statistics"):
                blocks.append(current or {})
                current = None
                continue
            if current is None:
                continue
            parts = line.split()
            if len(parts) >= 2 and (parts[0].startswith(XBAR) or parts[0].startswith(PM)
                                    or parts[0].startswith("system.llc.blocked")):
                try:
                    current[parts[0]] = float(parts[1])
                except ValueError:
                    pass
    return blocks


def spearman(x: list[float], y: list[float]) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        for rank, i in enumerate(order):
            r[i] = float(rank)
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def pearson(x: list[float], y: list[float]) -> float:
    mx, my = statistics.mean(x), statistics.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else float("nan")


def classify(p1: bool, p3: bool, ide_reduction: list[float]) -> str:
    """Preregistered outcome for H-xbar."""
    if p1 and p3:
        return "confirmed"
    if p1 and all(r >= PARTIAL_REDUCTION for r in ide_reduction):
        return "partial"
    return "not supported"


def analyze_run(setting: str, seed: int, ways: int, arm: str, root: Path) -> tuple[dict, list[dict]]:
    name = f"UNPARTITIONED-A{ways}" if arm == "control" else f"{ways}-{16 - ways}"
    d = root / f"seed-{seed:08x}" / name
    meta = json.loads((d / "run_meta.json").read_text())
    if meta.get("monitor_variant") != "v3" or meta.get("mechanism") != EXPECTED_MECHANISM[setting]:
        raise MechanismError(f"{d}: wrong monitor variant or mechanism settings {meta.get('mechanism')}")
    c = meta["contention"]
    labels = [int(v) for v in c["activity_labels"]]
    matrix, labels = parse_probe_binary(d / "probes.bin", expected_labels=labels,
                                        start_cycle=int(c["start_cycle"]),
                                        epoch_cycles=int(c["epoch_cycles"]),
                                        interval_count=int(c["interval_count"]),
                                        set_count=int(c["llc_sets"]))
    hit = hit_only_test(matrix, labels, ways)
    blocks = read_stats_blocks(d / "stats.txt.gz")
    if len(blocks) != INTERVALS + 1:
        raise MechanismError(f"{d}: expected {INTERVALS + 1} stats blocks, found {len(blocks)}")
    blocks = blocks[:INTERVALS]
    simout = (d / "simout.txt").read_text()
    lookups = sum(b.get(PM + "probeAddressLookups", 0) for b in blocks)
    mapping_ok = (lookups > 0 and sum(b.get(PM + "probeMissingVaddr", 0) for b in blocks) == 0
                  and sum(b.get(PM + "probeSetMappingMismatches", 0) for b in blocks) == 0)
    isolation = "n/a"
    if arm == "treatment":
        isolation = ("PASS disjoint (64/64 interval snapshots)"
                     if all(partition_evidence(b, meta["ways"])["isolation_validation"] == "PASS disjoint"
                            for b in blocks) else "FAIL")
    blocked = sum(v for b in blocks for k, v in b.items() if k.startswith("system.llc.blockedCycles"))
    occ = [b.get(KEYS["occupancy"], 0.0) for b in blocks]
    aes = [b.get(KEYS["aes_packets"], 0.0) for b in blocks]
    mon = [b.get(KEYS["monitor_packets"], 0.0) for b in blocks]
    wb = [b.get(KEYS["writebacks"], 0.0) for b in blocks]
    occ_test = permutation_test(occ, labels)
    act = [v for v, l in zip(occ, labels) if l == 1]
    idl = [v for v, l in zip(occ, labels) if l == 0]
    row = {
        "setting": setting, "seed_hex": f"0x{seed:08x}", "monitor_ways": ways, "arm": arm,
        "aes_pass": "aes_self_test=PASS" in simout,
        "monitor_pass": "monitor status=PASS records=16384" in simout,
        "mapping_ok": mapping_ok, "isolation": isolation, "llc_blocked_cycles": blocked,
        "miss_walk_fraction": miss_walk_fraction(d),
        "all_hit_fraction": hit["all_hit_record_fraction"],
        "hit_only_delta_per_line": hit["hit_only_delta_per_line"],
        "hit_only_p": hit["hit_only_p"], "hit_only_distinguishable": hit["hit_only_distinguishable"],
        "occupancy_utilization_mean": statistics.mean(occ) / INTERVAL_TICKS,
        "occupancy_active_minus_idle_ticks": statistics.mean(act) - statistics.mean(idl),
        "occupancy_p": occ_test["empirical_p"],
        "occupancy_vs_hit_mean_pearson": pearson(occ, hit["hit_only_interval_means"]),
        "aes_packets_active_mean": statistics.mean(v for v, l in zip(aes, labels) if l == 1),
        "aes_packets_idle_mean": statistics.mean(v for v, l in zip(aes, labels) if l == 0),
        "ticks_per_aes_packet": sum(occ) / sum(aes) if sum(aes) else float("nan"),
        "_interval_means": hit["hit_only_interval_means"], "_labels": labels,
    }
    intervals = [{"setting": setting, "seed_hex": f"0x{seed:08x}", "monitor_ways": ways, "arm": arm,
                  "interval": i, "label": labels[i], "req_layer_occupancy_ticks": occ[i],
                  "aes_packets": aes[i], "monitor_packets": mon[i], "writebacks": wb[i],
                  "hit_only_interval_mean": hit["hit_only_interval_means"][i]}
                 for i in range(INTERVALS)]
    return row, intervals


def summarize(roots: dict[str, Path], sweep_v3: Path | None = None) -> tuple[list[dict], list[dict], list[dict], dict]:
    runs, intervals = [], []
    for s in SETTINGS:
        for seed in PUBLIC_SEEDS:
            for a in WAYS:
                for arm in ARMS:
                    row, iv = analyze_run(s, seed, a, arm, roots[s])
                    # Sanity check S1: with the default crossbar, per-interval stats dumps must
                    # not perturb the measurement (same output-path length as sweep-v3).
                    row["probes_identical_to_sweep_v3"] = ""
                    if s == "std" and sweep_v3 is not None:
                        name = f"UNPARTITIONED-A{a}" if arm == "control" else f"{a}-{16 - a}"
                        rel = Path(f"seed-{seed:08x}") / name / "probes.bin"
                        row["probes_identical_to_sweep_v3"] = (
                            (roots[s] / rel).read_bytes() == (sweep_v3 / rel).read_bytes())
                    runs.append(row)
                    intervals.extend(iv)
    bad = [r for r in runs if not (r["aes_pass"] and r["monitor_pass"] and r["mapping_ok"]
                                   and r["isolation"] in ("n/a", "PASS disjoint (64/64 interval snapshots)"))]
    if bad:
        raise MechanismError(f"{len(bad)} runs failed validation: "
                             + ", ".join(f"{r['setting']}/{r['seed_hex']}/{r['arm']}A{r['monitor_ways']}" for r in bad))

    cell = lambda s, a, arm: [r for r in runs if (r["setting"], r["monitor_ways"], r["arm"]) == (s, a, arm)]
    occ_fisher = {f"{s}|{a}|{arm}": fisher_combined_p([r["occupancy_p"] for r in cell(s, a, arm)])
                  for s in SETTINGS for a in WAYS for arm in ARMS}
    occ_holm_std = holm_adjust({k: v for k, v in occ_fisher.items() if k.startswith("std|")})
    rng = random.Random(BOOTSTRAP_SEED)
    summary = []
    for s in SETTINGS:
        for a in WAYS:
            for arm in ARMS:
                group = cell(s, a, arm)
                low, high = bootstrap_ci([(r["_interval_means"], r["_labels"], a) for r in group], rng)
                summary.append({
                    "setting": s, "monitor_ways": a, "arm": arm,
                    "effect_per_line": statistics.mean(r["hit_only_delta_per_line"] for r in group),
                    "ci90_low": low, "ci90_high": high,
                    "equivalent_within_margin": -EQUIVALENCE_MARGIN < low and high < EQUIVALENCE_MARGIN,
                    "hit_only_fisher_p": fisher_combined_p([r["hit_only_p"] for r in group]),
                    "req_layer_utilization": statistics.mean(r["occupancy_utilization_mean"] for r in group),
                    "occupancy_active_minus_idle_ticks": statistics.mean(r["occupancy_active_minus_idle_ticks"] for r in group),
                    "occupancy_fisher_p": occ_fisher[f"{s}|{a}|{arm}"],
                    "occupancy_vs_hit_mean_pearson": statistics.mean(r["occupancy_vs_hit_mean_pearson"] for r in group),
                    "ticks_per_aes_packet": statistics.mean(r["ticks_per_aes_packet"] for r in group),
                    "miss_walk_fraction": statistics.mean(r["miss_walk_fraction"] for r in group),
                    "llc_blocked_cycles": sum(r["llc_blocked_cycles"] for r in group),
                })
    get = lambda s, a, arm: next(x for x in summary if (x["setting"], x["monitor_ways"], x["arm"]) == (s, a, arm))
    for x in summary:
        base = get("std", x["monitor_ways"], x["arm"])["effect_per_line"]
        x["reduction_vs_std"] = 1 - x["effect_per_line"] / base if base else float("nan")
    # P1: occupancy higher in AES-active intervals, all four default-crossbar cells.
    p1_cells = {k: (v < ALPHA and get("std", int(k.split("|")[1]), k.split("|")[2])["occupancy_active_minus_idle_ticks"] > 0)
                for k, v in occ_holm_std.items()}
    p1 = all(p1_cells.values())
    # P2: treatment effect falls as request-layer utilization falls (Spearman over 4 settings).
    p2_rho = {a: spearman([get(s, a, "treatment")["req_layer_utilization"] for s in SETTINGS],
                          [get(s, a, "treatment")["effect_per_line"] for s in SETTINGS]) for a in WAYS}
    p2 = all(r >= P2_MIN_SPEARMAN for r in p2_rho.values())
    # P3: near-ideal crossbar makes the treatment effect equivalent to zero at both A.
    p3 = all(get("ide", a, "treatment")["equivalent_within_margin"] for a in WAYS)
    ide_reduction = [get("ide", a, "treatment")["reduction_vs_std"] for a in WAYS]
    result = {
        "status": "mechanism study (PREREGISTRATION_MECHANISM_20261014.md)",
        "P1_occupancy_higher_when_active": {"pass": p1, "holm_p_std": occ_holm_std, "cells": p1_cells},
        "P2_effect_tracks_utilization": {"pass": p2, "spearman_treatment": p2_rho},
        "P3_ideal_crossbar_equivalent_to_zero": {"pass": p3, "ide_treatment_reduction_vs_std": ide_reduction},
        "outcome": classify(p1, p3, ide_reduction),
        "S1_std_probes_identical_to_sweep_v3": sum(r["probes_identical_to_sweep_v3"] is True for r in runs),
        "rows": summary,
    }
    for r in runs:
        r.pop("_interval_means"), r.pop("_labels")
    return runs, intervals, summary, result


def plot(summary: list[dict], intervals: list[dict], out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    for a, marker in zip(WAYS, ("o", "s")):
        for arm, style in zip(ARMS, ("--", "-")):
            pts = [x for x in summary if x["monitor_ways"] == a and x["arm"] == arm]
            xs = [100 * p["req_layer_utilization"] for p in pts]
            ys = [p["effect_per_line"] for p in pts]
            err = [[p["effect_per_line"] - p["ci90_low"] for p in pts], [p["ci90_high"] - p["effect_per_line"] for p in pts]]
            axes[0].errorbar(xs, ys, yerr=err, marker=marker, linestyle=style, capsize=3,
                             label=f"A={a} {'partitioned' if arm == 'treatment' else 'control'}")
            for p, x, y in zip(pts, xs, ys):
                axes[0].annotate(p["setting"], (x, y), fontsize=7, xytext=(3, 3), textcoords="offset points")
    axes[0].axhspan(-EQUIVALENCE_MARGIN, EQUIVALENCE_MARGIN, color="grey", alpha=0.2, label="±0.02 margin")
    axes[0].set_xlabel("Shared request-layer utilization (%)")
    axes[0].set_ylabel("Active − idle hit latency (cycles/line)")
    axes[0].legend(fontsize=7)
    std = [r for r in intervals if r["setting"] == "std" and r["monitor_ways"] == 8 and r["arm"] == "treatment"
           and r["seed_hex"] == f"0x{PUBLIC_SEEDS[0]:08x}"]
    for label, color in ((0, "tab:blue"), (1, "tab:red")):
        pts = [r for r in std if r["label"] == label]
        axes[1].scatter([r["req_layer_occupancy_ticks"] / INTERVAL_TICKS * 100 for r in pts],
                        [r["hit_only_interval_mean"] for r in pts], s=12, color=color,
                        label="AES active" if label else "AES idle")
    axes[1].set_xlabel("Request-layer utilization in the interval (%)")
    axes[1].set_ylabel("Monitor hit-only walk mean (cycles)")
    axes[1].set_title("Default crossbar, 8/8, seed 0x5764A5E5", fontsize=9)
    axes[1].legend(fontsize=8)
    fig.savefig(out / "mechanism.pdf")
    fig.savefig(out / "mechanism.png", dpi=200)
    plt.close(fig)


def write_csv(rows: list[dict], path: Path) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-parent", type=Path, default=Path("results/updated run"))
    parser.add_argument("--out", type=Path, default=Path("results/updated run/mech-summary"))
    parser.add_argument("--sweep-v3", type=Path, default=Path("results/updated run/sweep-v3"))
    args = parser.parse_args()
    roots = {s: args.results_parent / f"mech-{s}" for s in SETTINGS}
    if any(args.out.resolve() == r.resolve() for r in roots.values()):
        raise SystemExit("error: --out must not be an input root")
    runs, intervals, summary, result = summarize(roots, args.sweep_v3)
    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(runs, args.out / "per_run_mechanism.csv")
    write_csv(intervals, args.out / "per_interval_mechanism.csv")
    write_csv(summary, args.out / "summary_mechanism.csv")
    (args.out / "summary_mechanism.json").write_text(json.dumps(result, indent=2) + "\n")
    plot(summary, intervals, args.out)
    for x in summary:
        print(f"{x['setting']} A={x['monitor_ways']} {x['arm']:9s} util={100 * x['req_layer_utilization']:.2f}% "
              f"effect={x['effect_per_line']:+.3f} [{x['ci90_low']:+.3f},{x['ci90_high']:+.3f}] "
              f"red={x['reduction_vs_std']:+.2f} occ_p={x['occupancy_fisher_p']:.2g}")
    print("P1", result["P1_occupancy_higher_when_active"]["pass"],
          "P2", result["P2_effect_tracks_utilization"]["pass"], result["P2_effect_tracks_utilization"]["spearman_treatment"],
          "P3", result["P3_ideal_crossbar_equivalent_to_zero"]["pass"])
    print("outcome:", result["outcome"])


if __name__ == "__main__":
    try:
        main()
    except MechanismError as exc:
        raise SystemExit(f"error: {exc}") from exc
