#!/usr/bin/env python3
"""Full confirmatory sweep with the v3 monitor (deviation D3).

Same 50-process plan as the v1/v2 sweeps (48 matched + 2 A=16 diagnostics),
runner mode `l1d4k-v3`, into `results/updated run/sweep-v3/`, then
analysis/summarize_sweep_v3.py.  Earlier roots are only read.
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
from scripts.run_repeated_contention_sweep import build_plan, case_directory  # noqa: E402
from scripts.run_rerun_v3 import completed_result_is_valid  # noqa: E402

RUNNER_MODE = "l1d4k-v3"
DEFAULT_ROOT = Path("results/updated run/sweep-v3")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    root, plan = args.results_root, build_plan()
    if root.exists() and not args.resume:
        raise SystemExit(f"error: refusing to reuse existing {root}; use --resume")
    root.mkdir(parents=True, exist_ok=True)
    manifest = {"plan": "full-v3", "runner_mode": RUNNER_MODE, "process_count": len(plan),
                "diagnostics_excluded_from_inference": True,
                "items": [asdict(i) for i in plan]}
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
              f"A={item.monitor_ways} role={item.role}", flush=True)
        env = os.environ.copy()
        env["RESULT_ROOT"] = str(result_dir.parent.resolve())
        subprocess.run(["bash", "scripts/run_contention_control.sh", RUNNER_MODE,
                        item.split, str(item.monitor_ways), str(item.seed)],
                       check=True, env=env)
        subprocess.run([sys.executable, "analysis/analyze_contention.py",
                        "--results", str(result_dir), "--statistic", "max-set"],
                       check=True)

    subprocess.run([sys.executable, "analysis/summarize_sweep_v3.py",
                    "--results-root", str(root)], check=True)


if __name__ == "__main__":
    main()
