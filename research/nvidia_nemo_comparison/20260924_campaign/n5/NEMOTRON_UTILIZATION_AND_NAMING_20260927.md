# Nemotron utilization, naming and optimization assessment

The separate speaker encoder is not required for anonymous Nemotron diarization.
Our D1 path already bypasses Pyannote segmentation and the baseline clustering
tracker. However, ordinary anonymous mode still computed E0/E1 embeddings for
research/identity plumbing. That work is unnecessary when the only desired
labels are Speaker 1, Speaker 2, etc. Automatic recognition of a person's name
across separate conversations remains a different task.

This audit reads the accepted N3 source, our measured N2/N4 evidence, the user's
[Baseten article](https://www.baseten.co/blog/nvidia-nemotron-3-diarization/), and
the primary implementation/model documentation linked below. It neither
contacts the Pi nor sends recordings to a hosted service. Training is assessed,
not started; the current campaign's no-training and GPU-off limits remain.

## Capability audit and concrete change

| Capability | Current implementation | Finding/action |
|---|---|---|
| Native eight-channel activity | All eight probabilities retained | Already utilized; no forced single-speaker argmax |
| Persistent session speaker state | Native stream reused through chunks; reset between sessions | Already utilized; no reset at every turn |
| Overlap | Multiple active slots retained; overlapping/mixed coarse ASR windows remain Unknown | Honest ambiguity; detecting overlap does not separate mixed voices into two transcripts |
| Pyannote segmentation and baseline clustering | Bypassed by D1 speaker loop | Already replaced on D1, retained for baseline/enrollment workflows |
| External embeddings in anonymous mode | Still loaded/called in accepted N3 | Fresh derivative prepared to bypass them |
| Name matching | Separate model-compatible gallery, confidence gate and name map | Required for current automatic cross-session naming design |
| Streaming presets | 1.04, 0.64, 0.32 s tested | Supported and measured; smallest preset increases work |
| Offline-style preset | Not exposed by our three-profile adapter | Add/test separately; not silently equivalent to the existing saved-file streaming tests |
| Speech/silence postprocessing | Fixed 0.5 native activity threshold in current timeline | Calibrate causal threshold/hysteresis against false activity and missed short replies |

Code evidence: accepted-source `app/n2_pipeline.py` retains native frame
probabilities, generates slot labels directly and only uses `_n2_name_history`
for naming. `app/n2_models.py` loads Pyannote only for D0, while
`app/n3_models.py` still loads an external encoder whenever the existing
non-caption resident path requests one. `ActivityTimeline.associate` avoids
inventing exact speaker-word alignment for a mixed coarse ASR span.

`prepare_d1_anonymous_v1.py` now creates a source-only derivative from the exact
accepted N3 receipt. In ordinary D1 anonymous mode it requests ASR-only resident
acquisition, while the independently acquired native diarizer and speaker lane
stay active. It also skips embedding-window extraction. Named/D0 modes and
explicit research observers retain their original routes. The original source,
working preview launchers and immutable releases are unchanged.

The derivative passed **50 model-free tests: 49 passed, one optional neural
test skipped**, with zero failures/errors. Tests check model acquisition,
all eight channels, overlap, short turns, caption labels/raw-word preservation,
named-mode boundaries and existing N2 contracts. One initial inherited test
failed because its campaign-tools path assumed a non-relocated checkout. The
failure is retained; the final run bound that test's campaign-tools location to
the unchanged worktree, without changing application code.

See `D1_ANONYMOUS_PREPARATION_CHECK_V1.json` and
[run instructions](README_D1_ANONYMOUS_V1.md). Status is **prepared and tested
without models**, not a neural/GUI acceptance or a new deployed backend. A
fresh-resident actual saved-file test must confirm zero encoder loads/calls,
identical activity/anonymous labels, normal drain, save/reopen and closure.
Global model-manifest requirements and package contents have not yet been
reduced. A resident used earlier for named mode may retain encoder weights.

## Naming without an external encoder

| Desired behavior | Separate voice encoder needed? | How to name speakers |
|---|---|---|
| Anonymous conversation | No | Direct native slot labels |
| Human assigns names for this session | No | Explicit session/track-to-name map, persisted with transcript |
| Human assigns a fixed roster without voice verification | Not necessarily | Explicit assignment; label as manual/assumed, not verified identity |
| Automatically recognize a saved person next session | A validated voice-matching mechanism is needed | Currently ReDimNet + compatible gallery + confidence/margin/Unknown gate |
| Reuse Nemotron internal features for recognition | Research possibility, not a validated replacement | Extract/pool suitable features, test cross-session matching, rebuild compatible references and calibrate rejection |

For example, the user may assign this session's Speaker 2 to Alice. The mapping
can follow Speaker 2 through the session without computing another embedding.
It does not tell the next session that Speaker 2 is Alice. If Bob speaks first
next time, output numbering will differ. Manual labels should remain editable,
be attached to the saved session's track ID, and never become automatic verified
gallery enrollments. Track swaps/merges still need correction; a label does not
repair a diarization mistake. The manual-map workflow is proposed, not newly
implemented in this derivative.

The current Transformers interface exposes per-frame activity logits, hidden
states and a streaming cache. Those hidden states contain chunk/cache context;
they are not documented as drop-in ReDimNet/TitaNet voiceprints. Reusing them for
recognition is an experiment requiring its own matching and rejection tests.
[Transformers model interface](https://huggingface.co/docs/transformers/main/model_doc/nemotron3_diarization)

Recommended architecture: D1 owns anonymous activity and continuity; an optional
identity layer attaches names. For automatic names, compute embeddings on clean
exclusive evidence until a calibrated decision is possible, then use limited
rechecks for contradiction/track changes rather than embedding every half-second
forever. This is a proposed policy requiring retests; disabling rechecks entirely
would risk retaining an incorrect name after a track swap. Keep Unknown when
evidence is insufficient. Our current processed-query naming gate is not yet
calibrated, so there is no verified automatic naming claim to preserve by fiat.

## Modes and optimization priorities

NVIDIA specifies one checkpoint with 1.04, 0.64 and 0.32-second streaming input
buffers and a 30.4-second offline-style configuration. The cache preserves
arrival-ordered speaker channels within a stream. Buffer delay excludes compute
time. [NVIDIA model card](https://huggingface.co/nvidia/Nemotron-3-Diarization)

1. **Anonymous mode without embeddings.** Implemented in the fresh candidate
   above, pending actual application qualification. It simplifies dependencies
   and removes needless identity work. Our N4 measured E0 embedding calls occupy
   only 0.52% of D1/E0 collection time; removing them cannot by itself fix the
   1.89 wall-seconds/audio-second CPU result. Memory savings require measurement.
2. **Longer chunks for saved files.** Compare the documented offline-style preset
   with nominal streaming on matched files; measure activity, returning speakers,
   false alarms, memory and actual model-call RTF. Larger chunks may amortize
   overhead, but no speedup or accuracy gain on our data is established yet.
   Keep a short-buffer option for live use. Select geometry at session creation;
   do not hot-swap it into an active cache without explicit state testing.
3. **Distinguish two offline routes.** Current upstream C++ documentation calls
   `v3-offline` a larger-chunk streaming preset. Its separate full-attention
   `--offline` path has a short-recording positional limit (about 6.6 minutes).
   Those current CLI capabilities are not automatically capabilities of our
   pinned C ABI. Reconcile version/API support before using them.
   [Native C++ diarization modes](https://github.com/NVIDIA/NeMo-Speech.cpp/blob/main/docs/cli.md#diarize-audio)
4. **CPU/runtime optimization.** Profile the native calls under admitted CPU
   limits; a two-thread build is a bounded experimental option only if resource
   ownership allows it. Retain a one-thread comparator and measure whole-stack
   contention. Additional quantization, smaller caches, fused kernels or lower
   output resolution are candidates, not established fixes. Cache changes must
   retain returning-speaker and overlap tests; coarse output may hurt boundaries.
5. **GPU Windows route.** Prior CUDA component results are promising. Benchmark
   the complete stack and actual GPU allocation before making it the default.
   No GPU work is launched under the present GPU-off allowance. Server throughput
   in the Baseten article does not predict this CPU or Raspberry Pi's speed.
6. **False-activity tuning before retraining.** D1's O1 false activity dominates
   its error numerator. Replay preserved probabilities through a small,
   predeclared causal onset/offset/hysteresis/min-duration grid using calibration
   data, then evaluate once on separate data. Penalize missed brief speech as
   well as false alarms. Never optimize against the reported test bank and call
   the result an independent improvement. Do not feed a delayed speech mask back
   into the diarizer in a way that deletes context/initial speech.
7. **Use activity for other app signals carefully.** Per-speaker activity can
   inform the UI and turn-taking. Replacing a fast ASR endpoint/VAD component is
   a separate latency/accuracy decision, especially with the current O1 false
   detections. Overlap activity does not reconstruct two overlapping sentences;
   that would need adequate ASR alignment or a separate separation/multitalker
   recognition capability.

## Fine-tuning feasibility and proposed experiment

NVIDIA provides an eight-speaker streaming training configuration with audio/RTTM
manifests, checkpoint initialization, separate validation data, and activity plus
phantom-speaker auxiliary losses. The default training settings are not a
hardware sizing prescription for our desktop.
[Official eight-speaker recipe](https://github.com/NVIDIA-NeMo/Speech/blob/main/examples/speaker_tasks/diarization/conf/neural_diarizer/sortformer_streaming_8spk.yaml)

Fine-tuning is feasible in principle. Its useful objective here would be better
activity detection and continuity under our microphones, room acoustics, noise,
brief replies and overlaps. It is not a mechanism for making anonymous channel
numbers intrinsically mean Alice/Bob, nor does unchanged-architecture fine-tuning
normally reduce the number of operations needed for inference.

Our proposed sequence, not an executed training run:

- Audit saved audio and per-speaker time labels. Existing estimated boundaries
  and incomplete ambient annotations are not automatically reliable training
  targets; an unlabelled audible person must not become a silence target.
- Separate calibration/training/validation/test by speaker, original recording,
  room and mixture family before tuning. The existing reported bank is already
  seen engineering data; genuine independent validation requires untouched
  material. Keep both taps/derived mixtures together to prevent leakage.
- Start from the unquantized trainable checkpoint. Use a small memory feasibility
  probe and bounded fine-tuning experiment before committing to longer training;
  adjust batch/chunk lengths and accumulation to measured capacity. A 100M
  parameter count alone does not establish fit in the RTX 3080's VRAM. Do not
  train the deployed Q8 GGUF directly through this inference runtime.
- Include annotated noise-only periods and difficult overlaps while retaining
  a broad validation set. Compare against simpler postprocessing calibration.
  Frozen-backbone or limited-layer adaptation may be worth testing, but those
  are proposed experiments, not validated campaign configurations.
- Measure zero-collar DER, explicit collar sensitivity, miss/false/confusion,
  short/returning-speaker behavior and runtime resources. Export/quantize only
  after gains survive the holdout; rerun native/reference, reset/cache, Windows
  and ARM64 compatibility checks on the new artifact.

No training, new human enrollment, capture, cloud upload or model download was
performed for this assessment. The campaign acceptance/deadline remains
unchanged. Training would be separately scoped work after offline delivery.
