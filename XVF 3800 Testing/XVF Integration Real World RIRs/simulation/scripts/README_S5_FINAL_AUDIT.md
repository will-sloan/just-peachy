# S5 final native, provenance, reserve and host audit

`s5_final_audit.py` independently verifies the completed S5 development panel. It never launches H2, loads model assets, plays audio, accesses XVF controls, changes settings, or signals/terminates any process. `test_s5_final_audit.py` uses synthetic in-memory and temporary-file fixtures only.

## When to run

The root coordinator runs the full audit **after** the native runner has exited, the final text/support panels have refreshed, and the optional representation process has closed or produced an explicit supported skipped result. Running the full audit with pending jobs or active/unverified owners fails closed before waveform validation. Do not call the S4.5 resume scripts.

Use the already prepared S5 analysis interpreter. No additional installation is needed.

**PowerShell**:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:PYTHONDONTWRITEBYTECODE='1'
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' -m unittest -v test_s5_final_audit
# Optional metadata-only snapshot; never a final verification:
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s5_final_audit.py
# Only after inference and final scoring/diagnostic processes have finished:
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' s5_final_audit.py --require-complete
```

**Anaconda Prompt / CMD**:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
..\staging\s5_text_metrics\analysis_env\Scripts\python.exe -m unittest -v test_s5_final_audit
..\staging\s5_text_metrics\analysis_env\Scripts\python.exe s5_final_audit.py --require-complete
```

Default mode reads metadata dispositions and access receipts only. It performs no raw/adapter/journal waveform audit, live process query, SSD query, or native environment query. Active-file changes may make this snapshot unavailable; that is explicitly a partial observation, not a final evidence-failure claim.

## Inputs and authority

Paths come from `s5_common.py`: report `simulation/reports/S5/20260909T130308Z`, new large payload `G:\Just_Peachy_S5\20260909T130308Z`, and existing S4.5 bank/captures/native completions. The audit binds `run_manifest.json`, its exact byte-bound execution contract and 360-row job manifest, canonical 240-scene metadata, accepted-capture selection, source manifests, recipes and frozen scoring/decision protocols. Job identities use canonical serialized JSON hashes; file SHA-256 checks use actual file bytes. These domains are not interchangeable.

Required final inputs include:

- Every intended job's wrapper and its zero, one or two preserved attempt receipts; original S4.5 native receipts for the 48 reuse candidates.
- Bound original PCM24 outputs, fixed-gain mono FLOAT32 adapters, exact native PCM16 spool, summary, event journal, mixed JSON CLI stdout, and native metrics.
- `RUNNER_CLEANUP.json`, `resource_samples.jsonl`, `RESOURCE_PREFLIGHT.json`, `GIT_PREFLIGHT.json` and the actual final process observation.
- `TEXT_PANEL_RECEIPT.json`, `access/text_panel.json`, `support/SUPPORT_PANEL_RECEIPT.json`, `support/FROZEN_SUPPORT_INDEX.json`, and their bound current code/result files.
- `access/prepare.json`, `runner.json`, `support_freeze.json`, `support_metrics.json`; `support_last_invocation.json` is a duplicate observation and is not counted as independent access evidence.
- `representation/WINDOW_PLAN.json`, `RUN_RECEIPT.json`, `RESULTS.json`, `RESERVE_ACCESS.json`, and `PROCESS_CLOSURE.json` for an executed diagnostic. A genuinely empty, bound plan with an explicit skipped result is handled separately. Vectors are not read or packaged by this audit.
- S0 baseline, unchanged H2 scientific sources/configuration plus the authorized v3 lifecycle fix, V10 master workbook, real 64-character RIR-manifest identity, `INPUT_COVERAGE_REVIEW.json`, `PREFLIGHT_CORRECTION.json`, and the preserved preflight contract archive.

Development permission is checked before opening every job/task input. Unexpected task directory names under S5 native payload, text and support outputs are inventoried and refused before reading their contents. Reserve metadata remains permitted. Component guard evidence is combined explicitly; missing components do not become zero-access observations. This is an application-boundary/provenance audit, not an OS-wide file-access trace.

## Native and scientific checks

The exact 180 development IDs × O0/O1 must match the sorted, counterbalanced manifest. Required identities join source metadata, selected capture, raw audio, recipe, gain, isolated root, native argv and successful attempt. Reused jobs cannot have new attempts. Fresh jobs allow one identical retry, with all failed receipts retained. Completed wrappers must equal the unique successful native attempt or point to the unchanged prepared historical receipt. Failures remain failures; they are not empty successful transcripts.

