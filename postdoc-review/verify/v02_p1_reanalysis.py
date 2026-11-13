"""V02 -- read-only re-analysis of the stored P1 run (2,000 windows).

Checks behind the review's answers to questions 2, 3 and 4:
  (a) the touched-vs-slow confusion table (is the channel an exact indicator?)
  (b) the raw effect in CPU cycles per predicted line (what the z hides)
  (c) how the registered z and the 16/16 gate behave when N shrinks
  (d) an exact permutation p-value on the raw-cycle statistic
  (e) reproduction of the stored analysis numbers (16/16, mean z 84.68)
"""
from _common import A, EXP, attribution, load_run, np, raw_effect

RUN = EXP / "runs" / "p1-r1-scrub-n2000"
r = load_run(RUN)
X, pt, ct, key, rk, lm = r["X"], r["pt"], r["ct"], r["key"], r["rk"], r["line_map"]
n = r["n"]
table_sets = np.array(lm["line_logical_set"])

print("== (e) reproduce the stored analysis")
full = attribution(X, pt, ct, key, rk[10], lm)
print("   bytes significant:", full["sig"])
print("   mean z p_xor_k = %.2f, p_only = %.2f, shuffled = %.2f" % (
    full["z"]["p_xor_k"].mean(), full["z"]["p_only"].mean(),
    full["z"]["shuffled"].mean()))
print("   decision:", {k: v for k, v in full["decision"].items()
                       if k.startswith(("round1", "lastround"))})

print("\n== (a) confusion table over the 68 table-line sets (slow = latency >= 1000)")
T = r["touched"]
L = X[:, table_sets]
slow = L >= 1000
tp, fn = int((slow & T).sum()), int((~slow & T).sum())
fp, tn = int((slow & ~T).sum()), int((~slow & ~T).sum())
print("   touched & slow %d | touched & fast %d | untouched & slow %d | "
      "untouched & fast %d" % (tp, fn, fp, tn))
print("   untouched latencies: distinct values %s" % np.unique(L[~T]).tolist())
print("   touched latencies: min %d median %d max %d" % (
    L[T].min(), np.median(L[T]), L[T].max()))
print("   => the indicator [set is slow] equals the indicator [line touched] in "
      "%d of %d cells" % (tp + tn, T.size))

print("\n== (b) raw effect in cycles per predicted line (unstandardized)")
for hyp in ("p_xor_k", "p_only", "shuffled"):
    vals = []
    rng = np.random.default_rng(1)
    for i in range(16):
        perm = rng.permutation(n)
        table, lines = A.predicted_lines(hyp, i, pt, ct, key, rk[10], perm)
        vals.append(raw_effect(X, lines, lm["tables"][table]["logical_sets"]))
    print("   %-9s mean %9.1f  min %9.1f  max %9.1f cycles" % (
        hyp, np.mean(vals), np.min(vals), np.max(vals)))

print("\n== (c) the registered z as a function of N (first N windows of P1)")
print("   N      mean z(p_xor_k)  z/sqrt(N)  p_xor_k sig  p_only sig  shuffled sig  raw effect byte0")
for m in (25, 50, 100, 250, 500, 1000, 2000):
    sub = attribution(X[:m], pt[:m], ct[:m], key, rk[10], lm)
    table, lines = A.predicted_lines("p_xor_k", 0, pt[:m], ct[:m], key, rk[10],
                                     np.arange(m))
    eff = raw_effect(X[:m], lines, lm["tables"][table]["logical_sets"])
    print("   %-6d %8.2f        %6.3f     %2d/16        %2d/16       %2d/16        %8.1f" % (
        m, sub["z"]["p_xor_k"].mean(), sub["z"]["p_xor_k"].mean() / np.sqrt(m),
        sub["sig"]["p_xor_k"], sub["sig"]["p_only"], sub["sig"]["shuffled"],
        eff))

print("\n== (d) permutation p-value of the raw-cycle statistic, byte 0, 10,000 "
      "window shuffles, seed 5764")
rng = np.random.default_rng(5764)
table, lines = A.predicted_lines("p_xor_k", 0, pt, ct, key, rk[10], np.arange(n))
sets = lm["tables"][table]["logical_sets"]
obs = raw_effect(X, lines, sets)
Xs = X[:, sets]
onehot = np.zeros((n, 16))
onehot[np.arange(n), lines] = 1.0
cnt = onehot.sum(0)


def stat(perm):
    s_in = (onehot[perm] * Xs).sum(0)
    tot = Xs.sum(0)
    return float(np.mean(s_in / cnt - (tot - s_in) / (n - cnt)))


assert abs(stat(np.arange(n)) - obs) < 1e-6
null = np.array([stat(rng.permutation(n)) for _ in range(10000)])
p = (1 + int((null >= obs).sum())) / 10001
print("   observed %.1f cycles; null mean %.2f sd %.2f max %.1f; "
      "empirical p = %.6f (the smallest value 10,000 shuffles can give)" % (
          obs, null.mean(), null.std(), null.max(), p))
