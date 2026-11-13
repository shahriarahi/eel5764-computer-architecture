"""Ad hoc detail pull for runs/p1-r1-scrub-n2000 (NOT covered by tests).

Reads the run directory and its .analysis.json (written by aes_leak_analysis.py
analyze) and prints: probe-pass deadline margins over all windows, the real
effect size of a touched table-line set, per-byte strength, trace agreement and
the calibration of the analytic z.  Run from the worktree root:

    python3 -B experiments/aes-leakage/runs/p1_detail.py
"""
import json
import sys

import numpy as np

sys.path.insert(0, "experiments/aes-leakage/analysis")
import aes_leak_analysis as a  # noqa: E402

run = "experiments/aes-leakage/runs/p1-r1-scrub-n2000"
res = json.load(open(run + ".analysis.json"))
cfg = json.load(open(run + "/leak_config.json"))
N, W, T0 = cfg["N_WIN"], cfg["W"], cfg["T0"]
d = np.fromfile(run + "/probes.bin", dtype=a.PROBE_DTYPE)
ts = d["timestamp"].astype(np.int64)
lat = d["latency"].astype(np.int64)
X = lat.reshape(N, 256).astype(float)

print("== (1) real deadline margins over %d windows (spec: probe budget %d)"
      % (N, W - cfg["OFF_PROBE"]))
base = T0 + np.arange(N) * W
starts = ts.reshape(N, 256)[:, 0] - base
ends = (ts + lat).reshape(N, 256)[:, -1] - base
dur = ends - starts
print("   probe pass starts at offset: min %d max %d (OFF_PROBE = %d)"
      % (starts.min(), starts.max(), cfg["OFF_PROBE"]))
print("   probe pass duration: min %d  median %d  p99 %d  max %d   => worst-case "
      "headroom %.2fx" % (dur.min(), np.median(dur), np.percentile(dur, 99),
                          dur.max(), (W - cfg["OFF_PROBE"]) / dur.max()))
print("   probe pass ends at offset <= %d of %d" % (ends.max(), W))
print("   drift: median duration first 200 windows %d, last 200 windows %d"
      % (np.median(dur[:200]), np.median(dur[-200:])))
print("   window 0 vs rest: duration %d vs median %d" % (dur[0], np.median(dur[1:])))

print("\n== (2) real effect size per table-line set (oracle = lines the "
      "encryption touches)")
key = a.hex16(cfg["key_hex"])
rk = a.key_expansion(key)
pt = a.plaintexts(cfg["workload_seed"], N)
ct, lookups, _ = a.aes_encrypt_trace(pt, rk)
off = {t: cfg["tables"][t]["line_offset"] for t in a.TABLES}
touched = a.touched_lines(lookups, bool(cfg["rounds1"]), off)
logical = res["line_map"]["line_logical_set"]
touched_lat, untouched_lat = [], []
for line in range(68):
    mask = touched[:, line]
    if mask.any():
        touched_lat.append(X[mask, logical[line]])
    if (~mask).any():
        untouched_lat.append(X[~mask, logical[line]])
lt, lu = np.concatenate(touched_lat), np.concatenate(untouched_lat)
print("   latency of a table-line set when TOUCHED  : median %.0f  mean %.0f  "
      "(n=%d)" % (np.median(lt), lt.mean(), lt.size))
print("   latency of a table-line set when UNTOUCHED: median %.0f  mean %.0f  "
      "sd %.1f (n=%d)" % (np.median(lu), lu.mean(), lu.std(), lu.size))
effect = lt.mean() - lu.mean()
if lu.std() == 0:
    print("   effect (mean touched - mean untouched): %.0f cycles; the untouched "
          "noise sd is exactly 0 (a noise-free baseline)" % effect)
else:
    print("   effect (mean touched - mean untouched): %.0f cycles = %.0f sd of "
          "the untouched noise" % (effect, effect / lu.std()))
print("   'visibility': %.1f%% of touched windows show a slow set (>= 1000 "
      "cycles); %.2f%% of untouched do"
      % (100 * (lt >= 1000).mean(), 100 * (lu >= 1000).mean()))
others = np.setdiff1d(np.arange(256), np.array(logical))
print("   sets that are not table lines: median latency %.0f, slow (>=1000) in "
      "%.2f%% of cells" % (np.median(X[:, others]),
                            100 * (X[:, others] >= 1000).mean()))
always_slow = int(((X[:, others] >= 1000).mean(axis=0) > 0.99).sum())
print("   of those, %d set(s) are slow in more than 99%% of windows (constant "
      "victim data such as the stack)" % always_slow)

print("\n== (3) per-byte strength (round-1 p_xor_k z, one-sided)")
z = np.array(res["attribution"]["p_xor_k"]["z_per_byte"])
print("   z per byte:", np.round(z, 1).tolist())
print("   weakest byte z = %.1f (byte %d), strongest %.1f (byte %d)"
      % (z.min(), z.argmin(), z.max(), z.argmax()))
zp = np.array(res["attribution"]["p_only"]["z_per_byte"])
print("   p_only z per byte: min %.1f max %.1f (negative = anti-correlated; "
      "expected, because the true line differs from p>>4 for every byte)"
      % (zp.min(), zp.max()))
hp = np.array(res["attribution"]["p_xor_k"]["holm_p_per_byte"])
print("   Holm p of p_xor_k per byte: max %.3g (values of 0 are below double "
      "precision)" % hp.max())

print("\n== (4) trace")
gt = res["ground_truth"]
print("   touched lines total %d; fills in AES phase %d; recall %.3f precision "
      "%.3f; outside AES phase %d"
      % (gt["touched_total"], gt["fills_in_aes_phase"], gt["recall"],
         gt["precision"], gt["fills_outside_aes_phase"]))

print("\n== (5) calibration of the analytic z on real data (windows shuffled)")
c = res["null_calibration"]
print("   %.3f of %d shuffled z > 2.33 (nominal 0.010); sd of shuffled z = %.2f "
      "(nominal 1)" % (c["frac_z_gt_2.33"], c["n"], c["z_sd"]))
