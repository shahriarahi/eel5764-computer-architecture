/* Simulator-only Prime+Probe-style monitor of its own cache lines. */
#include <stdint.h>

#include "common.h"
#include "contention_common.h"

#define CACHE_LINE_BYTES 64
#define OUTPUT_CAPACITY (2UL * 1024UL * 1024UL)
#define RECORD_COUNT (CONTENTION_INTERVAL_COUNT * CONTENTION_LLC_SETS)

struct probe_line {
    volatile uintptr_t next;
    unsigned char padding[CACHE_LINE_BYTES - sizeof(uintptr_t)];
};

struct probe_record {
    unsigned long timestamp;
    unsigned long latency;
    unsigned short interval;
    unsigned short cache_set;
    unsigned char label;
};

_Static_assert(sizeof(struct probe_line) == CACHE_LINE_BYTES,
               "one probe node must occupy one cache line");

static struct probe_line
probe_lines[CONTENTION_LLC_WAYS][CONTENTION_LLC_SETS]
    __attribute__((aligned(CACHE_LINE_BYTES)));
#ifdef MONITOR_PROBE_SINK_FILE
/* Record-free variant (October 11, 2026).  The original variant stored a
 * 384 KiB record array during measurement; in a partitioned run those stores
 * allocated 96 new LLC lines per interval inside the monitor's own ways and
 * evicted its probe lines.  Here each set's result is stored in the spare
 * bytes of the probe line that was just loaded (an L1D hit, no new line), and
 * after every interval one writev() hands all 256 slots to the simulator.
 * gem5 emulates the syscall with functional memory reads, which do not
 * change cache contents or replacement state.
 */
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
#define SINK_INTERVAL_BYTES \
    ((long)(CONTENTION_LLC_SETS * sizeof(struct probe_slot)))

static struct sink_iovec sink_iov[CONTENTION_LLC_SETS];
static long sink_fd;

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
#else
static struct probe_record records[RECORD_COUNT];
static char output_buffer[OUTPUT_CAPACITY];
static unsigned long output_length;
#endif
static unsigned int probe_way_count;

static void wait_until(unsigned long target)
{
    unsigned long now;
    while ((now = contention_rdcycle()) < target)
        __asm__ volatile("" : : "r"(now) : "memory");
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

#ifndef MONITOR_HOT_STATE_IN_REGISTERS
static struct probe_line *walk_set(unsigned int set)
{
    struct probe_line *cursor = &probe_lines[0][set];
    for (unsigned int way = 0; way < probe_way_count; ++way)
        cursor = (struct probe_line *)cursor->next;
    __asm__ volatile("" : : "r"(cursor) : "memory");
    return cursor;
}

static void prime_all_sets(void)
{
    for (unsigned int set = 0; set < CONTENTION_LLC_SETS; ++set)
        (void)walk_set(set);
}
#else
/* v3 (October 11, 2026).  In v2 the walk re-read the global probe_way_count
 * for every set.  Its cache line (which also holds sink_fd) shares an L1D set
 * with the probe lines of sets 15, 31, ...; from A=4 the 4-way L1D evicts it,
 * every refetch makes it most-recently-used in the LLC, and in a partitioned
 * run it then holds one of the monitor's A ways in LLC set 191 for good.
 * Here the measurement loop takes the way count and fd as register values.
 */
static inline __attribute__((always_inline)) struct probe_line *
walk_set_ways(unsigned int set, unsigned int ways)
{
    struct probe_line *cursor = &probe_lines[0][set];
    for (unsigned int way = 0; way < ways; ++way)
        cursor = (struct probe_line *)cursor->next;
    __asm__ volatile("" : : "r"(cursor) : "memory");
    return cursor;
}
#endif

#ifdef MONITOR_PROBE_SINK_FILE
static struct probe_slot *slot_for_set(unsigned int set)
{
    /* The walk loads way A-1 last, so this line is resident in the L1D. */
    return (struct probe_slot *)probe_lines[probe_way_count - 1][set].padding;
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
        sink_iov[set].base = slot_for_set(set);
        sink_iov[set].length = sizeof(struct probe_slot);
    }
}

