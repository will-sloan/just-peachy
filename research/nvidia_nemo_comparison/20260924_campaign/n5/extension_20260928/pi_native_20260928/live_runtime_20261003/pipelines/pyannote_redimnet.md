# Pyannote + ReDimNet: selection and timing

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

Retained Pyannote powerset speech/overlap activity feeds ReDimNet2-B2 FP32 voice evidence. Original C088 resolver/gates remain; repair fixtures do not establish personal-domain accuracy. Compatible enrollment and source-linked unverified closed-group assumptions remain separate.

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

# Pyannote + ReDimNet

## Current integration: build25 speech and build26 rich Saved replay passed

Select **Pyannote + ReDimNet** (`pyannote_redimnet`) and independent Live/Saved,
then **Open Application** for the mature portrait Mode/People/Settings pages.
The retained segmentation, normalized ReDimNet vectors and thresholds explained
below are unchanged. Rich saved spatial replay uses recorded beams/BMI and
source anchors; plain WAV has no such evidence. Original C088 calibration
applies only in its original Pyannote/ReDimNet domain; invalid spatial cues or
unaccepted naming evidence remains Unknown. Build25 prepares an explicitly
reserved metadata/terminal cleanup repair, with 256 MiB independently per Pi/PC
qualification copy (disk, not RAM). CHECK21 passed60.4s/966400samples,48indexed
nonempty captions/40visible, source closure, cleanup and Save raw + processed with no
failure. The verified export records120 positive Pyannote segmentation API calls
(summed16.875635s) and208 positive ReDimNet embedding API calls
(summed20.750158s), all normalized192D. It also records208 speaker decisions and
105 identity decisions. Overlapping model windows prevent interpreting these
call sums as whole-pipeline RTF. They establish actual inference, without named
accuracy,300s speech or hour qualification. Model setup took3.231309s;
RSS49,283,072→354,811,904B is a startup observation rather than a session peak.
CHECK27's worker consumed the full matched saved source and recorded spatial
anchors, with source verification and logical cleanup. Its parent GUI closure
failed while requiring a physical microphone owner from Saved input. Fresh
build26 CHECK28 passed the repaired full GUI replay, processed Save,
Settings/Exit and independent closure. It consumed the full966400 samples,
6040 audio anchors,906 beams and3156 original poses without current motion;
source membership/pins stayed unchanged. Its35 nonempty indexed/visible captions
differ from live CHECK21's48; neither a quality nor output-equivalence claim is made.
See [current guide](../stabilization_20261005/STABILIZATION_MODE_GUIDE.md)
and [storage findings](../stabilization_20261005/SPEECH_STORAGE_REPAIR_FINDINGS.md).

Purpose: Retained baseline Pyannote segmentation and ReDimNet identity namespace.

Inputs: processed mono 16 kHz audio from live capture, an external mono PCM16 WAV, or the exact authoritative `FLOAT32_LE` segments of a kept History recording; existing installed model assets; and a finite session policy. Source selection is independent of backend. These settings do not select Nemotron geometry.

```python
selection = RuntimeSelection(diarizer="pyannote", embedding="redimnet", input_source="live")
policy = SessionPolicy(maximum_session_seconds=300)
selection.validate()
policy.validate()
```

Run the registered PowerShell or CMD/Anaconda validation commands in [command_matrix.md](command_matrix.md), inserting this selection. Use `input_source="saved"` for file replay. This validation only prints JSON and does not load models. Actual `raw-qualification-07` passed, and build08 completed a live300 raw/processed GUI workflow. Reviewed derivatives retain that exact source proof; it does not establish this selected model combination's accuracy or throughput. Raw capture eligibility remains separately pinned. See [raw-capture contract](../README_RAW_CAPTURE.md).

Outputs: independent configuration JSON; when native execution is admitted, immediate caption text and retained Pyannote speaker/name evidence. Existing identities are not re-enrolled or silently moved between ReDimNet and TitaNet galleries.

Use `SessionPolicy(3600, True)` only for an explicitly reserved developer soak. Audio duration, processing drain, backlog stop and cleanup are separate limits. These source tests establish no new diarization-quality or real-time result. See [README_PIPELINES](../README_PIPELINES.md) for input/output contracts and checks.


Shared clocks, powerset, embedding, cache and motion mathematics: [architecture and math](../ARCHITECTURE_AND_MATH.md).

## High-level choice and actual operations

`installed_engine.run` chooses `pipeline.ResidentModels` and the retained
`PrototypeEngine` for this baseline. Pyannote supplies local activity/overlap;
ReDimNet supplies voice vectors used by tracking and the unchanged name resolver.
`SpeakerModels.segment` consumes the retained segmentation window and
`SpeakerModels.embed` produces the embedding. The ReDimNet model SHA and route
preprocessing select its compatible read-only gallery. A successful embedding
call with an empty gallery cannot establish a person's name.

Temporal convolution has the general form
`h[t,o]=activation(b[o]+sum(k,i,W[k,i,o]*x[t+k,i]))`; pooling maps variable-duration
frame representations to a fixed-length vector. The exact retained graph defines
its pooling and dimensions; this page does not substitute an unverified average
for learned pooling. The emitted192-vector is normalized as `e=v/||v||2`, and
`e·g` is cosine similarity only for another normalized ReDimNet vector. Existing
score, margin and evidence-support thresholds remain unchanged.

The retained segmentation input is160,000 samples (10 seconds at16 kHz). Its
seven powerset classes are `000,100,010,001,110,101,011`; the powerset decision is
converted to per-local-speaker activity and overlap evidence before tracking.
It is activity evidence, not an enrolled identity. See the precise shared
[powerset, clocks and resolver explanation](../ARCHITECTURE_AND_MATH.md).

Live/saved selects the source independently. The live route uses retained
processed microphone samples and genuinely available mounted-motion evidence;
saved replay does not invent motion or reapply live gain. ASR text and stable
caption IDs remain independent of the speaker lane. Continuous optional delayed
D1 refinement is a separate default-off worker requiring measured combined
admission; the single-D1 late-label selector is restricted to Nemotron primary.

The build08 complete Pyannote/TitaNet saved pipeline is a different selected embedding configuration. The raw07 source proof and build08 GUI300 workflow establish their recorded source/control scopes, not this combination's full native result. ReDimNet naming accuracy, sustained throughput and4/8GB performance remain unmeasured here.

## RAM and execution scope

There is no newly measured complete Pyannote/ReDimNet worker or aggregate RAM result in the representative qualification set. Build07's 531 MiB worker result uses CurrentDelayed instead of Pyannote, while build08's Pyannote result uses TitaNet. Neither may be substituted for this combination. Its embedding encoder and gallery state still consume CPU/RAM; input source adds its own costs.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).
