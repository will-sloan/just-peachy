# CurrentDelayed: selection and timing

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

Both encoder rows retain cache264/FIFO0/chunk264/right1/left1/update188 in80ms frames: nominal21.20s buffering excludes compute/association/queue delay. Shared ASR partials remain immediate. Actual native singleton activity/cue source clocks and late-label revisions remain; neither encoder inherits C088 calibration.

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

# CurrentDelayed

## Current stabilization: both encoder routes have scoped quiet native checks

The chooser exposes **Nemotron Delayed + ReDimNet** (`delayed_redimnet`) and
**Nemotron Delayed + TitaNet** (`delayed_titanet`), with independent Live/Saved.
Open Application enters the mature portrait pages. Geometry below is unchanged;
Advanced attribution selects retained sparse and/or single-D1 late labels,
without a second diarizer. Delayed seat evidence uses the original speech
window, not model-output arrival or current tablet pose. Rich replay requires
recorded beams/BMI/sample anchors; plain WAV has none. C088 voice calibration
does not transfer to these query domains: unaccepted hybrid calibration or
missing cues stays Unknown, and direction-only seats remain marked assumptions.
The fresh metadata/terminal repair reserves 256 MiB independently per Pi/PC
finite-check copy (disk, not RAM). CHECK23 completed30.1s quiet ReDimNet live
input with301 actual D1 pushes, Stop/Save and independent process closure.
Fresh build26 CHECK29 completed30.1s quiet TitaNet live input with301 D1
pushes, Stop/Save and natural/independent source, worker and main closure.
Neither quiet check establishes captions, separate embedding-call evidence or
speaker-quality/calibration results. Build25 CHECK21 passed60.4s speech/Stop/Save
with Pyannote/ReDimNet only; no Delayed or embedding-extraction pass is inferred.
Prior timing/math below retains its measured scope. See [current guide](../stabilization_20261005/STABILIZATION_MODE_GUIDE.md)
and [storage findings](../stabilization_20261005/SPEECH_STORAGE_REPAIR_FINDINGS.md).

Purpose: select the `current_delayed` Nemotron geometry independently of source and identity encoder. Retained delayed LRU1/2 MiB metadata recipe. Historical unpaced RTF 0.4047877, source wait 21.3 s; neither is new live qualification.

Inputs: mono 16 kHz audio, live or saved; ReDimNet, TitaNet or anonymous identity; the existing pinned Q8 model and retained delayed LRU1 library. No model conversion or new download.

| Parameter | Value |
| --- | ---: |
| Chunk | 264 |
| Right context | 1 |
| Left context | 1 |
| FIFO | 0 |
| Speaker cache | 264 |
| Update period | 188 |
| Nominal input buffer seconds | 21.20 |

Geometry uses 80 ms encoder frames. Nominal input buffering excludes computation and scheduling. Output probability frames use the separate 10 ms model clock. The explicit preset is `v3-offline`, required to preserve FIFO zero.

Configuration input:

```python
selection = RuntimeSelection(diarizer="nemotron", embedding="redimnet",
    input_source="live", nemotron_profile="current_delayed", allow_experimental=False)
policy = SessionPolicy(maximum_session_seconds=300)
selection.validate()
policy.validate()
```

