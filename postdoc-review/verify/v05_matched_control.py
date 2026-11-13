"""V05 -- can a matched-depth UNPARTITIONED control (monitor depth A < 16) show
cache-STATE leakage at all?

Read-only, from the frozen paper sweep (sweep-v3) and from this experiment's
P1 run.  The state channel needs a victim fill to evict a monitor line, i.e.
an LLC replacement.  If an unpartitioned LLC holding an A-line monitor never
replaces a block while AES runs, the registered P3 controls (A = 8 and A = 1,
--split off) cannot show state leakage, and the registered control-validity
gate marks every P3/P4 pair uninterpretable.

Also prints the monitor's probe-pass duration at A = 1 and A = 8, used for the
overlap-schedule arithmetic in V01.
"""
import re

from _common import A, EXP, RESULTS, np

SEEDS = ("5764a5e5", "5764a5e6", "5764a5e7")


def first_block(path):
    out = {}
    for line in path.read_text().splitlines():
        if line.startswith("---------- End"):
            break
        m = re.match(r"^(system\.llc\.\S+)\s+(\d+)\b", line)
        if m:
            out[m.group(1)] = int(m.group(2))
    return out


def row(label, stats):
    g = lambda k: stats.get("system.llc." + k, 0)
    print("   %-34s %10d %12d %12d %12d %12d" % (
        label, g("replacements"), g("demandMisses::cpu0.data"),
        g("demandAccesses::cpu0.data"), g("demandMisses::cpu1.data"),
        g("demandAccesses::cpu1.data")))


print("== LLC statistics of the measurement block (first stats dump)")
print("   %-34s %10s %12s %12s %12s %12s" % (
    "run", "replaced", "mon misses", "mon accesses", "AES misses",
    "AES accesses"))
for case in ("UNPARTITIONED-A1", "UNPARTITIONED-A4", "UNPARTITIONED-A8",
             "1-15", "8-8"):
    for s in SEEDS:
        p = RESULTS / "sweep-v3" / ("seed-" + s) / case / "stats.txt"
        if p.is_file():
            row("paper sweep-v3 %s %s" % (case, s[-2:]), first_block(p))
for name in ("p1-r1-scrub-n2000", "smoke-full-scrub-a16-n20",
             "smoke-full-noscrub-a16-n20"):
    row("this study %s" % name, first_block(EXP / "runs" / name / "stats.txt"))

print("\n== probe walks with an LLC miss in the stored controls "
      "(walk > 1st percentile + 100 cycles)")
print("   case               seed  walks   slow walks  slow after interval 0   "
      "per-walk latency p1/median/max   pass duration median/max (cycles)")
for case in ("UNPARTITIONED-A1", "UNPARTITIONED-A8", "1-15", "8-8"):
    for s in SEEDS:
        p = RESULTS / "sweep-v3" / ("seed-" + s) / case / "probes.bin"
        rec = np.frombuffer(p.read_bytes(), dtype=A.PROBE_DTYPE)
        lat = rec["latency"].astype(np.int64)
        p1 = np.percentile(lat, 1)
        slow = lat > p1 + 100
        ts = rec["timestamp"].astype(np.int64).reshape(-1, 256)
        dur = ts[:, -1] + lat.reshape(-1, 256)[:, -1] - ts[:, 0]
        print("   %-18s %s   %6d  %6d      %6d                  %5d / %5d / %6d"
              "             %7d / %7d" % (
                  case, s[-2:], lat.size, slow.sum(),
                  slow[256:].sum(), p1, np.median(lat), lat.max(),
                  np.median(dur), dur.max()))

print("\n== victim footprint (lines the AES workload can own in the LLC)")
print("   victim_leak_full_scrub: text 4696 B, data+bss 8528 B (riscv64-linux-gnu-"
      "size) = 5 pages; with a stack page or two that is at most about 7 pages,")
print("   so at most 2 victim lines per LLC set (256 sets = 4 pages per way). "
      "Monitor A=8: 8 + 2 < 16 ways, A=1: 1 + 2 < 16: no eviction is possible.")
