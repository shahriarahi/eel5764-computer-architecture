/* Host harness for aes_leak_ext.c.  It #includes the .c file so it can see the
 * static tables, and checks:
 *   1. the FIPS-197 C.1 known-answer test through the paper's own encrypt code,
 *   2. that aes128_first_round_lookups() loads exactly the 16 round-1 table
 *      words (its sink equals the XOR of Te_(i%4)[p_i ^ k_i] over i),
 *   3. XOR-folded plaintext and ciphertext checksums over N windows, which
 *      tests/test_aes_ext.py compares with the numpy reference.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../../aes_leak_ext.c"
#include "../../leak_schedule.h"

static void print_hex(const uint8_t *bytes, unsigned int count)
{
    for (unsigned int i = 0; i < count; ++i)
        printf("%02x", bytes[i]);
}

static int kat_passes(void)
{
    static const uint8_t kat_key[16] = {
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f};
    static const uint8_t plaintext[16] = {
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
        0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff};
    static const uint8_t expected[16] = {
        0x69, 0xc4, 0xe0, 0xd8, 0x6a, 0x7b, 0x04, 0x30,
        0xd8, 0xcd, 0xb7, 0x80, 0x70, 0xb4, 0xc5, 0x5a};
    uint32_t rk[AES128_ROUND_KEY_WORDS];
    uint8_t out[16];
    aes128_expand_key(kat_key, rk);
    aes128_encrypt_block(plaintext, out, rk);
    return memcmp(out, expected, 16) == 0;
}

static uint32_t expected_round1_xor(const uint8_t pt[16], const uint8_t key[16])
{
    const uint32_t *tables[4] = {te0, te1, te2, te3};
    uint32_t acc = 0;
    for (unsigned int i = 0; i < 16; ++i)
        acc ^= tables[i % 4][(uint8_t)(pt[i] ^ key[i])];
    return acc;
}

int main(int argc, char **argv)
{
    if (argc != 4) {
        fprintf(stderr, "usage: aes_host_harness <seed> <windows> <tvla 0|1>\n");
        return 2;
    }
    uint64_t state = strtoull(argv[1], NULL, 0);
    const unsigned int windows = (unsigned int)strtoul(argv[2], NULL, 0);
    const int tvla = atoi(argv[3]);

    aes_ttable_init();
    printf("kat=%s\n", kat_passes() ? "PASS" : "FAIL");

    static const uint8_t key[16] = LEAK_KEY_INIT;
    uint32_t rk[AES128_ROUND_KEY_WORDS];
    aes128_expand_key(key, rk);

    uint8_t pt_fold[16] = {0};
    uint8_t ct_fold[16] = {0};
    int round1_ok = 1;
    for (unsigned int j = 0; j < windows; ++j) {
        uint8_t pt[16], ct[16];
        next_plaintext(&state, j, tvla, leak_tvla_fixed_pt, pt);
        aes128_encrypt_block(pt, ct, rk);

        leak_round1_sink = 0;
        aes128_first_round_lookups(pt, rk);
        if (leak_round1_sink != expected_round1_xor(pt, key))
            round1_ok = 0;

        for (unsigned int b = 0; b < 16; ++b) {
            pt_fold[b] ^= pt[b];
            ct_fold[b] ^= ct[b];
        }
        if (j < 3) {
            printf("ct %u ", j);
            print_hex(ct, 16);
            printf("\n");
        }
    }
    printf("round1_lookups=%s\n", round1_ok ? "PASS" : "FAIL");
    printf("pt_checksum=");
    print_hex(pt_fold, 16);
    printf("\nct_checksum=");
    print_hex(ct_fold, 16);
    printf("\n");
    return 0;
}
