import tempfile
import unittest
from pathlib import Path

from run_structural import validate_disabled_trace, validate_enabled_trace
from test_trace_traffic import install_short_profile


def trace_line(tick: int, stage: str, outcome: str = "ok") -> str:
    return (
        f"{tick}: system: CAUSAL_TRACE version=1 tick={tick} stage={stage} "
        "component=system.test requestor=7 cmd=ReadReq paddr=0x1000 "
        f"vaddr=0x12080 size=8 outcome={outcome}\n"
    )


class StructuralValidationTests(unittest.TestCase):
    def test_short_profile_updates_live_baseline_globals(self) -> None:
        def original(config: dict, l1d_size: str) -> None:
            config["selected"] = l1d_size
            config["measure_ticks"] = 99
        live_globals = {"apply_experiment_profile": original}
        install_short_profile(live_globals)
        config = {}
        live_globals["apply_experiment_profile"](config, "4KiB")
        self.assertEqual(config["selected"], "4KiB")
        self.assertEqual(config["warmup_ticks"], 1_000_000_000)
        self.assertEqual(config["measure_ticks"], 20_000_000)
        self.assertEqual(config["logging_grace_ticks"], 0)

    def test_accepts_complete_eight_stage_trace(self) -> None:
        stages = (
            "request_admit", "llc_response_ready", "response_enqueue",
            "response_send_attempt", "response_retry", "response_dequeue",
            "xbar_response_forward", "cpu_delivery",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "causal.log"
            path.write_text("".join(
                trace_line(index, stage) for index, stage in enumerate(stages)
            ))
            result = validate_enabled_trace(path)
        self.assertEqual(result["stages"], list(stages))
        self.assertEqual(result["matched_timelines"], 1)

    def test_accepts_trace_without_backpressure_retry(self) -> None:
        stages = (
            "request_admit", "llc_response_ready", "response_enqueue",
            "response_send_attempt", "response_dequeue",
            "xbar_response_forward", "cpu_delivery",
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "causal.log"
            path.write_text("".join(
                trace_line(index, stage) for index, stage in enumerate(stages)
            ))
            result = validate_enabled_trace(path)
        self.assertEqual(result["stages"], list(stages))
        self.assertEqual(result["response_retries"], 0)

    def test_rejects_incomplete_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "causal.log"
            path.write_text(trace_line(0, "request_admit"))
            with self.assertRaisesRegex(ValueError, "missing stages"):
                validate_enabled_trace(path)

    def test_disabled_trace_rejects_causal_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "causal.log"
            path.write_text(trace_line(0, "request_admit"))
            with self.assertRaisesRegex(ValueError, "trace-disabled"):
                validate_disabled_trace(path)


if __name__ == "__main__":
    unittest.main()
