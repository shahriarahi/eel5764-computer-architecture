/*
 * aes_leak_ext.c -- the paper's T-table AES plus a round-1-only lookup mode.
 *
 * The frozen workloads/aes_ttable.c is #included (not copied), so
 * aes128_encrypt_block() is the paper's source text.  The tables are static,
 * which is why the extension must live in the same translation unit.
 * Build victim_leak.c with THIS file instead of workloads/aes_ttable.c; linking
 * both would define every AES symbol twice.
 */
#include "../../workloads/aes_ttable.c"

#include "aes_leak_ext.h"

volatile uint32_t leak_round1_sink;

/*
 * Exactly round 1's 16 table loads: byte i of the state (p_i ^ k_i) indexes
 * Te_(i % 4), in the same expressions as the first iteration of the loop in
 * aes128_encrypt_block().  The XOR of the loaded words is stored to a volatile
 * sink so no load can be removed.  This is the positive-control mode (P0/P1):
 * only the first-round lookups reach the cache.
 */
void aes128_first_round_lookups(const uint8_t input[16],
                                const uint32_t round_keys[AES128_ROUND_KEY_WORDS])
{
    const uint32_t s0 = load_be32(&input[0]) ^ round_keys[0];
    const uint32_t s1 = load_be32(&input[4]) ^ round_keys[1];
    const uint32_t s2 = load_be32(&input[8]) ^ round_keys[2];
    const uint32_t s3 = load_be32(&input[12]) ^ round_keys[3];

    uint32_t acc = te0[s0 >> 24] ^ te1[(s1 >> 16) & 0xffU] ^
                   te2[(s2 >> 8) & 0xffU] ^ te3[s3 & 0xffU];
    acc ^= te0[s1 >> 24] ^ te1[(s2 >> 16) & 0xffU] ^
           te2[(s3 >> 8) & 0xffU] ^ te3[s0 & 0xffU];
    acc ^= te0[s2 >> 24] ^ te1[(s3 >> 16) & 0xffU] ^
           te2[(s0 >> 8) & 0xffU] ^ te3[s1 & 0xffU];
    acc ^= te0[s3 >> 24] ^ te1[(s0 >> 16) & 0xffU] ^
           te2[(s1 >> 8) & 0xffU] ^ te3[s2 & 0xffU];
    leak_round1_sink = acc;
}
