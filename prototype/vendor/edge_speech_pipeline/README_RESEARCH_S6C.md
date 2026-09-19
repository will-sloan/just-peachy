# S6C integrated file, evidence and enrollment research

This README covers `research_profiles_v3.py`, `research_audio_v3.py`,
`research_evidence_v3.py`, `research_identity_v3.py`, `research_scheduler_v3.py`
and `checks_research_s6c.py`, plus their opt-in runtime/CLI dispatch. The separate
tracker has `README_RESEARCH_TRACKING_V3.md`. These are S6C research components;
ordinary GUI, default file/live execution and v1/v2 profiles keep their existing
paths. No model checkpoint, hardware setting or production default is changed.

## Purpose, inputs and outputs

V3 uses the actual fixed Sherpa ASR, Pyannote and ReDimNet models, one persistent
ReDimNet instance and separate short/mature evidence opportunities. An optional
explicit gallery is loaded through the existing ProfileStore and scored inside
the native/shared policy, after anonymous association. Cached replay imports the
same scheduler and resolver. Gallery names do not change anonymous association.

Inputs are two admitted, equal-length mono16kHz WAVs from a common capture sample
origin, a strict v3 profile and optionally sanitized causal telemetry and a
research gallery manifest. Positional WAV supplies ASR; `--identity-wav` supplies
Pyannote/ReDimNet. Same-tap profiles may omit the second path. Prepared O0 already
contains its prescribed +3 dB; O1 remains unity. V3 requires runtime unity gain
and `already_gained=true`; it does not resample, downmix, align to reference turns
or play audio. File headers and actual complete delivery must agree. Waveform
hash/common-origin admission remains the campaign's responsibility.

Each session writes `audio_spool.pcm16` (ASR), `identity_audio_spool.pcm16`, normal
`events.jsonl`, immutable-first `labelled_transcript.jsonl`, `transcript.md`,
`latest_labelled_transcript.jsonl` and `session_summary.json`. A shared journal
commit barrier exposes a source boundary only after both files have written that
block. Both journals remain complete even when the speaker analysis leaves a
reported sub-dispatch residual tail; ASR accepts its exact partial tail and then
separately accounts for synthetic drain padding.
V3 has a declared `runtime.lane_drain_timeout_sec` (default 600 s) after the
producer closes; historical paths retain their 30 s limit. Failed v3 lanes abort
between model calls. A lane still alive after bounded failure cleanup prevents
resident-bundle release/reuse and is explicitly reported; the owning coordinator
must close that failed worker process rather than reuse its models. This cannot
preempt a native model call already in progress.
After lane/lease checks and writer closure, `session_finalization_v3.json` records
the actual final state, surviving lanes, retained/released resident lease and
sample counts, including failed drain attempts. These post-finalization facts
are not inferred from the earlier summary. `wait_for_completion()` also reports
failure to durably write this closure artifact.
The closure records each writer's observed close outcome. A close exception or
unavailable `closed` state cannot produce a successful all-handles-closed claim.

Actual inference logs include `research_embedding_observation` (exact shared API
input), `research_embedding`, admission diagnostics, full segmentation frame
views, ASR observations/dispatch/tail/drain, scheduler watermarks, speaker/name
decisions and forward transcript corrections. First anonymous/known/final names
and latest names are separate from raw text. A correct-name flag is deliberately
absent: only the evaluator can establish correctness. GUI automatic rewriting
and default promotion are not implemented by these commands.

## Example profile

Save `C:\Users\amiri\Downloads\s6c_voice.json`:

```json
{
  "schema_version": "edge-research-profile.v3",
  "profile_id": "S6C_example_empty",
  "input": {"asr_tap":"O0", "identity_tap":"O0"},
  "tracker": {"mode":"old_voice_gate", "cues_enabled":false, "lifecycle_policy":"none"},
  "identity": {"mode":"none"},
  "xvf": {"mode":"none"}
}
```

This is an executable example, not a result-selected recommendation. Omitted
v3 component defaults are posterior-hysteresis segmentation every .5 s using its
fixed 10 s graph, .5 s short evidence every .25 s and 1.5 s mature evidence every
.5 s, full-window RMS, estimated clean fraction .8, original greedy ASR with
100 ms delivery and 2.4/1.2/20 s endpoint rules, one configured model thread.
CPU libraries still create other OS threads. For split input declare different
`input.asr_tap`/`input.identity_tap` and supply the second actual WAV.

## PowerShell

