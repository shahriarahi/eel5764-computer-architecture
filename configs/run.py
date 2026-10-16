# gem5 configuration for the EEL5764 LLC way-partitioning study.
#
#   gem5.opt -d <outdir> configs/run.py --split {A-B | A/B | off}
#
# Two TimingSimpleCPUs (RISC-V, SE mode), private L1I/L1D per core, one
# shared 16-way LLC. Core 0 -> partition 0 (A ways), core 1 -> partition 1
# (B ways), A + B = 16. "off" is the unpartitioned control.
#
# ---------------------------------------------------------------------------
# How partition IDs reach the LLC
#   Stock gem5 v25.1 only tags packets with a partition ID via Arm MPAM
#   (src/dev/arm/mpam.cc); the base PartitionManager returns 0. The LLC
#   therefore uses RequestorPartitionManager (../gem5_ext), which maps the
#   requestors "cpuN.inst"/"cpuN.data" to partition N. L1 writebacks carry
#   the shared wbRequestorId, so they take the partition recorded for their
#   block address when a core's request for it was last seen at the LLC.
#
# How disjoint ways are enforced
#   gem5's unmodified WayPartitioningPolicy filters the replacement
#   candidates in BaseSetAssoc::findVictim to the ways allocated to the
#   requesting partition: partition 0 = ways [0, A), partition 1 = [A, 16).
#   A partition can therefore only allocate (and evict) within its own ways.
#   Lookups are NOT filtered: a hit may be served from any way. In SE mode
#   the two processes share no physical memory, so no line is in both.
#   In "off" mode the manager is attached with no policies: partition IDs
#   are still recorded (for occupancy stats) but nothing is restricted.
#
# Inclusion policy actually configured
#   LLC clusivity = "mostly_incl" (gem5 default): blocks are allocated in
#   the LLC on L1 miss fills, but gem5's classic caches do not back-
#   invalidate L1 copies when the LLC evicts, so inclusion is not enforced.
#   writeback_clean = False at both levels (only dirty L1 victims are
#   written back; clean L1 evictions send CleanEvict, which never allocates).
#
# Shared structures NOT isolated by LLC way partitioning
#   - LLC tag lookup port/latency, MSHRs, write buffers: shared by both cores
#     (a miss from one core can occupy MSHRs the other needs).
#   - L2XBar between L1s and LLC, and the memory bus: shared, arbitrated.
#   - Coherence: snoop traffic on the coherent L2XBar is shared (there is no
#     directory in this classic-cache model).
#   - Memory controller queues and DRAM banks/row buffers: shared.
#   - Replacement state: each block's replacement data is per-block, but
#     hits are unfiltered and inclusion is not enforced (see above).
#   Way partitioning isolates LLC data-way *capacity* only.
# ---------------------------------------------------------------------------

import argparse
import json
import os
import re
import sys

import m5
from m5.objects import *

# All experiment tunables in one place.
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
    "llc": {"size": "256KiB", "assoc": 16, "tag_lat": 10, "data_lat": 10,
            "resp_lat": 10, "mshrs": 32, "tgts_per_mshr": 12,
            "clusivity": "mostly_incl", "replacement": "LRURP"},
    # Core i runs workloads[i] and is assigned to partition i.
    "workloads": ["workloads/randacc", "workloads/stream"],
    "warmup_ticks": 1_000_000_000,   # 1 ms simulated (1 tick = 1 ps)
    "measure_ticks": 4_000_000_000,  # 4 ms simulated
    # The measurement window is split into this many equal segments with a
    # stats dump after each. Stats are cumulative since the post-warm-up
    # reset, so the LAST dump covers the whole window; the earlier dumps
    # exist so way occupancy can be checked at several instants.
    "measure_segments": 8,
}

LLC_ASSOC = CONFIG["llc"]["assoc"]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_split(text):
    """Return (ways_core0, ways_core1), or None for the 'off' control."""
    t = text.strip().lower()
    if t in ("off", "unpartitioned"):
        return None
    m = re.fullmatch(r"(\d+)\s*[-/]\s*(\d+)", t)
    if not m:
        raise argparse.ArgumentTypeError(
            f"invalid split '{text}': expected A-B, A/B or off"
        )
    a, b = int(m.group(1)), int(m.group(2))
    if a < 1 or b < 1:
        raise argparse.ArgumentTypeError(
            f"invalid split '{text}': each partition needs at least 1 way"
        )
    if a + b != LLC_ASSOC:
        raise argparse.ArgumentTypeError(
            f"invalid split '{text}': A + B must equal the LLC "
            f"associativity ({LLC_ASSOC}), got {a + b}"
        )
    return a, b


def positive_ticks(text):
    v = int(text)
    if v <= 0:
        raise argparse.ArgumentTypeError("tick counts must be positive")
    return v


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--split", required=True, type=parse_split,
                    help="LLC ways core0-core1, e.g. 8-8, or 'off'")
parser.add_argument("--warmup-ticks", type=positive_ticks,
                    default=CONFIG["warmup_ticks"])
parser.add_argument("--measure-ticks", type=positive_ticks,
                    default=CONFIG["measure_ticks"])
parser.add_argument("--workloads", default=None,
                    help="Override CONFIG['workloads'] as PATH0,PATH1 "
                         "(relative to the project root)")
args = parser.parse_args()
CONFIG["warmup_ticks"] = args.warmup_ticks
CONFIG["measure_ticks"] = args.measure_ticks
if args.workloads is not None:
    paths = [p.strip() for p in args.workloads.split(",")]
    if len(paths) != CONFIG["num_cores"] or not all(paths):
        parser.error(f"--workloads needs exactly {CONFIG['num_cores']} "
                     "comma-separated paths")
    CONFIG["workloads"] = paths

