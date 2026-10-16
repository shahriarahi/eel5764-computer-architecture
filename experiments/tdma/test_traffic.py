"""Actual gem5 traffic harness; run with the experimental executable."""
import argparse


def main() -> None:
    import m5
    from m5.objects import (System, SrcClockDomain, VoltageDomain, AddrRange,
                            L2XBar, SimpleMemory, PyTrafficGen, Cache, Root)

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("reads", "quiet", "writebacks", "refusal"), required=True)
    args = parser.parse_args()
    system = System()
    system.clk_domain = SrcClockDomain(clock="1GHz", voltage_domain=VoltageDomain())
    system.mem_mode = "timing"
    system.mem_ranges = [AddrRange("1MiB")]
    system.cache_line_size = 64
    # This synthetic bus connects directly to memory, so it must terminate
    # coherence operations that the production hierarchy's lower bus handles.
    system.bus = L2XBar(tdma_slot_cycles=4, tdma_port_domains=[0, 1], point_of_coherency=True)
    system.memory = SimpleMemory(range=system.mem_ranges[0], latency="10ns",
                                 bandwidth="1MiB/s" if args.mode == "refusal" else "1TiB/s")
    system.memory.port = system.bus.mem_side_ports
    system.system_port = system.bus.cpu_side_ports
    system.generators = [PyTrafficGen(max_outstanding_reqs=8) for _ in range(2)]
    if args.mode == "writebacks":
        system.caches = [Cache(size="1KiB", assoc=1, tag_latency=1, data_latency=1,
                               response_latency=1, mshrs=4, tgts_per_mshr=8,
                               write_buffers=8) for _ in range(2)]
        for gen, cache in zip(system.generators, system.caches):
            gen.port = cache.cpu_side
            cache.mem_side = system.bus.cpu_side_ports
    else:
        for gen in system.generators:
            gen.port = system.bus.cpu_side_ports
    # Explicit construction order: functional port, gen 0, gen 1.
    system.bus.tdma_port_domains = [0, 0, 1]
    root = Root(full_system=False, system=system)
    m5.instantiate()
    for domain, gen in enumerate(system.generators):
        if args.mode == "quiet" and domain == 1:
            states = [gen.createIdle(2_000_000)]
        else:
            states = [gen.createLinear(2_000_000, domain * 65536, (domain + 1) * 65536,
                                       64, 2000, 2000, 0 if args.mode == "writebacks" else 100, 0)]
        gen.start(states + [gen.createExit(1)])
    event = m5.simulate(2_000_000)
    print(f"STRUCTURAL mode={args.mode} tick={m5.curTick()} cause={event.getCause()}")
    m5.stats.dump()


if __name__ in ("__main__", "__m5_main__"):
    main()
