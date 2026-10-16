#include "gem5_ext/requestor_partition_manager.hh"

#include <sstream>

#include "base/logging.hh"
#include "base/trace.hh"
#include "debug/RequestorPartition.hh"
#include "mem/cache/cache_blk.hh"
#include "mem/cache/tags/base.hh"
#include "mem/packet.hh"
#include "sim/system.hh"

namespace gem5
{
namespace partitioning_policy
{

RequestorPartitionManager::RequestorPartitionManager(const Params &p)
  : PartitionManager(p),
    system(p.system),
    requestorNames(p.requestor_names),
    requestorPartitions(p.requestor_partitions),
    defaultPartitionId(p.default_partition_id),
    numPartitions(p.num_partitions),
    assoc(p.assoc),
    blkSize(p.blk_size),
    tagsPath(p.tags_path),
    monitorRequestorName(""),
    probeVaddrBase(0),
    probeVaddrSize(0),
    probeSetCount(0),
    stats(*this)
{
    std::vector<std::string> descriptor;
    std::stringstream stream(tagsPath);
    std::string field;
    while (std::getline(stream, field, '|'))
        descriptor.push_back(field);
    fatal_if(descriptor.size() != 1 && descriptor.size() != 5,
        "%s: tags_path instrumentation descriptor needs 1 or 5 fields",
        name());
    if (descriptor.size() == 5) {
        tagsPath = descriptor[0];
        monitorRequestorName = descriptor[1];
        probeVaddrBase = std::stoull(descriptor[2], nullptr, 0);
        probeVaddrSize = std::stoull(descriptor[3], nullptr, 0);
        probeSetCount = std::stoul(descriptor[4], nullptr, 0);
    }
    fatal_if(requestorNames.size() != requestorPartitions.size(),
        "%s: requestor_names (%d) and requestor_partitions (%d) differ in "
        "length", name(), requestorNames.size(), requestorPartitions.size());
    fatal_if(numPartitions == 0, "%s: num_partitions must be > 0", name());
    fatal_if(probeVaddrSize != 0 && probeSetCount == 0,
        "%s: probe_set_count must be > 0 when probe range is configured",
        name());
    for (auto pid : requestorPartitions) {
        fatal_if(pid >= numPartitions,
            "%s: partition %d outside 0..%d", name(), pid, numPartitions - 1);
    }
}

void
RequestorPartitionManager::init()
{
    PartitionManager::init();

    // Requestor IDs are registered by the CPUs' constructors, so they are
    // all known by init().
    for (size_t i = 0; i < requestorNames.size(); ++i) {
        const RequestorID id = system->lookupRequestorId(requestorNames[i]);
        fatal_if(id == Request::invldRequestorId,
            "%s: unknown requestor '%s'", name(), requestorNames[i]);
        fatal_if(id == Request::wbRequestorId,
            "%s: writebacks cannot be mapped by requestor", name());
        requestorToPartition[id] = requestorPartitions[i];
        if (requestorNames[i] == monitorRequestorName)
            monitorRequestorId = id;
        DPRINTF(RequestorPartition, "requestor %s (id %d) -> partition %d\n",
            requestorNames[i], id, requestorPartitions[i]);
    }
    fatal_if(probeVaddrSize != 0 &&
             monitorRequestorId == Request::invldRequestorId,
        "%s: unknown monitor_requestor_name '%s'", name(),
        monitorRequestorName);

    if (!tagsPath.empty()) {
        tags = dynamic_cast<BaseTags *>(SimObject::find(tagsPath.c_str()));
        fatal_if(!tags, "%s: tags_path '%s' is not a BaseTags object",
            name(), tagsPath);
    }
}

uint64_t
RequestorPartitionManager::readPacketPartitionID(PacketPtr pkt) const
{
    const Addr blk_addr = pkt->getBlockAddr(blkSize);
    const auto req_it = requestorToPartition.find(pkt->req->requestorId());

    if (req_it != requestorToPartition.end()) {
        const uint64_t pid = req_it->second;
        if (pkt->req->requestorId() == monitorRequestorId) {
            if (!pkt->req->hasVaddr()) {
                probeMissingVaddrTotal++;
            } else {
                const Addr vaddr = pkt->req->getVaddr();
                if (vaddr >= probeVaddrBase &&
                    vaddr < probeVaddrBase + probeVaddrSize) {
                    const unsigned logical_set =
                        ((vaddr - probeVaddrBase) / blkSize) % probeSetCount;
                    const unsigned physical_set =
                        (blk_addr / blkSize) % probeSetCount;
                    const unsigned rotation =
                        (physical_set + probeSetCount - logical_set) %
                        probeSetCount;
                    if (!probeRotationKnown) {
                        probeRotationKnown = true;
                        probeSetRotation = rotation;
                    } else if (rotation != probeSetRotation) {
                        probeSetMappingMismatchesTotal++;
                    }
                    probeAddressLookupsTotal++;
                }
            }
        }
        auto [rec_it, inserted] = blockToPartition.try_emplace(blk_addr, pid);
        if (!inserted && rec_it->second != pid) {
            stats.addrPartitionConflicts++;
            rec_it->second = pid;
        }
        stats.requestorLookups[pid]++;
        return pid;
    }

    const auto rec_it = blockToPartition.find(blk_addr);
    if (rec_it != blockToPartition.end()) {
        stats.recordLookups[rec_it->second]++;
        return rec_it->second;
    }

    stats.unmappedLookups++;
    DPRINTF(RequestorPartition, "unmapped lookup: requestor %d addr %#x\n",
        pkt->req->requestorId(), blk_addr);
    return defaultPartitionId;
}

RequestorPartitionManager::PartitionStats::PartitionStats(
    RequestorPartitionManager &_mgr)
  : statistics::Group(&_mgr),
    mgr(_mgr),
    ADD_STAT(requestorLookups, statistics::units::Count::get(),
             "Partition lookups resolved from a mapped requestor"),
    ADD_STAT(recordLookups, statistics::units::Count::get(),
             "Partition lookups (writebacks) resolved from the block record"),
    ADD_STAT(unmappedLookups, statistics::units::Count::get(),
             "Partition lookups matching no requestor or record"),
    ADD_STAT(addrPartitionConflicts, statistics::units::Count::get(),
             "Mapped lookups of a block recorded under another partition"),
    ADD_STAT(wayOccupancy, statistics::units::Count::get(),
             "Valid blocks per [partition][way], sampled at stats dump"),
    ADD_STAT(probeAddressLookups, statistics::units::Count::get(),
             "Monitor probe requests checked for physical-set congruence"),
    ADD_STAT(probeMissingVaddr, statistics::units::Count::get(),
             "Mapped monitor requests without a virtual address"),
    ADD_STAT(probeSetMappingMismatches, statistics::units::Count::get(),
             "Probe requests not preserving one constant set rotation"),
    ADD_STAT(probeSetRotation, statistics::units::Count::get(),
             "Observed physical-set minus logical-set rotation")
{
}

void
RequestorPartitionManager::PartitionStats::regStats()
{
    statistics::Group::regStats();

    requestorLookups.init(mgr.numPartitions);
    recordLookups.init(mgr.numPartitions);

    // Last row ("other") collects blocks carrying any other partition ID.
    wayOccupancy.init(mgr.numPartitions + 1, mgr.assoc);
    for (unsigned p = 0; p < mgr.numPartitions; ++p) {
        wayOccupancy.subname(p, csprintf("p%d", p));
    }
    wayOccupancy.subname(mgr.numPartitions, "other");
    for (unsigned w = 0; w < mgr.assoc; ++w) {
        wayOccupancy.ysubname(w, csprintf("way%d", w));
    }
}

void
RequestorPartitionManager::PartitionStats::preDumpStats()
{
    statistics::Group::preDumpStats();
    probeAddressLookups = mgr.probeAddressLookupsTotal;
    probeMissingVaddr = mgr.probeMissingVaddrTotal;
    probeSetMappingMismatches = mgr.probeSetMappingMismatchesTotal;
    probeSetRotation = mgr.probeRotationKnown ? mgr.probeSetRotation : 0;
    if (!mgr.tags) {
        return;
    }

    // Recompute from the live tag array so the dump reflects exactly which
    // ways each partition's blocks occupy at this instant.
    std::vector<std::vector<uint64_t>> counts(
        mgr.numPartitions + 1, std::vector<uint64_t>(mgr.assoc, 0));
    mgr.tags->forEachBlk([&](CacheBlk &blk) {
        if (!blk.isValid()) {
            return;
        }
        const uint64_t pid = blk.getPartitionId();
        const unsigned row = pid < mgr.numPartitions ? pid : mgr.numPartitions;
        counts[row][blk.getWay()]++;
    });
    for (unsigned p = 0; p <= mgr.numPartitions; ++p) {
        for (unsigned w = 0; w < mgr.assoc; ++w) {
            wayOccupancy[p][w] = counts[p][w];
        }
    }
}

} // namespace partitioning_policy
} // namespace gem5
