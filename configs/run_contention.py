"""gem5 configuration for the simulated monitor/AES contention experiment.

Core 0 runs the self-timed monitor; core 1 runs the public educational AES
workload. The cache hierarchy and requestor partition mapping match run.py.
The first validation uses --split off. Partitioned splits are accepted for a
later sweep only if that control passes its predeclared null test.
"""

import argparse
import json
import os
import re
import subprocess
import sys


CONFIG = {
    "isa": "RISCV",
    "cpu_type": "TimingSimpleCPU",
    "num_cores": 2,
    "cpu_clock": "2GHz",
    "sys_clock": "1GHz",
    "mem_size": "512MiB",
    "mem_type": "DDR3_1600_8x8",
    "cache_line": 64,
    "l1i": {"size": "16KiB", "assoc": 4, "tag_lat": 1, "data_lat": 1,
            "resp_lat": 1, "mshrs": 4, "tgts_per_mshr": 20},
    "l1d": {"size": "16KiB", "assoc": 4, "tag_lat": 1, "data_lat": 1,
            "resp_lat": 1, "mshrs": 8, "tgts_per_mshr": 20},
    "llc": {"size": "256KiB", "assoc": 16, "tag_lat": 10,
            "data_lat": 10, "resp_lat": 10, "mshrs": 32,
            "tgts_per_mshr": 12, "clusivity": "mostly_incl",
            "replacement": "LRURP"},
    "workloads": ["workloads/monitor", "workloads/victim"],
    # 2 GHz means one CPU cycle is 500 gem5 ticks (1 tick = 1 ps).
    "warmup_ticks": 1_000_000_000,
    "measure_ticks": 32_000_000_000,
    "logging_grace_ticks": 15_000_000_000,
    "contention": {
        "start_cycle": 2_000_000,
        "epoch_cycles": 1_000_000,
        "interval_count": 64,
        "llc_sets": 256,
        "activity_labels": [
            0, 1, 1, 0, 1, 0, 0, 1,
            1, 0, 1, 1, 0, 0, 1, 0,
            0, 0, 1, 1, 0, 1, 1, 0,
            1, 1, 0, 0, 1, 0, 0, 1,
            0, 1, 0, 1, 1, 0, 1, 0,
            1, 0, 0, 1, 0, 1, 1, 0,
            0, 1, 1, 0, 0, 1, 0, 1,
            1, 0, 1, 0, 1, 1, 0, 0,
        ],
    },
}

EXPERIMENT_PROFILES = {
    "16KiB": {
        "workloads": ["workloads/monitor", "workloads/victim"],
        "epoch_cycles": 1_000_000,
    },
    "4KiB": {
        "workloads": [
            "workloads/monitor_l1d4k",
            "workloads/victim_l1d4k",
        ],
        "epoch_cycles": 2_000_000,
    },
}

# Record-free monitor (2026-10-11): results leave through a probe file, so
# the monitor allocates no record lines in the LLC during measurement.
MONITOR_SINK_BINARIES = {"file": "workloads/monitor_v2_l1d4k"}
# v3 (2026-10-11): same as v2, but the measurement loop keeps the way count
# and probe-file fd in registers (no global-variable line in the LLC).
MONITOR_VARIANT_BINARIES = {"v3": "workloads/monitor_v3_l1d4k"}
PROBE_FILE_NAME = "probes.bin"

TICKS_PER_CPU_CYCLE = 500

