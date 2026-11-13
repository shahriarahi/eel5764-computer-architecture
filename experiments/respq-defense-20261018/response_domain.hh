#ifndef __MEM_CACHE_RESPONSE_DOMAIN_HH__
#define __MEM_CACHE_RESPONSE_DOMAIN_HH__

#include <set>
#include <string>
#include <vector>

// Pure requestor-name -> response-domain mapping for split LLC response queues.
namespace respq {

constexpr int NoDomain = -1;
constexpr int Ambiguous = -2;

inline bool
validPrefixes(const std::vector<std::string> &prefixes)
{
    std::set<std::string> seen;
    for (const auto &prefix : prefixes) {
        if (prefix.empty() || !seen.insert(prefix).second)
            return false;
    }
    return prefixes.size() >= 2;
}

/** Index of the single prefix that starts the name, NoDomain, or Ambiguous. */
inline int
responseDomain(const std::string &name, const std::vector<std::string> &prefixes)
{
    int found = NoDomain;
    for (int index = 0; index < static_cast<int>(prefixes.size()); ++index) {
        if (name.compare(0, prefixes[index].size(), prefixes[index]) == 0) {
            if (found != NoDomain)
                return Ambiguous;
            found = index;
        }
    }
    return found;
}

} // namespace respq

#endif // __MEM_CACHE_RESPONSE_DOMAIN_HH__
