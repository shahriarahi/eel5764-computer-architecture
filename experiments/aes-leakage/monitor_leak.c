/*
 * monitor_leak.c -- simulator-only Prime+Probe-style monitor of its OWN cache
 * lines, one window per AES encryption.
 *
 * Derived from workloads/monitor.c (MONITOR_PROBE_SINK_FILE +
 * MONITOR_HOT_STATE_IN_REGISTERS path) and keeping its measurement safeguards:
 *   - probe chains are walked from registers (way count and fd are read once);
 *   - each result is stored in the spare bytes of the probe line that was just
 *     walked (an L1D hit), so the monitor allocates no new LLC line while
 *     measuring;
 *   - one writev() hands all 256 results of a window to the simulator, which
 *     reads them functionally (no cache effect);
 *   - a missed deadline exits with status 2 and an error line.
 * The symbol name probe_lines is kept: configs/run_contention.py finds it with
 * nm.  Output is probe_bin_v2: 16-byte little-endian records
 * {u64 timestamp, u32 latency, u16 interval, u16 cache_set}, 256 per window.
 */
#include <stdint.h>

#include "../../workloads/common.h"
#include "../../workloads/contention_common.h"
#include "leak_schedule.h"

#define CACHE_LINE_BYTES 64

_Static_assert(CONTENTION_LLC_SETS == LEAK_NSETS,
               "monitor and schedule disagree on the number of LLC sets");

struct probe_line {
    volatile uintptr_t next;
    unsigned char padding[CACHE_LINE_BYTES - sizeof(uintptr_t)];
};

_Static_assert(sizeof(struct probe_line) == CACHE_LINE_BYTES,
               "one probe node must occupy one cache line");

static struct probe_line
probe_lines[CONTENTION_LLC_WAYS][CONTENTION_LLC_SETS]
    __attribute__((aligned(CACHE_LINE_BYTES)));

struct probe_slot {
    unsigned long timestamp;
    unsigned int latency;
    unsigned short interval;
    unsigned short cache_set;
} __attribute__((may_alias));

struct sink_iovec {
    void *base;
    unsigned long length;
};

_Static_assert(sizeof(struct probe_slot) == 16, "probe slot is 16 bytes");
_Static_assert(sizeof(struct probe_slot) <= CACHE_LINE_BYTES - sizeof(uintptr_t),
               "probe slot must fit in a probe line's padding");

#define SYS_OPENAT 56
#define SYS_CLOSE 57
#define SYS_WRITEV 66
#define SINK_AT_FDCWD (-100L)
#define SINK_OPEN_FLAGS (01L | 0100L | 01000L) /* O_WRONLY|O_CREAT|O_TRUNC */
#define SINK_WINDOW_BYTES \
    ((long)(CONTENTION_LLC_SETS * sizeof(struct probe_slot)))

static struct sink_iovec sink_iov[CONTENTION_LLC_SETS];
static long sink_fd;
static unsigned int probe_way_count;

static inline long sys4(long n, long a0, long a1, long a2, long a3)
{
    register long a7 __asm__("a7") = n;
    register long r0 __asm__("a0") = a0;
    register long r1 __asm__("a1") = a1;
    register long r2 __asm__("a2") = a2;
    register long r3 __asm__("a3") = a3;
    __asm__ volatile("ecall"
                     : "+r"(r0)
                     : "r"(r1), "r"(r2), "r"(r3), "r"(a7)
                     : "memory");
    return r0;
}

static __attribute__((noreturn)) void monitor_error(const char *what,
                                                    unsigned int window)
{
    put_str("monitor error=");
    put_str(what);
    put_str(" window=");
    put_u64(window);
    put_str("\n");
    sys_exit(2);
}

static void initialize_probe_chains(void)
{
    for (unsigned int set = 0; set < CONTENTION_LLC_SETS; ++set) {
        for (unsigned int way = 0; way < probe_way_count; ++way) {
            unsigned int next_way = (way + 1) % probe_way_count;
            probe_lines[way][set].next =
                (uintptr_t)&probe_lines[next_way][set];
        }
    }
}

/* The way count is taken as a value so the measurement loop never re-reads the
 * global (its cache line would otherwise hold a monitor way in the LLC). */
