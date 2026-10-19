"""Stage-latency localization for one validated trace-enabled case."""

import argparse
from fractions import Fraction
import json
from pathlib import Path

from trace_analysis import LATENCY_FIELDS, latency_rows, match_timelines, read_trace


TICKS_PER_CPU_CYCLE = 500
# Cumulative latency from request_admit, in pipeline order.
CHECKPOINTS = (
    "cumulative_llc_ready",
    "cumulative_enqueue",
    "cumulative_dequeue",
    "cumulative_xbar",
    "admit_to_cpu",
)
REPORTED_FIELDS = LATENCY_FIELDS + ("upstream_gap",)


def analysis_metadata(run_meta: dict) -> dict:
    contention = run_meta["contention"]
    start = int(run_meta["reset_tick"])
    width = int(contention["epoch_cycles"]) * TICKS_PER_CPU_CYCLE
    labels = list(contention["activity_labels"])
    end = int(run_meta["measurement_end_tick"])
    if len(labels) != int(contention["interval_count"]) or end - start != width * len(labels):
        raise ValueError("measurement window is not a whole number of labelled intervals")
    return {"start_tick": start, "epoch_ticks": width, "end_tick": end,
            "activity_labels": labels}


def split_by_window(timelines: list[dict], metadata: dict) -> tuple[list[dict], dict]:
    inside, before, after = [], 0, 0
    for timeline in timelines:
        tick = timeline["cpu_delivery"].tick
        if tick < metadata["start_tick"]:
            before += 1
        elif tick >= metadata["end_tick"]:
            after += 1
        else:
            inside.append(timeline)
    return inside, {"before_measurement": before, "after_measurement": after}


def upstream_gaps(timelines: list[dict]) -> list[int | None]:
    """Previous delivery to next admission: CPU issue, L1D, and TDMA admission wait."""
    gaps: list[int | None] = [None]
    for previous, current in zip(timelines, timelines[1:]):
        gap = current["request_admit"].tick - previous["cpu_delivery"].tick
        if gap < 0:
            raise ValueError("monitor requests overlap; upstream gap undefined")
        gaps.append(gap)
    return gaps[:len(timelines)]


def exact_effects(rows: list[dict], fields: tuple[str, ...]) -> dict[str, Fraction]:
    labels: dict[int, int] = {}
    values: dict[str, dict[int, list[int]]] = {field: {} for field in fields}
    for row in rows:
        labels[row["interval"]] = row["label"]
        for field in fields:
            if row.get(field) is not None:
                values[field].setdefault(row["interval"], []).append(row[field])
    effects = {}
    for field, by_interval in values.items():
        means = {interval: Fraction(sum(items), len(items))
                 for interval, items in by_interval.items()}
        active = [mean for interval, mean in means.items() if labels[interval] == 1]
        idle = [mean for interval, mean in means.items() if labels[interval] == 0]
        if active and idle:
            effects[field] = sum(active) / len(active) - sum(idle) / len(idle)
    return effects


def earliest_divergence(effects: dict[str, Fraction], rows: list[dict]) -> dict:
    previous = None
    for checkpoint in CHECKPOINTS:
        if effects.get(checkpoint, Fraction(0)) != 0:
            if previous is not None and all(row[previous] == row[checkpoint] for row in rows):
                return {"status": "unresolved", "checkpoint": checkpoint,
                        "reason": f"simultaneous with {previous} for every request"}
            if previous is None and all(row[checkpoint] == 0 for row in rows):
                return {"status": "unresolved", "checkpoint": checkpoint,
                        "reason": "simultaneous with request_admit for every request"}
            return {"status": "resolved", "checkpoint": checkpoint,
                    "after": previous or "request_admit"}
        previous = checkpoint
    return {"status": "unresolved", "checkpoint": None,
            "reason": "no checkpoint from request_admit onward diverges; any residual "
                      "arises before request_admit (not instrumented) or is absent"}


def describe(rows: list[dict]) -> dict:
    if not rows:
        return {"requests": 0}
    effects = exact_effects(rows, REPORTED_FIELDS)
    without_zero = [row for row in rows if row["interval"] != 0]
    effects_without_zero = exact_effects(without_zero, REPORTED_FIELDS)

    def table(values: dict[str, Fraction]) -> dict:
        return {field: {"exact_ticks": str(value), "ticks": float(value),
                        "cpu_cycles": float(value / TICKS_PER_CPU_CYCLE)}
                for field, value in values.items()}

    return {
        "requests": len(rows),
        "retries": sum(row["retry_count"] for row in rows),
        "boundary_crossings": sum(bool(row["boundary_crossing"]) for row in rows),
        "effects": table(effects),
        "earliest_divergence": earliest_divergence(effects, rows),
        "without_interval_zero": {
            "requests": len(without_zero),
            "effects": table(effects_without_zero),
            "earliest_divergence": earliest_divergence(effects_without_zero, without_zero),
        },
    }


def analyze_case(case: Path) -> dict:
    metadata = analysis_metadata(json.loads((case / "run_meta.json").read_text()))
    timelines = match_timelines(read_trace(case / "causal.log"))
    gaps = upstream_gaps(timelines)
    for timeline, gap in zip(timelines, gaps):
        timeline["upstream_gap"] = gap
    inside, window = split_by_window(timelines, metadata)
    rows = latency_rows(inside, metadata)
    for row, timeline in zip(rows, inside):
        row["upstream_gap"] = timeline["upstream_gap"]
    paths: dict[str, int] = {}
    for row in rows:
        paths[str(row["llc_path"])] = paths.get(str(row["llc_path"]), 0) + 1
    return {
        "case": str(case),
        "matched_timelines": len(timelines),
        "window_exclusions": window,
        "llc_paths": paths,
        "all_requests": describe(rows),
        "llc_hits": describe([row for row in rows if row["llc_path"] == "hit"]),
        "llc_fills": describe([row for row in rows if row["llc_path"] == "fill"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = analyze_case(args.case)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({key: result[key] for key in ("matched_timelines", "window_exclusions",
                                                   "llc_paths")}))


if __name__ == "__main__":
    main()
