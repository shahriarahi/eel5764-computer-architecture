#!/usr/bin/env python3
"""
leak_followup.py -- three additions to the AES leakage analysis (deviations
D1 to D3 of PREREGISTRATION_DRAFT.md).  SIMULATOR ONLY, public key.

The analysis uses the known public key.  It never searches for a key and it
does not score, rank or guess key bytes.

Subcommands
  diff    Differential (non-interference) test.  Two runs of the SAME arm that
          differ only in the public plaintext seed.  gem5 is deterministic, so
          if the monitor's probe log is byte-identical for two different
          plaintext streams, the monitor's observation did not depend on the
          encrypted data for those streams.  No statistics are involved.
  effect  Raw-cycle effect size of the six registered hypotheses (CPU cycles
          per set walk and per probed line), a 10,000-shuffle permutation
          p-value (seed 5764) in place of the normal approximation, a
          materiality margin, the slow-versus-touched confusion table, and the
          fraction of a reference run's effect that is retained.
  count   Location-free collision-count test for the overlap (contention)
          schedule: does the monitor's delay in a window follow the NUMBER of
          distinct table lines the encryption uses?

Requires numpy and scipy (through aes_leak_analysis).  Never writes into a run
directory.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aes_leak_analysis as A  # noqa: E402

NPERM = 10_000                 # the proposal's permutation count
PERM_SEED = 5764               # the proposal's analysis seed
ALPHA = 0.05
MARGIN_PER_LINE = 0.02         # cycles per probed line (the paper's margin)
SLOW_CYCLES = 100              # a walk this far above its set's fastest time
                               # contains an LLC miss (the paper's gate)
SCHEDULE_KEYS = ("T0", "W", "OFF_PRIME", "OFF_ENC", "OFF_ENC_END", "OFF_PROBE")
_PROBE_PATH = re.compile(r'"(/[^"]*/probes\.bin)"')


class FollowupError(Exception):
    """The comparison or analysis cannot be made (not a result)."""


def require_perms(nperm, n_tests, alpha):
    """With P shuffles the smallest p-value is 1/(P+1); after Holm over
    n_tests it must still be able to fall below alpha."""
    if n_tests / (nperm + 1.0) >= alpha:
        raise FollowupError(
            "--nperm %d is too small: Holm over %d tests at alpha %s needs "
            "more than %d shuffles" % (nperm, n_tests, alpha,
                                       int(n_tests / alpha)))


# ----------------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------------


def load_run(run_dir, need_line_map=True):
    run_dir = Path(run_dir)
    for name in ("leak_config.json", "probes.bin", "simout.txt", "stats.txt"):
        if not (run_dir / name).is_file():
            raise FollowupError("%s is missing from %s" % (name, run_dir))
    cfg = json.loads((run_dir / "leak_config.json").read_text())
    n = int(cfg["N_WIN"])
    raw = (run_dir / "probes.bin").read_bytes()
    try:
        X = A.read_probes(run_dir / "probes.bin", n)
    except A.AnalysisError as exc:
        raise FollowupError(str(exc)) from exc
    rec = np.frombuffer(raw, dtype=A.PROBE_DTYPE)
    sim = A.parse_simout((run_dir / "simout.txt").read_text())
    line_map = None
    if need_line_map:
        scalars, vectors = A.parse_first_stats_block(
            (run_dir / "stats.txt").read_text())
        try:
            line_map = A.build_line_map(scalars, vectors, cfg)
        except A.AnalysisError as exc:
            raise FollowupError(str(exc)) from exc
    key = A.hex16(cfg["key_hex"])
    rk = A.key_expansion(key)
    fixed = A.hex16(A.TVLA_FIXED_PT_HEX) if cfg.get("tvla") else None
    pt = A.plaintexts(cfg["workload_seed"], n, tvla_fixed=fixed)
    ct, lookups, _ = A.aes_encrypt_trace(pt, rk)
    probe_path = None
    config_json = run_dir / "config.json"
    if config_json.is_file():
        match = _PROBE_PATH.search(config_json.read_text())
        probe_path = match.group(1) if match else None
    return {"dir": run_dir, "cfg": cfg, "n": n, "raw": raw, "rec": rec, "X": X,
            "TS": rec["timestamp"].reshape(n, A.NSETS).astype(np.int64),
            "sim": sim, "line_map": line_map, "key": key, "rk": rk, "pt": pt,
            "ct": ct, "lookups": lookups, "probe_path": probe_path}


def run_health(run):
    """Problems that make a run unusable (empty list = healthy)."""
    sim, n = run["sim"], run["n"]
    problems = []
    if not sim["self_test_pass"]:
        problems.append("no AES self-test PASS line")
    if sim["errors"]:
        problems.append("error lines: %s" % sim["errors"])
    if sim["monitor_records"] != n * A.NSETS:
        problems.append("monitor records %s, expected %d" % (
            sim["monitor_records"], n * A.NSETS))
    return problems


# ----------------------------------------------------------------------------
# diff: differential (non-interference) test
# ----------------------------------------------------------------------------


def diff_runs(dir_a, dir_b, allow_same_seed=False):
    a = load_run(dir_a, need_line_map=False)
    b = load_run(dir_b, need_line_map=False)
    ca, cb = a["cfg"], b["cfg"]
    problems = []
    for label, run in (("A", a), ("B", b)):
        problems += ["run %s: %s" % (label, p) for p in run_health(run)]
    for field in ("N_WIN", "key_hex", "victim_variant", "split", "monitor_ways",
                  "rounds1", "scrub", "tvla") + SCHEDULE_KEYS:
        if ca.get(field) != cb.get(field):
            problems.append("%s differs: %r vs %r" % (field, ca.get(field),
                                                      cb.get(field)))
    for role in ("victim", "monitor"):
        if ca["binaries"][role]["sha256"] != cb["binaries"][role]["sha256"]:
            problems.append("%s binary differs between the runs" % role)
    if ca.get("build_dir") != cb.get("build_dir"):
        problems.append("build_dir differs (argv[0] of both workloads would "
                        "differ): %r vs %r" % (ca.get("build_dir"),
                                               cb.get("build_dir")))
    same_seed = ca["workload_seed"] == cb["workload_seed"]
    if same_seed and not allow_same_seed:
        problems.append("both runs use seed %d; a differential test needs two "
                        "different plaintext seeds (--allow-same-seed is for "
                        "reproducibility guards only)" % ca["workload_seed"])
    if len(str(ca["workload_seed"])) != len(str(cb["workload_seed"])):
        problems.append("the seeds have different decimal lengths, which "
                        "shifts the victim's stack")
    if a["probe_path"] is None or b["probe_path"] is None:
        problems.append("config.json with the probe path is missing")
    elif len(a["probe_path"]) != len(b["probe_path"]):
        problems.append("probe path lengths differ (%d vs %d): the monitor's "
                        "stack would be shifted" % (len(a["probe_path"]),
                                                    len(b["probe_path"])))
    inputs_differ = a["sim"]["pt_checksum"] != b["sim"]["pt_checksum"]
    if not same_seed and not inputs_differ:
        problems.append("the victims report the same plaintext checksum, so "
                        "they did not encrypt different data")

    ra, rb = a["rec"], b["rec"]
    result = {
        "a": str(dir_a), "b": str(dir_b),
        "seed_a": ca["workload_seed"], "seed_b": cb["workload_seed"],
        "n_windows": a["n"], "split": ca.get("split"),
        "monitor_ways": ca.get("monitor_ways"),
        "victim_variant": ca.get("victim_variant"),
        "schedule": {k: ca.get(k) for k in SCHEDULE_KEYS},
        "victim_inputs_differ": bool(inputs_differ),
        "sha256_a": hashlib.sha256(a["raw"]).hexdigest(),
        "sha256_b": hashlib.sha256(b["raw"]).hexdigest(),
        "preconditions_ok": not problems, "problems": problems,
    }
    if len(ra) == len(rb):
        lat = ra["latency"] != rb["latency"]
        ts = ra["timestamp"] != rb["timestamp"]
        delta = np.abs(ra["latency"].astype(np.int64) -
                       rb["latency"].astype(np.int64))
        result.update({
            "n_records": int(len(ra)),
            "file_identical": a["raw"] == b["raw"],
            "latency_records_differing": int(lat.sum()),
            "timestamp_records_differing": int(ts.sum()),
            "windows_with_latency_difference":
                int(lat.reshape(a["n"], A.NSETS).any(1).sum()),
            "sets_with_latency_difference":
                int(lat.reshape(a["n"], A.NSETS).any(0).sum()),
            "max_abs_latency_difference": int(delta.max()) if len(ra) else 0,
        })
        if result["file_identical"]:
            verdict = "IDENTICAL"
        elif not lat.any():
            verdict = "LATENCY_IDENTICAL"
        else:
            verdict = "DIFFERENT"
    else:
        verdict = "DIFFERENT"
        result["file_identical"] = False
    result["verdict"] = verdict if not problems else "INVALID"
    return result


def render_diff(res):
    out = ["# Differential test (simulated)", "",
           "A: `%s` (seed %s)" % (res["a"], res["seed_a"]),
           "B: `%s` (seed %s)" % (res["b"], res["seed_b"]),
           "Arm: victim `%s`, split %s, monitor ways %s, %s windows, "
           "OFF_PROBE %s." % (res["victim_variant"], res["split"],
                              res["monitor_ways"], res["n_windows"],
                              res["schedule"]["OFF_PROBE"]), ""]
    if res["problems"]:
        out += ["Preconditions FAILED:"] + ["* " + p for p in res["problems"]]
    else:
        out += ["Preconditions: PASS (same binaries, arm, schedule and path "
                "lengths; the victims encrypted different data: %s)." %
                res["victim_inputs_differ"]]
    if "n_records" in res:
        out += ["", "| quantity | value |", "|---|---|",
                "| probes.bin byte-identical | %s |" % res["file_identical"],
                "| records | %d |" % res["n_records"],
                "| records whose latency differs | %d |" %
                res["latency_records_differing"],
                "| records whose timestamp differs | %d |" %
                res["timestamp_records_differing"],
                "| windows with a latency difference | %d |" %
                res["windows_with_latency_difference"],
                "| sets with a latency difference | %d |" %
                res["sets_with_latency_difference"],
                "| largest latency difference (cycles) | %d |" %
                res["max_abs_latency_difference"]]
    out += ["", "sha256 A `%s`" % res["sha256_a"],
            "sha256 B `%s`" % res["sha256_b"], "",
            "DIFF VERDICT: %s" % res["verdict"]]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# effect: raw-cycle effect size with a permutation p-value
# ----------------------------------------------------------------------------


def raw_effect(lines, Xs):
    """Mean over table lines l of [mean latency of l's set in the windows where
    the hypothesis predicts l - mean in the other windows], in CPU cycles per
    set walk.  lines: (N,) ints in [0, L); Xs: (N, L) raw latencies."""
    n, n_lines = Xs.shape
    cnt = np.bincount(lines, minlength=n_lines).astype(float)
    valid = (cnt > 0) & (cnt < n)
    if not valid.any():
        return float("nan")
    s_in = np.bincount(lines, weights=Xs[np.arange(n), lines],
                       minlength=n_lines)
    tot = Xs.sum(0)
    diff = s_in[valid] / cnt[valid] - (tot[valid] - s_in[valid]) / (n - cnt[valid])
    return float(diff.mean())


def permutation_p(lines, Xs, perms):
    """One-sided p-value of raw_effect under shuffling of the windows.
    perms: (P, N) array of permutations shared by all tests of a run."""
    obs = raw_effect(lines, Xs)
    if obs != obs:
        return obs, 1.0
    n, n_lines = Xs.shape
    cnt = np.bincount(lines, minlength=n_lines).astype(float)
    valid = (cnt > 0) & (cnt < n)
    tot = Xs.sum(0)
    hits = 0
    for perm in perms:
        shuffled = lines[perm]
        s_in = np.bincount(shuffled, weights=Xs[np.arange(n), shuffled],
                           minlength=n_lines)
        diff = (s_in[valid] / cnt[valid] -
                (tot[valid] - s_in[valid]) / (n - cnt[valid]))
        hits += diff.mean() >= obs
    return obs, (1 + int(hits)) / (len(perms) + 1)


def confusion(run):
    """Slow-versus-touched table over the 68 table-line sets.  A walk is slow
    if it exceeds its set's fastest walk by SLOW_CYCLES or more."""
    cfg = run["cfg"]
    offsets = {t: (cfg.get("tables") or {}).get(t, {}).get(
        "line_offset", A.DEFAULT_LINE_OFFSETS[t]) for t in A.TABLES}
    touched = A.touched_lines(run["lookups"], bool(cfg["rounds1"]), offsets)
    sets = np.array(run["line_map"]["line_logical_set"])
    L = run["X"][:, sets]
    slow = L >= L.min(0) + SLOW_CYCLES
    return {"touched_slow": int((slow & touched).sum()),
            "touched_fast": int((~slow & touched).sum()),
            "untouched_slow": int((slow & ~touched).sum()),
            "untouched_fast": int((~slow & ~touched).sum()),
            "cells": int(touched.size),
            "exact_indicator": bool((slow == touched).all())}


