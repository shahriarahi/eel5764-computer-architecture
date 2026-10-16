#include "aes_ttable.h"

#define ALIGN_CACHE_LINE __attribute__((aligned(64)))

/* Four conventional 256-entry, 32-bit AES encryption T-tables (1 KiB each). */
static uint32_t te0[256] ALIGN_CACHE_LINE;
static uint32_t te1[256] ALIGN_CACHE_LINE;
static uint32_t te2[256] ALIGN_CACHE_LINE;
static uint32_t te3[256] ALIGN_CACHE_LINE;
static uint8_t sbox[256] ALIGN_CACHE_LINE;

static uint8_t xtime(uint8_t value)
{
    return (uint8_t)((value << 1) ^ ((value >> 7) * 0x1bU));
}

static uint8_t gf_multiply(uint8_t left, uint8_t right)
{
    uint8_t result = 0;
    while (right != 0) {
        if ((right & 1U) != 0)
            result ^= left;
        left = xtime(left);
        right >>= 1;
    }
    return result;
}

static uint8_t gf_power(uint8_t value, unsigned int exponent)
{
    uint8_t result = 1;
    while (exponent != 0) {
        if ((exponent & 1U) != 0)
            result = gf_multiply(result, value);
        value = gf_multiply(value, value);
        exponent >>= 1;
    }
    return result;
}

static uint8_t rotate_left8(uint8_t value, unsigned int shift)
{
    return (uint8_t)((value << shift) | (value >> (8U - shift)));
}

static uint32_t load_be32(const uint8_t *bytes)
{
    return ((uint32_t)bytes[0] << 24) | ((uint32_t)bytes[1] << 16) |
           ((uint32_t)bytes[2] << 8) | (uint32_t)bytes[3];
}

static void store_be32(uint8_t *bytes, uint32_t value)
{
    bytes[0] = (uint8_t)(value >> 24);
    bytes[1] = (uint8_t)(value >> 16);
    bytes[2] = (uint8_t)(value >> 8);
    bytes[3] = (uint8_t)value;
}

static uint32_t rotate_word(uint32_t value)
{
    return (value << 8) | (value >> 24);
}

static uint32_t substitute_word(uint32_t value)
{
    return ((uint32_t)sbox[value >> 24] << 24) |
           ((uint32_t)sbox[(value >> 16) & 0xffU] << 16) |
           ((uint32_t)sbox[(value >> 8) & 0xffU] << 8) |
           (uint32_t)sbox[value & 0xffU];
}

void aes_ttable_init(void)
{
    for (unsigned int i = 0; i < 256; ++i) {
        uint8_t inverse = (i == 0) ? 0 : gf_power((uint8_t)i, 254);
        uint8_t substituted = (uint8_t)(
            inverse ^ rotate_left8(inverse, 1) ^ rotate_left8(inverse, 2) ^
            rotate_left8(inverse, 3) ^ rotate_left8(inverse, 4) ^ 0x63U);
        uint8_t times_two = xtime(substituted);
        uint8_t times_three = (uint8_t)(times_two ^ substituted);
        sbox[i] = substituted;
        te0[i] = ((uint32_t)times_two << 24) |
                 ((uint32_t)substituted << 16) |
                 ((uint32_t)substituted << 8) | times_three;
        te1[i] = ((uint32_t)times_three << 24) |
                 ((uint32_t)times_two << 16) |
                 ((uint32_t)substituted << 8) | substituted;
        te2[i] = ((uint32_t)substituted << 24) |
                 ((uint32_t)times_three << 16) |
                 ((uint32_t)times_two << 8) | substituted;
        te3[i] = ((uint32_t)substituted << 24) |
                 ((uint32_t)substituted << 16) |
                 ((uint32_t)times_three << 8) | times_two;
    }
}

