"""Apply checked causal-trace edits to the isolated TDMA gem5 worktree."""

from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = Path("/home/shahriarahi/eel5764/gem5-causal")
STAGES = {
    "request_admit", "llc_response_ready", "response_enqueue",
    "response_send_attempt", "response_retry", "response_dequeue",
    "xbar_response_forward", "cpu_delivery",
}
TARGETS = {
    "src/mem/SConscript", "src/mem/XBar.py", "src/mem/coherent_xbar.hh",
    "src/mem/coherent_xbar.cc", "src/mem/cache/base.cc",
    "src/mem/cache/cache.cc", "src/mem/packet_queue.cc",
    "src/cpu/simple/timing.cc",
}


def replace(relative: str, old: str, new: str, count: int = 1) -> None:
    path = ROOT / relative
    text = path.read_text()
    if text.count(new) == count:
        return
    if text.count(old) != count:
        raise RuntimeError(f"expected {count} patch anchor(s) in {relative}: {old[:80]!r}")
    path.write_text(text.replace(old, new))


HEADER = r'''#ifndef __MEM_CAUSAL_TRACE_HH__
#define __MEM_CAUSAL_TRACE_HH__

#include <string>

#include "base/trace.hh"
#include "debug/CausalTrace.hh"
#include "mem/packet.hh"

namespace gem5 {
void configureCausalTrace(RequestorID requestor, Addr base, Addr size,
                          const std::string &xbar, const std::string &llc,
                          const std::string &queue);
bool causalTraceEligible(const PacketPtr pkt);
bool causalTraceXbar(const std::string &name);
bool causalTraceLlc(const std::string &name);
bool causalTraceQueue(const std::string &name);
}

#define CAUSAL_TRACE_EVENT(STAGE, COMPONENT, PKT, OUTCOME) do { \
    if (gem5::causalTraceEligible(PKT)) { \
        DPRINTF(CausalTrace, "CAUSAL_TRACE version=1 tick=%llu stage=" STAGE \
                " component=%s requestor=%u cmd=%s paddr=%#llx vaddr=%#llx" \
                " size=%u outcome=" OUTCOME "\n", \
                (unsigned long long)gem5::curTick(), (COMPONENT).c_str(), \
                (unsigned)(PKT)->req->requestorId(), (PKT)->cmdString(), \
                (unsigned long long)(PKT)->getAddr(), \
                (unsigned long long)(PKT)->req->getVaddr(), (PKT)->getSize()); \
    } \
} while (0)

#endif
'''

SOURCE = r'''#include "mem/causal_trace.hh"

#include <memory>

#include "base/logging.hh"
#include "mem/causal_trace_filter.hh"

namespace gem5 {
namespace {
std::unique_ptr<causal::Filter> filter;
std::string xbarName;
}

void configureCausalTrace(RequestorID requestor, Addr base, Addr size,
                          const std::string &xbar, const std::string &llc,
                          const std::string &queue)
{
    fatal_if(filter, "causal trace configured more than once");
    filter = std::make_unique<causal::Filter>(true, requestor, base, size,
                                              llc, queue);
    xbarName = xbar;
}

bool causalTraceEligible(const PacketPtr pkt)
{
    return filter && pkt && pkt->req && pkt->req->hasVaddr() &&
           filter->eligible(pkt->req->requestorId(), pkt->req->getVaddr());
}
bool causalTraceXbar(const std::string &name) { return filter && name == xbarName; }
bool causalTraceLlc(const std::string &name) { return filter && filter->isLlc(name); }
bool causalTraceQueue(const std::string &name) { return filter && filter->isQueue(name); }
} // namespace gem5
'''