Use the existing environment; no install or activation is required. Replace WAV
paths with admitted prepared files. The following only reads local file audio.

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONPATH = 'C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app'
$env:OMP_NUM_THREADS = '1'
$env:OPENBLAS_NUM_THREADS = '1'
$env:MKL_NUM_THREADS = '1'
$env:NUMEXPR_NUM_THREADS = '1'
$env:EDGE_SPEECH_DATA_ROOT = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s6c\manual_run'
$s6cPython = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $s6cPython -m edge_speech_pipeline research-profile 'C:\Users\amiri\Downloads\s6c_voice.json'
& $s6cPython -m edge_speech_pipeline file 'G:\Just_Peachy_S6B\20260909T230840Z\inputs\S45_01_06\O0.wav' --research-profile 'C:\Users\amiri\Downloads\s6c_voice.json'
& $s6cPython -m edge_speech_pipeline.checks_research_s6c --receipt 'C:\Users\amiri\Downloads\s6c_component_checks.json'
```

For a split/naming profile, the file invocation becomes:

```powershell
& $s6cPython -m edge_speech_pipeline file 'C:\admitted\O0.wav' --identity-wav 'C:\admitted\O1.wav' --research-profile 'C:\admitted\split_naming.json' --research-gallery 'C:\admitted\gallery.json'
```

Add `--research-telemetry 'C:\admitted\sanitized.jsonl'` only for a profile with
an enabled cue route. Add `--accelerated` for an explicitly accelerated study;
default CLI file execution is paced. Public Python can pass
`accelerated_factor=0` for unpaced engineering inference.

## Anaconda Prompt / Windows Command Prompt

```bat
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets\Evaluation Tool\app"
set "OMP_NUM_THREADS=1"
set "OPENBLAS_NUM_THREADS=1"
set "MKL_NUM_THREADS=1"
set "NUMEXPR_NUM_THREADS=1"
set "EDGE_SPEECH_DATA_ROOT=C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\staging\s6c\manual_run"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline research-profile "C:\Users\amiri\Downloads\s6c_voice.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline file "C:\admitted\O0.wav" --identity-wav "C:\admitted\O1.wav" --research-profile "C:\admitted\split_naming.json" --research-gallery "C:\admitted\gallery.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -m edge_speech_pipeline.checks_research_s6c --receipt "C:\Users\amiri\Downloads\s6c_component_checks.json"
```

## Actual enrollment and isolated gallery

Create templates with the existing backend, on the separately admitted disjoint
E files and a fresh research-only directory. Do not call microphone enrollment
or use a private user gallery. This Python API can run in the same explicitly
configured interpreter (save a caller only with its own maintained README):

```python
from dataclasses import replace
from pathlib import Path
from edge_speech_pipeline.config import PipelineConfig
from edge_speech_pipeline.models import SpeakerModels
from edge_speech_pipeline.enrollment import enroll_wavs
config = replace(PipelineConfig(), profile_root=Path(r'C:\admitted\research_templates'))
models = SpeakerModels(config)
metadata = enroll_wavs('ResearchPerson_001', [Path(r'C:\admitted\E001.wav')],
                      models=models, config=config)
