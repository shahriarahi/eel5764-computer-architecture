"""victim_leak under qemu-user with the fake clock (functional check only).

qemu-user has no meaningful cycle counter, so these runs use -DLEAK_FAKE_CLOCK:
they prove the printed header, the FIPS-197 self-test, the plaintext stream and
the checksums, not any timing behaviour.
"""
import unittest

import numpy as np

from tests import _helpers as h

SEED = 0x5764A5E5
N = 8
KEY = "f1e2d3c4b5a69788796a5b4c3d2e1f10"


@h.skip_unless_tool(h.RISCV_CC, h.QEMU)
class VictimUnderQemu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = h.fake_clock_build(N)
        cls.analysis = h.load_analysis()

    def run_victim(self, name, seed=SEED):
        return h.qemu_run(self.build / name, seed)

    def checksums(self, tvla):
        a = self.analysis
        fixed = a.hex16("da39a3ee5e6b4b0d3255bfef95601890")
        pts = a.plaintexts(SEED, N, tvla_fixed=fixed if tvla else None)
        cts = a.aes_encrypt_trace(pts, a.key_expansion(a.hex16(KEY)))[0]
        return (bytes(np.bitwise_xor.reduce(pts, axis=0)).hex(),
                bytes(np.bitwise_xor.reduce(cts, axis=0)).hex())

    def header(self, rounds1, scrub, tvla):
        return ("victim leak_format=v1 key=%s seed=%d windows=%d rounds1=%d "
                "scrub=%d tvla=%d" % (KEY, SEED, N, rounds1, scrub, tvla))

    def check(self, name, rounds1, scrub, tvla):
        proc = self.run_victim(name)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertIn("victim aes_self_test=PASS", lines)
        self.assertIn(self.header(rounds1, scrub, tvla), lines)
        pt_sum, ct_sum = self.checksums(tvla)
        if rounds1:
            ct_sum = "00" * 16          # no ciphertext is computed in r1 mode
        self.assertIn("victim pt_checksum=%s ct_checksum=%s" % (pt_sum, ct_sum),
                      lines)

    def test_full_aes_with_scrub(self):
        self.check("victim_leak_full_scrub", 0, 1, 0)

    def test_full_aes_without_scrub(self):
        self.check("victim_leak_full_noscrub", 0, 0, 0)

    def test_round1_only_with_scrub(self):
        self.check("victim_leak_r1_scrub", 1, 1, 0)

    def test_round1_only_without_scrub(self):
        self.check("victim_leak_r1_noscrub", 1, 0, 0)

    def test_tvla_variant_uses_the_fixed_plaintext_on_even_windows(self):
        self.check("victim_leak_tvla", 0, 1, 1)

    def test_invalid_seed_is_rejected_with_exit_2(self):
        for bad in ("0", "abc", "-5", ""):
            proc = h.qemu_run(self.build / "victim_leak_full_scrub", bad)
            self.assertEqual(proc.returncode, 2, bad)
            self.assertIn("victim error=invalid_plaintext_seed", proc.stdout)

    def test_missing_seed_is_rejected_with_exit_2(self):
        proc = h.qemu_run(self.build / "victim_leak_full_scrub")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
