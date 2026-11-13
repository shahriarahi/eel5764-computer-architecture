"""Shared read-only helpers for the postdoc-review verification scripts.

Nothing here writes outside postdoc-review/verify/.  The experiment's own
analysis module is imported read-only (run every script with `python3 -B` so
that no __pycache__ is written into the experiment directory).
"""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True

VERIFY = Path(__file__).resolve().parent
ROOT = VERIFY.parents[1]
WORKTREE = ROOT / ".codex-tmp" / "aes-leakage-worktree"
EXP = WORKTREE / "experiments" / "aes-leakage"
RESULTS = ROOT / "results" / "updated run"
TMP = VERIFY / "_tmp"

sys.path.insert(0, str(EXP / "analysis"))
sys.path.insert(0, str(EXP))
import aes_leak_analysis as A  # noqa: E402

import numpy as np  # noqa: E402


def load_run(run_dir):
    """Latency matrix, config, line map, plaintexts, ciphertexts, lookups."""
    run_dir = Path(run_dir)
    cfg = json.loads((run_dir / "leak_config.json").read_text())
    n = int(cfg["N_WIN"])
    X = A.read_probes(run_dir / "probes.bin", n)
    scalars, vectors = A.parse_first_stats_block(
        (run_dir / "stats.txt").read_text())
    line_map = A.build_line_map(scalars, vectors, cfg)
    key = A.hex16(cfg["key_hex"])
    rk = A.key_expansion(key)
    pt = A.plaintexts(cfg["workload_seed"], n)
    ct, lookups, _ = A.aes_encrypt_trace(pt, rk)
    offsets = {t: cfg["tables"][t]["line_offset"] for t in A.TABLES}
    touched = A.touched_lines(lookups, bool(cfg["rounds1"]), offsets)
    return {"cfg": cfg, "n": n, "X": X, "line_map": line_map, "key": key,
            "rk": rk, "pt": pt, "ct": ct, "lookups": lookups,
            "offsets": offsets, "touched": touched}


def attribution(X, pt, ct, key, rk10, line_map, seed=5764, alpha=0.05):
    """Same computation as analyze_run_dir() section (B): standardize, score
    the six hypotheses for 16 bytes, Holm over 96 tests, decision rule."""
    from scipy.stats import norm
    rng = np.random.default_rng(seed)
    n = len(X)
    rng.permutation(n)                      # the detection shuffle draw
    Z = A.standardize(X)
    z = {h: np.zeros(16) for h in A.HYPOTHESES}
    score = {h: np.zeros(16) for h in A.HYPOTHESES}
    for i in range(16):
        perm = rng.permutation(n)
        for hyp in A.HYPOTHESES:
            table, lines = A.predicted_lines(hyp, i, pt, ct, key, rk10, perm)
            sets = line_map["tables"][table]["logical_sets"]
            score[hyp][i], z[hyp][i] = A.hypothesis_score(lines, Z[:, sets])
    z = {h: np.nan_to_num(v, nan=0.0) for h, v in z.items()}
    pvals = np.concatenate([norm.sf(z[h]) for h in A.HYPOTHESES])
    adjusted = A.holm(pvals).reshape(len(A.HYPOTHESES), 16)
    decision = A._decide(
        {h: {"holm_p_per_byte": adjusted[k], "z_per_byte": z[h]}
         for k, h in enumerate(A.HYPOTHESES)}, alpha)
    sig = {h: int((adjusted[k] < alpha).sum())
           for k, h in enumerate(A.HYPOTHESES)}
    return {"z": z, "score": score, "sig": sig, "decision": decision}


def raw_effect(X, lines, sets):
    """Unstandardized effect in CPU cycles: mean over table lines of
    [mean latency of the line's set when predicted - when not predicted]."""
    diffs = []
    for l, s in enumerate(sets):
        inside = lines == l
        if inside.any() and (~inside).any():
            diffs.append(X[inside, s].mean() - X[~inside, s].mean())
    return float(np.mean(diffs)) if diffs else float("nan")


def synthetic_line_map(rng):
    """A line map shaped like build_line_map()'s, for array-only synthetics."""
    logical = rng.permutation(A.NSETS)[:A.N_TABLE_LINES]
    tables = {}
    for name in A.TABLES:
        off = A.DEFAULT_LINE_OFFSETS[name]
        tables[name] = {"line_offset": off,
                        "logical_sets": logical[off:off + A.TABLE_LINES[name]]
                        .tolist()}
    return {"tables": tables, "line_logical_set": logical.tolist()}
