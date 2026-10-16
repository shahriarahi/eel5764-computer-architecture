#!/usr/bin/env python3
"""Parse gem5 results for the LLC way-partitioning study.

Usage (inside WSL2, from the project root):
    python3 analysis/analyze.py              # all results/<split>/ present
    python3 analysis/analyze.py --require-all  # fail unless all nine exist

Inputs, per configuration directory results/<split>/:
    stats.txt      gem5 statistics; one block per stats dump. run.py resets
                   stats after warm-up and dumps after each of N equal
                   measurement segments, so the LAST block is cumulative over
                   the whole measurement window and earlier blocks are
                   snapshots used only for the occupancy invariant.
    run_meta.json  split, way allocation, config and exit causes (run.py).

Metrics (all SIMULATED, taken from the last stats block):
    IPC, core i         system.cpu<i>.ipc
    LLC miss rate, i    (demandMisses::cpu<i>.inst + demandMisses::cpu<i>.data)
                      / (demandAccesses::cpu<i>.inst + demandAccesses::cpu<i>.data)
                        from system.llc.*. gem5 omits zero-valued vector
                        entries, so a missing entry counts as 0 provided
                        system.llc.demandAccesses::total exists. Zero accesses
                        gives NaN (reported, never silently replaced).

Isolation evidence (DERIVED from gem5 statistics written by
gem5_ext/RequestorPartitionManager):
    wayOccupancy_p<P>::way<W>  valid LLC blocks with partition P in way W,
                               sampled from the tag array at every dump.
    For a split A-B, partition 0 may use ways [0, A), partition 1 [A, 16).
    violations = blocks of p0 outside [0,A) + blocks of p1 outside [A,16)
                 + every block in the 'other' row. Must be 0 at EVERY dump.
    Also required: unmappedLookups == 0, addrPartitionConflicts == 0, and
    both partitions hold > 0 blocks (so the check is not vacuous).
    For UNPARTITIONED (control), sharing is demonstrated when at least one
    way holds blocks of both partitions in the final dump.

Malformed input (missing file, wrong number of dumps, missing required stat)
raises an error naming the file and stat; nothing is estimated or skipped.
"""

import argparse
import csv
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
ORDER = ["UNPARTITIONED", "1-15", "2-14", "3-13", "4-12",
         "5-11", "6-10", "7-9", "8-8"]
ASSOC = 16
PM = "system.llc.partitioning_manager."
BEGIN = "---------- Begin Simulation Statistics ----------"

# Validated categorical slots 1-2 (dataviz reference palette, light mode).
COLOR = {0: "#2a78d6", 1: "#eb6834"}
MARKER = {0: "o", 1: "s"}
TEXT = "#0b0b0b"
TEXT2 = "#52514e"
GRID = "#e4e3df"


class AnalysisError(RuntimeError):
    pass