#ifndef MONITOR_HOT_STATE_IN_REGISTERS
static void flush_probe_sink(unsigned int interval)
{
    if (sys3(SYS_WRITEV, sink_fd, (long)sink_iov, CONTENTION_LLC_SETS) !=
        SINK_INTERVAL_BYTES) {
        put_str("monitor error=probe_sink_write interval=");
        put_u64(interval);
        put_str("\n");
        sys_exit(2);
    }
}
#endif
#else
static int append_character(char value)
{
    if (output_length >= OUTPUT_CAPACITY)
        return 0;
    output_buffer[output_length++] = value;
    return 1;
}

static int append_string(const char *text)
{
    while (*text != '\0') {
        if (!append_character(*text++))
            return 0;
    }
    return 1;
}

static int append_u64(unsigned long value)
{
    char reversed[24];
    unsigned int count = 0;
    do {
        reversed[count++] = (char)('0' + value % 10);
        value /= 10;
    } while (value != 0);
    while (count != 0) {
        if (!append_character(reversed[--count]))
            return 0;
    }
    return 1;
}

static int format_records(void)
{
    output_length = 0;
    for (unsigned long i = 0; i < RECORD_COUNT; ++i) {
        const struct probe_record *record = &records[i];
        if (!append_string("probe,") || !append_u64(record->timestamp) ||
            !append_character(',') || !append_u64(record->interval) ||
            !append_character(',') || !append_u64(record->label) ||
            !append_character(',') || !append_u64(record->cache_set) ||
            !append_character(',') || !append_u64(record->latency) ||
            !append_character('\n'))
            return 0;
    }
    return 1;
}
#endif

static void print_schedule(void)
{
    for (unsigned int i = 0; i < CONTENTION_INTERVAL_COUNT; ++i)
        put_u64(contention_activity_labels[i]);
}

