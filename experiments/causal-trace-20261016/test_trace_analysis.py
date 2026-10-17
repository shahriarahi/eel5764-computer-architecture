import tempfile
import unittest
from pathlib import Path

from trace_analysis import (
    TraceEvent,
    latency_rows,
    match_timelines,
    parse_trace_line,
    read_trace,
    summarize_segments,
)


VALID = (
    "CAUSAL_TRACE version=1 tick=100 stage=request_admit "
    "component=system.l2bus requestor=3 cmd=ReadReq "
    "paddr=0x1000 vaddr=0x2000 size=8"
)


class TraceParserTests(unittest.TestCase):
    def test_parses_version_one_record(self) -> None:
        event = parse_trace_line(VALID)
        self.assertEqual(
            event,
            TraceEvent(1, 100, "request_admit", "system.l2bus", 3,
                       "ReadReq", 0x1000, 0x2000, 8, None),
        )

    def test_ignores_non_trace_line(self) -> None:
        self.assertIsNone(parse_trace_line("gem5 started normally"))

    def test_rejects_malformed_integer(self) -> None:
        with self.assertRaisesRegex(ValueError, "tick"):
            parse_trace_line(VALID.replace("tick=100", "tick=soon"))

    def test_rejects_unknown_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "version"):
            parse_trace_line(VALID.replace("version=1", "version=2"))

    def test_rejects_unknown_stage(self) -> None:
        with self.assertRaisesRegex(ValueError, "stage"):
            parse_trace_line(VALID.replace("stage=request_admit", "stage=mystery"))

    def test_rejects_missing_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "vaddr"):
            parse_trace_line(VALID.replace(" vaddr=0x2000", ""))

    def test_parses_blocked_retry(self) -> None:
        line = VALID.replace("stage=request_admit", "stage=response_retry") + " outcome=blocked"
        event = parse_trace_line(line)
        self.assertEqual(event.outcome, "blocked")

    def test_read_trace_reports_line_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "causal.log"
            path.write_text("ordinary line\n" + VALID.replace("size=8", "size=bad") + "\n")
            with self.assertRaisesRegex(ValueError, "line 2"):
                read_trace(path)


def make_event(stage: str, tick: int, address: int = 0x1000,
               outcome: str | None = None) -> TraceEvent:
    return TraceEvent(1, tick, stage, "system.test", 3, "ReadReq",
                      address, address + 0x1000, 8, outcome)


def timeline_events(address: int = 0x1000, start: int = 10) -> list[TraceEvent]:
    return [
        make_event("request_admit", start, address),
        make_event("llc_response_ready", start + 10, address),
        make_event("response_enqueue", start + 11, address),
        make_event("response_send_attempt", start + 20, address, "sent"),
        make_event("response_dequeue", start + 21, address, "sent"),
        make_event("xbar_response_forward", start + 30, address),
        make_event("cpu_delivery", start + 40, address),
    ]


class TimelineTests(unittest.TestCase):
    def test_matches_one_complete_timeline(self) -> None:
        timelines = match_timelines(timeline_events())
        self.assertEqual(len(timelines), 1)
        self.assertEqual(timelines[0]["cpu_delivery"].tick, 50)
        self.assertEqual(len(timelines[0]["response_send_attempts"]), 1)
        self.assertEqual(timelines[0]["response_retries"], [])

    def test_retains_retries_until_successful_dequeue(self) -> None:
        events = timeline_events()
        events[3:5] = [
            make_event("response_send_attempt", 30, outcome="blocked"),
            make_event("response_retry", 31, outcome="blocked"),
            make_event("response_send_attempt", 35, outcome="blocked"),
            make_event("response_retry", 36, outcome="blocked"),
            make_event("response_send_attempt", 40, outcome="sent"),
            make_event("response_dequeue", 41, outcome="sent"),
        ]
        events[-2] = make_event("xbar_response_forward", 45)
        events[-1] = make_event("cpu_delivery", 50)
        timeline = match_timelines(events)[0]
        self.assertEqual([event.tick for event in timeline["response_retries"]], [31, 36])
        self.assertEqual([event.tick for event in timeline["response_send_attempts"]], [30, 35, 40])

    def test_rejects_reordered_address_at_one_stage(self) -> None:
        first = timeline_events(0x1000, 10)
        second = timeline_events(0x2000, 100)
        events = first + second
        ready = [event for event in events if event.stage == "llc_response_ready"]
        ready[0] = make_event("llc_response_ready", 20, 0x2000)
        ready[1] = make_event("llc_response_ready", 110, 0x1000)
        events = [event for event in events if event.stage != "llc_response_ready"] + ready
        with self.assertRaisesRegex(ValueError, "llc_response_ready.*index 0"):
            match_timelines(events)

    def test_rejects_missing_required_stage(self) -> None:
        events = [event for event in timeline_events() if event.stage != "response_enqueue"]
        with self.assertRaisesRegex(ValueError, "response_enqueue"):
            match_timelines(events)

    def test_rejects_duplicate_terminal_event(self) -> None:
        events = timeline_events() + [make_event("cpu_delivery", 51)]
        with self.assertRaisesRegex(ValueError, "cpu_delivery"):
            match_timelines(events)

    def test_rejects_negative_stage_duration(self) -> None:
        events = timeline_events()
        events[1] = make_event("llc_response_ready", 9)
        with self.assertRaisesRegex(ValueError, "negative"):
            match_timelines(events)

    def test_labels_by_delivery_and_reports_boundary_crossing(self) -> None:
        events = timeline_events(start=70)
        rows = latency_rows(match_timelines(events), {
            "start_tick": 0,
            "epoch_ticks": 100,
            "activity_labels": [0, 1],
        })
        self.assertEqual(rows[0]["interval"], 1)
        self.assertEqual(rows[0]["label"], 1)
        self.assertTrue(rows[0]["boundary_crossing"])
        self.assertEqual(rows[0]["admit_to_llc_ready"], 10)
        self.assertEqual(rows[0]["admit_to_cpu"], 40)

    def test_summarizes_interval_means_and_separates_interval_zero(self) -> None:
        rows = [
            {"interval": 0, "label": 0, "retry_count": 0,
             "boundary_crossing": False, "admit_to_cpu": 10},
            {"interval": 1, "label": 1, "retry_count": 1,
             "boundary_crossing": False, "admit_to_cpu": 16},
            {"interval": 2, "label": 0, "retry_count": 0,
             "boundary_crossing": True, "admit_to_cpu": 12},
            {"interval": 3, "label": 1, "retry_count": 0,
             "boundary_crossing": False, "admit_to_cpu": 18},
        ]
        summary = summarize_segments(rows)
        self.assertEqual(summary["effects"]["admit_to_cpu"], 6)
        self.assertEqual(summary["without_interval_zero"]["effects"]["admit_to_cpu"], 5)
        self.assertEqual(summary["retry_count"], 1)
        self.assertEqual(summary["boundary_crossings"], 1)


if __name__ == "__main__":
    unittest.main()