def mean_effect_per_probed_line(run_dir, hyp):
    """Mean raw effect of one hypothesis over the 16 bytes, in cycles per
    probed line (no p-values; used for the reference run)."""
    run = load_run(run_dir)
    n = run["n"]
    values = []
    for i in range(16):
        table, lines = A.predicted_lines(hyp, i, run["pt"], run["ct"],
                                         run["key"], run["rk"][10],
                                         np.arange(n))
        sets = run["line_map"]["tables"][table]["logical_sets"]
        values.append(raw_effect(lines, run["X"][:, sets]))
    return float(np.nan_to_num(np.array(values)).mean() /
                 int(run["cfg"]["monitor_ways"]))


def effect_run(run_dir, nperm=NPERM, seed=PERM_SEED, alpha=ALPHA,
               margin=MARGIN_PER_LINE, reference=None):
    require_perms(nperm, 6 * 16, alpha)
    run = load_run(run_dir)
    cfg, n, X = run["cfg"], run["n"], run["X"]
    ways = int(cfg["monitor_ways"])
    rng = np.random.default_rng(seed)
    perms = np.array([rng.permutation(n) for _ in range(nperm)])
    label_rng = np.random.default_rng(seed + 1)
    eff = {h: np.zeros(16) for h in A.HYPOTHESES}
    pval = {h: np.ones(16) for h in A.HYPOTHESES}
    for i in range(16):
        shuffle = label_rng.permutation(n)
        for hyp in A.HYPOTHESES:
            table, lines = A.predicted_lines(hyp, i, run["pt"], run["ct"],
                                             run["key"], run["rk"][10], shuffle)
            sets = run["line_map"]["tables"][table]["logical_sets"]
            eff[hyp][i], pval[hyp][i] = permutation_p(lines, X[:, sets], perms)
    eff = {h: np.nan_to_num(v, nan=0.0) for h, v in eff.items()}
    adjusted = A.holm(np.concatenate([pval[h] for h in A.HYPOTHESES])
                      ).reshape(len(A.HYPOTHESES), 16)
    adj = {h: adjusted[k] for k, h in enumerate(A.HYPOTHESES)}

    def supported(main, other, shuffled):
        return [i for i in range(16)
                if adj[main][i] < alpha and
                eff[main][i] > eff[other][i] and
                eff[main][i] > eff[shuffled][i] and
                eff[main][i] / ways >= margin]

    statements = {
        "round1_plaintext_plus_key": supported("p_xor_k", "p_only", "shuffled"),
        "round1_plaintext_only": supported("p_only", "p_xor_k", "shuffled"),
        "lastround_c_xor_k10": supported("lr_c_xor_k10", "c_only",
                                         "lr_shuffled"),
        "lastround_ciphertext_only": supported("c_only", "lr_c_xor_k10",
                                               "lr_shuffled"),
    }
    result = {
        "run": {"dir": str(run_dir), "n_windows": n, "seed": cfg["workload_seed"],
                "victim_variant": cfg.get("victim_variant"),
                "split": cfg.get("split"), "monitor_ways": ways},
        "health_problems": run_health(run),
        "nperm": nperm, "perm_seed": seed, "alpha": alpha,
        "margin_cycles_per_probed_line": margin,
        "smallest_possible_p": 1.0 / (nperm + 1),
        "hypotheses": {h: {
            "effect_cycles_per_set_walk": np.round(eff[h], 4).tolist(),
            "mean_effect_cycles_per_set_walk": float(eff[h].mean()),
            "mean_effect_cycles_per_probed_line": float(eff[h].mean() / ways),
            "holm_p_per_byte": adj[h].tolist(),
            "bytes_significant": int((adj[h] < alpha).sum()),
            "bytes_significant_and_material": int(
                ((adj[h] < alpha) & (eff[h] / ways >= margin)).sum())}
            for h in A.HYPOTHESES},
        "decision": {k: bool(v) for k, v in statements.items()},
        "supporting_bytes": statements,
        "confusion": confusion(run),
        "retained": None,
    }
    if reference is not None:
        out = {}
        for h in ("p_xor_k", "lr_c_xor_k10"):
            base = mean_effect_per_probed_line(reference, h)
            mine = result["hypotheses"][h]["mean_effect_cycles_per_probed_line"]
            out[h] = {"reference_cycles_per_probed_line": base,
                      "this_run_cycles_per_probed_line": mine,
                      "fraction_retained": (mine / base) if base else None}
        result["retained"] = {"reference": str(reference), "values": out}
    return result


