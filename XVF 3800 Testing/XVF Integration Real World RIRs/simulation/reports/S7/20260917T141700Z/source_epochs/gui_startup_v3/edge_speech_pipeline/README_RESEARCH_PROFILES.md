# Opt-in S6 research profiles

For the separately versioned S6B scheduler, resident sessions, component admission
and forward transcript revisions, see [README_RESEARCH_S6B.md](README_RESEARCH_S6B.md).
This document describes the preserved v1 interface.

This interface runs supported candidate settings through the actual edge application. Ordinary GUI and CLI launches keep the historical defaults and model weights. Historical S5 reports remain immutable. Exact B0 is the separately preserved application copy and baseline receipts; explicit research runs add instrumentation.

## Inputs and outputs

Supply one prepared mono 16 kHz WAV/FLAC, a JSON profile, and optionally sanitized source-clock XVF JSONL. The profile declares the supplied tap; it does not switch an audio device or channel. No hardware playback occurs. No reference text, true identity, scenario label or seat enters the predictor.

Use unity when input already contains historical O0 +3 dB. Setting input.already_gained to true rejects another non-unity gain. Optional gain acts once on both model branches after native PCM16 journaling; this differs from pre-quantization gain and needs its own cache identity.

Outputs retain the normal PCM16 journal, events, transcript and durable summary. Explicit profiles additionally record complete effective settings, profile hash, model spans, measured elapsed compute/wall time, modeled serial-lane availability and real tracker lineage. research_embedding contains local vectors for exact downstream replay; keep vector-bearing logs out of compact handoffs.

## PowerShell

~~~powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline file "C:\audio\prepared_O0.wav" --accelerated --research-profile "C:\audio\candidate.json" --research-telemetry "C:\audio\sanitized_source_clock.jsonl"
~~~

Use the existing environment; no install or download is needed. For cue-disabled runs set xvf.mode to none and omit --research-telemetry. Omit --accelerated for paced file execution. For rollback, omit both research arguments; GUI defaults were never switched.

## Anaconda Prompt or ordinary Command Prompt

~~~bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline file "C:\audio\prepared_O0.wav" --accelerated --research-profile "C:\audio\candidate.json" --research-telemetry "C:\audio\sanitized_source_clock.jsonl"
~~~

## Example candidate.json

~~~json
{
  "schema_version": "edge-research-profile.v1",
  "profile_id": "P1X1_example",
  "input": {"tap": "O0", "gain": 1.0, "already_gained": true},
  "asr": {
    "endpoint_rule1_silence_sec": 1.6,
    "endpoint_rule2_silence_sec": 0.8,
    "endpoint_rule3_utterance_sec": 20.0,
    "journal_read_ms": 50
  },
  "segmentation": {"hop_sec": 0.5, "post_policy": "posterior_hysteresis"},
  "embedding": {"window_sec": 1.0, "hop_sec": 0.5, "minimum_rms": 0.002},
  "tracker": {"mode": "reliability_adaptive"},
  "xvf": {"mode": "soft_energy_advisory"}
}
~~~

Missing sections take typed historical defaults. Unknown fields, wrong types, non-finite values, fixed-shape violations, cadence rounding and changed conditionally inactive knobs fail before models load. ResearchProfile().apply() equals PipelineConfig(). A baseline JSON can simply be {"profile_id":"B0_explicit"}.

Programmatic API: ResearchProfile.from_dict/load/apply/effective/to_dict/digest and PipelineEngine(config, research_profile=profile, spatial_provider=provider). File CLI uses exactly this implementation.

## Supported controls and limits

