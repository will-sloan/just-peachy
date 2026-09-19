# S5 reference support and native evidence diagnostics

`s5_support_metrics.py` implements offline, development-only diagnostics for the existing S4.5 captures. It does not call models, operate USB/audio hardware, modify the scene bank or change H2. The coordinator owns the scoring protocol, full-panel invocation, results aggregation and reports. `s5_support_panel.py` freezes and resumes the complete authorized support panel. `test_s5_support_metrics.py` exercises synthetic deterministic fixtures by default, with an explicit historical integration mode.

Inputs are the exact frozen scene dictionary, accepted capture result, saved audio-mapping metrics, MUSAN prepared-source catalogue, frozen scoring protocol SHA-256, native completed job receipt and optionally the one shared capture callback/telemetry trace. Files consumed through `DevelopmentGuard` require their expected SHA-256; identical unchanged files use a verification cache. Reserve permissions are checked before path stat, hashing, task-log parsing or audio reads. The coordinator must apply the same guard before loading metadata that itself contains task performance. Metadata-only scene inventory can include reserve rows.

Outputs are JSON-compatible dictionaries: a versioned source support record, per-output support/segmentation/embedding/anonymous-continuity metrics, one shared noise-direction record per physical scene, and a component access receipt. This module does not write result files automatically. The coordinator saves these dictionaries under its S5 report/payload directories and combines the access receipt with other components. There are no new trained models, enrollment profiles or inferred speaker names.

## Run the fixtures

PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
& 'C:\Users\amiri\anaconda3\python.exe' -m unittest test_s5_support_metrics -v
& 'C:\Users\amiri\anaconda3\python.exe' s5_support_metrics.py --describe-policy
```

Anaconda Prompt or Windows command line with the explicit Anaconda executable:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s5_support_metrics -v
"C:\Users\amiri\anaconda3\python.exe" s5_support_metrics.py --describe-policy
```

Existing NumPy and SoundFile are sufficient. Shared direction diagnostics import the existing pure `s4_spatial_analysis` timing/receipt helpers; importing these does not initialize USB or run hardware. No package installation is required. Restrict parallel metadata tasks to at most four workers; the module itself creates no worker pools or numerical threads.

An explicitly bounded historical integration regression is also available. It opens only the24 already inspected development sentinel scenes and their48 existing native jobs, freezes source-only support in memory, checks every inherited gate counter and successful-call count exactly, and prints a compact provenance receipt. It does not run models or compare the new full panel. The fixture suite itself does not perform this integration unless requested:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' test_s5_support_metrics.py --prior24-regression
```

```bat
"C:\Users\amiri\anaconda3\python.exe" test_s5_support_metrics.py --prior24-regression
```

The initial observed regression passed all24 scenes/48 outputs, with identical native gate/call counts. Saved output mapping was unavailable for both outputs in `S45_12_01` and `S45_12_15`, and was preserved as unavailable. Source-only masks for the four historical real-noise sentinel scenes were generated successfully. These regression facts are not new output-ranking evidence; the coordinator records current test receipts and code bindings.

## Bulk support panel and resume

The driver consumes the frozen S5 `run_manifest.json`, `SCORING_PROTOCOL.json` and360-row `JOB_MANIFEST.json` under `simulation/reports/S5/20260909T130308Z`. It validates the exact180 development pairs against the canonical manifest. The S5-bound pack artifact index resolves the saved capture-analysis index, whose per-scene spatial receipts bind the callback metadata and raw telemetry. These files are selected by exact verified bindings, not WAV globs. Only development task metadata is opened. The39 real-noise scenes receive new event-local shared telemetry metrics; the other141 retain their existing shared whole-capture availability once.

Run `freeze` before full support comparisons. It writes180 deterministic input-only support records under `support/source/` and `support/FROZEN_SUPPORT_INDEX.json`. Re-running verifies identical contents. Changed masks/protocol/inputs block instead of silently replacing the frozen records. `score` consumes that frozen index, scores the one shared direction trace per scene, and scores only completed native outputs currently available. It leaves pending/failed native rows visible in the360-row receipt; rerun the same command after later jobs complete. It does not launch or retry models.

PowerShell, after changing into the scripts directory as above:

```powershell
& 'C:\Users\amiri\anaconda3\python.exe' s5_support_panel.py freeze --workers 4
& 'C:\Users\amiri\anaconda3\python.exe' s5_support_panel.py score --workers 4
```

Anaconda Prompt / Windows command line:

```bat
"C:\Users\amiri\anaconda3\python.exe" s5_support_panel.py freeze --workers 4
"C:\Users\amiri\anaconda3\python.exe" s5_support_panel.py score --workers 4
```

`all` performs freeze then score in that order. Choose `--workers 1` for serial analysis during other CPU-intensive work; values above4 are refused. A score invocation is bounded to the current inventory and returns without waiting for future model completions. Resume uses exactly the same command. It reuses self-consistent metrics only when code, protocol, support and native input identities match. New metrics live in `support/outputs/<case_id>/O0.json` and `O1.json`; each contains `metrics`, a semantic checksum, and bound provenance. Shared metrics live in `support/shared_direction/<case_id>.json`. `support/SUPPORT_PANEL_RECEIPT.json` contains all360 statuses, result bindings, counts and limitations, while `support/status.json` reports progress. The driver writes component access receipts under `access/` even when an invocation stops with an exception.

There is no duplicated audio tree or large derived waveform cache. Raw journals and outputs remain in their accepted original locations. Full local metrics can be larger than the compact handoff; the coordinator chooses small aggregate tables for the ZIP. Shared direction rows must never be joined as two independent output treatments. Resume deliberately blocks when analysis identity changes; preserve an earlier analysis version explicitly rather than editing its frozen inputs or cached results.

## Coordinator API and ordering

```python
from s5_support_metrics import (
    POLICY, DevelopmentGuard, freeze_scene_support,
    analyze_bound_output, shared_direction_metrics,
)