def render_effect(res):
    run = res["run"]
    out = ["# Raw-cycle effect size (simulated)", "",
           "Run `%s`: victim `%s`, split %s, monitor ways %s, %d windows, "
           "seed %s." % (run["dir"], run["victim_variant"], run["split"],
                         run["monitor_ways"], run["n_windows"], run["seed"]),
           "Permutation p-values: %d window shuffles, seed %d (smallest "
           "possible p %.6f); Holm over 96 tests; alpha %s; materiality margin "
           "%s cycles per probed line." % (
               res["nperm"], res["perm_seed"], res["smallest_possible_p"],
               res["alpha"], res["margin_cycles_per_probed_line"]), ""]
    if res["health_problems"]:
        out += ["RUN HEALTH: FAIL %s" % res["health_problems"], ""]
    out += ["| hypothesis | mean effect (cycles per set walk) | per probed "
            "line | bytes significant | significant and material |",
            "|---|---|---|---|---|"]
    for h in A.HYPOTHESES:
        v = res["hypotheses"][h]
        out.append("| %s | %.3f | %.4f | %d/16 | %d/16 |" % (
            h, v["mean_effect_cycles_per_set_walk"],
            v["mean_effect_cycles_per_probed_line"], v["bytes_significant"],
            v["bytes_significant_and_material"]))
    out += ["", "| statement (significant, beats its alternative and its "
            "shuffled control, and material) | supported | bytes |",
            "|---|---|---|"]
    for k, v in res["decision"].items():
        out.append("| %s | %s | %s |" % (k, "yes" if v else "no",
                                         res["supporting_bytes"][k]))
    c = res["confusion"]
    out += ["", "Slow-versus-touched over the 68 table-line sets: touched and "
            "slow %d, touched and fast %d, untouched and slow %d, untouched "
            "and fast %d (%d cells); exact indicator: %s." % (
                c["touched_slow"], c["touched_fast"], c["untouched_slow"],
                c["untouched_fast"], c["cells"], c["exact_indicator"])]
    if res["retained"]:
        out += ["", "Against reference `%s`:" % res["retained"]["reference"]]
        for h, v in res["retained"]["values"].items():
            frac = v["fraction_retained"]
            out.append("* %s: %.4f of %.4f cycles per probed line retained "
                       "(%s)" % (h, v["this_run_cycles_per_probed_line"],
                                 v["reference_cycles_per_probed_line"],
                                 "n/a" if frac is None else "%.4f" % frac))
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# count: location-free collision-count test (overlap schedule)
# ----------------------------------------------------------------------------


