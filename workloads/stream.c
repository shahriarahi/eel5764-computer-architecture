/*
 * stream: sequential read sweep over a buffer much larger than the LLC
 * (core 1). One load per 64-byte line, so it has almost no reuse and
 * continuously inserts new blocks into the shared LLC: the classic
 * cache-polluting co-runner. Runs forever; gem5 ends the simulation.
 */
#include "common.h"

#ifndef BUF_BYTES
#define BUF_BYTES (1024 * 1024)
#endif

#define LINE 64

static unsigned char buf[BUF_BYTES] __attribute__((aligned(LINE)));

void _start(void)
{
    put_str("stream ");
    put_kv("buf_bytes", BUF_BYTES);
    put_kv("lines", BUF_BYTES / LINE);
    put_str("\n");

    /* buf is never written, so without volatile GCC folds every load to a
     * constant zero and the loop touches no memory at all. */
    const volatile unsigned char *vbuf = buf;
    unsigned long sum = 0;
    for (;;) {
        for (unsigned long i = 0; i < BUF_BYTES; i += LINE)
            sum += vbuf[i];
        __asm__ volatile("" : : "r"(sum) : "memory");
    }
}
