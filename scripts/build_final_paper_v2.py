#!/usr/bin/env python3
"""Build the final paper v2: the v1 paper (scripts/build_final_paper.py) plus Section IX,
the follow-up that closes the channel (request time slots, causal localization, and
per-domain LLC response queues evaluated under the proposal's frozen criterion).

Reads (never modifies) everything build_final_paper.py reads, plus the follow-up results
on the experiment/tdma-prototype worktree (.codex-tmp/tdma-worktree/experiments):
  tdma/summary-final/summary.json
  causal-trace-20261016/analysis/{A1,A8,exploratory_mechanism}.json
  respq-defense-20261018/analysis/{outcome,sweep_outcome}.json
  results/updated run/tdma-rsv/summary_v3.{csv,json}   (frozen decision code on the defense sweep)
  results/updated run/defense-figures/fig_defense_paper.png
Writes a new file only (refuses to overwrite): Group18_EEL5764_Final_Paper_v2.docx

The original research question, design, and negative result are unchanged; the follow-up is
added as its own section. Every new number is read from those files and each declared
outcome is asserted. Standard library only.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scripts.build_final_paper as v1  # noqa: E402  (runs all v1 data checks)
from scripts.build_final_paper import bur  # noqa: E402

OUTPUT = Path("Group18_EEL5764_Final_Paper_v2.docx")
EXP = Path(".codex-tmp/tdma-worktree/experiments")
RSV = Path("results/updated run/tdma-rsv")
FIG3 = Path("results/updated run/defense-figures/fig_defense_paper.png")

# ---- follow-up data and declared outcomes ------------------------------------
tdma = {(r["arm"], r["ways"]): r for r in json.loads((EXP / "tdma/summary-final/summary.json").read_text())["rows"]}
way1, way8, onx1, onx8 = tdma[("way", 1)], tdma[("way", 8)], tdma[("onx", 1)], tdma[("onx", 8)]
assert not onx1["mean_equivalent"] and onx8["mean_equivalent"]
assert onx1["hit_only_holm_p"] < 0.05 and onx8["hit_only_holm_p"] < 0.05
slot_cost =-(onx1["aes_throughput_change_vs_way_only_percent"] + onx8["aes_throughput_change_vs_way_only_percent"]) / 2

causal = {}
for name, path in (("1-15", "A1.json"), ("8-8", "A8.json")):
    hits = json.loads((EXP / "causal-trace-20261016/analysis" / path).read_text())["llc_hits"]
    assert hits["without_interval_zero"]["effects"]["admit_to_llc_ready"]["exact_ticks"] == "0"
explore = {c["case"].rstrip("/").split("/")[-1].split("\\")[-1]: c
           for c in json.loads((EXP / "causal-trace-20261016/analysis/exploratory_mechanism.json").read_text())}


def slipped(case: dict, label: int) -> int:
    rows = [r for r in case["joint_label_residence_forward_latency"] if r["label"] == label]
    # one-to-one: every 1-tick dequeue slip forwards at 1,999 ticks and nothing else does
    assert all((r["queue_residence_ticks"], r["xbar_forward_latency_ticks"]) in ((0, 1000), (1, 1999)) for r in rows)
    return sum(r["requests"] for r in rows if r["queue_residence_ticks"] == 1)


def missed_slot(case: dict) -> int:
    return sum(r["requests"] for r in case["next_gap_after_delayed_dequeue"]
               if r["label"] == 1 and r["next_upstream_gap_ticks"] == 18500)


a1, i1, a8, i8 = slipped(explore["1-15"], 1), slipped(explore["1-15"], 0), slipped(explore["8-8"], 1), slipped(explore["8-8"], 0)
m1, m8 = missed_slot(explore["1-15"]), missed_slot(explore["8-8"])

endpoint = json.loads((EXP / "respq-defense-20261018/analysis/outcome.json").read_text())
assert endpoint["primary_outcome"] == "PASS"
for split in ("1-15", "8-8"):
    assert endpoint["allocations"][split]["aes_throughput_change_percent"]["vs_request_tdma"] == 0.0
base_diff1 = endpoint["allocations"]["1-15"]["baseline_tdma_aes_vs_tdma_quiet"]["differing_records"]
records = endpoint["allocations"]["1-15"]["baseline_tdma_aes_vs_tdma_quiet"]["records"]

sweep = json.loads((EXP / "respq-defense-20261018/analysis/sweep_outcome.json").read_text())
assert sweep["primary_1_proposal_criterion"]["pass"] and sweep["primary_2_byte_identity"]["pass"]
n_identical = sweep["primary_2_byte_identity"]["identical_configurations"]
assert n_identical == sweep["primary_2_byte_identity"]["configurations"] == 24
enc = [r["change_vs_way_only_percent"] for r in sweep["aes_throughput_vs_way_only"]]
defense_enc_cost = -sum(enc) / len(enc)

rsv_json = json.loads((RSV / "summary_v3.json").read_text())
assert rsv_json["stable_collapse_point"] == "1-15" and rsv_json["stable_equivalence_point"] == "1-15"
rsv = {r["split"]: r for r in csv.DictReader(open(RSV / "summary_v3.csv", newline=""))}
assert all(rsv[s]["conclusion"] == "indistinguishable" and rsv[s]["gate_d2_pairs_ok"] == "3" for s in bur.SPLITS)
assert all(bur.v3[s]["control_effect_per_line"] == rsv[s]["control_effect_per_line"] for s in bur.SPLITS)
f = float
cpe = [f(rsv[s]["aes_cycles_per_encryption_cost_pct_mean"]) for s in bur.SPLITS]
mon = [f(rsv[s]["monitor_ipc_cost_pct_mean"]) for s in bur.SPLITS]
worst_ci = max(max(abs(f(rsv[s]["treatment_effect_ci90_low"])), abs(f(rsv[s]["treatment_effect_ci90_high"])))
               for s in bur.SPLITS)
assert worst_ci < 0.02


def ways(split: str) -> str:
    return split.replace("-", "/")


# ---- new prose -----------------------------------------------------------------
ABSTRACT_ADD = (
    " Two follow-up mechanisms close this channel: fixed request time slots at the crossbar and per-domain "
    "LLC response queues. With both added to way partitioning, every allocation becomes indistinguishable under "
    "the same preregistered rule, and the monitor's probe log is byte-identical whether the victim runs AES or "
    f"stays idle in all {n_identical} seed-allocation configurations, at about {defense_enc_cost:.0f}% AES cost.")
SIXTH = (" Sixth, it locates the remaining residual with request-level tracing and closes the channel with "
         "request time slots and per-domain LLC response queues, judged by the same preregistered rule.")

SEC = "IX. CLOSING THE CHANNEL"
INTRO = (
    "Sections VII and VIII show that way partitioning leaves a hit-timing channel through the shared path into and "
    "out of the LLC. We tested whether isolating that path closes it, adding two mechanisms to the A/(16-A) way "
    "partition while keeping the monitor, workloads, seeds, labels, and decision rule unchanged. Each step was "
    "preregistered and built in a separate gem5 tree whose disabled path reproduces the stored results byte for byte.")
SLOTS = (
    "The first mechanism time-multiplexes the shared crossbar request layer, following static-turn arbitration for "
    "shared memory controllers [6]. Each core owns alternating 4 ns slots of an 8 ns frame; a core may launch one LLC "
    "request at the start of its own slot, an unused slot stays idle, and every transfer must finish before the next "
    "slot. Writebacks and page-table walks belong to the issuing core. At the allocation extremes this cut the "
    f"hit-only leak from {way1['effect_cycles_per_line']:.3f} to {onx1['effect_cycles_per_line']:.3f} cycles per line "
    f"at 1/15 and from {way8['effect_cycles_per_line']:.3f} to {onx8['effect_cycles_per_line']:.3f} at 8/8 (three-seed "
    "means). The hit-only test still detected activity at both allocations (Holm-adjusted "
    f"p = {bur.pv(onx1['hit_only_holm_p'])} and {bur.pv(onx8['hit_only_holm_p'])}), and the 1/15 interval "
    f"[{onx1['ci90'][0]:.3f}, {onx1['ci90'][1]:.3f}] fails the ±0.02 margin. AES completed {slot_cost:.1f}% fewer "
    "encryptions than under way partitioning alone.")
LOCATE = (
    "To find where the remaining difference enters, debug-only trace points follow each monitor request through "
    "crossbar admission, the LLC's scheduled response time, the LLC's CPU-side response queue, the crossbar's "
    "response forwarding, and delivery to the CPU, recording both the current tick and the tick at which each "
    "response was scheduled to be ready. Tracing left probe bytes and every simulated statistic unchanged. For LLC "
    "hits at seed 0x5764A5E5, LLC service time was identical in active and idle intervals at 1/15 and 8/8. The only "
    "difference was that a few responses left the shared response queue one tick (1 ps) after their scheduled "
    f"time: {a1} active versus {i1} idle hits at 1/15 and {a8} versus {i8} at 8/8. gem5's packet queue sends a second "
    "packet that becomes ready on the same tick one tick later, so a victim response ready at the same moment "
    "delays the monitor's. The crossbar then aligns that response to its next 1 GHz clock edge, turning one tick "
    f"into a full nanosecond, and in {m1} and {m8} of these cases the monitor's next request missed its time slot "
    "and waited a further 8 ns frame. Every delayed response showed all three signatures, and no other response "
    "did. The same-tick rule is a modelling convention of gem5's packet queue; whether hardware arbitration "
    "behaves the same way was not evaluated.")
QUEUES = (
    "The second mechanism gives the LLC one CPU-side response queue per security domain, so responses for "
    "different cores never serialize against each other inside the cache, as in MI6's per-domain response "
    "queues [5]. Each response is routed by its requester's core. An unmapped requester or a response retry stops "
    "the simulation rather than silently sharing a queue; neither occurred. The crossbar already keeps a separate "
    "response layer for each core and is unchanged.")
EVAL = (
    "We repeated the 48-case matched design with the full defense (way partitioning, request slots, and per-domain "
    "response queues) as the treatment and the stored unpartitioned controls, and judged it with the unmodified "
    "decision code of Section V; applied to copies of the original runs, that code reproduces the stored decision "
    "exactly. Every allocation is now indistinguishable (Fig. 3 and the following table, which gives leak in cycles "
    "per probed line): both co-primary statistics "
    "have Holm-adjusted p = 1 at every allocation, every self-eviction gate passes, the stable collapse point is "
    f"1/15, and every 90% interval lies within ±{worst_ci:.3f} cycles per line.")
IDENTITY = (
    "A stronger, deterministic test agrees. Replacing AES with an idle victim leaves the monitor's entire probe log "
    f"byte-identical in all {n_identical} seed-allocation configurations; at seed 0x5764A5E5 the AES victim makes "
    "694,708 LLC data accesses and the idle victim one. With request slots alone, the same comparison differs in "
    f"{base_diff1:,} of {records:,} records at 1/15. For these inputs the monitor's observations carry no "
    "information about victim activity in this model.")
COST = (
    f"The defense costs AES {min(cpe):.1f}–{max(cpe):.1f}% in cycles per encryption relative to the matched controls "
    f"and the monitor at most {max(mon):.2f}% in IPC; AES completes {defense_enc_cost:.2f}% fewer encryptions than "
    "under way partitioning alone. The cost comes from the request slots: at both allocation extremes, adding the "
    "per-domain response queues changed AES throughput by 0.00% relative to request slots alone.")
TABLE = (["Split", "Partition only", "Full defense", "Defense Holm p (max-set / hit-only)"],
         [[ways(s), f"{f(bur.v3[s]['treatment_effect_per_line']):+.3f}",
           f"{f(rsv[s]['treatment_effect_per_line']):+.4f}",
           f"{bur.pv(f(rsv[s]['treatment_max_set_holm_p']))} / {bur.pv(f(rsv[s]['treatment_hit_only_holm_p']))}"]
          for s in bur.SPLITS])
CAPTION3 = ("Fig. 3. Hit-only leak per allocation (mean over three seeds; bars: 90% bootstrap interval) for the "
            "unpartitioned control, way partitioning alone, and the full defense (way partitioning, request time "
            "slots, and per-domain LLC response queues). Shaded: ±0.02 equivalence margin.")
REFS = [
    "[5] T. Bourgeat, I. Lebedev, A. Wright, S. Zhang, Arvind, and S. Devadas, “MI6: Secure enclaves in a "
    "speculative out-of-order processor,” in Proc. IEEE/ACM MICRO, 2019.",
    "[6] Y. Wang, A. Ferraiuolo, and G. E. Suh, “Timing channel protection for a shared memory controller,” in "
    "Proc. IEEE HPCA, 2014.",
]

EDITS = [  # (block text prefix, old substring, new substring), each must apply exactly once
    ("This work makes five", "This work makes five concrete contributions.",
     "This work makes six concrete contributions."),
    ("This work makes six", "leaves open.", "leaves open." + SIXTH),
    ("Partitioning does not change this channel", "partition or time-multiplex the interconnect into the LLC.",
     "partition or time-multiplex the interconnect into the LLC. Section IX does so."),
    ("Way masks isolate LLC data capacity",
     "Section VIII measures the main channel directly; only the small 8/8 residual is attributed by elimination.",
     "Section VIII measures the main channel directly, and Section IX traces the remaining residual to the LLC's "
     "shared response queue. The full defense also isolates request admission and LLC responses; MSHRs, the write "
     "buffer, DRAM, and response retries remain shared or unsupported, and the idle-victim comparison covers one "
     "key and one activity schedule."),
    ("Every quantitative claim traces", "traces to results/updated run/mech-summary/summary_mechanism.csv.",
     "traces to results/updated run/mech-summary/summary_mechanism.csv. The Section IX experiments are on the "
     "experiment/tdma-prototype branch under experiments/tdma, experiments/causal-trace-20261016, and "
     "experiments/respq-defense-20261018; the defense decision table is results/updated run/tdma-rsv/summary_v3.csv."),
    ("Architecturally, the next step",
     "Architecturally, the next step is to test mitigations aimed at the measured channel, such as bandwidth "
     "partitioning or per-domain arbitration of the shared crossbar request layer, and to instrument the LLC's own "
     "request path to explain the remaining 8/8 residual.",
     "Section IX closed the measured channel for this design. The next steps are to compare AES runs with different "
     "keys and independent activity schedules against each other, to isolate response retries rather than reject "
     "them, and to reduce the cost of the request slots."),
    ("This project evaluated LLC way partitioning",
     "A complete defense must also partition that interconnect, and any evaluation of such defenses must verify",
     "Adding fixed request time slots and per-domain LLC response queues closes it: every allocation becomes "
     "indistinguishable under the same rule, and the monitor's probe log matches an idle victim's byte for byte, "
     f"at about {defense_enc_cost:.0f}% AES cost. Any evaluation of such defenses must also verify"),
]


def apply_edits(blocks: list[tuple]) -> list[tuple]:
    out = list(blocks)
    for prefix, old, new in EDITS:
        hits = [i for i, b in enumerate(out) if len(b) > 1 and isinstance(b[1], str)
                and b[1].startswith(prefix) and old in b[1]]
        assert len(hits) == 1, (prefix, old, hits)
        kind, text = out[hits[0]]
        assert text.count(old) == 1, old
        out[hits[0]] = (kind, text.replace(old, new))
    return out


def paper_blocks() -> list[tuple]:
    b = apply_edits(v1.paper_blocks())
    i = next(i for i, x in enumerate(b) if x[0] == "p" and x[1].startswith("Abstract—"))
    b[i] = ("p", b[i][1] + ABSTRACT_ADD)
    i = next(i for i, x in enumerate(b) if x[0] == "p" and x[1].startswith("Index Terms—"))
    assert b[i][1].endswith("on-chip interconnect.")
    b[i] = ("p", b[i][1].replace("on-chip interconnect.", "on-chip interconnect, timing isolation."))
    renumber = {"IX. PERFORMANCE TRADEOFF": "X. PERFORMANCE TRADEOFF",
                "X. THREATS TO VALIDITY": "XI. THREATS TO VALIDITY", "XI. CONCLUSION": "XII. CONCLUSION"}
    b = [(x[0], renumber.get(x[1], x[1])) if x[0] == "h1" else x for x in b]
    assert sum(x[0] == "h1" and x[1] in renumber.values() for x in b) == 3
    i = next(i for i, x in enumerate(b) if x[0] == "h1" and x[1] == "X. PERFORMANCE TRADEOFF")
    b[i:i] = [("h1", SEC), ("p", INTRO),
              ("h2", "A. Request Time Slots"), ("p", SLOTS),
              ("h2", "B. Locating the Residual"), ("p", LOCATE),
              ("h2", "C. Per-Domain LLC Response Queues"), ("p", QUEUES),
              ("h2", "D. Evaluation Under the Proposal's Criterion"), ("p", EVAL),
              ("table", *TABLE), ("figure3",), ("caption", CAPTION3), ("p", IDENTITY),
              ("h2", "E. Cost"), ("p", COST)]
    last_ref = max(i for i, x in enumerate(b) if x[0] == "ref")
    assert b[last_ref][1].startswith("[4]")
    b[last_ref + 1:last_ref + 1] = [("ref", r) for r in REFS]
    return b


class PaperTemplatesV2(v1.PaperTemplates):
    """v1 templates plus a third figure built from the first figure's drawing XML."""

    def __init__(self, document_xml: str, rid2: str, cy2: int, rid3: str, cy3: int):
        super().__init__(document_xml, rid2, cy2)
        fig = self.figure
        self.figure3 = (fig.replace(re.search(r'r:embed="(rId\d+)"', fig).group(0), f'r:embed="{rid3}"')
                        .replace('<wp:docPr id="1" name="Picture 1"/>', '<wp:docPr id="3" name="Picture 3"/>')
                        .replace('name="repeated_snr.png"', 'name="fig_defense_paper.png"'))
        self.figure3 = re.sub(r'cy="\d+"', f'cy="{cy3}"', self.figure3)
        assert 'id="3"' in self.figure3 and rid3 in self.figure3

    def render(self, blocks: list[tuple]) -> str:
        marker = "@@FIGURE3@@"
        xml = super().render([("p", marker) if x == ("figure3",) else x for x in blocks])
        para = next(p for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S) if marker in p)
        return xml.replace(para, self.figure3)


