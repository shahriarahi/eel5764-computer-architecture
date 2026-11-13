/*
 * leak_schedule.h -- window schedule, public key and plaintext stream for the
 * AES leakage-attribution experiment (simulator only, public test key).
 *
 * One WINDOW is: monitor primes its own lines -> the AES workload performs
 * exactly one encryption -> the monitor re-times its lines.  All offsets are
 * CPU cycles relative to the window start w0 = T0 + j * W.  This header is the
 * single source of the schedule: leak_params.py parses it for Python and
 * tests/test_schedule.py checks the C and Python plaintext streams agree.
 *
 * Name mapping to the task text: T0 -> LEAK_T0, W -> LEAK_W, OFF_* ->
 * LEAK_OFF_*; N_WIN is the -D knob and is exposed unprefixed.  Prefixes keep
 * short names like W out of the macro namespace of the shared workload headers.
 */
#ifndef LEAK_SCHEDULE_H
#define LEAK_SCHEDULE_H

#include <stdint.h>

/* Measurement starts at the end of the 1e9-tick (2,000,000-cycle) warm-up. */
#define LEAK_T0 2000000UL
#define LEAK_W 1048576UL

#ifndef LEAK_OFF_PRIME
#define LEAK_OFF_PRIME 65536UL
#endif
#ifndef LEAK_OFF_ENC
#define LEAK_OFF_ENC 524288UL
#endif
#ifndef LEAK_OFF_ENC_END
#define LEAK_OFF_ENC_END (LEAK_OFF_ENC + 65536UL)
#endif
#ifndef LEAK_OFF_PROBE
#define LEAK_OFF_PROBE (LEAK_OFF_ENC_END + 4096UL)
#endif

/* Number of windows; the monitor's interval field is 16 bits wide. */
#ifndef N_WIN
#define N_WIN 2000
#endif
#define LEAK_N_WIN N_WIN
#define LEAK_N_WIN_MAX 65535UL
#define LEAK_NSETS 256UL

_Static_assert(LEAK_N_WIN >= 1 && LEAK_N_WIN <= LEAK_N_WIN_MAX,
               "N_WIN must be 1..65535 (probe_bin_v2 interval is a u16)");
_Static_assert(LEAK_OFF_PRIME < LEAK_OFF_ENC, "prime must precede encryption");
_Static_assert(LEAK_OFF_ENC < LEAK_OFF_ENC_END, "encryption budget is empty");
_Static_assert(LEAK_OFF_PROBE < LEAK_W, "probe must start inside the window");
#ifndef LEAK_ALLOW_OVERLAP
/* Default schedule: no victim traffic overlaps the monitor's probe pass.
 * Define LEAK_ALLOW_OVERLAP only for a preregistered overlap variant. */
_Static_assert(LEAK_OFF_ENC_END < LEAK_OFF_PROBE,
               "encryption must finish before the probe starts");
#endif

/* Fixed PUBLIC test key.  Every upper nibble is nonzero, so (p ^ k) >> 4 and
 * p >> 4 differ at all 16 bytes (the paper's key 000102..0f cannot tell them
 * apart). */
#define LEAK_KEY_INIT \
    {0xf1, 0xe2, 0xd3, 0xc4, 0xb5, 0xa6, 0x97, 0x88, \
     0x79, 0x6a, 0x5b, 0x4c, 0x3d, 0x2e, 0x1f, 0x10}

/* TVLA fixed plaintext: the first 16 bytes of SHA-1("") -- an arbitrary
 * public constant. */
#define LEAK_TVLA_FIXED_PT_INIT \
    {0xda, 0x39, 0xa3, 0xee, 0x5e, 0x6b, 0x4b, 0x0d, \
     0x32, 0x55, 0xbf, 0xef, 0x95, 0x60, 0x18, 0x90}

static const uint8_t leak_tvla_fixed_pt[16] = LEAK_TVLA_FIXED_PT_INIT;

/* ---- clock -------------------------------------------------------------- */
#if defined(LEAK_FAKE_CLOCK)
/* qemu-user cannot provide a meaningful cycle counter: every call returns a
 * strictly larger value so that wait_until() loops terminate. */
#ifndef LEAK_FAKE_CLOCK_STEP
#define LEAK_FAKE_CLOCK_STEP 16UL
#endif
static unsigned long leak_fake_now;
static inline unsigned long leak_rdcycle(void)
{
    leak_fake_now += LEAK_FAKE_CLOCK_STEP;
    return leak_fake_now;
}
#elif defined(__riscv)
static inline unsigned long leak_rdcycle(void)
{
    unsigned long value;
    __asm__ volatile("rdcycle %0" : "=r"(value) : : "memory");
    return value;
}
#else
#error "leak_rdcycle needs RISC-V or -DLEAK_FAKE_CLOCK"
#endif

static inline void leak_wait_until(unsigned long target)
{
    unsigned long now;
    while ((now = leak_rdcycle()) < target)
        __asm__ volatile("" : : "r"(now) : "memory");
}

/* ---- public plaintext stream (splitmix64) ------------------------------- */
static inline uint64_t splitmix64(uint64_t *state)
{
    uint64_t z = (*state += 0x9E3779B97F4A7C15ULL);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ULL;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBULL;
    return z ^ (z >> 31);
}

/*
 * Plaintext of window j: two draws (lo, hi), little-endian bytes lo then hi.
 * In TVLA mode even windows use the fixed plaintext, but both words are still
 * drawn so the random stream stays aligned with the non-TVLA run.
 */
static inline void next_plaintext(uint64_t *state, unsigned int j, int tvla,
                                  const uint8_t fixed[16], uint8_t pt[16])
{
    const uint64_t lo = splitmix64(state);
    const uint64_t hi = splitmix64(state);
    for (unsigned int b = 0; b < 8; ++b) {
        pt[b] = (uint8_t)(lo >> (8 * b));
        pt[8 + b] = (uint8_t)(hi >> (8 * b));
    }
    if (tvla && (j % 2U) == 0U) {
        for (unsigned int b = 0; b < 16; ++b)
            pt[b] = fixed[b];
    }
}

#endif /* LEAK_SCHEDULE_H */