def distinct_line_counts(run):
    """Per-window number of distinct table lines, for three fixed models."""
    cfg = run["cfg"]
    rounds1 = bool(cfg["rounds1"])
    off = A.DEFAULT_LINE_OFFSETS
    real = A.touched_lines(run["lookups"], rounds1, off).sum(1)
    r1 = A.touched_lines(run["lookups"], True, off).sum(1)
    keyfree = run["lookups"].copy()
    keyfree[:, 0, :] = run["pt"]            # round-1 indices WITHOUT the key
    r1_p = A.touched_lines(keyfree, True, off).sum(1)
    return {"lines_all_rounds": real.astype(float),
            "lines_round1_p_xor_k": r1.astype(float),
            "lines_round1_p_only": r1_p.astype(float)}


def _corr_perm(model, feature, perms):
    if model.std() == 0 or feature.std() == 0:
        return 0.0, 1.0
    x = (model - model.mean()) / model.std()
    y = (feature - feature.mean()) / feature.std()
    obs = float((x * y).mean())
    hits = sum(abs(float((x[p] * y).mean())) >= abs(obs) for p in perms)
    return obs, (1 + int(hits)) / (len(perms) + 1)


def count_run(run_dir, nperm=NPERM, seed=PERM_SEED, alpha=ALPHA):
    require_perms(nperm, 8, alpha)
    run = load_run(run_dir, need_line_map=False)
    n, X = run["n"], run["X"]
    base = np.median(X, axis=0)
    features = {"excess_cycles": (X - base).sum(1),
                "delayed_walks": (X > base).sum(1).astype(float)}
    models = distinct_line_counts(run)
    rng = np.random.default_rng(seed)
    models["shuffled"] = models["lines_all_rounds"][rng.permutation(n)]
    perms = np.array([rng.permutation(n) for _ in range(nperm)])
    names = [(m, f) for m in models for f in features]
    r, p = {}, {}
    for m, f in names:
        r[(m, f)], p[(m, f)] = _corr_perm(models[m], features[f], perms)
    adjusted = A.holm(np.array([p[k] for k in names]))
    adj = {k: float(adjusted[i]) for i, k in enumerate(names)}

    def sig(model):
        return [f for f in features
                if adj[(model, f)] < alpha and
                abs(r[(model, f)]) > abs(r[("shuffled", f)])]

    key_dep = [f for f in sig("lines_round1_p_xor_k")
               if abs(r[("lines_round1_p_xor_k", f)]) >
               abs(r[("lines_round1_p_only", f)])]
    key_free = [f for f in sig("lines_round1_p_only")
                if abs(r[("lines_round1_p_only", f)]) >
                abs(r[("lines_round1_p_xor_k", f)])]
    cfg = run["cfg"]
    return {
        "run": {"dir": str(run_dir), "n_windows": n, "seed": cfg["workload_seed"],
                "victim_variant": cfg.get("victim_variant"),
                "split": cfg.get("split"),
                "monitor_ways": cfg.get("monitor_ways"),
                "OFF_PROBE": cfg.get("OFF_PROBE"), "OFF_ENC": cfg.get("OFF_ENC")},
        "health_problems": run_health(run),
        "overlap_schedule": bool(cfg.get("OFF_PROBE", 0) < cfg.get("OFF_ENC_END", 0)),
        "nperm": nperm, "perm_seed": seed, "alpha": alpha,
        "feature_summary": {f: {"mean": float(v.mean()), "sd": float(v.std()),
                                "max": float(v.max())}
                            for f, v in features.items()},
        "model_summary": {m: {"mean": float(v.mean()), "sd": float(v.std())}
                          for m, v in models.items()},
        "tests": [{"model": m, "feature": f, "r": r[(m, f)],
                   "holm_p": adj[(m, f)]} for m, f in names],
        "round1_statements_registered": bool(cfg["rounds1"]),
        "decision": {"count_dependent": bool(sig("lines_all_rounds")),
                     "round1_count_plaintext_plus_key": bool(key_dep),
                     "round1_count_plaintext_only": bool(key_free)},
    }


