#!/usr/bin/env python3
"""
aes_leak_analysis.py -- Which public data does the LLC probe monitor see?

SIMULATOR ONLY.  One WINDOW = the monitor primes its own lines -> the AES
workload performs exactly one encryption -> the monitor re-times its lines.
The key (a fixed PUBLIC test constant) and the plaintext stream are known, so
every plaintext/ciphertext is regenerated offline and each leakage MODEL is
tested against the probe latencies.  This is a known-key leakage assessment of
a defense configuration: the analysis never searches for a key, and it does not
score key guesses (that would go beyond the accepted proposal's "does not
recover or guess key bytes").  Models use the known key only.

Models (per byte i = 0..15; table lines = 16 for Te tables, 4 for the sbox)
  p_xor_k        round 1: line (p_i ^ k_i) >> 4 of Te_(i%4)     [key dependent]
  p_only         round 1: line  p_i        >> 4 of Te_(i%4)     [no key]
  shuffled       p_xor_k labels with the windows permuted       [must be null]
  lr_c_xor_k10   last round: line InvS[c_i ^ k10_i] >> 6 of the sbox
  c_only         last round: line  c_i >> 6 of the sbox          [no key]
  lr_shuffled    lr_c_xor_k10 with the windows permuted          [must be null]

Subcommands
  selftest   AES / PRNG known answers + synthetic end-to-end checks
  synth      write a complete fake run directory (probes.bin, stats.txt,
             simout.txt, leak_config.json, victim_table.trace)
  analyze    analyse a run directory written by run_leakage.py (or synth)

Requires numpy and scipy.  Synthetic data are a rehearsal tool, not a model of
gem5: nothing they produce is a leakage result.
"""
import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

import numpy as np


class AnalysisError(Exception):
    """The run directory cannot be analysed (a hard failure, not a result)."""


# ----------------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------------
NSETS = 256
NWAYS = 16
TICKS_PER_CYCLE = 500                      # 2 GHz CPU, 1 tick = 1 ps
PREFIX = "system.llc.partitioning_manager."
TABLES = ("sbox", "te0", "te1", "te2", "te3")
TABLE_LINES = {"sbox": 4, "te0": 16, "te1": 16, "te2": 16, "te3": 16}
DEFAULT_LINE_OFFSETS = {"sbox": 0, "te0": 4, "te1": 20, "te2": 36, "te3": 52}
N_TABLE_LINES = 68
DEFAULT_SCHEDULE = {"T0": 2_000_000, "W": 1_048_576, "OFF_PRIME": 65_536,
                    "OFF_ENC": 524_288, "OFF_ENC_END": 589_824,
                    "OFF_PROBE": 593_920}
DEFAULT_KEY_HEX = "f1e2d3c4b5a69788796a5b4c3d2e1f10"
TVLA_FIXED_PT_HEX = "da39a3ee5e6b4b0d3255bfef95601890"
PROBE_DTYPE = np.dtype([("timestamp", "<u8"), ("latency", "<u4"),
                        ("interval", "<u2"), ("cache_set", "<u2")])
HYPOTHESES = ["p_xor_k", "p_only", "shuffled",
              "lr_c_xor_k10", "c_only", "lr_shuffled"]
ALPHA = 0.05

# ----------------------------------------------------------------------------
# AES-128 reference (generated S-box, so there are no table typos to trust)
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


