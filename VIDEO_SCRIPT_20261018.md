# Video script: Group 18 (5-minute recorded presentation), updated October 18

Due November 17, 2026. Slides: the "Group 18 Video Deck" artifact. Each slide's speaker notes hold the same text.
This version adds the channel-closing follow-up (slides 9–11). The October 14 script is kept unchanged as
`VIDEO_SCRIPT_20261014.md`. Pace is about 150 words per minute, and the times below are estimates at that pace.

## 1. Does cache way partitioning stop a cross-core leak?  (~18 s, 46 words)

Hi, we're Group 18. If two programs share a last-level cache and each gets its own private ways, can one still tell when the other is working, and what would it take to stop it? Everything here runs in gem5, with a public key and inputs.

## 2. The question  (~20 s, 49 words)

Core zero runs a Prime-and-Probe style monitor; core one runs a textbook T-table AES. They share a sixteen-way cache. Way partitioning gives the monitor A ways and AES the rest, so neither can evict the other. We tested every split from one of sixteen up to eight of sixteen.

## 3. How we tested it  (~16 s, 39 words)

For each allocation and three public inputs, we run the monitor twice: unpartitioned, as a positive control, and partitioned. Nothing else changes. And we check every run directly: disjoint ways, the right physical sets, and a passing AES self-test.

## 4. Our first answer was wrong  (~20 s, 49 words)

Our first analysis said one way was enough. That was wrong. The monitor was evicting its own probe lines: its measurement buffer, squeezed into a few ways, pushed them out, but only in partitioned runs. A quarter of its probes became slow misses, and that noise buried the signal.

## 5. How we fixed the measurement  (~16 s, 41 words)

So we fixed the monitor. Results are stored inside the probe line just loaded, loop state lives in registers, and we preregistered the analysis rules. Probe misses fell from a quarter of all walks to under two hundredths of a percent.

## 6. Partitioning does not hide AES  (~17 s, 43 words)

With a clean monitor, the answer reverses. Gray is the unpartitioned control, blue is partitioned. At every allocation the monitor still tells active from idle, with corrected p-values far below point zero five. It keeps seventy to a hundred percent of its signal.

## 7. What the leak looks like  (~15 s, 37 words)

So what leaks, if not evictions? When AES is idle, every hit takes exactly thirty-three cycles. When AES is active, about nine percent arrive two, four or six cycles late: whole ticks of the shared crossbar's clock.

## 8. The leak runs through the shared crossbar  (~18 s, 45 words)

Both cores reach the cache through one shared crossbar. In a preregistered test, the leak tracked how busy its request lane was, perfectly in rank order. A near-ideal crossbar removed the whole leak at one of sixteen, but only 88 percent at eight of eight.

## 9. Time slots shrink the leak  (~21 s, 53 words)

So we partitioned that lane in time. Each core gets alternating four-nanosecond request slots, used or not. The leak shrank about ninefold at one of sixteen and seventy-fold at eight of eight. But it didn't vanish: the monitor could still detect AES at both ends, and AES lost six percent of its throughput.

## 10. Finding the rest  (~23 s, 57 words)

To find the rest, we traced every monitor request through the cache. Cache service time was identical. The difference: when a victim response was ready on the same tick, the monitor's response left the shared response queue one picosecond late. The crossbar rounded that up to a full nanosecond, and sometimes the next request missed its slot.

## 11. Per-domain response queues close it  (~24 s, 60 words)

The fix is to give each core its own response queue in the cache. With time slots plus per-domain queues, we reran the whole original design and judged it with the exact same frozen code. Every allocation is now indistinguishable. Even stronger: the monitor's entire record is byte-identical whether the victim runs AES or sits idle, in all twenty-four configurations.

## 12. What it costs  (~13 s, 32 words)

The cost? Way partitioning alone costs almost nothing, under three hundredths of a percent. The full defense costs AES about six percent, all from the time slots; the per-domain queues add nothing.

## 13. Takeaways  (~20 s, 51 words)

Three takeaways. Way partitioning stops evictions, not timing leaks. The leak lives in the shared path to and from the cache, so isolate that path too: time slots and per-domain response queues closed it here. And validate the measurer: our own monitor once said "secure" when it wasn't. Thanks for watching.

**Total: 602 words, about 4.0 minutes.** That leaves about 59 seconds of slack for pauses and slide transitions.

## Numbers behind the narration

- **Slide 6.** The partitioned treatment keeps 70–100% of the control's signal, and the largest corrected p is 1.2e-5 (paper §VII).
- **Slide 9.** Hit-only leak falls from 0.346 to 0.040 cycles per line at 1/15 (8.7×) and from 0.279 to 0.004 at 8/8 (70×). The hit-only Holm p values are 8.2e-10 and 2.8e-9. AES throughput is −6.0% relative to way-only (paper §IX-A).
- **Slide 10.** One gem5 tick is 1 ps. The one-tick dequeue slip occurred for 40 active versus 2 idle hits at 1/15 and 268 versus 1 at 8/8. The crossbar edge alignment adds 999 ticks (paper §IX-B).
- **Slide 11.** Stable collapse point 1/15, and byte identity holds in 24 of 24 configurations (paper §IX-D).
- **Slide 12.** The full defense costs 6.3–6.4% in AES cycles per encryption. Split queues change AES throughput by 0.00% relative to request slots alone (paper §IX-E).
