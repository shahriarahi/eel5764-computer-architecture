#ifndef WORKLOADS_AES_TTABLE_H
#define WORKLOADS_AES_TTABLE_H

#include <stdint.h>

#define AES128_ROUND_KEY_WORDS 44

void aes_ttable_init(void);
void aes128_expand_key(const uint8_t key[16],
                       uint32_t round_keys[AES128_ROUND_KEY_WORDS]);
void aes128_encrypt_block(const uint8_t input[16], uint8_t output[16],
                          const uint32_t round_keys[AES128_ROUND_KEY_WORDS]);

#endif /* WORKLOADS_AES_TTABLE_H */
