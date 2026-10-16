/*
 * Minimal freestanding runtime for gem5 RISC-V SE mode.
 *
 * The workloads are linked with -nostdlib because Ubuntu 26.04's static
 * glibc uses RVV fault-only-first loads that gem5 v25.1's TimingSimpleCPU
 * does not handle (it panics instead of trimming vl). Without libc, every
 * memory access in the trace comes from the workload itself.
 */
#ifndef WORKLOADS_COMMON_H
#define WORKLOADS_COMMON_H

/*
 * gem5's ELF loader panics on a segment whose file offset lies past EOF even
 * when its file size is 0 (src/base/loader/memory_image.hh:70). A workload
 * whose writable data is all .bss produces exactly that, so every workload
 * carries this one initialised word to give the RW segment file contents.
 */
__attribute__((used)) static volatile unsigned long rw_segment_anchor = 1;

#define SYS_WRITE 64
#define SYS_EXIT 93

static inline long sys3(long n, long a0, long a1, long a2)
{
    register long a7 __asm__("a7") = n;
    register long r0 __asm__("a0") = a0;
    register long r1 __asm__("a1") = a1;
    register long r2 __asm__("a2") = a2;
    __asm__ volatile("ecall" : "+r"(r0) : "r"(r1), "r"(r2), "r"(a7) : "memory");
    return r0;
}

static inline void put_str(const char *s)
{
    long n = 0;
    while (s[n])
        n++;
    sys3(SYS_WRITE, 1, (long)s, n);
}

static inline void put_u64(unsigned long v)
{
    char tmp[24];
    int k = 0;
    do {
        tmp[k++] = (char)('0' + v % 10);
        v /= 10;
    } while (v);
    char out[24];
    int n = 0;
    while (k)
        out[n++] = tmp[--k];
    sys3(SYS_WRITE, 1, (long)out, n);
}

static inline void put_kv(const char *key, unsigned long v)
{
    put_str(key);
    put_str("=");
    put_u64(v);
    put_str(" ");
}

static inline __attribute__((noreturn)) void sys_exit(int code)
{
    sys3(SYS_EXIT, code, 0, 0);
    for (;;) {
    }
}

#endif /* WORKLOADS_COMMON_H */
