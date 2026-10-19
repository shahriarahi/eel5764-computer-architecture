"""EXPLORATORY (post-hoc, not preregistered): per-request joint signature behind the hit effect.

For LLC hits with interval 0 separated, count requests by activity label, response-queue
residence, crossbar forwarding latency (xbar.sched - xbar.tick), and the gap from their
delivery to the next admission. Uses only fields already in the version-2 trace.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

from analyze import analysis_metadata, upstream_gaps
from trace_analysis import match_timelines, read_trace


TDMA_FRAME_TICKS = 8000  # two 4 ns request slots


def explore(case: Path) -> dict:
    meta = analysis_metadata(json.loads((case / "run_meta.json").read_text()))
    timelines = match_timelines(read_trace(case / "causal.log"))
    gaps = upstream_gaps(timelines)
    joint: Counter = Counter()
    next_gaps: Counter = Counter()
    admit_phases: Counter = Counter()
    post_forward: Counter = Counter()
    for index, timeline in enumerate(timelines):
        delivery = timeline["cpu_delivery"].tick
        if not meta["start_tick"] <= delivery < meta["end_tick"]:
            continue
        interval = (delivery - meta["start_tick"]) // meta["epoch_ticks"]
        if interval == 0 or timeline["llc_response_ready"].outcome != "hit":
            continue
        label = meta["activity_labels"][interval]
        residence = timeline["response_dequeue"].tick - timeline["response_enqueue"].sched
        forward = timeline["xbar_response_forward"]
        latency = forward.sched - forward.tick
        following = gaps[index + 1] if index + 1 < len(timelines) else None
        joint[(label, residence, latency)] += 1
        if residence:
            next_gaps[(label, following)] += 1
        admit_phases[timeline["request_admit"].tick % TDMA_FRAME_TICKS] += 1
        post_forward[delivery - forward.sched] += 1
    return {
        "case": str(case),
        "label": "exploratory, post-hoc",
        "joint_label_residence_forward_latency": [
            {"label": k[0], "queue_residence_ticks": k[1], "xbar_forward_latency_ticks": k[2],
             "requests": v} for k, v in sorted(joint.items())],
        "next_gap_after_delayed_dequeue": [
            {"label": k[0], "next_upstream_gap_ticks": k[1], "requests": v}
            for k, v in sorted(next_gaps.items(), key=lambda item: (item[0][0], item[0][1] or -1))],
        "admit_phase_mod_frame": {str(k): v for k, v in sorted(admit_phases.items())},
        "post_forward_to_cpu_ticks": {str(k): v for k, v in sorted(post_forward.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = [explore(case) for case in args.cases]
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
