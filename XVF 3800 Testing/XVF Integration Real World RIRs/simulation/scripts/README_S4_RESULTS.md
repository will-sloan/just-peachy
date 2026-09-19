# S4 result aggregation and figures

These two scripts summarize existing final S4 evidence. They do not regenerate RIRs or scenes, open an audio endpoint, operate USB, or run an H2 model. Run them after the physical coordinator has completed/released all captures and after audio, spatial and H2 analysis have finished. Plotting reads three short received-telemetry traces and uses Matplotlib on the existing Anaconda Python; no FFT or model processing is performed.

## Inputs and outputs

The fixed run is `simulation/reports/S4/20260909T002140Z` and the bank is `simulation/scene_bank/s4_v2_20260909T002140Z`, as defined by `s4_common.py`.

Required inputs:

- Frozen `SCENE_MANIFEST.json`, `SOURCE_AND_SPLIT_MANIFEST.json`, `OUTPUT_LEVEL_POLICY.json` and `SPATIAL_SCORING_POLICY.json`.
- `ACCEPTED_FINAL_CAPTURES.json` authoritatively binds exactly one successful final capture per canonical ID. Each `cases` entry has `case_id`, `batch` and a hashed `case_result` binding. The accepted folders may span `hardware/final` and `hardware/final_completion`; original failed attempts remain preserved and listed in `excluded_attempts`. Each accepted folder supplies `case_result.json`, `audio_metrics.json` and `spatial_metrics.json`.
- Nominal repetitions at `hardware/repeat1/S4_01` and `hardware/repeat2/S4_01`, with the same three analysis files. Repetitions remain separate attempts of scene 01.
- H2 `h2/execution_contract.json` and `h2/S4_XX/O0` and `O1`: `run_receipt.json` and `metrics.json`, exactly 48 ordinary output jobs. The contract must retain the selected scene/output policy hashes, fixed gains and unchanged execution/scoring code hashes; each job must name that contract identity.
- For figures, calibration audio metrics from `calibration_base`, `calibration_limiter` and `calibration_agc` for the common scene IDs 01, 02 and 03. The direction figure additionally reads `capture_metadata.json` and `telemetry/received_telemetry.jsonl` for accepted scene 01 and its two repetitions.

`s4_summary.py` writes `per_case_metrics.csv` (48 planned rows, one per scene/output) and `summary_metrics.json`. It checks final capture/scene identities, fixed gains, metric hashes, complete transcript references, and the frozen spatial scoring policy. Missing or invalid required evidence produces an INCOMPLETE summary and a nonzero exit. `--partial` explicitly produces PARTIAL artifacts even if the currently available inputs happen to be complete; it is for inspection only and must not become the final completion claim.

`s4_plots.py` writes exactly three PNGs and three small CSV data files under `reports/S4/20260909T002140Z/plots`, plus `FIGURE_INDEX.json` with hashes and input provenance:

1. `figure_01_headroom`: pooled rail counts/sample denominators from matched 01/02/03 calibration captures, final raw/projected fixed-gain peaks and final O1 rail density. Per-case calibration values remain in the CSV. This is numerical headroom evidence, not an output-accuracy ranking.
2. `figure_02_text`: paired per-scene WER, pooled errors/reference words and empty-reference insertions per minute. Overlap scenes are shaded and have no ordinary WER points.
3. `figure_03_directions`: selected processed/raw-auto observations for final scene 01 and its repetitions on the host callback-availability clock. Gray reference bands preserve the whole folded manual ±5° interval. Gaps indicate an unavailable cue; no future interpolation or fitted timing shift is used. Reference activity ranges come from the corrected spatial scorer, with the retained RIR margin applied once.

## PowerShell commands

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\anaconda3\python.exe'
& $py "$sim\scripts\s4_summary.py" --self-test
& $py "$sim\scripts\s4_capture_selection.py" --self-test
# After all physical capture, restoration, and ordinary H2 jobs:
& $py "$sim\scripts\s4_summary.py"
& $py "$sim\scripts\s4_plots.py"
```

Optional inspection of incomplete evidence, after physical capture is no longer active:

```powershell
& $py "$sim\scripts\s4_summary.py" --partial
& $py "$sim\scripts\s4_plots.py" --partial
```

After more evidence becomes available, run the two full commands again to replace derived PARTIAL artifacts with the complete aggregation. The raw inputs and frozen policies remain unchanged. A full plot run rejects a PARTIAL or INCOMPLETE summary. Inspect the three generated PNGs before including them in the compact handoff.

## Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s4_summary.py --self-test
"C:\Users\amiri\anaconda3\python.exe" s4_capture_selection.py --self-test
"C:\Users\amiri\anaconda3\python.exe" s4_summary.py
"C:\Users\amiri\anaconda3\python.exe" s4_plots.py
```

