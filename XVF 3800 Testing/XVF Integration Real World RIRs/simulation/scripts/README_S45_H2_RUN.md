# S4.5 bounded H2 runner

`s45_h2_run.py` runs only the 24 predeclared development sentinels on O0 and O1 (at most 48 captured-output invocations), plus at most 24 predeclared unique whole-clip dry controls. It never opens an audio/USB endpoint. Jobs run sequentially in the established H2 CPU environment; each has an independent initially empty data/profile root. No truth, identities, seat labels or transcripts are passed to H2. Reserve task scoring and training are prohibited.

The S0 source/configuration baseline is checked before execution. Exactly the two runtime/CLI source hashes recorded in `staging/s45_h2_fix/v3/FIX_RECEIPT.json` are allowed to differ. Revision 3 retains atomic summary/writer completion and publishes startup before any worker starts, preventing very short completion or immediate failure from being overwritten by startup state. Every other baseline source and scientific parameter must match S0. The old S4 runner/scorer/recovery evidence remain unchanged. Each native CLI invocation performs its normal eight-asset validation; this adapter does not repeatedly hash model weights outside the CLI.

## Inputs and gates

- `scene_bank/s45_v2_20260909T031300Z/SCENE_MANIFEST.json`: active validated canonical bank and all source/reference provenance. The superseded v1 input bank is preserved and is not a model input.
- `reports/S4_5/20260909T031300Z/SENTINEL_PLAN.json`: exactly two development scenes per each of 12 families, frozen before H2.
- `DRY_CONTROL_PLAN.json`: created by `--prepare-plans` before any model job. Deterministic round robin across corpus, quality and whole-clip duration bins, then shortest clip/source ID within each bin; identical decoded PCM is used once. Controls use the frozen source-preparation gain. No RIR, family headroom, relative-source gain or output-stream gain is applied to a dry control. This is a corresponding-source ASR floor, not a matched isolated device treatment effect.
- `ACCEPTED_CAPTURES.json`: the coordinator's authoritative accepted attempts. Each job binds its chosen receipt/input/output hashes. Later accepted additions do not invalidate already completed jobs.
- Each selected capture's `s45_analysis_receipt.json` and `audio_metrics.json`: accepted-attempt provenance, measured output alignment and gross-saturation gate. A grossly saturated stream receives an explicit `QUARANTINED` receipt/metric row and zero model invocations; valid paired and other outputs continue. The intended denominator remains 48 with separate completed, quarantined, failed/incomplete and pending counts. Transport/provenance failures still stop for diagnosis. Missing qualified lag retains transcript analysis but disables truth-matched turn continuity.
- Frozen output policy: O0 host scalar 1.4125375446227544 (+3 dB), O1 1.0. Raw PCM24 outputs are preserved; adapters are explicit mono 16-kHz FLOAT WAV. Any gain that would exceed numerical headroom fails without retuning.
- `H2_RELEASE.json`: coordinator-created `{ "status": "AUTHORIZED_OFFLINE_H2", "allow_during_physical_capture": false }`. The coordinator may set the boolean true only after its transport/scheduling review. This does not grant the runner hardware ownership. With false, unfinished physical work or unreleased restoration blocks execution.

Default alignment comes directly from the bound selected capture analysis. An optional `--alignment-json` accepts the established case-to-stream measured-delay/evidence mapping. Preserve the same mapping on resume: changing it changes the analysis identity, although it never reruns a compatible completed model job.

