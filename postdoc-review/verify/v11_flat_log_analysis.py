"""V11 -- does the existing analysis survive a perfectly flat probe log?

A flat log (every set has the same latency in every window) is the EXPECTED
outcome of a way-partitioned or fully defended arm in the window schedule.
Synthetic run directories only (written under verify/_tmp); the experiment's
analysis module is imported read-only.
"""
import shutil
import traceback
import warnings

from _common import A, TMP, np

warnings.simplefilter("ignore")
for label, kwargs in (
        ("flat log, partitioned 8-8", dict(delta=0.0, noise=0.0, split="8-8", ways=8)),
        ("flat log, unpartitioned", dict(delta=0.0, noise=0.0)),
        ("one set jitters by 1 cycle, rest flat", dict(delta=0.0, noise=0.0, jitter=True))):
    run_dir = TMP / "flat"
    shutil.rmtree(run_dir, ignore_errors=True)
    jitter = kwargs.pop("jitter", False)
    A.synth_run(run_dir, n=300, rounds1=False, **kwargs)
    if jitter:
        rec = np.frombuffer((run_dir / "probes.bin").read_bytes(),
                            dtype=A.PROBE_DTYPE).copy()
        lat = rec["latency"].reshape(300, 256)
        lat[::7, 200] += 1
        rec.tofile(run_dir / "probes.bin")
    try:
        res = A.analyze_run_dir(run_dir, nperm=2)
        print("%-40s -> analysed: run checks %s, any statement supported: %s" % (
            label, res["run_checks"]["all_passed"],
            any(res["decision"][k] for k in (
                "round1_plaintext_plus_key", "round1_plaintext_only",
                "lastround_c_xor_k10", "lastround_ciphertext_only"))))
    except Exception as exc:                       # noqa: BLE001
        last = traceback.extract_tb(exc.__traceback__)[-1]
        print("%-40s -> CRASH %s: %s (%s line %d, in %s)" % (
            label, type(exc).__name__, exc, last.filename.split("/")[-1],
            last.lineno, last.name))
shutil.rmtree(TMP / "flat", ignore_errors=True)
