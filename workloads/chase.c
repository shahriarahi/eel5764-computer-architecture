/*
 * chase: dependent pointer chase over a fixed working set (core 0).
 *
 * The working set is WS_BYTES of 64-byte lines linked into a single random
 * cycle (Sattolo's algorithm, fixed LCG seed), so every load depends on the
 * previous one and the visit order is identical in every run. Its IPC is
 * therefore governed by where the lines live (L1 / LLC / DRAM), which is
 * what LLC way allocation changes. Runs forever; gem5 ends the simulation.
 */
#include "common.h"

#ifndef WS_BYTES
#define WS_BYTES (96 * 1024)
#endif
#ifndef SEED
#define SEED 12345UL
#endif

#define LINE 64
#define NLINES (WS_BYTES / LINE)

struct line {
    struct line *next;
    unsigned long pad[LINE / sizeof(unsigned long) - 1];
};

static struct line lines[NLINES] __attribute__((aligned(LINE)));
static unsigned int order[NLINES];

static unsigned long lcg_state = SEED;

static unsigned long lcg(void)
{
    /* Knuth MMIX constants. */
    lcg_state = lcg_state * 6364136223846793005UL + 1442695040888963407UL;
    return lcg_state >> 33;
}

void _start(void)
{
    /* Sattolo shuffle yields a single cycle covering every line. */
    for (unsigned int i = 0; i < NLINES; i++)
        order[i] = i;
    for (unsigned int i = NLINES - 1; i > 0; i--) {
        unsigned int j = (unsigned int)(lcg() % i);
        unsigned int t = order[i];
        order[i] = order[j];
        order[j] = t;
    }
    for (unsigned int i = 0; i < NLINES; i++)
        lines[order[i]].next = &lines[order[(i + 1) % NLINES]];

    put_str("chase ");
    put_kv("ws_bytes", WS_BYTES);
    put_kv("lines", NLINES);
    put_kv("seed", SEED);
    put_str("\n");

    struct line *p = &lines[order[0]];
    for (;;) {
        for (unsigned int i = 0; i < NLINES; i++)
            p = p->next;
        /* Keep the chase observable so it cannot be optimised away. */
        __asm__ volatile("" : : "r"(p) : "memory");
    }
}
