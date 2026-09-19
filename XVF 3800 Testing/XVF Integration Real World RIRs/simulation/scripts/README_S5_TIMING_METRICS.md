# S5 native timing and emitted transcript revisions

`s5_timing_metrics.py` is a pure reporting helper. It accepts already verified native receipts/events and a canonical development scene; it opens no files, loads no models, and touches no processes or hardware. It preserves historical reused versus fresh S5 timing as separate origins. `test_s5_timing_metrics.py` contains model-free fixtures.

## Inputs and integration

The root scorer first calls its development guard, verifies the input hashes, and resolves a reused wrapper to its original S4.5 native `run_receipt.json`. Fresh jobs use the native S5 attempt receipt. Pass native event objects from that exact session.

```python
from s5_timing_metrics import analyze_timing

result = analyze_timing(
    native_receipt, native_events,
    scene=canonical_scene,
    development_ids=guard.allowed,
    origin='reused_s45',  # 'fresh_s5' for a native S5 attempt
)
```

The adapter independently checks development permission first. It rejects failed/nonzero receipts, case/stream or origin/schema mismatch, missing/duplicate lifecycle events, nonterminal completion, missing raw transcript text, duplicate finals, events following a final for the same utterance, and inconsistent native/adapter duration. It does not replace the main audit's input hash, complete PCM16, asset/science, and process closure checks.

## Outputs and interpretation

The JSON-compatible result has `schema: jp_s5_timing_metrics_v1`, scene/output/origin, `timestamps_utc`, `intervals_s`, unavailable reasons and host-clock anomalies. It reports receipt→process creation (fresh when recorded), process→session creation, session creation→session start→source start→session completion→observed child exit→completed analysis receipt. It retains the exact monotonic `model_child_wall_s`, native completion telemetry elapsed time, decoded audio duration, both ratios, and recorded short unanalysed tail separately.

These durations have different boundaries. The source-start/completion interval combines accelerated processing and lane drain. Completion/exit combines remaining export and CLI/process finalization. Exit/completed receipt is host verification and legacy scoring after the model process ended. No timestamp isolates model loading, summary-file write time, or true user-visible word/name latency. Historical process-start timestamps and queue waits remain null when unrecorded; they are never inferred from elapsed duration. Negative UTC intervals become LIMITED/null, preserving the signed discrepancy rather than silently taking its absolute value. A final process audit must verify PID plus creation time; this helper makes no current-process observation.

`transcript_revisions` groups native partial/final events by utterance index in journal order, using raw `payload.text`. It separates prefix appends from rewrites and records suffix token removals/additions, raw versus normalized text changes, actual emitted-label changes, missing labels, first-partial/final snapshot differences, and explicit missing finals. An incomplete word changing from `NO` to `NORTH` is a rewrite, not evidence of an ASR error. Suffix counts are **not** edit-distance errors or ground-truth corrections. Display punctuation is excluded. Labels remain actual snapshots; no cluster merge/reconciliation, enrolled naming, or corrected-identity lineage is inferred. There is no independent-scene population claim from overlapping updates.

The main aggregation may sum transition counts and report the number of utterances exhibiting changes, with all denominators. Keep cached historical timing separate from fresh jobs at the fixed one-worker setting. Do not claim faster live captions from offline child wall alone.

## Run focused verification

In **PowerShell**:

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:PYTHONDONTWRITEBYTECODE='1'
& '..\staging\s5_text_metrics\analysis_env\Scripts\python.exe' -m unittest -v test_s5_timing_metrics
```

In **Anaconda Prompt / CMD**:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set PYTHONDONTWRITEBYTECODE=1
..\staging\s5_text_metrics\analysis_env\Scripts\python.exe -m unittest -v test_s5_timing_metrics
```

The interpreter is the already prepared S5 analysis venv; no additional dependency installation is required. Directly executing the library produces no report. The root scorer calls `analyze_timing` only after protocol freeze and writes its returned dictionary into bound S5 metrics. Tests use synthetic timestamps/events, not new model runs. Test output and exact code/test/README bindings are preserved under `simulation/staging/s5_timing_metrics`.
