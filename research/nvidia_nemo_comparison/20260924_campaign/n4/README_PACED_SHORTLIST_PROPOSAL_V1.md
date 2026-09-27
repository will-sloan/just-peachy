# Proposed paced application shortlist

`PACED_SHORTLIST_PROPOSAL_V1.json` is a configuration input for the future
qualified production planner, not a release or executable plan. It binds the
actual accepted main and modes review pair checked by
`PANEL_SCORING_GUARDED_CHECK_V2.json`. Its strict selection schema passed the
existing `paced_panel_plan.validate_selection` check: six selected compositions
and explicit reasons for all ten omitted compositions. Every composition keeps
its complete numerical evidence.

| Composition | Purpose in the paired application evaluation |
|---|---|
| A0/D0/E0 | Exact baseline |
| A1/D0/E0 | Isolate the nominal 120M new ASR against the baseline |
| A0/D1/E0 | Isolate D1 with the baseline ASR and embedding |
| A0/D1/E1 | Matched E0/E1 identity contrast under A0/D1 |
| A2/D1/E0 | Lowest modeled primary WER family with D1 |
| A3/D1/E0 | Distinct newer ASR architecture with the same D1/E0 comparator |

The objectives are hypotheses for evaluation. None is a measured 2-GB stack,
accepted release or default recommendation. Use the same frozen settings,
frontend and protected E/C/Q split. Do not tune identities or thresholds from
these results. Naming, source-speed latency, startup, whole-stack RAM and
stop/restart/continuity remain to be measured; ARM64 functionality remains open.

Inputs used to choose the proposal: the accepted numerical pair and the bound
main/modes summary reports. Output: this small JSON and an identical private
copy at `local/n4/proposed-paced-selection-v1.json`; its validation receipt is
`local/n4/proposed-paced-selection-v1-check.json`. The expected SHA-256 for both
copies is `af70a048111cd8437b553c078bfe911ade2d931dea36575b34fdc03463caa682`.

PowerShell inspection and checksum (no worker or model starts):

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$jpSelection='research/nvidia_nemo_comparison/20260924_campaign/n4/PACED_SHORTLIST_PROPOSAL_V1.json'
(Get-Content -Raw -LiteralPath $jpSelection | ConvertFrom-Json).selected | Format-Table composition,objective
Get-FileHash -Algorithm SHA256 -LiteralPath $jpSelection
```

CMD and Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
type research\nvidia_nemo_comparison\20260924_campaign\n4\PACED_SHORTLIST_PROPOSAL_V1.json
certutil -hashfile research\nvidia_nemo_comparison\20260924_campaign\n4\PACED_SHORTLIST_PROPOSAL_V1.json SHA256
```

Do not feed this proposal to an old V4 planner by changing review schemas. The
guarded planner diagnostic and qualified production reconstruction/resource
admission with compatible application consumers are prerequisites. That path
will generate 240 paced panel/repeat cells for this proposal. Its source audio
alone totals 2.980 hours; six later 20-minute continuity tests add two hours.
These durations exclude startup, slow computation, failures and review. Preserve
the packaging reserve and report untested coverage honestly if it does not fit.
No Pi connection, installation or optional-backend package acceptance occurs here.
