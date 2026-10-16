#!/usr/bin/env python3
"""Summarize the frozen 4 KiB monitor/AES contention sweep."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ORDER = [
    "UNPARTITIONED", "1-15", "2-14", "3-13", "4-12",
    "5-11", "6-10", "7-9", "8-8",
]


class SummaryError(RuntimeError):
    """Raised when sweep artifacts cannot support a complete summary."""


def load_analyses(results_root: Path) -> list[dict[str, object]]:
    """Load and validate all nine per-configuration analyses in order."""
    rows: list[dict[str, object]] = []
    required = (
        "l1d_size", "statistic", "observed_max_snr", "null_max_snr_95th",
        "empirical_p", "decision", "ipc_core0", "ipc_core1",
        "llc_miss_rate_core0", "llc_miss_rate_core1",
    )
    for display_split in ORDER:
        path = results_root / display_split / "analysis.json"
        if not path.is_file():
            raise SummaryError(f"missing analysis for {display_split}: {path}")
        try:
            row = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            raise SummaryError(f"cannot read valid {path}: {exc}") from exc
        expected_split = "off" if display_split == "UNPARTITIONED" else display_split
        if row.get("split") != expected_split:
            raise SummaryError(
                f"{path}: split is {row.get('split')!r}, expected {expected_split!r}"
            )
        missing = [field for field in required if field not in row]
        if missing:
            raise SummaryError(f"{path}: missing fields: {', '.join(missing)}")
        if row["l1d_size"] != "4KiB" or row["statistic"] != "max-set":
            raise SummaryError(f"{path}: result does not use the frozen method")
        if row["decision"] not in ("PASS", "FAIL"):
            raise SummaryError(f"{path}: invalid decision {row['decision']!r}")
        if display_split != "UNPARTITIONED":
            if row.get("isolation_validation") != "PASS disjoint":
                raise SummaryError(f"{path}: LLC way isolation did not pass")
            if row.get("isolation_violations") != 0:
                raise SummaryError(f"{path}: nonzero LLC way isolation violations")
        rows.append({**row, "display_split": display_split})
    return rows


def first_indistinguishable(
    rows: list[dict[str, object]],
) -> dict[str, object] | None:
    """Return the first partitioned split that fails the corrected null test."""
    by_split = {str(row["display_split"]): row for row in rows}
    for split in ORDER[1:]:
        row = by_split[split]
        if row["decision"] == "FAIL":
            return row
    return None


def csv_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Add way counts and performance deltas relative to unpartitioned."""
    baseline = rows[0]
    output: list[dict[str, object]] = []
    for row in rows:
        split = str(row["display_split"])
        if split == "UNPARTITIONED":
            monitor_ways: int | str = ""
            aes_ways: int | str = ""
        else:
            monitor_ways, aes_ways = (int(value) for value in split.split("-"))
        item: dict[str, object] = {
            "split": split,
            "monitor_ways": monitor_ways,
            "aes_ways": aes_ways,
            "observed_max_snr": row["observed_max_snr"],
            "null_max_snr_95th": row["null_max_snr_95th"],
            "empirical_p": row["empirical_p"],
            "decision": row["decision"],
            "ipc_core0_monitor": row["ipc_core0"],
            "ipc_core1_aes": row["ipc_core1"],
            "ipc_cost_core0_pct": 100.0 * (
                float(baseline["ipc_core0"]) - float(row["ipc_core0"])
            ) / float(baseline["ipc_core0"]),
            "ipc_cost_core1_pct": 100.0 * (
                float(baseline["ipc_core1"]) - float(row["ipc_core1"])
            ) / float(baseline["ipc_core1"]),
            "llc_miss_rate_core0_monitor": row["llc_miss_rate_core0"],
            "llc_miss_rate_core1_aes": row["llc_miss_rate_core1"],
            "llc_miss_rate_delta_core0_pp": 100.0 * (
                float(row["llc_miss_rate_core0"])
                - float(baseline["llc_miss_rate_core0"])
            ),
            "llc_miss_rate_delta_core1_pp": 100.0 * (
                float(row["llc_miss_rate_core1"])
                - float(baseline["llc_miss_rate_core1"])
            ),
            "isolation_validation": row.get("isolation_validation", "control"),
            "isolation_violations": row.get("isolation_violations", ""),
        }
        output.append(item)
    return output


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    table = csv_rows(rows)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)


def plot_results(
    rows: list[dict[str, object]],
    results_root: Path,
    formats: tuple[str, ...] = ("pdf",),
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [str(row["display_split"]) for row in rows]
    positions = list(range(len(rows)))
    snr_values = [float(row["observed_max_snr"]) for row in rows]
    null_values = [float(row["null_max_snr_95th"]) for row in rows]

    plt.rcParams.update({"font.size": 10})
    figure, axis = plt.subplots(figsize=(8.2, 4.6), constrained_layout=True)
    axis.plot(positions, snr_values, marker="o", label="Observed max-set SNR")
    axis.plot(positions, null_values, marker="s", label="Shuffled-max 95th percentile")
    axis.set_xticks(positions, labels, rotation=25, ha="right")
    axis.set_xlabel("LLC allocation (monitor/AES ways)")
    axis.set_ylabel("SNR (dimensionless)")
    axis.grid(axis="y", alpha=0.3)
    axis.legend()
    for output_format in formats:
        figure.savefig(
            results_root / f"snr_vs_split.{output_format}",
            dpi=300 if output_format == "png" else None,
        )
    plt.close(figure)

    figure, axes = plt.subplots(3, 1, figsize=(8.2, 9.0), sharex=True,
                                constrained_layout=True)
    axes[0].plot(positions, snr_values, marker="o", label="Observed max-set SNR")
    axes[0].plot(positions, null_values, marker="s", label="Null 95th percentile")
    axes[0].set_ylabel("SNR")
    axes[0].legend()
    axes[1].plot(positions, [float(row["ipc_core0"]) for row in rows],
                 marker="o", label="Core 0 monitor")
    axes[1].plot(positions, [float(row["ipc_core1"]) for row in rows],
                 marker="s", label="Core 1 AES")
    axes[1].set_ylabel("IPC (instructions/cycle)")
    axes[1].legend()
    axes[2].plot(positions, [float(row["llc_miss_rate_core0"]) for row in rows],
                 marker="o", label="Core 0 monitor")
    axes[2].plot(positions, [float(row["llc_miss_rate_core1"]) for row in rows],
                 marker="s", label="Core 1 AES")
    axes[2].set_ylabel("LLC miss rate")
    axes[2].set_xlabel("LLC allocation (monitor/AES ways)")
    axes[2].set_xticks(positions, labels, rotation=25, ha="right")
    axes[2].legend()
    for axis in axes:
        axis.grid(axis="y", alpha=0.3)
    for output_format in formats:
        figure.savefig(
            results_root / f"contention_tradeoff.{output_format}",
            dpi=300 if output_format == "png" else None,
        )
    plt.close(figure)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-root", type=Path,
        default=project_root / "results" / "contention-l1d4k",
    )
    args = parser.parse_args()
    rows = load_analyses(args.results_root)
    summary_path = args.results_root / "summary.csv"
    write_csv(rows, summary_path)
    plot_results(rows, args.results_root)
    collapse = first_indistinguishable(rows)
    collapse_text = "none" if collapse is None else collapse["display_split"]
    print(f"wrote {summary_path}")
    print(f"collapse_point={collapse_text}")


if __name__ == "__main__":
    try:
        main()
    except SummaryError as exc:
        raise SystemExit(f"error: {exc}") from exc
