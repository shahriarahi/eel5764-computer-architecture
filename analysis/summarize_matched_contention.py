#!/usr/bin/env python3
"""Summarize depth-matched unpartitioned/partitioned contention pairs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


class MatchedSummaryError(RuntimeError):
    """Raised when saved runs cannot support a paired conclusion."""


def _load(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise MatchedSummaryError(f"cannot read valid {path}: {exc}") from exc


def load_matched_pairs(results_root: Path) -> list[dict[str, object]]:
    """Load eight A-line controls and their A/(16-A) treatments."""
    pairs: list[dict[str, object]] = []
    for monitor_ways in range(1, 9):
        control_path = (
            results_root / f"UNPARTITIONED-A{monitor_ways}" / "analysis.json"
        )
        split = f"{monitor_ways}-{16 - monitor_ways}"
        treatment_path = results_root / split / "analysis.json"
        control = _load(control_path)
        treatment = _load(treatment_path)
        for name, row, expected_split in (
            ("control", control, "off"),
            ("treatment", treatment, split),
        ):
            if row.get("split") != expected_split:
                raise MatchedSummaryError(
                    f"{name} A={monitor_ways} has split {row.get('split')!r}; "
                    f"expected {expected_split!r}"
                )
            if row.get("monitor_ways") != monitor_ways:
                raise MatchedSummaryError(
                    f"{name} A={monitor_ways} has mismatched monitor depth"
                )
            if row.get("probe_mapping_validation") != "PASS congruent":
                raise MatchedSummaryError(
                    f"{name} A={monitor_ways} lacks physical-set congruence"
                )
        if control.get("distinguishable") is not True:
            raise MatchedSummaryError(
                f"matched control A={monitor_ways} is not distinguishable"
            )
        if treatment.get("isolation_validation") != "PASS disjoint":
            raise MatchedSummaryError(f"treatment {split} lacks disjoint ways")
        if treatment.get("isolation_violations") != 0:
            raise MatchedSummaryError(f"treatment {split} has isolation violations")
        pairs.append({
            "monitor_ways": monitor_ways,
            "split": split,
            "control": control,
            "treatment": treatment,
        })
    return pairs


def paired_rows(pairs: list[dict[str, object]]) -> list[dict[str, object]]:
    """Create traceable control/treatment rows with depth-matched costs."""
    rows: list[dict[str, object]] = []
    for pair in pairs:
        control = pair["control"]
        treatment = pair["treatment"]
        assert isinstance(control, dict) and isinstance(treatment, dict)

        def cost(field: str) -> float:
            baseline = float(control[field])
            return 100.0 * (baseline - float(treatment[field])) / baseline

        rows.append({
            "split": pair["split"],
            "monitor_ways": pair["monitor_ways"],
            "aes_ways": 16 - int(pair["monitor_ways"]),
            "control_observed_snr": control["observed_max_snr"],
            "control_null95": control["null_max_snr_95th"],
            "control_p": control["empirical_p"],
            "control_distinguishable": control["distinguishable"],
            "partitioned_observed_snr": treatment["observed_max_snr"],
            "partitioned_null95": treatment["null_max_snr_95th"],
            "partitioned_p": treatment["empirical_p"],
            "partitioned_distinguishable": treatment["distinguishable"],
            "paired_conclusion": (
                "signal remains" if treatment["distinguishable"]
                else "signal suppressed"
            ),
            "monitor_ipc_control": control["ipc_core0"],
            "monitor_ipc_partitioned": treatment["ipc_core0"],
            "monitor_ipc_cost_pct": cost("ipc_core0"),
            "aes_ipc_control": control["ipc_core1"],
            "aes_ipc_partitioned": treatment["ipc_core1"],
            "aes_ipc_cost_pct": cost("ipc_core1"),
            "monitor_llc_miss_rate_control": control["llc_miss_rate_core0"],
            "monitor_llc_miss_rate_partitioned": treatment["llc_miss_rate_core0"],
            "aes_llc_miss_rate_control": control["llc_miss_rate_core1"],
            "aes_llc_miss_rate_partitioned": treatment["llc_miss_rate_core1"],
            "aes_cycles_per_encryption_control": control["aes_cycles_per_encryption"],
            "aes_cycles_per_encryption_partitioned": treatment["aes_cycles_per_encryption"],
            "isolation_validation": treatment["isolation_validation"],
            "probe_mapping_validation_control": control["probe_mapping_validation"],
            "probe_mapping_validation_partitioned": treatment["probe_mapping_validation"],
        })
    return rows


def stable_collapse_point(rows: list[dict[str, object]]) -> str | None:
    """Return the first split only when every later split stays suppressed."""
    for index, row in enumerate(rows):
        if row["paired_conclusion"] == "signal suppressed" and all(
            later["paired_conclusion"] == "signal suppressed"
            for later in rows[index:]
        ):
            return str(row["split"])
    return None


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_results(rows: list[dict[str, object]], results_root: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = [int(row["monitor_ways"]) for row in rows]
    labels = [str(row["split"]) for row in rows]
    plt.rcParams.update({"font.size": 10})

    figure, axis = plt.subplots(figsize=(8.2, 4.8), constrained_layout=True)
    axis.plot(x, [float(r["control_observed_snr"]) for r in rows],
              marker="o", label="Matched unpartitioned control")
    axis.plot(x, [float(r["partitioned_observed_snr"]) for r in rows],
              marker="s", label="Partitioned treatment")
    axis.plot(x, [float(r["control_null95"]) for r in rows],
              linestyle=":", color="tab:blue", label="Control null 95th percentile")
    axis.plot(x, [float(r["partitioned_null95"]) for r in rows],
              linestyle="--", color="black", label="Treatment null 95th percentile")
    axis.set_xticks(x, labels)
    axis.set_xlabel("LLC allocation (monitor/AES ways)")
    axis.set_ylabel("Maximum per-set SNR (dimensionless)")
    axis.grid(axis="y", alpha=0.3)
    axis.legend()
    figure.savefig(results_root / "matched_snr.pdf")
    figure.savefig(results_root / "matched_snr.png", dpi=300)
    plt.close(figure)

    figure, axes = plt.subplots(3, 1, figsize=(8.2, 9.2), sharex=True,
                                constrained_layout=True)
    axes[0].plot(x, [float(r["partitioned_observed_snr"]) for r in rows],
                 marker="o", label="Partitioned SNR")
    axes[0].plot(x, [float(r["partitioned_null95"]) for r in rows],
                 marker="s", label="Null 95th percentile")
    axes[0].set_ylabel("SNR")
    axes[1].plot(x, [float(r["monitor_ipc_partitioned"]) for r in rows],
                 marker="o", label="Monitor")
    axes[1].plot(x, [float(r["aes_ipc_partitioned"]) for r in rows],
                 marker="s", label="AES")
    axes[1].set_ylabel("IPC (instructions/cycle)")
    axes[2].plot(x, [float(r["monitor_llc_miss_rate_partitioned"]) for r in rows],
                 marker="o", label="Monitor")
    axes[2].plot(x, [float(r["aes_llc_miss_rate_partitioned"]) for r in rows],
                 marker="s", label="AES")
    axes[2].set_ylabel("LLC miss rate")
    axes[2].set_xlabel("LLC allocation (monitor/AES ways)")
    axes[2].set_xticks(x, labels)
    for axis in axes:
        axis.grid(axis="y", alpha=0.3)
        axis.legend()
    figure.savefig(results_root / "matched_tradeoff.pdf")
    figure.savefig(results_root / "matched_tradeoff.png", dpi=300)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", required=True, type=Path)
    args = parser.parse_args()
    pairs = load_matched_pairs(args.results_root)
    rows = paired_rows(pairs)
    summary = args.results_root / "summary_matched.csv"
    write_csv(rows, summary)
    plot_results(rows, args.results_root)
    first_suppressed = next(
        (row["split"] for row in rows
         if row["paired_conclusion"] == "signal suppressed"),
        "none",
    )
    stable_collapse = stable_collapse_point(rows) or "none"
    print(f"validated_pairs={len(pairs)}")
    print(f"first_tested_indistinguishable={first_suppressed}")
    print(f"stable_collapse_point={stable_collapse}")
    print(f"wrote {summary}")


if __name__ == "__main__":
    try:
        main()
    except MatchedSummaryError as exc:
        raise SystemExit(f"error: {exc}") from exc
