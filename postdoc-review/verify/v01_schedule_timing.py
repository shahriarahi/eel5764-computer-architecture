"""V01 -- schedule arithmetic, measured margins, run-time and overlap offsets.

Read-only.  Constants come from leak_schedule.h through the experiment's own
parser (leak_params.py); measured numbers come from the stored run files.
"""
import json

from _common import A, EXP, load_run, np  # also puts EXP on sys.path

import leak_params  # noqa: E402  (the experiment's own header parser)

c = leak_params.constants()
W, T0 = c["W"], c["T0"]
prime_budget = c["OFF_ENC"] - c["OFF_PRIME"]
probe_budget = W - c["OFF_PROBE"]
print("== schedule (leak_schedule.h): T0 %d W %d OFF_PRIME %d OFF_ENC %d "
      "OFF_ENC_END %d OFF_PROBE %d" % (T0, W, c["OFF_PRIME"], c["OFF_ENC"],
                                       c["OFF_ENC_END"], c["OFF_PROBE"]))
print("   prime budget %d, encryption budget %d, gap %d, probe budget %d" % (
    prime_budget, c["OFF_ENC_END"] - c["OFF_ENC"],
    c["OFF_PROBE"] - c["OFF_ENC_END"], probe_budget))
assert prime_budget == 458752 and probe_budget == 454656

print("\n== measured probe-pass durations at A = 16 (from probes.bin timestamps)")
worst = {}
for name in ("p1-r1-scrub-n2000", "smoke-full-scrub-a16-n20",
             "smoke-full-noscrub-a16-n20", "smoke-tvla-a16-n20"):
    cfg = json.loads((EXP / "runs" / name / "leak_config.json").read_text())
    n = cfg["N_WIN"]
    rec = np.frombuffer((EXP / "runs" / name / "probes.bin").read_bytes(),
                        dtype=A.PROBE_DTYPE)
    ts = rec["timestamp"].astype(np.int64).reshape(n, 256)
    lat = rec["latency"].astype(np.int64).reshape(n, 256)
    dur = ts[:, -1] + lat[:, -1] - ts[:, 0]
    start = ts[:, 0] - (T0 + np.arange(n) * W)
    worst[name] = dur.max()
    print("   %-28s N=%-5d start offset %d..%d  duration min %d median %d max %d"
          "  headroom %.2fx" % (name, n, start.min(), start.max(), dur.min(),
                                np.median(dur), dur.max(),
                                probe_budget / dur.max()))

print("\n== worst-case bound for the full-AES probe pass at A = 16")
r = load_run(EXP / "runs" / "smoke-full-scrub-a16-n20")
sets = np.array(r["line_map"]["line_logical_set"])
slow = r["X"] >= 1000
non_table = np.ones(256, bool)
non_table[sets] = False
extra = slow[:, non_table].sum(1).max()
p1 = load_run(EXP / "runs" / "p1-r1-scrub-n2000")
t_lat = p1["X"][:, np.array(p1["line_map"]["line_logical_set"])][p1["touched"]]
fast, slow_mean, slow_max = 513, t_lat.mean(), t_lat.max()
k = 68 + int(extra)
overhead = np.median(
    (lambda rec: (rec["timestamp"].astype(np.int64).reshape(-1, 256)[:, -1]
                  + rec["latency"].astype(np.int64).reshape(-1, 256)[:, -1]
                  - rec["timestamp"].astype(np.int64).reshape(-1, 256)[:, 0])
     - rec["latency"].astype(np.int64).reshape(-1, 256).sum(1))(
        np.frombuffer((EXP / "runs" / "p1-r1-scrub-n2000" / "probes.bin")
                      .read_bytes(), dtype=A.PROBE_DTYPE)))
bound_mean = (256 - k) * fast + k * slow_mean + overhead
bound_max = (256 - k) * fast + k * slow_max + overhead
print("   all 68 table lines + %d non-table slow sets (the most seen in any of "
      "the 20 smoke windows) = %d slow sets" % (extra, k))
print("   loop overhead outside the timed walks: %d cycles per pass (P1 median)"
      % overhead)
print("   bound with the mean slow-walk time (%.0f): %.0f cycles = %.2fx inside "
      "the %d budget" % (slow_mean, bound_mean, probe_budget / bound_mean,
                         probe_budget))
print("   bound with the slowest walk ever seen (%d): %.0f cycles = %.2fx" % (
    slow_max, bound_max, probe_budget / bound_max))

print("\n== prime pass (progress.md, 'Measured margins'): between 334,464 and "
      "393,216 cycles at A = 16")
print("   headroom %.2fx to %.2fx of the %d budget; cold window 0 is the worst "
      "case" % (prime_budget / 393216, prime_budget / 334464, prime_budget))

print("\n== run time from the P1 measurement (10 min 59.5 s for N = 2000)")
cycles = T0 + (2000 + 2) * W
rate = cycles / 659.5
for n in (20, 200, 2000, 4000):
    sim = T0 + (n + 2) * W
    print("   N = %-5d %12d simulated cycles  -> %6.1f min at %.2f M cycles/s" % (
        n, sim, sim / rate / 60, rate / 1e6))

print("\n== overlap schedule (encrypt DURING the probe pass), offsets by -D only")
pass_a1, pass_a8 = 12574, 70906   # V05 output: stored paper runs, max pass duration
enc_est = 2678 + 80 * 33          # paper: 2,678 cycles/encryption; +<=80 L1D
                                  # misses served as LLC hits (~33 cycles each)
print("   monitor pass duration (V05, stored paper runs): A=1 max ~%d, A=8 max "
      "~%d cycles" % (pass_a1, pass_a8))
print("   encryption with scrub under partitioning, estimate: %d cycles "
      "[UNVERIFIED: no such run exists yet]" % enc_est)
for a, dur in ((1, pass_a1), (8, pass_a8)):
    off_probe = c["OFF_ENC"] - 4096
    end = off_probe + dur
    ok = (off_probe < W and c["OFF_PRIME"] + dur < c["OFF_ENC"] and end < W
          and off_probe > c["OFF_PRIME"] + dur)
    print("   A=%d: OFF_PROBE = OFF_ENC - 4096 = %d; pass ends at ~%d (< W: %s); "
          "prime ends at ~%d (< OFF_PROBE: %s); encryption %d..~%d lies inside "
          "the pass: %s" % (
              a, off_probe, end, end < W, c["OFF_PRIME"] + dur,
              c["OFF_PRIME"] + dur < off_probe, c["OFF_ENC"],
              c["OFF_ENC"] + enc_est, c["OFF_ENC"] + enc_est < end))
    assert ok
print("   A=16 unpartitioned is NOT usable for overlap: its pass takes 170,000 "
      "to 341,000 cycles and each victim fill changes later walk times (state "
      "and contention would be mixed).")