```

This is the real unchanged enrollment frontend: per-file downmix/resample,
at-least-.5-second level check, contiguous up-to-2-second ReDimNet windows at
1-second steps, normalized mean centroid. It does not estimate unique clean
speech or run Pyannote. Independent whole clips approximate paragraph duration;
they are not a newly recorded paragraph. E/C/Q leakage/rights and usable speech
duration are audited externally, and evaluation clips must never supply E or C.

Gallery JSON uses this exact schema (hash values must be actual full SHA256):

```json
{
 "schema_version":"edge-research-gallery.v1",
 "gallery_id":"fixed_roster_tier15",
 "profile_root":"C:\\admitted\\research_templates",
 "backend_sha256":"5c1a8635cba0d4648463f3b6d30c5a6137bc38d1200ab00c5944400aaa7b5609",
 "profiles":[{"profile_id":"actual_profile_stem", "display_name":"ResearchPerson_001",
   "metadata":{"path":"C:\\admitted\\research_templates\\actual_profile_stem.json", "sha256":"actual metadata SHA256"},
   "vector":{"path":"C:\\admitted\\research_templates\\actual_profile_stem.npy", "sha256":"actual vector SHA256"}}]
}
```

Only optional `provenance_binding` is additionally allowed at the top. E/C/Q
truth, rights and actual identities stay outside predictor inputs. All expected
profile JSONs must be manifest-listed, backend-compatible, uniquely named and
finite 192D float32. The loader verifies bytes and then executes
`ProfileStore.load()`, checking its count and exact templates. Invalid profiles
cannot silently disappear. Load the gallery once per worker and share its
immutable template matrix; create fresh resolver/session memory for each scene.
An explicitly requested roster may contain `profiles: []` when no enrollment
templates are available. It still passes through the actual `ProfileStore.load()`
and records `loaded_count: 0`, `template_availability: NO_AVAILABLE_TEMPLATES`,
and an immutable `(0, 192)` matrix. Post-association naming then reports an
unknown name with `NO_AVAILABLE_TEMPLATES`, performs no score/query, and retains
the anonymous speaker fallback. This is unavailable requested gallery coverage,
distinct from the `identity.mode: none` control and from positive enrollment.

Naming profile: `identity.mode='post_association'`. Defaults preserve historical
score .5128856897354127 and margin .03, but explicitly use 2 s unioned clean
support plus two disjoint observations rather than historical elapsed-source
duration. `query_policy='mature'` uses mature vectors; `any` is a named alternative.
`display_tentative` controls early tentative display. Bounded same-track name
memory (default 30 s) may carry an existing name on short evidence without a new
identification query or refreshed evidence time. Severe current voice conflict,
insufficient score/margin, identity state budget and prototype consistency remain
explicit outcomes. Known names never merge anonymous fragments in this mode.
Name-state memory follows the current live anonymous registry: a retired/archived
track releases its naming state and must receive fresh naming evidence on reentry.
This is logged separately from anonymous archive continuity; old transcript/name
events remain unchanged. If live tracks exceed the declared naming-state budget,
explicit naming-capacity rejections are retained and counted.

## Shared native/replay API and cache boundary

```python
from edge_speech_pipeline.research_scheduler_v3 import build_s6c_policy
from edge_speech_pipeline.research_identity_v3 import ResearchGallery
gallery = ResearchGallery(gallery_path, config.asset('redimnet2_b2_fp32').sha256)
policy = build_s6c_policy(profile, gallery=gallery, spatial_provider=provider)
# Submit exact raw research_embedding_observation / research_asr_observation.
records = policy.push(embedding_event, lane='speaker')
records += policy.advance({'speaker': next_speaker_bound, 'asr': next_asr_bound})
records += policy.finish()
snapshot = policy.snapshot()
```

Embedding input requires kind/event_id/observation_id, 192D finite vector,
source/receptive spans, available_at_sec, speech/overlap, evidence_kind short or
mature, clean_intervals and optional measured rms/clipping_fraction/clean_fraction.
`observation_id`, when supplied, equals event_id. Unknown fields reject. Model
outputs are never invented from truth. Event readiness is after required context
and upstream work; lane watermarks must not seal before later observations can
arrive. Model-free tests and actual-neural prefix proof are separate evidence.

Short/mature opportunities share one actual ReDimNet object, with separate call
and readiness logs. `embedding.window_sec` is mature length; `hop_sec` is dispatch.
`short_window_sec`, `short_hop_sec`, `mature_hop_sec` configure roles. Purity uses
arrived fixed-context segmentation frames; uncovered recent samples are unclean.
`clipping_fraction_max=1.0` disables clipping suppression; smaller registered
values cause actual admission rejections. `cadence_policy` supports fixed,
frequent (dispatch rate), sparse and uncertainty. Uncertainty uses online voice
change/onset and per-track clean/disjoint deficits from already released,
timestamped tracker snapshots. It records requested track debts and bounded
observation opportunities; an inference request itself never pays a track's
unique-evidence debt. Only subsequently associated accepted support does that.
Absent names/gallery scores are never used for this scheduling. Cue-triggered
cadence must explicitly enable its tracking cue route.
Context age and missing/empty dispatch counts are logged. A source-safe context
is limited to snapshots already released by both native lane watermarks; it can
be older or absent under accelerated/contended execution. This is actual runtime
dependence, not a deterministic hindsight context oracle. Uncertainty-native
cache identities must include full tracker/cue/scheduling policy and execution
mode; another profile's trace cannot regenerate its admissions. Native and paced
behavior require separate comparisons.

The resolver reports comparison/query hashes, loaded gallery and name events.
Forward name corrections need actual overlapping support, the same associated
track and bounded horizon/edit count. Anonymous association and first text/name
history remain preserved. Policy work is measured separately from shared cached
upstream times; native release/wall/export timing is separately observed.

Changing audio routing, evidence windows/context/gates or stateful ASR/endpoint
behavior requires affected real inference. Changing only post-association naming
may reuse exact compatible native observations, with the gallery/settings in the
prediction key. If uncertainty changes future inference, scheduling state and
all relevant policies enter the neural cache dependency. Do not reuse an S6B
projection that dropped the clean-support/role metadata needed by S6C.

## Validation and rollback

The check command writes a JSON receipt and uses temporary synthetic WAVs,
constructed vectors and injected deterministic model objects. It exercises real
file journals, scheduler/resolver/ProfileStore and native export code without
loading a neural model or hardware. It is not enrollment accuracy or actual-neural
timing evidence. Campaign-bound native, paced and long-session checks must follow
source freeze and are reported separately.

Rollback is omission of the v3 profile and added file/gallery options. Exact S6B
source remains in the admitted immutable snapshot and its receipts. Do not edit
an active execution epoch; new code/profile changes require a new admitted epoch.
This implementation does not establish real-world enrollment, CM5 memory/RTF,
continuous XVF hardware behavior or a promoted operating profile.
