# Pyannote anonymous

Purpose: Retained Pyannote segmentation with anonymous conversation labels and no enrolled-person naming. The retained Pyannote anonymous path still loads ReDimNet for voice continuity; it omits the enrolled-person gallery lookup, not embedding computation.

Inputs: processed mono 16 kHz audio from live capture, an external mono PCM16 WAV, or the exact authoritative `FLOAT32_LE` segments of a kept History recording; existing installed model assets; and a finite session policy. Source selection is independent of backend. These settings do not select Nemotron geometry.

```python
selection = RuntimeSelection(diarizer="pyannote", embedding="anonymous", input_source="live")
policy = SessionPolicy(maximum_session_seconds=300)
selection.validate()
policy.validate()
```

Run the registered PowerShell or CMD/Anaconda validation commands in [command_matrix.md](command_matrix.md), inserting this selection. Use `input_source="saved"` for file replay. This validation only prints JSON and does not load models. Actual `raw-qualification-07` passed, and build08 completed a live300 raw/processed GUI workflow. Reviewed derivatives retain that exact source proof; it does not establish this selected model combination's accuracy or throughput. Raw capture eligibility remains separately pinned. See [raw-capture contract](../README_RAW_CAPTURE.md).

Outputs: independent configuration JSON; when native execution is admitted, immediate caption text and retained Pyannote speaker/name evidence. Existing identities are not re-enrolled or silently moved between ReDimNet and TitaNet galleries.

Use `SessionPolicy(3600, True)` only for an explicitly reserved developer soak. Audio duration, processing drain, backlog stop and cleanup are separate limits. These source tests establish no new diarization-quality or real-time result. See [README_PIPELINES](../README_PIPELINES.md) for input/output contracts and checks.


Shared clocks, powerset, embedding, cache and motion mathematics: [architecture and math](../ARCHITECTURE_AND_MATH.md).

## High-level choice and actual operations

`installed_engine.run` chooses the same baseline `ResidentModels` as
Pyannote/ReDimNet and passes `mode='anonymous_conversation'` with `gallery=None`.
The baseline `PrototypeEngine` still needs ReDimNet voice embeddings for
continuity/clustering. Anonymous removes enrolled-person naming; it does not
remove the encoder's CPU/RAM cost. By contrast, the installed D1
`N2Engine._anonymous_native_only` explicitly obtains ASR-only resident models and
skips its embedding window loop, acquiring the native diarizer separately.

The same convolution/temporal-pooling encoder produces `v`; L2 normalization
`e=v/sqrt(sum_i(v_i^2))` lets the tracker compare consistent voice evidence over
time. Those comparisons support an anonymous track, not a known person's name.
Pyannote's local powerset channel numbers may change across windows and must not
be rendered as permanent identity without the retained continuity mechanism.

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

Anonymous removes enrolled-person naming here but retains ReDimNet embeddings for continuity, so it does not remove the encoder's CPU/RAM cost. There is no newly measured complete worker/aggregate memory result for this precise combination. Native D1 anonymous bypasses embedding and is a different execution path; its component RSS cannot be used as this Pyannote mode's requirement.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).
