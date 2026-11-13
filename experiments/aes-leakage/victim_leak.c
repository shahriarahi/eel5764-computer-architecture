/*
 * victim_leak.c -- educational AES-128 T-table workload for the leakage
 * attribution experiment.  Simulator only: the key is a fixed PUBLIC test
 * constant (LEAK_KEY_INIT in leak_schedule.h, printed at start) and the
 * plaintexts are public and deterministic (splitmix64 of the argv seed).
 *
 * One WINDOW = one encryption at w0 + LEAK_OFF_ENC, where w0 = T0 + j * W.
 * Variants are chosen by compile flag (see build.sh):
 *   LEAK_ROUNDS1=1  only round 1's 16 table loads (positive control)
 *   LEAK_SCRUB=1    walk a private 4 KiB buffer first (LEAK_SCRUB_BYTES) so the table lookups
 *                   miss the 4 KiB L1D and reach the LLC
 *   LEAK_TVLA=1     even windows use the fixed plaintext (fixed-vs-random)
 */
#include <stdint.h>

#include "../../workloads/common.h"
#include "../../workloads/contention_common.h"
#include "aes_leak_ext.h"
#include "leak_schedule.h"

#ifndef LEAK_ROUNDS1
#define LEAK_ROUNDS1 0
#endif
#ifndef LEAK_SCRUB
#define LEAK_SCRUB 1
#endif
#ifndef LEAK_TVLA
#define LEAK_TVLA 0
#endif

#define CACHE_LINE_BYTES 64UL

/*
 * Size of the scrub walk.  The L1D is 4 KiB and 4-way (16 sets), so 64
 * consecutive lines put exactly 4 lines in every set and replace every line
 * under LRU: that is the smallest walk that flushes the tables.  Larger walks
 * only add LLC allocations.  In an unpartitioned LLC full of the monitor's own
 * lines each allocation evicts a monitor line, and the monitor's next prime
 * (same walk order) then misses on all 16 lines of that set, an LRU cascade.
 * An 8 KiB walk (128 lines) made the A=16 prime take about 476,000 cycles
 * against a 458,752-cycle budget in the P0 smoke run (runs/p0-r1-scrub-n20).
 */
#ifndef LEAK_SCRUB_BYTES
#define LEAK_SCRUB_BYTES 4096UL
#endif
#define SCRUB_BYTES LEAK_SCRUB_BYTES
_Static_assert(SCRUB_BYTES % CACHE_LINE_BYTES == 0 && SCRUB_BYTES >= 64,
               "the scrub walk is a whole number of cache lines");

static const uint8_t experiment_key[16] = LEAK_KEY_INIT;

#if LEAK_SCRUB
static volatile uint8_t scrub_buffer[SCRUB_BYTES]
    __attribute__((aligned(CACHE_LINE_BYTES)));
static volatile uint8_t scrub_sink;
#endif

static void put_hex(const uint8_t *bytes, unsigned int count)
{
    static const char digits[] = "0123456789abcdef";
    char text[33];
    for (unsigned int i = 0; i < count && i < 16; ++i) {
        text[2 * i] = digits[bytes[i] >> 4];
        text[2 * i + 1] = digits[bytes[i] & 0xfU];
    }
    text[2 * (count < 16 ? count : 16)] = '\0';
    put_str(text);
}

static int bytes_equal(const uint8_t *left, const uint8_t *right,
                       unsigned int count)
{
    for (unsigned int i = 0; i < count; ++i) {
        if (left[i] != right[i])
            return 0;
    }
    return 1;
}

/* FIPS-197 Appendix C.1, run through the same encrypt code as the windows. */
static int aes_known_answer_passes(void)
{
    static const uint8_t kat_key[16] = {
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
    };
    static const uint8_t plaintext[16] = {
        0x00, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77,
        0x88, 0x99, 0xaa, 0xbb, 0xcc, 0xdd, 0xee, 0xff,
    };
    static const uint8_t expected[16] = {
        0x69, 0xc4, 0xe0, 0xd8, 0x6a, 0x7b, 0x04, 0x30,
        0xd8, 0xcd, 0xb7, 0x80, 0x70, 0xb4, 0xc5, 0x5a,
    };
    uint32_t round_keys[AES128_ROUND_KEY_WORDS];
    uint8_t ciphertext[16];
    aes128_expand_key(kat_key, round_keys);
    aes128_encrypt_block(plaintext, ciphertext, round_keys);
    return bytes_equal(ciphertext, expected, 16);
}

