#ifndef AES_LEAK_EXT_H
#define AES_LEAK_EXT_H

#include <stdint.h>

#include "../../workloads/aes_ttable.h"

/* XOR of the 16 words loaded by the last aes128_first_round_lookups() call. */
extern volatile uint32_t leak_round1_sink;

/* Performs exactly round 1's 16 table loads (no later rounds, no ciphertext). */
void aes128_first_round_lookups(const uint8_t input[16],
                                const uint32_t round_keys[AES128_ROUND_KEY_WORDS]);

#endif /* AES_LEAK_EXT_H */