def aes_encrypt_trace(pt, rk):
    """
    Vectorised AES-128 over N blocks (pt: (N,16) uint8).
    Returns (ciphertexts (N,16), lookups (N,10,16), tables (10,16)):
      lookups[:, r-1, i] = state byte used as a table index in round r
      tables[r-1, i]     = which table: 0..3 = Te0..Te3 (rounds 1-9, row i%4),
                           4 = the 256 B sbox (round 10, as in aes_ttable.c)
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
    tables[9, :] = 4
    return s, lookups, tables


# ----------------------------------------------------------------------------
# Deterministic public plaintext stream -- MUST match leak_schedule.h
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
    """Window j draws two 64-bit words -> 16 bytes (little-endian: lo, hi).
    In TVLA mode even windows use the fixed plaintext instead (the words are
    still drawn, so the random stream stays aligned with the workload)."""
    g = splitmix64_stream(seed)
    out = np.zeros((n, 16), dtype=np.uint8)
    for j in range(n):
        lo, hi = next(g), next(g)
        out[j] = np.frombuffer((lo | (hi << 64)).to_bytes(16, "little"),
                               dtype=np.uint8)
    if tvla_fixed is not None:
        out[0::2] = tvla_fixed
    return out


def hex16(s):
    b = bytes.fromhex(s.replace(" ", ""))
    if len(b) != 16:
        raise argparse.ArgumentTypeError("need 16 bytes of hex")
    return np.frombuffer(b, dtype=np.uint8).copy()


def fold(blocks):
    """XOR-fold of all blocks, as the victim prints it (hex)."""
    return bytes(np.bitwise_xor.reduce(blocks, axis=0)).hex()


# ----------------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------------


def class_stats(labels, X, nclass):
    """Per-class count, sum, sum of squares of every column of X."""
    onehot = np.zeros((X.shape[0], nclass))
    onehot[np.arange(X.shape[0]), labels] = 1.0
    return onehot.sum(0), onehot.T @ X, onehot.T @ (X * X)


def snr_from_stats(cnt, s1, s2, min_count=2):
    ok = cnt >= min_count
    c, a, b = cnt[ok, None], s1[ok], s2[ok]
    mean = a / c
    var = b / c - mean ** 2
    noise = var.mean(0)
    noise[noise <= 0] = np.nan
    return mean.var(0) / noise          # Mangard SNR (NOT the proposal's SNR)


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


def standardize(X):
    sd = X.std(0)
    sd[sd == 0] = 1.0
    return (X - X.mean(0)) / sd


def anova_p_min(labels, X, nclass):
    """Per-set one-way ANOVA across `nclass` byte-value classes.
    Returns (max SNR, argmax set, Bonferroni-over-sets p of the best set)."""
    from scipy.stats import f as fdist
    cnt, s1, s2 = class_stats(labels, X, nclass)
    ok = cnt > 0
    cnt, s1, s2 = cnt[ok, None], s1[ok], s2[ok]
    n, k = cnt.sum(), len(cnt)
    if k < 2:
        return float("nan"), 0, 1.0
    m_k = s1 / cnt
    m = s1.sum(0) / n
    ssb = (cnt * (m_k - m) ** 2).sum(0)
    ssw = (s2 - cnt * m_k ** 2).sum(0)
    F = (ssb / (k - 1)) / np.maximum(ssw / (n - k), 1e-30)
    p = fdist.sf(F, k - 1, n - k)
    snr_v = snr_from_stats(cnt[:, 0], s1, s2)
    j = int(np.nanargmin(p))
    return (float(np.nanmax(snr_v)), int(np.nanargmax(snr_v)),
            min(1.0, float(p[j]) * X.shape[1]))


def hypothesis_score(lines, Xt):
    """
    Location-aware score of ONE hypothesis for ONE byte.

    lines: (N,) predicted table line per window, in [0, n_lines)
    Xt:    (N, n_lines) standardized latencies of the n_lines LLC sets that
           hold that table's lines (column sums are zero)
    score = mean over lines l of [mean Xt[:,l] when the hypothesis predicts
            line l  -  mean Xt[:,l] otherwise]; z uses
            Var(diff_l) ~ 1/c_in + 1/c_out and treats the lines as independent
            (checked by the permutation calibration, --nperm).
    Works for any n_lines (16 for Te tables, 4 for the sbox).
    """
    n, n_lines = Xt.shape
    lines = np.asarray(lines, dtype=int)
    cnt = np.bincount(lines, minlength=n_lines).astype(float)
    s_in = np.array([Xt[lines == l, l].sum() for l in range(n_lines)])
    valid = (cnt > 0) & (cnt < n)
    if not valid.any():
        return float("nan"), float("nan")
    c, s = cnt[valid], s_in[valid]
    diff = s / c + s / (n - c)
    var = (1.0 / c + 1.0 / (n - c)).sum() / valid.sum() ** 2
    score = float(diff.mean())
    return score, float(score / np.sqrt(var))


def classify_bytes(z_key, z_plain, z_shuf, p_key, p_plain, alpha):
    """Per-byte label from the two competing round models.
    p_* are Holm-adjusted p-values.  A byte is `plaintext_plus_key` when only
    the key-dependent model is significant and it beats the shuffled control,
    `plaintext_only` when only the key-free model does, `ambiguous` when both
    are significant (or the winner does not beat the control), else `none`."""
    labels = []
    for zk, zp, zs, pk, pp in zip(z_key, z_plain, z_shuf, p_key, p_plain):
        key_sig, plain_sig = pk < alpha, pp < alpha
        if not key_sig and not plain_sig:
            labels.append("none")
        elif key_sig and plain_sig:
            labels.append("ambiguous")
        elif key_sig:
            labels.append("plaintext_plus_key" if zk > zs else "ambiguous")
        else:
            labels.append("plaintext_only" if zp > zs else "ambiguous")
    return labels


# ----------------------------------------------------------------------------
# Models: which table line each hypothesis predicts, per byte and window
# ----------------------------------------------------------------------------


def predicted_lines(hyp, i, pt, ct, key, rk10, perm):
    """(table name, (N,) predicted line) for hypothesis `hyp` and byte i."""
    if hyp in ("p_xor_k", "p_only", "shuffled"):
        table = "te%d" % (i % 4)
        if hyp == "p_only":
            return table, (pt[:, i] >> 4).astype(int)
        lines = ((pt[:, i] ^ key[i]) >> 4).astype(int)
        return table, (lines[perm] if hyp == "shuffled" else lines)
    if hyp == "c_only":
        return "sbox", (ct[:, i] >> 6).astype(int)
    lines = (INV_SBOX[ct[:, i] ^ rk10[i]] >> 6).astype(int)
    return "sbox", (lines[perm] if hyp == "lr_shuffled" else lines)


def touched_lines(lookups, rounds1, offsets):
    """Oracle: which of the 68 table lines the encryption algorithmically
    touches in each window.  Global line index = table line offset + line.
    rounds1 restricts it to round 1 (the positive-control mode)."""
    n = lookups.shape[0]
    out = np.zeros((n, N_TABLE_LINES), dtype=bool)
    rows = np.arange(n)
    for r in ([0] if rounds1 else range(10)):
        for i in range(16):
            if r < 9:
                idx = offsets["te%d" % (i % 4)] + (lookups[:, r, i] >> 4)
            else:
                idx = offsets["sbox"] + (lookups[:, 9, i] >> 6)
            out[rows, idx.astype(int)] = True
    return out


# ----------------------------------------------------------------------------
# Run-directory inputs
# ----------------------------------------------------------------------------

_SCALAR = re.compile(r"^(\S+)\s+([-+]?(?:\d+\.?\d*(?:[eE][-+]?\d+)?|nan|inf))\b")
_VECTOR = re.compile(r"^(\S+?)::(\S+)\s+([-+]?\d+\.?\d*(?:[eE][-+]?\d+)?)\b")
_TRACE = re.compile(r"^\s*(\d+):.*?victim_fill line=(\d+) set=(\d+)")


def parse_first_stats_block(text):
    """Scalars and indexed vector entries of the FIRST statistics block.
    (gem5 appends a block per dump; the measurement dump is the first.)"""
    scalars, vectors = {}, {}
    for line in text.splitlines():
        if line.startswith("---------- End"):
            break
        if line.startswith("---------- Begin") or not line.strip():
            continue
        match = _VECTOR.match(line)
        if match:
            name, key, value = match.groups()
            if key.isdigit():
                vectors.setdefault(name, {})[int(key)] = float(value)
            continue
        match = _SCALAR.match(line)
        if match:
            scalars[match.group(1)] = float(match.group(2))
    return scalars, vectors


_WAY_OCC = re.compile(r"^\S+?::(p\d+|other)::way(\d+)\s+(\d+)\b")


def parse_way_occupancy(text):
    """Valid LLC blocks per (partition row, way) from the first statistics
    block; the catch-all 'other' row is key -1."""
    occupancy = {}
    for line in text.splitlines():
        if line.startswith("---------- End"):
            break
        match = _WAY_OCC.match(line)
        if match:
            row = -1 if match.group(1) == "other" else int(match.group(1)[1:])
            occupancy[(row, int(match.group(2)))] = int(match.group(3))
    return occupancy


def isolation_violations(occupancy, split):
    """The proposal's isolation metric: valid blocks outside the assigned ways
    (partition 0 = monitor owns ways [0, A), partition 1 = AES owns [A, 16),
    'other' may own none).  None for an unpartitioned run."""
    if split in (None, "off"):
        return None
    monitor_ways = int(split.split("-")[0])
    violations = 0
    for (row, way), blocks in occupancy.items():
        allowed = ((row == 0 and way < monitor_ways) or
                   (row == 1 and way >= monitor_ways))
        if not allowed:
            violations += blocks
    return violations


def build_line_map(scalars, vectors, cfg):
    """Logical monitor set of each of the 68 table lines, from the stats.
    logical = (physical - rotation) mod 256.  Fails on any unmapped line, any
    recorded set change, or two table lines sharing one set."""
    rotation = scalars.get(PREFIX + "probeSetRotation")
    plus_one = vectors.get(PREFIX + "victimTableLineSetPlusOne")
    mismatches = scalars.get(PREFIX + "victimTableSetMismatches")
    if rotation is None or plus_one is None or mismatches is None:
        raise AnalysisError(
            "stats.txt lacks probeSetRotation / victimTableLineSetPlusOne / "
            "victimTableSetMismatches: was the run made with the gem5 tracing "
            "extension (experiments/aes-leakage/gem5_ext)?")
    if mismatches > 0:
        raise AnalysisError(
            "set mismatch: victimTableSetMismatches=%d, so a table line's LLC "
            "set changed during the run and the line-to-set map is not "
            "constant" % mismatches)
    probe_mismatch = scalars.get(PREFIX + "probeSetMappingMismatches", 0)
    if probe_mismatch > 0:
        raise AnalysisError("set mismatch: probeSetMappingMismatches=%d, the "
                            "monitor's logical-to-physical set rotation is "
                            "not constant" % probe_mismatch)
    tables = cfg.get("tables") or {
        t: {"line_offset": DEFAULT_LINE_OFFSETS[t], "lines": TABLE_LINES[t]}
        for t in TABLES}
    physical = [None] * N_TABLE_LINES
    logical = [None] * N_TABLE_LINES
    unmapped, owner = [], {}
    for name in TABLES:
        offset, count = tables[name]["line_offset"], tables[name]["lines"]
        for line in range(count):
            value = int(plus_one.get(offset + line, 0))
            if value == 0:
                unmapped.append("%s[%d]" % (name, line))
                continue
            physical[offset + line] = value - 1
            logical[offset + line] = (value - 1 - int(rotation)) % NSETS
    if unmapped:
        raise AnalysisError(
            "%d table line(s) unmapped (never filled into the LLC, or absent "
            "from stats): %s" % (len(unmapped), ", ".join(unmapped[:8])))
    for name in TABLES:
        offset = tables[name]["line_offset"]
        for line in range(tables[name]["lines"]):
            s = logical[offset + line]
            if s in owner:
                raise AnalysisError(
                    "table lines %s and %s share logical set %d; attribution "
                    "would be confounded" % (owner[s], "%s[%d]" % (name, line), s))
            owner[s] = "%s[%d]" % (name, line)
    return {
        "rotation": int(rotation),
        "line_physical_set": physical,
        "line_logical_set": logical,
        "missing_vaddr": int(scalars.get(PREFIX + "victimTableMissingVaddr", 0)),
        "tables": {name: {
            "line_offset": tables[name]["line_offset"],
            "logical_sets": logical[tables[name]["line_offset"]:
                                    tables[name]["line_offset"] +
                                    tables[name]["lines"]]}
            for name in TABLES},
    }


def read_probes(path, n_win):
    """probes.bin (probe_bin_v2) -> latency matrix (n_win, 256), validated."""
    raw = Path(path).read_bytes()
    expected = n_win * NSETS * PROBE_DTYPE.itemsize
    if len(raw) != expected:
        raise AnalysisError(
            "probes.bin is %d bytes, expected %d (%d windows x %d sets x 16 B)"
            % (len(raw), expected, n_win, NSETS))
    rec = np.frombuffer(raw, dtype=PROBE_DTYPE)
    index = np.arange(len(rec))
    bad = np.flatnonzero(rec["interval"] != (index // NSETS) % 65536)
    if bad.size:
        raise AnalysisError("probes.bin: interval field of record %d is %d, "
                            "expected %d" % (bad[0], rec["interval"][bad[0]],
                                             bad[0] // NSETS))
    bad = np.flatnonzero(rec["cache_set"] != index % NSETS)
    if bad.size:
        raise AnalysisError("probes.bin: cache_set field of record %d is %d, "
                            "expected %d" % (bad[0], rec["cache_set"][bad[0]],
                                             bad[0] % NSETS))
    if (np.diff(rec["timestamp"].astype(np.int64)) < 0).any():
        raise AnalysisError("probes.bin: timestamps are not monotone")
    return rec["latency"].reshape(n_win, NSETS).astype(np.float64)


_SIM_HEADER = re.compile(
    r"victim leak_format=v1 key=([0-9a-f]{32}) seed=(\d+) windows=(\d+) "
    r"rounds1=(\d) scrub=(\d) tvla=(\d)")
_SIM_CHECKSUM = re.compile(
    r"victim pt_checksum=([0-9a-f]{32}) ct_checksum=([0-9a-f]{32})")
_SIM_MONITOR = re.compile(
    r"monitor format=probe_bin_v2 windows=(\d+) sets=256 ways=(\d+)")


def parse_simout(text):
    header = _SIM_HEADER.search(text)
    checksum = _SIM_CHECKSUM.search(text)
    monitor = _SIM_MONITOR.search(text)
    status = re.search(r"monitor status=PASS records=(\d+)", text)
    return {
        "self_test_pass": re.search(r"^victim aes_self_test=PASS$", text,
                                    re.M) is not None,
        "header": None if not header else {
            "key_hex": header.group(1), "seed": int(header.group(2)),
            "windows": int(header.group(3)), "rounds1": int(header.group(4)),
            "scrub": int(header.group(5)), "tvla": int(header.group(6))},
        "pt_checksum": checksum.group(1) if checksum else None,
        "ct_checksum": checksum.group(2) if checksum else None,
        "monitor_windows": int(monitor.group(1)) if monitor else None,
        "monitor_ways": int(monitor.group(2)) if monitor else None,
        "monitor_records": int(status.group(1)) if status else None,
        "errors": re.findall(r"^(?:victim|monitor) error=.*$", text, re.M),
    }


def parse_trace(text, cfg):
    """Fills from victim_table.trace as (window, offset in window, line).
    cycle = tick / 500; window = (cycle - T0) // W (negative = warm-up)."""
    t0, w = cfg["T0"], cfg["W"]
    events = []
    for line in text.splitlines():
        match = _TRACE.match(line)
        if not match:
            continue
        cycle = int(match.group(1)) // TICKS_PER_CYCLE
        window = (cycle - t0) // w
        events.append((window, cycle - t0 - window * w, int(match.group(2))))
    return events