# scenes is the verified frozen scene metadata list, not a folder/WAV glob.
guard = DevelopmentGuard(scenes, scoring_protocol_sha256=protocol_sha256)
guard.require(scene, 'support_freeze')
capture_result = guard.read_json(scene, accepted_case_result_binding)
audio_metrics = guard.read_json(scene, accepted_audio_metrics_binding)
support = freeze_scene_support(scene, capture_result, audio_metrics,
                               noise_catalog, guard)
# Save support and its support_sha256 BEFORE full paired scoring.
# Bind POLICY in the coordinator's SCORING_PROTOCOL.json before comparisons.

guard.require(scene)  # Refuses if protocol absent or scene is not development.
receipt = guard.read_json(scene, native_job_receipt_binding)
output_metrics = analyze_bound_output(scene, support, output, receipt, guard)

# Load callback_metadata and telemetry_rows using guarded, bound input readers.
shared = shared_direction_metrics(scene, support, capture_result,
                                  callback_metadata, telemetry_rows, guard)
component_reserve_receipt = guard.receipt()
```

`freeze_scene_support` accepts either the full noise catalogue (`prepared_segments`) or a dictionary keyed by noise ID. It verifies and reads only the exact scheduled noise crop from the already prepared development parent. It does not read output audio or predictions. The caller can initialize the guard without a protocol while freezing input support; output performance functions then refuse until a protocol is supplied. Bind saved support files externally as well as checking the embedded semantic support hash. Reuse the same record for both outputs; never rebuild masks from their favorable results.

For an in-memory fixture/integration, `score_output(scene, support, output, events, pcm16, raw_pcm24, guard)` accepts actual signed PCM16 journal counts and signed PCM24 preadapter raw output counts. Do not pass normalized floats or apply host gain to either array again. `analyze_bound_output` reads these exact bound files from the native completed job receipt, checks mono16-kHz PCM24 raw format and the frozen gain identity, and invokes `score_output`. Failed/incomplete native jobs are rejected; the coordinator retains them in its job/failure denominator.

## Timing, populations and interpretation

All source intervals are integer half-open16-kHz sample intervals. Existing `activity_ranges_samples_estimated` contains absolute source schedule plus800 samples already. A dry-file fallback adds800 once and has no estimated-active-duration bin. Actual empty estimated activity remains empty. Whole-clip duration and union active duration are separately binned `<1s`, `1-<2s`, `>=2s`; no nonexistent corpus/split coverage is generated.

Real-noise masks use the exact scheduled crop and unchanged S4 source estimator: nonoverlapping320-sample frames, threshold `max(-50 dBFS, frame RMS p95 minus25dB)`. The final incomplete frame is explicitly unestimated. These are source-energy indications, not speech labels. Crop offsets are relative to the prepared parent; activity is placed at source-start plus800 once. Full scheduled convolution envelopes retain onset/tail uncertainty. Quiet is outside all component convolution envelopes, not any low-energy gap. Active speech, active noise, speech/noise overlap and multiple-speaker activity are overlapping named diagnostic regions; do not sum them as disjoint time.

Saved source-to-capture offset and saved per-output correlation lag are added once. No output shifts are refitted. Their observed lag spread and the20-ms source activity grid are reporting uncertainty, not calibrated phonetic latency. Missing saved output lag makes output-local reference metrics unavailable, while whole-output native flags, embedding workload and levels remain available. Do not silently substitute zero. Five clocks remain distinct: dry source schedule, retained RIR origin, microphone capture, processed output and callback/host availability.

Native segmentation events contain boolean flags based on the last44 model frames (nominal0.7425s), emitted every0.75s. Their interval intersection with reference support is a coarse source-supported indication. It is not precise phonetic VAD, recognized short-reply accuracy or a final-transcript timing measurement. Each turn retains observed support, positive-flag intersection, partial/missing observation and first/last positive interval uncertainty. A negative flag over only part of the support does not prove a whole-turn miss: `missed_supported_flag` is null there, while `no_positive_on_observed_support` describes the narrower observation. Native whole-output flag durations remain available when saved source/output mapping is missing. Transcript omissions and event-local inserted words remain unavailable from final-consumed-audio cursors alone; ordinary/overlap/attributed text scoring belongs to the separate text scorer.

Embedding gate reconstruction uses exact journal PCM16, each0.25-s hop RMS, the last emitted segmentation state,0.5-s minimum window and frozen RMS0.002. Blocking reasons overlap. Actual speaker decisions represent successful calls; unlogged rejected model calls remain unavailable. Windows use actual exported evidence intervals and check the unchanged contract, or explicitly use that same configured window from a native decision cursor if an older export omitted intervals. Report summed window duration and interval-union evidence duration separately. These windows overlap and are not independent trials.

Continuity uses the whole RIR-shifted clip support, consistent with the inherited file-support rule: an entire embedding window must belong to one utterance and intersect no other scheduled utterance. Additionally report strict-active containment. Native anonymous labels and exported cluster IDs stay distinct; no post-merge lineage is invented. Dominant ties, missing evidence or missing label observations keep returning-person groups unknown. All returning-person groups retain consistent/inconsistent/unknown in their denominator. Per-turn label switches are decision variation, not DER, identity errors or reconciliation events. Seat changes/short replies and family identifiers are reported as condition labels.

One shared telemetry record is scored once per scene using actual callback availability and last-received causal values. It is not duplicated into two independently improved O0/O1 traces. The inherited250-ms receipt age remains a causal availability policy, not end-to-end latency or proof of DSP freshness. Environmental recordings with unknown speech generate noise-associated indications, never certified false-speech rates. Instrumental `vocals=N` eligibility retains the original annotation limitation. No target-only processed SNR is inferred from nonlinear mixtures without isolated output stems.

Unknown ambient speech prevents known-source attribution even inside a scheduled target turn. Such return groups remain `unknown` with the explicit ambient-reference reason; their actual label observations are retained descriptively. Overlapping scheduled turns can have aggregate segmentation flags without supporting source-specific detection. `source_specific_supported_detection` is unavailable for these cases; never aggregate `detected_supported_flag` as if it were talker-specific overlap recall. Complete-reference single-source temporal evidence remains a proxy, not recognition or identity proof.

Rail/energy summaries explicitly distinguish original24-bit output from post-adapter journal16-bit audio, both whole decoded file and source-supported regions where mapping exists. Raw packed XVF clears its least significant bit, so the inherited positive rail is8388606 (`2**23-2`), with negative rail-8388608; the PCM16 journal criterion is32767/-32768. Longest runs do not bridge gaps between support intervals. Empty supports return null RMS/peak rather than zero-valued accuracy. Whole-file padding/silence stays in the whole-file denominator. The coordinator must retain original gross-quarantine rules and LIMITED rail flags independently of these descriptive metrics. The historical integration also reproduces all48 saved raw rail counts, run counts and maxima exactly.