binaries = [os.path.join(PROJECT_ROOT, w) for w in CONFIG["workloads"]]
for b in binaries:
    if not os.path.isfile(b):
        sys.exit(f"error: workload binary not found: {b} "
                 "(run workloads/build.sh)")


def make_cache(p, **extra):
    return Cache(
        size=p["size"], assoc=p["assoc"],
        tag_latency=p["tag_lat"], data_latency=p["data_lat"],
        response_latency=p["resp_lat"],
        mshrs=p["mshrs"], tgts_per_mshr=p["tgts_per_mshr"], **extra,
    )


# ---- System -----------------------------------------------------------------
system = System()
system.clk_domain = SrcClockDomain(clock=CONFIG["sys_clock"],
                                   voltage_domain=VoltageDomain())
system.cpu_clk_domain = SrcClockDomain(clock=CONFIG["cpu_clock"],
                                       voltage_domain=VoltageDomain())
system.mem_mode = "timing"
system.mem_ranges = [AddrRange(CONFIG["mem_size"])]
system.cache_line_size = CONFIG["cache_line"]

system.membus = SystemXBar()
system.l2bus = L2XBar()

# ---- Shared LLC + partitioning ------------------------------------------------
split = args.split
if split is None:
    policies = []
else:
    a, _ = split
    policies = [WayPartitioningPolicy(allocations=[
        WayPolicyAllocation(partition_id=0, ways=list(range(0, a))),
        WayPolicyAllocation(partition_id=1, ways=list(range(a, LLC_ASSOC))),
    ])]

llc_p = CONFIG["llc"]
system.llc = make_cache(
    llc_p,
    clusivity=llc_p["clusivity"],
    writeback_clean=False,
    replacement_policy=LRURP(),
)
system.llc.partitioning_manager = RequestorPartitionManager(
    partitioning_policies=policies,
    requestor_names=[f"cpu{i}.{p}" for i in range(CONFIG["num_cores"])
                     for p in ("inst", "data")],
    requestor_partitions=[i for i in range(CONFIG["num_cores"])
                          for _ in ("inst", "data")],
    num_partitions=CONFIG["num_cores"],
    tags_path="system.llc.tags",
)
system.llc.cpu_side = system.l2bus.mem_side_ports
system.llc.mem_side = system.membus.cpu_side_ports

# ---- Cores with private L1s -------------------------------------------------
system.workload = SEWorkload.init_compatible(binaries[0])
cpus = []
for i, binary in enumerate(binaries):
    cpu = TimingSimpleCPU(cpu_id=i, clk_domain=system.cpu_clk_domain)
    cpu.addPrivateSplitL1Caches(make_cache(CONFIG["l1i"]),
                                make_cache(CONFIG["l1d"]))
    cpu.createInterruptController()
    # L1s and the (unused in SE) page-walker ports go to the shared L2 bus.
    cpu.connectAllPorts(system.l2bus.cpu_side_ports,
                        system.membus.cpu_side_ports,
                        system.membus.mem_side_ports)
    # Separate process per core: distinct PID and address space.
    cpu.workload = Process(pid=100 + i, cmd=[binary],
                           executable=binary, cwd=PROJECT_ROOT)
    cpu.createThreads()
    cpus.append(cpu)
system.cpu = cpus

system.mem_ctrl = MemCtrl()
system.mem_ctrl.dram = getattr(m5.objects, CONFIG["mem_type"])(
    range=system.mem_ranges[0])
system.mem_ctrl.port = system.membus.mem_side_ports
system.system_port = system.membus.cpu_side_ports

root = Root(full_system=False, system=system)

# ---- Record exactly what was run -------------------------------------------
outdir = m5.options.outdir
meta = {
    "split": ("off" if split is None else f"{split[0]}-{split[1]}"),
    "ways": (None if split is None else {
        "partition0_core0": list(range(0, split[0])),
        "partition1_core1": list(range(split[0], LLC_ASSOC))}),
    "command_line": sys.argv,
    "config": CONFIG,
}

m5.instantiate()

# Warm-up, reset stats, then measure a fixed window with both cores running,
# dumping (cumulative) stats after each of the equal measurement segments.
nseg = CONFIG["measure_segments"]
if CONFIG["measure_ticks"] % nseg:
    sys.exit(f"error: measure_ticks must be divisible by {nseg} segments")
ev = m5.simulate(CONFIG["warmup_ticks"])
meta["warmup_exit"] = ev.getCause()
meta["reset_tick"] = m5.curTick()
m5.stats.reset()
meta["segment_exits"] = []
meta["dump_ticks"] = []
for _ in range(nseg):
    ev = m5.simulate(CONFIG["measure_ticks"] // nseg)
    meta["segment_exits"].append(ev.getCause())
    meta["dump_ticks"].append(m5.curTick())
    m5.stats.dump()
meta["end_tick"] = m5.curTick()

with open(os.path.join(outdir, "run_meta.json"), "w") as f:
    json.dump(meta, f, indent=2)

LIMIT = "simulate() limit reached"
exits = [meta["warmup_exit"]] + meta["segment_exits"]
if any(e != LIMIT for e in exits):
    sys.exit(f"error: simulation ended early ({exits!r}); "
             "both workloads must run for the whole window")
print(f"OK split={meta['split']} end_tick={meta['end_tick']}")