def ground_truth(events, touched, cfg):
    """Compare simulator-side LLC fills with the algorithmically touched lines.
    NOTE the trace records LLC ALLOCATIONS only: a table line that stays
    resident in the LLC (e.g. in a way-partitioned run) produces no fill, so
    recall below 1 there is expected, not an error."""
    n = touched.shape[0]
    lo, hi = cfg["OFF_ENC"], cfg["OFF_ENC_END"]
    before = after = outside = in_phase = 0
    filled = [set() for _ in range(n)]
    for window, offset, line in events:
        if window < 0:
            before += 1
        elif window >= n:
            after += 1
        elif not lo <= offset <= hi:
            outside += 1
        else:
            in_phase += 1
            filled[window].add(line)
    hit = 0
    for w in range(n):
        hit += len(filled[w] & set(np.flatnonzero(touched[w]).tolist()))
    touched_total = int(touched.sum())
    filled_total = sum(len(f) for f in filled)
    return {
        "windows": n,
        "touched_total": touched_total,
        "recall": hit / touched_total if touched_total else None,
        "precision": hit / filled_total if filled_total else None,
        "fills_in_aes_phase": in_phase,
        "fills_outside_aes_phase": outside,
        "fills_before_measurement": before,
        "fills_after_measurement": after,
        "mean_fills_per_window": (in_phase + outside) / n if n else None,
    }


