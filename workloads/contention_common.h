#ifndef WORKLOADS_CONTENTION_COMMON_H
#define WORKLOADS_CONTENTION_COMMON_H

#define CONTENTION_START_CYCLE 2000000UL
#ifndef CONTENTION_EPOCH_CYCLES
#define CONTENTION_EPOCH_CYCLES 1000000UL
#endif
#define CONTENTION_INTERVAL_COUNT 64
#define CONTENTION_LLC_SETS 256
#define CONTENTION_LLC_WAYS 16
#define CONTENTION_PROBE_OFFSET_CYCLES (CONTENTION_EPOCH_CYCLES / 2)
#define CONTENTION_LOGGING_GRACE_CYCLES 20000000UL

/* Fixed public schedule: non-alternating and exactly 32 active / 32 idle. */
static const unsigned char
contention_activity_labels[CONTENTION_INTERVAL_COUNT] = {
    0, 1, 1, 0, 1, 0, 0, 1,
    1, 0, 1, 1, 0, 0, 1, 0,
    0, 0, 1, 1, 0, 1, 1, 0,
    1, 1, 0, 0, 1, 0, 0, 1,
    0, 1, 0, 1, 1, 0, 1, 0,
    1, 0, 0, 1, 0, 1, 1, 0,
    0, 1, 1, 0, 0, 1, 0, 1,
    1, 0, 1, 0, 1, 1, 0, 0,
};

static inline int
contention_parse_probe_ways(const char *text, unsigned int *ways_out)
{
    unsigned int value = 0;
    if (text == 0 || *text == '\0')
        return 0;
    for (const char *cursor = text; *cursor != '\0'; ++cursor) {
        if (*cursor < '0' || *cursor > '9')
            return 0;
        value = value * 10U + (unsigned int)(*cursor - '0');
        if (value > CONTENTION_LLC_WAYS)
            return 0;
    }
    if (value == 0)
        return 0;
    *ways_out = value;
    return 1;
}

static inline int
contention_parse_seed(const char *text, unsigned long *seed_out)
{
    unsigned long value = 0;
    if (text == 0 || *text == '\0')
        return 0;
    for (const char *cursor = text; *cursor != '\0'; ++cursor) {
        unsigned long digit;
        if (*cursor < '0' || *cursor > '9')
            return 0;
        digit = (unsigned long)(*cursor - '0');
        if (value > (~0UL - digit) / 10UL)
            return 0;
        value = value * 10UL + digit;
    }
    if (value == 0)
        return 0;
    *seed_out = value;
    return 1;
}

#if defined(__riscv)
static inline unsigned long contention_rdcycle(void)
{
    unsigned long value;
    __asm__ volatile("rdcycle %0" : "=r"(value) : : "memory");
    return value;
}
#endif

#endif /* WORKLOADS_CONTENTION_COMMON_H */
