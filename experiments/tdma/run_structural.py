"""Check actual gem5 grant timestamps and the deliberate refusal diagnostic."""
import argparse
import json
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=HERE / "structural-01")
    args = parser.parse_args()
    binary = Path.home() / "eel5764/gem5-timeslot/build/RISCV/gem5.opt"
    root = args.out
    root.mkdir(exist_ok=False)
    reports = []
    for mode in ("reads", "quiet", "writebacks", "refusal"):
        out = root / mode
        out.mkdir()
        command = [str(binary), "-d", str(out), "--debug-flags=CoherentXBar",
                   "--debug-file=trace.log", str(HERE / "test_traffic.py"), "--mode", mode]
        with (out / "launcher.log").open("x") as stream:
            process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=30)
        log = (out / "launcher.log").read_text()
        if mode == "refusal":
            if process.returncode == 0 or "TDMA unsupported downstream refusal" not in log:
                raise ValueError(f"wrong refusal outcome: {log[-2500:]}")
            reports.append({"mode": mode, "expected_refusal": "PASS"})
            print("PASS deliberate downstream refusal", flush=True)
            continue
        if process.returncode:
            raise ValueError(f"{mode}: {log[-3000:]}")
        trace = (out / "trace.log").read_text()
        grants = [tuple(map(int, values)) for values in re.findall(
            r"^\s*(\d+): .*TDMA grant domain=(\d+) port=(\d+) duration=(\d+)", trace, re.MULTILINE)]
        if not grants:
            raise ValueError("no actual grant trace")
        if len({g[0] for g in grants}) != len(grants):
            raise ValueError("multiple launches in one slot")
        for tick, domain, port, duration in grants:
            if tick % 4000 or (tick // 4000) % 2 != domain or duration > 4000:
                raise ValueError(f"slot violation: {(tick, domain, port, duration)}")
        stats = {}
        for line in (out / "stats.txt").read_text().splitlines():
            parts = line.split()
            if len(parts) > 1 and parts[0].startswith("system.bus.tdma"):
                stats[parts[0].split(".")[-1]] = float(parts[1])
        if stats["tdmaGrants0"] <= 0 or (mode != "quiet" and stats["tdmaGrants1"] <= 0):
            raise ValueError("missing domain grants")
        if mode == "quiet" and stats["tdmaGrants1"] != 0:
            raise ValueError("quiet domain unexpectedly granted")
        if mode == "writebacks" and stats["tdmaWritebackGrants"] <= 0:
            raise ValueError("no dirty writebacks exercised")
        reports.append({"mode": mode, "grant_trace_checks": "PASS", "counters": stats})
        print("PASS", mode, stats, flush=True)
    read = reports[0]["counters"]["tdmaGrants0"]
    quiet = reports[1]["counters"]["tdmaGrants0"]
    if read != quiet:
        raise ValueError(f"domain 0 service changed when peer idle: {read} != {quiet}")
    (root / "validation.json").write_text(json.dumps(reports, indent=2))
    print("PASS all structural tests; quiet peer grants no extra service", flush=True)


if __name__ == "__main__":
    main()
