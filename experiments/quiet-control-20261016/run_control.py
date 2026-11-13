"""Four-case diagnostic; existing inputs/results are read-only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import string
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
TDMA = HERE.parent / "tdma"
sys.path.insert(0, str(TDMA))
from run_pilot import stats_rows
from validate import validate_case, scheduler_counters


def require_quiet(blocks: list[dict[str, float]]) -> None:
    if len(blocks) != 64:
        raise ValueError("quiet control requires exactly 64 measured intervals")
    zero = ("tdmaGrants1", "tdmaOverruns", "tdmaDownstreamRefusals", "tdmaExpressBypasses")
    for index, block in enumerate(blocks):
        for key in (*zero, "tdmaGrants0"):
            if "system.l2bus." + key not in block:
                raise ValueError(f"interval {index}: missing {key}")
        if any(block["system.l2bus." + key] != 0 for key in zero):
            raise ValueError(f"interval {index}: victim traffic or scheduler violation")
        if block["system.l2bus.tdmaGrants0"] <= 0:
            raise ValueError(f"interval {index}: missing monitor grants")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: dict) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)


def validate_quiet(project: Path, case: Path, ways: int) -> dict:
    result = validate_case(project, case, ways, True, 0)
    from analysis.summarize_mechanism import read_stats_blocks
    blocks = read_stats_blocks(case / "stats.txt.gz")
    if len(blocks) != 65:
        raise ValueError("expected 64 measured stats blocks and one logging block")
    require_quiet(blocks[:64])
    config = json.loads((case / "tdma_config.json").read_text())
    if config["slot_cycles"] != 4 or set(config["port_domains"]) != {0, 1}:
        raise ValueError("quiet TDMA configuration mismatch")
    identity = json.loads((case / "quiet_config.json").read_text())
    if identity["quiet_sha256"] != digest(HERE / "quiet_victim"):
        raise ValueError("quiet binary identity mismatch")
    output = (case / "simout.txt").read_text()
    if "quiet_control=1" not in output or "encryptions=0 " not in output:
        raise ValueError("quiet completion marker missing")
    result["tdma_counters"] = scheduler_counters(blocks[:64], True)
    result["quiet_intervals"] = 64
    result["startup_drain"] = "unverified: no per-domain outstanding counter"
    result["victim_llc_demand_accesses"] = {
        kind: (sum(block[f"system.llc.demandAccesses::cpu1.{kind}"] for block in blocks[:64])
               if all(f"system.llc.demandAccesses::cpu1.{kind}" in block for block in blocks[:64])
               else None)
        for kind in ("inst", "data")}
    return result


def run_case(project: Path, phase: str, ways: int) -> dict:
    name = f"{ways}-{16-ways}"
    old = project / "results/updated run/tdma-onx/seed-5764a5e5" / name
    reference = json.loads((old / "command.json").read_text())
    for path, expected in reference["workloads"].items():
        if digest(project / path) != expected:
            raise ValueError(f"original workload changed: {path}")
    root_name = "tdma-np0" if phase == "replay" else "tdma-nc0"
    parent = project / "results/updated run" / root_name / "seed-5764a5e5"
    final = parent / name
    if final.exists():
        raise FileExistsError(f"refusing existing case {final}")
    parent.mkdir(parents=True, exist_ok=True)
    suffix = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(6))
    staging = parent / f".{name}.tmp.{suffix}"
    staging.mkdir(exist_ok=False)
    command = list(reference["command"])
    command[command.index("-d") + 1] = str(staging)
    if len(str(staging / "probes.bin")) != reference["probe_argument_length"]:
        raise ValueError("probe argument length differs from frozen run")
    if phase == "quiet":
        index = command.index(str(TDMA / "run_contention_tdma.py"))
        command[index] = str(HERE / "quiet_adapter.py")
        command[index + 1:index + 1] = ["--quiet-binary", str(HERE / "quiet_victim")]
    manifest = {"phase": phase, "ways": ways, "command": command,
                "reference": str(old), "timeout_seconds": 240,
                "probe_argument_length": len(str(staging / "probes.bin")),
                "gem5_sha256": digest(Path(command[0])),
                "source_sha256": {p.name: digest(p) for p in HERE.glob("*.py")},
                "preregistration_sha256": digest(HERE / "PLAN.md"),
                "workloads": reference["workloads"],
                "quiet_sha256": digest(HERE / "quiet_victim") if phase == "quiet" else None}
    write_json(staging / "command.json", manifest)
    start = time.monotonic()
    try:
        with (staging / "launcher.log").open("x") as stream:
            subprocess.run(command, cwd=project, stdout=stream, stderr=subprocess.STDOUT,
                           timeout=240, check=True,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if phase == "replay":
            result = validate_case(project, staging, ways, True, 4)
            if (staging / "probes.bin").read_bytes() != (old / "probes.bin").read_bytes():
                raise ValueError("replay probe bytes differ")
            if stats_rows(staging / "stats.txt.gz") != stats_rows(old / "stats.txt.gz"):
                raise ValueError("replay simulated statistics differ")
            result["replay"] = "byte-identical probes and matching simulated statistics"
        else:
            result = validate_quiet(project, staging, ways)
        result["wall_seconds"] = round(time.monotonic() - start, 3)
        write_json(staging / "validation.json", result)
        staging.rename(final)
        print("PASS", phase, name, json.dumps(result), flush=True)
        return result
    except Exception as exc:
        write_json(staging / "failure.json", {"error": repr(exc), "wall_seconds": time.monotonic()-start})
        failed = parent / f"{name}.failed.{suffix}"
        staging.rename(failed)
        print("FAILED preserved", failed, repr(exc), flush=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--phase", choices=("replay", "quiet"), required=True)
    args = parser.parse_args()
    project = args.baseline_root.resolve()
    if args.phase == "quiet":
        for ways in (1, 8):
            guard = project / "results/updated run/tdma-np0/seed-5764a5e5" / f"{ways}-{16-ways}" / "validation.json"
            result = json.loads(guard.read_text())
            if result.get("replay") != "byte-identical probes and matching simulated statistics":
                raise ValueError("positive replay gate not satisfied")
    arm = "tdma-np0" if args.phase == "replay" else "tdma-nc0"
    (project / "results/updated run" / arm).mkdir(exist_ok=False)
    for ways in (1, 8):
        run_case(project, args.phase, ways)


if __name__ == "__main__":
    main()
