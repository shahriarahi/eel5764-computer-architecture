#!/usr/bin/env python3
"""Aggregate three public-seed matched contention sweeps."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
import statistics


PUBLIC_SEEDS = (0x5764A5E5, 0x5764A5E6, 0x5764A5E7)
ALPHA = 0.05


class RepeatedSummaryError(RuntimeError):
    """Raised when repeated outputs cannot support the declared analysis."""


def fisher_combined_p(p_values: list[float]) -> float:
    """Combine independent p-values using Fisher's exact even-df survival."""
    if not p_values or any(not 0.0 < value <= 1.0 for value in p_values):
        raise ValueError("Fisher p-values must be in (0, 1]")
    half_statistic = -sum(math.log(value) for value in p_values)
    terms = sum(
        half_statistic**power / math.factorial(power)
        for power in range(len(p_values))
    )
    return min(1.0, math.exp(-half_statistic) * terms)


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    """Return Holm familywise-error adjusted p-values by key."""
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for rank, (key, value) in enumerate(ordered):
        running = max(running, (count - rank) * value)
        adjusted[key] = min(1.0, running)
    return adjusted


def percent_cost(control: float, treatment: float, *, higher_is_better: bool) -> float:
    """Return positive percent cost in the metric's worse direction."""
    if control == 0.0:
        raise ValueError("percent cost requires a nonzero control")
    difference = control - treatment if higher_is_better else treatment - control
    return 100.0 * difference / control


def stable_collapse_point(rows: list[dict[str, object]]) -> str | None:
    """Require valid controls and suppression at one split and every larger A."""
    for index, row in enumerate(rows):
        if row["control_valid"] is True and row["distinguishable"] is False:
            if all(
                later["control_valid"] is True
                and later["distinguishable"] is False
                for later in rows[index:]
            ):
                return str(row["split"])
    return None


def _load(path: Path) -> dict[str, object]:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RepeatedSummaryError(f"cannot read valid {path}: {exc}") from exc


