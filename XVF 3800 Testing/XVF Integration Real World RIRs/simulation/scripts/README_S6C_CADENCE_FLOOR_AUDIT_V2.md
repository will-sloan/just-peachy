# Native cadence floor neighborhood audit

This additive helper audits actual C191–C194 native admissions after their entire
448-cell epoch5 batch, shared-replay parity and core scoring are complete. These
are the registered .5s and 2s voice-observation-floor neighbors of C071/C082.
All56 panel cases and both taps remain. It does not run models, rescore, read PCM
or query hardware. The old336-cell audit and all its source bytes are preserved.

The exact original `Accumulator`, causal/stream guards and two compact aggregation
statements are imported or compiled from the pinned original audit. Numeric
definitions do not change. New admission verifies epoch5, native/source/core grid,
registered parent/floor settings, exact canonical audio/cue and native finalization.
Each new event log is read and hashed once. Model/vector/audio payloads remain
transitively bound. Original C065/C071/C082 observations are reused only from their
certified compact audit, without reading those native logs a second time.

Inputs: exact completed core receipt, its448 native/shared prediction index and
native result index, immutable epoch5/registered amendment/input authority, old
audit and compact cells, and new actual event/summary/finalization bindings.
Outputs: fresh `reports/S6C/20260910T123540Z/cadence_floor_audit_v2/PLAN.json`,
`NATIVE_CELLS.json` and `RESULT.json`; a failed attempt preserves `FAILURE.json`.
The source refuses an active shared paced quiet lease. Use only one audit worker.
No automatic resume, result replacement or native retry exists.

Role opportunities, shared dispatches, actual embeddings, due ledger entries,
direct cue flags, released-state ages and nested costs remain distinct. An admitted
global window acknowledges all due ledger entries; it does not establish which
person's voice satisfied a debt. Separate onset/cosine/sole-cue causal contributions
are unavailable. Missing queue peaks stay null. Actual accelerated context ages,
calls and whole-worker costs cannot establish source-paced performance, general
cadence rejection or CM5 speed. Quality uses separate core support/word/return
denominators; these mechanism outputs do not create new accuracy scores.

## PowerShell

```powershell
$simTask = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$analysisTask = "$simTask\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
Set-Location -LiteralPath $simTask
& $analysisTask scripts/s6c_cadence_floor_audit_v2.py checks
# Only after exact native/parity/core closure; use the printed actual receipt hash.
& $analysisTask scripts/s6c_cadence_floor_audit_v2.py prepare --core reports/S6C/20260910T123540Z/cadence_floor_native_core_v3/ANALYSIS_RECEIPT.json --core-sha256 EXACT_COMPLETED_CORE_SHA256
& $analysisTask scripts/s6c_cadence_floor_audit_v2.py run --plan reports/S6C/20260910T123540Z/cadence_floor_audit_v2/PLAN.json --sha256 EXACT_PREPARED_PLAN_SHA256
```

## Anaconda Prompt or Windows CMD

No environment activation or installation is necessary; use the exact interpreter.

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_CADENCE_PY=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s5_text_metrics\analysis_env\Scripts\python.exe"
"%S6C_CADENCE_PY%" scripts\s6c_cadence_floor_audit_v2.py checks
"%S6C_CADENCE_PY%" scripts\s6c_cadence_floor_audit_v2.py prepare --core reports\S6C\20260910T123540Z\cadence_floor_native_core_v3\ANALYSIS_RECEIPT.json --core-sha256 EXACT_COMPLETED_CORE_SHA256
"%S6C_CADENCE_PY%" scripts\s6c_cadence_floor_audit_v2.py run --plan reports\S6C\20260910T123540Z\cadence_floor_audit_v2\PLAN.json --sha256 EXACT_PREPARED_PLAN_SHA256
```

`checks --output FRESH.json` writes a source-bound synthetic receipt. Tests prove
guard behavior and unchanged parser/aggregation use; they do not prove actual
batch completion. Exact real admission is deferred until `prepare` after closure.
