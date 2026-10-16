#!/usr/bin/env python3
"""Run the record-free (v2) repeated contention study.

Same 50-process plan as scripts/run_repeated_contention_sweep.py (unchanged),
but every gem5 process uses runner mode `l1d4k-v2` (monitor_v2_l1d4k, probe
file sink).  All output goes under `results/updated run/`.

  --plan smoke   2 processes (seed 0x5764A5E5, A=1 control + 1/15) and a
                 self-eviction gate check; root `results/updated run/smoke`
  --plan full    48 matched + 2 diagnostic processes, then the v2 summarizer;
                 root `results/updated run/sweep`
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.run_repeated_contention_sweep import (  # noqa: E402
    PUBLIC_SEEDS,
    RunItem,
    build_plan,
    case_directory,
)


RUNNER_MODE = "l1d4k-v2"
UPDATED_ROOT = Path("results/updated run")
SELF_EVICTION_TOLERANCE = 0.01


def smoke_plan() -> list[RunItem]:
    seed = PUBLIC_SEEDS[0]
    return [RunItem(seed, "UNPARTITIONED", 1, "matched"), RunItem(seed, "1-15", 1, "matched")]


def completed_result_is_valid(result_dir: Path, item: RunItem) -> bool:
    try:
        analysis = json.loads((result_dir / "analysis.json").read_text())
    except (OSError, json.JSONDecodeError):
        return False
    required = (
        analysis.get("monitor_sink") == "file"
        and analysis.get("split") == ("off" if item.split == "UNPARTITIONED" else item.split)
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
    env = os.environ.copy()
    env["RESULT_ROOT"] = str(result_dir.parent.resolve())
    subprocess.run([
        "bash", "scripts/run_contention_control.sh", RUNNER_MODE,
        item.split, str(item.monitor_ways), str(item.seed),
    ], check=True, env=env)
    subprocess.run([
        sys.executable, "analysis/analyze_contention.py",
        "--results", str(result_dir), "--statistic", "max-set",
    ], check=True)


def smoke_gate(root: Path) -> bool:
    control_dir, treatment_dir = (case_directory(root, item) for item in smoke_plan())
    control = json.loads((control_dir / "analysis.json").read_text())
    treatment = json.loads((treatment_dir / "analysis.json").read_text())
    difference = treatment["all_hit_record_fraction"] - control["all_hit_record_fraction"]
    passed = abs(difference) <= SELF_EVICTION_TOLERANCE
    for name, record in (("control", control), ("treatment", treatment)):
        print(f"{name:9s} all_hit={record['all_hit_record_fraction']:.4f} "
              f"max-set p={record['empirical_p']:.4f} "
              f"hit-only snr={record['hit_only_snr']:.2f} p={record['hit_only_p']:.4f} "
              f"effect={record['hit_only_delta_per_line']:+.3f} cyc/line "
              f"llc_miss_core0={record['llc_miss_rate_core0']:.4f}")
    print(f"self_eviction_gate={'PASS' if passed else 'FAIL'} "
          f"difference={difference:+.4f} tolerance={SELF_EVICTION_TOLERANCE}")
    return passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", choices=("smoke", "full"), required=True)
    parser.add_argument("--results-root", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    plan = smoke_plan() if args.plan == "smoke" else build_plan()
    root = args.results_root or UPDATED_ROOT / ("smoke" if args.plan == "smoke" else "sweep")
    if root.exists() and not args.resume:
        raise SystemExit(f"error: refusing to reuse existing {root}; use --resume")
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "plan": args.plan,
        "runner_mode": RUNNER_MODE,
        "process_count": len(plan),
        "public_workload_seeds": list(PUBLIC_SEEDS),
        "diagnostics_excluded_from_inference": True,
        "items": [asdict(item) for item in plan],
    }
    manifest_path = root / "run_plan.json"
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    elif json.loads(manifest_path.read_text()) != manifest:
        raise SystemExit("error: existing run plan does not match this program")

    for number, item in enumerate(plan, 1):
        result_dir = case_directory(root, item)
        if args.resume and completed_result_is_valid(result_dir, item):
            print(f"SKIP {number}/{len(plan)} verified-output-present {result_dir}", flush=True)
            continue
        print(f"RUN {number}/{len(plan)} seed=0x{item.seed:08x} split={item.split} "
              f"A={item.monitor_ways} role={item.role}", flush=True)
        run_item(root, item)

    if args.plan == "smoke":
        raise SystemExit(0 if smoke_gate(root) else 1)
    subprocess.run([
        sys.executable, "analysis/summarize_repeated_contention_v2.py",
        "--results-root", str(root),
    ], check=True)


if __name__ == "__main__":
    main()
