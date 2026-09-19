# S4 offline H2 and output analysis

This module analyzes completed captures and sessions. It never opens the XVF, runs an audio endpoint, executes a model, or changes H2. The existing `app.scoring.wer.compute_wer` supplies edit counts. English scoring lowercases, removes ASCII punctuation, and collapses whitespace on both sides; CER additionally excludes spaces. The normalization is recorded with every result. Empty references have undefined WER/CER and explicit insertion counts/words per minute. Overlap without a valid timed scorer is LIMITED.

Inputs are an explicit 16 kHz mono O0 or O1 WAV, an H2 session directory containing `events.jsonl` and `session_summary.json`, and a reference JSON. Optional turns use `participant_id`, `start_s`, and `end_s` in the dry-source file schedule. The caller must supply an evidenced `alignment_offset_s` into decoded output time; the helper never estimates it from speaker labels. File support is not a phonetic annotation. The native converter audit also reads the completed case's `case_result.json`, `native_packed.wav`, `O0.wav`, and `O1.wav`.

Outputs are strict JSON with edit S/D/I and denominators, original final text and speaker labels, offline availability, embedding gate evidence, and clearly limited source-window continuity. Raw audio and events are unchanged. The edge baseline has no final label reconciliation stage: `reconciled_labels` is null and the status says unavailable. Successful `speaker_decision` events count completed embedding calls; rejection counts are unknown because the baseline does not log attempted rejected calls. Gate counts can have overlapping rejection reasons and are not independent speech duration.

## PowerShell

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\anaconda3\python.exe'
Set-Location -LiteralPath "$sim\scripts"
& $py -m unittest test_s4_h2_analysis -v
& $py "$sim\staging\s4_h2_audit\run_audit.py"
```

The second command reproduces the bounded historical audit and writes `S3_OFFLINE_H2_HEADROOM_AUDIT.json` and the two `O*_s3_analysis.json` files in `simulation\staging\s4_h2_audit`. It reads three selected S3 captures and the two existing H2 sessions. It does not rerun S3 playback or H2 inference.

For a new completed session, replace the three example input paths and output path with the actual S4 case paths:

```powershell
& $py "$sim\scripts\s4_h2_analysis.py" session --session 'C:\absolute\session_directory' --reference-json 'C:\absolute\reference.json' --audio 'C:\absolute\O0_fixed_gain.wav' --output 'C:\absolute\metrics.json'
& $py "$sim\scripts\s4_h2_analysis.py" converter --case 'C:\absolute\completed_hardware_case' --output 'C:\absolute\converter_audit.json'
```

Reference JSON example:

```json
{
  "reference": "The complete verified transcript.",
  "duration_s": 30,
  "overlap": false,
  "transcript_valid": true,
  "turns": [{"participant_id": "development_A", "start_s": 3, "end_s": 8}],
  "alignment_offset_s": 0.25
}
```

`0.25` is only a schema example, not a default or device-latency claim. Use the actual capture offset, documented RIR convention and measured descriptive output delay consistently.

## Anaconda Prompt or Command Prompt

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" -m unittest test_s4_h2_analysis -v
"C:\Users\amiri\anaconda3\python.exe" "..\staging\s4_h2_audit\run_audit.py"
"C:\Users\amiri\anaconda3\python.exe" s4_h2_analysis.py session --session "C:\absolute\session_directory" --reference-json "C:\absolute\reference.json" --audio "C:\absolute\O0_fixed_gain.wav" --output "C:\absolute\metrics.json"
```

Dependencies are the existing Anaconda NumPy and SoundFile packages and the local unchanged H2 scorer. No install is needed. Analysis is deterministic for fixed inputs; rerunning replaces only the explicitly selected metrics output atomically. Preserve versioned S4 reports when inputs or policy change.

## Python integration

```python
from s4_h2_analysis import analyze_scene, analyze_session, rail_metrics, audit_converter

metrics = analyze_scene(session_directory, scene, audio_path=h2_input_mono_path,
                        alignment_offset_s=evidenced_offset)
```

`scene['segments']` uses `speaker_key`, whole `transcript`, `source_start_sample`, and `source_stop_sample`. Sample rate defaults to 16000, or use `sample_rate_hz`. Any overlapping speech-file intervals conservatively make transcript WER/CER LIMITED. Noise segments without transcripts are omitted from the speech reference. An explicit `scene['overlap']=true` also disables ordinary WER. `analyze_session` accepts the reference/turn arguments directly. `rail_metrics` takes signed 24-bit counts; when using SoundFile `dtype='int32'` for PCM24, shift right by 8 first. Do not give it normalized floats.

The focused tests cover edit denominators, empty references, overlap limitations, normalization, rail runs, exact H2 gate behavior, multichannel rejection, returning speakers, missing evidence and overlap exclusion. They do not exercise hardware or models.

## Execute the final S4 H2 pairs

