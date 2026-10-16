"""Fresh-process endpoint runs in new folders; original project is read-only."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import secrets
import shlex
import string
import subprocess
import sys
import time
from validate import validate_case

HERE = Path(__file__).resolve().parent
SEEDS = (0x5764A5E5, 0x5764A5E6, 0x5764A5E7)


def build_plan(seeds: tuple[int, ...] = SEEDS) -> list[tuple[str, int, int]]:
    return [(arm, seed, ways) for seed in seeds for ways in (1, 8) for arm in ("off", "way", "onx")]


def case_path(arm: str, seed: int, ways: int, guard: bool = False) -> Path:
    case = f"UNPARTITIONED-A{ways}" if arm == "off" else f"{ways}-{16-ways}"
    return Path("results/updated run") / ("tdma-gd0" if guard else f"tdma-{arm}") / f"seed-{seed:08x}" / case


def reserve_output(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=False)


def stats_rows(path: Path) -> list[str]:
    with gzip.open(path, "rt") as stream:
        return [line.strip() for line in stream if line.strip() and
                not line.startswith("host") and " .tdma" not in line and
                not line.startswith("system.l2bus.tdma") and not line.startswith("system.membus.tdma")]


def run_case(project: Path, original: Path, experimental: Path,
             arm: str, seed: int, ways: int, guard: bool) -> dict:
    final = project / case_path(arm, seed, ways, guard)
    if final.exists():
        raise FileExistsError(f"refusing to overwrite {final}")
    final.parent.mkdir(parents=True, exist_ok=True)
    alphabet = string.ascii_letters + string.digits
    staging = final.parent / f".{final.name}.tmp.{''.join(secrets.choice(alphabet) for _ in range(6))}"
    reserve_output(staging)
    slot = 0 if guard else (4 if arm == "onx" else 0)
    binary = experimental if guard or arm == "onx" else original
    config = ([str(HERE / "run_contention_tdma.py"), "--baseline-root", str(project),
               "--tdma-slot-cycles", str(slot)] if guard or arm == "onx" else ["configs/run_contention.py"])
    split = "off" if arm == "off" else f"{ways}-{16-ways}"
    command = [str(binary), "-r", "-e", "-d", str(staging), "--stats-file=stats.txt.gz", *config,
               "--split", split, "--l1d-size", "4KiB", "--monitor-ways", str(ways),
               "--workload-seed", str(seed), "--monitor-sink", "file", "--monitor-variant", "v3",
               "--stats-per-interval"]
    manifest = {"command": command, "slot_cycles": slot, "arm": arm, "seed": seed, "ways": ways,
                "preregistration_sha256": hashlib.sha256((HERE / "PREREGISTRATION.md").read_bytes()).hexdigest(),
                "gem5_patch_sha256": hashlib.sha256((HERE / "gem5-timeslot.patch").read_bytes()).hexdigest(),
                "probe_argument_length": len(str(staging / "probes.bin")),
                "workloads": {name: hashlib.sha256((project / name).read_bytes()).hexdigest()
                              for name in ("workloads/monitor_v3_l1d4k", "workloads/victim_l1d4k")}}
    (staging / "command.json").write_text(json.dumps(manifest, indent=2))
    (staging / "cmd.txt").write_text(shlex.join(command) + "\n")
    start = time.monotonic()
    try:
        with (staging / "launcher.log").open("x") as stream:
            subprocess.run(command, cwd=project, stdout=stream, stderr=subprocess.STDOUT,
                           timeout=240, check=True)
        validation = validate_case(project, staging, ways, arm != "off", slot)
        if guard:
            reference = project / "results/updated run/mech-std" / f"seed-{seed:08x}" / final.name
            if (staging / "probes.bin").read_bytes() != (reference / "probes.bin").read_bytes():
                raise ValueError("disabled regression: probe bytes differ")
            if stats_rows(staging / "stats.txt.gz") != stats_rows(reference / "stats.txt.gz"):
                raise ValueError("disabled regression: simulated statistics differ")
            validation["disabled_regression"] = "byte-identical probes and matching simulated statistics"
        validation["wall_seconds"] = round(time.monotonic() - start, 3)
        (staging / "validation.json").write_text(json.dumps(validation, indent=2))
        staging.rename(final)
        print("PASS", final, validation, flush=True)
        return validation
    except Exception:
        failed = final.with_name(final.name + ".failed." + time.strftime("%Y%m%dT%H%M%S"))
        staging.rename(failed)
        print("FAILED preserved at", failed, flush=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--phase", choices=("guard", "pilot", "remaining"), required=True)
    parser.add_argument("--list-plan", action="store_true")
    args = parser.parse_args()
    original = Path.home() / "eel5764/gem5/build/RISCV/gem5.opt"
    experimental = Path.home() / "eel5764/gem5-timeslot/build/RISCV/gem5.opt"
    plan = build_plan(SEEDS[1:] if args.phase == "remaining" else SEEDS[:1])
    if args.phase == "guard":
        plan = [item for item in plan if item[0] != "onx"]
    if args.list_plan:
        for item in plan: print(item, case_path(*item, guard=args.phase == "guard"))
        return
    for item in plan:
        print("RUN", item, flush=True)
        run_case(args.baseline_root.resolve(), original, experimental, *item, guard=args.phase == "guard")


if __name__ == "__main__":
    main()