- Pyannote requires exactly 160000 samples and returns 589 seven-class powerset log probabilities. Default hard_argmax_fraction preserves argmax then >=0.20 tail-fraction gates. Historical onset/offset 0.46/0.45 were inactive. Opt-in posterior_hysteresis sums valid powerset probabilities and uses onset/offset on mean tail speech probability. Speaker slots are local to each invocation; this is not full Pyannote clustering.
- Segmentation hops 0.25–1.5 seconds must be an integer multiple of the embedding dispatch hop. Early calls left-pad the fixed graph. Frontend frame step is 0.016875 seconds and frame receptive duration 0.0619375 seconds; bidirectional computation uses the full supplied 10-second context. No shorter graph or future source sample is invented.
- ReDim windows 0.5–3 seconds use contiguous waveform inputs; hops 0.25–1 second. Existing graph frontend/pooling remain unchanged. No frame-mask input exists. RMS eligibility still examines the current dispatch block; this preserved limitation is logged. Overlapping windows are not independent evidence seconds.
- Installed Sherpa supports greedy and modified beam search. Active paths only affect modified beam. Endpoint rules, blank penalty and host dispatch are explicit. Host dispatch 20/50/100/200 ms is distinct from encoder feature shape [N,39,80] and decode_chunk_len=32.
- XVF none disables metadata; tracking_only enables only the chosen tracker. soft_energy lowers posterior speech threshold by bounded delta only for qualified fresh positive energy; positive energy is not calibrated VAD. advisory permits reset only after sustained fresh direction change plus actual low-RMS trailing audio. It never resets merely due to tentative identity. soft_energy_advisory combines these.
- Anonymous research trackers have no enrollment names. Changing naming gates with an anonymous tracker is rejected. Real bounded forward revisions are documented in README_RESEARCH_TRACKING.md. Baseline elapsed-span naming evidence remains unchanged for B0.
- Final punctuation remains final only. Optional partial-display throttling preserves final raw words. Thread counts 1/2/4 use existing CPU providers; JSON cannot replace weights.
- The current application writes growing session files. Production retention and eMMC write budgets remain design work; this is not a memory/storage qualification.

## Telemetry and clocks

Allowed JSONL fields: angle_deg, available_at_sec, energy, reliability, valid, sequence, source_start_sec, source_end_sec. Angle (nullable) and availability are required. Native directions are folded 0..180 degrees and use linear differences. Source end cannot exceed availability; preserve observation time when known so recent delivery cannot refresh old data.

~~~json
{"angle_deg":90.0,"available_at_sec":1.05,"source_start_sec":1.0,"source_end_sec":1.02,"energy":0.1,"reliability":0.8,"valid":true,"sequence":12}
~~~

The provider releases only data delivered by the current source cursor. Source and availability must share a declared mapping. Observation age is unknown when source span is omitted; do not claim it was measured.

Measured elapsed compute/event timestamps stay separate from modeled availability. Each serial lane charges ready=max(previous_ready,input_end)+measured_compute_seconds. Segmentation precedes embedding; ASR final padding/drain and punctuation are charged. This queue model is not calibrated live latency and never joins accelerated wall time to historical QPC. Revisions retain their later availability.

The modeled clock starts with source capture after loading; it is a warm-resident lane model, not button-to-first-decision latency. Explicit sessions separately emit research_models_ready with actual loading and session elapsed times. Candidate overlap display uses its own causal segmentation history, including overlap periods that deliberately produce no embedding. Speaker and overlap availability are checked independently. The initial cue-enabled flag and final summary match the selected profile. Tracking-only cues with a baseline/voice-time tracker are rejected as ineffective; disable reconciliation with its boolean rather than a zero revision horizon.

## Tests

~~~powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline.research_profile_checks --output "C:\audio\profile_checks.json" --models
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m pytest ".\tests\edge_speech_pipeline" -q
~~~

For Anaconda Prompt/CMD use cd /d instead of Set-Location and remove PowerShell's & before Python. Omit --models for pure policy checks. Checks cover validation/default parity, powerset semantics, operative hysteresis, stale/redelivered/reordered advisory cues, graph constraints and actual ReDim lengths.

The optional real-model smoke reads the first 12.037 seconds of an existing gained native PCM16 file and supplies a clearly synthetic constant cue. Its new output directory must not exist. Failures remain inspectable. This engineering test is not an accuracy measurement.

~~~powershell
Set-Location "C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app"
& "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline.research_profile_smoke --pcm16 "C:\audio\audio_spool.pcm16" --output-dir "C:\audio\smoke_new"
~~~

Apply the same CMD/Anaconda conversion. Outputs are SMOKE_RECEIPT.json, engineering input/cue, and a normal session. Do not package its audio or vector-bearing logs. A successful smoke does not establish candidate accuracy, tap superiority or CM5 qualification.
