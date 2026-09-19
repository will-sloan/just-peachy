# S4 analysis and handoff commands

These commands complete the fixed S4 run after its source preparation and calibration. Read README_S4.md for safety, environments, inputs and the physical attempt limits. The run is `20260909T002140Z`. Scripts use absolute paths from `s4_common.py`; all commands below start in `simulation\scripts`.

`s4_audio_analysis.py` reads the saved native/decoded/mono recordings and scene manifest. It checks output conversion independently, counts rails and contiguous runs, measures approximate output-versus-recaptured-MIC0 correlation lag, and writes per-case `audio_metrics.json` and batch summaries. It never opens hardware. Its `--freeze-recipe` operation derives one O0 host gain from calibration peaks and refuses to overwrite an already frozen output policy.

`s4_spatial_batch.py` reads completed case, callback and telemetry files with the frozen scene/scoring policies. It writes per-case `spatial_metrics.json` and a batch summary using receipt-causal availability and explicit age limits. Estimated scene activity already contains the 50 ms RIR margin; the scorer counts that margin once. No speaker/seat truth enters H2 or the live adapter.

## PowerShell

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$env:OMP_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'

# Historical bounded calibration analyses; do not change or refreeze the policy after final capture.
& 'C:\Users\amiri\anaconda3\python.exe' s4_audio_analysis.py --batch calibration_base
& 'C:\Users\amiri\anaconda3\python.exe' s4_audio_analysis.py --batch calibration_limiter
& 'C:\Users\amiri\anaconda3\python.exe' s4_audio_analysis.py --batch calibration_agc

# The original final batch is preserved: scenes01-18 passed; scene19 had a
# telemetry-only failure with exact audio payload and successful restoration.
# The one diagnosed retry and remaining scenes use final_completion. Do not
# resume or overwrite the failed original final/S4_19 attempt.
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s4_hardware.py --batch final_completion --cases S4_19 S4_20 S4_21 S4_22 S4_23 S4_24 --recipe limiter_and_agc_headroom --final
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s4_hardware.py --batch repeat1 --cases S4_01 --recipe limiter_and_agc_headroom --final
& 'C:\Users\amiri\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' s4_hardware.py --batch repeat2 --cases S4_01 --recipe limiter_and_agc_headroom --final

# Run offline analysis after all captures/repeats have released/restored the
# device and ACCEPTED_FINAL_CAPTURES.json binds the complete accepted24.
# --batch final follows that manifest across final and final_completion;
# it writes output_alignment.json for all24 accepted scenes.
& 'C:\Users\amiri\anaconda3\python.exe' s4_audio_analysis.py --batch final
& 'C:\Users\amiri\anaconda3\python.exe' s4_audio_analysis.py --batch repeat1
& 'C:\Users\amiri\anaconda3\python.exe' s4_audio_analysis.py --batch repeat2
& 'C:\Users\amiri\anaconda3\python.exe' s4_spatial_batch.py --batch final
& 'C:\Users\amiri\anaconda3\python.exe' s4_spatial_batch.py --batch repeat1
& 'C:\Users\amiri\anaconda3\python.exe' s4_spatial_batch.py --batch repeat2

# First paired H2 case, then remaining cases using the same compatible execution contract.
& 'C:\Users\amiri\anaconda3\python.exe' s4_h2_run.py --cases S4_01 --alignment-json '..\reports\S4\20260909T002140Z\output_alignment.json'
& 'C:\Users\amiri\anaconda3\python.exe' s4_h2_run.py --alignment-json '..\reports\S4\20260909T002140Z\output_alignment.json'
```

## Anaconda Prompt / Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
"C:\Users\amiri\anaconda3\python.exe" s4_audio_analysis.py --batch final
"C:\Users\amiri\anaconda3\python.exe" s4_audio_analysis.py --batch repeat1
"C:\Users\amiri\anaconda3\python.exe" s4_audio_analysis.py --batch repeat2
"C:\Users\amiri\anaconda3\python.exe" s4_spatial_batch.py --batch final
"C:\Users\amiri\anaconda3\python.exe" s4_spatial_batch.py --batch repeat1
"C:\Users\amiri\anaconda3\python.exe" s4_spatial_batch.py --batch repeat2
"C:\Users\amiri\anaconda3\python.exe" s4_h2_run.py --cases S4_01 --alignment-json "..\reports\S4\20260909T002140Z\output_alignment.json"
"C:\Users\amiri\anaconda3\python.exe" s4_h2_run.py --alignment-json "..\reports\S4\20260909T002140Z\output_alignment.json"
```

