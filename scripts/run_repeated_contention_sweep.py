#!/usr/bin/env python3
"""Run exactly 50 fresh gem5 processes for the repeated contention study."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import subprocess
import sys


PUBLIC_SEEDS = (0x5764A5E5, 0x5764A5E6, 0x5764A5E7)


@dataclass(frozen=True)
class RunItem:
    seed: int
    split: str
    monitor_ways: int
    role: str


def build_plan() -> list[RunItem]:
    """Return 48 matched cases plus two excluded A16 diagnostics."""
    plan: list[RunItem] = []
    for seed in PUBLIC_SEEDS:
        for monitor_ways in range(1, 9):
            plan.append(RunItem(seed, "UNPARTITIONED", monitor_ways, "matched"))
            plan.append(RunItem(
                seed, f"{monitor_ways}-{16 - monitor_ways}",
                monitor_ways, "matched",
            ))
    for seed in PUBLIC_SEEDS[:2]:
        plan.append(RunItem(seed, "UNPARTITIONED", 16, "diagnostic"))
    assert len(plan) == 50
    return plan


def case_directory(root: Path, item: RunItem) -> Path:
    parent = (
        root / f"seed-{item.seed:08x}" if item.role == "matched"
        else root / "diagnostics" / f"seed-{item.seed:08x}"
    )
    name = (
        f"UNPARTITIONED-A{item.monitor_ways}"
        if item.split == "UNPARTITIONED" else item.split
    )
    return parent / name


def completed_result_is_valid(result_dir: Path, item: RunItem) -> bool:
    """Return true only when the saved analysis matches this planned case."""
    try:
        analysis = json.loads((result_dir / "analysis.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return False
    expected_split = "off" if item.split == "UNPARTITIONED" else item.split
    required = (
        analysis.get("split") == expected_split
        and analysis.get("monitor_ways") == item.monitor_ways
        and analysis.get("workload_seed") == item.seed
        and analysis.get("probe_mapping_validation") == "PASS congruent"
        and analysis.get("stats_blocks") == 2
    )
    if item.split != "UNPARTITIONED":
        required = required and analysis.get("isolation_validation") == "PASS disjoint"
    return required


def run_item(root: Path, item: RunItem) -> None:
    result_dir = case_directory(root, item)
    parent = result_dir.parent
    env = os.environ.copy()
    env["RESULT_ROOT"] = str(parent)
    subprocess.run([
        "bash", "scripts/run_contention_control.sh", "l1d4k",
        item.split, str(item.monitor_ways), str(item.seed),
    ], check=True, env=env)
    subprocess.run([
        sys.executable, "analysis/analyze_contention.py",
        "--results", str(result_dir), "--statistic", "max-set",
    ], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-root", type=Path,
        default=Path("results/contention-repeated-20261001"),
    )
    parser.add_argument("--list-plan", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    plan = build_plan()
    if args.list_plan:
        for number, item in enumerate(plan, 1):
            print(number, json.dumps(asdict(item), sort_keys=True))
        return
    if args.results_root.exists() and not args.resume:
        raise SystemExit(
            f"error: refusing to reuse existing {args.results_root}; use --resume"
        )
    args.results_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "process_count": len(plan),
        "matched_process_count": 48,
        "diagnostic_process_count": 2,
        "public_workload_seeds": list(PUBLIC_SEEDS),
        "diagnostics_excluded_from_inference": True,
        "plan": [asdict(item) for item in plan],
    }
    manifest_path = args.results_root / "run_plan.json"
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    elif json.loads(manifest_path.read_text()) != manifest:
        raise SystemExit("error: existing run plan does not match this program")

    for number, item in enumerate(plan, 1):
        result_dir = case_directory(args.results_root, item)
        if args.resume and completed_result_is_valid(result_dir, item):
            print(f"SKIP {number}/50 verified-output-present {result_dir}", flush=True)
            continue
        print(
            f"RUN {number}/50 seed=0x{item.seed:08x} split={item.split} "
            f"A={item.monitor_ways} role={item.role}",
            flush=True,
        )
        run_item(args.results_root, item)

    subprocess.run([
        sys.executable, "analysis/summarize_repeated_contention.py",
        "--results-root", str(args.results_root),
    ], check=True)


if __name__ == "__main__":
    main()
