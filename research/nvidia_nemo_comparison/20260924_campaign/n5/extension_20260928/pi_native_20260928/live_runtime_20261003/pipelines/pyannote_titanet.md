# Pyannote + TitaNet

## Current stabilization: preserved CHECK22 quiet native pass

Select **Pyannote + TitaNet** (`pyannote_titanet`) and independent Live/Saved,
then **Open Application** for the mature portrait Mode/People/Settings pages.
The pinned mel frontend, TitaNet encoder and separate gallery explained below
are unchanged. Rich spatial replay consumes recorded source-time beams/BMI;
plain WAV cannot use current sensors to fill missing evidence. C088 ReDimNet
calibration is not transferred: hybrid naming needs accepted calibration for
this actual encoder/query domain or reports Unknown/calibration blocker.
Direction-only seats are marked assumptions. Build25 prepares the metadata and
terminal cleanup repair; finite Pi/PC copies each reserve 256 MiB disk, not RAM.
CHECK22 completed30.1s quiet live input/Stop/raw+processed Save with independent
source and process closure. No captions or separate embedding-call evidence
were observed in that quiet check; TitaNet speech/extraction quality remains
unqualified. Build25 CHECK21
passed60.4s speech/Stop/Save with Pyannote/ReDimNet; it does not substitute for
this encoder's execution, extraction or accuracy evidence. See [current guide](../stabilization_20261005/STABILIZATION_MODE_GUIDE.md)
and [storage findings](../stabilization_20261005/SPEECH_STORAGE_REPAIR_FINDINGS.md).

Purpose: Retained Pyannote segmentation and the separately pinned TitaNet identity namespace; galleries must use that namespace.

Inputs: processed mono 16 kHz audio from live capture, an external mono PCM16 WAV, or the exact authoritative `FLOAT32_LE` segments of a kept History recording; existing installed model assets; and a finite session policy. Source selection is independent of backend. These settings do not select Nemotron geometry.

```python
selection = RuntimeSelection(diarizer="pyannote", embedding="titanet", input_source="live")
policy = SessionPolicy(maximum_session_seconds=300)
selection.validate()
policy.validate()
```

Run the registered PowerShell or CMD/Anaconda validation commands in [command_matrix.md](command_matrix.md), inserting this selection. Use `input_source="saved"` for file replay. This validation only prints JSON and does not load models. Actual `raw-qualification-07` passed and its exact source-module proof is retained by the reviewed candidate derivatives. Build08 also completed a live300 raw/processed GUI workflow. Raw eligibility remains separately pinned; these source results do not establish this model combination's live accuracy. See [raw-capture contract](../README_RAW_CAPTURE.md).

Outputs: independent configuration JSON; when native execution is admitted, immediate caption text and retained Pyannote speaker/name evidence. Existing identities are not re-enrolled or silently moved between ReDimNet and TitaNet galleries.

Use `SessionPolicy(3600, True)` only for an explicitly reserved developer soak. Audio duration, processing drain, backlog stop and cleanup are separate limits. These source tests establish no new diarization-quality or real-time result. See [README_PIPELINES](../README_PIPELINES.md) for input/output contracts and checks.


Shared clocks, powerset, embedding, cache and motion mathematics: [architecture and math](../ARCHITECTURE_AND_MATH.md).

## High-level choice and actual operations

`installed_engine.run` selects `N2ResidentModels('D0','E1', document)` and
`N2Engine`; Pyannote segmentation is retained while `N2SpeakerModels.embed`
dispatches `TitanetEmbedding.embed`. The manifest, frontend buffers and ONNX
hashes form the TitaNet namespace; `n2_people.titanet_store` opens only its own
gallery. Matching192-vector dimensions do not permit ReDimNet/TitaNet comparison.

The actual `titanet_embedding.mel_features` frontend uses pre-emphasis
`y[n]=x[n]-0.97*x[n-1]`, a512-point windowed FFT every160 samples and80 pinned
mel filters: `m[b,t]=log(sum(k,F[b,k]*|FFT(y_t)[k]|^2)+2^-24)`.
It normalizes each band over valid frames and pads the feature axis to the
exported model's contract; it does not repeat short waveform evidence.
The retained convolutional encoder/decoder maps those frames to a192-vector,
then `e=v/||v||2`. For a temporal convolution, each output combines weighted
neighboring features; pooling removes the duration axis. Exact internal layer
counts/pooling weights belong to the pinned ONNX graph and are not invented here.
The adapter rejects spans shorter than8000 samples (0.5 seconds); this application
minimum is not an accuracy guarantee. Resolver thresholds are unchanged.

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

Actual build08 `pipeline-qualification-05` completed the matched715127-sample
(44.6954375-second) saved input, kept the recording, closed models/owners and
mirrored all output. Paced source-to-EOF was44.863128 seconds; this is wall time
including source pacing, not model compute RTF. The retained768MiB address-space
limit and actual arena-disabled constructor remained in force. The model's fit
and complete saved pipeline are now measured; naming accuracy, live combined
refinement, sustained whole-application throughput and4/8GB performance are not
inferred. Later candidate reuse retains actual08 provenance through its explicit
source-difference review. See [current measured results](../NATIVE_RESULTS.md).

## RAM and execution scope

The actual build08 matched saved whole-pipeline worker sampled RSS 468,762,624 bytes, PSS 459,514,880 bytes and VmSize 626,655,232 bytes, with VmPeak 634,437,632 bytes under the unchanged 768 MiB address-space guard. The real TitaNet constructor retained arena disabling. A partial external unit trace sampled aggregate RSS 492,240,896 bytes and PSS 474,051,584 bytes; its minimum available RAM was 1,246,920,704 bytes. Partial sampling is not an exact continuous whole-unit peak. This establishes short saved fit/function for this selection, not live dual-worker fit, sustained performance or identity accuracy.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).


## Later exact optional selection

Actual build14 First03 completed matched saved45 child/primary EOF; Followup02 then completed all4.8M primary/raw/child live300 samples and30,001 child frames with window60, source300/drain60/backlog30. Full owner/model closure and sampled aggregateRSS760,020,992B/minimumavailable1,178,828,800B/owned swap0 support that bounded experimental scope. Zero optional corrections were observed. The exact measured receipt is accepted for production16 through reviewed GUI-policy and path-only reuse. Its actual idle GUI verified the controls without starting models or capture; the model measurements remain build14 facts. The actual build13 window30 child timeout remains a preserved fallback result, not full child EOF. These aggregate observations belong to the exact optional live selection; they do not replace the earlier primary-only saved worker measurements.
