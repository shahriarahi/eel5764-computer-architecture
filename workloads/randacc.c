/*
 * randacc: uniform random line accesses over a fixed working set (core 0).
 *
 * Each iteration draws a line index from a fixed-seed LCG and loads one word
 * from that 64-byte line. Unlike a fixed cyclic traversal (chase.c), whose
 * LRU hit rate is all-or-nothing, uniform random reuse gives an LLC hit rate
 * that grows roughly with (allocated capacity / working set), so IPC varies
 * smoothly with the number of LLC ways. The access sequence is identical in
 * every run. Runs forever; gem5 ends the simulation.
 */
#include "common.h"

#ifndef WS_BYTES
#define WS_BYTES (128 * 1024)
#endif
#ifndef SEED
#define SEED 12345UL
#endif

#define LINE 64
#define NLINES (WS_BYTES / LINE)
#define WORDS_PER_LINE (LINE / sizeof(unsigned long))

static unsigned long data[NLINES * WORDS_PER_LINE]
    __attribute__((aligned(LINE)));

static unsigned long lcg_state = SEED;

static inline unsigned long lcg(void)
{
    /* Knuth MMIX constants; the high 32 bits are the best-distributed. */
    lcg_state = lcg_state * 6364136223846793005UL + 1442695040888963407UL;
    return lcg_state >> 32;
}

void _start(void)
{
    /* Write every line once so the working set is real, dirty-free data. */
    for (unsigned long i = 0; i < NLINES; i++)
        data[i * WORDS_PER_LINE] = i;

    put_str("randacc ");
    put_kv("ws_bytes", WS_BYTES);
    put_kv("lines", NLINES);
    put_kv("seed", SEED);
    put_str("\n");

    const volatile unsigned long *vdata = data;
    unsigned long sum = 0;
    for (;;) {
        /* Multiply-shift maps a 32-bit draw onto [0, NLINES) without '%'. */
        unsigned long idx = (lcg() * NLINES) >> 32;
        sum += vdata[idx * WORDS_PER_LINE];
        __asm__ volatile("" : : "r"(sum) : "memory");
    }
}
