#include <stdio.h>

#include "../workloads/contention_common.h"

#ifndef EXPECTED_EPOCH_CYCLES
#define EXPECTED_EPOCH_CYCLES 1000000UL
#endif

int main(void)
{
    unsigned int active = 0;
    unsigned int idle = 0;
    unsigned int probe_ways = 0;
    unsigned long workload_seed = 0;

    if (!contention_parse_probe_ways("1", &probe_ways) || probe_ways != 1 ||
        !contention_parse_probe_ways("16", &probe_ways) || probe_ways != 16 ||
        contention_parse_probe_ways("0", &probe_ways) ||
        contention_parse_probe_ways("17", &probe_ways) ||
        contention_parse_probe_ways("4x", &probe_ways)) {
        fputs("monitor way parser failed\n", stderr);
        return 1;
    }

    if (!contention_parse_seed("1466213861", &workload_seed) ||
        workload_seed != 1466213861UL ||
        contention_parse_seed("0", &workload_seed) ||
        contention_parse_seed("-1", &workload_seed) ||
        contention_parse_seed("18446744073709551616", &workload_seed) ||
        contention_parse_seed("12x", &workload_seed)) {
        fputs("workload seed parser failed\n", stderr);
        return 1;
    }

    if (CONTENTION_INTERVAL_COUNT != 64 || CONTENTION_START_CYCLE != 2000000UL ||
        CONTENTION_EPOCH_CYCLES != EXPECTED_EPOCH_CYCLES) {
        fputs("contention timing constants changed\n", stderr);
        return 1;
    }
    for (unsigned int i = 0; i < CONTENTION_INTERVAL_COUNT; ++i) {
        if (contention_activity_labels[i] == 1)
            ++active;
        else if (contention_activity_labels[i] == 0)
            ++idle;
        else {
            fputs("non-binary activity label\n", stderr);
            return 1;
        }
    }
    if (active != 32 || idle != 32) {
        fprintf(stderr, "unbalanced schedule: active=%u idle=%u\n", active, idle);
        return 1;
    }
    puts("contention schedule PASS: 32 active, 32 idle");
    return 0;
}