def render_count(res):
    run = res["run"]
    out = ["# Collision-count test, location-free (simulated)", "",
           "Run `%s`: victim `%s`, split %s, monitor ways %s, %d windows, "
           "seed %s; overlap schedule: %s (OFF_PROBE %s, OFF_ENC %s)." % (
               run["dir"], run["victim_variant"], run["split"],
               run["monitor_ways"], run["n_windows"], run["seed"],
               res["overlap_schedule"], run["OFF_PROBE"], run["OFF_ENC"]),
           "Pearson r between a per-window model count and a per-window "
           "monitor feature; two-sided permutation p (%d shuffles, seed %d), "
           "Holm over %d tests." % (res["nperm"], res["perm_seed"],
                                    len(res["tests"])), ""]
    if res["health_problems"]:
        out += ["RUN HEALTH: FAIL %s" % res["health_problems"], ""]
    out += ["| feature | mean | sd | max |", "|---|---|---|---|"]
    for f, v in res["feature_summary"].items():
        out.append("| %s | %.3f | %.3f | %.1f |" % (f, v["mean"], v["sd"],
                                                    v["max"]))
    out += ["", "| model | feature | r | Holm p |", "|---|---|---|---|"]
    for t in res["tests"]:
        out.append("| %s | %s | %+.4f | %.4g |" % (t["model"], t["feature"],
                                                   t["r"], t["holm_p"]))
    out += ["", "| statement | supported |", "|---|---|"]
    for k, v in res["decision"].items():
        out.append("| %s | %s |" % (k, "yes" if v else "no"))
    if not res["round1_statements_registered"]:
        out += ["", "This is a full-AES run: round 1 supplies only about a "
                "quarter of the distinct lines, so the two round-1 statements "
                "are low-power here and are registered for the round-1-only "
                "victim (`r1-scrub`) only."]
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------


