"""Final read-only audit of endpoint outputs and preservation evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from run_pilot import build_plan, case_path, stats_rows
from validate import validate_case

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    args = parser.parse_args()
    project = args.baseline_root.resolve()
    preregistration = hashlib.sha256((HERE / "PREREGISTRATION.md").read_bytes()).hexdigest()
    patch = hashlib.sha256((HERE / "gem5-timeslot.patch").read_bytes()).hexdigest()
    for arm, seed, ways in build_plan():
        case = project / case_path(arm, seed, ways)
        validate_case(project, case, ways, arm != "off", 4 if arm == "onx" else 0)
        command = json.loads((case / "command.json").read_text())
        if command["preregistration_sha256"] != preregistration or command["gem5_patch_sha256"] != patch:
            raise ValueError("frozen preregistration/patch fingerprint mismatch")
    print("PASS 18/18 efficacy cases: records, mapping, isolation and scheduler gates", flush=True)
    for arm, seed, ways in build_plan((0x5764A5E5,)):
        if arm == "onx":
            continue
        guard = project / case_path(arm, seed, ways, guard=True)
        reference = project / "results/updated run/mech-std" / f"seed-{seed:08x}" / guard.name
        if (guard / "probes.bin").read_bytes() != (reference / "probes.bin").read_bytes():
            raise ValueError("guard probe mismatch")
        if stats_rows(guard / "stats.txt.gz") != stats_rows(reference / "stats.txt.gz"):
            raise ValueError("guard simulated-statistics mismatch")
    print("PASS 4/4 disabled guards: identical probes and simulated statistics", flush=True)
    for arm, seed, ways in build_plan():
        if arm == "onx":
            continue
        case = project / case_path(arm, seed, ways)
        reference = project / "results/updated run/mech-std" / f"seed-{seed:08x}" / case.name
        if (case / "probes.bin").read_bytes() != (reference / "probes.bin").read_bytes():
            raise ValueError("fresh baseline probe mismatch")
    print("PASS 12/12 fresh baseline arms: identical probes to original study", flush=True)
    subprocess.run([sys.executable, str(HERE / "preserve.py"), "verify", str(project),
                    str(HERE / "preservation.json"), "--gem5",
                    str(Path.home() / "eel5764/gem5/build/RISCV/gem5.opt")], check=True)
    summary = json.loads((HERE / "summary-final/summary.json").read_text())
    if summary["pilot_only"] or len(summary["rows"]) != 6 or any(r["seeds"] != 3 for r in summary["rows"]):
        raise ValueError("final summary is incomplete")
    print("PASS final summary: six cells, three public seeds each", flush=True)


if __name__ == "__main__":
    main()