def load_records(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for seed in PUBLIC_SEEDS:
        seed_root = root / f"seed-{seed:08x}"
        for ways in range(1, 9):
            split = f"{ways}-{16 - ways}"
            for mode, directory, expected_split in (
                ("control", f"UNPARTITIONED-A{ways}", "off"),
                ("partitioned", split, split),
            ):
                path = seed_root / directory / "analysis.json"
                record = _load(path)
                if record.get("workload_seed") != seed:
                    raise RepeatedSummaryError(f"{path}: workload seed mismatch")
                if record.get("monitor_ways") != ways:
                    raise RepeatedSummaryError(f"{path}: monitor depth mismatch")
                if record.get("split") != expected_split:
                    raise RepeatedSummaryError(f"{path}: split mismatch")
                if record.get("probe_mapping_validation") != "PASS congruent":
                    raise RepeatedSummaryError(f"{path}: mapping validation failed")
                if mode == "partitioned":
                    if record.get("isolation_validation") != "PASS disjoint":
                        raise RepeatedSummaryError(f"{path}: disjoint-way validation failed")
                    if record.get("isolation_violations") != 0:
                        raise RepeatedSummaryError(f"{path}: isolation violation")
                records.append({
                    "seed": seed,
                    "monitor_ways": ways,
                    "split": split,
                    "mode": mode,
                    "analysis": record,
                })
    return records


def _sample_summary(values: list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "stdev": statistics.stdev(values),
        "min": min(values),
        "max": max(values),
    }


def aggregate(records: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    per_seed: list[dict[str, object]] = []
    grouped: dict[int, list[dict[str, object]]] = {ways: [] for ways in range(1, 9)}
    for seed in PUBLIC_SEEDS:
        for ways in range(1, 9):
            selected = [
                item for item in records
                if item["seed"] == seed and item["monitor_ways"] == ways
            ]
            if len(selected) != 2:
                raise RepeatedSummaryError(f"seed={seed} A={ways}: incomplete pair")
            control = next(item["analysis"] for item in selected if item["mode"] == "control")
            treatment = next(item["analysis"] for item in selected if item["mode"] == "partitioned")
            assert isinstance(control, dict) and isinstance(treatment, dict)

            def higher_better_cost(field: str) -> float:
                return percent_cost(
                    float(control[field]), float(treatment[field]),
                    higher_is_better=True,
                )

            row = {
                "seed": seed,
                "seed_hex": f"0x{seed:08x}",
                "split": f"{ways}-{16 - ways}",
                "monitor_ways": ways,
                "control_snr": control["observed_max_snr"],
                "control_p": control["empirical_p"],
                "control_distinguishable": control["distinguishable"],
                "partitioned_snr": treatment["observed_max_snr"],
                "partitioned_p": treatment["empirical_p"],
                "partitioned_distinguishable_uncorrected": treatment["distinguishable"],
                "monitor_ipc_cost_pct": higher_better_cost("ipc_core0"),
                "aes_ipc_cost_pct": higher_better_cost("ipc_core1"),
                "monitor_llc_miss_delta_pp": 100.0 * (
                    float(treatment["llc_miss_rate_core0"])
                    - float(control["llc_miss_rate_core0"])
                ),
                "aes_llc_miss_delta_pp": 100.0 * (
                    float(treatment["llc_miss_rate_core1"])
                    - float(control["llc_miss_rate_core1"])
                ),
                "aes_cycles_per_encryption_cost_pct": percent_cost(
                    float(control["aes_cycles_per_encryption"]),
                    float(treatment["aes_cycles_per_encryption"]),
                    higher_is_better=False,
                ),
            }
            per_seed.append(row)
            grouped[ways].append(row)

    control_combined = {
        f"{ways}-{16-ways}": fisher_combined_p([
            float(row["control_p"]) for row in grouped[ways]
        ]) for ways in range(1, 9)
    }
    treatment_combined = {
        f"{ways}-{16-ways}": fisher_combined_p([
            float(row["partitioned_p"]) for row in grouped[ways]
        ]) for ways in range(1, 9)
    }
    control_adjusted = holm_adjust(control_combined)
    treatment_adjusted = holm_adjust(treatment_combined)

    aggregate_rows: list[dict[str, object]] = []
    for ways in range(1, 9):
        split = f"{ways}-{16-ways}"
        group = grouped[ways]
        control_valid = (
            all(row["control_distinguishable"] is True for row in group)
            and control_adjusted[split] < ALPHA
        )
        distinguishable = control_valid and treatment_adjusted[split] < ALPHA
        row: dict[str, object] = {
            "split": split,
            "monitor_ways": ways,
            "aes_ways": 16 - ways,
            "repetitions": len(group),
            "control_individual_passes": sum(
                row["control_distinguishable"] is True for row in group
            ),
            "control_fisher_p": control_combined[split],
            "control_holm_p": control_adjusted[split],
            "control_valid": control_valid,
            "partitioned_fisher_p": treatment_combined[split],
            "partitioned_holm_p": treatment_adjusted[split],
            "distinguishable": distinguishable,
            "conclusion": (
                "invalid control" if not control_valid else
                "distinguishable" if distinguishable else
                "indistinguishable"
            ),
        }
        for field in (
            "control_snr", "partitioned_snr", "monitor_ipc_cost_pct",
            "aes_ipc_cost_pct", "monitor_llc_miss_delta_pp",
            "aes_llc_miss_delta_pp", "aes_cycles_per_encryption_cost_pct",
        ):
            for name, value in _sample_summary([
                float(item[field]) for item in group
            ]).items():
                row[f"{field}_{name}"] = value
        aggregate_rows.append(row)
    return per_seed, aggregate_rows


def write_csv(rows: list[dict[str, object]], path: Path) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_results(rows: list[dict[str, object]], root: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    x = list(range(1, 9))
    labels = [str(row["split"]) for row in rows]
    plt.rcParams.update({"font.size": 10})
    figure, axes = plt.subplots(2, 1, figsize=(8.2, 7.2), sharex=True, constrained_layout=True)
    for prefix, label, marker in (
        ("control_snr", "Matched unpartitioned control", "o"),
        ("partitioned_snr", "Partitioned treatment", "s"),
    ):
        means = [float(row[f"{prefix}_mean"]) for row in rows]
        low = [mean - float(row[f"{prefix}_min"]) for mean, row in zip(means, rows)]
        high = [float(row[f"{prefix}_max"]) - mean for mean, row in zip(means, rows)]
        axes[0].errorbar(x, means, yerr=[low, high], marker=marker, capsize=3, label=label)
    axes[0].set_ylabel("Maximum per-set SNR")
    axes[0].legend()
    axes[0].grid(axis="y", alpha=0.3)
    axes[1].plot(x, [float(row["partitioned_holm_p"]) for row in rows], marker="o")
    axes[1].axhline(ALPHA, color="black", linestyle="--", label="Holm alpha = 0.05")
    axes[1].set_yscale("log")
    axes[1].set_ylabel("Fisher combined Holm-adjusted p")
    axes[1].set_xlabel("LLC allocation (monitor/AES ways)")
    axes[1].set_xticks(x, labels)
    axes[1].legend()
    axes[1].grid(axis="y", alpha=0.3)
    figure.savefig(root / "repeated_snr.pdf")
    figure.savefig(root / "repeated_snr.png", dpi=300)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", required=True, type=Path)
    args = parser.parse_args()
    records = load_records(args.results_root)
    per_seed, rows = aggregate(records)
    write_csv(per_seed, args.results_root / "per_seed_matched.csv")
    write_csv(rows, args.results_root / "summary_repeated.csv")
    collapse = stable_collapse_point(rows)
    summary = {
        "public_workload_seeds": list(PUBLIC_SEEDS),
        "repetitions": len(PUBLIC_SEEDS),
        "matched_processes": 48,
        "diagnostic_processes": 2,
        "combination": "Fisher across three workload seeds",
        "multiple_testing": "Holm correction across eight allocations",
        "alpha": ALPHA,
        "stable_collapse_point": collapse,
        "rows": rows,
    }
    (args.results_root / "repeated_summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    plot_results(rows, args.results_root)
    print(f"validated_matched_processes={len(records)}")
    print("validated_diagnostic_processes=2")
    print(f"stable_collapse_point={collapse or 'none'}")
    print(f"wrote {args.results_root / 'summary_repeated.csv'}")


if __name__ == "__main__":
    try:
        main()
    except RepeatedSummaryError as exc:
        raise SystemExit(f"error: {exc}") from exc
