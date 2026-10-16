#!/usr/bin/env python3
"""Mechanism study runner (PREREGISTRATION_MECHANISM_20261014.md).

Tests whether the hit-timing leak travels through the shared L1-to-LLC
crossbar request layer (system.l2bus.reqLayer0).  Four crossbar settings x
three public seeds x A in {1, 8} x {matched control, partitioned treatment}
= 48 fresh gem5 processes, all with the v3 monitor and one statistics block
per labelled interval.

Each setting writes to its own root, `results/updated run/mech-<setting>/`.
The root names have the same length as `sweep-v3`, so the monitor's
probe-file argument (and therefore its stack layout) matches the v3 sweep.
Completed cases are never replaced; a failed case is preserved as
`<case>.failed.<timestamp>`.  Mirrors scripts/run_contention_control.sh,
which is left unchanged.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import random
import shlex
import string
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GEM5 = Path(os.environ.get("GEM5", Path.home() / "eel5764/gem5/build/RISCV/gem5.opt"))
PUBLIC_SEEDS = (0x5764A5E5, 0x5764A5E6, 0x5764A5E7)
MONITOR_WAYS = (1, 8)
WORKLOADS = ("workloads/monitor_v3_l1d4k", "workloads/victim_l1d4k")
RESULTS_PARENT = Path("results/updated run")
STATS_FILE = "stats.txt.gz"
INTERVALS = 64
# Ordered from the default crossbar to the near-ideal one.
SETTINGS = {
    "std": [],
    "wid": ["--l2bus-width", "128"],
    "clk": ["--l2bus-clock", "cpu"],
    "ide": ["--l2bus-width", "512", "--l2bus-header-latency", "0", "--l2bus-clock", "cpu"],
}
BEGIN_STATS = "---------- Begin Simulation Statistics ----------"


@dataclass(frozen=True)
class MechItem:
    setting: str
    seed: int
    monitor_ways: int
    role: str          # "control" or "treatment"

    @property
    def split_arg(self) -> str:
        return "off" if self.role == "control" else f"{self.monitor_ways}-{16 - self.monitor_ways}"

    @property
    def case_name(self) -> str:
        return (f"UNPARTITIONED-A{self.monitor_ways}" if self.role == "control"
                else f"{self.monitor_ways}-{16 - self.monitor_ways}")


def setting_root(setting: str) -> Path:
    root = RESULTS_PARENT / f"mech-{setting}"
    assert len(root.name) == len("sweep-v3"), root
    return root


def build_plan(settings=tuple(SETTINGS)) -> list[MechItem]:
    return [MechItem(s, seed, a, role)
            for s in settings for seed in PUBLIC_SEEDS
            for a in MONITOR_WAYS for role in ("control", "treatment")]


def case_directory(item: MechItem) -> Path:
    return setting_root(item.setting) / f"seed-{item.seed:08x}" / item.case_name


def gem5_command(item: MechItem, staging: Path) -> list[str]:
    return [str(GEM5), "-r", "-e", "-d", str(staging), f"--stats-file={STATS_FILE}",
            "configs/run_contention.py",
            "--split", item.split_arg, "--l1d-size", "4KiB",
            "--monitor-ways", str(item.monitor_ways), "--workload-seed", str(item.seed),
            "--monitor-sink", "file", "--monitor-variant", "v3",
            "--stats-per-interval", *SETTINGS[item.setting]]


def stats_block_count(path: Path) -> int:
    with gzip.open(path, "rt") as stream:
        return sum(line.startswith(BEGIN_STATS) for line in stream)


def check_outputs(staging: Path, item: MechItem) -> list[str]:
    """Return the list of problems (empty when the case is valid)."""
    problems = []
    for name in (STATS_FILE, "run_meta.json", "config.ini", "config.json",
                 "simout.txt", "simerr.txt", "probes.bin"):
        if not (staging / name).is_file() or (staging / name).stat().st_size == 0:
            problems.append(f"{name} missing or empty")
    if problems:
        return problems
    simout = (staging / "simout.txt").read_text()
    lines = simout.splitlines()
    if not any(l.startswith("victim aes_self_test=PASS ") for l in lines):
        problems.append("AES self-test marker missing")
    if "monitor status=PASS records=16384" not in lines:
        problems.append("monitor completion marker missing")
    if not any(l.startswith(f"OK contention split={item.split_arg} ") for l in lines):
        problems.append("gem5 completion marker missing")
    if (staging / "probes.bin").stat().st_size != 262144:
        problems.append("probes.bin is not 262144 bytes")
    blocks = stats_block_count(staging / STATS_FILE)
    if blocks != INTERVALS + 1:
        problems.append(f"expected {INTERVALS} interval blocks plus a final block, found {blocks}")
    meta = json.loads((staging / "run_meta.json").read_text())
    if meta.get("monitor_variant") != "v3" or not meta.get("mechanism", {}).get("stats_per_interval"):
        problems.append("run_meta.json lacks the v3 / per-interval markers")
    return problems


def completed_case_is_valid(item: MechItem) -> bool:
    final = case_directory(item)
    return final.is_dir() and not check_outputs(final, item)


def staging_directory(parent: Path, case_name: str) -> Path:
    # Six random characters, like `mktemp -d .X.tmp.XXXXXX`, so the probe-file
    # path has the same length as in the v3 sweep.
    alphabet = string.ascii_letters + string.digits
    while True:
        path = parent / f".{case_name}.tmp.{''.join(random.choices(alphabet, k=6))}"
        try:
            path.mkdir()
            return path
        except FileExistsError:
            continue


def run_case(item: MechItem) -> None:
    final = case_directory(item)
    if final.exists():
        raise SystemExit(f"error: refusing to replace existing {final}")
    parent = (PROJECT_ROOT / final.parent).resolve()
    parent.mkdir(parents=True, exist_ok=True)
    staging = staging_directory(parent, item.case_name)
    command = gem5_command(item, staging)
    (staging / "cmd.txt").write_text(" ".join(shlex.quote(c) for c in command) + " \n")
    with (staging / "workload_sha256.txt").open("w") as stream:
        for binary in WORKLOADS:
            digest = hashlib.sha256((PROJECT_ROOT / binary).read_bytes()).hexdigest()
            stream.write(f"{digest}  {binary}\n")
    try:
        subprocess.run(command, cwd=PROJECT_ROOT, check=True)
        problems = check_outputs(staging, item)
        if problems:
            raise RuntimeError("; ".join(problems))
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        failed = parent / f"{item.case_name}.failed.{time.strftime('%Y%m%dT%H%M%S')}"
        staging.rename(failed)
        raise SystemExit(f"error: {item} failed ({exc}); preserved at {failed}")
    staging.rename(PROJECT_ROOT / final)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--settings", nargs="+", choices=list(SETTINGS), default=list(SETTINGS))
    parser.add_argument("--resume", action="store_true",
                        help="skip cases that already completed and validate")
    parser.add_argument("--list-plan", action="store_true")
    args = parser.parse_args()
    os.chdir(PROJECT_ROOT)
    plan = build_plan(tuple(args.settings))
    if args.list_plan:
        for number, item in enumerate(plan, 1):
            print(number, item.setting, f"0x{item.seed:08x}", item.case_name, case_directory(item))
        return
    if not GEM5.is_file():
        raise SystemExit(f"error: gem5 binary not found: {GEM5}")
    for setting in args.settings:
        root = setting_root(setting)
        if root.exists() and not args.resume:
            raise SystemExit(f"error: refusing to reuse existing {root}; use --resume")
        root.mkdir(parents=True, exist_ok=True)
        manifest = {"setting": setting, "gem5_args": SETTINGS[setting],
                    "items": [asdict(i) for i in plan if i.setting == setting]}
        path = root / "run_plan.json"
        if not path.exists():
            path.write_text(json.dumps(manifest, indent=2) + "\n")
        elif json.loads(path.read_text()) != manifest:
            raise SystemExit(f"error: {path} does not match this program")
    for number, item in enumerate(plan, 1):
        if args.resume and completed_case_is_valid(item):
            print(f"SKIP {number}/{len(plan)} {case_directory(item)}", flush=True)
            continue
        print(f"RUN {number}/{len(plan)} {item.setting} seed=0x{item.seed:08x} {item.case_name}", flush=True)
        run_case(item)
        print(f"OK {case_directory(item)}", flush=True)


if __name__ == "__main__":
    main()
