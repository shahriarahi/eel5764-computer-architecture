#!/usr/bin/env python3
"""
power_synth.py -- synthetic power and false-positive tables for the analysis.

SYNTHETIC ONLY.  The data come from aes_leak_analysis.synth_run(), a rehearsal
generator, NOT from gem5.  The tables answer two questions before any gem5 data
exist: (1) how many windows N does the preregistered decision rule need when
the monitor sees a data-dependent latency rise of a given size, and (2) does the
rule stay quiet when there is no data dependence at all.  They say nothing about
how large the real effect is; that is what the gem5 runs P1-P4 measure.

    python3 power_synth.py                 # full grid (several minutes)
    python3 power_synth.py --quick         # small grid
"""
import argparse
import importlib.util
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "aes_leak_analysis_for_power", HERE / "aes_leak_analysis.py")
analysis = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analysis)


def _one(rounds1, n, delta, noise, leak, rng_seed):
    with tempfile.TemporaryDirectory(prefix="aesleak-power-") as tmp:
        analysis.synth_run(Path(tmp) / "run", n=n, rounds1=rounds1, leak=leak,
                           delta=delta, noise=noise, rng_seed=rng_seed)
        return analysis.analyze_run_dir(Path(tmp) / "run")


def power_grid(modes=("round1", "full"), deltas=(40.0, 10.0, 4.0),
               sizes=(250, 500, 1000, 2000, 4000), reps=6, noise=6.0):
    """Mean significant bytes and decision frequency per (mode, delta, N)."""
    rows = []
    for mode in modes:
        for delta in deltas:
            for n in sizes:
                bytes_r1, bytes_lr, sup_r1, sup_lr = [], [], [], []
                for rep in range(reps):
                    res = _one(mode == "round1", n, delta, noise, "key",
                               1000 * rep + 7)
                    at, dec = res["attribution"], res["decision"]
                    bytes_r1.append(at["p_xor_k"]["bytes_significant"])
                    bytes_lr.append(at["lr_c_xor_k10"]["bytes_significant"])
                    sup_r1.append(dec["round1_plaintext_plus_key"])
                    sup_lr.append(dec["lastround_c_xor_k10"])
                rows.append({
                    "mode": mode, "delta": delta, "noise": noise, "n": n,
                    "reps": reps,
                    "mean_bytes_p_xor_k": sum(bytes_r1) / reps,
                    "mean_bytes_lastround": sum(bytes_lr) / reps,
                    "frac_round1_supported": sum(sup_r1) / reps,
                    "frac_lastround_supported": sum(sup_lr) / reps})
    return rows


def false_positive_rate(rounds1, n, reps, delta=40.0, noise=6.0):
    """Runs with NO data dependence (round-1 lines random): how often does any
    of the four decision statements come out true, and how often is any of the
    six hypotheses (including both shuffled controls) significant on a byte."""
    any_decision = any_hypothesis = 0
    for rep in range(reps):
        res = _one(rounds1, n, delta, noise, "none", 5000 + rep)
        dec = res["decision"]
        any_decision += any(dec[k] for k in (
            "round1_plaintext_plus_key", "round1_plaintext_only",
            "lastround_c_xor_k10", "lastround_ciphertext_only"))
        any_hypothesis += any(v["bytes_significant"] > 0
                              for v in res["attribution"].values())
    return {"mode": "round1" if rounds1 else "full", "n": n, "reps": reps,
            "any_decision_true": any_decision,
            "any_hypothesis_significant": any_hypothesis}


def render_markdown(power_rows, fp_rows):
    out = ["# Synthetic power and false-positive tables", "",
           "Synthetic data from `synth_run()`; NOT gem5 results. `delta` is the "
           "latency rise (cycles) of a set whose table line was touched, "
           "`noise` the per-probe standard deviation (cycles); every touched "
           "line is visible (visibility 1.0).", "",
           "## Power of the preregistered decision rule", "",
           "| mode | delta | N | reps | mean bytes sig. p_xor_k (of 16) | "
           "mean bytes sig. last round (of 16) | frac round1 supported | "
           "frac last round supported |",
           "|---|---|---|---|---|---|---|---|"]
    for r in power_rows:
        out.append("| %s | %g | %d | %d | %.1f | %.1f | %.2f | %.2f |" % (
            r["mode"], r["delta"], r["n"], r["reps"], r["mean_bytes_p_xor_k"],
            r["mean_bytes_lastround"], r["frac_round1_supported"],
            r["frac_lastround_supported"]))
    out += ["", "## False positives on data with no data dependence", "",
            "| mode | N | reps | runs with any decision true | runs with any "
            "hypothesis significant |", "|---|---|---|---|---|"]
    for r in fp_rows:
        out.append("| %s | %d | %d | %d | %d |" % (
            r["mode"], r["n"], r["reps"], r["any_decision_true"],
            r["any_hypothesis_significant"]))
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--reps", type=int, default=6)
    parser.add_argument("--fp-reps", type=int, default=200)
    parser.add_argument("--out")
    args = parser.parse_args()
    if args.quick:
        power = power_grid(sizes=(500, 2000), deltas=(10.0,), reps=2)
        fp = [false_positive_rate(True, 500, 6), false_positive_rate(False, 500, 6)]
    else:
        power = power_grid(reps=args.reps)
        fp = [false_positive_rate(True, 1000, args.fp_reps),
              false_positive_rate(False, 1000, args.fp_reps)]
    text = render_markdown(power, fp)
    print(text)
    if args.out:
        Path(args.out).write_text(text)


if __name__ == "__main__":
    main()
