#!/usr/bin/env python3
"""IEEE single-column Fig. 3: hit-only leak per allocation, way partitioning vs the full defense.

Reads (never writes) the frozen decision tables produced by analysis/summarize_sweep_v3.py:
  results/updated run/sweep-v3/summary_v3.csv  (unpartitioned control, way partitioning only)
  results/updated run/tdma-rsv/summary_v3.csv  (way partitioning + request slots + per-domain
                                                LLC response queues; see the experiment branch)
Writes a new file only: results/updated run/defense-figures/fig_defense_paper.png
Purely presentational: every plotted value is a field of those tables.
Palette: categorical slots 1-2 (blue, orange) validated in light mode; the control is the
neutral reference series.
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

WAY, DEFENSE = "#2a78d6", "#eb6834"        # categorical slots 1, 2
CONTROL, INK, INK2, GRID = "#a3a29c", "#0b0b0b", "#52514e", "#e4e3df"
V3 = Path("results/updated run/sweep-v3/summary_v3.csv")
DEFENDED = Path("results/updated run/tdma-rsv/summary_v3.csv")
OUT = Path("results/updated run/defense-figures/fig_defense_paper.png")
MARGIN = 0.02


def rows(path: Path) -> list[dict]:
    data = list(csv.DictReader(path.open(newline="")))
    assert [r["split"] for r in data] == [f"{a}-{16 - a}" for a in range(1, 9)], path
    return data


def main() -> None:
    if OUT.exists():
        raise SystemExit(f"error: refusing to overwrite {OUT}")
    v3, defended = rows(V3), rows(DEFENDED)
    # The two tables share one control set (the stored v3 unpartitioned runs).
    assert [r["control_effect_per_line"] for r in v3] == [r["control_effect_per_line"] for r in defended]
    x = list(range(1, 9))
    size = 7.5
    plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(figsize=(3.5, 2.45))
    ax.axhspan(-MARGIN, MARGIN, color=GRID, lw=0, zorder=0)
    ax.text(8.35, MARGIN + 0.008, "±0.02 equivalence margin", fontsize=size - 1.5, color=INK2,
            ha="right", va="bottom")
    ax.axhline(0, color=INK2, lw=0.6, zorder=1)

    def series(data, key_mid, key_low, key_high, color, marker, label, offset):
        mid = [float(r[key_mid]) for r in data]
        xs = [a + offset for a in x]
        if key_low:
            low = [mid[i] - float(r[key_low]) for i, r in enumerate(data)]
            high = [float(r[key_high]) - mid[i] for i, r in enumerate(data)]
            ax.errorbar(xs, mid, yerr=[low, high], fmt="none", ecolor=color, elinewidth=1.0,
                        capsize=1.6, zorder=3)
        ax.plot(xs, mid, color=color, lw=1.6, marker=marker, ms=4.2, mec="white", mew=0.8,
                label=label, zorder=4)
        return mid

    series(v3, "control_effect_per_line", None, None, CONTROL, "o", "Unpartitioned control", -0.12)
    way = series(v3, "treatment_effect_per_line", "treatment_effect_ci90_low",
                 "treatment_effect_ci90_high", WAY, "s", "Way partitioning only", 0.0)
    series(defended, "treatment_effect_per_line", "treatment_effect_ci90_low",
           "treatment_effect_ci90_high", DEFENSE, "D", "Full defense", 0.12)
    ax.annotate("Full defense:\nindistinguishable at all 8", xy=(4.6, 0.003), xytext=(3.2, 0.11),
                fontsize=size - 1, color=INK, arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.6})
    ax.annotate("Way partitioning:\ndistinguishable at all 8", xy=(6.5, (way[5] + way[6]) / 2),
                xytext=(6.9, 0.17), fontsize=size - 1, color=INK, ha="center",
                arrowprops={"arrowstyle": "-", "color": INK2, "lw": 0.6})
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK2)
        ax.spines[side].set_linewidth(0.6)
    ax.tick_params(colors=INK2, labelsize=size, width=0.6, length=2.5)
    ax.set_xticks(x, [f"{a}/{16 - a}" for a in x])
    ax.set_xlim(0.5, 8.5)
    ax.set_ylim(-0.05, 0.48)
    ax.set_xlabel("Monitor/AES ways", fontsize=size)
    ax.set_ylabel("Leak: active − idle\n(cycles per probed line)", fontsize=size)
    ax.yaxis.grid(True, color=GRID, lw=0.5, zorder=0)
    ax.legend(fontsize=size - 1, frameon=False, loc="upper left", ncol=1, labelcolor=INK,
              bbox_to_anchor=(0.0, 1.02))
    fig.tight_layout(pad=0.3)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=300)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
