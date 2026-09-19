# S6B opt-in native runtime and shared causal scheduler

These modules implement bounded research execution with the existing fixed
Sherpa Giga, Pyannote and ReDimNet2-B2 assets. Ordinary GUI/default file runs and
v1 profiles retain their prior path. S6A V2 is separately preserved in the S6B
staging snapshot; returning to that snapshot restores exact historical source.
No hardware, downloading or training is involved in the commands below.

## Inputs and outputs

- Input audio is a prepared mono 16 kHz WAV, with an explicit mono/O0/O1 tap
  declaration. `input.gain` is applied exactly once after the native PCM16
  journal; `already_gained=true` requires unity gain.
- A JSON `edge-research-profile.v2` selects the v2 tracker, sealed-watermark
  scheduler and component admission hooks. Unknown fields and changed inactive
  controls reject. `edge-research-profile.v1` remains supported unchanged.
- Optional telemetry is sanitized JSONL accepted by `JsonSpatialProvider`:
  angle_deg, available_at_sec, energy, reliability, valid, sequence and optional
  source_start_sec/source_end_sec. Availability is on the modeled source clock;
  historical wall timestamps and reference speaker identities are not inputs.
- Sessions contain the original `audio_spool.pcm16`, append-only `events.jsonl`,
  immutable first-final `labelled_transcript.jsonl` and `transcript.md`, plus
  `latest_labelled_transcript.jsonl` and a summary. Forward correction events
  retain first labels and times. GUI transcript rewriting is not implemented.

## Minimal v2 profile

Save this as `C:\Users\amiri\Downloads\s6b_voice.json`:

```json
{
  "schema_version": "edge-research-profile.v2",
  "profile_id": "S6B_voice_dispatch_control",
  "embedding": {"rms_policy": "dispatch", "purity_policy": "gate_only"},
  "tracker": {"mode": "voice", "cues_enabled": false},
  "xvf": {"mode": "none"},
  "runtime": {"asr_threads": 1, "speaker_threads": 1, "punctuation_threads": 1}
}
```

These values are a runnable example, not a recommendation selected by results.
V2 has a different tracker/scheduler from exact historical B0.

## PowerShell commands

