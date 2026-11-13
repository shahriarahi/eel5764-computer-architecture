"""V13 -- which leakage model would a CONTENTION channel carry, and can the
registered statistic see it?

A MODEL, not gem5.  It encodes only what the submitted paper measured about
the crossbar channel (Section VIII): a monitor walk is delayed by a few cycles
when a victim LLC request holds the shared request layer at that moment.  Under
way partitioning with the L1D scrub, the victim sends one LLC request for the
FIRST use of each table line in an encryption; later uses hit the L1D.  So

  * the NUMBER of victim requests = number of distinct table lines touched
    (a collision count, the quantity of Bonneau and Mironov, CHES 2006);
  * WHICH monitor set is delayed depends on WHEN the request is sent, i.e. on
    the lookup's position in the encryption, not on the table line's address.

Model: lookup number t (0..159) is issued at a fixed time, so it coincides with
the monitor walking set (t * STRIDE) mod 256.  If lookup t is a first use of
its line, the walk of that set is delayed by DELAY cycles with probability
P_HIT (the paper saw 9.4% of active walks delayed by 2, 4 or 6 cycles).

Checked: (1) the registered location-aware rule, (2) the location-free per-byte
ANOVA, (3) a collision-count statistic with a permutation p-value.
"""
from _common import A, attribution, np, synthetic_line_map

KEY = A.hex16(A.DEFAULT_KEY_HEX)
RK = A.key_expansion(KEY)
N, STRIDE, BASE = 2000, 1, 36.0
SEED = 0x5764A5E5


def first_use(pt_like_lookups):
    """(N,160) bool: lookup t is the first use of its Te line in the window.
    Round 10 (sbox) lookups are ignored for simplicity."""
    n = pt_like_lookups.shape[0]
    seen = np.zeros((n, 4, 16), dtype=bool)
    out = np.zeros((n, 160), dtype=bool)
    rows = np.arange(n)
    for r in range(9):
        for i in range(16):
            line = (pt_like_lookups[:, r, i] >> 4).astype(int)
            new = ~seen[rows, i % 4, line]
            out[:, 16 * r + i] = new
            seen[rows, i % 4, line] = True
    return out


def perm_p(x, y, rng, nperm=10000):
    x = (x - x.mean()) / x.std()
    y = (y - y.mean()) / y.std()
    obs = float((x * y).mean())
    null = np.array([(x[rng.permutation(len(x))] * y).mean()
                     for _ in range(nperm)])
    return obs, (1 + int((np.abs(null) >= abs(obs)).sum())) / (nperm + 1)


pt = A.plaintexts(SEED, N)
ct, lookups, _ = A.aes_encrypt_trace(pt, RK)
fu = first_use(lookups)                       # true (key-dependent) first uses
fake = lookups.copy()
fake[:, 0, :] = pt                            # key-free round 1: indices = p
fu_p = first_use(fake)

print("== victim LLC requests per encryption in the model (first uses of Te "
      "lines, rounds 1-9)")
print("   all rounds: mean %.2f sd %.2f min %d max %d;  round 1 only: mean %.2f "
      "sd %.2f" % (fu.sum(1).mean(), fu.sum(1).std(), fu.sum(1).min(),
                   fu.sum(1).max(), fu[:, :16].sum(1).mean(),
                   fu[:, :16].sum(1).std()))
c_pk = fu[:, :16].sum(1)
c_p = fu_p[:, :16].sum(1)
print("   round-1 distinct-line count: key-dependent vs key-free model "
      "correlation r = %.3f (they are separable)" % np.corrcoef(c_pk, c_p)[0, 1])

print("\n== synthetic contention arm: N = %d, delay lands on the set walked at "
      "the lookup's time" % N)
print("   P_HIT  DELAY | registered rule: p_xor_k sig, any statement supported | "
      "per-byte ANOVA bytes sig (first_round) | count models: r and "
      "permutation p (10,000 shuffles)")
for p_hit, delay in ((0.094, 4.0), (0.5, 4.0), (1.0, 4.0)):
    rng = np.random.default_rng(42)
    X = np.full((N, A.NSETS), BASE)
    hit = fu & (rng.random(fu.shape) < p_hit)
    for t in range(144):
        X[:, (t * STRIDE) % A.NSETS] += delay * hit[:, t]
    lm = synthetic_line_map(np.random.default_rng(5))
    res = attribution(X, pt, ct, KEY, RK[10], lm)
    d = res["decision"]
    supported = any(d[k] for k in ("round1_plaintext_plus_key",
                                   "round1_plaintext_only",
                                   "lastround_c_xor_k10",
                                   "lastround_ciphertext_only"))
    rows = [A.anova_p_min((pt[:, i] >> 4).astype(int), X, 16)[2]
            for i in range(16)]
    anova_sig = int((A.holm(np.array(rows)) < 0.05).sum())
    total = X.sum(1)
    r1win = X[:, :16].sum(1)                  # sets walked during round 1
    prng = np.random.default_rng(5764)
    r_full, p_full = perm_p(fu.sum(1).astype(float), total, prng)
    r_pk, p_pk = perm_p(c_pk.astype(float), r1win, prng)
    r_p, p_p = perm_p(c_p.astype(float), r1win, prng)
    r_sh, p_sh = perm_p(c_pk[prng.permutation(N)].astype(float), r1win, prng)
    print("   %-5s  %-5s | %2d/16, %-5s | %2d/16 | all-round count vs total "
          "latency r=%.3f p=%.4f; round-1 key-dependent count r=%.3f p=%.4f; "
          "round-1 key-free count r=%.3f p=%.4f; shuffled r=%.3f p=%.4f" % (
              p_hit, delay, res["sig"]["p_xor_k"], supported, anova_sig,
              r_full, p_full, r_pk, p_pk, r_p, p_p, r_sh, p_sh))