def main() -> None:
    if not ROOT.is_dir():
        raise FileNotFoundError(ROOT)
    replace("src/mem/SConscript", "Source('packet_queue.cc')",
            "Source('packet_queue.cc')\nSource('causal_trace.cc')")
    replace("src/mem/SConscript", "DebugFlag('PacketQueue')",
            "DebugFlag('PacketQueue')\nDebugFlag('CausalTrace')")
    replace("src/mem/XBar.py", "    # The coherent crossbar additionally has snoop responses",
            '''    causal_trace_requestor = Param.String("", "Monitor requestor name; empty disables causal tracing")
    causal_trace_vaddr_base = Param.Addr(0, "Monitor probe virtual base")
    causal_trace_vaddr_size = Param.Addr(0, "Monitor probe virtual size")
    causal_trace_llc_name = Param.String("", "Shared LLC object name")
    causal_trace_queue_name = Param.String("", "Shared LLC response queue name")

    # The coherent crossbar additionally has snoop responses''')
    replace("src/mem/coherent_xbar.cc", '#include "mem/coherent_xbar.hh"',
            '#include "mem/coherent_xbar.hh"\n#include "mem/causal_trace.hh"')
    replace("src/mem/coherent_xbar.hh", "    const Cycles tdmaSlotCycles;",
            '''    const std::string causalTraceRequestor;
    const Addr causalTraceVaddrBase;
    const Addr causalTraceVaddrSize;
    const std::string causalTraceLlcName;
    const std::string causalTraceQueueName;
    const Cycles tdmaSlotCycles;''')
    replace("src/mem/coherent_xbar.cc", "      tdmaSlotCycles(p.tdma_slot_cycles),",
            '''      causalTraceRequestor(p.causal_trace_requestor),
      causalTraceVaddrBase(p.causal_trace_vaddr_base),
      causalTraceVaddrSize(p.causal_trace_vaddr_size),
      causalTraceLlcName(p.causal_trace_llc_name),
      causalTraceQueueName(p.causal_trace_queue_name),
      tdmaSlotCycles(p.tdma_slot_cycles),''')
    replace("src/mem/coherent_xbar.cc", "    // iterate over our CPU-side ports and determine which of our",
            '''    if (!causalTraceRequestor.empty()) {
        fatal_if(causalTraceVaddrSize == 0, "causal trace range is empty");
        configureCausalTrace(system->lookupRequestorId(causalTraceRequestor),
            causalTraceVaddrBase, causalTraceVaddrSize, name(),
            causalTraceLlcName, causalTraceQueueName);
    }
    // iterate over our CPU-side ports and determine which of our''')
    replace("src/mem/coherent_xbar.cc", "    if (pkt->isRead()) tdmaReadGrants++;\n    if (pkt->isWriteback()) tdmaWritebackGrants++;\n    return true;",
            '''    if (pkt->isRead()) tdmaReadGrants++;
    if (pkt->isWriteback()) tdmaWritebackGrants++;
    CAUSAL_TRACE_EVENT("request_admit", name(), pkt, "admitted");
    return true;''')
    replace("src/mem/coherent_xbar.cc", "    cpuSidePorts[cpu_side_port_id]->schedTimingResp(pkt, curTick()\n                                        + latency);",
            '''    if (causalTraceXbar(name()))
        CAUSAL_TRACE_EVENT("xbar_response_forward", name(), pkt, "accepted");
    cpuSidePorts[cpu_side_port_id]->schedTimingResp(pkt, curTick()
                                        + latency);''')

    replace("src/mem/cache/base.cc", '#include "mem/cache/base.hh"',
            '#include "mem/cache/base.hh"\n#include "mem/causal_trace.hh"')
    replace("src/mem/cache/cache.cc", '#include "mem/cache/cache.hh"',
            '#include "mem/cache/cache.hh"\n#include "mem/causal_trace.hh"')
    replace("src/mem/cache/base.cc", "        cpuSidePort.schedTimingResp(pkt, request_time);",
            '''        if (causalTraceLlc(name()))
            CAUSAL_TRACE_EVENT("llc_response_ready", name(), pkt, "ready");
        cpuSidePort.schedTimingResp(pkt, request_time);''')
    replace("src/mem/cache/cache.cc", "            cpuSidePort.schedTimingResp(tgt_pkt, completion_time);",
            '''            if (causalTraceLlc(name()))
                CAUSAL_TRACE_EVENT("llc_response_ready", name(), tgt_pkt, "ready");
            cpuSidePort.schedTimingResp(tgt_pkt, completion_time);''')

    replace("src/mem/packet_queue.cc", '#include "mem/packet_queue.hh"',
            '#include "mem/packet_queue.hh"\n#include "mem/causal_trace.hh"')
    replace("src/mem/packet_queue.cc", "    // we can still send a packet before the end of this tick",
            '''    if (causalTraceQueue(name()))
        CAUSAL_TRACE_EVENT("response_enqueue", name(), pkt, "queued");
    // we can still send a packet before the end of this tick''')
    replace("src/mem/packet_queue.cc", "    waitingOnRetry = !sendTiming(dp.pkt);",
            '''    if (causalTraceQueue(name()))
        CAUSAL_TRACE_EVENT("response_send_attempt", name(), dp.pkt, "attempt");
    waitingOnRetry = !sendTiming(dp.pkt);
    if (causalTraceQueue(name())) {
        if (waitingOnRetry)
            CAUSAL_TRACE_EVENT("response_retry", name(), dp.pkt, "blocked");
        else
            CAUSAL_TRACE_EVENT("response_dequeue", name(), dp.pkt, "sent");
    }''')
    replace("src/cpu/simple/timing.cc", '#include "cpu/simple/timing.hh"',
            '#include "cpu/simple/timing.hh"\n#include "mem/causal_trace.hh"')
    replace("src/cpu/simple/timing.cc", '    DPRINTF(SimpleCPU, "Received load/store response %#x\\n", pkt->getAddr());',
            '''    DPRINTF(SimpleCPU, "Received load/store response %#x\\n", pkt->getAddr());
    CAUSAL_TRACE_EVENT("cpu_delivery", name(), pkt, "accepted");''')

    (ROOT / "src/mem/causal_trace.hh").write_text(HEADER)
    (ROOT / "src/mem/causal_trace.cc").write_text(SOURCE)
    shutil.copyfile(HERE / "causal_trace_filter.hh", ROOT / "src/mem/causal_trace_filter.hh")
    patch = subprocess.check_output(["git", "diff", "--", "src/mem", "src/cpu/simple/timing.cc"], cwd=ROOT)
    for relative in ("src/mem/causal_trace.hh", "src/mem/causal_trace.cc",
                     "src/mem/causal_trace_filter.hh", "src/mem/tdma_schedule.hh"):
        result = subprocess.run(
            ["git", "diff", "--no-index", "--", "/dev/null", relative],
            cwd=ROOT, capture_output=True,
        )
        if result.returncode not in (0, 1):
            raise RuntimeError(result.stderr.decode())
        patch += result.stdout
    (HERE / "gem5-causal.patch").write_bytes(patch)
    print("Applied causal trace hooks and retained gem5-causal.patch")


if __name__ == "__main__":
    main()
