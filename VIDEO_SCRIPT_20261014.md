# Video script: Group 18 (5-minute recorded presentation)

Due November 17, 2026. Slides: the "Group 18 Video Deck" artifact; each slide's speaker notes hold the same text.
Pace: about 150 words per minute. Times are estimates at that pace.

## 1. Does cache way partitioning stop a cross-core leak?  (~22 s, 54 words)

Hi, we're Group 18. Our project asks a simple security question: if two programs share a last-level cache, and we give each one its own private ways of that cache, can one program still tell when the other is working? Everything here runs in the gem5 simulator, with a public key and public inputs.

## 2. The question  (~26 s, 66 words)

Here's the setup. Core zero runs a Prime-and-Probe style monitor. Core one runs a textbook T-table AES. They share a sixteen-way last-level cache. Way partitioning gives the monitor A ways and AES the rest, so they can never evict each other's data. We tested every split from one of sixteen up to eight of sixteen, and asked: can the monitor still tell when AES is active?

## 3. How we tested it  (~27 s, 67 words)

Our method is a matched-control design. For each of the eight allocations and three public inputs, we run the monitor twice: once with no partitioning, as a positive control, and once with the way masks on. Everything else is identical. And we check every run directly: the ways really are disjoint, the probes hit the physical sets we think they hit, and AES passes its known-answer test.

## 4. Our first answer was wrong  (~31 s, 77 words)

Here's the twist. Our first analysis said one way was already enough: the leak seemed to vanish. That was wrong. When we validated the data, we found the monitor was evicting its own probe lines. It wrote its measurements into a buffer, and once it only had a few ways, that buffer pushed its probe lines out. A quarter of its probes became slow misses, only in the partitioned runs, and that noise buried the real signal.

## 5. How we fixed the measurement  (~30 s, 74 words)

So we fixed the monitor. It now stores each result inside the probe line it just loaded, so measuring costs no extra cache lines. A cache trace then showed one global variable still stealing a way, so the final version keeps its loop state in registers. And we wrote the analysis rules down before collecting the final data. Probe misses dropped from a quarter of all walks to under two hundredths of a percent.

## 6. Partitioning does not hide AES  (~26 s, 65 words)

With a clean monitor, the answer reverses. Gray is the unpartitioned control, blue is the partitioned run. At every allocation, from one way to eight, the monitor still tells active from idle, with corrected p-values far below point zero five. At one of sixteen it keeps essentially all of its signal; at larger shares, seventy to eighty-five percent. Nowhere does it come close to zero.

## 7. What the leak looks like  (~23 s, 58 words)

So what leaks, if not evictions? Look at single probe walks. When AES is idle, virtually every hit takes exactly thirty-three cycles. When AES is active, about nine percent arrive two, four or six cycles late. Two CPU cycles is exactly one tick of the shared crossbar's clock. On the right, with a near-ideal crossbar, those delays disappear.

## 8. The leak runs through the shared crossbar  (~38 s, 94 words)

Both cores reach the cache through one shared crossbar, and its request lane into the cache is not partitioned. So we preregistered a test: rerun with four crossbar settings, from default to near-ideal. The leak tracks how busy that lane is, perfectly in rank order. A near-ideal crossbar removes the entire leak at one of sixteen and 88 percent at eight of eight. The small remainder is identical with or without partitioning and steps by one tick of the cache's own clock, so we attribute it, by elimination, to the cache's own request path.

## 9. Cheap, but incomplete  (~18 s, 46 words)

What does partitioning cost? Almost nothing here: under three hundredths of a percent in IPC or AES throughput, because both programs fit in their ways. And the masks work: zero cross-domain evictions. Partitioning closes the channel it was designed for. It just isn't the only channel.

## 10. Takeaways  (~24 s, 59 words)

Three takeaways. First, way partitioning stops evictions, not timing leaks. Second, the remaining leak is queueing at the shared crossbar into the cache, so a real defense has to partition the interconnect as well, for example with bandwidth partitioning. Third, validate the measurer: our own monitor once told us the system was secure when it wasn't. Thanks for watching.

**Total: 660 words, about 4.4 minutes.**
