/*
 * RequestorPartitionManager: derives an LLC partition ID from the packet's
 * requestor so gem5's stock WayPartitioningPolicy can isolate cores on
 * ISAs without MPAM (see RequestorPartitionManager.py for the rationale).
 */

#ifndef __GEM5_EXT_REQUESTOR_PARTITION_MANAGER_HH__
#define __GEM5_EXT_REQUESTOR_PARTITION_MANAGER_HH__

#include <cstdint>
#include <unordered_map>
#include <vector>

#include "base/statistics.hh"
#include "mem/cache/tags/partitioning_policies/partition_manager.hh"
#include "mem/request.hh"
#include "params/RequestorPartitionManager.hh"

namespace gem5
{

class BaseTags;
class System;

namespace partitioning_policy
{

class RequestorPartitionManager : public PartitionManager
{
  public:
    PARAMS(RequestorPartitionManager);
    RequestorPartitionManager(const Params &p);

    void init() override;

    /**
     * Mapped requestor -> its partition (and record the block address).
     * Unmapped requestor (e.g. L1 writebacks) -> recorded partition of the
     * block address, else default_partition_id (counted as unmapped).
     */
    uint64_t readPacketPartitionID(PacketPtr pkt) const override;

  private:
    System *system;
    const std::vector<std::string> requestorNames;
    const std::vector<uint64_t> requestorPartitions;
    const uint64_t defaultPartitionId;
    const unsigned numPartitions;
    const unsigned assoc;
    const unsigned blkSize;
    std::string tagsPath;
    std::string monitorRequestorName;
    Addr probeVaddrBase;
    Addr probeVaddrSize;
    unsigned probeSetCount;

    /** Resolved in init(): RequestorID -> partition ID. */
    std::unordered_map<RequestorID, uint64_t> requestorToPartition;
    RequestorID monitorRequestorId = Request::invldRequestorId;
    mutable bool probeRotationKnown = false;
    mutable unsigned probeSetRotation = 0;
    mutable uint64_t probeAddressLookupsTotal = 0;
    mutable uint64_t probeMissingVaddrTotal = 0;
    mutable uint64_t probeSetMappingMismatchesTotal = 0;

    /** AES-leakage experiment: optional victim-table tracing. */
    const std::string victimRequestorName;
    const Addr victimVaddrBase;
    const Addr victimVaddrSize;
    const unsigned victimSetCount;
    const unsigned victimLineCount;
    RequestorID victimRequestorId = Request::invldRequestorId;
    /** Physical LLC set + 1 of each traced line (0 = never filled). Kept
     *  outside the stats so a stats reset cannot erase the mapping. */
    mutable std::vector<uint64_t> victimLineSetPlusOne;
    mutable uint64_t victimSetMismatchesTotal = 0;
    mutable uint64_t victimMissingVaddrTotal = 0;
    /** gem5 consults the manager several times per allocation; count each
     *  (tick, block) once. */
    mutable Tick victimLastTick = MaxTick;
    mutable Addr victimLastBlock = 0;
    void traceVictimFill(PacketPtr pkt, Addr blk_addr) const;

    /** Block address -> partition of the last mapped requestor to use it. */
    mutable std::unordered_map<Addr, uint64_t> blockToPartition;

    /** Owning cache's tags; only used to sample way occupancy. */
    BaseTags *tags = nullptr;

    struct PartitionStats : public statistics::Group
    {
        PartitionStats(RequestorPartitionManager &mgr);
        void regStats() override;
        void preDumpStats() override;

        RequestorPartitionManager &mgr;

        /** Lookups resolved directly from a mapped requestor. */
        statistics::Vector requestorLookups;
        /** Lookups (writebacks) resolved via the block-address record. */
        statistics::Vector recordLookups;
        /** Lookups that matched nothing; must be 0 in a valid run. */
        statistics::Scalar unmappedLookups;
        /** Mapped lookups whose block was recorded under another partition
         *  (i.e. a physically shared line); expected 0 in SE mode. */
        statistics::Scalar addrPartitionConflicts;
        /** Valid LLC blocks per [partition][way], sampled at each dump;
         *  row numPartitions collects any other partition ID. */
        statistics::Vector2d wayOccupancy;
        statistics::Scalar probeAddressLookups;
        statistics::Scalar probeMissingVaddr;
        statistics::Scalar probeSetMappingMismatches;
        statistics::Scalar probeSetRotation;
        /** Victim-table LLC fills per traced line (measurement-only). */
        statistics::Vector victimTableFills;
        /** Physical LLC set + 1 of each traced line (0 = never filled). */
        statistics::Vector victimTableLineSetPlusOne;
        statistics::Scalar victimTableSetMismatches;
        statistics::Scalar victimTableMissingVaddr;
    };

    mutable PartitionStats stats;
};

} // namespace partitioning_policy
} // namespace gem5

#endif // __GEM5_EXT_REQUESTOR_PARTITION_MANAGER_HH__
