# Operational launch readiness

## Verdict

**`NOT_READY_TO_LAUNCH`**

The repository now contains a reproducible candidate campaign specification,
complete-assignment preflight, deterministic non-overlapping worker manifests,
launch/export/merge/analysis wrappers, and a real bounded two-worker rehearsal.
The operators must not start the massive campaign yet: Stage 14 is uncommitted,
Machine A lacks FFmpeg, Machine B has not been tested, the component canary is
incomplete, small/standard release gates have not passed, and the current
candidate contains only Whisper Base—not a screening-approved finalist set.

## Readiness matrix

| Area | Machine A | Machine B | Massive campaign impact |
|---|---|---|---|
| Git clone | `PASS_WITH_WARNING` — genuine remote clone/run passed at `4e1`; Stage 14 not in that commit | `NOT_YET_TESTED` | Final commit-bound package cannot launch |
| Core environment | `PASS_WITH_WARNING` — Python/PyTorch/pip pass; FFmpeg missing | `NOT_YET_TESTED` | A blocked; B unknown |
| CUDA | `NOT_APPLICABLE` to CPU candidate; prior core CUDA evidence exists | `NOT_YET_TESTED` | No CUDA work in candidate |
| Models | `PASS` for exact Whisper Base | `NOT_YET_TESTED` | B must hash exact asset |
| Datasets | `PASS` for all 20 assigned scenarios | `NOT_YET_TESTED` | B must resolve all 21 |
| RIR | `PASS` for Dining/Restaurant assigned work | `NOT_YET_TESTED` | Bedroom excluded; no substitute |
| Extended local | `PASS_WITH_WARNING` in retained qualification evidence | `NOT_YET_TESTED` | Excluded from candidate |
| ONNX | `PASS_WITH_WARNING` in retained qualification evidence | `NOT_YET_TESTED` | Excluded from candidate |
| WeNet | `BLOCKED` — `final.zip` unavailable | `NOT_YET_TESTED` | Excluded |
| WeSpeaker | `PASS_WITH_WARNING` in retained evidence | `NOT_YET_TESTED` | Excluded |
| pyannote | `MANUAL_ACTION_REQUIRED` | `NOT_YET_TESTED` | Credential-gated and excluded; not a current blocker |
| Falcon | `MANUAL_ACTION_REQUIRED` | `NOT_YET_TESTED` | Credential-gated and excluded; not a current blocker |
| NeMo | `BLOCKED` on current Windows/core profile | `NOT_YET_TESTED` | Linux/checkpoints required; excluded |
| Campaign assignment | `PASS_WITH_WARNING` — 20/20 scenario-specific checks, assignment-wide blocked | `NOT_YET_TESTED` | Provisional split only |
| Transfer | `PASS` in local two-worker rehearsal | `NOT_YET_TESTED` | Massive transfer not yet possible |
| Merge | `PASS` in local two-worker rehearsal | `NOT_YET_TESTED` | Mechanics proven, real B handoff absent |
| Analysis | `PASS` in bounded rehearsal; Windows idempotence defect corrected | `NOT_YET_TESTED` | Massive analysis awaits 41 merged scenarios and standard evidence |

## Massive campaign status

- ID/hash: `campaign_05_massive_release` /
  `FF833023B2CBFCC58C4CB65038BBF97A4A791296BE8AC7C09B6AA948C66046D4`.
- Scope: 41 Whisper Base CPU/full-record ASR scenarios; 25,798 item
  executions; 33.720121 repeated audio hours.
- A: 20 scenarios, 16.882998 hours, estimated 4.08 hours
  (3.46–6.24), 2.15 GiB artifacts.
- B: 21 scenarios, 16.837123 hours, **provisional** 4.07 hours
  (3.45–6.24), 2.30 GiB artifacts.
- Required credentials: none. Blocked optional families: pyannote, Falcon,
  NeMo, WeNet; all extended/component alternatives are excluded from this
  candidate pending selection.
- Machine A command:
  `powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_a.ps1`.
- Machine B command:
  `powershell -ExecutionPolicy Bypass -File scripts/launch_campaign_machine_b.ps1`.
- Merge command:
  `powershell -ExecutionPolicy Bypass -File scripts/merge_massive_campaign.ps1 -MachineATransfer <A> -MachineBTransfer <B>`.
- Analysis command:
  `powershell -ExecutionPolicy Bypass -File scripts/analyze_massive_campaign.ps1 -PrerequisiteEvidence automated_runs/campaign_04_standard_release/analysis/report/release_qualification.json`.

These launch commands are listed for handoff; they are not currently authorized.

## Execution evidence

- Genuine clean clone, new `.venv`, install, activation in PowerShell/cmd,
  `pip check`, Tiny/Base/Small plus ECAPA bootstrap/verification, and one real
  end-to-end CMU Arctic Base run passed. FFmpeg is the sole verifier failure.
- Installation smoke: one real scenario succeeded and was analyzed.
- Component canary: 15 scenarios generated/validated, not fully executed.
- Local two-worker shakedown: two real scenarios split, stopped/resumed,
  exported, transfer-validated, merged 2/2 without conflicts, and analyzed.
- Small (26), standard (41), and massive candidate (41) campaigns generate and
  validate, but none of the scientific gates has been run.
- Machine A complete assignment: 20/20 scenarios and 12,368 item executions
  inspected; all local scenario requirements pass. Global dirty/FFmpeg blockers
  correctly prevent launch.
- Machine B: remains `NOT_YET_TESTED`. Its complete 21-scenario assignment was
  statically cross-checked on A (21/21 scenario-specific checks, 13,430 item
  executions, 2,622 unique files), but that is explicitly not B environment,
  dataset, output, disk, hardware, or runtime evidence.

## Representative expected outputs

These are format examples, not fabricated scientific results:

```text
preflight: verdict=READY_TO_LAUNCH, assigned=21, preflighted=21,
           blocked=0, complete_assignment_preflight=true
campaign plan/validation: campaign_id + manifest_sha256 + scenario_count
status: pending/running/succeeded/failed/stopped counts
transfer: valid=true, worker_id, scenario_ids, unexported_scenario_ids=[]
merge: status=accepted, merged_scenario_ids=41, missing=[], conflicts=[]
coverage: planned=41, included=41, mandatory_unexpected_missing=0
release status: passed only when all checks and standard prerequisite pass
```

The actual bounded rehearsal produced an accepted merge with two validated
transfers, two merged scenario IDs, no missing IDs, and no conflicts. The final
report path will be
`automated_runs/campaign_05_massive_release/analysis/report/campaign_report.md`.

## Exact next actions

1. Review/commit/push Stage 14 once; check out that exact commit in both clean
   clones; run `python scripts/materialize_launch_campaign.py --bind-current-commit`
   on both; require byte-identical `release_binding.json` files; repeat
   clean-clone evidence.
2. Install FFmpeg and rerun A's complete preflight.
3. Run the component canary, then small and standard gates; select/freeze the
   actual finalists.
4. Have the second operator complete `machine_b_setup.md` and return both JSON
   evidence files. Rebalance/regenerate assignments if B measurements require it.
5. Only when both full preflights and scientific prerequisites pass, change the
   control-sheet verdict and execute the two launch wrappers.

Use [launch_control_sheet.md](launch_control_sheet.md) on launch day.
