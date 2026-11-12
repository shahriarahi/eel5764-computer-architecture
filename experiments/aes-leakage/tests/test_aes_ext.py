"""aes_leak_ext.c: the paper's encryption plus a round-1-only lookup mode.

The host harness #includes aes_leak_ext.c, which #includes the frozen
workloads/aes_ttable.c, so the encryption under test is the paper's source.
"""
import unittest

import numpy as np

from tests import _helpers as h


@h.skip_unless_tool(h.HOST_CC)
class HostHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = h.tmpdir()
        cls.exe = h.Path(cls._tmp.name) / "aes_host_harness"
        proc = h.host_build([h.C_DIR / "aes_host_harness.c"], cls.exe,
                            defines=["LEAK_FAKE_CLOCK"])
        if proc.returncode != 0:
            raise AssertionError("host build failed:\n" + proc.stderr)
        cls.analysis = h.load_analysis()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def harness(self, seed, windows, tvla):
        proc = h.run([self.exe, seed, windows, tvla])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = {}
        for line in proc.stdout.splitlines():
            key, _, value = line.partition("=")
            if line.startswith("ct "):
                out.setdefault("ct_lines", []).append(line.split()[2])
            else:
                out[key] = value
        return out

    def python_reference(self, seed, windows, tvla):
        a = self.analysis
        key = a.hex16("f1e2d3c4b5a69788796a5b4c3d2e1f10")
        fixed = a.hex16("da39a3ee5e6b4b0d3255bfef95601890")
        pts = a.plaintexts(seed, windows, tvla_fixed=fixed if tvla else None)
        cts = a.aes_encrypt_trace(pts, a.key_expansion(key))[0]
        return (pts, cts,
                bytes(np.bitwise_xor.reduce(pts, axis=0)).hex(),
                bytes(np.bitwise_xor.reduce(cts, axis=0)).hex())

    def test_fips197_c1_known_answer_through_the_papers_encrypt(self):
        self.assertEqual(self.harness(5, 1, 0)["kat"], "PASS")

    def test_round1_mode_loads_exactly_the_sixteen_round1_table_words(self):
        self.assertEqual(self.harness(0x5764A5E5, 50, 0)["round1_lookups"],
                         "PASS")

    def test_checksums_match_python_over_many_windows(self):
        for seed, windows, tvla in ((0x5764A5E5, 200, 0), (3, 64, 1)):
            got = self.harness(seed, windows, tvla)
            _, cts, pt_sum, ct_sum = self.python_reference(seed, windows, tvla)
            self.assertEqual(got["pt_checksum"], pt_sum, (seed, tvla))
            self.assertEqual(got["ct_checksum"], ct_sum, (seed, tvla))

    def test_first_ciphertexts_match_python(self):
        got = self.harness(0x5764A5E5, 5, 0)
        _, cts, _, _ = self.python_reference(0x5764A5E5, 5, 0)
        self.assertEqual(got["ct_lines"], [bytes(c).hex() for c in cts[:3]])


if __name__ == "__main__":
    unittest.main()
