#!/usr/bin/env python3
"""Append preregistered deviations, with today's date, to the two ledgers.

  usage: python3 -B log_deviations.py <path to experiments/aes-leakage> D1 [D2 ...]

The text comes verbatim from docs/DEVIATIONS_D1_D4.md next to this script; only
the token DATE_LOGGED is replaced by today's date (YYYY-MM-DD).  The bullets
are appended to the END of
  PREREGISTRATION_DRAFT.md   (its last section is "## 11. Deviations")
  progress.md                (its last section is "## Deviations log")
Nothing above the end of either file is changed.  A deviation that is already
present is refused, so the script cannot log one twice or re-date it.
"""
import datetime
import re
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "docs" / "DEVIATIONS_D1_D4.md"
TARGETS = (("PREREGISTRATION_DRAFT.md", "## 11. Deviations"),
           ("progress.md", "## Deviations log"))


def bullets():
    """{'D1': text, ...} -- each bullet runs to the next '* **D' or the end."""
    text = SOURCE.read_bytes().decode("utf-8").replace("\r\n", "\n")
    parts = re.split(r"(?m)^(?=\* \*\*D\d+ \()", text)
    out = {}
    for part in parts:
        match = re.match(r"\* \*\*(D\d+) \(", part)
        if match:
            out[match.group(1)] = part.rstrip("\n") + "\n"
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    exp, wanted = Path(sys.argv[1]), sys.argv[2:]
    available = bullets()
    today = datetime.date.today().isoformat()
    for name in wanted:
        if name not in available:
            sys.exit("ERROR: %s is not in %s" % (name, SOURCE.name))
    plans = []
    for rel, heading in TARGETS:
        path = exp / rel
        text = path.read_bytes().decode("utf-8")
        newline = "\r\n" if "\r\n" in text else "\n"
        body = text.replace("\r\n", "\n")
        last_heading = [l for l in body.splitlines() if l.startswith("## ")][-1]
        if last_heading != heading:
            sys.exit("ERROR: the last section of %s is %r, expected %r" % (
                rel, last_heading, heading))
        for name in wanted:
            if "* **%s (" % name in body:
                sys.exit("ERROR: %s is already logged in %s" % (name, rel))
        addition = "".join(available[n].replace("DATE_LOGGED", today)
                           for n in wanted)
        new_body = body.rstrip("\n") + "\n" + addition
        plans.append((path, new_body.replace("\n", newline)))
    for path, content in plans:
        path.write_bytes(content.encode("utf-8"))
        print("appended %s to %s (dated %s)" % (", ".join(wanted), path.name,
                                               today))


if __name__ == "__main__":
    main()
