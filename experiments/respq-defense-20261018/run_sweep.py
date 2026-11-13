"""Defense sweep over the proposal's design: 3 seeds x A=1..8, AES and quiet victims.

Each case reuses its frozen v3 treatment's baseline arguments and probe-path length, and
adds only request TDMA (4-cycle slots) and per-domain LLC response queues.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import json
import os
from pathlib import Path
import secrets
import shlex
import string
import subprocess
import sys
import threading


HERE = Path(__file__).resolve().parent
EXECUTABLE = Path.home() / "eel5764/gem5-respq/build/RISCV/gem5.opt"
QUIET_BINARY = HERE.parent / "quiet-control-20261016/quiet_victim"
SEEDS = (0x5764A5E5, 0x5764A5E6, 0x5764A5E7)
AES_ROOT = "tdma-rsa"
QUIET_ROOT = "tdma-rsq"
TIMEOUT_SECONDS = 600
VIOLATIONS = ("tdmaOverruns", "tdmaDownstreamRefusals", "tdmaExpressBypasses")


@dataclass(frozen=True)
class Case:
    root: str
    seed: int
    ways: int

    @property
    def split(self) -> str:
        return f"{self.ways}-{16 - self.ways}"

    @property
    def quiet(self) -> bool:
        return self.root == QUIET_ROOT


def plan_cases() -> list[Case]:
    return [Case(root, seed, ways) for root in (AES_ROOT, QUIET_ROOT)
            for seed in SEEDS for ways in range(1, 9)]


def v3_arguments(cmd_txt: str) -> list[str]:
    words = shlex.split(cmd_txt)
    return words[words.index("configs/run_contention.py") + 1:]


def v3_probe_length(cmd_txt: str) -> int:
    words = shlex.split(cmd_txt)
    return len(words[words.index("-d") + 1] + "/probes.bin")


def staging_name(parent: Path, probe_length: int) -> str:
    width = probe_length - len(str(parent / "x" / "probes.bin")) + 1
    if width < 1:
        raise ValueError("probe argument length unreachable under this parent")
    return "".join(secrets.choice(string.ascii_lowercase) for _ in range(width))


def sweep_command(output: Path, executable: Path, adapter: Path, project: Path,
                  baseline_args: list[str], quiet: Path | None) -> list[str]:
    command = [str(executable), "-r", "-e", "-d", str(output), str(adapter), "--respq"]
    if quiet is not None:
        command += ["--quiet-binary", str(quiet)]
    return command + ["--baseline-root", str(project), "--tdma-slot-cycles", "4",
                      *baseline_args]


def tdma_gate_plain(case: Path) -> dict:
    lines = [line.strip() for line in (case / "stats.txt").read_text().splitlines()
             if ".tdma" in line]
    if not lines:
        raise ValueError("no tdma counters in case statistics")
    for line in lines:
        fields = line.split()
        if fields[0].rsplit(".", 1)[-1] in VIOLATIONS and float(fields[1]) != 0:
            raise ValueError(f"scheduler violation {fields[0]}={fields[1]}")
    return {"tdma_lines": len(lines), "violations": 0}


def llc_prefixes(case: Path) -> str:
    section = None
    for line in (case / "config.ini").read_text().splitlines():
        if line.startswith("["):
            section = line.strip("[]")
        elif section == "system.llc" and line.startswith("response_domain_prefixes="):
            return line.split("=", 1)[1]
    raise ValueError("system.llc has no response_domain_prefixes parameter")


def run_case(project: Path, case: Case, stop: threading.Event) -> str:
    if stop.is_set():
        return f"SKIPPED {case}"
    v3 = project / "results/updated run/sweep-v3" / f"seed-{case.seed:08x}" / case.split
    cmd_txt = (v3 / "cmd.txt").read_text()
    parent = project / "results/updated run" / case.root / f"seed-{case.seed:08x}"
    final = parent / case.split
    if final.exists():
        raise FileExistsError(final)
    stage = staging_name(parent, v3_probe_length(cmd_txt))
    staging = parent / stage
    staging.mkdir()
    command = sweep_command(staging, EXECUTABLE, HERE / "run_contention_respq.py", project,
                            v3_arguments(cmd_txt), QUIET_BINARY if case.quiet else None)
    (staging / "command.json").write_text(json.dumps({
        "case": {"root": case.root, "seed": case.seed, "ways": case.ways},
        "command": command, "v3_treatment": str(v3), "timeout_seconds": TIMEOUT_SECONDS,
        "probe_argument_length": v3_probe_length(cmd_txt)}, indent=2) + "\n")
    try:
        with (staging / "launcher.log").open("x") as stream:
            subprocess.run(command, cwd=project, stdout=stream, stderr=subprocess.STDOUT,
                           timeout=TIMEOUT_SECONDS, check=True,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        if llc_prefixes(staging) != "cpu0. cpu1.":
            raise ValueError("defense not enabled on system.llc")
        result = {"defense": "cpu0. cpu1.", **tdma_gate_plain(staging)}
        if not case.quiet:
            subprocess.run([sys.executable, "-B", "analysis/analyze_contention.py",
                            "--results", str(staging), "--statistic", "max-set"],
                           cwd=project, check=True, stdout=subprocess.DEVNULL)
            analysis = json.loads((staging / "analysis.json").read_text())
            checks = {
                "mapping": analysis.get("probe_mapping_validation") == "PASS congruent",
                "disjoint": analysis.get("isolation_validation") == "PASS disjoint"
                and analysis.get("isolation_violations") == 0,
                "hit_only": analysis.get("hit_only_error") is None,
                "encryptions": analysis.get("aes_encryptions", 0) > 0,
            }
            if not all(checks.values()):
                raise ValueError(f"analysis checks failed: {checks}")
            result["analysis_checks"] = checks
        (staging / "validation.json").write_text(json.dumps(result, indent=2) + "\n")
        staging.rename(final)
        return f"PASS {case.root} {case.seed:#x} {case.split}"
    except Exception as exc:
        stop.set()
        (staging / "failure.json").write_text(json.dumps({"error": repr(exc)}, indent=2) + "\n")
        staging.rename(parent / f"{case.split}.failed.{stage}")
        return f"FAILED {case.root} {case.seed:#x} {case.split}: {exc!r}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=6)
    args = parser.parse_args()
    project = args.baseline_root.resolve()
    for root in (AES_ROOT, QUIET_ROOT):
        if (project / "results/updated run" / root).exists():
            raise FileExistsError(root)
    for root in (AES_ROOT, QUIET_ROOT):
        for seed in SEEDS:
            (project / "results/updated run" / root / f"seed-{seed:08x}").mkdir(parents=True)
    stop = threading.Event()
    failures = 0
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for line in pool.map(lambda case: run_case(project, case, stop), plan_cases()):
            print(line, flush=True)
            failures += not line.startswith("PASS")
    if failures:
        raise SystemExit(f"{failures} case(s) failed or were skipped")


if __name__ == "__main__":
    main()
