"""Opt-in adapter around the unchanged original gem5 configuration."""
import argparse
import json
from pathlib import Path
import re
import runpy
import sys


def slot_cycles(value: str) -> int:
    number = int(value)
    if number != 0 and number < 4:
        raise ValueError("slot cycles must be zero (disabled) or at least four")
    return number


def domain_for_peer(name: str) -> int:
    match = re.search(r"(?:^|\.)cpu([01])\.(?:[id]cache\.mem_side|mmu\.[id]tb\.walker\.port)$", name)
    if not match:
        raise ValueError(f"unmapped TDMA peer: {name}")
    return int(match.group(1))


def main() -> None:
    import m5
    from m5.objects.Root import Root

    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--baseline-root", required=True, type=Path)
    parser.add_argument("--tdma-slot-cycles", required=True, type=slot_cycles)
    args, remaining = parser.parse_known_args()
    baseline = args.baseline_root / "configs/run_contention.py"
    if not baseline.is_file():
        parser.error(f"baseline config missing: {baseline}")
    original_instantiate = m5.instantiate

    def instantiate(*positional, **keywords):
        system = Root.getInstance().system
        bus = system.l2bus
        peers = [str(port.peer) for port in bus.cpu_side_ports.elements]
        domains = [domain_for_peer(peer) for peer in peers]
        if set(domains) != {0, 1}:
            raise ValueError(f"TDMA requires both domains, got {domains}")
        bus.tdma_slot_cycles = args.tdma_slot_cycles
        bus.tdma_port_domains = domains
        metadata = {"slot_cycles": args.tdma_slot_cycles, "peers": peers,
                    "port_domains": domains, "baseline_config": str(baseline)}
        with (Path(m5.options.outdir) / "tdma_config.json").open("x") as stream:
            json.dump(metadata, stream, indent=2)
        return original_instantiate(*positional, **keywords)

    # Temporary function replacement injects parameters only after the original
    # config has connected real ports; the original file is never edited.
    m5.instantiate = instantiate
    sys.argv = ["configs/run_contention.py", *remaining]
    try:
        runpy.run_path(str(baseline), run_name="__m5_main__")
    finally:
        m5.instantiate = original_instantiate


if __name__ in ("__main__", "__m5_main__"):
    main()
