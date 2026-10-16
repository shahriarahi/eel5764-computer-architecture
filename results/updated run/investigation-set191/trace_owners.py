import re, sys, collections
pat = re.compile(r"^(\d+): system\.llc: access for (\S+) \[([0-9a-f]+):[0-9a-f]+\] (hit|miss).*?(?:set: 0x([0-9a-f]+) way: 0x([0-9a-f]+)|set: 0x([0-9a-f]+) way: (\d+))?$")
PROBE_LO, PROBE_HI = 0x2080, 0x2080 + 0x40000
lines = collections.defaultdict(lambda: collections.Counter())
cmds = collections.Counter(); way_of = {}
for raw in open(sys.argv[1]):
    m = re.match(r"^(\d+): system\.llc: access for (\S+) \[([0-9a-f]+):[0-9a-f]+\] (hit|miss)(.*)$", raw)
    if not m: continue
    tick, cmd, addr, hm, rest = m.groups(); a = int(addr, 16) & ~63
    w = re.search(r"set: 0x([0-9a-f]+) way: (0x[0-9a-f]+|\d+)", rest)
    pset = (a >> 6) & 255
    probe = PROBE_LO <= a < PROBE_HI
    if not probe:
        lines[a][(cmd, hm)] += 1
        if w: way_of[a] = int(w.group(2), 0)
print("non-probe lines seen in monitor ways 0..7 (8/8 partition):")
for a, c in sorted(lines.items()):
    if a in way_of and way_of[a] < 8:
        print(f"  addr=0x{a:x} phys_set={(a>>6)&255:3d} way={way_of[a]} accesses={dict(c)}")
