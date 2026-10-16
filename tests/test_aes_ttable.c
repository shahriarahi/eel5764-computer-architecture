#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "../workloads/aes_ttable.h"

int main(void)
{
    static const uint8_t key[16] = {
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

    aes_ttable_init();
    aes128_expand_key(key, round_keys);
    aes128_encrypt_block(plaintext, ciphertext, round_keys);
    if (memcmp(ciphertext, expected, sizeof(expected)) != 0) {
        fputs("AES-128 known-answer mismatch\n", stderr);
        return 1;
    }
    puts("AES-128 T-table known-answer PASS");
    return 0;
}
