#!/usr/bin/env python3
"""
aes_leak_analysis.py -- Which AES data does the LLC Prime+Probe monitor see?

Works on per-encryption probe vectors from gem5 (one window = prime -> 1 AES
encryption -> probe). Because key and plaintexts are public and deterministic,
we regenerate every plaintext/ciphertext offline and test leakage MODELS:

  fr_pxk   first round:  table line = (p_i XOR k_i) >> 4      (key-dependent)
  p_only   plaintext only:            p_i >> 4                (no key)
  lr_cxk   last round:   table line = InvS[c_i XOR k10_i] >> 4 (key-dependent)
  c_only   ciphertext only:           c_i >> 4
  shuffled control: fr_pxk labels randomly permuted          (must be null)

Subcommands
  selftest   AES/PRNG known-answer tests + synthetic end-to-end check
  synth      write a synthetic probes file (to rehearse the pipeline)
  analyze    per-set SNR, permutation p-values (Holm), key-guess ranking
  tvla       fixed-vs-random Welch t-test (interleaved windows)
  oracle     write the true table lines touched per window (for gem5 trace check)

Probe file format (default): raw little-endian uint32, NSETS values per window,
windows in order. Value = probe-walk latency (cycles) of that LLC set.
A .npy file of shape (N, NSETS) also works.

Only numpy is required; matplotlib is optional (--plot).
"""
import argparse
import json
import sys

import numpy as np

# ----------------------------------------------------------------------------
# AES-128 (reference implementation, generated S-box to avoid table typos)
# ----------------------------------------------------------------------------

def _gen_sbox():
    def gmul(a, b):
        r = 0
        while b:
            if b & 1:
                r ^= a
            a = ((a << 1) ^ 0x11B) if (a & 0x80) else (a << 1)
            b >>= 1
        return r & 0xFF
    inv = [0] * 256
    for x in range(1, 256):
        for y in range(1, 256):
            if gmul(x, y) == 1:
                inv[x] = y
                break
    sbox = []
    for x in range(256):
        b = inv[x]
        s = b
        for k in range(1, 5):
            s ^= ((b << k) | (b >> (8 - k))) & 0xFF
        sbox.append(s ^ 0x63)
    return np.array(sbox, dtype=np.uint8)

SBOX = _gen_sbox()
INV_SBOX = np.zeros(256, dtype=np.uint8)
INV_SBOX[SBOX] = np.arange(256, dtype=np.uint8)
RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36]


