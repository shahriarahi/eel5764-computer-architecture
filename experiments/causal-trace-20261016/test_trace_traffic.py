"""Short wrapper around the real monitor/AES configuration for hook testing."""

import argparse
from pathlib import Path
import runpy
import sys


WARMUP_TICKS = 1_000_000_000
MEASUREMENT_TICKS = 20_000_000


class StructuralStop:
    def getCause(self) -> str:
        return "structural harness stop"


def install_short_profile(baseline_globals: dict) -> None:
    original_profile = baseline_globals["apply_experiment_profile"]

    def short_profile(config: dict, l1d_size: str) -> None:
        original_profile(config, l1d_size)
        config["warmup_ticks"] = WARMUP_TICKS
        config["measure_ticks"] = MEASUREMENT_TICKS
        config["logging_grace_ticks"] = 0

    baseline_globals["apply_experiment_profile"] = short_profile


def main() -> None:
    import m5
    from m5.objects.Root import Root
    from run_contention_causal import llc_response_queue_name

    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--trace", action="store_true")
    parser.add_argument("--vaddr-base", required=True, type=lambda value: int(value, 0))
    parser.add_argument("--vaddr-size", required=True, type=lambda value: int(value, 0))
    args = parser.parse_args()
    baseline = args.baseline_root / "configs/run_contention.py"
    namespace = runpy.run_path(str(baseline), run_name="causal_structural_baseline")
    baseline_globals = namespace["main"].__globals__
    install_short_profile(baseline_globals)

    original_instantiate = m5.instantiate
    def instantiate(*positional: object, **keywords: object) -> object:
        bus = Root.getInstance().system.l2bus
        peers = [str(port.peer) for port in bus.cpu_side_ports.elements]
        bus.tdma_slot_cycles = 4
        bus.tdma_port_domains = [
            int(peer.split(".cpu", 1)[1][0]) for peer in peers
        ]
        if args.trace and hasattr(bus, "causal_trace_requestor"):
            bus.causal_trace_requestor = "cpu0.data"
            bus.causal_trace_vaddr_base = args.vaddr_base
            bus.causal_trace_vaddr_size = args.vaddr_size
            bus.causal_trace_llc_name = "system.llc"
            bus.causal_trace_queue_name = llc_response_queue_name("system.llc")
        return original_instantiate(*positional, **keywords)

    original_simulate = m5.simulate
    calls = 0
    def simulate(*positional: object, **keywords: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 3:
            return StructuralStop()
        return original_simulate(*positional, **keywords)

    m5.instantiate = instantiate
    m5.simulate = simulate
    sys.argv = [
        str(baseline), "--split", "1-15", "--l1d-size", "4KiB",
        "--monitor-ways", "1", "--workload-seed", "1466213861",
        "--monitor-sink", "file", "--monitor-variant", "v3",
    ]
    try:
        baseline_globals["main"]()
    finally:
        m5.instantiate = original_instantiate
        m5.simulate = original_simulate


if __name__ in ("__main__", "__m5_main__"):
    main()
