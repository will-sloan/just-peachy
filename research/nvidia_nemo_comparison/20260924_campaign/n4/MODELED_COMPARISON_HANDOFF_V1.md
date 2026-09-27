# Reviewed numerical comparison checkpoint

This checkpoint records completed numerical comparison work. N4 application
acceptance and N5 release validation remain incomplete. It supersedes historical
handoff statements that main/modes numerical scoring is still waiting to run.

| Scope | Required | Completed/reviewed | Prediction failures | Missing metrics |
|---|---:|---:|---:|---:|
| Main: 16 compositions, 240 scenes, both taps | 7,680 | 7,680 | 0 | 0 |
| Modes panel: 16 compositions, four modes, 24 outputs | 1,536 | 1,536 | 0 | 0 |

The main bank and modes panel are different populations. The modes panel is not
full 240-scene coverage for every mode. The main bank preserves 832 cases with
incomplete ambient references as target-only evidence, rather than claiming
all-speaker accuracy. The method bank retains empty hypotheses. Neither a
complete queue nor these numerical totals establishes actual GUI acceptance.

## Evidence and interpretation

- [Main numerical acceptance](MAIN_MODELED_SCORING_ACCEPTANCE_V1.json):
  `1972386aa05ade607ad2d45484b1db3fc49012c29edb4d13084ebbcd9e12a5c0`.
- [Modes numerical acceptance](MODES_MODELED_SCORING_ACCEPTANCE_V1.json):
  `51ed6a13d13a020c1ba85206fc76955154de873cc759387b8c398e99290b47b5`.
- [Main results](MAIN_MODELED_RESULTS_V1.md) contain 32 aggregate cohorts and
  45 paired comparisons. [Modes results](MODES_MODELED_RESULTS_V1.md) contain
  128 composition/mode/tap cohorts; all 180 paired comparisons and condition
  strata remain in the bound private report.

The independent reviews verified metric inputs, execution lineage and report
totals, including the pinned evaluator environment. They did not recompute
optimal alignments. Public reports contain aggregate counts, not transcripts,
profiles or audio. The original scene bank is a seen engineering bank with
dependent taps/voices/texts, not unseen-room validation.

On the main bank, primary nonoverlap WER is 14.92% for the baseline and 13.34%
for A2 across both taps. D1 compositions have much lower modeled cpWER than D0
on this bank, but that does not establish correct first-visible names or a
deployable memory/latency advantage. E0/E1 D1 word-assignment totals coincide;
this is not evidence of equivalent speaker recognition. Preserve the naming
and quality diagnostics required by N4 before selecting a release.

## Work remaining on the application path

1. Complete actual closed-review reader and planner diagnostics. Preserve the
   first reader probe's rejected admission and the fresh V2 repair. A fixture
   pass cannot substitute for checking both actual score chains.
2. Qualify production plan reconstruction and compatible application, semantic,
   restart and continuity consumers with the current resource accounting. Do
   not force new evidence into the older V4 schema or truncate dependencies.
3. Select the baseline plus a bounded set of distinct alternatives using the
   accepted numerical evidence. Run their actual paced application panels,
   naming/control checks, restarts and resource measurements. No shortlist or
   default backend is promoted by this checkpoint.
4. Run the required 20-minute saved-audio continuity checks for every release
   candidate, then complete the per-build Windows and ARM64 software checks.

The frozen panel has 24 saved outputs plus 16 timing repeats per candidate.
Their source duration is **29.797 minutes per candidate**. Six configurations
would therefore need **2.980 hours of source-paced panel audio**, plus **two
hours of continuity audio**. These are lower bounds, excluding model startup,
slow computation, restart checks, failures and review; they are not a completion
estimate. Preserve the packaging reserve instead of extending the campaign.

## Pi delivery and deadline

The existing N5 baseline archive, read-only storage preflight and
install/stage/health/activate/rollback guides remain available. See
[N5 handoff](../n5/N5_HANDOFF.md) and
[Pi reconnection requirements](../n5/PI_RECONNECTION_REQUIREMENTS.md).
The 2.80-GiB baseline additional-space estimate does not cover optional backend
assets or prove RAM feasibility. ARM64 loader/build checks are not model/WAV/GUI
functional validation. Additional backends need accepted configurations and
their own validated package entries before being offered for installation.

The Pi stays off; actual installation, storage and live CM5 checks are deferred
until the user reconnects it. Packaging reserve starts **2026-09-28 02:48:19
UTC** and the campaign deadline is **2026-09-28 14:48:19 UTC**. If complete
confirmation does not fit, package supported candidates and report the exact
remaining coverage as PARTIAL. Do not relabel preparation as completion.
