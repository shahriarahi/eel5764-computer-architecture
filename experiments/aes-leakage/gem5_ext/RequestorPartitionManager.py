from m5.objects.PartitioningPolicies import PartitionManager
from m5.params import (
    Param,
    VectorParam,
)
from m5.proxy import Parent


class RequestorPartitionManager(PartitionManager):
    """PartitionManager that derives a packet's partition ID from its source.

    Stock gem5 (v25.1) only tags packets with a partition ID on Arm via MPAM
    (src/dev/arm/mpam.cc); the base PartitionManager returns 0 for every
    packet. This subclass maps requestor names (e.g. "cpu0.data") to
    partition IDs so the unmodified WayPartitioningPolicy can confine each
    core to its own LLC ways on RISC-V/X86 in SE mode.

    L1 writebacks reach the LLC with the shared Request::wbRequestorId, so
    their partition is taken from a block-address record written whenever a
    mapped requestor's request is looked up. Anything else is counted in the
    'unmappedLookups' statistic and assigned default_partition_id.
    """

    type = "RequestorPartitionManager"
    cxx_header = "gem5_ext/requestor_partition_manager.hh"
    cxx_class = "gem5::partitioning_policy::RequestorPartitionManager"

    system = Param.System(Parent.any, "System that owns the requestor IDs")
    requestor_names = VectorParam.String(
        "Requestor names as registered with the System, e.g. 'cpu0.inst'"
    )
    requestor_partitions = VectorParam.UInt64(
        "Partition ID for each entry of requestor_names (same length)"
    )
    default_partition_id = Param.UInt64(
        0xFFFF,
        "Partition ID for lookups that match no requestor and no recorded "
        "block address; must never be used in a valid run",
    )
    num_partitions = Param.Unsigned(
        2, "Partition IDs 0..num_partitions-1 are reported in wayOccupancy"
    )
    assoc = Param.Unsigned(Parent.assoc, "Associativity of the owning cache")
    blk_size = Param.Unsigned(
        Parent.cache_line_size, "Block size of the owning cache"
    )
    # AES-leakage experiment (2026-11-12): optional victim-table tracing.
    # Defaults disable it; nothing else in this object changes behaviour.
    victim_requestor_name = Param.String(
        "", "Requestor whose LLC fills inside the victim range are traced, "
        "e.g. 'cpu1.data'; empty disables tracing"
    )
    victim_vaddr_base = Param.Addr(0, "Victim table range start (virtual)")
    victim_vaddr_size = Param.Addr(0, "Victim table range size in bytes")
    victim_set_count = Param.Unsigned(
        256, "LLC sets used to report each victim line's physical set"
    )
    tags_path = Param.String(
        "",
        "Full SimObject path of the owning cache's tags (e.g. "
        "'system.l2cache.tags'); when set, per-(partition, way) block "
        "occupancy is sampled from the tags before every stats dump",
    )
