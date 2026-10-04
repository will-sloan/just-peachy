# Pyannote + ReDimNet

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