LLC_ASSOC = CONFIG["llc"]["assoc"]
DEFAULT_WORKLOAD_SEED = 0x5764A5E5
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_split(text):
    """Return (monitor ways, AES ways), or None for the control."""
    normalized = text.strip().lower()
    if normalized in ("off", "unpartitioned"):
        return None
    match = re.fullmatch(r"(\d+)\s*[-/]\s*(\d+)", normalized)
    if not match:
        raise argparse.ArgumentTypeError(
            f"invalid split '{text}': expected A-B, A/B or off"
        )
    monitor_ways, aes_ways = (int(value) for value in match.groups())
    if monitor_ways < 1 or aes_ways < 1:
        raise argparse.ArgumentTypeError(
            f"invalid split '{text}': each partition needs at least 1 way"
        )
    if monitor_ways + aes_ways != LLC_ASSOC:
        raise argparse.ArgumentTypeError(
            f"invalid split '{text}': A + B must equal the LLC "
            f"associativity ({LLC_ASSOC}), got {monitor_ways + aes_ways}"
        )
    return monitor_ways, aes_ways


def parse_l1d_size(text):
    """Accept only the original or predeclared redesigned L1D capacity."""
    if text not in ("16KiB", "4KiB"):
        raise argparse.ArgumentTypeError(
            "invalid L1D size: expected 16KiB or 4KiB"
        )
    return text


def parse_monitor_ways(text):
    """Parse the number of monitor lines walked per LLC set."""
    try:
        ways = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "invalid monitor ways: expected an integer from 1 through 16"
        ) from exc
    if str(ways) != text.strip() or not 1 <= ways <= LLC_ASSOC:
        raise argparse.ArgumentTypeError(
            "invalid monitor ways: expected an integer from 1 through 16"
        )
    return ways


def parse_workload_seed(text):
    """Parse a positive unsigned 64-bit public plaintext seed."""
    try:
        seed = int(text, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "invalid workload seed: expected a positive unsigned 64-bit integer"
        ) from exc
    if not 1 <= seed <= 2**64 - 1:
        raise argparse.ArgumentTypeError(
            "invalid workload seed: expected a positive unsigned 64-bit integer"
        )
    return seed


def validate_monitor_ways(split, monitor_ways):
    """Require a partitioned monitor to fit exactly in its assigned ways."""
    if split is not None and monitor_ways != split[0]:
        raise ValueError(
            f"monitor ways ({monitor_ways}) must equal its LLC allocation "
            f"({split[0]})"
        )


# Mechanism study (2026-10-14, PREREGISTRATION_MECHANISM_20261014.md): opt-in
# knobs for the shared L1-to-LLC crossbar (system.l2bus) and per-interval
# statistics.  With none of them given, no SimObject parameter is touched and
# the run is identical to the v3 sweep.
L2BUS_WIDTHS = (16, 32, 64, 128, 256, 512)
L2BUS_HEADER_LATENCIES = (0, 1)
L2BUS_CLOCKS = ("system", "cpu")


def parse_l2bus_width(text):
    """Crossbar datapath width in bytes (gem5 L2XBar default: 32)."""
    try:
        width = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"invalid l2bus width: expected one of {L2BUS_WIDTHS}") from exc
    if str(width) != text.strip() or width not in L2BUS_WIDTHS:
        raise argparse.ArgumentTypeError(
            f"invalid l2bus width: expected one of {L2BUS_WIDTHS}")
    return width


def parse_l2bus_header_latency(text):
    """Crossbar header latency in crossbar cycles (gem5 default: 1)."""
    try:
        cycles = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "invalid l2bus header latency: expected 0 or 1") from exc
    if str(cycles) != text.strip() or cycles not in L2BUS_HEADER_LATENCIES:
        raise argparse.ArgumentTypeError(
            "invalid l2bus header latency: expected 0 or 1")
    return cycles


def mechanism_options(args):
    """Non-default mechanism settings as a dict ({} for an ordinary run)."""
    options = {}
    if args.l2bus_width is not None:
        options["l2bus_width"] = args.l2bus_width
    if args.l2bus_header_latency is not None:
        options["l2bus_header_latency"] = args.l2bus_header_latency
    if args.l2bus_clock != "system":
        options["l2bus_clock"] = args.l2bus_clock
    if args.stats_per_interval:
        options["stats_per_interval"] = True
    return options