static __attribute__((noreturn)) void deadline_error(const char *what,
                                                     unsigned int window)
{
    put_str("victim error=");
    put_str(what);
    put_str(" window=");
    put_u64(window);
    put_str("\n");
    sys_exit(2);
}

#if LEAK_SCRUB
/* 128 lines over the 16 sets of the 4-way L1D leave only the scrub buffer
 * resident, so the next table lookups miss L1D and go to the LLC. */
static void scrub_private_cache(void)
{
    unsigned int sum = 0;
    for (unsigned long offset = 0; offset < SCRUB_BYTES;
         offset += CACHE_LINE_BYTES)
        sum += scrub_buffer[offset];
    scrub_sink = (uint8_t)sum;
}
#endif

__attribute__((used, noreturn))
static void victim_main(unsigned long argc, char **argv)
{
    uint32_t round_keys[AES128_ROUND_KEY_WORDS];
    unsigned long seed = 0;

    if (argc != 2 || !contention_parse_seed(argv[1], &seed)) {
        put_str("victim error=invalid_plaintext_seed "
                "expected=positive_u64_decimal\n");
        sys_exit(2);
    }
    uint64_t plaintext_state = (uint64_t)seed;

    aes_ttable_init();
    if (!aes_known_answer_passes()) {
        put_str("victim aes_self_test=FAIL\n");
        sys_exit(2);
    }
    put_str("victim aes_self_test=PASS\n");
    aes128_expand_key(experiment_key, round_keys);

    put_str("victim leak_format=v1 key=");
    put_hex(experiment_key, 16);
    put_str(" ");
    put_kv("seed", seed);
    put_kv("windows", LEAK_N_WIN);
    put_kv("rounds1", LEAK_ROUNDS1);
    put_kv("scrub", LEAK_SCRUB);
    put_str("tvla=");
    put_u64(LEAK_TVLA);
    put_str("\n");

    if (leak_rdcycle() >= LEAK_T0) {
        put_str("victim error=missed_start\n");
        sys_exit(2);
    }

    uint8_t plaintext[16];
    uint8_t ciphertext[16] = {0};
    uint8_t pt_checksum[16] = {0};
    uint8_t ct_checksum[16] = {0};

    for (unsigned int window = 0; window < LEAK_N_WIN; ++window) {
        /* The public plaintext is computed before the window starts. */
        next_plaintext(&plaintext_state, window, LEAK_TVLA, leak_tvla_fixed_pt,
                       plaintext);
        const unsigned long w0 = LEAK_T0 + (unsigned long)window * LEAK_W;

        leak_wait_until(w0);
#if LEAK_SCRUB
        scrub_private_cache();
#endif
        if (leak_rdcycle() > w0 + LEAK_OFF_PRIME)
            deadline_error("prime_deadline", window);

        leak_wait_until(w0 + LEAK_OFF_ENC);
#if LEAK_ROUNDS1
        aes128_first_round_lookups(plaintext, round_keys);
#else
        aes128_encrypt_block(plaintext, ciphertext, round_keys);
#endif
        if (leak_rdcycle() > w0 + LEAK_OFF_ENC_END)
            deadline_error("encrypt_deadline", window);

        for (unsigned int i = 0; i < 16; ++i) {
            pt_checksum[i] ^= plaintext[i];
            ct_checksum[i] ^= ciphertext[i];
        }
    }

    /* Print only after the measurement window (and its statistics dump) so the
     * output system calls cannot touch a measured window. */
    leak_wait_until(LEAK_T0 + (unsigned long)LEAK_N_WIN * LEAK_W + LEAK_W / 4);
    put_str("victim pt_checksum=");
    put_hex(pt_checksum, 16);
    put_str(" ct_checksum=");
    put_hex(ct_checksum, 16);
    put_str("\n");

    leak_wait_until(LEAK_T0 + ((unsigned long)LEAK_N_WIN + 2UL) * LEAK_W);
    sys_exit(0);
}

/* Linux places argc and argv on the initial RISC-V stack. */
__attribute__((naked, noreturn)) void _start(void)
{
    __asm__ volatile(
        "ld a0, 0(sp)\n"
        "addi a1, sp, 8\n"
        "tail victim_main\n"
    );
}