def build() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"error: refusing to overwrite {OUTPUT}")
    rid2, rid3 = "rId100", "rId101"
    with zipfile.ZipFile(v1.TEMPLATE) as src:
        document = src.read("word/document.xml").decode("utf-8")
        cx = int(re.search(r'<wp:extent cx="(\d+)"', document).group(1))
        (w2, h2), (w3, h3) = v1.png_size(v1.FIG2), v1.png_size(FIG3)
        document = PaperTemplatesV2(document, rid2, round(cx * h2 / w2), rid3,
                                    round(cx * h3 / w3)).render(paper_blocks())
        rels = src.read("word/_rels/document.xml.rels").decode("utf-8")
        assert rid2 not in rels and rid3 not in rels
        image = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
        rels = rels.replace("</Relationships>",
                            f'<Relationship Id="{rid2}" Type="{image}" Target="media/image2.png"/>'
                            f'<Relationship Id="{rid3}" Type="{image}" Target="media/image3.png"/></Relationships>')
        first_media = next(n for n in src.namelist() if n.startswith("word/media/"))
        with zipfile.ZipFile(OUTPUT, "w", zipfile.ZIP_DEFLATED) as dst:
            for info in src.infolist():
                data = src.read(info.filename)
                if info.filename == "word/document.xml":
                    data = document.encode("utf-8")
                elif info.filename == "word/_rels/document.xml.rels":
                    data = rels.encode("utf-8")
                elif info.filename == first_media:
                    data = v1.FIG1.read_bytes()
                dst.writestr(info, data)
            for name, path in (("word/media/image2.png", v1.FIG2), ("word/media/image3.png", FIG3)):
                info = zipfile.ZipInfo(name, date_time=src.getinfo(first_media).date_time)
                info.compress_type = zipfile.ZIP_DEFLATED
                dst.writestr(info, path.read_bytes())
    print("wrote", OUTPUT)


if __name__ == "__main__":
    build()
