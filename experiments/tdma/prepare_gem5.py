"""Apply exact, checked edits only to the isolated gem5 worktree."""
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = Path.home() / "eel5764/gem5-timeslot"


def replace(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError(f"expected exactly one patch anchor in {relative}: {old[:90]!r}")
    path.write_text(text.replace(old, new))


def main() -> None:
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT).strip():
        raise RuntimeError("isolated gem5 worktree must be clean before applying patch")
    replace("src/mem/XBar.py", '    # The coherent crossbar additionally has snoop responses',
            '    tdma_slot_cycles = Param.Cycles(0, "Experimental TDMA slot cycles; zero disables")\n'
            '    tdma_port_domains = VectorParam.Unsigned([], "CPU-side port domains, 0 or 1")\n\n'
            '    # The coherent crossbar additionally has snoop responses')
    replace("src/mem/coherent_xbar.hh", '#include "mem/xbar.hh"',
            '#include "mem/xbar.hh"\n#include "mem/tdma_schedule.hh"')
    replace("src/mem/coherent_xbar.hh", '    bool recvTimingReq(PacketPtr pkt, PortID cpu_side_port_id);', '''    const Cycles tdmaSlotCycles;
    const std::vector<unsigned> tdmaPortDomains;
    std::unique_ptr<tdma::SlotSchedule> tdmaSchedule;
    std::vector<bool> tdmaWaiting;
    unsigned tdmaCursor[2] = {0, 0};
    EventFunctionWrapper tdmaRetryEvent;
    void tdmaRetry();
    void tdmaScheduleRetry();
    bool tdmaAdmit(PacketPtr pkt, PortID port);
    statistics::Scalar tdmaGrants0, tdmaGrants1, tdmaWithheld;
    statistics::Scalar tdmaOverruns, tdmaDownstreamRefusals;
    statistics::Scalar tdmaExpressBypasses, tdmaReadGrants, tdmaWritebackGrants;
    bool recvTimingReq(PacketPtr pkt, PortID cpu_side_port_id);''')
    replace("src/mem/coherent_xbar.cc", '      pointOfUnification(p.point_of_unification),', '''      pointOfUnification(p.point_of_unification),
      tdmaSlotCycles(p.tdma_slot_cycles),
      tdmaPortDomains(p.tdma_port_domains),
      tdmaWaiting(p.port_cpu_side_ports_connection_count, false),
      tdmaRetryEvent([this]{ tdmaRetry(); }, name() + ".tdmaRetry"),
      ADD_STAT(tdmaGrants0, statistics::units::Count::get(), "Domain 0 slot grants"),
      ADD_STAT(tdmaGrants1, statistics::units::Count::get(), "Domain 1 slot grants"),
      ADD_STAT(tdmaWithheld, statistics::units::Count::get(), "Requests withheld before request layer"),
      ADD_STAT(tdmaOverruns, statistics::units::Count::get(), "Transport bound violations"),
      ADD_STAT(tdmaDownstreamRefusals, statistics::units::Count::get(), "Unsupported downstream refusals"),
      ADD_STAT(tdmaExpressBypasses, statistics::units::Count::get(), "Express snoops bypassing schedule"),
      ADD_STAT(tdmaReadGrants, statistics::units::Count::get(), "Read grants"),
      ADD_STAT(tdmaWritebackGrants, statistics::units::Count::get(), "Writeback grants"),''')
    replace("src/mem/coherent_xbar.cc", '    // iterate over our CPU-side ports and determine which of our', '''    if (tdmaSlotCycles != Cycles(0)) {
        fatal_if(tdmaSlotCycles < Cycles(4), "TDMA slots must be at least four cycles");
        fatal_if(tdmaPortDomains.size() != cpuSidePorts.size(), "TDMA incomplete port map");
        bool seen[2] = {false, false};
        for (auto domain : tdmaPortDomains) {
            fatal_if(domain > 1, "TDMA domain must be 0 or 1");
            seen[domain] = true;
        }
        fatal_if(!seen[0] || !seen[1], "TDMA requires two domains");
        tdmaSchedule = std::make_unique<tdma::SlotSchedule>(
            uint64_t(tdmaSlotCycles) * clockPeriod());
    }
    // iterate over our CPU-side ports and determine which of our''')
    replace("src/mem/coherent_xbar.cc", '    // determine the destination based on the destination address range\n    PortID mem_side_port_id = findPort(pkt);', '''    if (tdmaSchedule) {
        if (is_express_snoop) {
            tdmaExpressBypasses++;
            fatal("TDMA unsupported express snoop: refusing an unscheduled bypass");
        }
        if (!tdmaAdmit(pkt, cpu_side_port_id))
            return false;
    }
    // determine the destination based on the destination address range
    PortID mem_side_port_id = findPort(pkt);''')
    replace("src/mem/coherent_xbar.cc",
            '        !reqLayers[mem_side_port_id]->tryTiming(src_port)) {',
            '        !reqLayers[mem_side_port_id]->tryTiming(src_port)) {\n'
            '        fatal_if(tdmaSchedule, "TDMA unexpected request-layer contention");')
    # Both downstream refusal sites must fail before stock shared retry state.
    for old in ('                reqLayers[mem_side_port_id]->failedTiming(src_port,',
                '        reqLayers[mem_side_port_id]->failedTiming(src_port,'):
        indent = old[:len(old)-len(old.lstrip())]
        replace("src/mem/coherent_xbar.cc", '\n' + old,
                '\n' + indent + 'if (tdmaSchedule) {\n' + indent + '    tdmaDownstreamRefusals++;\n' +
                indent + '    fatal("TDMA unsupported downstream refusal");\n' + indent + '}\n' + old)
    # Keep the stock arbitration/routing code. Admission ensures its layer has
    # finished the previous transfer, and any unexpected blocking aborts.
    methods = '''void
CoherentXBar::tdmaScheduleRetry()
{
    Tick next = MaxTick;
    for (unsigned i = 0; i < tdmaWaiting.size(); ++i)
        if (tdmaWaiting[i])
            next = std::min(next, tdmaSchedule->next(curTick(), tdmaPortDomains[i]));
    if (next == MaxTick) return;
    if (!tdmaRetryEvent.scheduled()) schedule(tdmaRetryEvent, next);
    else if (next < tdmaRetryEvent.when()) reschedule(tdmaRetryEvent, next);
}

void
CoherentXBar::tdmaRetry()
{
    unsigned domain = tdmaSchedule->owner(curTick());
    unsigned count = tdmaWaiting.size();
    for (unsigned offset = 0; offset < count; ++offset) {
        unsigned port = (tdmaCursor[domain] + offset) % count;
        if (tdmaWaiting[port] && tdmaPortDomains[port] == domain) {
            tdmaWaiting[port] = false;
            tdmaCursor[domain] = (port + 1) % count;
            cpuSidePorts[port]->sendRetryReq();
            break; // never fill an unused grant from another port or domain
        }
    }
    tdmaScheduleRetry();
}

bool
CoherentXBar::tdmaAdmit(PacketPtr pkt, PortID port)
{
    unsigned domain = tdmaPortDomains.at(port);
    if (!tdmaSchedule->eligible(curTick(), domain)) {
        fatal_if(tdmaWaiting[port], "TDMA duplicate request before retry");
        tdmaWaiting[port] = true;
        tdmaWithheld++;
        tdmaScheduleRetry();
        return false;
    }
    Tick payload = pkt->hasData() ? divCeil(pkt->getSize(), width) * clockPeriod() : 0;
    Tick duration = uint64_t(headerLatency) * clockPeriod() +
        std::max<Tick>(payload, pkt->payloadDelay);
    if (!tdmaSchedule->fits(duration)) {
        tdmaOverruns++;
        fatal("TDMA transport exceeds slot");
    }
    tdmaSchedule->grant(curTick(), domain);
    DPRINTF(CoherentXBar, "TDMA grant domain=%u port=%d duration=%llu\\n",
            domain, port, duration);
    if (domain == 0) tdmaGrants0++; else tdmaGrants1++;
    if (pkt->isRead()) tdmaReadGrants++;
    if (pkt->isWriteback()) tdmaWritebackGrants++;
    return true;
}

'''
    replace("src/mem/coherent_xbar.cc", 'void\nCoherentXBar::recvReqRetry(PortID mem_side_port_id)',
            methods + 'void\nCoherentXBar::recvReqRetry(PortID mem_side_port_id)')
    shutil.copyfile(HERE / "slot_schedule.hh", ROOT / "src/mem/tdma_schedule.hh")
    diff = subprocess.check_output(["git", "diff", "--", "src/mem"], cwd=ROOT)
    # Include new helper in the retained patch without adding it to baseline git.
    helper = subprocess.run(["git", "diff", "--no-index", "--", "/dev/null", "src/mem/tdma_schedule.hh"], cwd=ROOT, capture_output=True)
    (HERE / "gem5-timeslot.patch").write_bytes(diff + helper.stdout)
    print("Patched isolated gem5 only; retained gem5-timeslot.patch")


if __name__ == "__main__":
    main()