`s4_h2_run.py` runs the unchanged H2 CLI sequentially in the established `.edge-speech-env`. It consumes the frozen S4 bank and authoritative `reports\S4\20260909T002140Z\ACCEPTED_FINAL_CAPTURES.json`, creates one explicit mono FLOAT32 adapter file per output, then analyzes each completed session. The shared `s4_capture_selection.py` resolves accepted folders across `hardware\final` and `hardware\final_completion`, validates the receipt hashes and successful final recipe, and preserves excluded attempts. It applies exactly the frozen `OUTPUT_LEVEL_POLICY.json` scalar to O0 on the host; O1 gain stays 1. Raw captured audio remains unchanged. No source text, seat label, reference timing or spatial input is sent to H2.

Run this only after the coordinator has restored and released the XVF. The runner verifies the restoration receipt and close flags, frozen policies, exact scene/capture/input hashes, and S0 source/config bindings. It never calls an audio endpoint or USB API. A software lock prevents duplicate H2 runners. Each ordinary scene/output gets a fresh, initially empty `empty_data` directory; conversation continuity is retained inside that one file. Ordinary output jobs are capped at 48, run sequentially with the original H2 CPU configuration. The original CLI validates model hashes internally; the outer runner does not repeatedly hash weights.

A preserved `restoration.json` FAIL can be resolved only by an accompanying `restoration_recovery.json` PASS that hashes that exact original failure, embeds the same failure evidence, reports every handle/lease closed and packed input disabled, and exactly matches all original settings, identity, USB width and ancillary readbacks. The runner rechecks those values against `initial_state.json`. It never overwrites the failed receipt, accepts a tolerance in place of exact getter equality, or treats an unbound recovery claim as success. This handles the separately documented, bounded float32 setter roundtrip recovery while retaining its original failure history.

PowerShell, after final hardware release:

```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$py = 'C:\Users\amiri\anaconda3\python.exe'
$alignment = "$sim\reports\S4\20260909T002140Z\output_alignment.json"
& $py "$sim\scripts\s4_h2_run.py" --cases S4_01 --alignment-json $alignment --validate-only
& $py "$sim\scripts\s4_h2_run.py" --cases S4_01 --alignment-json $alignment
& $py "$sim\scripts\s4_h2_run.py" --alignment-json $alignment
```

The middle command runs the first two ordinary output jobs, O0 and O1 for scene 01. The final command reuses those completed compatible jobs and runs the remaining pairs; it does not add duplicate model jobs. Run the final command again to resume after a safe interruption, retaining the same `output_alignment.json` mapping used for the completed S4 results. Omitting or changing that mapping changes analysis identity and can replace available reference-turn metrics with LIMITED results, even though compatible model jobs are not repeated. `--validate-only` checks prerequisites without loading models or running inference. `--hardware` is only an optional consistency check and cannot override the authoritative accepted selection. The selection hash is included in the frozen H2 execution contract; no model job uses an excluded failed attempt.

Anaconda Prompt or Command Prompt:

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\anaconda3\python.exe" s4_h2_run.py --cases S4_01 --alignment-json "..\reports\S4\20260909T002140Z\output_alignment.json" --validate-only
"C:\Users\amiri\anaconda3\python.exe" s4_h2_run.py --cases S4_01 --alignment-json "..\reports\S4\20260909T002140Z\output_alignment.json"
"C:\Users\amiri\anaconda3\python.exe" s4_h2_run.py --alignment-json "..\reports\S4\20260909T002140Z\output_alignment.json"
```

Results go to `reports\S4\20260909T002140Z\h2\S4_XX\O0` and `O1`: `run_receipt.json`, `metrics.json`, the fixed-gain adapter WAV, stdout/stderr, and isolated session files. `h2\execution_contract.json` freezes model/config/code/input-policy identity; `h2\run_summary.json` counts all ordinary jobs. Atomic progress and a 15-second heartbeat use the shared S4 status files. A model timeout or failure stops execution with a preserved receipt instead of automatically repeating failed jobs. An interrupted job whose session already completed can be adopted for metrics without rerunning the model; an incomplete model session needs diagnosis before more execution. Only the child created by this runner is stopped on interruption.

Source-to-output turn continuity requires an independently evidenced processed-output delay. The completed S4 run uses `reports\S4\20260909T002140Z\output_alignment.json`; retain that exact file on resume. Its structure is illustrated below:

```json
{
  "S4_01": {
    "O0": {"processed_output_minus_recaptured_input_s": 0.0547, "evidence": "Actual local delay-metric receipt and method", "uncertainty_s": 0.0002},
    "O1": {"processed_output_minus_recaptured_input_s": 0.0547, "evidence": "Actual local delay-metric receipt and method", "uncertainty_s": 0.0002}
  }
}
```

These values illustrate the schema; use actual measured case values. The runner adds the exact recaptured-input offset plus the retained 0.05-second RIR convention. It never fits a delay to expected speakers. Missing entries leave reference-turn scoring LIMITED while retaining WER/CER, emitted labels, gate evidence and qualified offline text availability. Adding an evidenced alignment mapping on resume recomputes metrics for compatible completed sessions without rerunning models. Incompatible model input/gain/config/code identity is rejected. The tests now also cover fixed-gain headroom, raw preservation, completed-session adoption, failed-session preservation, and missing alignment; all tests remain offline.
