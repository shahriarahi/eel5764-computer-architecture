"""Preregistered outcomes of the defense sweep (PREREGISTRATION_SWEEP.md).

1. Builds the view root tdma-rsv from byte-identical copies (v3 controls, defended
   treatments) and runs the frozen analysis/summarize_sweep_v3.py on it unchanged.
2. Compares defended AES and quiet probes for all 24 configurations.
3. Reports AES encryptions against the v3 way-only treatments.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from run_respq import compare_probes
from run_sweep import AES_ROOT, QUIET_ROOT, SEEDS

VIEW_ROOT = "tdma-rsv"
COPIED = ("analysis.json", "run_meta.json", "probes.bin")


def copy_exact(source: Path, target: Path) -> None:
    target.mkdir(parents=True)
    for name in COPIED:
        shutil.copyfile(source / name, target / name)
        if hashlib.sha256((source / name).read_bytes()).digest() != \
                hashlib.sha256((target / name).read_bytes()).digest():
            raise ValueError(f"copy mismatch for {source / name}")


def build_view(results: Path) -> Path:
    view = results / VIEW_ROOT
    if view.exists():
        raise FileExistsError(view)
    for seed in SEEDS:
        seed_dir = f"seed-{seed:08x}"
        for ways in range(1, 9):
            split = f"{ways}-{16 - ways}"
            copy_exact(results / "sweep-v3" / seed_dir / f"UNPARTITIONED-A{ways}",
                       view / seed_dir / f"UNPARTITIONED-A{ways}")
            copy_exact(results / AES_ROOT / seed_dir / split, view / seed_dir / split)
    return view


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    project = args.baseline_root.resolve()
    results = project / "results/updated run"

    view = build_view(results)
    printed = subprocess.run([sys.executable, "-B", "analysis/summarize_sweep_v3.py",
                              "--results-root", str(view)], cwd=project, check=True,
                             capture_output=True, text=True).stdout
    decision = json.loads((view / "summary_v3.json").read_text())

    identity, costs = [], []
    for seed in SEEDS:
        seed_dir = f"seed-{seed:08x}"
        for ways in range(1, 9):
            split = f"{ways}-{16 - ways}"
            comparison = compare_probes(results / AES_ROOT / seed_dir / split,
                                        results / QUIET_ROOT / seed_dir / split)
            identity.append({"seed": f"{seed:#x}", "split": split, **comparison})
            way_only = json.loads((results / "sweep-v3" / seed_dir / split / "analysis.json").read_text())
            defended = json.loads((results / AES_ROOT / seed_dir / split / "analysis.json").read_text())
            costs.append({"seed": f"{seed:#x}", "split": split,
                          "way_only_encryptions": way_only["aes_encryptions"],
                          "defended_encryptions": defended["aes_encryptions"],
                          "change_vs_way_only_percent":
                              100 * (defended["aes_encryptions"] / way_only["aes_encryptions"] - 1)})
    identical = sum(row["byte_identical"] for row in identity)
    report = {
        "label": "simulated (gem5); 3 public seeds sharing one activity schedule and key",
        "primary_1_proposal_criterion": {
            "stable_collapse_point": decision["stable_collapse_point"],
            "stable_equivalence_point": decision["stable_equivalence_point"],
            "conclusions": {row["split"]: row["conclusion"] for row in decision["rows"]},
            "pass": decision["stable_collapse_point"] == "1-15",
            "summarizer_stdout": printed.splitlines(),
        },
        "primary_2_byte_identity": {
            "identical_configurations": identical, "configurations": len(identity),
            "pass": identical == len(identity), "rows": identity,
        },
        "aes_throughput_vs_way_only": costs,
        "view_root": str(view),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(printed)
    print(f"proposal criterion: collapse point {decision['stable_collapse_point']} -> "
          f"{'PASS' if report['primary_1_proposal_criterion']['pass'] else 'FAIL'}")
    print(f"byte identity: {identical}/{len(identity)} -> "
          f"{'PASS' if report['primary_2_byte_identity']['pass'] else 'FAIL'}")


if __name__ == "__main__":
    main()