# ----------------------------------------------------------------------------
# Analysis of one run directory
# ----------------------------------------------------------------------------


def _check(checks, name, ok, detail=""):
    checks.append({"name": name, "ok": bool(ok), "detail": detail})


def _run_checks(cfg, sim, pt, ct, rounds1, n_win, missing_vaddr,
                violations=None):
    checks = []
    _check(checks, "aes_self_test_pass", sim["self_test_pass"],
           "FIPS-197 known-answer line in simout.txt")
    header = sim["header"]
    want = {"key_hex": cfg["key_hex"], "seed": cfg["workload_seed"],
            "windows": n_win, "rounds1": int(cfg["rounds1"]),
            "scrub": int(cfg["scrub"]), "tvla": int(cfg["tvla"])}
    _check(checks, "config_matches_simout", header == want,
           "simout header %s vs leak_config %s" % (header, want))
    pt_sum, ct_sum = fold(pt), fold(ct)
    ok = (sim["pt_checksum"] == pt_sum and
          (rounds1 or sim["ct_checksum"] == ct_sum))
    _check(checks, "checksum_matches", ok,
           "victim pt/ct checksum %s/%s vs python %s/%s%s" % (
               sim["pt_checksum"], sim["ct_checksum"], pt_sum, ct_sum,
               " (ct not computed in round-1 mode)" if rounds1 else ""))
    _check(checks, "monitor_status_pass",
           sim["monitor_records"] == n_win * NSETS and
           sim["monitor_windows"] == n_win and not sim["errors"],
           "monitor records=%s windows=%s errors=%s" % (
               sim["monitor_records"], sim["monitor_windows"], sim["errors"]))
    _check(checks, "table_fills_have_vaddr", missing_vaddr == 0,
           "victimTableMissingVaddr=%d" % missing_vaddr)
    if violations is not None:            # partitioned runs only
        _check(checks, "way_isolation", violations == 0,
               "stats lack wayOccupancy" if violations < 0 else
               "valid LLC blocks outside the assigned ways: %d" % violations)
    return {"all_passed": all(c["ok"] for c in checks), "checks": checks}