def _emit(text, result, args):
    print(text)
    if args.out_json:
        Path(args.out_json).write_text(json.dumps(result, indent=1) + "\n")
        print("wrote", args.out_json)
    if args.out_md:
        Path(args.out_md).write_text(text)
        print("wrote", args.out_md)


def main(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("diff", help="differential test of two runs")
    sp.add_argument("--a", required=True)
    sp.add_argument("--b", required=True)
    sp.add_argument("--allow-same-seed", action="store_true",
                    help="reproducibility guard: the two runs use one seed")
    sp = sub.add_parser("effect", help="raw-cycle effect size of one run")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--reference", help="run whose p_xor_k effect is the 100%% mark")
    sp.add_argument("--nperm", type=int, default=NPERM)
    sp = sub.add_parser("count", help="collision-count test of one run")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--nperm", type=int, default=NPERM)
    for name in ("diff", "effect", "count"):
        sub.choices[name].add_argument("--out-json")
        sub.choices[name].add_argument("--out-md")
    args = p.parse_args(argv)
    try:
        if args.cmd == "diff":
            res = diff_runs(args.a, args.b, args.allow_same_seed)
            _emit(render_diff(res), res, args)
            return 0 if res["preconditions_ok"] else 2
        if args.cmd == "effect":
            res = effect_run(args.run_dir, nperm=args.nperm,
                             reference=args.reference)
            _emit(render_effect(res), res, args)
        else:
            res = count_run(args.run_dir, nperm=args.nperm)
            _emit(render_count(res), res, args)
        if res["health_problems"]:
            print("RUN HEALTH: FAIL")
            return 1
        print("RUN HEALTH: PASS")
        return 0
    except FollowupError as exc:
        print("ERROR: %s" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
