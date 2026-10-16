# Final Submission Audit

Audit date: October 1, 2026

> **Revision, October 11, 2026: status downgraded to NOT READY.** An
> independent re-validation reproduced every number in this audit exactly.
> A post-hoc analysis (`APPENDIX_POSTHOC_20261011.md`) then found monitor
> self-eviction in all 24 partitioned treatments, and a hit-latency signal
> that survives partitioning. `REPORT_REPEATED_20261001.md` has been revised
> to qualify its claims. The DOCX files below still state the unqualified
> conclusion and must be revised before submission:
>
> | File | Paragraph (0-based, `word/document.xml`) | Claim to revise |
> |---|---|---|
> | `Group18_EEL5764_Final_Project_Report.docx` and `..._Expanded.docx` | 9 | "This removes monitor self-thrashing as an alternative explanation for signal suppression" is contradicted (Appendix A.3) |
> | Both report DOCX files | 3 (abstract) | "support way partitioning for the tested data-way contention signal" needs qualifying with the hit-timing result (Appendix A.5–A.6) |
> | Both report DOCX files | Results "stable collapse" paragraph (104 / 135) | Mention `4/12` seed `0x5764A5E5` (p=0.0202), and limit the claim to the max-set statistic |
> | `..._Expanded.docx` | 142, 169 | "way partitioning removed distinguishability for this monitor" holds only for the predeclared statistic |
>
> **Update, October 12:** the corrected reports are
> `Group18_EEL5764_Final_Project_Report_Updated.docx` and
> `Group18_EEL5764_Final_Project_Report_Expanded_Updated.docx` (new files).
> They are built from the v3 sweep (`results/updated run/sweep-v3/`;
> `REPORT_UPDATED_RUN_20261011.md` §12). The original DOCX files above are
> kept unchanged.
>
> A corrected monitor (no record traffic during measurement) and a
> preregistered rerun were completed. See `PREREGISTRATION_V2_20261011.md`
> once it exists. The October 1 status below is kept unchanged as the record
> of that audit.
>
> **Status, October 14, 2026: READY.** An independent validation
> (`VALIDATION_20261014.md`) reproduced every stage and every number, and
> confirmed the final v3 result: all eight allocations are distinguishable.
>
> **Submit:**
>
> - `Group18_EEL5764_Final_Project_Report_Updated.docx` (3 pages)
> - `Group18_EEL5764_Final_Project_Report_Expanded_Updated.docx` (5 pages)
> - technical report `REPORT_UPDATED_RUN_20261011.md` (§12 is final)
> - results `results/updated run/sweep-v3/`
>
> **Changes made today:**
>
> - Both `_Updated` DOCX files were regenerated from the corrected builder.
>   The changes are three wording fixes: the control-effect range, the
>   meaning of the +0.26 pp miss rise, and the seed-independence and gate
>   caveats.
> - Both files were checked in Word: same page counts, clean page breaks.
> - The pre-fix copies are in `archive/pre-20261014/`.
>
> The "Files to use" table below is the October 1 submission set and is
> superseded. `PREREGISTRATION_V2_20261011.md` exists and records deviations
> D1–D3.

## Submission status

The corrected three-seed project is internally consistent and ready for
submission with the limitation noted below about DOCX visual rendering. The
security conclusion, performance values, process count, validation counts, and
statistical method agree across the aligned proposal, final report, runbook,
beginner explanation, and derived result files.

## Files to use as the current submission

| Purpose | File or directory | Audit status |
|---|---|---|
| Aligned project proposal | `Group18_EEL5764_Final_Project_Proposal_Aligned.docx` | PASS: three seeds, 48 inferential cases, two diagnostics, Fisher/Holm rule, and actual throughput granularity are stated |
| Final technical report | `REPORT_REPEATED_20261001.md` | PASS: measured claims trace to the repeated result root |
| Reproduction instructions | `RUNBOOK.md` | PASS: Step 10B and key facts match the repeated study |
| Beginner explanation | `project explanation.md` | PASS: invalid fixed-16-line conclusion removed |
| Final raw and derived results | `results/contention-repeated-20261001/` | PASS: 50 analyses, no failed-run directories |
| Source and tests | `configs/`, `workloads/`, `gem5_ext/`, `analysis/`, `scripts/`, `tests/` | PASS: automated and integration tests pass |

## Claim and evidence checks

| Check | Verified evidence | Status |
|---|---|---|
| Planned process count | 50 entries in `run_plan.json` | PASS |
| Completed process count | 50 `analysis.json` files | PASS |
| Inferential design | 24 controls plus 24 partitioned treatments | PASS |
| Excluded diagnostics | Two A=16 unpartitioned processes | PASS |
| Probe records | 819,200 total | PASS |
| Statistics blocks | 100 total | PASS |
| AES correctness | 50 `aes_self_test=PASS` records | PASS |
| Physical-set mapping | 50 `PASS congruent` results and zero mismatches | PASS |
| Way-mask enforcement | 24 `PASS disjoint` treatments and zero violations | PASS |
| Matched positive controls | All 24 individually distinguishable | PASS |
| Repeated inference | Fisher combination across three public seeds | PASS |
| Across-allocation correction | Holm correction across eight control and eight treatment tests as separate families | PASS |
| Stable-collapse result | `1/15` under the predefined rule | PASS |
| First-allocation performance values | Monitor IPC cost 0.7867%; AES IPC change +0.0016%; monitor LLC miss-rate change +19.362274 percentage points | PASS |
| Figures | PDF and PNG repeated-SNR figures exist and the PNG was visually inspected | PASS |

## Verification outputs

Python test suite:

```text
Ran 49 tests in 0.128s
OK
```

Workload and runner integration checks:

```text
contention workload build PASS
corrected runner validation PASS
```

Result and artifact checks:

```text
required_submission_artifacts=10 present=PASS
analysis_files=50 failed_dirs=0 stable_collapse_point=1-15
current_document_stale_claim_scan=PASS
```

## Historical files not to present as current conclusions

The following artifacts remain intentionally preserved for research integrity,
but they should not be submitted or cited as the final result:

- `EEL5764_Project_Proposal.docx`, `Group_18_EEL5764_Project_Proposal.docx`,
  and `Group18_EEL5764_Revised_Project_Proposal_Matched_Control.docx`;
- `REPORT.md` and `REPORT_CORRECTED_20261001.md`;
- `results/contention/`, `results/contention-l1d4k/`, and
  `results/contention-corrected-20261001-v2/`.

These files document the failed 16 KiB control, the invalid fixed-16-line
pilot, and the corrected but non-monotonic single-seed study. They are useful
as provenance, not as the current conclusion.

## Remaining limitation

The aligned DOCX passed structural inspection: all expected paragraphs,
tables, statistical terms, process counts, seeds, and throughput wording are
present. The packaged DOCX renderer could not perform visual page inspection
because LibreOffice is unavailable on this Windows host. Open the aligned copy
in Microsoft Word once before submission to confirm that the longer replacement
paragraphs did not create an undesirable page break or cramped table row.

Scientifically, the final result remains limited to three deterministic public
seeds. Failure to reject the partitioned signal is not a formal equivalence
proof, and the `7/9` treatment is close to the corrected threshold at
`Holm p=0.061546`.
