"""Opt-in causal tracing around the unchanged contention configuration."""

import argparse
import json
from pathlib import Path
import re
import runpy
import sys


UINT64_MAX = (1 << 64) - 1


def domain_for_peer(name: str) -> int:
    match = re.search(
        r"(?:^|\.)cpu([01])\.(?:[id]cache\.mem_side|mmu\.[id]tb\.walker\.port)$",
        name,
    )
    if not match:
        raise ValueError(f"unmapped TDMA peer: {name}")
    return int(match.group(1))


def llc_response_queue_name(llc: str) -> str:
    return f"{llc}.cpu_side_port-CpuSidePort"


def validate_trace_config(enabled: bool, requestor: str, base: int, size: int,
                          llc: str, queue: str) -> None:
    if not enabled:
        return
    if not requestor or not llc or not queue:
        raise ValueError("causal trace names must be non-empty")
    if base < 0 or size <= 0:
        raise ValueError("causal trace base must be non-negative and size positive")
    if base > UINT64_MAX or size > UINT64_MAX or base + size > UINT64_MAX + 1:
        raise ValueError("causal trace address overflow")


def slot_cycles(value: str) -> int:
    number = int(value)
    if number != 0 and number < 4:
        raise ValueError("slot cycles must be zero (disabled) or at least four")
    return number


def main() -> None:
    import m5
    from m5.objects.Root import Root

    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--tdma-slot-cycles", required=True, type=slot_cycles)
    parser.add_argument("--causal-trace", action="store_true")
    parser.add_argument("--causal-requestor", default="")
    parser.add_argument("--causal-vaddr-base", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--causal-vaddr-size", type=lambda value: int(value, 0), default=0)
    parser.add_argument("--causal-llc", default="system.llc")
    parser.add_argument("--causal-queue", default="")
    args, remaining = parser.parse_known_args()
    args.causal_queue = args.causal_queue or llc_response_queue_name(args.causal_llc)
    validate_trace_config(args.causal_trace, args.causal_requestor,
                          args.causal_vaddr_base, args.causal_vaddr_size,
                          args.causal_llc, args.causal_queue)
    baseline = args.baseline_root / "configs/run_contention.py"
    if not baseline.is_file():
        parser.error(f"baseline config missing: {baseline}")
    original_instantiate = m5.instantiate

    def instantiate(*positional: object, **keywords: object) -> object:
        system = Root.getInstance().system
        bus = system.l2bus
        peers = [str(port.peer) for port in bus.cpu_side_ports.elements]
        domains = [domain_for_peer(peer) for peer in peers]
        if set(domains) != {0, 1}:
            raise ValueError(f"TDMA requires both domains, got {domains}")
        bus.tdma_slot_cycles = args.tdma_slot_cycles
        bus.tdma_port_domains = domains
        if args.causal_trace:
            bus.causal_trace_requestor = args.causal_requestor
            bus.causal_trace_vaddr_base = args.causal_vaddr_base
            bus.causal_trace_vaddr_size = args.causal_vaddr_size
            bus.causal_trace_llc_name = args.causal_llc
            bus.causal_trace_queue_name = args.causal_queue
        metadata = {
            "enabled": args.causal_trace,
            "requestor": args.causal_requestor if args.causal_trace else "",
            "vaddr_base": args.causal_vaddr_base if args.causal_trace else 0,
            "vaddr_size": args.causal_vaddr_size if args.causal_trace else 0,
            "llc": args.causal_llc if args.causal_trace else "",
            "queue": args.causal_queue if args.causal_trace else "",
            "slot_cycles": args.tdma_slot_cycles,
            "peers": peers,
            "port_domains": domains,
            "baseline_config": str(baseline),
        }
        with (Path(m5.options.outdir) / "causal_config.json").open("x") as stream:
            json.dump(metadata, stream, indent=2)
        return original_instantiate(*positional, **keywords)

    m5.instantiate = instantiate
    sys.argv = ["configs/run_contention.py", *remaining]
    try:
        runpy.run_path(str(baseline), run_name="__m5_main__")
    finally:
        m5.instantiate = original_instantiate


if __name__ in ("__main__", "__m5_main__"):
    main()
