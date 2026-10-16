#!/usr/bin/env python3
"""Rerun 7/9 and 8/8 with the v3 monitor (deviation D2).

12 fresh gem5 processes: seeds 0x5764A5E5..E7 x A in {7, 8} x {control,
partitioned}, runner mode `l1d4k-v3`, into
`results/updated run/rerun-7-9-8-8/`, then the combined v3 summarizer.
The updated-run sweep (`results/updated run/sweep/`) is only read.
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
    case_directory,
)


RUNNER_MODE = "l1d4k-v3"
DEFAULT_ROOT = Path("results/updated run/rerun-7-9-8-8")
RERUN_WAYS = (7, 8)


def rerun_plan() -> list[RunItem]:
    plan = []
    for seed in PUBLIC_SEEDS:
        for ways in RERUN_WAYS:
            plan.append(RunItem(seed, "UNPARTITIONED", ways, "matched"))
            plan.append(RunItem(seed, f"{ways}-{16 - ways}", ways, "matched"))
    return plan


def completed_result_is_valid(result_dir: Path, item: RunItem) -> bool:
    try:
        analysis = json.loads((result_dir / "analysis.json").read_text())
        meta = json.loads((result_dir / "run_meta.json").read_text())
    except (OSError, json.JSONDecodeError):
        return False
    ok = (
        meta.get("monitor_variant") == "v3"
        and analysis.get("monitor_sink") == "file"
        and analysis.get("split") == ("off" if item.split == "UNPARTITIONED" else item.split)
        and analysis.get("monitor_ways") == item.monitor_ways
        and analysis.get("workload_seed") == item.seed
        and analysis.get("probe_mapping_validation") == "PASS congruent"
        and analysis.get("stats_blocks") == 2
    )
    if item.split != "UNPARTITIONED":
        ok = ok and analysis.get("isolation_validation") == "PASS disjoint"
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root = args.results_root
    plan = rerun_plan()
    if root.exists() and not args.resume:
        raise SystemExit(f"error: refusing to reuse existing {root}; use --resume")
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"plan": "rerun-7-9-8-8", "runner_mode": RUNNER_MODE,
                "process_count": len(plan), "items": [asdict(i) for i in plan]}
    manifest_path = root / "run_plan.json"
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    elif json.loads(manifest_path.read_text()) != manifest:
        raise SystemExit("error: existing run plan does not match this program")

    for number, item in enumerate(plan, 1):
        result_dir = case_directory(root, item)
        if args.resume and completed_result_is_valid(result_dir, item):
            print(f"SKIP {number}/{len(plan)} {result_dir}", flush=True)
            continue
        print(f"RUN {number}/{len(plan)} seed=0x{item.seed:08x} split={item.split} "
              f"A={item.monitor_ways}", flush=True)
        env = os.environ.copy()
        env["RESULT_ROOT"] = str(result_dir.parent.resolve())
        subprocess.run(["bash", "scripts/run_contention_control.sh", RUNNER_MODE,
                        item.split, str(item.monitor_ways), str(item.seed)],
                       check=True, env=env)
        subprocess.run([sys.executable, "analysis/analyze_contention.py",
                        "--results", str(result_dir), "--statistic", "max-set"],
                       check=True)

    subprocess.run([sys.executable, "analysis/summarize_rerun_v3.py",
                    "--rerun-root", str(root)], check=True)


if __name__ == "__main__":
    main()
