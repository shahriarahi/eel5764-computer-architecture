"""Validation gates for causal trace cases."""

import sys
from pathlib import Path


TDMA = Path(__file__).resolve().parent.parent / "tdma"
sys.path.insert(0, str(TDMA))
from run_pilot import stats_rows
from trace_analysis import match_timelines, read_trace


def validate_equivalence(reference: Path, candidate: Path) -> dict:
    if (reference / "probes.bin").read_bytes() != (candidate / "probes.bin").read_bytes():
        raise ValueError("probe bytes differ")
    if stats_rows(reference / "stats.txt.gz") != stats_rows(candidate / "stats.txt.gz"):
        raise ValueError("simulated statistics differ")
    return {"equivalence": "byte-identical probes and matching simulated statistics"}


def validate_trace_case(case: Path) -> dict:
    events = read_trace(case / "causal.log")
    timelines = match_timelines(events)
    return {"trace_events": len(events), "matched_timelines": len(timelines)}