def key_expansion(key16):
    """Return 11 round keys, shape (11, 16) uint8, FIPS-197 byte order."""
    w = [list(key16[4 * i:4 * i + 4]) for i in range(4)]
    for i in range(4, 44):
        t = list(w[i - 1])
        if i % 4 == 0:
            t = t[1:] + t[:1]
            t = [int(SBOX[b]) for b in t]
            t[0] ^= RCON[i // 4 - 1]
        w.append([w[i - 4][j] ^ t[j] for j in range(4)])
    return np.array(w, dtype=np.uint8).reshape(11, 16)


def _xtime(a):
    a = a.astype(np.uint16)
    return (((a << 1) ^ np.where(a & 0x80, 0x1B, 0)) & 0xFF).astype(np.uint8)


# ShiftRows: new[r + 4c] = old[r + 4((c + r) % 4)]
SHIFT_IDX = np.array([(i % 4) + 4 * (((i // 4) + (i % 4)) % 4) for i in range(16)])


def aes_encrypt_trace(pt, rk, last_round_tables="te4"):
    """
    Vectorised AES-128 over N blocks (pt: (N,16) uint8).
    Returns ciphertexts (N,16) and the T-table lookup trace:
      lookups: (N, 10, 16) uint8 = state byte used as table index, per round
      tables : (10, 16) int    = which table each lookup goes to
    T-table convention (OpenSSL / Daemen-Rijmen): in rounds 1..9 the byte in
    row r (= i % 4) indexes Te_r. The last round depends on the implementation:
      'te4'     -> separate 5th table (index 4)          [many educational codes]
      'openssl' -> rows 0..3 use Te2, Te3, Te0, Te1 (masked)
    CHECK which one your victim uses.
    """
    n = pt.shape[0]
    s = pt ^ rk[0]
    lookups = np.zeros((n, 10, 16), dtype=np.uint8)
    for r in range(1, 11):
        lookups[:, r - 1, :] = s            # index bytes before SubBytes
        s = SBOX[s]
        s = s[:, SHIFT_IDX]
        if r != 10:
            out = np.empty_like(s)
            for c in range(4):
                a0, a1, a2, a3 = (s[:, 4 * c + k] for k in range(4))
                t = a0 ^ a1 ^ a2 ^ a3
                out[:, 4 * c + 0] = a0 ^ t ^ _xtime(a0 ^ a1)
                out[:, 4 * c + 1] = a1 ^ t ^ _xtime(a1 ^ a2)
                out[:, 4 * c + 2] = a2 ^ t ^ _xtime(a2 ^ a3)
                out[:, 4 * c + 3] = a3 ^ t ^ _xtime(a3 ^ a0)
            s = out
        s = s ^ rk[r]
    tables = np.tile(np.arange(16) % 4, (10, 1))
    if last_round_tables == "te4":
        tables[9, :] = 4
    elif last_round_tables == "openssl":
        tables[9, :] = np.array([2, 3, 0, 1])[np.arange(16) % 4]
    else:
        raise ValueError(last_round_tables)
    return s, lookups, tables


# ----------------------------------------------------------------------------
# Deterministic plaintext stream -- MUST match splitmix64 in victim.c
# ----------------------------------------------------------------------------
MASK64 = (1 << 64) - 1


def splitmix64_stream(seed):
    x = seed & MASK64
    while True:
        x = (x + 0x9E3779B97F4A7C15) & MASK64
        z = x
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        yield z ^ (z >> 31)


def plaintexts(seed, n, tvla_fixed=None):
    """Window j draws two 64-bit words -> 16 bytes (little-endian).
    In TVLA mode, even windows use the fixed plaintext instead (the words are
    still drawn, so the random stream stays aligned with victim.c)."""
    g = splitmix64_stream(seed)
    out = np.zeros((n, 16), dtype=np.uint8)
    for j in range(n):
        lo, hi = next(g), next(g)
        out[j] = np.frombuffer((lo | (hi << 64)).to_bytes(16, "little"), dtype=np.uint8)
    if tvla_fixed is not None:
        out[0::2] = tvla_fixed
    return out


def hex16(s):
    b = bytes.fromhex(s.replace(" ", ""))
    if len(b) != 16:
        raise argparse.ArgumentTypeError("need 16 bytes of hex")
    return np.frombuffer(b, dtype=np.uint8).copy()


# ----------------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------------

def class_stats(labels, X, nclass):
    """Per-class count, mean, var of every column of X. labels: (N,) ints."""
    onehot = np.zeros((X.shape[0], nclass))
    onehot[np.arange(X.shape[0]), labels] = 1.0
    cnt = onehot.sum(0)
    s1 = onehot.T @ X
    s2 = onehot.T @ (X * X)
    return cnt, s1, s2


def snr_from_stats(cnt, s1, s2, min_count=2):
    ok = cnt >= min_count
    c, a, b = cnt[ok, None], s1[ok], s2[ok]
    mean = a / c
    var = b / c - mean ** 2
    noise = var.mean(0)
    noise[noise <= 0] = np.nan
    return mean.var(0) / noise          # Mangard SNR, one value per set


def snr(labels, X, nclass=16):
    return snr_from_stats(*class_stats(labels, X, nclass))


def holm(pvals):
    p = np.asarray(pvals, float)
    order = np.argsort(p)
    adj = np.empty_like(p)
    running = 0.0
    m = len(p)
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj


def welch_t(a, b):
    ma, mb = a.mean(0), b.mean(0)
    va, vb = a.var(0, ddof=1), b.var(0, ddof=1)
    return (ma - mb) / np.sqrt(va / len(a) + vb / len(b) + 1e-30)


# ----------------------------------------------------------------------------
# Leakage models
#
# Two different questions, two different tests:
#
# (A) DETECTION, location-free: does the partition of windows by some byte
#     value explain probe latency in ANY set? (Mangard SNR, max over sets.)
#     Caveat: XOR with a constant only RELABELS classes, so (p^k)>>4 and p>>4
#     give the SAME SNR. Detection cannot tell "plaintext" from "p XOR key".
#
# (B) ATTRIBUTION, location-aware: with the table->LLC-set map, a hypothesis
#     predicts WHICH set lights up in each window. Key guesses now differ, so
#     the true key nibble / byte must rank first, and "plaintext only"
#     (guess 0) can be rejected -- unless the key nibble really is 0.
# ----------------------------------------------------------------------------

def detection_labels(pt, ct, rk, rng):
    fr = pt >> 4                       # identical partition to (p ^ k) >> 4
    return {
        "first_round": fr,
        "last_round": INV_SBOX[ct ^ rk[10]] >> 4,
        "c_nibble": ct >> 4,
        "shuffled": fr[rng.permutation(len(fr))],
    }


def table_set_map(bases, nsets):
    """bases[t] = LLC set of line 0 of table t; line l -> (bases[t] + l) % nsets.
    (Constant rotation, as in your physical-set congruence check.)"""
    return np.array([[(b + l) % nsets for l in range(16)] for b in bases])


def _standardize(X):
    sd = X.std(0)
    sd[sd == 0] = 1.0
    return (X - X.mean(0)) / sd


def location_scores(values, nval, cls_of_value, Xt):
    """
    values: (N,) ints in [0,nval); cls_of_value: (G, nval) predicted line per
    guess; Xt: (N,16) standardized latencies of the 16 sets of one table.
    Score(g) = mean over lines l of [mean Xt[:,l] when predicted line == l
                                     - mean Xt[:,l] otherwise].
    Returns (scores, z): z uses Var(diff_l) ~ 1/c_in + 1/c_out and treats the
    16 sets as independent (check with --nperm calibration).
    """
    n = len(values)
    onehot = np.zeros((n, nval))
    onehot[np.arange(n), values] = 1.0
    cnt = onehot.sum(0)                     # (nval,)
    S = onehot.T @ Xt                       # (nval, 16) sums; column sums = 0
    G = cls_of_value.shape[0]
    scores, z = np.full(G, np.nan), np.full(G, np.nan)
    lines = np.arange(16)
    for g in range(G):
        M = (cls_of_value[g][:, None] == lines[None, :]).astype(float)  # (nval,16)
        s_in = (M * S).sum(0)
        c_in = M.T @ cnt
        v = (c_in > 0) & (c_in < n)
        if not v.any():
            continue
        diff = s_in[v] / c_in[v] + s_in[v] / (n - c_in[v])
        var = (1 / c_in[v] + 1 / (n - c_in[v])).sum() / v.sum() ** 2
        scores[g] = diff.mean()
        z[g] = scores[g] / np.sqrt(var)
    return scores, z


FR_GUESS = np.array([[(v ^ g) for v in range(16)] for g in range(16)])      # on p>>4
LR_GUESS = np.array([INV_SBOX[np.arange(256) ^ g] >> 4 for g in range(256)])  # on c


HYPS = ["p_xor_k", "p_only", "lastround_c_xor_k10", "c_only", "shuffled"]
C_ONLY = np.array([np.arange(256) >> 4])


def _attr_one_byte(i, pt, ct, key, k10, Z, setmap, tables_last, perm):
    t_fr, t_lr = i % 4, tables_last[i]
    Xa, Xb = Z[:, setmap[t_fr]], Z[:, setmap[t_lr]]
    pn, cb = (pt[:, i] >> 4).astype(int), ct[:, i].astype(int)
    kn = key[i] >> 4
    fr, frz = location_scores(pn, 16, FR_GUESS, Xa)
    lr, lrz = location_scores(cb, 256, LR_GUESS, Xb)
    co, coz = location_scores(cb, 256, C_ONLY, Xb)
    sh, shz = location_scores(pn[perm], 16, FR_GUESS[kn:kn + 1], Xa)
    sc = {"p_xor_k": fr[kn], "p_only": fr[0], "lastround_c_xor_k10": lr[k10[i]],
          "c_only": co[0], "shuffled": sh[0]}
    zz = {"p_xor_k": frz[kn], "p_only": frz[0], "lastround_c_xor_k10": lrz[k10[i]],
          "c_only": coz[0], "shuffled": shz[0]}
    rank_fr = int((fr > fr[kn]).sum()) + 1
    rank_lr = int((lr > lr[k10[i]]).sum()) + 1
    return sc, zz, rank_fr, rank_lr


def attribution(pt, ct, key, rk, X, setmap, tables_last, rng):
    """Location-aware scores, one-sided z, p-values and key ranks per byte."""
    from scipy.stats import norm
    Z = _standardize(X)
    sc = {h: np.zeros(16) for h in HYPS}
    zz = {h: np.zeros(16) for h in HYPS}
    r_fr, r_lr = [], []
    for i in range(16):
        s, z, a, b = _attr_one_byte(i, pt, ct, key, rk[10], Z, setmap, tables_last,
                                    rng.permutation(len(pt)))
        for h in HYPS:
            sc[h][i], zz[h][i] = s[h], z[h]
        r_fr.append(a); r_lr.append(b)
    pv = {h: norm.sf(zz[h]) for h in HYPS}
    return sc, zz, pv, r_fr, r_lr


def calibrate_null(pt, ct, key, rk, X, setmap, tables_last, rng, nperm):
    """Shuffle windows -> z of the TRUE-key hypotheses under no leakage.
    If the analytic z is calibrated, ~1% of these exceed 2.33."""
    Z = _standardize(X)
    out = []
    for _ in range(nperm):
        q = rng.permutation(len(pt))
        for i in range(16):
            _, z, _, _ = _attr_one_byte(i, pt[q], ct[q], key, rk[10], Z, setmap, tables_last, q)
            out += [z["p_xor_k"], z["lastround_c_xor_k10"]]
    return np.array(out)


# ----------------------------------------------------------------------------
# I/O
# ----------------------------------------------------------------------------

def load_probes(path, nsets):
    if path.endswith(".npy"):
        X = np.load(path)
    else:
        X = np.fromfile(path, dtype="<u4")
        if X.size % nsets:
            sys.exit(f"{path}: {X.size} values is not a multiple of nsets={nsets}")
        X = X.reshape(-1, nsets)
    return X.astype(np.float64)


def ct_checksum(ct):
    """XOR-fold of all ciphertexts; victim.c prints the same value."""
    return bytes(np.bitwise_xor.reduce(ct, axis=0)).hex()


# ----------------------------------------------------------------------------
# Synthetic traces (rehearsal only -- NOT a model of gem5)
# ----------------------------------------------------------------------------

def synth_traces(key, seed, n, nsets=256, table_base=64, rounds=10, delta=40.0,
                 noise=6.0, visibility=1.0, last="te4", rng=None):
    rng = rng or np.random.default_rng(1)
    pt = plaintexts(seed, n)
    rk = key_expansion(key)
    ct, lookups, tables = aes_encrypt_trace(pt, rk, last)
    X = 100.0 + rng.normal(0, noise, size=(n, nsets))
    touched = np.zeros((n, nsets), dtype=bool)
    for r in range(rounds):
        sets = table_base + 16 * tables[r][None, :] + (lookups[:, r, :] >> 4)
        np.put_along_axis(touched, (sets % nsets).astype(int), True, axis=1)
    X += delta * (touched & (rng.random((n, nsets)) < visibility))
    return X, pt, ct


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------

def anova_p_min(labels, X, nclass=16):
    """Per-set one-way ANOVA F test; returns (max SNR, argmax set,
    Bonferroni-over-sets p of the best set)."""
    from scipy.stats import f as fdist
    cnt, s1, s2 = class_stats(labels, X, nclass)
    ok = cnt > 0
    cnt, s1, s2 = cnt[ok, None], s1[ok], s2[ok]
    n, k = cnt.sum(), len(cnt)
    m_k = s1 / cnt
    m = s1.sum(0) / n
    ssb = (cnt * (m_k - m) ** 2).sum(0)
    ssw = (s2 - cnt * m_k ** 2).sum(0)
    F = (ssb / (k - 1)) / np.maximum(ssw / (n - k), 1e-30)
    p = fdist.sf(F, k - 1, n - k)
    snr_v = snr_from_stats(cnt[:, 0], s1, s2)
    j = int(np.nanargmin(p))
    return float(np.nanmax(snr_v)), int(np.nanargmax(snr_v)), min(1.0, float(p[j]) * X.shape[1])


def run_analysis(X, pt, ct, key, bases, nperm=0, seed=5764, last="te4", quiet=False):
    rng = np.random.default_rng(seed)
    rk = key_expansion(key)
    nsets = X.shape[1]
    tables_last = aes_encrypt_trace(pt[:1], rk, last)[2][9]
    res = {"n_windows": int(len(X))}

    # (A) detection
    det = detection_labels(pt, ct, rk, rng)
    rows = {m: [anova_p_min(L[:, i], X) for i in range(16)] for m, L in det.items()}
    names = list(det)
    adj = holm(np.array([[r[2] for r in rows[m]] for m in names]).ravel()).reshape(len(names), 16)
    res["detection"] = {m: {"max_snr_per_byte": [round(r[0], 5) for r in rows[m]],
                            "best_set_per_byte": [r[1] for r in rows[m]],
                            "holm_p_per_byte": adj[k].tolist(),
                            "bytes_significant": int((adj[k] < 0.05).sum())}
                        for k, m in enumerate(names)}

    # (B) attribution (needs table->set map)
    if bases is not None:
        setmap = table_set_map(bases, nsets)
        sc, zz, pv, r_fr, r_lr = attribution(pt, ct, key, rk, X, setmap, tables_last, rng)
        adjb = holm(np.concatenate([pv[h] for h in HYPS])).reshape(len(HYPS), 16)
        res["attribution"] = {h: {"score_per_byte": np.round(sc[h], 5).tolist(),
                                  "z_per_byte": np.round(zz[h], 2).tolist(),
                                  "holm_p_per_byte": adjb[k].tolist(),
                                  "bytes_significant": int((adjb[k] < 0.05).sum())}
                              for k, h in enumerate(HYPS)}
        res["key_rank_first_round_upper_nibble"] = r_fr
        res["key_rank_last_round_full_byte"] = r_lr
        res["key_bytes_with_zero_upper_nibble"] = [i for i in range(16) if key[i] >> 4 == 0]
        if nperm:
            nz = calibrate_null(pt, ct, key, rk, X, setmap, tables_last, rng, nperm)
            res["null_calibration"] = {"n": int(nz.size), "frac_z_gt_2.33": float((nz > 2.33).mean()),
                                       "z_sd": float(nz.std())}

    if not quiet:
        print(f"\nwindows = {len(X)}, sets = {nsets}")
        print("\n(A) DETECTION  (location-free; p and p^k are the same partition here)")
        print(f"  {'partition':14s} {'mean maxSNR':>12s} {'bytes sig':>10s}")
        for m in names:
            d = res["detection"][m]
            print(f"  {m:14s} {np.mean(d['max_snr_per_byte']):12.5f} {d['bytes_significant']:>7d}/16")
        if bases is not None:
            print("\n(B) ATTRIBUTION (location-aware; which data explains WHERE it leaks)")
            print(f"  {'hypothesis':22s} {'mean z':>8s} {'bytes sig':>10s}")
            for h in HYPS:
                d = res["attribution"][h]
                print(f"  {h:22s} {np.mean(d['z_per_byte']):8.2f} {d['bytes_significant']:>7d}/16")
            print("\n  rank of TRUE key among guesses (1 = best):")
            print("    first round, upper nibble (16 guesses):", r_fr)
            print("    last round, full k10 byte (256 guesses):", r_lr)
            z = res["key_bytes_with_zero_upper_nibble"]
            if z:
                print(f"  WARNING: key bytes {z} have upper nibble 0 -> p^k == p at line"
                      " granularity there; choose a key with nonzero upper nibbles.")
            if nperm:
                c = res["null_calibration"]
                print(f"  null calibration: {c['frac_z_gt_2.33']:.3f} of {c['n']} shuffled z > 2.33"
                      f" (expect ~0.01), sd={c['z_sd']:.2f} (expect ~1)")
        else:
            print("\n(B) skipped: pass --table-bases to separate plaintext from key leakage")
    return res


def parse_bases(s):
    return None if not s else [int(x, 0) for x in s.split(",")]


def cmd_analyze(a):
    X = load_probes(a.probes, a.nsets)[a.drop_first:]
    n = len(X)
    pt = plaintexts(a.seed, n + a.drop_first)[a.drop_first:]
    rk = key_expansion(a.key)
    ct, _, _ = aes_encrypt_trace(pt, rk, a.last_round)
    if a.victim_checksum:
        full = aes_encrypt_trace(plaintexts(a.seed, a.n_victim or n + a.drop_first), rk)[0]
        mine = ct_checksum(full)
        print(f"ciphertext checksum python={mine} victim={a.victim_checksum.lower()}",
              "OK" if mine == a.victim_checksum.lower() else "MISMATCH -> key/seed/window count differ")
    bases = parse_bases(a.table_bases)
    if bases is not None and len(bases) < (5 if a.last_round == "te4" else 4):
        sys.exit("--table-bases needs 5 values for te4 (Te0..Te3, Te4), 4 for openssl")
    res = run_analysis(X, pt, ct, a.key, bases, a.nperm, last=a.last_round)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(res, f, indent=1)
        print("wrote", a.out)
    if a.plot:
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 4))
        for m, L in detection_labels(pt, ct, rk, np.random.default_rng(0)).items():
            curve = np.nanmax(np.stack([snr(L[:, i], X) for i in range(16)]), 0)
            ax.plot(curve, label=m, lw=1)
        ax.set_xlabel("LLC set"); ax.set_ylabel("max SNR over 16 bytes"); ax.legend()
        fig.tight_layout(); fig.savefig(a.plot, dpi=150); print("wrote", a.plot)


def cmd_tvla(a):
    X = load_probes(a.probes, a.nsets)[a.drop_first:]
    first_fixed = (a.drop_first % 2 == 0)
    fixed, rand = (X[0::2], X[1::2]) if first_fixed else (X[1::2], X[0::2])
    t = welch_t(fixed, rand)
    print(f"fixed={len(fixed)} random={len(rand)}  max|t|={np.nanmax(np.abs(t)):.2f}"
          f"  sets with |t|>4.5: {np.flatnonzero(np.abs(t) > 4.5).tolist()}")


def cmd_synth(a):
    X, _, _ = synth_traces(a.key, a.seed, a.n, a.nsets, a.table_base, a.rounds,
                           a.delta, a.noise, a.visibility, a.last_round)
    X.round().astype("<u4").tofile(a.out)
    print(f"wrote {a.out}: {a.n} windows x {a.nsets} sets")


def cmd_oracle(a):
    pt = plaintexts(a.seed, a.n)
    rk = key_expansion(a.key)
    ct, lookups, tables = aes_encrypt_trace(pt, rk, a.last_round)
    ntab = 5 if a.last_round == "te4" else 4
    lines = np.zeros((a.n, ntab * 16), dtype=np.uint8)
    for r in range(10):
        idx = 16 * tables[r][None, :] + (lookups[:, r, :] >> 4)
        np.put_along_axis(lines, idx.astype(int), 1, axis=1)
    np.save(a.out, lines)
    print(f"wrote {a.out}: (windows, table*16+line) touched-line bitmap; "
          f"mean lines touched per table = {lines.reshape(a.n, ntab, 16).sum(2).mean(0).round(2)}")


def cmd_selftest(a):
    ok = True
    # FIPS-197 Appendix C.1
    key = hex16("000102030405060708090a0b0c0d0e0f")
    pt = hex16("00112233445566778899aabbccddeeff")[None, :]
    ct = aes_encrypt_trace(pt, key_expansion(key))[0][0]
    good = bytes(ct).hex() == "69c4e0d86a7b0430d8cdb78070b4c55a"
    print("AES FIPS-197 C.1  :", "PASS" if good else f"FAIL {bytes(ct).hex()}"); ok &= good
    # FIPS-197 Appendix A.1 last round key
    k = hex16("2b7e151628aed2a6abf7158809cf4f3c")
    good = bytes(key_expansion(k)[10]).hex() == "d014f9a8c9ee2589e13f0cc8b6630ca6"
    print("Key expansion A.1 :", "PASS" if good else "FAIL"); ok &= good
    # splitmix64 reference values for seed 0 (also printed by prng_check.c)
    g = splitmix64_stream(0)
    v = [next(g) for _ in range(2)]
    good = v == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4]
    print("splitmix64 seed 0 :", "PASS" if good else f"FAIL {[hex(x) for x in v]}"); ok &= good
    # End-to-end on synthetic data. Key chosen so every upper nibble is nonzero.
    key = hex16("f1e2d3c4b5a69788796a5b4c3d2e1f10")
    bases = [64, 80, 96, 112, 128]
    for rounds, n in [(1, 1500), (10, 6000)]:
        X, pt, ct = synth_traces(key, 0x5764A5E5, n, rounds=rounds)
        res = run_analysis(X, pt, ct, key, bases, nperm=3, quiet=True)
        at = res["attribution"]
        r1, r10 = res["key_rank_first_round_upper_nibble"], res["key_rank_last_round_full_byte"]
        cond = (at["p_xor_k"]["bytes_significant"] == 16 and at["p_only"]["bytes_significant"] == 0
                and at["shuffled"]["bytes_significant"] == 0 and max(r1) == 1
                and res["detection"]["shuffled"]["bytes_significant"] == 0)
        if rounds == 10:
            cond &= max(r10) == 1 and at["lastround_c_xor_k10"]["bytes_significant"] == 16
        else:
            cond &= at["lastround_c_xor_k10"]["bytes_significant"] == 0
        cal = res["null_calibration"]["frac_z_gt_2.33"]
        cond &= cal < 0.05
        print(f"synthetic rounds={rounds:2d} N={n}: sig bytes p^k={at['p_xor_k']['bytes_significant']}"
              f" p_only={at['p_only']['bytes_significant']} lastround={at['lastround_c_xor_k10']['bytes_significant']}"
              f" c_only={at['c_only']['bytes_significant']} shuffled={at['shuffled']['bytes_significant']};"
              f" worst key rank fr={max(r1)} lr={max(r10)}; null z>2.33 frac={cal:.3f} -> {'PASS' if cond else 'FAIL'}")
        ok &= cond
    print("\nSELFTEST", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, probes=True):
        sp.add_argument("--key", type=hex16, required=True, help="16-byte hex AES key")
        sp.add_argument("--seed", type=lambda s: int(s, 0), default=0x5764A5E5)
        sp.add_argument("--nsets", type=int, default=256)
        sp.add_argument("--last-round", choices=["te4", "openssl"], default="te4")
        if probes:
            sp.add_argument("probes")
            sp.add_argument("--drop-first", type=int, default=0, help="warm-up windows to discard")

    sp = sub.add_parser("analyze"); common(sp)
    sp.add_argument("--nperm", type=int, default=0, help="shuffles for null calibration (e.g. 20)")
    sp.add_argument("--table-bases", help="LLC set of line 0 of Te0,Te1,Te2,Te3[,Te4], e.g. 64,80,96,112,128")
    sp.add_argument("--victim-checksum", help="hex printed by victim at exit")
    sp.add_argument("--n-victim", type=int, help="windows the victim ran (default: probes)")
    sp.add_argument("--out", help="JSON summary path"); sp.add_argument("--plot", help="PNG path")
    sp.set_defaults(f=cmd_analyze)

    sp = sub.add_parser("tvla"); common(sp); sp.set_defaults(f=cmd_tvla)

    sp = sub.add_parser("synth"); common(sp, probes=False)
    sp.add_argument("--n", type=int, default=4000); sp.add_argument("--out", default="synth_probes.bin")
    sp.add_argument("--rounds", type=int, default=10); sp.add_argument("--table-base", type=int, default=64)
    sp.add_argument("--delta", type=float, default=40); sp.add_argument("--noise", type=float, default=6)
    sp.add_argument("--visibility", type=float, default=1.0)
    sp.set_defaults(f=cmd_synth)

    sp = sub.add_parser("oracle"); common(sp, probes=False)
    sp.add_argument("--n", type=int, required=True); sp.add_argument("--out", default="oracle_lines.npy")
    sp.set_defaults(f=cmd_oracle)

    sp = sub.add_parser("selftest"); sp.set_defaults(f=cmd_selftest)
    a = p.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
