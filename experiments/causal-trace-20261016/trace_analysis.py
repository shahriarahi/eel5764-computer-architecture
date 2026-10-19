"""Parse and analyze filtered gem5 causal-trace records."""

from dataclasses import dataclass
from pathlib import Path


STAGES = {
    "request_admit",
    "llc_response_ready",
    "response_enqueue",
    "response_send_attempt",
    "response_retry",
    "response_dequeue",
    "xbar_response_forward",
    "cpu_delivery",
}
REQUIRED_FIELDS = {
    "version", "tick", "stage", "component", "requestor", "cmd",
    "paddr", "vaddr", "size",
}


@dataclass(frozen=True, slots=True)
class TraceEvent:
    version: int
    tick: int
    stage: str
    component: str
    requestor: int
    cmd: str
    paddr: int
    vaddr: int
    size: int
    outcome: str | None
    # Version 2: the future tick handed to a sched* call (equals tick otherwise).
    sched: int | None = None


def parse_trace_line(line: str) -> TraceEvent | None:
    marker = "CAUSAL_TRACE "
    position = line.find(marker)
    if position < 0:
        return None
    fields: dict[str, str] = {}
    for item in line[position + len(marker):].split():
        if "=" not in item:
            raise ValueError(f"malformed field: {item}")
        key, value = item.split("=", 1)
        fields[key] = value
    missing = sorted(REQUIRED_FIELDS - fields.keys())
    if missing:
        raise ValueError("missing fields: " + ", ".join(missing))
    def integer(name: str, base: int) -> int:
        try:
            return int(fields[name], base)
        except ValueError as exc:
            raise ValueError(f"invalid {name}: {fields[name]!r}") from exc

    version = integer("version", 10)
    tick = integer("tick", 10)
    requestor = integer("requestor", 10)
    paddr = integer("paddr", 16)
    vaddr = integer("vaddr", 16)
    size = integer("size", 10)
    if version not in (1, 2):
        raise ValueError(f"unsupported version: {version}")
    sched = None
    if version == 2:
        if "sched" not in fields:
            raise ValueError("missing fields: sched")
        sched = integer("sched", 10)
        if sched < tick:
            raise ValueError(f"sched {sched} precedes tick {tick}")
    stage = fields["stage"]
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    return TraceEvent(version, tick, stage, fields["component"], requestor,
                      fields["cmd"], paddr, vaddr, size,
                      fields.get("outcome"), sched)


def read_trace(path: Path) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            try:
                event = parse_trace_line(line)
            except ValueError as exc:
                raise ValueError(f"{path}: line {number}: {exc}") from exc
            if event is not None:
                events.append(event)
    return events


REQUIRED_TIMELINE_STAGES = (
    "request_admit",
    "llc_response_ready",
    "response_enqueue",
    "response_dequeue",
    "xbar_response_forward",
    "cpu_delivery",
)
LATENCY_FIELDS = (
    "admit_to_llc_ready",
    "llc_ready_to_enqueue",
    "queue_residence",
    "dequeue_to_xbar",
    "xbar_to_cpu",
    "admit_to_cpu",
    "cumulative_llc_ready",
    "cumulative_enqueue",
    "cumulative_dequeue",
    "cumulative_xbar",
)


def match_timelines(
    events: list[TraceEvent],
) -> list[dict[str, TraceEvent | list[TraceEvent]]]:
    by_stage = {
        stage: sorted((event for event in events if event.stage == stage),
                      key=lambda event: event.tick)
        for stage in STAGES
    }
    admissions = by_stage["request_admit"]
    if not admissions:
        raise ValueError("no request_admit events")
    count = len(admissions)
    expected_addresses = [(event.paddr, event.vaddr) for event in admissions]
    for stage in REQUIRED_TIMELINE_STAGES[1:]:
        stage_events = by_stage[stage]
        if len(stage_events) != count:
            raise ValueError(
                f"{stage}: expected {count} events, found {len(stage_events)}"
            )
        for index, (event, address) in enumerate(zip(stage_events, expected_addresses)):
            if (event.paddr, event.vaddr) != address:
                raise ValueError(f"{stage}: address mismatch at index {index}")

    timelines: list[dict[str, TraceEvent | list[TraceEvent]]] = []
    assigned_attempts: set[int] = set()
    assigned_retries: set[int] = set()
    for index in range(count):
        timeline: dict[str, TraceEvent | list[TraceEvent]] = {
            stage: by_stage[stage][index] for stage in REQUIRED_TIMELINE_STAGES
        }
        ordered = [by_stage[stage][index] for stage in REQUIRED_TIMELINE_STAGES]
        if any(left.tick > right.tick for left, right in zip(ordered, ordered[1:])):
            raise ValueError(f"negative stage duration at index {index}")
        enqueue = by_stage["response_enqueue"][index]
        dequeue = by_stage["response_dequeue"][index]
        address = expected_addresses[index]
        attempts = [event for event in by_stage["response_send_attempt"]
                    if enqueue.tick <= event.tick <= dequeue.tick
                    and (event.paddr, event.vaddr) == address]
        retries = [event for event in by_stage["response_retry"]
                   if enqueue.tick <= event.tick <= dequeue.tick
                   and (event.paddr, event.vaddr) == address]
        if not attempts:
            raise ValueError(f"response_send_attempt: missing at index {index}")
        timeline["response_send_attempts"] = attempts
        timeline["response_retries"] = retries
        assigned_attempts.update(id(event) for event in attempts)
        assigned_retries.update(id(event) for event in retries)
        timelines.append(timeline)
    if len(assigned_attempts) != len(by_stage["response_send_attempt"]):
        raise ValueError("unmatched response_send_attempt event")
    if len(assigned_retries) != len(by_stage["response_retry"]):
        raise ValueError("unmatched response_retry event")
    return timelines