Physical commands use the same arguments shown in PowerShell, without the initial `&` and with double quotes around the executable. The transport/calibration work consumed 13 physical passes. The 24 accepted final scenes, one preserved telemetry-only failed attempt and two nominal repeats bring the complete plan to the **40-pass cap**. No further calibration recipe or extra attempt is available within this S4 budget. Compatible completed cases are skipped. The single diagnosed retry is bound in `TELEMETRY_RETRY_DIAGNOSIS.json` and `TELEMETRY_RETRY_RESOLUTION.json`; it does not authorize replaying other failed or incompatible attempts.

`ACCEPTED_FINAL_CAPTURES.json` is the authoritative selection of 24 final captures, with one case-result path/hash and batch per canonical scene. Its only excluded failed attempt is the original `final/S4_19`; the accepted replacement is `final_completion/S4_19`. The accepted input bytes, code identity, final recipe, audio transport and telemetry must agree. H2 and final audio/spatial analyses use the shared `s4_capture_selection.py` reader, preserving all original captures and their outcomes.

## Frozen recipe and limitations

Dry sources use the one documented −24 dBFS active-RMS method with12dB maximum boost and0.5FS dry peak cap, applied once before RIR convolution. The common bank headroom scalar is1. RIRs and microphone channels are not normalized. Final device settings change only the declared headroom recipe: limiter power0.1175, AGC desired power0.001125, current/maximum gain62.5. Other baseline settings and the S3 input/output routing remain as recorded. O0 uses device ASR gain1 and one +3dB host adapter; O1 host gain1 preserves its original output. Clipped device samples remain marked as a limitation.

Frozen calibration results are evidence inputs to OUTPUT_LEVEL_POLICY.json. Do not rewrite their bound JSON during a compatible resume; skip already analyzed compatible files. The canonical bank and raw captures are retained locally. Missing or old spatial data produces `spatial_unavailable` while audio/text remain allowed. Host callback/telemetry timing, estimated source activity, and approximate correlation delay do not establish device-internal or live-caption latency.

Historical first-regression restoration hit a decimal/float32 round-trip issue. Its failure receipt remains. `README_S4_RESTORE.md` describes the bounded exact-getter recovery and tests; the recovery receipt binds the original failure and compares every recorded setting. Do not overwrite that history. Later batches use the corrected restorer.

README_S4_H2_ANALYSIS.md documents model/session isolation, scoring and resume. README_S4_RESULTS.md documents aggregation/plots. The final report, NEXT_PHASE_INPUTS.md, WORKBOOK_UPDATE.md and compact ZIP close S4. Do not start S5 or S6 from these commands.

Some completed H2 invocations returned exit zero with complete event/stdout journals and exact full-input PCM16 spools, but their native summary files were empty. The unchanged daemon watcher announces completion before its summary export finishes; a CLI exit race is supported by implementation evidence, without a direct thread trace. `H2_SUMMARY_RECOVERY.json` preserves the first S4_18/O1 case; subsequent `H2_SUMMARY_RECOVERY_<case>_<stream>.json` files preserve individually verified cases. These receipts bind the original empty files and failed runner receipts, primary completion evidence, unchanged execution/source identities and explicitly derived summaries. Original artifacts remain local. Each compatible runner resume scores the existing model session; it does not repeat that model invocation. See README_S4_H2_RECOVERY.md and the recovery helper's current README for the bounded recovery commands. A derived summary is not a native runtime export, and successful model completion does not remove this export limitation.

## Validate and package the completed handoff

`s4_handoff.py` consumes the finished accepted-capture manifest, all charged case receipts and exact restoration evidence, 48 completed H2 receipts/metrics, unchanged baseline and workbook bindings, frozen policies, aggregate metrics, authored reports and three or fewer plots. It does not produce missing model results or synthesize an approval. Do not call full validation while these required inputs are incomplete. The `--self-test` action runs 13 in-memory checks only and is safe independently of final-data completion.

