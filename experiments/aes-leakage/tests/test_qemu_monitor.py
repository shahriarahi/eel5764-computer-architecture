"""monitor_leak alone under qemu-user (fake clock, N=4 windows, A=2 ways)."""
import os
import struct
import unittest

from tests import _helpers as h

N = 4
WAYS = 2
RECORD = struct.Struct("<QIHH")          # timestamp, latency, interval, set


@h.skip_unless_tool(h.RISCV_CC, h.QEMU)
class MonitorUnderQemu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = h.fake_clock_build(N)
        cls.out = h.tmpdir()

    @classmethod
    def tearDownClass(cls):
        cls.out.cleanup()

    def run_monitor(self, ways=WAYS, name="probes.bin"):
        path = os.path.join(self.out.name, name)
        proc = h.qemu_run(self.build / "monitor_leak", ways, path)
        return proc, path

    def test_header_line_and_clean_exit(self):
        proc, _ = self.run_monitor()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertIn("monitor format=probe_bin_v2 windows=%d sets=256 ways=%d"
                      % (N, WAYS), lines)
        self.assertIn("monitor status=PASS records=%d" % (N * 256), lines)

    def test_probe_file_is_valid_probe_bin_v2(self):
        proc, path = self.run_monitor(name="valid.bin")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        data = h.Path(path).read_bytes()
        self.assertEqual(len(data), N * 256 * RECORD.size)
        records = [RECORD.unpack_from(data, i * RECORD.size)
                   for i in range(N * 256)]
        for index, (timestamp, latency, interval, cache_set) in enumerate(records):
            self.assertEqual(interval, index // 256, index)
            self.assertEqual(cache_set, index % 256, index)
            # fake clock: two consecutive rdcycle calls differ by exactly one step
            self.assertEqual(latency, 16, index)
        stamps = [r[0] for r in records]
        self.assertEqual(stamps, sorted(stamps))
        self.assertEqual(len(set(stamps)), len(stamps), "timestamps strictly increase")

    def test_each_window_is_probed_after_its_own_start(self):
        proc, path = self.run_monitor(name="windows.bin")
        self.assertEqual(proc.returncode, 0)
        p = h.load_params().constants()
        data = h.Path(path).read_bytes()
        for window in range(N):
            first = RECORD.unpack_from(data, window * 256 * RECORD.size)[0]
            w0 = p["T0"] + window * p["W"]
            self.assertGreaterEqual(first, w0 + p["OFF_PROBE"])
            self.assertLess(first, w0 + p["W"])

    def test_invalid_way_counts_exit_2(self):
        for bad in ("0", "17", "x", ""):
            proc, _ = self.run_monitor(ways=bad, name="bad.bin")
            self.assertEqual(proc.returncode, 2, bad)
            self.assertIn("monitor error=usage", proc.stdout)

    def test_missing_probe_path_exits_2(self):
        proc = h.qemu_run(self.build / "monitor_leak", 2)
        self.assertEqual(proc.returncode, 2)

    def test_unwritable_probe_path_exits_2(self):
        proc = h.qemu_run(self.build / "monitor_leak", 2,
                          "/nonexistent-dir/probes.bin")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("monitor error=probe_sink_open", proc.stdout)


if __name__ == "__main__":
    unittest.main()