def parse_stats(path):
    """Return a list of {stat_name: float}, one dict per stats dump."""
    if not os.path.isfile(path):
        raise AnalysisError(f"missing {path}")
    blocks, cur = [], None
    with open(path) as f:
        for line in f:
            if line.startswith(BEGIN):
                cur = {}
                blocks.append(cur)
                continue
            if cur is None or line.startswith("----------"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            try:
                cur[parts[0]] = float(parts[1])
            except ValueError:
                continue  # distribution headers etc.
    if not blocks:
        raise AnalysisError(f"{path}: no statistics blocks")
    return blocks


def need(block, name, path):
    if name not in block:
        raise AnalysisError(f"{path}: required statistic '{name}' missing")
    return block[name]


def occupancy(block, path):
    """Return {row: [16 counts]} for rows p0, p1, other."""
    rows = {}
    for row in ("p0", "p1", "other"):
        keys = [f"{PM}wayOccupancy_{row}::way{w}" for w in range(ASSOC)]
        rows[row] = [block.get(k, 0.0) for k in keys]
    if not any(f"{PM}wayOccupancy_p0::way{w}" in block for w in range(ASSOC)):
        raise AnalysisError(f"{path}: no wayOccupancy statistics found")
    return rows


def allowed_ways(meta):
    if meta["ways"] is None:
        return None
    return (set(meta["ways"]["partition0_core0"]),
            set(meta["ways"]["partition1_core1"]))


def violations(occ, allowed):
    a0, a1 = allowed
    v = sum(c for w, c in enumerate(occ["p0"]) if w not in a0)
    v += sum(c for w, c in enumerate(occ["p1"]) if w not in a1)
    v += sum(occ["other"])
    return int(v)


def miss_rate(block, core, path):
    need(block, "system.llc.demandAccesses::total", path)
    m = sum(block.get(f"system.llc.demandMisses::cpu{core}.{p}", 0.0)
            for p in ("inst", "data"))
    a = sum(block.get(f"system.llc.demandAccesses::cpu{core}.{p}", 0.0)
            for p in ("inst", "data"))
    return (m / a if a > 0 else math.nan), int(m), int(a)


def analyze_one(name):
    d = os.path.join(RESULTS, name)
    stats_path = os.path.join(d, "stats.txt")
    meta_path = os.path.join(d, "run_meta.json")
    if not os.path.isfile(meta_path):
        raise AnalysisError(f"missing {meta_path}")
    with open(meta_path) as f:
        meta = json.load(f)
    blocks = parse_stats(stats_path)
    nseg = meta["config"]["measure_segments"]
    if len(blocks) != nseg:
        raise AnalysisError(f"{stats_path}: {len(blocks)} dumps, "
                            f"expected {nseg}")
    last = blocks[-1]

    allowed = allowed_ways(meta)
    per_dump_viol = ([violations(occupancy(b, stats_path), allowed)
                      for b in blocks] if allowed else None)
    occ_last = occupancy(last, stats_path)
    shared = sum(1 for w in range(ASSOC)
                 if occ_last["p0"][w] > 0 and occ_last["p1"][w] > 0)
    unmapped = int(need(last, PM + "unmappedLookups", stats_path))
    conflicts = int(need(last, PM + "addrPartitionConflicts", stats_path))
    blocks_p = [int(sum(occ_last["p0"])), int(sum(occ_last["p1"]))]

    row = {"split": name,
           "core0_ways": len(allowed[0]) if allowed else "",
           "core1_ways": len(allowed[1]) if allowed else ""}
    for c in (0, 1):
        row[f"ipc_core{c}"] = need(last, f"system.cpu{c}.ipc", stats_path)
        mr, m, a = miss_rate(last, c, stats_path)
        row[f"llc_miss_rate_core{c}"] = mr
        row[f"llc_misses_core{c}"] = m
        row[f"llc_accesses_core{c}"] = a
    row.update({
        "llc_blocks_p0": blocks_p[0],
        "llc_blocks_p1": blocks_p[1],
        "ways_holding_both_partitions": shared,
        "dumps_checked": len(blocks),
        "max_isolation_violations": (max(per_dump_viol)
                                     if per_dump_viol else ""),
        "unmapped_lookups": unmapped,
        "addr_partition_conflicts": conflicts,
        "sim_seconds_measured": need(last, "simSeconds", stats_path),
    })
    if allowed:
        ok = (max(per_dump_viol) == 0 and unmapped == 0 and conflicts == 0
              and min(blocks_p) > 0)
        row["validation"] = "PASS disjoint" if ok else "FAIL"
    else:
        ok = shared > 0 and unmapped == 0 and conflicts == 0
        row["validation"] = ("PASS sharing observed" if ok
                             else "FAIL no sharing observed")
    return row, occ_last


def fmt(v):
    if isinstance(v, float):
        return "nan" if math.isnan(v) else f"{v:.6f}"
    return v


def write_csv(rows):
    path = os.path.join(RESULTS, "summary.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow({k: fmt(v) for k, v in r.items()})
    return path


def style_axes(ax):
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(TEXT2)
    ax.tick_params(colors=TEXT2, labelcolor=TEXT)


def plot_tradeoff(rows, out_base):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = [r["split"] for r in rows]
    x = list(range(len(names)))
    labels = ["Unpart."] + [n.replace("-", "/") for n in names[1:]] \
        if names[0] == "UNPARTITIONED" else [n.replace("-", "/") for n in names]
    fig, axes = plt.subplots(2, 1, figsize=(7.0, 5.6), sharex=True)
    panels = [("ipc_core{}", "IPC (instructions / cycle)",
               "(a) Per-core IPC"),
              ("llc_miss_rate_core{}", "LLC demand miss rate",
               "(b) Per-core LLC miss rate")]
    part = [i for i, n in enumerate(names) if n != "UNPARTITIONED"]
    for ax, (key, ylabel, title) in zip(axes, panels):
        style_axes(ax)
        for c in (0, 1):
            ys = [r[key.format(c)] for r in rows]
            ax.plot([x[i] for i in part], [ys[i] for i in part],
                    color=COLOR[c], linewidth=2, marker=MARKER[c],
                    markersize=6, markeredgecolor="white",
                    markeredgewidth=1.2, zorder=3)
            if "UNPARTITIONED" in names:
                i0 = names.index("UNPARTITIONED")
                ax.plot([x[i0]], [ys[i0]], linestyle="none",
                        marker=MARKER[c], markersize=7, color=COLOR[c],
                        markeredgecolor="white", markeredgewidth=1.2,
                        zorder=3)
            # Direct label at the right end of each series.
            ax.annotate(f"Core {c}", (x[part[-1]], ys[part[-1]]),
                        xytext=(8, 0), textcoords="offset points",
                        va="center", fontsize=9, color=TEXT)
        if "UNPARTITIONED" in names:
            ax.axvline(0.5, color=TEXT2, linewidth=0.8, linestyle=":")
        ax.set_ylabel(ylabel, color=TEXT, fontsize=9)
        ax.set_title(title, loc="left", fontsize=10, color=TEXT)
        ax.set_ylim(bottom=0)
    axes[1].set_ylim(0, 1.05)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=9)
    axes[1].set_xlabel("LLC ways, core 0 / core 1 (16-way shared LLC)",
                       color=TEXT, fontsize=9)
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=COLOR[c], marker=MARKER[c], linewidth=2,
                      label=lbl) for c, lbl in
               ((0, "Core 0: randacc (128 KiB random reuse)"),
                (1, "Core 1: stream (1 MiB sequential)"))]
    fig.legend(handles=handles, loc="upper center", ncol=2, frameon=False,
               fontsize=9, bbox_to_anchor=(0.5, 1.0))
    fig.text(0.01, 0.005, "Simulated (gem5 v25.1.0.1, RISC-V SE, "
             "TimingSimpleCPU); 4 ms measured after 1 ms warm-up.",
             fontsize=7.5, color=TEXT2)
    fig.tight_layout(rect=(0, 0.02, 0.97, 0.95))
    for ext, kw in (("pdf", {}), ("png", {"dpi": 300})):
        fig.savefig(f"{out_base}.{ext}", **kw)
    plt.close(fig)


