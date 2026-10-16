#!/usr/bin/env python3
"""Presentation figures for the crossbar mechanism study.

Reads (never writes) `results/updated run/mech-summary/summary_mechanism.csv`,
the output of the preregistered analysis/summarize_mechanism.py, and the raw
`probes.bin` of two 1/15 runs.  Writes to `results/updated run/mech-figures/`:

* fig_mechanism_paper.png  IEEE single-column Fig. 2 (3.5 in wide, 300 dpi)
* slide_dose_response.png  16:9 slide versions of the two panels
* slide_latency_histogram.png

Purely presentational: no statistic is computed here that is not already in
the preregistered summary, except the walk-latency histogram (a direct count).
Palette: reference categorical slots 1-3 (blue, orange, aqua), validated with
the dataviz skill's validator in light mode; idle bars use a neutral gray.
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

SERIES = {1: "#2a78d6", 8: "#eb6834"}     # categorical slots 1, 2
ACTIVE, IDLE = "#1baf7a", "#a3a29c"       # slot 3; neutral gray
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SETTING_NAMES = {"std": "default", "wid": "wider", "clk": "2 GHz", "ide": "near-ideal"}
PROBE = np.dtype([("ts", "<u8"), ("lat", "<u4"), ("iv", "<u2"), ("set", "<u2")])
DELAYS = list(range(-2, 9))


def load_summary(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open()))


def delay_counts(run: Path) -> dict[str, collections.Counter]:
    """Hit-walk latency minus the idle mode, split by activity label."""
    rec = np.fromfile(run / "probes.bin", dtype=PROBE)
    labels = np.array(json.loads((run / "run_meta.json").read_text())["contention"]["activity_labels"])
    active = labels[rec["iv"]] == 1
    base = collections.Counter(rec["lat"][~active].tolist()).most_common(1)[0][0]
    delay = rec["lat"].astype(int) - base
    return {name: collections.Counter(delay[mask & (np.abs(delay) <= 8)].tolist())
            for name, mask in (("idle", ~active), ("active", active))}


def style(ax, size: float) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
        ax.spines[side].set_linewidth(0.6)
    ax.tick_params(colors=INK2, labelsize=size, width=0.6, length=2.5)
    ax.yaxis.label.set_color(INK)
    ax.xaxis.label.set_color(INK)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def dose_response(ax, rows: list[dict], size: float) -> None:
    ax.axhspan(-0.02, 0.02, color="#efeeea", zorder=0)
    ax.text(7.5, 0.0, "±0.02 equivalence margin", fontsize=size - 1, color=INK2, va="center", ha="right")
    # Setting names sit above the 8/8 control points, offset away from the lines.
    label_offsets = {"std": (0, 1.1, "center"), "wid": (-0.4, 0.9, "right"),
                     "clk": (-0.9, 1.1, "right"), "ide": (0, 1.6, "center")}
    for ways in (1, 8):
        for arm, dash, fill in (("control", (0, (3, 2)), "white"), ("treatment", "solid", SERIES[ways])):
            pts = sorted((r for r in rows if int(r["monitor_ways"]) == ways and r["arm"] == arm),
                         key=lambda r: float(r["req_layer_utilization"]))
            x = [100 * float(r["req_layer_utilization"]) for r in pts]
            y = [float(r["effect_per_line"]) for r in pts]
            err = [[v - float(r["ci90_low"]) for v, r in zip(y, pts)],
                   [float(r["ci90_high"]) - v for v, r in zip(y, pts)]]
            ax.errorbar(x, y, yerr=err, color=SERIES[ways], linestyle=dash, linewidth=1.4,
                        marker="o", markersize=size * 0.75, markerfacecolor=fill, markeredgewidth=1.2,
                        capsize=0, zorder=3,
                        label=f"{ways}/{16 - ways} {'partitioned' if arm == 'treatment' else 'control'}")
            if arm == "control" and ways == 8:        # name each crossbar setting once
                for r, xi, yi in zip(pts, x, y):
                    dx, dy, ha = label_offsets[r["setting"]]
                    ax.annotate(SETTING_NAMES[r["setting"]], (xi, yi), xytext=(dx * size, dy * size),
                                textcoords="offset points", ha=ha, fontsize=size - 1, color=INK2)
    ax.set_xlabel("Shared request-layer utilization (%)", fontsize=size)
    ax.set_ylabel("Leak: active − idle\n(cycles per probed line)", fontsize=size)
    ax.set_xlim(0, 7.6)
    ax.set_ylim(-0.04, 0.44)
    ax.legend(fontsize=size - 1, frameon=False, loc="upper left", labelcolor=INK)
    style(ax, size)


def histogram(ax, counts: dict[str, collections.Counter], title: str, size: float, ylabel: bool,
              xlabel: bool = True) -> None:
    width = 0.4
    for offset, name, color in ((-width / 2, "idle", IDLE), (width / 2, "active", ACTIVE)):
        total = sum(counts[name].values())
        share = [100 * counts[name].get(d, 0) / total for d in DELAYS]
        ax.bar([d + offset for d in DELAYS], share, width=width - 0.06, color=color,
               label=f"AES {name}", zorder=3)
    ax.set_yscale("log")
    ax.set_ylim(0.005, 200)
    ax.set_yticks([0.01, 0.1, 1, 10, 100], ["0.01", "0.1", "1", "10", "100"])
    ax.set_xticks(DELAYS[::2])
    if xlabel:
        ax.set_xlabel("Walk delay vs idle (CPU cycles)", fontsize=size)
    if ylabel:
        ax.set_ylabel("Walks (%)", fontsize=size)
    ax.set_title(title, fontsize=size, color=INK, pad=3)
    style(ax, size)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--parent", type=Path, default=Path("results/updated run"))
    args = parser.parse_args()
    rows = load_summary(args.parent / "mech-summary" / "summary_mechanism.csv")
    run = lambda s: args.parent / f"mech-{s}" / "seed-5764a5e5" / "1-15"
    hist = {s: delay_counts(run(s)) for s in ("std", "ide")}
    out = args.parent / "mech-figures"
    out.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})

    # IEEE single-column figure: (a) dose-response on top, (b)(c) histograms below.
    size = 7
    fig = plt.figure(figsize=(3.5, 4.4))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.35, 1], hspace=0.55, wspace=0.12)
    ax = fig.add_subplot(grid[0, :])
    dose_response(ax, rows, size)
    ax.set_title("(a) Leak tracks crossbar load", fontsize=size, color=INK, loc="left", pad=3)
    for col, (s, title) in enumerate((("std", "(b) default crossbar, 1/15"), ("ide", "(c) near-ideal, 1/15"))):
        axh = fig.add_subplot(grid[1, col])
        histogram(axh, hist[s], title, size, ylabel=col == 0, xlabel=False)
        if col:
            axh.tick_params(labelleft=False)
            axh.legend(fontsize=size - 1, frameon=False, loc="upper right", labelcolor=INK)
    fig.text(0.53, 0.035, "Hit-walk delay vs the idle walk (CPU cycles)", ha="center", fontsize=size, color=INK)
    fig.savefig(out / "fig_mechanism_paper.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    # 16:9 slides (larger type).
    size = 14
    fig, ax = plt.subplots(figsize=(10, 5.6))
    dose_response(ax, rows, size)
    fig.savefig(out / "slide_dose_response.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharey=True)
    histogram(axes[0], hist["std"], "Default crossbar (1 GHz, 32 B)", size, ylabel=True)
    histogram(axes[1], hist["ide"], "Near-ideal crossbar", size, ylabel=False)
    axes[1].legend(fontsize=size - 2, frameon=False, loc="upper right", labelcolor=INK)
    fig.savefig(out / "slide_latency_histogram.png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    for s in ("std", "ide"):
        print(s, {k: dict(sorted(v.items())) for k, v in hist[s].items()})
    print("wrote", out)


if __name__ == "__main__":
    main()
