"""V03 -- how the registered z / Holm rule behaves on noise-free data.

Synthetic arrays only (NOT gem5).  The line-touch model is the real AES with
the experiment's public key and plaintext stream; only the latencies are made
up.  Three questions:
  (a) Does z say anything about the size of an effect?  (magnitude blindness)
  (b) Does the rule fire on rare data-INDEPENDENT one-off delays?  (false
      positives when columns are almost constant)
  (c) Is z comparable between an arm with and an arm without background
      jitter, for the same data-dependent effect in cycles?
"""
from _common import A, attribution, np, raw_effect, synthetic_line_map

KEY = A.hex16(A.DEFAULT_KEY_HEX)
RK = A.key_expansion(KEY)
N = 2000


def model(seed, n=N, rounds1=True):
    pt = A.plaintexts(seed, n)
    ct, lookups, _ = A.aes_encrypt_trace(pt, RK)
    touched = A.touched_lines(lookups, rounds1, A.DEFAULT_LINE_OFFSETS)
    return pt, ct, touched


def run(X, pt, ct, lm):
    res = attribution(X, pt, ct, KEY, RK[10], lm)
    effs = []
    for i in range(16):
        table, lines = A.predicted_lines("p_xor_k", i, pt, ct, KEY, RK[10],
                                         np.arange(len(X)))
        effs.append(raw_effect(X, lines, lm["tables"][table]["logical_sets"]))
    return res, float(np.mean(effs))


print("== (a) magnitude blindness: X = 513 + delta * [line touched], no noise, "
      "N = %d, round-1 lookups" % N)
print("   delta (cycles)  visibility  raw effect/predicted line  mean z   "
      "p_xor_k sig  round1_plaintext_plus_key")
rng = np.random.default_rng(11)
lm = synthetic_line_map(rng)
pt, ct, touched = model(0x5764A5E5)
sets = np.array(lm["line_logical_set"])
for delta, vis in ((2642, 1.0), (10, 1.0), (1, 1.0), (1, 0.05), (1, 0.01)):
    X = np.full((N, A.NSETS), 513.0)
    visible = np.random.default_rng(3).random(touched.shape) < vis
    X[:, sets] += delta * (touched & visible)
    res, eff = run(X, pt, ct, lm)
    print("   %-15s %-10s %12.4f               %7.2f   %2d/16        %s" % (
        delta, vis, eff, res["z"]["p_xor_k"].mean(), res["sig"]["p_xor_k"],
        res["decision"]["round1_plaintext_plus_key"]))

print("\n== (b) data-independent rare delays: X = 257 everywhere, each cell gets "
      "+2 cycles with probability q; NO data dependence; 300 runs per q")
print("   q        runs where the rule supports any statement   runs with any "
      "hypothesis significant   (nominal: about 5%)")
for q in (0.0002, 0.002, 0.02, 0.2):
    fired = anysig = 0
    for rep in range(300):
        rng = np.random.default_rng(1000 + rep)
        lm_r = synthetic_line_map(rng)
        pt_r, ct_r, _ = model(0x1000 + rep)
        X = 257.0 + 2.0 * (rng.random((N, A.NSETS)) < q)
        res = attribution(X, pt_r, ct_r, KEY, RK[10], lm_r, seed=rep)
        d = res["decision"]
        fired += any(d[k] for k in ("round1_plaintext_plus_key",
                                    "round1_plaintext_only",
                                    "lastround_c_xor_k10",
                                    "lastround_ciphertext_only"))
        anysig += any(v > 0 for v in res["sig"].values())
    print("   %-8s %3d of 300 (%.1f%%)                              %3d of 300 (%.1f%%)" % (
        q, fired, fired / 3.0, anysig, anysig / 3.0))

print("\n== (c) same 1-cycle data-dependent effect, with and without "
      "data-independent background jitter")
print("   background                         raw effect  mean z   p_xor_k sig")
for label, q, amp in (("none (deterministic arm)", 0.0, 0.0),
                      ("+2 cycles in 5% of cells", 0.05, 2.0),
                      ("+6 cycles in 20% of cells", 0.20, 6.0)):
    rng = np.random.default_rng(77)
    X = np.full((N, A.NSETS), 513.0)
    X[:, sets] += 1.0 * touched
    X += amp * (rng.random(X.shape) < q)
    res, eff = run(X, pt, ct, lm)
    print("   %-34s %8.3f   %7.2f   %2d/16" % (
        label, eff, res["z"]["p_xor_k"].mean(), res["sig"]["p_xor_k"]))
