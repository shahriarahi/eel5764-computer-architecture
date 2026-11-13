"""V04 -- what a FULL encryption does to the round-1 and last-round contrasts.

(1) Pure AES arithmetic with the experiment's public key and seed S1: how many
    table lines one full encryption touches, and how much of the round-1
    contrast survives (a line that round 1 did not pick is usually touched by
    a later round anyway).
(2) Noise-free power of the registered rule for full AES: synthetic arrays
    X = 513 + 2642 * [line touched], the two numbers measured in P1.  Valid as
    a forecast of P2a only if every touched line stays visible in full-AES
    mode, which the 20-window smoke run supports and (3) re-checks.
(3) Read-only look at the stored 20-window full-AES smoke run.
"""
from _common import A, EXP, attribution, load_run, np, raw_effect, synthetic_line_map

KEY = A.hex16(A.DEFAULT_KEY_HEX)
RK = A.key_expansion(KEY)
OFF = A.DEFAULT_LINE_OFFSETS

print("== (1) line coverage of one full encryption (key f1e2..1f10, seed "
      "0x5764A5E5, 4000 windows)")
pt = A.plaintexts(0x5764A5E5, 4000)
ct, lookups, _ = A.aes_encrypt_trace(pt, RK)
t_full = A.touched_lines(lookups, False, OFF)
t_r1 = A.touched_lines(lookups, True, OFF)
te = slice(4, 68)
sb = slice(0, 4)
print("   Te lines touched per window (of 64): round 1 only mean %.2f; full AES "
      "mean %.2f sd %.2f min %d max %d" % (
          t_r1[:, te].sum(1).mean(), t_full[:, te].sum(1).mean(),
          t_full[:, te].sum(1).std(), t_full[:, te].sum(1).min(),
          t_full[:, te].sum(1).max()))
print("   sbox lines touched per window (of 4): full AES mean %.3f; all four "
      "touched in %.1f%% of windows" % (
          t_full[:, sb].sum(1).mean(), 100 * (t_full[:, sb].sum(1) == 4).mean()))
print("   analytic: P(Te line touched) = 1-(15/16)^40 = %.4f; P(sbox line "
      "touched) = 1-(3/4)^16 = %.4f" % (1 - (15 / 16) ** 40, 1 - 0.75 ** 16))
line0 = ((pt[:, 0] ^ KEY[0]) >> 4).astype(int)
in_r1 = np.zeros(4000)
out_r1 = np.zeros(4000)
cols = t_full[:, OFF["te0"]:OFF["te0"] + 16]
p_in = np.mean([cols[line0 == l, l].mean() for l in range(16)])
p_out = np.mean([cols[line0 != l, l].mean() for l in range(16)])
print("   byte 0, Te0: P(line slow | round-1 model predicts it) = %.4f; "
      "P(line slow | not predicted) = %.4f; contrast %.4f" % (
          p_in, p_out, p_in - p_out))
print("   => expected raw round-1 effect in full AES ~ %.0f cycles per predicted "
      "line (P1, round 1 only: 2177)" % (2642 * (p_in - p_out)))
lr = (A.INV_SBOX[ct[:, 0] ^ RK[10][0]] >> 6).astype(int)
cs = t_full[:, 0:4]
q_in = np.mean([cs[lr == l, l].mean() for l in range(4)])
q_out = np.mean([cs[lr != l, l].mean() for l in range(4)])
print("   last round byte 0, sbox: P(slow | predicted) = %.4f; P(slow | not "
      "predicted) = %.4f; contrast %.4f => ~ %.0f cycles" % (
          q_in, q_out, q_in - q_out, 2642 * (q_in - q_out)))

print("\n== (2) noise-free power of the registered rule, full AES, "
      "X = 513 + 2642*[touched]")
print("   N      seed  p_xor_k sig  p_only sig  lr_c_xor_k10 sig  c_only sig  "
      "shuffled/lr_shuffled  mean z r1  mean z last  r1 supported  last supported")
for n in (250, 500, 1000, 2000, 4000):
    for seed in (0x5764A5E5, 0x5764A5E6, 0x5764A5E7):
        rng = np.random.default_rng(seed % 9973)
        lm = synthetic_line_map(rng)
        p = A.plaintexts(seed, n)
        c, lk, _ = A.aes_encrypt_trace(p, RK)
        touched = A.touched_lines(lk, False, OFF)
        X = np.full((n, A.NSETS), 513.0)
        X[:, np.array(lm["line_logical_set"])] += 2642.0 * touched
        res = attribution(X, p, c, KEY, RK[10], lm)
        print("   %-6d %x  %2d/16        %2d/16       %2d/16             %2d/16       "
              "%d/%d                   %6.2f     %6.2f       %-5s         %s" % (
                  n, seed, res["sig"]["p_xor_k"], res["sig"]["p_only"],
                  res["sig"]["lr_c_xor_k10"], res["sig"]["c_only"],
                  res["sig"]["shuffled"], res["sig"]["lr_shuffled"],
                  res["z"]["p_xor_k"].mean(), res["z"]["lr_c_xor_k10"].mean(),
                  res["decision"]["round1_plaintext_plus_key"],
                  res["decision"]["lastround_c_xor_k10"]))

print("\n== (3) stored 20-window full-AES smoke run (real gem5 data, read-only)")
r = load_run(EXP / "runs" / "smoke-full-scrub-a16-n20")
sets = np.array(r["line_map"]["line_logical_set"])
L = r["X"][:, sets]
slow = L >= 1000
T = r["touched"]
print("   table-line cells: touched & slow %d, touched & fast %d, untouched & "
      "slow %d, untouched & fast %d" % (
          (slow & T).sum(), (~slow & T).sum(), (slow & ~T).sum(),
          (~slow & ~T).sum()))
print("   untouched latencies: %s" % np.unique(L[~T]).tolist())
allslow = (r["X"] >= 1000).sum(1)
print("   slow sets per window (all 256 sets): min %d median %d max %d; "
      "table lines touched per window: min %d max %d" % (
          allslow.min(), np.median(allslow), allslow.max(),
          T.sum(1).min(), T.sum(1).max()))
