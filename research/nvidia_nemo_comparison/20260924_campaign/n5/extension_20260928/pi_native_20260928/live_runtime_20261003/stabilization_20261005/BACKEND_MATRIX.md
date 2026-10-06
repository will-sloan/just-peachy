# Stabilization backend matrix

Build26 is activated; its Saved-source closure repair passed CHECK28.
All six routes have scoped Live/Stop/Save/closure evidence.
Actual current outcomes are in STABILIZATION_RESULTS.md. Retained component
measurements and current native results are separate. Selectability does not
establish sustainable real-time operation.

## Six normal choices and exact pins

Sherpa ONNX ASR/punctuation is shared. Live microphone / Saved WAV is independent;
kept-session Replay comes through History. Each encoder retains its own gallery.

| Choice | Catalogue ID | Diarizer profile | Encoder | Native app |
|---|---|---|---|---|
| Pyannote + ReDimNet | `pyannote_redimnet` | `pyannote` | ReDimNet | CHECK21 speech/segmentation/embeddings/Stop/Save passed |
| Pyannote + TitaNet | `pyannote_titanet` | `pyannote` | TitaNet | CHECK22 short live/ASR/Stop/Save/closure passed; no speech/identity quality |
| Nemotron Delayed + ReDimNet | `delayed_redimnet` | `current_delayed` | ReDimNet | CHECK23 short live/D1/Stop/Save/closure passed |
| Nemotron Delayed + TitaNet | `delayed_titanet` | `current_delayed` | TitaNet | CHECK29 short live/D1/Stop/Save/Exit/closure passed; CHECK24 failure retained |
| Nemotron Chunk52 2T + ReDimNet | `chunk52_2t_redimnet` | `chunk52_threads2` | ReDimNet | CHECK30 speech/D1/37 embedding calls/Stop/Save/Exit/closure passed |
| Nemotron Chunk52 2T + TitaNet | `chunk52_2t_titanet` | `chunk52_threads2` | TitaNet | CHECK31 speech/D1/24 embedding calls/Stop/Save/Exit/closure passed |

Default recipe **balanced**, retained O0 route and named **Open with names** intent
do not confer identity calibration. The old classic recipe has restrictions and
is not a universal named default. Chunk52 2T requires its separate descriptor and
two native graph-thread pin, not the one-thread alias.

| Nemotron profile | Chunk | Right | Left | FIFO | Cache | Update | Native preset | Nominal buffer |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| CurrentDelayed | 264 | 1 | 1 | 0 | 264 | 188 | v3-offline | 21.20 s |
| Chunk52 2T | 52 | 1 | 0 | 80 | 264 | 40 | v3-streaming | 4.24 s |
| Compact3s, hidden | 37 | 1 | 0 | 40 | 128 | 40 | v3-streaming | 3.04 s |

Nominal buffering = `(chunk + right) × 0.08 s`, excluding compute, scheduling
and association. CurrentDelayed's retained source wait was about 21.3 s. GPU
remains disabled. Compact3s reduces context/history, so it is not a numerically
equivalent speed optimization. Its two encoder candidates remain hidden until
current native Live success qualifies each route.

Streaming, official low/very-low/ultra-low and other poor-RTF candidates remain
in the full historical catalogue, outside normal choices. This stabilization
does not restart their campaigns or create permanent shortcuts for a sweep.

## Retained performance scope

| Configuration | Measurement | Scope/limit |
|---|---|---|
| CurrentDelayed | RTF 0.4047877 | Historical matched 44.695 s component; not current whole app |
| Chunk52 one thread | RTF 1.081286854 in matched comparison; earlier about 1.085 | Component near/above real time |
| Chunk52 two threads | RTF 0.554327206; 4470 × 8 outputs exact in matched comparison | Same-geometry component improvement |
| Chunk52 two-thread soak | Hour RTF 0.8844478644; last 10 min 0.94448; late rolling cost briefly >1; 85.35 °C; RSS about 166.5 MiB | D1 only, excludes ASR/encoder/physical capture/GUI |
| Compact3s | Short RTF 0.856810; RSS 169,885,696 B; first output 3.68575 s | Reduced context; quality/current live pending |
| Pyannote, either encoder | Current app timing PENDING | No invented combined CM5 RTF |

RTF is compute wall time/source-audio duration. Component RTF below 1 does not
prove stable integrated queues, thermal state, latency or drain. The retained
whole-application hour attempt failed; component soak evidence does not repair
that qualification. See [NATIVE_RESULTS.md](../NATIVE_RESULTS.md) for original
pins, input and limits.

