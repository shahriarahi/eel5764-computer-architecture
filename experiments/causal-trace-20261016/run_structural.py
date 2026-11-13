"""Run and validate short trace-enabled and trace-disabled gem5 cases."""

import argparse
import json
from pathlib import Path
import subprocess

from trace_analysis import STAGES, match_timelines, read_trace


STAGE_ORDER = (
    "request_admit", "llc_response_ready", "response_enqueue",
    "response_send_attempt", "response_retry", "response_dequeue",
    "xbar_response_forward", "cpu_delivery",
)
# Retries occur only under response backpressure, so they are measured, not required.
CONDITIONAL_STAGES = {"response_retry"}
VIOLATION_STATS = (
    "tdmaOverruns", "tdmaDownstreamRefusals", "tdmaExpressBypasses",
)


def validate_enabled_trace(path: Path) -> dict:
    events = read_trace(path)
    present = {event.stage for event in events}
    missing = [stage for stage in STAGE_ORDER
               if stage not in present and stage not in CONDITIONAL_STAGES]
    if missing:
        raise ValueError("missing stages: " + ", ".join(missing))
    timelines = match_timelines(events)
    return {
        "events": len(events),
        "matched_timelines": len(timelines),
        "stages": [stage for stage in STAGE_ORDER if stage in present],
        "response_retries": sum(len(t["response_retries"]) for t in timelines),
    }


def validate_disabled_trace(path: Path) -> dict:
    events = read_trace(path) if path.exists() else []
    if events:
        raise ValueError("trace-disabled case emitted causal records")
    return {"events": 0}


def statistics(path: Path) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) >= 2:
            try:
                values[fields[0]] = float(fields[1])
            except ValueError:
                pass
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument(
        "--binary", type=Path,
        default=Path.home() / "eel5764/gem5-causal/build/RISCV/gem5.opt",
    )
    args = parser.parse_args()
    project = args.baseline_root.resolve()
    root = args.out.resolve()
    if root.exists():
        raise FileExistsError(root)
    root.mkdir(parents=True)
    reference = project / "results/updated run/tdma-onx/seed-5764a5e5/1-15/run_meta.json"
    metadata = json.loads(reference.read_text())
    reports = {}
    for mode in ("disabled", "enabled"):
        case = root / mode
        case.mkdir()
        command = [
            str(args.binary), "-d", str(case), "--debug-flags=CausalTrace",
            "--debug-file=causal.log", str(Path(__file__).with_name("test_trace_traffic.py")),
            "--baseline-root", str(project),
            "--vaddr-base", hex(int(metadata["probe_vaddr_base"])),
            "--vaddr-size", hex(int(metadata["probe_vaddr_size"])),
        ]
        if mode == "enabled":
            command.append("--trace")
        (case / "command.json").write_text(json.dumps(command, indent=2) + "\n")
        with (case / "launcher.log").open("x") as stream:
            process = subprocess.run(
                command, cwd=project, stdout=stream, stderr=subprocess.STDOUT,
                timeout=120,
            )
        if process.returncode:
            raise RuntimeError(f"{mode} gem5 exit code {process.returncode}")
        trace = case / "causal.log"
        report = (validate_enabled_trace(trace) if mode == "enabled"
                  else validate_disabled_trace(trace))
        stats = statistics(case / "stats.txt")
        violations = {
            key: stats.get(f"system.l2bus.{key}", 0.0)
            for key in VIOLATION_STATS
        }
        if any(violations.values()):
            raise ValueError(f"scheduler violations: {violations}")
        report.update({"simTicks": stats["simTicks"], "violations": violations})
        reports[mode] = report
    if reports["disabled"]["simTicks"] != reports["enabled"]["simTicks"]:
        raise ValueError("tracing changed simulated time")
    (root / "validation.json").write_text(json.dumps(reports, indent=2) + "\n")
    print("PASS structural causal tracing", json.dumps(reports), flush=True)


if __name__ == "__main__":
    main()