The audit independently reproduces raw→fixed FLOAT32→complete PCM16 using the established audit implementation, rather than trusting the runner's completion flag. Existing positive PCM24 rails and the unchanged PCM16 clamp are retained. A second gain, changed sample, missing/truncated journal, source path mismatch, reconstructed summary, nonterminal completion, missing zero-drop counter, changed asset/policy identity, transcript/event mismatch, or different native source cursor blocks verification. It requires exactly one completion event and the actual startup ordering. Summary/completion/final CLI telemetry must agree, apart from monotonically increasing recorded elapsed time. Final short analysis tails remain explicit and unscored.

Eight native asset identities and all scientific source/config bindings must match S0 plus the exact two-file v3 durability repair. The final audit does not repeat model-weight hashes or hash all 121 RIR waveforms. It relies on unchanged source/config authority and each native model initialization's internal validation, and checks current package metadata with a short read-only subprocess using the frozen H2 Python; this subprocess imports no model. The native CPU/provider contract remains unchanged.

Final text/support receipts must match the successful native population, current protocol and bound result/code files. This is a freshness/provenance check; the root results review independently checks score arithmetic and scientific conclusions. Representation COMPLETE additionally requires one loaded backend and every frozen paired window exactly once with matching case/output/interval and COMPLETE status.

## Resources, process closure and limitations

Before and after the full audio verification, a read-only CIM query observes all recorded model/runner/representation PIDs and relevant S5 command lines. PID plus creation time distinguishes a live owned process from PID reuse. Historical S4.5 receipts lacking creation time remain explicit; a present PID is treated as reused only if its current creation strictly follows the bound historical completion. The audit never terminates by PID or performs any process control. The runner's unconditional `owned_child_remaining` declaration is not used as proof of closure.

SSD identity follows the validated `Win32_LogicalDiskToPartition` → `Win32_DiskDriveToDiskPartition` associations, joined to `Get-PhysicalDisk` by exact trimmed serial and model. `Get-Disk` is an optional identity/health supplement; its absence for G: is not a disk failure. Current identity must match preflight, with at least 50 GiB free on C: and 75 GiB on G:. This is Windows provider observation, not an exhaustive SMART/stress test.

New logical-byte accounting includes report, G: payload, all `staging/s5_*` directories (including the isolated analysis dependency), S5 scripts/tests/READMEs and any existing matching handoff ZIP. It excludes existing source/RIR/capture/model trees and allocated-block overhead; the cap is 40 GiB. A ZIP created after the audit is added separately by the final packaging receipt. Current RAM and recorded model process-tree samples must respect 8 GiB OS headroom and 40 GiB model RSS caps. Report sampled peak, not continuous maximum. Historical/new child wall and audio totals remain separate; neither is live latency or CM5 fit.

## Outputs and statuses

The tool writes only files prefixed `FINAL_AUDIT` under the S5 report directory. Each invocation preserves an immutable timestamped JSON plus a byte-identical current alias:

- Full: `FINAL_AUDIT_<timestamp>.json` and `FINAL_AUDIT.json`.
- Metadata only: `FINAL_AUDIT_PARTIAL_<timestamp>.json` and `FINAL_AUDIT_PARTIAL.json`.
- During full job verification: atomic `FINAL_AUDIT_PROGRESS.json`, explicitly not final, updated by bounded row/time intervals.

`PASS_ALL_360_NATIVE` means all 360 native completions verified, normally 48 reused and 312 fresh. `VERIFIED_TERMINAL_COVERAGE_WITH_FAILURES` preserves visible FAILED/QUARANTINED dispositions if every intended row is terminal and all applicable evidence checks pass. `BLOCKED` means missing/invalid evidence or unresolved ownership; it is not a model accuracy score. Default partial statuses never certify completion. Errors return a nonzero exit code, with evidence bindings and an immutable failure receipt preserved. The final `counts` and `native_totals` carry explicit reused/fresh/job/sample/runtime denominators. `reserve_protection`, `conservation`, `panel_freshness`, `resources`, `git` and before/after `process_closure` document their actual scope and observation times.

The tested version is bound in `staging/s5_final_audit/TEST_RECEIPT.json`, including exact code/test/README and inherited audit helper identities. Tests use only temporary fake audio/events/receipts and in-memory process/access records. The initial 21-test source/output snapshot is retained in `initial_21_tests`; later fixtures cover the reviewed representation metadata joins, nonfinite process identity and positive-rail clamp. No actual final audit is implied by passing fixtures.