To validate these inputs without native execution, use the registered PowerShell or CMD/Anaconda commands in [README_PIPELINES](../README_PIPELINES.md#run-the-focused-tests), replacing the final test-loading line with the configuration above plus `print(selection.validate(), policy.validate())`, and import `RuntimeSelection, SessionPolicy` from `profiles`. The full command matrix is in [command_matrix.md](command_matrix.md).

Outputs: validated selection JSON, immediate ASR captions and the selected diarizer's speaker evidence when the native worker is admitted. Synthetic tests produce no model results. Actual `raw-qualification-07` source proof passed and is retained by the exact reviewed source modules; build08 completed300 seconds with4,800,000 raw and processed samples, Save raw and full replay/closure. Raw eligibility remains separately pinned. See [raw-capture contract](../README_RAW_CAPTURE.md).

For saved audio set `input_source="saved"` and provide a bounded mono PCM16 16 kHz WAV through the runtime. For a kept History recording, replay instead reads the authoritative mono 16 kHz `FLOAT32_LE` segments exactly; its PCM16 convenience WAV is not the exact replay source. Select `embedding="titanet"` for the retained TitaNet namespace or `embedding="anonymous"` for anonymous identity. A developer soak explicitly uses `SessionPolicy(3600, True)`; it needs separate complete resource reservation and native execution evidence.

Status: build07 completed a matched44.6954375-second saved CurrentDelayed+ReDimNet+Sherpa whole pipeline (sampled peak RSS about531MiB), and build08 completed the live300 GUI workflow. The quiet GUI run is functional/control evidence, not speech-quality evidence. The later build08 whole-application hour failed around319 seconds at an output-membership guard; it is not a sustained pass. New-root reuse preserves the exact actual evidence and reviewed source differences. See [native results](../NATIVE_RESULTS.md). General model reference (this retained/local geometry is not an official recipe): [NVIDIA model card](https://huggingface.co/nvidia/Nemotron-3-Diarization/blob/main/README.md).


Shared clocks, powerset, embedding, cache and motion mathematics: [architecture and math](../ARCHITECTURE_AND_MATH.md).

## How this selection changes the pipeline

At the application level, this mode large delayed block and LRU1 residency amortize graph work over much more new audio; its21.20-second input buffer leaves little room inside a30-second revision window. ASR publishes independently of
the speaker lane. Live capture and saved replay use the same selected diarizer;
source selection changes acquisition and motion availability, not the model or
geometry. Saved audio keeps its recorded sample clock and does not use current
IMU pose or apply live gain again.

The native call advances by `264 x0.08 =21.12 s` once enough context exists. Its maximum
positional extent is `264+0+1+264+1=530` coarse frames. The six submitted integers and
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
[shared mathematics](../ARCHITECTURE_AND_MATH.md). Named-gallery accuracy,
optional combined admission and sustained whole-application operation remain
separate gates; completed short pipeline/source results do not satisfy them.

## RAM and execution scope

The build07 saved CurrentDelayed/ReDimNet whole-pipeline worker reached sampled RSS 556,761,088 bytes (531 MiB), PSS 547,734,528 bytes and VmSize 730,234,880 bytes under the unchanged 768 MiB address-space guard. These are worker observations, not a continuous aggregate peak for the GUI, source and all children. Build08 GUI02's quiet live worker reached RSS 500,858,880 bytes; its later aggregate trace covered replay only and cannot supply the missing full live aggregate peak. The failed build08 hour stopped at an output-membership guard, not demonstrated RAM exhaustion. The repaired full-application hour04 ended at its worker watchdog with only 57,359,280 of 57,600,000 source samples committed (3,584.955 seconds), before normal EOF. Its full closed mirror is available, but worker logical/model cleanup and a completed hour are not established.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).


The controlled build13 source candidate adds bounded100ms saved/repeated/kept replay appends and numeric append-time/source-wall-lag metrics; see the [source-only batching contract](../README_SAVED_SOURCE_METRICS.md). It also includes the reviewed optional activity-handoff repair. Production16 is now activated through the consolidated launcher; actual build13/14 matched45s trials exercised the changed saved path with exact sample/F32 agreement. Research07 also matched all4,470 x8 D1 floats exactly and preserved final ASR while publishing30 supported/partial late-label updates. This is not a claim that batching fixes the failed hour04: external5Hz output-tree checks and1Hz fsynced resource sampling are other unmeasured overhead candidates, and their guards remain unchanged. The research comparison reuses baseline04, requires exact processed float32/sample-clock agreement, and compares all4470×8native D1 probabilities by hash and maximum absolute difference with an explicit1e-5 tolerance. No additional baseline, hour or geometry sweep is prescribed.


The separate Pyannote-primary/anonymous-CurrentDelayed child has later actual build14 live300 EOF evidence under its exact window60 admission. This does not expand the above CurrentDelayed-primary selection evidence; see [optional contract](../README_OPTIONAL_REFINER.md).