## PowerShell commands

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\anaconda3\python.exe'
& $py "$sim\scripts\s45_h2_run.py" --help
& $py "$sim\scripts\test_s45_h2_run.py"
& $py "$sim\scripts\s45_h2_run.py" --prepare-plans
# Read-only validation after the chosen captures and their analysis exist:
& $py "$sim\scripts\s45_h2_run.py" --kind outputs --cases S45_01_01 --validate-only
& $py "$sim\scripts\s45_h2_run.py" --kind dry --validate-only
# Only after coordinator release; first scene is two of the 48 output jobs:
& $py "$sim\scripts\s45_h2_run.py" --kind outputs --cases S45_01_01
# After all 24 predeclared sentinels are accepted and analyzed:
# Reuse completed compatible jobs and finish the remaining output jobs.
& $py "$sim\scripts\s45_h2_run.py" --kind outputs
& $py "$sim\scripts\s45_h2_run.py" --kind dry
```

## Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" test_s45_h2_run.py
"C:\Users\amiri\anaconda3\python.exe" s45_h2_run.py --prepare-plans
"C:\Users\amiri\anaconda3\python.exe" s45_h2_run.py --kind outputs --cases S45_01_01 --validate-only
"C:\Users\amiri\anaconda3\python.exe" s45_h2_run.py --kind dry --validate-only
REM After coordinator release:
"C:\Users\amiri\anaconda3\python.exe" s45_h2_run.py --kind outputs --cases S45_01_01
"C:\Users\amiri\anaconda3\python.exe" s45_h2_run.py --kind outputs
"C:\Users\amiri\anaconda3\python.exe" s45_h2_run.py --kind dry
```

`--cases` accepts exact sentinel IDs and always handles both streams. Without `--cases`, `--kind outputs` requires all 24 planned sentinel captures and their analysis; it does not automatically select only the currently accepted subset. Use an explicit `--cases` list when only a chosen subset is accepted and analyzed. `--control-ids DRY_01 DRY_02` selects exact frozen dry controls. Neither option can introduce new cases. Default per-model timeout is 240 seconds; `--timeout-s` may be 66–600 seconds, but the run deadline and 30-minute closing reserve still apply. Use existing environments; no installation is required. The adapter launches `just-peachy/.edge-speech-env/python.exe -m app.edge_speech_pipeline file <adapter.wav> --accelerated` internally with the fresh `EDGE_SPEECH_DATA_ROOT`.

## Outputs, resume and interpretation

Metadata is written to `reports/S4_5/20260909T031300Z/h2/<case>/O0|O1` and `h2_dry/<DRY_nn>`: `run_receipt.json`, `metrics.json`, stdout and stderr. Audio adapters, native PCM16 spools, session journals and native atomic summaries are on `G:/Just_Peachy_S4_5/20260909T031300Z/h2` or `h2_dry`. The shared execution contract, counts and atomic progress records remain in the report. The runner records child PID, actual exit status, process wall time, file/code/policy/selection bindings and exact native full-input PCM16 verification. Final analysis can stop at the last full hop before the complete file end; full journaling does not invent a tail decision.

Resume only reuses compatible completed invocations and can finish post-model scoring after interruption. Prior incomplete/nonzero-exit work stops for diagnosis; it is never silently repeated. Native summaries must be complete, contain no reconstruction marker and agree with one completion event and an exact full PCM16 spool. S4.5 does not silently apply historical summary reconstruction. The single runner lock prevents two model coordinators from exceeding the 48/24 budgets. Deadline/storage/stop receipts prevent new launches and retain partial counts.

Metrics retain explicit word/character substitutions, deletions, insertions and reference denominators. Aggregate valid nonoverlap counts, not means of per-case WER. Overlap remains LIMITED. Untranscribed/uncertain speech in ambient recordings makes ordinary all-speaker WER/CER LIMITED; a separately named target-only diagnostic can show raw counts but must never be pooled as ordinary WER. False-word rates are meaningful only for genuinely speech-free controls. Source corpus/quality strata remain visible. Speaker continuity uses fully contained source-file support with qualified output alignment; it is not DER, enrollment accuracy or calibrated live latency. One native dry clip and a multi-turn processed scene do not create a paired single-clip score.

`test_s45_h2_run.py` runs only small local numerical/schema fixtures and baseline source/config checks. It tests reserved-source rejection, sentinel family counts, unique bounded dry selection, pre-model plan freeze, ambient-reference limits, missing-lag limits, exact native spool completion, frozen gain preservation and invocation caps. An integration fixture executes the actual runner loop with a fake child: a grossly saturated O1 is quarantined, valid O0 runs once, and resume adds no model invocation. It executes no neural models or hardware.