void aes128_expand_key(const uint8_t key[16],
                       uint32_t round_keys[AES128_ROUND_KEY_WORDS])
{
    uint8_t round_constant = 1;
    for (unsigned int i = 0; i < 4; ++i)
        round_keys[i] = load_be32(&key[4 * i]);
    for (unsigned int i = 4; i < AES128_ROUND_KEY_WORDS; ++i) {
        uint32_t temporary = round_keys[i - 1];
        if ((i & 3U) == 0) {
            temporary = substitute_word(rotate_word(temporary)) ^
                        ((uint32_t)round_constant << 24);
            round_constant = xtime(round_constant);
        }
        round_keys[i] = round_keys[i - 4] ^ temporary;
    }
}

void aes128_encrypt_block(const uint8_t input[16], uint8_t output[16],
                          const uint32_t round_keys[AES128_ROUND_KEY_WORDS])
{
    uint32_t s0 = load_be32(&input[0]) ^ round_keys[0];
    uint32_t s1 = load_be32(&input[4]) ^ round_keys[1];
    uint32_t s2 = load_be32(&input[8]) ^ round_keys[2];
    uint32_t s3 = load_be32(&input[12]) ^ round_keys[3];

    for (unsigned int round = 1; round < 10; ++round) {
        uint32_t t0 = te0[s0 >> 24] ^ te1[(s1 >> 16) & 0xffU] ^
                      te2[(s2 >> 8) & 0xffU] ^ te3[s3 & 0xffU] ^
                      round_keys[4 * round];
        uint32_t t1 = te0[s1 >> 24] ^ te1[(s2 >> 16) & 0xffU] ^
                      te2[(s3 >> 8) & 0xffU] ^ te3[s0 & 0xffU] ^
                      round_keys[4 * round + 1];
        uint32_t t2 = te0[s2 >> 24] ^ te1[(s3 >> 16) & 0xffU] ^
                      te2[(s0 >> 8) & 0xffU] ^ te3[s1 & 0xffU] ^
                      round_keys[4 * round + 2];
        uint32_t t3 = te0[s3 >> 24] ^ te1[(s0 >> 16) & 0xffU] ^
                      te2[(s1 >> 8) & 0xffU] ^ te3[s2 & 0xffU] ^
                      round_keys[4 * round + 3];
        s0 = t0;
        s1 = t1;
        s2 = t2;
        s3 = t3;
    }

    uint32_t t0 = ((uint32_t)sbox[s0 >> 24] << 24) |
                  ((uint32_t)sbox[(s1 >> 16) & 0xffU] << 16) |
                  ((uint32_t)sbox[(s2 >> 8) & 0xffU] << 8) |
                  (uint32_t)sbox[s3 & 0xffU];
    uint32_t t1 = ((uint32_t)sbox[s1 >> 24] << 24) |
                  ((uint32_t)sbox[(s2 >> 16) & 0xffU] << 16) |
                  ((uint32_t)sbox[(s3 >> 8) & 0xffU] << 8) |
                  (uint32_t)sbox[s0 & 0xffU];
    uint32_t t2 = ((uint32_t)sbox[s2 >> 24] << 24) |
                  ((uint32_t)sbox[(s3 >> 16) & 0xffU] << 16) |
                  ((uint32_t)sbox[(s0 >> 8) & 0xffU] << 8) |
                  (uint32_t)sbox[s1 & 0xffU];
    uint32_t t3 = ((uint32_t)sbox[s3 >> 24] << 24) |
                  ((uint32_t)sbox[(s0 >> 16) & 0xffU] << 16) |
                  ((uint32_t)sbox[(s1 >> 8) & 0xffU] << 8) |
                  (uint32_t)sbox[s2 & 0xffU];
    store_be32(&output[0], t0 ^ round_keys[40]);
    store_be32(&output[4], t1 ^ round_keys[41]);
    store_be32(&output[8], t2 ^ round_keys[42]);
    store_be32(&output[12], t3 ^ round_keys[43]);
}