## Source, identity and attribution compatibility

| Route | Behavior |
|---|---|
| Live + acoustic/named Modes | Actual selected XVF/diarizer/encoder; per-row current scope above |
| Plain WAV + acoustic/named Modes | Reproducible acoustic replay with source/sample clocks |
| Plain WAV + spatial/assigned Modes | Unavailable: missing recorded beam/BMI clocks |
| Kept rich session + spatial/assigned Modes | Original logs/epoch/callback/sample anchors; no current pose |
| Assigned direction | Unique eligible seat assumption, marked seat assumed; not verified voice |
| Hybrid, original Pyannote/ReDimNet | Original C088 gate retained |
| Hybrid, TitaNet/Nemotron domains | Independent encoder/query-domain/roster calibration required; otherwise Unknown/blocker |
| Internal Unknown/anonymous | Preserved uncertainty; no normal standalone Anonymous choice |

TitaNet's writable personal domain is currently uncalibrated. New
Nemotron/ReDimNet queries likewise do not inherit the old C088 calibration.
Scores/thresholds cannot be copied between domains.

Named Nemotron choices retain one collapsed Advanced control:

| Preset | `embedding_schedule` | `speaker_attribution` |
|---|---|---|
| Standard | continuous | retained |
| Sparse clean turns | sparse_clean_turn | retained |
| Late labels | continuous | single_d1_late_labels |
| Sparse + late | sparse_clean_turn | single_d1_late_labels |

Single-D1 correction uses the selected diarizer, existing 2 s refresh/30 s recent
revision window. No optional parallel refiner runs. Sparse scheduling is not
audio dropping. Exact selections still need manager admission.

## RAM and CPU interpretation

This physical CM5 has **2 GB RAM**. OS, model residency, ASR, diarizer, encoder,
source/archive buffers and GUI consume distinct memory. Component RSS is not
aggregate app RSS; address-space limits are not measured hard RSS caps.

A future 4 GB/8 GB device may improve residency/caching/concurrent headroom when
measurement identifies a memory bottleneck. It does not make the same CPU faster,
remove thermal limits, qualify parallel diarizers, or prove better accuracy.
There is no upgraded-RAM native benchmark here. The two-thread graph shares its
admitted CPU budget with the rest of the app. See
[RAM_RESOURCE_GUIDE.md](../RAM_RESOURCE_GUIDE.md).

## Architecture and math references

Start with [STABILIZATION_MODE_GUIDE.md](STABILIZATION_MODE_GUIDE.md), then:

- [Pyannote + ReDimNet](../pipelines/pyannote_redimnet.md)
- [Pyannote + TitaNet](../pipelines/pyannote_titanet.md)
- [CurrentDelayed](../pipelines/current_delayed.md)
- [Chunk52 two threads](../pipelines/chunk52_threads2.md)
- [Shared architecture/math](../ARCHITECTURE_AND_MATH.md)
- [Conversation Modes/math](../full_application_20261004/APPLICATION_MODES_AND_MATH.md)
- [Seat/calibration adapter](README_SEAT_BACKENDS.md)
- [Recorded spatial math/clocks](README_SAVED_SPATIAL.md)
- [Kept replay](README_SAVED_REPLAY.md)
- [Sparse embedding](../README_SPARSE_EMBEDDING.md)
- [Single-D1 late labels](../README_LATE_LABELS.md)

Angles retain the microphone-array frame. Relative orientation compensation
does not create absolute heading or reliable translation from a six-axis BMI270.
Saved replay uses the recorded historical frame and rejects gaps.

## Preserved startup failures

Current per-route results are in the first table and STABILIZATION_RESULTS.md.
Historical package23 pin: `16bfa6fcddfac639c83e0c785b4292d98eac478873d5a4c3a2efb3ceb7740492`.
Job13 reached chooser, mature portrait, named Mode, Start and consent, then failed
in the worker before SESSION/capture; the exact closed/private monitor is
preserved. This establishes workflow reachability, not ASR/diarizer/encoder
execution. Build22's FSIZE0 staging failure/partial is retained separately.

The current guides document seat/blocker behavior, recorded pose/beam consumption,
readback, source/storage failure causes and closure. Quiet execution does not
measure DER, readable speech, named-speaker
accuracy, noisy-room utility, physical touch or whole-app hour stability.

