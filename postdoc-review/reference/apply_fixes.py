#!/usr/bin/env python3
"""Apply two small, exact source fixes to the experiment directory.

  usage: python3 -B apply_fixes.py <path to experiments/aes-leakage>

Fix 1 (analysis/aes_leak_analysis.py, anova_p_min): a probe log in which every
  set has the same latency in every window made np.nanargmax raise ValueError.
  That log is the expected outcome of a partitioned or defended arm.
Fix 2 (preserve.py, list_files): files under a `.claude/` directory are
  assistant-session state that other sessions rewrite; pinning them made
  `preserve.py verify` fail without any change to the experiment.

Each fix replaces one exact anchor.  Running the script twice is safe: an
already-applied fix is reported and skipped; a missing anchor is an error.
"""
import sys
from pathlib import Path

FIXES = [
    ("analysis/aes_leak_analysis.py",
     "    snr_v = snr_from_stats(cnt[:, 0], s1, s2)\n"
     "    j = int(np.nanargmin(p))\n",
     "    snr_v = snr_from_stats(cnt[:, 0], s1, s2)\n"
     "    if np.isnan(snr_v).all():      # every set is constant: nothing to test\n"
     "        return 0.0, 0, 1.0\n"
     "    j = int(np.nanargmin(p))\n"),
    ("preserve.py",
     "        if not path.is_file() or \"__pycache__\" in path.parts:\n"
     "            continue\n",
     "        if not path.is_file() or \"__pycache__\" in path.parts:\n"
     "            continue\n"
     "        if \".claude\" in path.relative_to(exp_dir).parts:\n"
     "            continue               # assistant-session state, not data\n"),
]


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    exp = Path(sys.argv[1])
    status = 0
    for rel, old, new in FIXES:
        path = exp / rel
        text = path.read_bytes().decode("utf-8")
        if text.count(new) == 1:
            print("already applied: %s" % rel)
        elif text.count(old) == 1:
            path.write_bytes(text.replace(old, new).encode("utf-8"))
            print("applied: %s" % rel)
        else:
            print("ERROR: anchor not found exactly once in %s" % rel)
            status = 1
    sys.exit(status)


if __name__ == "__main__":
    main()
