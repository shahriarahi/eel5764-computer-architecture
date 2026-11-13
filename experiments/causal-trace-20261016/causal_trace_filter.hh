#ifndef CAUSAL_TRACE_FILTER_HH
#define CAUSAL_TRACE_FILTER_HH

#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>

namespace causal
{

class Filter
{
  private:
    bool enabled_;
    uint64_t requestor_;
    uint64_t base_;
    uint64_t end_;
    std::string llc_;
    std::string queue_;

  public:
    Filter(bool enabled, uint64_t requestor, uint64_t base, uint64_t size,
           std::string llc, std::string queue)
        : enabled_(enabled), requestor_(requestor), base_(base), end_(base),
          llc_(std::move(llc)), queue_(std::move(queue))
    {
        if (enabled && (size == 0 || base > UINT64_MAX - (size - 1)))
            throw std::invalid_argument("invalid causal trace range");
        if (enabled)
            end_ = base + size;
    }

    bool eligible(uint64_t requestor, uint64_t vaddr) const
    {
        return enabled_ && requestor == requestor_ &&
               vaddr >= base_ && vaddr < end_;
    }

    bool isLlc(const std::string &name) const { return enabled_ && name == llc_; }
    bool isQueue(const std::string &name) const { return enabled_ && name == queue_; }
};

} // namespace causal

#endif