No new dependencies or installs are required. Self-tests exercise pooled edit denominators, separate empty-reference rates, energy-based RMS pooling and unknown/censored spatial denominators. The self-tests do not create plots, load models or touch hardware.

## Shared accepted-capture resolver

`s4_capture_selection.py` is the shared offline reader used by audio/spatial consumers, H2, summaries, figures and the handoff. `accepted_cases(partial=False)` returns an ordered dictionary keyed by `S4_01` through `S4_24`. Each value has `case_id`, `batch`, `folder` (a `Path`), parsed `case_result`, and `case_result_binding`. `case_folder(case_id, partial=False)` returns the accepted folder. Validation requires exactly 24 unique IDs, receipt hash/path/batch identity, canonical scene hash, frozen hardware recipe, and PASS audio/telemetry/transport gates. This selects the successful replacement for a telemetry-only failed attempt without rewriting its original evidence.

With no command-line arguments, the resolver validates the authoritative manifest and prints accepted paths. `--partial` permits inspection of successful original `hardware/final` cases only when the authoritative manifest is absent. An existing invalid manifest is never bypassed. `--self-test` checks exact counts, duplicate IDs, bound replacement selection, failed telemetry, changed receipt bytes and path mismatch. H2 has no partial-selection mode and cannot start until the authoritative selection exists and all hardware is released.

## Summary schema and interpretation

`counts` distinguishes 24 canonical renders/final captures from 48 ordinary H2 jobs and two nominal repetition attempts. Full aggregation requires all 24 final scenes to have audio/spatial analysis and both H2 outputs, plus both repetition analyses. `omissions` lists exact missing or incompatible artifacts. `status=COMPLETE_EVIDENCE_COUNTS` establishes aggregation completeness, not the complete S4 phase disposition or S5/S6 readiness.

`text_by_output.O0` and `.O1` contain `pooled_wer`, `pooled_cer`, `word_counts`, `character_counts`, `empty_reference_insertions`, `empty_reference_words_per_minute`, and limited scene IDs. WER/CER sum S/D/I and reference denominators; they are not averages of per-scene scores. `paired_weighted_text` restricts to the same valid nonoverlap scene IDs in both outputs. Silence and noise controls have undefined WER/CER. Ordinary concatenated-transcript WER is not used for overlap, including scene 20.

`audio_by_output.<output>.all_final_captures`, `.speech_captures` and `.nonspeech_controls` report rail samples, sample denominators, maximum peaks/rail runs and energy-weighted RMS. `fixed_host_gain` and `max_adapted_peak_fs` remain separate from raw levels. Noise controls and repetition captures are never silently folded into the speech-only or canonical-bank totals.

`H2_by_output.<output>` contains successful embedding calls, reconstructed gate counts, emitted final labels, underlying dominant-label return consistency and fragmentation. Gate reasons overlap; successful decisions count completed embedding calls, while attempted rejected calls remain unknown. The unchanged baseline has no final reconciliation stage, so reconciled labels, full DER and enrolled-name accuracy remain unavailable. Offline process RTF and file-event wall availability are not live caption latency.

`summary_export_evidence` separately counts `native_runtime_summary_count` and `derived_completion_evidence_summary_count`. Its `derived_summaries` list names every validated completed-job export recovery, its preserved empty original and bound derived summary. Each referenced `H2_SUMMARY_RECOVERY*.json` and derived session summary is included in `consumed_json_bindings`; there is no hardcoded native/derived count. Metrics must preserve the recovered primary telemetry and original scientific policy. These cases recover completed inference evidence without rerunning a model or repairing the unchanged baseline's export race.

`spatial_final_bank.streams.<stream>` contains support-weighted coverage/sector occupancy, unavailable time/fraction, first-hit and sustained-acquisition censored counts, observed-only acquisition/off-delay medians and nonspeech positive indications. Streams include selected processed, selected auto, raw auto, two focused beams and scanning. The denominators count dependent scored turns and preserve overlap limitations. Censored/never-acquired cases remain in explicit counts; an observed-only median must never be read as if every turn acquired. Manual ±5° describes source-label uncertainty, not acceptable device error. Host receipt freshness does not prove internal DSP freshness, and a beam ID is not a person ID.

`nominal_repeats_excluded_from_bank_totals` holds the two additional scene-01 attempts with audio and spatial results. `consumed_json_bindings` records compact evidence provenance, including the source/split manifest and H2 execution contract. These scripts do not declare an S5 output winner, claim an S6 fusion benefit, or produce population confidence intervals from this dependent development bank.
