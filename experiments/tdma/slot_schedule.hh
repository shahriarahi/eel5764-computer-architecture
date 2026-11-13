#ifndef TDMA_SLOT_SCHEDULE_HH
#define TDMA_SLOT_SCHEDULE_HH
#include <cstdint>
#include <limits>
#include <stdexcept>

namespace tdma {
class SlotSchedule {
    std::uint64_t width;
    std::uint64_t last = std::numeric_limits<std::uint64_t>::max();
  public:
    explicit SlotSchedule(std::uint64_t ticks) : width(ticks) {
        if (!ticks || ticks > std::numeric_limits<std::uint64_t>::max() / 2)
            throw std::invalid_argument("invalid slot width");
    }
    unsigned owner(std::uint64_t tick) const { return (tick / width) % 2; }
    bool eligible(std::uint64_t tick, unsigned domain) const {
        return domain < 2 && tick % width == 0 && owner(tick) == domain && last != tick;
    }
    std::uint64_t next(std::uint64_t tick, unsigned domain) const {
        if (domain > 1) throw std::invalid_argument("invalid domain");
        auto boundary = tick / width + 1;
        if (boundary % 2 != domain) ++boundary;
        return boundary * width;
    }
    bool fits(std::uint64_t duration) const { return duration < width; }
    void grant(std::uint64_t tick, unsigned domain) {
        if (!eligible(tick, domain)) throw std::logic_error("invalid slot grant");
        last = tick;
    }
};
}
#endif
