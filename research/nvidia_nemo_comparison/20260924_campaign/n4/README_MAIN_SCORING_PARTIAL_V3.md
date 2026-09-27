# Original main scoring result: preserved partial attempt

The subsequent five-case retest passed at the already-supported 120-second
limit, with unchanged metric code and predictions. Its separate receipt is
METRIC_TIMEOUT_RETEST_CHECK_V1.json. A fresh full scoring attempt is documented
in README_MAIN_SCORING_TIMEOUT120_V1.md. Neither result changes this original
partial attempt or promotes its provisional table to accepted evidence.

## Purpose and limits

Record the first complete main scoring attempt and expose its missing metrics.
All 7,680 prediction cases completed their earlier full-artifact method review.
This scoring attempt produced 7,675 SCORED cases and five TIMEOUT cases. It is
PARTIAL_MODELED_BANK_SCORING; an exit-zero supervisor does not make it accepted.
The automatic handoff refused this result before any independent score-review
launch. Original outputs and failed handoff evidence remain immutable.

The table below extracts count-weighted totals from the sealed original REPORT.
It has not passed the independent full-score review and is not a shortlist,
deployment recommendation or N4 acceptance. Every row requires 480 cases across
240 saved scenes and both taps. Missing metrics remain explicit; primary WER
uses supported nonoverlap references, while cpWER/MIMO have their own supported
populations. Do not compare their percentages as if denominators were identical.
Raw WER retains the original text conventions; canonicalized primary WER is
reported separately. Both taps share scene dependency groups. This is the seen
engineering bank, not unseen-room validation. Naming/widget/resource/latency
acceptance is unavailable from this modeled-method bank.

| Composition | Scored/required | Primary edits/words | Primary WER % | Raw WER % | cpWER % | MIMO % |
|---|---:|---:|---:|---:|---:|---:|
| A0_D0_E0 | 479/480 | 1360/9069 | 15.00 | 99.23 | 99.67 | 81.46 |
| A0_D0_E1 | 480/480 | 1361/9120 | 14.92 | 99.21 | 108.49 | 90.09 |
| A0_D1_E0 | 480/480 | 1361/9120 | 14.92 | 99.21 | 39.36 | 34.23 |
| A0_D1_E1 | 480/480 | 1361/9120 | 14.92 | 99.21 | 39.36 | 34.23 |
| A1_D0_E0 | 480/480 | 1536/9120 | 16.84 | 40.88 | 97.25 | 77.70 |
| A1_D0_E1 | 480/480 | 1536/9120 | 16.84 | 40.88 | 101.42 | 81.62 |
| A1_D1_E0 | 480/480 | 1536/9120 | 16.84 | 40.88 | 40.30 | 35.09 |
| A1_D1_E1 | 480/480 | 1536/9120 | 16.84 | 40.88 | 40.30 | 35.09 |
| A2_D0_E0 | 478/480 | 1199/9028 | 13.28 | 29.23 | 91.37 | 69.07 |
| A2_D0_E1 | 478/480 | 1214/9024 | 13.45 | 29.41 | 104.29 | 79.01 |
| A2_D1_E0 | 480/480 | 1217/9120 | 13.34 | 29.34 | 34.23 | 29.59 |
| A2_D1_E1 | 480/480 | 1217/9120 | 13.34 | 29.34 | 34.23 | 29.59 |
| A3_D0_E0 | 480/480 | 1600/9120 | 17.54 | 33.66 | 93.62 | 71.09 |
| A3_D0_E1 | 480/480 | 1600/9120 | 17.54 | 33.66 | 107.55 | 82.40 |
| A3_D1_E0 | 480/480 | 1600/9120 | 17.54 | 33.66 | 39.40 | 33.67 |
| A3_D1_E1 | 480/480 | 1600/9120 | 17.54 | 33.66 | 39.40 | 33.67 |

## Failure evidence and next step

Indices 00888, 00889, 01417, 01424 and 06568 reached the original 60-second
metric request limit. All original scoring owners exited and all 7,680 requests
have process/pipe closure evidence. A separate five-case retest uses the existing
qualified 120-second maximum with unchanged predictions and metric code; see
README_METRIC_TIMEOUT_RETEST_V1.md. No failure is rewritten or excluded from
the original totals. Retest results alone do not constitute a complete reviewed
bank. Paired uncertainty, condition strata and deployment choices must be assessed
against the final independent review and actual application evidence.

## Inputs and outputs

Inputs: private integrated-main-scores-v3/{ADMISSION,RESULT,REPORT}.json,
its 7,680 score receipts, original method review and closed supervisor/worker
records. MAIN_SCORING_PARTIAL_V3.json binds the exact public summary inputs.
Outputs: that count/hash receipt and this provisional table; no new executor
was introduced. Full captions, reference text, metric inputs, profiles, audio
and model weights remain private. The Pi was not contacted.

## Inspection from PowerShell

```powershell
Get-Content -Raw -LiteralPath 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4\MAIN_SCORING_PARTIAL_V3.json'
Get-Content -Raw -LiteralPath 'G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v3\REPORT.json'
```

## Inspection from CMD or Anaconda Prompt

```bat
type G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n4\MAIN_SCORING_PARTIAL_V3.json
type G:\Just_Peachy_N1\20260924_campaign\local\n4\integrated-main-scores-v3\REPORT.json
```

These are read-only inspection commands. Execution and resource limits are
specified in the retest README and original README_SCORING_HISTORY_V3.md.