static inline __attribute__((always_inline)) struct probe_line *
walk_set_ways(unsigned int set, unsigned int ways)
{
    struct probe_line *cursor = &probe_lines[0][set];
    for (unsigned int way = 0; way < ways; ++way)
        cursor = (struct probe_line *)cursor->next;
    __asm__ volatile("" : : "r"(cursor) : "memory");
    return cursor;
}

static void open_probe_sink(const char *path)
{
    sink_fd = sys4(SYS_OPENAT, SINK_AT_FDCWD, (long)path, SINK_OPEN_FLAGS,
                   0644L);
    if (sink_fd < 0) {
        put_str("monitor error=probe_sink_open\n");
        sys_exit(2);
    }
    for (unsigned int set = 0; set < CONTENTION_LLC_SETS; ++set) {
        /* The walk loads way A-1 last, so this line is L1D-resident. */
        sink_iov[set].base =
            probe_lines[probe_way_count - 1][set].padding;
        sink_iov[set].length = sizeof(struct probe_slot);
    }
}

__attribute__((used, noreturn))
static void monitor_main(unsigned long argc, char **argv)
{
    if (argc != 3 || !contention_parse_probe_ways(argv[1], &probe_way_count)) {
        put_str("monitor error=usage expected=<ways 1..16> <probe file>\n");
        sys_exit(2);
    }
    initialize_probe_chains();
    open_probe_sink(argv[2]);
    put_str("monitor format=probe_bin_v2 windows=");
    put_u64(LEAK_N_WIN);
    put_str(" sets=256 ways=");
    put_u64(probe_way_count);
    put_str("\n");

    if (leak_rdcycle() >= LEAK_T0) {
        put_str("monitor error=missed_start\n");
        sys_exit(2);
    }
    leak_wait_until(LEAK_T0);

    /* Read once; the measurement loop never touches these globals' lines. */
    const unsigned int ways = probe_way_count;
    const long fd = sink_fd;

    for (unsigned int window = 0; window < LEAK_N_WIN; ++window) {
        const unsigned long w0 = LEAK_T0 + (unsigned long)window * LEAK_W;

        /* Prime: walk our own lines. */
        leak_wait_until(w0 + LEAK_OFF_PRIME);
        for (unsigned int set = 0; set < CONTENTION_LLC_SETS; ++set)
            (void)walk_set_ways(set, ways);
        if (leak_rdcycle() >= w0 + LEAK_OFF_ENC)
            monitor_error("prime_deadline", window);

        /* Probe: time the same walks after the encryption. */
        leak_wait_until(w0 + LEAK_OFF_PROBE);
        for (unsigned int set = 0; set < CONTENTION_LLC_SETS; ++set) {
            const unsigned long before = leak_rdcycle();
            (void)walk_set_ways(set, ways);
            const unsigned long after = leak_rdcycle();
            struct probe_slot *record =
                (struct probe_slot *)probe_lines[ways - 1][set].padding;
            record->timestamp = before;
            record->latency = (unsigned int)(after - before);
            record->interval = (unsigned short)window;
            record->cache_set = (unsigned short)set;
        }
        if (leak_rdcycle() >= w0 + LEAK_W)
            monitor_error("probe_deadline", window);

        if (sys3(SYS_WRITEV, fd, (long)sink_iov, CONTENTION_LLC_SETS) !=
            SINK_WINDOW_BYTES)
            monitor_error("probe_sink_write", window);
    }

    leak_wait_until(LEAK_T0 + ((unsigned long)LEAK_N_WIN + 1UL) * LEAK_W);
    if (sys3(SYS_CLOSE, sink_fd, 0, 0) != 0) {
        put_str("monitor error=probe_sink_close\n");
        sys_exit(2);
    }
    put_str("monitor status=PASS records=");
    put_u64((unsigned long)LEAK_N_WIN * CONTENTION_LLC_SETS);
    put_str("\n");
    sys_exit(0);
}

/* Linux places argc and argv on the initial RISC-V stack. */
__attribute__((naked, noreturn)) void _start(void)
{
    __asm__ volatile(
        "ld a0, 0(sp)\n"
        "addi a1, sp, 8\n"
        "tail monitor_main\n"
    );
}
