"""Full-defense wrapper around run_leakage.py (simulator only).

Adds the paper's two interconnect mechanisms to a leakage run:
  * request time slots at the shared L1-to-LLC crossbar (--tdma-slot-cycles,
    the paper used 4), exactly as experiments/tdma/run_contention_tdma.py
    sets them, and
  * per-domain LLC response queues (--respq), exactly as
    experiments/respq-defense-20261018/run_contention_respq.py sets them.
Everything else (workloads, schedule, tracing parameters, leak_config.json) is
run_leakage.py, unchanged.  Needs a gem5 binary built from the paper's defense
tree together with experiments/aes-leakage/gem5_ext (see gem5_build.md); on any
other binary the parameters do not exist and the run is refused.

  gem5.opt -r -e --debug-flags=VictimTable --debug-file=victim_table.trace \\
      -d <out> experiments/aes-leakage/run_leakage_defense.py \\
      --tdma-slot-cycles 4 --respq --victim-variant full-scrub \\
      --build-dir <build> --split 8-8 --monitor-ways 8

It writes defense_config.json next to leak_config.json.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_leakage  # noqa: E402

# Domain index = core index, as in the paper's adapters.
RESPONSE_DOMAIN_PREFIXES = ["cpu0.", "cpu1."]
_PEER = re.compile(
    r"(?:^|\.)cpu([01])\.(?:[id]cache\.mem_side|mmu\.[id]tb\.walker\.port)$")


def slot_cycles(value):
    number = int(value)
    if number != 0 and number < 4:
        raise argparse.ArgumentTypeError(
            "slot cycles must be zero (disabled) or at least four")
    return number


def domain_for_peer(name):
    match = _PEER.search(name)
    if not match:
        raise run_leakage.AdapterError("unmapped time-slot peer: %s" % name)
    return int(match.group(1))


def apply_defense(system, slots, respq):
    """Set the defense parameters on a built system; returns the metadata that
    is written to defense_config.json."""
    bus = system.l2bus
    peers = [str(port.peer) for port in bus.cpu_side_ports.elements]
    domains = [domain_for_peer(peer) for peer in peers]
    if set(domains) != {0, 1}:
        raise run_leakage.AdapterError(
            "time slots need both domains, got %s" % domains)
    try:
        bus.tdma_slot_cycles = slots
        bus.tdma_port_domains = domains
        if respq:
            system.llc.response_domain_prefixes = RESPONSE_DOMAIN_PREFIXES
    except AttributeError as exc:
        raise run_leakage.AdapterError(
            "this gem5 binary lacks the defense parameters (%s); build the "
            "defense tree with EXTRAS=<...>/experiments/aes-leakage/gem5_ext "
            "(see gem5_build.md)" % exc) from exc
    return {"format": "aes-leakage-defense-config-v1",
            "tdma_slot_cycles": slots, "peers": peers, "port_domains": domains,
            "respq": bool(respq),
            "response_domain_prefixes":
                RESPONSE_DOMAIN_PREFIXES if respq else None}


def main(argv=None, m5_module=None, baseline=None, root=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    parser = argparse.ArgumentParser(add_help=False, allow_abbrev=False)
    parser.add_argument("--tdma-slot-cycles", required=True, type=slot_cycles)
    parser.add_argument("--respq", action="store_true")
    args, remaining = parser.parse_known_args(argv)

    if m5_module is None:
        import m5 as m5_module
    if root is None:
        from m5.objects.Root import Root as root
    original_instantiate = m5_module.instantiate

    def instantiate(*positional, **keywords):
        try:
            metadata = apply_defense(root.getInstance().system,
                                     args.tdma_slot_cycles, args.respq)
        except run_leakage.AdapterError as exc:
            sys.exit("error: %s" % exc)
        with (Path(m5_module.options.outdir) / "defense_config.json").open("x") \
                as stream:
            json.dump(metadata, stream, indent=2)
            stream.write("\n")
        return original_instantiate(*positional, **keywords)

    # run_leakage.main() saves whatever m5.instantiate is when it starts and
    # calls it after setting the tracing parameters, so installing this wrapper
    # first chains the two: tracing parameters, then defense parameters, then
    # the real instantiate.
    m5_module.instantiate = instantiate
    try:
        run_leakage.main(remaining, m5_module=m5_module, baseline=baseline,
                         root=root)
    finally:
        m5_module.instantiate = original_instantiate


if __name__ in ("__main__", "__m5_main__"):
    main()
