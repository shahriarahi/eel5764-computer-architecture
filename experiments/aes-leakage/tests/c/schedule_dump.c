/* Host check of leak_schedule.h: prints constants and plaintext streams so
 * that tests/test_schedule.py can compare them with the Python reference. */
#include <stdio.h>
#include <stdlib.h>

#include "../../leak_schedule.h"

static void print_hex(const uint8_t *bytes, unsigned int count)
{
    for (unsigned int i = 0; i < count; ++i)
        printf("%02x", bytes[i]);
}

int main(int argc, char **argv)
{
    if (argc != 4) {
        fprintf(stderr, "usage: schedule_dump <seed> <windows> <tvla 0|1>\n");
        return 2;
    }
    uint64_t state = strtoull(argv[1], NULL, 0);
    unsigned int windows = (unsigned int)strtoul(argv[2], NULL, 0);
    int tvla = atoi(argv[3]);

    printf("T0=%lu W=%lu OFF_PRIME=%lu OFF_ENC=%lu OFF_ENC_END=%lu "
           "OFF_PROBE=%lu N_WIN=%lu\n",
           (unsigned long)LEAK_T0, (unsigned long)LEAK_W,
           (unsigned long)LEAK_OFF_PRIME, (unsigned long)LEAK_OFF_ENC,
           (unsigned long)LEAK_OFF_ENC_END, (unsigned long)LEAK_OFF_PROBE,
           (unsigned long)LEAK_N_WIN);

    {
        static const uint8_t key[16] = LEAK_KEY_INIT;
        printf("key=");
        print_hex(key, 16);
        printf("\n");
    }

    {
        uint64_t probe = 0;
        uint64_t first = splitmix64(&probe);
        uint64_t second = splitmix64(&probe);
        printf("splitmix_seed0=%016llx,%016llx\n",
               (unsigned long long)first, (unsigned long long)second);
    }

    for (unsigned int j = 0; j < windows; ++j) {
        uint8_t pt[16];
        next_plaintext(&state, j, tvla, leak_tvla_fixed_pt, pt);
        printf("pt %u ", j);
        print_hex(pt, 16);
        printf("\n");
    }
    return 0;
}