def plot_occupancy(rows, occs, out_base):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(rows)
    ncol = 3
    nrow = math.ceil(n / ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(7.2, 2.1 * nrow + 0.6),
                             sharex=True, sharey=True, squeeze=False)
    ways = list(range(ASSOC))
    for k, (r, occ) in enumerate(zip(rows, occs)):
        ax = axes[k // ncol][k % ncol]
        style_axes(ax)
        p0, p1 = occ["p0"], occ["p1"]
        ax.bar(ways, p0, width=0.8, color=COLOR[0], edgecolor="white",
               linewidth=1)
        ax.bar(ways, p1, bottom=p0, width=0.8, color=COLOR[1],
               edgecolor="white", linewidth=1)
        if r["core0_ways"] != "":
            ax.axvline(r["core0_ways"] - 0.5, color=TEXT, linewidth=1,
                       linestyle="--")
        title = ("Unpartitioned" if r["split"] == "UNPARTITIONED"
                 else r["split"].replace("-", "/"))
        verdict = r["validation"].split()[0]
        ax.set_title(f"{title}  [{verdict}]", fontsize=9, color=TEXT,
                     loc="left")
        ax.set_ylim(0, 270)
        ax.set_xticks([0, 4, 8, 12, 15])
    for k in range(n, nrow * ncol):
        axes[k // ncol][k % ncol].set_visible(False)
    for a in axes[-1]:
        a.set_xlabel("LLC way", fontsize=9, color=TEXT)
    for a in axes[:, 0]:
        a.set_ylabel("Valid blocks\n(of 256 sets)", fontsize=8, color=TEXT)
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=COLOR[0], label="Partition 0 (core 0)"),
                        Patch(color=COLOR[1], label="Partition 1 (core 1)")],
               loc="upper center", ncol=2, frameon=False, fontsize=9)
    fig.text(0.01, 0.005, "Final stats dump; dashed line = partition "
             "boundary. Derived from gem5 wayOccupancy statistics.",
             fontsize=7.5, color=TEXT2)
    fig.tight_layout(rect=(0, 0.02, 1, 0.96))
    for ext, kw in (("pdf", {}), ("png", {"dpi": 300})):
        fig.savefig(f"{out_base}.{ext}", **kw)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-all", action="store_true",
                    help="fail unless all nine configurations are present")
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args()

    present = [n for n in ORDER if os.path.isdir(os.path.join(RESULTS, n))]
    missing = [n for n in ORDER if n not in present]
    if args.require_all and missing:
        raise AnalysisError(f"missing configurations: {missing}")
    if not present:
        raise AnalysisError(f"no configuration directories in {RESULTS}")

    rows, occs = [], []
    for n in present:
        r, occ = analyze_one(n)
        rows.append(r)
        occs.append(occ)

    csv_path = write_csv(rows)
    print(f"wrote {os.path.relpath(csv_path, ROOT)}")
    for r in rows:
        print(f"{r['split']:>13}  ipc0={r['ipc_core0']:.6f} "
              f"ipc1={r['ipc_core1']:.6f} "
              f"mr0={fmt(r['llc_miss_rate_core0'])} "
              f"mr1={fmt(r['llc_miss_rate_core1'])}  "
              f"viol={r['max_isolation_violations']!s:>2} "
              f"shared_ways={r['ways_holding_both_partitions']:>2} "
              f"unmapped={r['unmapped_lookups']} "
              f"conflicts={r['addr_partition_conflicts']}  "
              f"{r['validation']}")
    if not args.no_plots:
        fig_dir = os.path.join(RESULTS, "figures")
        os.makedirs(fig_dir, exist_ok=True)
        plot_tradeoff(rows, os.path.join(fig_dir, "tradeoff"))
        plot_occupancy(rows, occs, os.path.join(fig_dir, "occupancy"))
        print(f"wrote {os.path.relpath(fig_dir, ROOT)}/"
              "{tradeoff,occupancy}.{pdf,png}")
    if any(r["validation"].startswith("FAIL") for r in rows):
        sys.exit("error: at least one configuration FAILED validation")


if __name__ == "__main__":
    try:
        main()
    except AnalysisError as e:
        sys.exit(f"error: {e}")
