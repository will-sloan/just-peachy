# N4 outcome: numerical comparison complete, application confirmation partial

The comparative numerical work is reviewed, but no new complete application
configuration is accepted for release. The latest actual application run failed
at two Nemotron diarization configurations. Further whole-panel repairs have
ended for this campaign so the remaining time can validate and package supported
software. The packaging reserve and deadline are unchanged.

| Evidence population | Required | Reviewed/collected | Failed | Unattempted |
|---|---:|---:|---:|---:|
| Main modeled comparison, 16 compositions × 240 scenes × 2 taps | 7,680 | 7,680 reviewed | 0 | 0 |
| Four-mode modeled panel, 16 compositions × 24 outputs | 1,536 | 1,536 reviewed | 0 | 0 |
| Latest actual paced GUI panel, six configurations × 40 occurrences | 240 | 2 collected, acceptance pending | 2 | 236 |

These populations must not be combined. The mode comparison is a representative
panel, not every mode on the complete bank. The actual application's accepted
cell count and accepted new release-profile count are both zero.

## What the comparison supports

The reviewed main-bank nonoverlap WER is 14.92% for A0 baseline and 13.34% for
A2 across both taps. D1 has substantially lower modeled cpWER than D0 on this
bank. Neither finding establishes first-visible naming quality, source-to-widget
delay, sustained throughput or a deployable memory tier. The coinciding D1 E0/E1
word-assignment totals do not establish equivalent speaker recognition.

All 240 scenes are a seen engineering bank, with dependent voices, texts and
taps. Incomplete ambient references remain target-only evidence. No unseen-room
generalization or physical microphone timing is claimed. See
MAIN_MODELED_RESULTS_V1.md, MODES_MODELED_RESULTS_V1.md and their acceptance
receipts for aggregate counts, matched contrasts and limitations. Component
N2/N3 acceptance remains valid only within its separately declared scope.

## Actual application evidence

The V10 lineage had 337 unchanged source bindings and 45 passing supervised
development checks. Its lease-open repair passed setup for all four attempted
source cells. Development qualification did not guarantee successful inference.

| Configuration | Required in frozen panel | Collected pending review | Failed | Unattempted |
|---|---:|---:|---:|---:|
| A0/D0/E0 | 40 | 1 | 0 | 39 |
| A1/D0/E0 | 40 | 1 | 0 | 39 |
| A0/D1/E0 | 40 | 0 | 1 | 39 |
| A0/D1/E1 | 40 | 0 | 1 | 39 |
| A2/D1/E0 | 40 | 0 | 0 | 40 |
| A3/D1/E0 | 40 | 0 | 0 | 40 |

Both failed cells delivered all 715,127 source samples. D1 exceeded the unchanged
60-second finalization drain. E0's failed application closed and was recorded
without success credit. E1 still had a live speaker lane at finalization, denied
resident-bundle reuse and recorded unsuccessful Controller closure. The collector
therefore stopped. A later engine snapshot had no live workers and all four
Windows jobs eventually exited normally; this cannot retrospectively turn the
application closure or latency into a pass.

The runner's attempted=3 is the number of returned outcomes. The fourth fatal
cell exists outside that list. APPLICATION_PANEL_CLOSURE_FAILURE_V10.json binds
the independent audit establishing four actual attempts, all four empty jobs,
closed exact PID creation identities and the complete 240-cell denominator.
Previous partial attempts are preserved separately and never pooled into a pass.

The Controller's ownership check and single Close request provide a plausible
timing explanation for the final failure. Its exact rejecting exception was not
captured, so a specific code-level cause remains unverified. No failure gate,
60-second drain, lease age, input pacing, source hash or accepted metric was
changed to obtain a favorable result.

## Release decision and remaining work

Retain the separately supported N1 baseline and its N5 preparation. Do not
promote a new backend, assert a CM5 memory tier, or substitute a different
backend after loading fails. ARM64 component checks can strengthen software
evidence but cannot accept these incomplete N4 application configurations.

Missing confirmation includes matching V10 semantic/timing consumers, the full
paced population, 20-minute continuity per retained candidate, 12 paired
stop/restart checks and isolated complete-stack resource/deployment decisions.
The 2.980 hours of panel source audio plus two hours of continuity are lower
bounds that exclude startup, slower inference, repairs, review and restart work.
They are not a completion estimate. The repeated real failures make another
whole-panel rescue inappropriate before the reserved packaging work.

For a later explicitly resumed campaign, create a fresh source derivative;
capture the exact Controller rejection; reproduce delayed lane termination and
ownership retention; qualify any bounded correction with failure regressions;
then regenerate and run paired affected configurations and matching reviewers.
Do not reuse a failed release or widen a reader to treat late process exit as
successful application closure.

The Pi stays powered off. Later installation, storage, saved-audio GUI checks and
physical CM5 validation are deferred until reconnection. Packaging reserve:
2026-09-28 02:48:19 UTC. Campaign deadline: 2026-09-28 14:48:19 UTC.
