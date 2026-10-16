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
static struct probe_record records[RECORD_COUNT];
static char output_buffer[OUTPUT_CAPACITY];
static unsigned long output_length;
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

static void print_schedule(void)
{
    for (unsigned int i = 0; i < CONTENTION_INTERVAL_COUNT; ++i)
        put_u64(contention_activity_labels[i]);
}

__attribute__((used, noreturn))
static void monitor_main(unsigned long argc, char **argv)
{
    if (argc != 2 || !contention_parse_probe_ways(argv[1], &probe_way_count)) {
        put_str("monitor error=invalid_probe_ways expected=1..16\n");
        sys_exit(2);
    }
    initialize_probe_chains();
    put_str("monitor format=probe_csv_v1 intervals=64 sets=256 ways=");
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

    for (unsigned int interval = 0; interval < CONTENTION_INTERVAL_COUNT;
         ++interval) {
        const unsigned long interval_start = CONTENTION_START_CYCLE +
            interval * CONTENTION_EPOCH_CYCLES;
        const unsigned long interval_end = interval_start +
            CONTENTION_EPOCH_CYCLES;
        wait_until(interval_start);
        prime_all_sets();
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
            (void)walk_set(set);
            const unsigned long after = contention_rdcycle();
            struct probe_record *record =
                &records[interval * CONTENTION_LLC_SETS + set];
            record->timestamp = before;
            record->latency = after - before;
            record->interval = (unsigned short)interval;
            record->cache_set = (unsigned short)set;
            record->label = contention_activity_labels[interval];
        }
        if (contention_rdcycle() >= interval_end) {
            put_str("monitor error=probe_deadline interval=");
            put_u64(interval);
            put_str("\n");
            sys_exit(2);
        }
    }

    wait_until(CONTENTION_START_CYCLE +
               CONTENTION_INTERVAL_COUNT * CONTENTION_EPOCH_CYCLES);
    if (!format_records()) {
        put_str("monitor error=output_buffer_overflow\n");
        sys_exit(2);
    }
    if (sys3(SYS_WRITE, 1, (long)output_buffer, output_length) !=
        (long)output_length) {
        put_str("monitor error=short_write\n");
        sys_exit(2);
    }
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