Use a fresh terminal. Replace `prepared_mono.wav` with a real prepared input.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:NUMEXPR_NUM_THREADS = '1'
$env:EDGE_SPEECH_DATA_ROOT = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s6b\manual_run'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m edge_speech_pipeline research-profile 'C:\Users\amiri\Downloads\s6b_voice.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m edge_speech_pipeline file 'C:\Users\amiri\Downloads\prepared_mono.wav' --research-profile 'C:\Users\amiri\Downloads\s6b_voice.json'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -m edge_speech_pipeline.research_s6b_checks --receipt 'C:\Users\amiri\Downloads\s6b_component_fixture_receipt.json'
```

The profile command validates and prints effective settings without loading any
model. The file command is paced unless `--accelerated` is explicitly added.
Cue-enabled modes also require `--research-telemetry 'C:\path\sanitized.jsonl'`.
No sound is played. Fixed model thread counts do not cap every process OS thread.

## Anaconda Prompt / Windows Command Prompt

The explicit interpreter makes `conda activate` unnecessary; use these commands
in either prompt. Replace the same example WAV path.

```bat
set PYTHONDONTWRITEBYTECODE=1
set PYTHONPATH=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app
set OMP_NUM_THREADS=1
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
set NUMEXPR_NUM_THREADS=1
set EDGE_SPEECH_DATA_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s6b\manual_run
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline research-profile "C:\Users\amiri\Downloads\s6b_voice.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline file "C:\Users\amiri\Downloads\prepared_mono.wav" --research-profile "C:\Users\amiri\Downloads\s6b_voice.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline.research_s6b_checks --receipt "C:\Users\amiri\Downloads\s6b_component_fixture_receipt.json"
```

## Actual component controls

All additional fields are defined and typed in `research_profiles.py`.

| Section/control | Native effect |
|---|---|
| segmentation.post_policy/hop_sec | Existing fixed 10 s graph, hard tail fraction or posterior hysteresis, exact dispatch-multiple stride |
| embedding.rms_policy | Dispatch block RMS or RMS of the complete proposed embedding window |
| embedding.purity_policy | gate_only, clean fraction, or clean fraction plus minimum contiguous clean support |
| minimum_clean_fraction / minimum_contiguous_clean_sec | Admission checks from arrived full-context Pyannote frame supports; newer uncovered audio is unclean |
| evidence_policy=early_short_long | First admitted .5 s (or configured supported early span) per detected speech run, then the configured longer window |
| cadence_policy | fixed uses hop_sec; sparse/frequent use their named interval; event_driven chooses bounded frequent or sparse opportunities |
| evidence_debt_enabled | N05 voice-only maximum observation opportunity gap; never overrides unsafe purity, RMS, overlap or minimum-length gates |
| cadence_cues_enabled | Optional fresh direction-change trigger for event cadence; absent cues reduce exactly to voice scheduling |
| xvf.mode | none / tracking_only / endpoint_only / both; tracker.cues_enabled must agree exactly |
| endpoint_min_interval_sec / endpoint_max_per_minute / endpoint_circuit_breaker_sec | N04 advisory-reset rate limit and burst breaker; native Sherpa endpoints remain independent |
| asr.decoding_method / max_active_paths | Installed greedy_search or modified_beam_search; changing inactive greedy path count rejects |
| asr.journal_read_ms | Actual 20/50/100/200 ms delivery, exact partial EOF tail and separate synthetic drain |
| scheduler.evidence_expiry_sec | Common queried modeled availability minus evidence source-end expiry, default .75 s |
| scheduler.revision_horizon_sec / max_revisions_per_utterance | Forward reconciliation bounded from first-final (or first-display before final), not extended by each correction; ongoing ASR partial display changes are separately counted |

Early-short and long evidence do not manufacture short speech that a conservative
segmentation gate rejected. All ASR words remain independently delivered, with
unknown or provisional speaker labels when acoustic evidence is insufficient.
Local Pyannote slots are never global identities. Overlap is shown as uncertain.
`one_person` and `all_unknown` tracker modes are explicitly named degenerate
diagnostic controls; they label all ASR events independently of embedding supply.
For a final-only ASR event, an already supported label on that same stable
utterance is retained through endpoint silence when fresh evidence is absent,
with `attribution_reason="finalization retains prior utterance label"`. A new
nonempty partial still applies expiry and may replace the current label with
unknown; finalization cannot revive an older label after that replacement.

## Shared replay API

```python
from edge_speech_pipeline.research_scheduler import CausalScheduler
from edge_speech_pipeline.research_tracking_v2 import S6BTracker
scheduler = CausalScheduler(S6BTracker(profile.tracker),
    spatial_provider=provider, cues_enabled=profile.tracker.cues_enabled,
    revision_horizon_sec=profile.scheduler.revision_horizon_sec,
    evidence_expiry_sec=profile.scheduler.evidence_expiry_sec)
scheduler.push({"kind": "embedding", "event_id": "embedding:00000001",
    "vector": vector_192, "source_start_sec": 0.0, "source_end_sec": 0.5,
    "available_at_sec": 0.54, "speech": True, "overlap": False}, lane="speaker")
scheduler.push({"kind": "asr", "event_id": "asr:00000001", "utterance_id": "utterance:000000",
    "text": "hello", "final": True, "source_start_sec": 0.0, "source_end_sec": 0.5,
    "available_at_sec": 0.56}, lane="asr")
