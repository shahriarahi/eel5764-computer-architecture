/* Separate quiet negative control; the original AES victim is unchanged. */
#include <stdint.h>

#include "aes_ttable.h"
#include "common.h"
#include "contention_common.h"

static const uint8_t public_key[16] = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
};

static unsigned long plaintext_state;

static int bytes_equal(const uint8_t *left, const uint8_t *right,
                       unsigned int count)
{
    for (unsigned int i = 0; i < count; ++i) {
        if (left[i] != right[i])
            return 0;
    }
    return 1;
}

static int aes_known_answer_passes(void)
{
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
    aes128_expand_key(public_key, round_keys);
    aes128_encrypt_block(plaintext, ciphertext, round_keys);
    return bytes_equal(ciphertext, expected, 16);
}

static void print_schedule(void)
{
    for (unsigned int i = 0; i < CONTENTION_INTERVAL_COUNT; ++i)
        put_u64(contention_activity_labels[i]);
}

__attribute__((used, noreturn))
static void victim_main(unsigned long argc, char **argv)
{
    uint32_t round_keys[AES128_ROUND_KEY_WORDS];

    if (argc != 2 || !contention_parse_seed(argv[1], &plaintext_state)) {
        put_str("victim error=invalid_plaintext_seed expected=positive_u64_decimal\n");
        sys_exit(2);
    }
    aes_ttable_init();
    if (!aes_known_answer_passes()) {
        put_str("victim aes_self_test=FAIL\n");
        sys_exit(2);
    }
    aes128_expand_key(public_key, round_keys);
    put_str("victim aes_self_test=PASS key=000102030405060708090a0b0c0d0e0f ");
    put_kv("plaintext_seed", plaintext_state);
    put_str("labels=");
    print_schedule();
    put_str("\n");
    put_str("victim quiet_control=1 aes_self_test_scope=startup nominal_labels=1\n");

    unsigned long now = contention_rdcycle();
    if (now >= CONTENTION_START_CYCLE) {
        put_str("victim error=missed_start\n");
        sys_exit(2);
    }

    /* This one loop begins in warmup and crosses every ROI boundary unchanged.
     * Inspect the compiled loop for loads/stores; validate zero victim traffic
     * separately in simulation. Source alone does not establish cache silence.
     */
    const unsigned long measurement_end = CONTENTION_START_CYCLE +
        CONTENTION_INTERVAL_COUNT * CONTENTION_EPOCH_CYCLES;
    while ((now = contention_rdcycle()) < measurement_end)
        __asm__ volatile("" : : "r"(now) : "memory");

    put_str("victim measurement_complete ");
    put_kv("encryptions", 0);
    put_kv("sink", 0);
    put_str("quiet_control=1\n");
    const unsigned long exit_cycle = measurement_end +
        CONTENTION_LOGGING_GRACE_CYCLES;
    while ((now = contention_rdcycle()) < exit_cycle)
        __asm__ volatile("" : : "r"(now) : "memory");
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
