# Chunk52, two native threads: selection and timing

Current build35 scope: build35 is activated through the Just Peachy shortcut.
Opening stays idle with capture off. Choose one of six backend combinations,
Live microphone or Saved WAV, then Open Application and a Mode. Eleven Mode
policies are visible; backend, identity policy and calibration are separate.

Ordinary Pyannote + ReDimNet Start captured 12.5 s and completed Stop and the
selected full Discard in normal03. That whole check FAILED its later Settings
observer. Separate exit-only05 passed idle Open Application, Settings and Exit
with no Start, capture, models or worker launch. These are distinct scopes.
Live53 passed quiet capture after one verified recovery; Saved54 processed C24
speech with 137 indexed parts, 40 text rows and 117 embedding queries.

Hour08 completed 3600 s / 57.6M samples and all 20 source/model/closure gates.
Backlog grew to 495.360 s; source-to-EOF took 4090.959 s. Completion passed,
but sustainable real-time operation did not. Speech/name accuracy, natural
conversation and biometric calibration remain unqualified or UNCALIBRATED.

Normal live uses manual Stop and storage capacity without arbitrary duration,
recording, people, reference or slot counts, or a fixed ordinary backlog cutoff.
Actual memory/AS/free-space, finite capacity-derived file/drain allowances,
bounded queues, source/lease/owner, I/O and cleanup guards remain. Individual
lane delay labels are unavailable; aggregate backlog remains in health metadata.
Model geometry, thresholds and calibration math are unchanged.

Both encoder rows retain cache264/FIFO80/chunk52/right1/left0/update40 in80ms frames: nominal4.24s buffering excludes compute. The exact separately pinned graph requests two native threads; OS/BLAS/shared CPU limits remain. Calibration is independent for each encoder/query domain/roster.

Choose this row with Live/Saved input in the ordinary chooser, then open the
idle app and select Mode. A plain WAV lacks beam/BMI; spatial replay needs
recorded rich cues. Closed-group/seat assumptions are not biometric names.

All six rows share actual-BPE continuation, internal bounded recognition resets,
pause/Stop PnC, source-ordered atomic captions and conservative delayed labels.
Known track changes/source gaps split paragraphs; contiguous unattributed text
may group without claiming a shared speaker. Manual History preserves its window.

Read the [six-row notes](../CORE_REPAIR_PIPELINE_NOTES.md),
[shared contracts](../CORE_REPAIR_TECHNICAL_NOTES.md) and final
[selected source map](../core_repair_20261006/current_build35/SOURCE_MAP.md).
Candidate33 carries tested capacity-driven gallery/storage and compact writer
repairs plus a finite 1 GiB model AS policy; model/geometry/calibration math is
unchanged.


## Historical pre-core technical sheet and measurements

The original bytes below retain their exact release/input/component scopes.
Their "current" checks, latency/RTF and run examples do not pass the changed33
whole application or independently calibrate personal naming.

# Chunk52 with two native graph threads

## Current stabilization: both encoder routes have bounded native passes