__attribute__((used, noreturn))
static void monitor_main(unsigned long argc, char **argv)
{
#ifdef MONITOR_PROBE_SINK_FILE
    if (argc != 3 || !contention_parse_probe_ways(argv[1], &probe_way_count)) {
        put_str("monitor error=usage expected=<ways 1..16> <probe file>\n");
        sys_exit(2);
    }
    initialize_probe_chains();
    open_probe_sink(argv[2]);
    put_str("monitor format=probe_bin_v2 intervals=64 sets=256 record_bytes=16 ways=");
#else
    if (argc != 2 || !contention_parse_probe_ways(argv[1], &probe_way_count)) {
        put_str("monitor error=invalid_probe_ways expected=1..16\n");
        sys_exit(2);
    }
    initialize_probe_chains();
    put_str("monitor format=probe_csv_v1 intervals=64 sets=256 ways=");
#endif
    put_u64(probe_way_count);
    put_str(" labels=");
    print_schedule();
    put_str("\n");

    unsigned long now = contention_rdcycle();
    if (now >= CONTENTION_START_CYCLE) {
        put_str("monitor error=missed_start\n");
        sys_exit(2);
    }
    wait_until(CONTENTION_START_CYCLE);
#ifdef MONITOR_HOT_STATE_IN_REGISTERS
    /* Read once; the measurement loop never touches these globals' line. */
    const unsigned int ways = probe_way_count;
    const long fd = sink_fd;
#endif

    for (unsigned int interval = 0; interval < CONTENTION_INTERVAL_COUNT;
         ++interval) {
        const unsigned long interval_start = CONTENTION_START_CYCLE +
            interval * CONTENTION_EPOCH_CYCLES;
        const unsigned long interval_end = interval_start +
            CONTENTION_EPOCH_CYCLES;
        wait_until(interval_start);
#ifdef MONITOR_HOT_STATE_IN_REGISTERS
        for (unsigned int set = 0; set < CONTENTION_LLC_SETS; ++set)
            (void)walk_set_ways(set, ways);
#else
        prime_all_sets();
#endif
        now = contention_rdcycle();
        if (now >= interval_start + CONTENTION_PROBE_OFFSET_CYCLES) {
            put_str("monitor error=prime_deadline interval=");
            put_u64(interval);
            put_str("\n");
            sys_exit(2);
        }
        wait_until(interval_start + CONTENTION_PROBE_OFFSET_CYCLES);
        for (unsigned int set = 0; set < CONTENTION_LLC_SETS; ++set) {
            const unsigned long before = contention_rdcycle();
#ifdef MONITOR_HOT_STATE_IN_REGISTERS
            (void)walk_set_ways(set, ways);
#else
            (void)walk_set(set);
#endif
            const unsigned long after = contention_rdcycle();
#ifdef MONITOR_PROBE_SINK_FILE
#ifdef MONITOR_HOT_STATE_IN_REGISTERS
            struct probe_slot *record =
                (struct probe_slot *)probe_lines[ways - 1][set].padding;
#else
            struct probe_slot *record = slot_for_set(set);
#endif
            record->timestamp = before;
            record->latency = (unsigned int)(after - before);
            record->interval = (unsigned short)interval;
            record->cache_set = (unsigned short)set;
#else
            struct probe_record *record =
                &records[interval * CONTENTION_LLC_SETS + set];
            record->timestamp = before;
            record->latency = after - before;
            record->interval = (unsigned short)interval;
            record->cache_set = (unsigned short)set;
            record->label = contention_activity_labels[interval];
#endif
        }
        if (contention_rdcycle() >= interval_end) {
            put_str("monitor error=probe_deadline interval=");
            put_u64(interval);
            put_str("\n");
            sys_exit(2);
        }
#ifdef MONITOR_HOT_STATE_IN_REGISTERS
        if (sys3(SYS_WRITEV, fd, (long)sink_iov, CONTENTION_LLC_SETS) !=
            SINK_INTERVAL_BYTES) {
            put_str("monitor error=probe_sink_write interval=");
            put_u64(interval);
            put_str("\n");
            sys_exit(2);
        }
#elif defined(MONITOR_PROBE_SINK_FILE)
        flush_probe_sink(interval);
#endif
    }

    wait_until(CONTENTION_START_CYCLE +
               CONTENTION_INTERVAL_COUNT * CONTENTION_EPOCH_CYCLES);
#ifdef MONITOR_PROBE_SINK_FILE
    /* The victim prints its multi-part completion line right at measurement
     * end.  Wait one more interval (after the measurement stats dump) so the
     * two processes' stdout lines cannot interleave.
     */
    wait_until(CONTENTION_START_CYCLE +
               (CONTENTION_INTERVAL_COUNT + 1) * CONTENTION_EPOCH_CYCLES);
    if (sys3(SYS_CLOSE, sink_fd, 0, 0) != 0) {
        put_str("monitor error=probe_sink_close\n");
        sys_exit(2);
    }
#else
    if (!format_records()) {
        put_str("monitor error=output_buffer_overflow\n");
        sys_exit(2);
    }
    if (sys3(SYS_WRITE, 1, (long)output_buffer, output_length) !=
        (long)output_length) {
        put_str("monitor error=short_write\n");
        sys_exit(2);
    }
#endif
    put_str("monitor status=PASS records=");
    put_u64(RECORD_COUNT);
    put_str("\n");
    sys_exit(0);
}

/* Linux places argc and argv on the initial RISC-V stack.  A naked wrapper
 * reads them before a compiler-generated prologue can move the stack pointer.
 */
__attribute__((naked, noreturn)) void _start(void)
{
    __asm__ volatile(
        "ld a0, 0(sp)\n"
        "addi a1, sp, 8\n"
        "tail monitor_main\n"
    );
}