def _clean(obj):
    """Plain-JSON copy: numpy scalars/arrays to Python, NaN to None."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _clean(obj.tolist())
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        value = float(obj)
        return None if value != value else value
    return obj


def _decide(attr, alpha):
    """Preregistered rule: a data hypothesis is supported if it is significant
    (Holm) on >= 1 byte AND beats its key-free alternative and its shuffled
    control on those bytes.  No key guesses are scored."""
    def supported(main, other, shuffled):
        bytes_ = [i for i in range(16)
                  if attr[main]["holm_p_per_byte"][i] < alpha and
                  attr[main]["z_per_byte"][i] > attr[other]["z_per_byte"][i] and
                  attr[main]["z_per_byte"][i] > attr[shuffled]["z_per_byte"][i]]
        return bool(bytes_), bytes_
    out, support = {}, {}
    for label, args in (
            ("round1_plaintext_plus_key", ("p_xor_k", "p_only", "shuffled")),
            ("round1_plaintext_only", ("p_only", "p_xor_k", "shuffled")),
            ("lastround_c_xor_k10", ("lr_c_xor_k10", "c_only", "lr_shuffled")),
            ("lastround_ciphertext_only", ("c_only", "lr_c_xor_k10",
                                           "lr_shuffled"))):
        out[label], support[label] = supported(*args)
    out["alpha"] = alpha
    out["supporting_bytes"] = support
    return out


def analyze_run_dir(run_dir, nperm=0, drop_first=0, seed=5764, alpha=ALPHA):
    """Analyse a run directory.  Raises AnalysisError when the data cannot be
    attributed (unmapped lines, bad probe file); soft problems are reported in
    result['run_checks'] instead."""
    from scipy.stats import norm
    run_dir = Path(run_dir)

    def need(name):
        path = run_dir / name
        if not path.is_file():
            raise AnalysisError("%s is missing from %s" % (name, run_dir))
        return path

    cfg = json.loads(need("leak_config.json").read_text())
    n_win = int(cfg["N_WIN"])
    key = hex16(cfg["key_hex"])
    rounds1, tvla = bool(cfg["rounds1"]), bool(cfg["tvla"])
    rng = np.random.default_rng(seed)

    X_all = read_probes(need("probes.bin"), n_win)
    sim = parse_simout(need("simout.txt").read_text())
    stats_text = need("stats.txt").read_text()
    scalars, vectors = parse_first_stats_block(stats_text)
    line_map = build_line_map(scalars, vectors, cfg)
    violations = None
    if cfg.get("split") not in (None, "off"):
        occupancy = parse_way_occupancy(stats_text)
        violations = (isolation_violations(occupancy, cfg["split"])
                      if occupancy else -1)

    fixed = hex16(TVLA_FIXED_PT_HEX) if tvla else None
    pt_all = plaintexts(cfg["workload_seed"], n_win, tvla_fixed=fixed)
    rk = key_expansion(key)
    ct_all, lookups_all, _ = aes_encrypt_trace(pt_all, rk)
    offsets = {t: (cfg.get("tables") or {}).get(t, {}).get(
        "line_offset", DEFAULT_LINE_OFFSETS[t]) for t in TABLES}

    result = {
        "run": {"dir": str(run_dir), "n_windows": n_win,
                "analysed_windows": n_win - drop_first,
                "drop_first": drop_first, "key_hex": cfg["key_hex"],
                "seed": cfg["workload_seed"],
                "victim_variant": cfg.get("victim_variant"),
                "rounds1": int(rounds1), "scrub": int(cfg["scrub"]),
                "tvla": int(tvla), "split": cfg.get("split"),
                "monitor_ways": cfg.get("monitor_ways")},
        "run_checks": _run_checks(cfg, sim, pt_all, ct_all, rounds1, n_win,
                                  line_map["missing_vaddr"], violations),
        "line_map": {k: line_map[k] for k in
                     ("rotation", "line_physical_set", "line_logical_set")},
    }

    trace_path = run_dir / "victim_table.trace"
    result["ground_truth"] = None
    if trace_path.is_file():
        events = parse_trace(trace_path.read_text(), cfg)
        result["ground_truth"] = ground_truth(
            events, touched_lines(lookups_all, rounds1, offsets), cfg)

    X = X_all[drop_first:]
    pt, ct = pt_all[drop_first:], ct_all[drop_first:]
    n = len(X)
    result["tvla_test"] = None
    if tvla:
        first_fixed = drop_first % 2 == 0
        fixed_x, rand_x = ((X[0::2], X[1::2]) if first_fixed
                           else (X[1::2], X[0::2]))
        t = welch_t(fixed_x, rand_x)
        result["tvla_test"] = {
            "fixed_windows": len(fixed_x), "random_windows": len(rand_x),
            "max_abs_t": float(np.nanmax(np.abs(t))),
            "sets_over_4p5": np.flatnonzero(np.abs(t) > 4.5).tolist()}
        return _clean(result)

    # (A) detection: location-free ANOVA over byte-value classes
    rk10 = rk[10]
    det_labels = {
        "first_round": ([(pt[:, i] >> 4).astype(int) for i in range(16)], 16),
        "last_round": ([(INV_SBOX[ct[:, i] ^ rk10[i]] >> 6).astype(int)
                        for i in range(16)], 4),
        "c_line": ([(ct[:, i] >> 6).astype(int) for i in range(16)], 4),
    }
    shuffle = rng.permutation(n)
    det_labels["shuffled"] = ([lab[shuffle] for lab in
                               det_labels["first_round"][0]], 16)
    rows = {m: [anova_p_min(labels[i], X, nclass) for i in range(16)]
            for m, (labels, nclass) in det_labels.items()}
    names = list(rows)
    adj = holm(np.array([[r[2] for r in rows[m]] for m in names]).ravel()
               ).reshape(len(names), 16)
    result["detection"] = {
        m: {"classes": det_labels[m][1],
            "max_snr_per_byte": [round(r[0], 5) for r in rows[m]],
            "best_set_per_byte": [r[1] for r in rows[m]],
            "holm_p_per_byte": adj[k].tolist(),
            "bytes_significant": int((adj[k] < alpha).sum())}
        for k, m in enumerate(names)}

    # (B) attribution: which data explains WHERE the latency rises
    Z = standardize(X)
    z = {h: np.zeros(16) for h in HYPOTHESES}
    score = {h: np.zeros(16) for h in HYPOTHESES}
    true_lines = {}
    for i in range(16):
        perm = rng.permutation(n)
        for hyp in HYPOTHESES:
            table, lines = predicted_lines(hyp, i, pt, ct, key, rk10, perm)
            sets = line_map["tables"][table]["logical_sets"]
            score[hyp][i], z[hyp][i] = hypothesis_score(lines, Z[:, sets])
            if hyp in ("p_xor_k", "lr_c_xor_k10"):
                true_lines[(hyp, i)] = (table, lines)
    z = {h: np.nan_to_num(v, nan=0.0) for h, v in z.items()}
    pvals = np.concatenate([norm.sf(z[h]) for h in HYPOTHESES])
    adjusted = holm(pvals).reshape(len(HYPOTHESES), 16)
    result["attribution"] = {
        h: {"score_per_byte": np.round(score[h], 5),
            "z_per_byte": np.round(z[h], 3),
            "holm_p_per_byte": adjusted[k],
            "bytes_significant": int((adjusted[k] < alpha).sum())}
        for k, h in enumerate(HYPOTHESES)}
    result["family_size"] = int(pvals.size)
    result["byte_classification"] = {
        "round1": classify_bytes(
            z["p_xor_k"], z["p_only"], z["shuffled"],
            adjusted[0], adjusted[1], alpha),
        "lastround": classify_bytes(
            z["lr_c_xor_k10"], z["c_only"], z["lr_shuffled"],
            adjusted[3], adjusted[4], alpha)}
    result["decision"] = _decide(
        {h: {"holm_p_per_byte": adjusted[k], "z_per_byte": z[h]}
         for k, h in enumerate(HYPOTHESES)}, alpha)

    if nperm:                    # calibration of the analytic z (null windows)
        zs = []
        for _ in range(nperm):
            q = rng.permutation(n)
            for (hyp, i), (table, lines) in true_lines.items():
                sets = line_map["tables"][table]["logical_sets"]
                zs.append(hypothesis_score(lines[q], Z[:, sets])[1])
        zs = np.nan_to_num(np.array(zs))
        result["null_calibration"] = {
            "n": int(zs.size), "frac_z_gt_2.33": float((zs > 2.33).mean()),
            "z_sd": float(zs.std())}
    return _clean(result)


# ----------------------------------------------------------------------------
# Markdown summary
# ----------------------------------------------------------------------------


def _fmt(value):
    return "n/a" if value is None else "%.3f" % value


def render_markdown(res):
    run = res["run"]
    out = ["# AES leakage analysis (simulated)", "",
           "Simulator-only run, public key `%s`, plaintext seed %s." % (
               run["key_hex"], run["seed"]),
           "Windows: %d analysed of %d (drop_first=%d); victim `%s`; split %s; "
           "monitor ways %s." % (run["analysed_windows"], run["n_windows"],
                                 run["drop_first"], run["victim_variant"],
                                 run["split"], run["monitor_ways"]),
           "", "## Run checks", "",
           "| check | result | detail |", "|---|---|---|"]
    for c in res["run_checks"]["checks"]:
        out.append("| %s | %s | %s |" % (
            c["name"], "PASS" if c["ok"] else "FAIL",
            c["detail"].replace("|", "/")))
    out += ["", "Rotation %d; %d table lines mapped to distinct logical sets." % (
        res["line_map"]["rotation"], len(res["line_map"]["line_logical_set"]))]
    if res.get("tvla_test"):
        t = res["tvla_test"]
        out += ["", "## TVLA fixed-vs-random (Welch t)", "",
                "fixed=%d random=%d, max |t| = %.2f, sets with |t| > 4.5: %s" % (
                    t["fixed_windows"], t["random_windows"], t["max_abs_t"],
                    t["sets_over_4p5"])]
        return "\n".join(out) + "\n"
    out += ["", "## Attribution (location-aware, known key, Holm over %d tests)"
            % res["family_size"], "",
            "| hypothesis | bytes significant | mean z | min Holm p |",
            "|---|---|---|---|"]
    for h in HYPOTHESES:
        a = res["attribution"][h]
        out.append("| %s | %d/16 | %.2f | %.3g |" % (
            h, a["bytes_significant"], np.mean(a["z_per_byte"]),
            min(a["holm_p_per_byte"])))
    for label, key in (("Round 1 (Te tables, 16 lines)", "round1"),
                       ("Last round (sbox, 4 lines)", "lastround")):
        labels = res["byte_classification"][key]
        counts = {l: labels.count(l) for l in sorted(set(labels))}
        out += ["", "%s per-byte labels: %s" % (label, counts)]
    d = res["decision"]
    out += ["", "## Decision (preregistered rule, alpha = %s)" % d["alpha"], "",
            "| statement | supported | bytes |", "|---|---|---|"]
    for k in ("round1_plaintext_plus_key", "round1_plaintext_only",
              "lastround_c_xor_k10", "lastround_ciphertext_only"):
        out.append("| %s | %s | %s |" % (
            k, "yes" if d[k] else "no", d["supporting_bytes"][k]))
    out += ["", "## Detection (location-free ANOVA; cannot tell p from p^k)", "",
            "| partition | bytes significant |", "|---|---|"]
    for m, v in res["detection"].items():
        out.append("| %s | %d/16 |" % (m, v["bytes_significant"]))
    gt = res.get("ground_truth")
    if gt:
        out += ["", "## Ground truth from the simulator trace", "",
                "Recall %s, precision %s; %d fills in the AES phase, %d outside "
                "it, %d before measurement; mean fills per window %.2f. The "
                "trace records LLC allocations only, so lines that stay "
                "resident in the LLC leave no fill." % (
                    _fmt(gt["recall"]), _fmt(gt["precision"]),
                    gt["fills_in_aes_phase"], gt["fills_outside_aes_phase"],
                    gt["fills_before_measurement"], gt["mean_fills_per_window"])]
    if res.get("null_calibration"):
        c = res["null_calibration"]
        out += ["", "Null calibration: %.3f of %d shuffled z > 2.33 (expect "
                "~0.01), sd %.2f (expect ~1)." % (
                    c["frac_z_gt_2.33"], c["n"], c["z_sd"])]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# Synthetic run directories (rehearsal only -- NOT a model of gem5)
# ----------------------------------------------------------------------------


def _trace_line(tick, line, physical_set):
    return ("%d: %s: victim_fill line=%d set=%d vaddr=%#x paddr=%#x" % (
        tick, PREFIX.rstrip("."), line, physical_set,
        0x14080 + 64 * line, 0x2a000 + 64 * line))


def synth_run(run_dir, key_hex=DEFAULT_KEY_HEX, seed=0x5764A5E5, n=2000,
              rounds1=True, leak="key", delta=40.0, noise=6.0, visibility=1.0,
              rng_seed=1, scrub=True, split="off", ways=16, schedule=None,
              isolation_violation=False):
    """Write a complete fake run directory with a known answer.
    leak: 'key' (round-1 lines follow p^k), 'plaintext' (round-1 lines follow
    p; later rounds still follow the real AES) or 'none' (EVERY round's table
    indices are random, i.e. no data dependence at all).  Returns the ground
    truth used."""
    sched = dict(DEFAULT_SCHEDULE, **(schedule or {}))
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(rng_seed)
    key = hex16(key_hex)
    pt = plaintexts(seed, n)
    rk = key_expansion(key)
    ct, lookups, _ = aes_encrypt_trace(pt, rk)
    model = lookups.copy()
    if leak == "plaintext":
        model[:, 0, :] = pt
    elif leak == "none":
        model = rng.integers(0, 256, model.shape, dtype=np.uint8)
    elif leak != "key":
        raise ValueError("leak must be key, plaintext or none")
    touched = touched_lines(model, rounds1, DEFAULT_LINE_OFFSETS)

    logical = rng.permutation(NSETS)[:N_TABLE_LINES]
    rotation = int(rng.integers(0, NSETS))
    physical = (logical + rotation) % NSETS
    X = 100.0 + noise * rng.normal(size=(n, NSETS))
    visible = rng.random((n, N_TABLE_LINES)) < visibility
    X[:, logical] += delta * (touched & visible)
    latency = np.rint(X).clip(0, None).astype("<u4")

    rec = np.zeros(n * NSETS, dtype=PROBE_DTYPE)
    index = np.arange(n * NSETS)
    rec["interval"] = index // NSETS
    rec["cache_set"] = index % NSETS
    rec["latency"] = latency.reshape(-1)
    rec["timestamp"] = (sched["T0"] + (index // NSETS) * sched["W"] +
                        sched["OFF_PROBE"] + (index % NSETS) * 1100)
    rec.tofile(run_dir / "probes.bin")

    stats = ["---------- Begin Simulation Statistics ----------",
             "simSeconds                                   0.010000   # fake",
             "%sprobeSetRotation %d # fake" % (PREFIX, rotation),
             "%sprobeSetMappingMismatches 0 # fake" % PREFIX]
    for line, value in enumerate(physical):
        stats.append("%svictimTableLineSetPlusOne::%d %d # fake"
                     % (PREFIX, line, value + 1))
    stats += ["%svictimTableLineSetPlusOne::total %d # fake" % (
                  PREFIX, int((physical + 1).sum())),
              "%svictimTableSetMismatches  0 # fake" % PREFIX,
              "%svictimTableMissingVaddr 0 # fake" % PREFIX]
    if split != "off":                 # way occupancy inside the assigned ways
        monitor_ways = int(split.split("-")[0])
        for way in range(NWAYS):
            stats.append("%swayOccupancy::p%d::way%d %d # fake" % (
                PREFIX, 0 if way < monitor_ways else 1, way, 40))
        if isolation_violation:        # a monitor block in an AES way
            stats.append("%swayOccupancy::p0::way%d 3 # injected violation" % (
                PREFIX, monitor_ways))
    stats += ["", "---------- End Simulation Statistics   ----------", "",
              "---------- Begin Simulation Statistics ----------",
              "%sprobeSetRotation %d # second block must be ignored" % (
                  PREFIX, (rotation + 7) % NSETS),
              "---------- End Simulation Statistics   ----------"]
    (run_dir / "stats.txt").write_text("\n".join(stats) + "\n")

    ct_sum = "00" * 16 if rounds1 else fold(ct)
    sim = ["victim aes_self_test=PASS",
           "victim leak_format=v1 key=%s seed=%d windows=%d rounds1=%d "
           "scrub=%d tvla=0" % (key_hex, seed, n, int(rounds1), int(scrub)),
           "monitor format=probe_bin_v2 windows=%d sets=256 ways=%d" % (n, ways),
           "victim pt_checksum=%s ct_checksum=%s" % (fold(pt), ct_sum),
           "monitor status=PASS records=%d" % (n * NSETS)]
    (run_dir / "simout.txt").write_text("\n".join(sim) + "\n")

    cfg = {
        "format": "aes-leakage-config-v1", "key_hex": key_hex,
        "workload_seed": seed, "N_WIN": n, "T0": sched["T0"], "W": sched["W"],
        "OFF_PRIME": sched["OFF_PRIME"], "OFF_ENC": sched["OFF_ENC"],
        "OFF_ENC_END": sched["OFF_ENC_END"], "OFF_PROBE": sched["OFF_PROBE"],
        "victim_variant": "r1-scrub" if rounds1 else "full-scrub",
        "rounds1": int(rounds1), "scrub": int(scrub), "tvla": 0,
        "split": split, "monitor_ways": ways, "synthetic": True,
        "trace_range": {"base": 0x14080, "size": N_TABLE_LINES * 64,
                        "n_lines": N_TABLE_LINES},
        "tables": {t: {"line_offset": DEFAULT_LINE_OFFSETS[t],
                       "lines": TABLE_LINES[t],
                       "addr": 0x14080 + 64 * DEFAULT_LINE_OFFSETS[t]}
                   for t in TABLES},
    }
    (run_dir / "leak_config.json").write_text(json.dumps(cfg, indent=2) + "\n")

    trace = []
    for line in range(N_TABLE_LINES):                       # table init (warm-up)
        trace.append(_trace_line((sched["T0"] - 500_000 + line) * TICKS_PER_CYCLE,
                                 line, int(physical[line])))
    windows, lines = np.nonzero(touched)
    for k, (window, line) in enumerate(zip(windows.tolist(), lines.tolist())):
        cycle = sched["T0"] + window * sched["W"] + sched["OFF_ENC"] + 100 + \
            (k % 400) * 7
        trace.append(_trace_line(cycle * TICKS_PER_CYCLE, line,
                                 int(physical[line])))
    (run_dir / "victim_table.trace").write_text("\n".join(trace) + "\n")
    return {"line_logical_set": logical.tolist(),
            "line_physical_set": physical.tolist(), "rotation": rotation,
            "touched": touched}


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------


def cmd_selftest(args):
    ok = True
    # FIPS-197 Appendix C.1
    key = hex16("000102030405060708090a0b0c0d0e0f")
    pt = hex16("00112233445566778899aabbccddeeff")[None, :]
    ct = aes_encrypt_trace(pt, key_expansion(key))[0][0]
    good = bytes(ct).hex() == "69c4e0d86a7b0430d8cdb78070b4c55a"
    print("AES FIPS-197 C.1  :", "PASS" if good else "FAIL %s" % bytes(ct).hex())
    ok &= good
    # FIPS-197 Appendix A.1 last round key
    k = hex16("2b7e151628aed2a6abf7158809cf4f3c")
    good = bytes(key_expansion(k)[10]).hex() == "d014f9a8c9ee2589e13f0cc8b6630ca6"
    print("Key expansion A.1 :", "PASS" if good else "FAIL")
    ok &= good
    # splitmix64 reference values (also checked against the C header by tests)
    g = splitmix64_stream(0)
    v = [next(g) for _ in range(2)]
    good = v == [0xE220A8397B1DCDAF, 0x6E789E6AA1B965F4]
    print("splitmix64 seed 0 :", "PASS" if good else "FAIL %s" % [hex(x) for x in v])
    ok &= good
    # End-to-end on synthetic run directories (key with nonzero upper nibbles)
    for rounds1, n in ((True, 1500), (False, 3000)):
        with tempfile.TemporaryDirectory(prefix="aesleak-selftest-") as tmp:
            synth_run(Path(tmp) / "run", n=n, rounds1=rounds1)
            res = analyze_run_dir(Path(tmp) / "run", nperm=3)
        at, dec = res["attribution"], res["decision"]
        cond = (at["p_xor_k"]["bytes_significant"] == 16 and
                at["p_only"]["bytes_significant"] == 0 and
                at["shuffled"]["bytes_significant"] == 0 and
                at["lr_shuffled"]["bytes_significant"] == 0 and
                dec["round1_plaintext_plus_key"] and
                not dec["round1_plaintext_only"] and
                res["run_checks"]["all_passed"] and
                res["null_calibration"]["frac_z_gt_2.33"] < 0.05)
        if rounds1:        # no last-round lookups exist: that family must be null
            cond &= at["lr_c_xor_k10"]["bytes_significant"] == 0
        print("synthetic %-6s N=%d: p^k %d/16, p_only %d/16, shuffled %d/16, "
              "last round %d/16, null z>2.33 frac %.3f -> %s" % (
                  "round1" if rounds1 else "full", n,
                  at["p_xor_k"]["bytes_significant"],
                  at["p_only"]["bytes_significant"],
                  at["shuffled"]["bytes_significant"],
                  at["lr_c_xor_k10"]["bytes_significant"],
                  res["null_calibration"]["frac_z_gt_2.33"],
                  "PASS" if cond else "FAIL"))
        ok &= cond
    print("\nSELFTEST", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)


def cmd_synth(args):
    synth_run(args.run_dir, key_hex=args.key, seed=args.seed, n=args.n,
              rounds1=not args.full, leak=args.leak, delta=args.delta,
              noise=args.noise, visibility=args.visibility,
              rng_seed=args.rng_seed)
    print("wrote synthetic run directory %s (%d windows, %s, leak=%s)" % (
        args.run_dir, args.n, "full AES" if args.full else "round 1 only",
        args.leak))


def cmd_analyze(args):
    try:
        res = analyze_run_dir(args.run_dir, nperm=args.nperm,
                              drop_first=args.drop_first)
    except AnalysisError as exc:
        print("ERROR: %s" % exc)
        sys.exit(2)
    text = render_markdown(res)
    print(text)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(res, indent=1) + "\n")
        print("wrote", args.out_json)
    if args.out_md:
        Path(args.out_md).write_text(text)
        print("wrote", args.out_md)
    if not res["run_checks"]["all_passed"]:
        print("RUN CHECKS: FAIL")
        sys.exit(1)
    print("RUN CHECKS: PASS")


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("selftest")
    sp.set_defaults(f=cmd_selftest)

    sp = sub.add_parser("synth", help="write a fake run directory")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--n", type=int, default=2000)
    sp.add_argument("--key", default=DEFAULT_KEY_HEX)
    sp.add_argument("--seed", type=lambda s: int(s, 0), default=0x5764A5E5)
    sp.add_argument("--full", action="store_true",
                    help="full AES (default: round-1 lookups only)")
    sp.add_argument("--leak", choices=["key", "plaintext", "none"], default="key")
    sp.add_argument("--delta", type=float, default=40.0)
    sp.add_argument("--noise", type=float, default=6.0)
    sp.add_argument("--visibility", type=float, default=1.0)
    sp.add_argument("--rng-seed", type=int, default=1)
    sp.set_defaults(f=cmd_synth)

    sp = sub.add_parser("analyze", help="analyse a run directory")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--nperm", type=int, default=0,
                    help="window shuffles for null calibration (e.g. 20)")
    sp.add_argument("--drop-first", type=int, default=0,
                    help="warm-up windows to discard")
    sp.add_argument("--out-json")
    sp.add_argument("--out-md")
    sp.set_defaults(f=cmd_analyze)

    args = p.parse_args()
    args.f(args)


if __name__ == "__main__":
    main()
