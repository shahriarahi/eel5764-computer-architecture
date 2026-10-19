#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "response_domain.hh"

namespace {

void expect(bool condition, const char *what)
{
    if (!condition) {
        std::fprintf(stderr, "FAIL %s\n", what);
        std::exit(1);
    }
}

} // namespace

int main()
{
    using respq::responseDomain;
    const std::vector<std::string> two{"cpu0.", "cpu1."};

    expect(responseDomain("cpu0.data", two) == 0, "monitor data in domain 0");
    expect(responseDomain("cpu0.inst", two) == 0, "monitor fetch in domain 0");
    expect(responseDomain("cpu0.mmu.dtb.walker", two) == 0, "monitor walker in domain 0");
    expect(responseDomain("cpu1.data", two) == 1, "victim data in domain 1");
    expect(responseDomain("cpu1.mmu.itb.walker", two) == 1, "victim walker in domain 1");

    expect(responseDomain("cpu10.data", two) == respq::NoDomain,
           "prefix must end at a separator, not match cpu10 as cpu1");
    expect(responseDomain("system.llc", two) == respq::NoDomain, "unmapped requestor");
    expect(responseDomain("", two) == respq::NoDomain, "empty name");

    const std::vector<std::string> overlap{"cpu", "cpu0."};
    expect(responseDomain("cpu0.data", overlap) == respq::Ambiguous,
           "two matching prefixes are ambiguous");

    expect(respq::validPrefixes(two), "distinct non-empty prefixes are valid");
    expect(!respq::validPrefixes({"cpu0.", ""}), "empty prefix is invalid");
    expect(!respq::validPrefixes({"cpu0.", "cpu0."}), "duplicate prefix is invalid");
    expect(!respq::validPrefixes({"cpu0."}), "a single domain cannot isolate anything");

    std::puts("PASS response domain mapping");
    return 0;
}