events = scheduler.advance({"speaker": 0.75, "asr": 0.60})
events += scheduler.finish()
transcripts = scheduler.snapshot()["utterances"]
```

Every event has a unique stable ID and a finite source/context/availability
span. `advance` is a promise that no later event in that lane arrives below its
watermark. The scheduler processes only events strictly below both watermarks;
ties order segmentation, embedding, then ASR, and stable event ID. `finish`
seals both lanes. Do not sort future observations into earlier availability.
The public input boundary rejects unknown/reference fields. Common keys are
kind/event_id/source_start_sec/source_end_sec/available_at_sec. Embedding events
add only vector (finite192D), speech/overlap and optional receptive_start/end_sec;
segmentation adds only speech/overlap; ASR adds utterance_id/text/final and optional
display_text/punctuation/asr_decode_ms. Punctuation metadata has its own bounded
allowed-field set. Context and measured cost must be available before admission.
Features must already include their complete neural context and measured cost.
Native records `research_asr_observation` before submission, allowing replay
without reconstructing inputs from labels. Returned records are flat dictionaries
with event_type/event_id/source_start_sec/source_end_sec/available_at_sec and
type-specific fields. Native files wrap these in the normal PipelineEvent envelope.
Cadence and endpoint cues use a source-end snapshot, conservatively excluding
telemetry that arrives while computation runs. Identity tracking queries at the
declared embedding availability. These are separately logged causal choices.

Policy compute is separately measured and is not added differently to paired
cached upstream clocks. Native measured elapsed and full dispatch elapsed include
policy and export overhead; modeled availability is explicitly a warm-resident
source-clock model. Startup/loading and resident admission are separately logged.
Replay is deterministic for identical admitted events/costs. This is not a claim
that two actual hardware executions have identical measured compute times.
Each record retains `input_available_at_sec` and the conservative
`release_watermark_lower_bound_sec` (null after all lanes close). Native
`research_scheduler_watermark` events record lane sealing and measured elapsed.
The logical input availability is not a measured display time: a native lane
can wait for the other lane's next dispatch before releasing an event. Paired
replay can use the same saved watermark stream; paced measurements alone support
physical display-latency claims. Segmentation overlap state has the same explicit
freshness expiry as speaker evidence. Ongoing partial display changes are counted
in `ongoing_display_label_changes`; `revision_count` and its configurable cap
refer only to bounded forward reconciliation, not ordinary evolving ASR text.

Default finite limits: 20,000 pending events, 1,000,000 total event identities,
4,096 utterances, 4 forward reconciliations per utterance, plus bounded 4,096
speaker/segmentation histories. Exceeding a limit fails explicitly. These are
bounded study sessions, not an unqualified unlimited-production-memory claim.

## Resident neural sessions

```python
from edge_speech_pipeline.models import ResidentModelBundle
from edge_speech_pipeline.runtime import PipelineEngine
effective = profile.apply(config)
bundle = ResidentModelBundle(effective)  # validates immutable asset bytes once
engine = PipelineEngine(config, research_profile=profile, spatial_provider=provider,
                        model_bundle=bundle)
engine.start_file(input_path, realtime=False)
# Wait for terminal state, then join artifact finalization before another scene.
engine.wait_for_completion(timeout=300)
# A new engine with the same bundle creates a fresh Sherpa stream and all new
# tracker, scheduler, endpoint and transcript state. Only weights are shared.
```

One active engine per bundle is enforced. Changed effective model/config values
require a new bundle. Session/gallery output paths may differ. The caller must
verify execution files and model bytes once at worker admission and keep them
immutable for the bundle lifetime; no per-scene weight rehash is claimed.

## Validation boundary

`research_s6b_checks` exercises the actual scheduler/tracker, causal visibility,
arrival-order invariance, immutable first-label revisions, expiry, limits,
full-window RMS, contiguous purity, short/long/debt admission, endpoint rate
limits and the complete file runtime's 50 ms + 107-sample tail with gain once.
Its full-engine test substitutes deterministic model objects, and its endpoint
limiter fixture substitutes the proposal source while separately checking real
stale-input rejection. The receipt explicitly does not claim neural prefix proof.
Actual-neural probes and runtime measurements must be reported separately by the
S6B coordinator after these source files are frozen.