def latency_rows(timelines: list[dict], metadata: dict) -> list[dict]:
    start = int(metadata["start_tick"])
    width = int(metadata["epoch_ticks"])
    labels = list(metadata["activity_labels"])
    if width <= 0:
        raise ValueError("epoch_ticks must be positive")
    rows = []
    for index, timeline in enumerate(timelines):
        if any(timeline[stage].sched is None for stage in REQUIRED_TIMELINE_STAGES):
            raise ValueError(f"version-1 timeline lacks scheduled ticks at index {index}")
        admit = timeline["request_admit"].tick
        ready = timeline["llc_response_ready"].sched
        enqueue = timeline["response_enqueue"].sched
        dequeue = timeline["response_dequeue"].tick
        xbar = timeline["xbar_response_forward"].tick
        delivery = timeline["cpu_delivery"].tick
        if not admit <= ready <= enqueue <= dequeue <= xbar <= delivery:
            raise ValueError(f"negative scheduled stage duration at index {index}")
        interval = (delivery - start) // width
        if interval < 0 or interval >= len(labels):
            raise ValueError(f"delivery outside labelled intervals at index {index}")
        admit_interval = (admit - start) // width
        rows.append({
            "index": index,
            "interval": interval,
            "label": labels[interval],
            "llc_path": timeline["llc_response_ready"].outcome,
            "boundary_crossing": admit_interval != interval,
            "retry_count": len(timeline["response_retries"]),
            "admit_to_llc_ready": ready - admit,
            "llc_ready_to_enqueue": enqueue - ready,
            "queue_residence": dequeue - enqueue,
            "dequeue_to_xbar": xbar - dequeue,
            "xbar_to_cpu": delivery - xbar,
            "admit_to_cpu": delivery - admit,
            "cumulative_llc_ready": ready - admit,
            "cumulative_enqueue": enqueue - admit,
            "cumulative_dequeue": dequeue - admit,
            "cumulative_xbar": xbar - admit,
        })
    return rows


def _effects(rows: list[dict]) -> dict[str, float]:
    interval_means: dict[str, dict[int, list[float]]] = {
        field: {} for field in LATENCY_FIELDS
    }
    interval_labels: dict[int, int] = {}
    for row in rows:
        interval = row["interval"]
        label = row["label"]
        if interval in interval_labels and interval_labels[interval] != label:
            raise ValueError(f"conflicting label for interval {interval}")
        interval_labels[interval] = label
        for field in LATENCY_FIELDS:
            if field in row:
                interval_means[field].setdefault(interval, []).append(row[field])
    effects = {}
    for field, values in interval_means.items():
        means = {interval: sum(items) / len(items)
                 for interval, items in values.items()}
        active = [value for interval, value in means.items()
                  if interval_labels[interval] == 1]
        idle = [value for interval, value in means.items()
                if interval_labels[interval] == 0]
        if active and idle:
            effects[field] = sum(active) / len(active) - sum(idle) / len(idle)
    return effects


def summarize_segments(rows: list[dict]) -> dict:
    without_zero = [row for row in rows if row["interval"] != 0]
    return {
        "effects": _effects(rows),
        "without_interval_zero": {"effects": _effects(without_zero)},
        "retry_count": sum(row["retry_count"] for row in rows),
        "boundary_crossings": sum(bool(row["boundary_crossing"]) for row in rows),
    }