The chooser exposes **Nemotron Chunk52 2T + ReDimNet**
(`chunk52_2t_redimnet`) and **Nemotron Chunk52 2T + TitaNet**
(`chunk52_2t_titanet`), each with independent Live/Saved and the retained mature
portrait application. This preserves the separately pinned two-thread core and
geometry below; earlier component RTF is not current whole-application RTF.
Advanced attribution selects retained sparse/single-D1 late policies. Spatial
evidence uses the original source window; rich saved replay consumes recorded
beam/BMI anchors and never current pose, while plain WAV lacks spatial evidence.
C088 voice thresholds do not transfer; unaccepted hybrid calibration or invalid
cues stays Unknown. The fresh metadata/terminal cleanup repair uses separate
256 MiB Pi/PC finite-check disk reservations, not RAM allocations. Fresh
build26 CHECK30 completed489599 processed/raw samples (about30.60s),57 indexed
nonempty captions/40 visible,306 actual D1 pushes and37 embedding calls over
overlapping656000 window-samples. Stop/Save, logical worker cleanup, natural
worker/main0 and independent source/unit closure passed. D1 push/finish sums
were19.560951s/3.343592s; embedding sum3.974033s and model setup3.173216s.
These call sums are not whole-pipeline sustainable RTF. Reported maximum source
lag was3.686385873s and reported drops0; the source separately recorded39
unconverted queued Stop-tail blocks/18720 transport frames and one incomplete
terminal packet. Those facts remain
visible rather than being relabeled as zero backlog or lossless continuous
operation. CHECK31 TitaNet completed30.1s/481600 processed/raw samples,
30 nonempty indexed captions,301 D1 pushes and24 embedding calls over448000
overlapping window-samples. D1 push/finish sums were16.636247113s/3.202955887s,
embedding5.088449037s, ASR7.299346898s and setup2.864817395s. Source lag maximum
was0.587177743s with reported drops0, five unconverted Stop-tail blocks/2400
transport frames and no incomplete terminal packet. Stop/Save/Settings/Exit and natural worker/
main0 plus independent physical closure passed. The live inputs differ, so
these are functional observations rather than an encoder-speed comparison.
Neither check establishes WER/DER,300s/hour use, named-speaker quality or
sustainable whole-pipeline real-time operation.
See [current guide](../stabilization_20261005/STABILIZATION_MODE_GUIDE.md)
and [storage findings](../stabilization_20261005/SPEECH_STORAGE_REPAIR_FINDINGS.md).

Purpose: explicitly select the measured separate two-thread native core while
preserving Chunk52 geometry, weights, source clock and probability output.
Default profiles and their libraries remain unchanged.

Inputs: `RuntimeSelection('nemotron', 'redimnet', 'live', 'chunk52_threads2', True)`;
live/saved source and ReDimNet/TitaNet/anonymous identity remain independent.
The original model, wrapper and A76 dependencies are required, plus the exact
isolated variant descriptor/build/source files and bundled component review.
See [README_NATIVE_VARIANT](../README_NATIVE_VARIANT.md) for all pins.

Geometry: cache264, FIFO80, chunk52, right1, left0, update40; unchanged 4.24 s
nominal input buffering, excluding computation. The four numerical-library
environment variables stay1. The native graph helper explicitly requests2.
The entire process remains on CPU2/3 in the shared200% unit.

Configuration only:

```python
from profiles import RuntimeSelection, SessionPolicy
selection = RuntimeSelection('nemotron', 'redimnet', 'live', 'chunk52_threads2', True)
print(selection.validate(), SessionPolicy().validate())
```

