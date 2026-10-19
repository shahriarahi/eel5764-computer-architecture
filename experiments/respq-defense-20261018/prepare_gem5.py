"""Apply checked per-domain LLC response-queue edits to the isolated gem5-respq worktree.

The worktree must already hold c8222cc plus experiments/causal-trace-20261016/gem5-causal.patch
(request TDMA and causal trace v2). Edits are idempotent and anchored.
"""

from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = Path("/home/shahriarahi/eel5764/gem5-respq")


def replace(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text()
    if text.count(new) == 1:
        return
    if text.count(old) != 1:
        raise RuntimeError(f"expected one patch anchor in {relative}: {old[:80]!r}")
    path.write_text(text.replace(old, new))


def main() -> None:
    if not ROOT.is_dir():
        raise FileNotFoundError(ROOT)
    shutil.copyfile(HERE / "response_domain.hh", ROOT / "src/mem/cache/response_domain.hh")

    replace("src/mem/cache/Cache.py", '''    partitioning_manager = Param.PartitionManager(
        NULL, "Cache partitioning manager"
    )
''', '''    partitioning_manager = Param.PartitionManager(
        NULL, "Cache partitioning manager"
    )

    response_domain_prefixes = VectorParam.String(
        [],
        "Requestor-name prefixes, one per response domain; empty keeps one "
        "shared CPU-side response queue",
    )
''')

    replace("src/mem/cache/base.hh", "#include <string>\n",
            "#include <memory>\n#include <string>\n#include <unordered_map>\n")
    replace("src/mem/cache/base.hh", '#include "mem/cache/cache_probe_arg.hh"',
            '#include "mem/cache/cache_probe_arg.hh"\n#include "mem/cache/response_domain.hh"')
    replace("src/mem/cache/base.hh", '''        bool isBlocked() const { return blocked; }

      protected:

        CacheResponsePort(const std::string &_name, BaseCache& _cache,
                       const std::string &_label);
''', '''        bool isBlocked() const { return blocked; }

        /** One response queue per domain; empty prefixes keep one queue. */
        void configureResponseDomains(const std::vector<std::string> &prefixes);

        /** Hides QueuedResponsePort::schedTimingResp to route by domain. */
        void schedTimingResp(PacketPtr pkt, Tick when);

        /** Hides QueuedResponsePort::trySatisfyFunctional to check every queue. */
        bool trySatisfyFunctional(PacketPtr pkt);

      protected:

        void recvRespRetry() override;

        CacheResponsePort(const std::string &_name, BaseCache& _cache,
                       const std::string &_label);
''')
    replace("src/mem/cache/base.hh", '''        bool mustSendRetry;

      private:

        void processSendRetry();
''', '''        bool mustSendRetry;

        /** Domain 0 uses queue; domain N >= 1 uses domainQueues[N - 1]. */
        std::vector<std::string> domainPrefixes;
        std::vector<std::unique_ptr<RespPacketQueue>> domainQueues;
        std::unordered_map<RequestorID, int> domainOf;

        RespPacketQueue &queueFor(PacketPtr pkt);

      private:

        void processSendRetry();
''')

    replace("src/mem/cache/base.cc", '''      sendRetryEvent([this]{ processSendRetry(); }, _name)
{
}
''', '''      sendRetryEvent([this]{ processSendRetry(); }, _name)
{
}

void
BaseCache::CacheResponsePort::configureResponseDomains(
    const std::vector<std::string> &prefixes)
{
    if (prefixes.empty())
        return;
    fatal_if(!respq::validPrefixes(prefixes),
             "%s: response domain prefixes must be at least two distinct, "
             "non-empty strings", name());
    domainPrefixes = prefixes;
    for (size_t domain = 1; domain < prefixes.size(); ++domain) {
        domainQueues.push_back(std::make_unique<RespPacketQueue>(
            cache, *this, true, "CpuSidePort-domain" + std::to_string(domain)));
    }
}

RespPacketQueue &
BaseCache::CacheResponsePort::queueFor(PacketPtr pkt)
{
    if (domainQueues.empty())
        return queue;
    const RequestorID id = pkt->req->requestorId();
    auto found = domainOf.find(id);
    if (found == domainOf.end()) {
        const std::string requestor = cache.system->getRequestorName(id);
        const int domain = respq::responseDomain(requestor, domainPrefixes);
        fatal_if(domain < 0, "%s: requestor %s maps to no single response "
                 "domain", name(), requestor);
        found = domainOf.emplace(id, domain).first;
    }
    return found->second == 0 ? queue : *domainQueues[found->second - 1];
}

void
BaseCache::CacheResponsePort::schedTimingResp(PacketPtr pkt, Tick when)
{
    queueFor(pkt).schedSendTiming(pkt, when);
}

bool
BaseCache::CacheResponsePort::trySatisfyFunctional(PacketPtr pkt)
{
    if (queue.trySatisfyFunctional(pkt))
        return true;
    for (auto &domain_queue : domainQueues) {
        if (domain_queue->trySatisfyFunctional(pkt))
            return true;
    }
    return false;
}

void
BaseCache::CacheResponsePort::recvRespRetry()
{
    // One port shared by several queues would need per-queue retry order.
    fatal_if(!domainQueues.empty(), "%s: response retry with split response "
             "queues is unsupported", name());
    queue.retry();
}
''')
    replace("src/mem/cache/base.cc", '''      stats(*this)
{
''', '''      stats(*this)
{
    cpuSidePort.configureResponseDomains(p.response_domain_prefixes);
''')

    patch = subprocess.check_output(["git", "diff", "--", "src"], cwd=ROOT)
    for relative in ("src/mem/causal_trace.hh", "src/mem/causal_trace.cc",
                     "src/mem/causal_trace_filter.hh", "src/mem/tdma_schedule.hh",
                     "src/mem/cache/response_domain.hh"):
        result = subprocess.run(["git", "diff", "--no-index", "--", "/dev/null", relative],
                                cwd=ROOT, capture_output=True)
        if result.returncode not in (0, 1):
            raise RuntimeError(result.stderr.decode())
        patch += result.stdout
    (HERE / "gem5-respq.patch").write_bytes(patch)
    print("Applied per-domain response queues and retained gem5-respq.patch")


if __name__ == "__main__":
    main()
