#include <cassert>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>

#include "causal_trace_filter.hh"

int main()
{
    using causal::Filter;
    Filter disabled(false, 3, 0x1000, 0x100, "system.llc",
                    "system.llc.cpu_side");
    assert(!disabled.eligible(3, 0x1000));

    Filter filter(true, 3, 0x1000, 0x100, "system.llc",
                  "system.llc.cpu_side");
    assert(filter.eligible(3, 0x1000));
    assert(filter.eligible(3, 0x10ff));
    assert(!filter.eligible(3, 0x1100));
    assert(!filter.eligible(2, 0x1000));
    assert(filter.isLlc("system.llc"));
    assert(!filter.isLlc("system.cpu0.dcache"));
    assert(filter.isQueue("system.llc.cpu_side"));
    assert(!filter.isQueue("system.cpu0.dcache.cpu_side"));

    bool overflow = false;
    try {
        Filter invalid(true, 3, std::numeric_limits<uint64_t>::max() - 7,
                       16, "system.llc", "system.llc.cpu_side");
    } catch (const std::invalid_argument&) {
        overflow = true;
    }
    assert(overflow);
    std::cout << "PASS causal trace filtering\n";
}