PowerShell, from `simulation\scripts`:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s4_handoff.py --self-test
& 'C:\Users\amiri\anaconda3\python.exe' s4_handoff.py --validate
& 'C:\Users\amiri\anaconda3\python.exe' s4_handoff.py --package
```

Anaconda Prompt / Command Prompt, from the same directory:

```bat
"C:\Users\amiri\anaconda3\python.exe" s4_handoff.py --self-test
"C:\Users\amiri\anaconda3\python.exe" s4_handoff.py --validate
"C:\Users\amiri\anaconda3\python.exe" s4_handoff.py --package
```

Validation checks the Common Voice source-to-scene mapping, canonical-to-capture byte hashes, capture-to-H2 raw input hashes, frozen execution contract, budgets, every batch's restoration and the sole resolved telemetry-only retry. It requires aggregate status `COMPLETE_EVIDENCE_COUNTS`, 24 analyzed scenes, 48 completed H2 jobs, two analyzed repeats and no omissions; it verifies the aggregate's consumed JSON hashes. Per-case audio/spatial metadata, converter equality, scoring policy, H2 reference text, gain, job identity and alignment/scorer identity must match their accepted inputs. A critical blocked issue prevents a COMPLETE status. The package includes accepted/retry manifests, output alignment and the H2 execution contract. The current Word master must still match its preflight hash; it is indexed locally and never copied into the ZIP.

Every H2 invocation must have exit zero, COMPLETE status and no stale top-level failure. For each recovered summary, validation rechecks exact primary journals, transcript payloads, full-input PCM16 conversion, unique completion and full-source cursors, then matches the derived summary to the final metrics. Original job identity, process ID, arguments, start time and model wall time must remain unchanged. The failed receipt's error and end time must be retained in explicit recovery provenance. All recovery receipts are included in the compact ZIP and the aggregate's consumed bindings; original failed/empty files, journals, spools and derived summaries are indexed locally. Run-manifest native/derived counts are calculated from the actual receipts. Model weights are not rehashed or run by this validator.

Scene 22's all-zero payload has no uniquely identifiable sample offset. Validation accepts its explicitly documented null alignment only for that canonical silence case, with zero differences over all decoded microphone samples. Other scenes still require proof that all nonzero source payload was captured.

Successful packaging writes `simulation\handoffs\S4_CHATGPT_HANDOFF_20260909T002140Z.zip`, `reports\S4\20260909T002140Z\run_manifest.json`, `LOCAL_ARTIFACT_INDEX.json`, `package_receipt.json` and final status. The run manifest records elapsed wall seconds from `2026-09-09T00:21:40Z` through completed validation, before ZIP packaging; the later package receipt records elapsed time through packaging. Physical playback seconds and model compute seconds are reported separately.

The ZIP targets 10 MiB, must not exceed 20 MiB, contains at most three plots, and excludes raw audio, models, RIR files and Word documents. Compact evidence includes `ANALYSIS_TEST_RECEIPT.json`, its archived original 25-test receipt and exact tested summary-source snapshot, `SPATIAL_FINDINGS.md`, `FIGURE_INDEX.json`, `INDEPENDENT_AGGREGATE_AUDIT.json` and `PLOT_VISUAL_QA.json`. Validation checks the audit's final aggregate/CSV/figure-index hashes, exact observed aggregate counts and native/derived summary accounting. Visual QA must bind the final figure index; all explicitly bound QA files are checked. Archived test provenance is preserved separately from subsequent end-to-end analysis. These receipts add no figure. Every included member is listed and verified in `SHA256SUMS.txt`.

Rerun the same `--package` command after a transient packaging interruption. Each partial packet/ZIP attempt is preserved under a unique local name; a retry does not repeat captures or H2 jobs. A commit record also covers interruption between final ZIP promotion and receipt creation. Once the final ZIP exists, this command verifies its recorded hash and internal checksums and returns the immutable receipt. Use `--validate` separately if current local evidence needs rechecking. Do not delete historical evidence to make an incompatible resume pass.
