#!/usr/bin/env python3
"""16:9 slide figure of the main v3 result for the video deck.

Reads (never writes) `results/updated run/sweep-v3/summary_v3.csv`; writes
`results/updated run/mech-figures/slide_main_result.png`.  Purely
presentational.  Palette: reference categorical slot 1 (blue) for the
partitioned monitor, neutral gray dashed for the matched control (identity is
also carried by line style and direct labels).
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BLUE, GRAY, INK, INK2, GRID = "#2a78d6", "#8a8984", "#0b0b0b", "#52514e", "#e4e3df"


def main() -> None:
    root = Path("results/updated run")
    rows = list(csv.DictReader((root / "sweep-v3" / "summary_v3.csv").open()))
    labels = [r["split"].replace("-", "/") for r in rows]
    x = list(range(len(rows)))
    ctl = [float(r["control_effect_per_line"]) for r in rows]
    trt = [float(r["treatment_effect_per_line"]) for r in rows]
    lo = [float(r["treatment_effect_ci90_low"]) for r in rows]
    hi = [float(r["treatment_effect_ci90_high"]) for r in rows]
    size = 15
    plt.rcParams.update({"font.family": "DejaVu Sans"})
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.axhspan(-0.02, 0.02, color="#efeeea", zorder=0)
    ax.text(7.3, 0.0, "±0.02 = \"no leak\" margin", fontsize=size - 2, color=INK2, va="center", ha="right")
    ax.plot(x, ctl, color=GRAY, linestyle=(0, (4, 3)), linewidth=2, marker="o", markersize=9,
            markerfacecolor="white", markeredgewidth=1.8, zorder=3)
    ax.fill_between(x, lo, hi, color=BLUE, alpha=0.18, linewidth=0, zorder=2)
    ax.plot(x, trt, color=BLUE, linewidth=2.4, marker="o", markersize=9, zorder=4)
    ax.annotate("Unpartitioned control", (7, ctl[-1]), xytext=(0, 12), textcoords="offset points",
                ha="right", fontsize=size - 1, color=INK2)
    ax.annotate("Partitioned (way masks on)", (7, trt[-1]), xytext=(0, -26), textcoords="offset points",
                ha="right", fontsize=size - 1, color=INK)
    ax.set_xticks(x, labels)
    ax.set_xlabel("LLC ways: monitor / AES", fontsize=size, color=INK)
    ax.set_ylabel("Leak (cycles per probed line)", fontsize=size, color=INK)
    ax.set_ylim(-0.05, 0.47)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
    ax.tick_params(colors=INK2, labelsize=size - 1)
    ax.grid(axis="y", color=GRID)
    ax.set_axisbelow(True)
    out = root / "mech-figures" / "slide_main_result.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)


if __name__ == "__main__":
    main()