PowerShell: use the CPU14/early-owner test wrapper in
[README_PIPELINES](../README_PIPELINES.md#run-the-focused-tests), replacing the
test invocation with the expression above. Command Prompt and Anaconda Prompt
use the equivalent wrapper shown there. These configuration commands load no
model. An admitted native launch must use the root-reviewed launcher/action and
a fresh process; changing a profile string alone never relaxes the binder pin.

Outputs: same selected pipeline's captions and speaker evidence, with explicit
native descriptor/core/component-review provenance. Missing or changed variant
evidence fails before model creation; an arbitrary descriptor is not admitted.

Actual 2 GB component result: all 715,127 samples / 4,470 frames completed, and all
4,470 × 8 values exactly matched the preserved same-geometry reference. Component
RTF was 0.554327206 versus 1.081286854 for one thread. This is a short component
comparison, not ground-truth accuracy, integrated performance or sustained
qualification. ASR/embedding CPU competition still requires measurement.
The later component-only repeated replay completed3,600 seconds/57,600,000 samples and360,001 frames with the same continuously retained D1 state. Average component RTF was0.8844478644; the last10-minute bin was0.94448, and late rolling windows briefly exceeded1. Temperature reached85.35 degrees C while RSS mostly plateaued near166.5MiB, swap stayed zero and available RAM stayed above1.48GB. This measures an hour of diarization with its cooling/CPU margin limits, without ASR, embedding, microphone or GUI. It does not qualify a whole-application hour or identity quality.

See [NATIVE_RESULTS](../NATIVE_RESULTS.md) for full source/closure/resource
provenance and [architecture and math](../ARCHITECTURE_AND_MATH.md) for the combined
pipeline explanation and nominal-input versus computation distinction.

## How this selection changes the pipeline

At the application level, this mode changes only the explicitly pinned graph thread request from1 to2; cache, model and arithmetic outputs matched exactly on the short reference, while whole-pipeline CPU competition remains unmeasured. ASR publishes independently of
the speaker lane. Live capture and saved replay use the same selected diarizer;
source selection changes acquisition and motion availability, not the model or
geometry. Saved audio keeps its recorded sample clock and does not use current
IMU pose or apply live gain again.

The native call advances by `52 ×0.08 =4.16 s` once enough context exists. Its maximum
positional extent is `264+80+0+52+1=397` coarse frames. The six submitted integers and
explicit preset are checked inside `nemotron_binding.bind` /
`BoundNemotronDiarizer._bind` against the actual C structure before model creation.
`installed_engine.selected_descriptor` chooses the retained assets;
`native_documents` preserves the selected embedding namespace when substituting
the explicitly admitted two-thread core. `_update` validates every new10 ms
probability row and EOF against `floor(received_samples/160)+1` for nonempty input.

The neural operations can be read as temporal convolution
`h[t,o] = activation(b[o] + sum(k,i, W[k,i,o] * x[t+k,i]))` and masked contextual
attention `A = softmax(Q K^T / sqrt(d) + mask) V`. These equations define the
operators, not an invented layer count or an exact cost forecast. The carried
speaker cache and FIFO supply selected prior context; they are not extra new
audio in the RTF denominator. Fewer cache frames alter the model's information,
whereas more native threads change scheduling of the same selected graph.

For named speakers, installed `N2Engine._speaker_loop` selects genuine contiguous
exclusive speech through `exclusive_windows`; `N2SpeakerModels.embed` runs the
selected encoder and the unchanged resolver compares its normalized vector to
the matching gallery. TitaNet and ReDimNet namespaces remain separate. Native
D1 anonymous mode takes `N2Engine._anonymous_native_only`, bypasses the embedding
model/query loop and publishes anonymous model-supported tracks. This differs
from Pyannote anonymous mode, which still uses ReDimNet continuity.

Optional `sparse_clean_turn` changes only eligible named-embedding query cadence,
not ASR/diarizer samples or thresholds. `single_d1_late_labels` changes bounded
presentation using real `n2-caption:` evidence and stable span IDs; neither
setting creates a second diarizer. See [late labels](../README_LATE_LABELS.md),
[sparse schedule](../README_SPARSE_EMBEDDING.md) and
[shared mathematics](../ARCHITECTURE_AND_MATH.md). The actual build07 CurrentDelayed whole-pipeline result and build08 live300 GUI/source result have their own exact scopes. They do not establish this geometry's integrated throughput or named-gallery accuracy. A completed component row above does not supply either claim.

## RAM and execution scope

The short D1-only comparison sampled RSS 190,808,064 bytes, PSS 184,850,432 bytes and VmSize 361,807,872 bytes. The completed continuous component hour had an RSS plateau near 166.5 MiB, sampled EOF RSS 175,210,496 bytes, zero owned swap and minimum system-available RAM 1,481,637,888 bytes. These distinct observations are not interchangeable peaks. Average RTF 0.88445 worsened toward 0.94 in later bins while temperature reached 85.35 C; the desired 0.8-0.85 margin was not sustained. Temperature and timing warrant CPU/cooling attention but do not prove thermal throttling at a particular time. Component-hour completion is established; whole-application two-thread RAM, CPU competition and sustained operation remain unqualified.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).