def interval_ticks(config):
    """gem5 ticks per labelled interval; the measurement window must be whole intervals."""
    ticks = config["contention"]["epoch_cycles"] * TICKS_PER_CPU_CYCLE
    if ticks * config["contention"]["interval_count"] != config["measure_ticks"]:
        raise ValueError("measurement window is not a whole number of intervals")
    return ticks


def parse_nm_symbol(output, symbol):
    """Return an ELF symbol's address and size from `nm -S` output."""
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[3] == symbol:
            return int(fields[0], 16), int(fields[1], 16)
    raise ValueError(f"symbol {symbol!r} not found in nm output")


def apply_experiment_profile(config, l1d_size):
    """Apply a predeclared cache/timing profile to a configuration copy."""
    profile = EXPERIMENT_PROFILES[l1d_size]
    config["l1d"]["size"] = l1d_size
    config["workloads"] = list(profile["workloads"])
    config["contention"]["epoch_cycles"] = profile["epoch_cycles"]
    config["measure_ticks"] = (
        profile["epoch_cycles"]
        * config["contention"]["interval_count"]
        * TICKS_PER_CPU_CYCLE
    )


def main():
    import m5

    objects = m5.objects
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, type=parse_split,
                        help="LLC ways monitor-AES, e.g. 8-8, or 'off'")
    parser.add_argument("--l1d-size", type=parse_l1d_size,
                        default=CONFIG["l1d"]["size"],
                        help="private L1D capacity: 16KiB baseline or 4KiB redesign")
    parser.add_argument(
        "--monitor-ways", required=True, type=parse_monitor_ways,
        help="number of monitor lines primed and probed per LLC set",
    )
    parser.add_argument(
        "--workload-seed", type=parse_workload_seed,
        default=DEFAULT_WORKLOAD_SEED,
        help="public deterministic AES plaintext seed",
    )
    parser.add_argument(
        "--monitor-sink", choices=("memory", "file"), default="memory",
        help="memory: original record array; file: record-free probe file",
    )
    parser.add_argument(
        "--monitor-variant", choices=("v2", "v3"), default="v2",
        help="record-free monitor build (file sink only); v3 keeps hot state in registers",
    )
    parser.add_argument(
        "--l2bus-width", type=parse_l2bus_width, default=None,
        help="mechanism study: L1-to-LLC crossbar width in bytes (default: gem5's 32)",
    )
    parser.add_argument(
        "--l2bus-header-latency", type=parse_l2bus_header_latency, default=None,
        help="mechanism study: crossbar header latency in cycles (default: gem5's 1)",
    )
    parser.add_argument(
        "--l2bus-clock", choices=L2BUS_CLOCKS, default="system",
        help="mechanism study: crossbar clock domain (system 1 GHz, cpu 2 GHz)",
    )
    parser.add_argument(
        "--stats-per-interval", action="store_true",
        help="mechanism study: dump and reset statistics after every labelled interval",
    )
    args = parser.parse_args()
    mechanism = mechanism_options(args)
    if mechanism and not (args.monitor_sink == "file" and args.monitor_variant == "v3"):
        parser.error("mechanism options require --monitor-sink file --monitor-variant v3")
    apply_experiment_profile(CONFIG, args.l1d_size)
    if args.monitor_sink == "file":
        if args.l1d_size != "4KiB":
            parser.error("--monitor-sink file requires --l1d-size 4KiB")
        CONFIG["workloads"][0] = MONITOR_SINK_BINARIES["file"]
        if args.monitor_variant == "v3":
            CONFIG["workloads"][0] = MONITOR_VARIANT_BINARIES["v3"]
    elif args.monitor_variant != "v2":
        parser.error("--monitor-variant v3 requires --monitor-sink file")
    try:
        validate_monitor_ways(args.split, args.monitor_ways)
    except ValueError as exc:
        parser.error(str(exc))

    binaries = [os.path.join(PROJECT_ROOT, path) for path in CONFIG["workloads"]]
    for binary in binaries:
        if not os.path.isfile(binary):
            sys.exit(f"error: workload binary not found: {binary} "
                     "(run workloads/build.sh)")
    try:
        nm_output = subprocess.check_output(
            ["riscv64-linux-gnu-nm", "-S", "--defined-only", binaries[0]],
            text=True,
        )
        probe_vaddr, probe_bytes = parse_nm_symbol(nm_output, "probe_lines")
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        sys.exit(f"error: cannot locate monitor probe_lines symbol: {exc}")

    def make_cache(parameters, **extra):
        return objects.Cache(
            size=parameters["size"], assoc=parameters["assoc"],
            tag_latency=parameters["tag_lat"],
            data_latency=parameters["data_lat"],
            response_latency=parameters["resp_lat"],
            mshrs=parameters["mshrs"],
            tgts_per_mshr=parameters["tgts_per_mshr"], **extra,
        )

    system = objects.System()
    system.clk_domain = objects.SrcClockDomain(
        clock=CONFIG["sys_clock"], voltage_domain=objects.VoltageDomain())
    system.cpu_clk_domain = objects.SrcClockDomain(
        clock=CONFIG["cpu_clock"], voltage_domain=objects.VoltageDomain())
    system.mem_mode = "timing"
    system.mem_ranges = [objects.AddrRange(CONFIG["mem_size"])]
    system.cache_line_size = CONFIG["cache_line"]
    system.membus = objects.SystemXBar()
    system.l2bus = objects.L2XBar()
    if "l2bus_width" in mechanism:
        system.l2bus.width = mechanism["l2bus_width"]
    if "l2bus_header_latency" in mechanism:
        system.l2bus.header_latency = mechanism["l2bus_header_latency"]
    if mechanism.get("l2bus_clock") == "cpu":
        system.l2bus.clk_domain = system.cpu_clk_domain

    split = args.split
    if split is None:
        policies = []
    else:
        monitor_ways, _ = split
        policies = [objects.WayPartitioningPolicy(allocations=[
            objects.WayPolicyAllocation(
                partition_id=0, ways=list(range(0, monitor_ways))),
            objects.WayPolicyAllocation(
                partition_id=1, ways=list(range(monitor_ways, LLC_ASSOC))),
        ])]

    llc_parameters = CONFIG["llc"]
    system.llc = make_cache(
        llc_parameters,
        clusivity=llc_parameters["clusivity"],
        writeback_clean=False,
        replacement_policy=objects.LRURP(),
    )
    system.llc.partitioning_manager = objects.RequestorPartitionManager(
        partitioning_policies=policies,
        requestor_names=[
            f"cpu{core}.{port}"
            for core in range(CONFIG["num_cores"])
            for port in ("inst", "data")
        ],
        requestor_partitions=[
            core
            for core in range(CONFIG["num_cores"])
            for _ in ("inst", "data")
        ],
        num_partitions=CONFIG["num_cores"],
        tags_path=(
            f"system.llc.tags|cpu0.data|{probe_vaddr:#x}|"
            f"{probe_bytes:#x}|{CONFIG['contention']['llc_sets']}"
        ),
    )
    system.llc.cpu_side = system.l2bus.mem_side_ports
    system.llc.mem_side = system.membus.cpu_side_ports

    outdir = os.path.abspath(m5.options.outdir)
    probe_file = os.path.join(outdir, PROBE_FILE_NAME)

    system.workload = objects.SEWorkload.init_compatible(binaries[0])
    cpus = []
    for core, binary in enumerate(binaries):
        cpu = objects.TimingSimpleCPU(
            cpu_id=core, clk_domain=system.cpu_clk_domain)
        cpu.addPrivateSplitL1Caches(
            make_cache(CONFIG["l1i"]), make_cache(CONFIG["l1d"]))
        cpu.createInterruptController()
        cpu.connectAllPorts(system.l2bus.cpu_side_ports,
                            system.membus.cpu_side_ports,
                            system.membus.mem_side_ports)
        if core == 0:
            command = [binary, str(args.monitor_ways)]
            if args.monitor_sink == "file":
                command.append(probe_file)
        else:
            command = [binary, str(args.workload_seed)]
        cpu.workload = objects.Process(
            pid=100 + core, cmd=command, executable=binary, cwd=PROJECT_ROOT)
        cpu.createThreads()
        cpus.append(cpu)
    system.cpu = cpus

    system.mem_ctrl = objects.MemCtrl()
    system.mem_ctrl.dram = getattr(objects, CONFIG["mem_type"])(
        range=system.mem_ranges[0])
    system.mem_ctrl.port = system.membus.mem_side_ports
    system.system_port = system.membus.cpu_side_ports
    objects.Root(full_system=False, system=system)

    metadata = {
        "split": "off" if split is None else f"{split[0]}-{split[1]}",
        "monitor_ways": args.monitor_ways,
        "workload_seed": args.workload_seed,
        "probe_vaddr_base": probe_vaddr,
        "probe_vaddr_size": probe_bytes,
        "ways": None if split is None else {
            "partition0_monitor": list(range(0, split[0])),
            "partition1_aes": list(range(split[0], LLC_ASSOC)),
        },
        "command_line": sys.argv,
        "config": CONFIG,
        "contention": CONFIG["contention"],
    }
    if args.monitor_sink == "file":
        # Only record-free runs carry these keys, so the original
        # (memory-sink) runs keep their exact original metadata.
        metadata["monitor_sink"] = args.monitor_sink
        metadata["probe_file"] = PROBE_FILE_NAME
        if args.monitor_variant == "v3":
            metadata["monitor_variant"] = "v3"
    if mechanism:
        # Only mechanism-study runs carry this key.
        metadata["mechanism"] = mechanism

    m5.instantiate()
    limit_cause = "simulate() limit reached"

    warmup_event = m5.simulate(CONFIG["warmup_ticks"])
    metadata["warmup_exit"] = warmup_event.getCause()
    metadata["reset_tick"] = m5.curTick()
    if metadata["warmup_exit"] != limit_cause:
        sys.exit(f"error: warm-up ended early: {metadata['warmup_exit']}")

    m5.stats.reset()
    if mechanism.get("stats_per_interval"):
        # One measurement-only statistics block per labelled interval.
        step = interval_ticks(CONFIG)
        for _ in range(CONFIG["contention"]["interval_count"]):
            measurement_event = m5.simulate(step)
            if measurement_event.getCause() != limit_cause:
                break
            m5.stats.dump()
            m5.stats.reset()
        metadata["measurement_exit"] = measurement_event.getCause()
        metadata["measurement_end_tick"] = m5.curTick()
        if metadata["measurement_exit"] != limit_cause:
            sys.exit(
                f"error: measurement ended early: {metadata['measurement_exit']}")
    else:
        measurement_event = m5.simulate(CONFIG["measure_ticks"])
        metadata["measurement_exit"] = measurement_event.getCause()
        metadata["measurement_end_tick"] = m5.curTick()
        if metadata["measurement_exit"] != limit_cause:
            sys.exit(
                f"error: measurement ended early: {metadata['measurement_exit']}")
        m5.stats.dump()

    logging_event = m5.simulate(CONFIG["logging_grace_ticks"])
    metadata["logging_exit"] = logging_event.getCause()
    metadata["end_tick"] = m5.curTick()
    if metadata["logging_exit"] == limit_cause:
        sys.exit("error: workloads did not exit during logging grace period")

    with open(os.path.join(outdir, "run_meta.json"), "w") as metadata_file:
        json.dump(metadata, metadata_file, indent=2)
    print(
        f"OK contention split={metadata['split']} "
        f"measurement_end_tick={metadata['measurement_end_tick']}"
    )


if __name__ in ("__main__", "__m5_main__"):
    main()
