# Intermediate 2.00 s

Purpose: select the `candidate_2` Nemotron geometry independently of source and identity encoder. Local intermediate candidate with matched-file CM5 component evidence; see the measured status below.

Inputs: mono 16 kHz audio, live or saved; ReDimNet, TitaNet or anonymous identity; the existing pinned Q8 model and retained streaming/Chunk52 LRU8 library. No model conversion or new download.

| Parameter | Value |
| --- | ---: |
| Chunk | 24 |
| Right context | 1 |
| Left context | 0 |
| FIFO | 80 |
| Speaker cache | 264 |
| Update period | 40 |
| Nominal input buffer seconds | 2.00 |

Geometry uses 80 ms encoder frames. Nominal input buffering excludes computation and scheduling. Output probability frames use the separate 10 ms model clock. The explicit preset is `v3-streaming`.

Configuration input:

```python
selection = RuntimeSelection(diarizer="nemotron", embedding="redimnet",
    input_source="live", nemotron_profile="candidate_2", allow_experimental=True)
policy = SessionPolicy(maximum_session_seconds=300)
selection.validate()
policy.validate()
```

To validate these inputs without native execution, use the registered PowerShell or CMD/Anaconda commands in [README_PIPELINES](../README_PIPELINES.md#run-the-focused-tests), replacing the final test-loading line with the configuration above plus `print(selection.validate(), policy.validate())`, and import `RuntimeSelection, SessionPolicy` from `profiles`. The full command matrix is in [command_matrix.md](command_matrix.md).

Outputs: validated selection JSON, immediate ASR captions and the selected diarizer's speaker evidence when the native worker is admitted. Synthetic tests produce no model results. Actual `raw-qualification-07` passed, and build08 completed a live300 raw/processed GUI workflow. Reviewed derivatives retain that exact source proof; it does not establish this selected model combination's accuracy or throughput. Raw capture eligibility remains separately pinned. See [raw-capture contract](../README_RAW_CAPTURE.md).

For saved audio set `input_source="saved"` and provide a bounded mono PCM16 16 kHz WAV through the runtime. For a kept History recording, replay instead reads the authoritative mono 16 kHz `FLOAT32_LE` segments exactly; its PCM16 convenience WAV is not the exact replay source. Select `embedding="titanet"` for the retained TitaNet namespace or `embedding="anonymous"` for anonymous identity. A developer soak explicitly uses `SessionPolicy(3600, True)`; it needs separate complete resource reservation and native execution evidence.

Actual `candidate2-01` completed all 715,127 samples / 4,470 frames with EOF,
model/cgroup closure and full independent mirror. Component RTF was 2.123295243;
first output was 2.461766 s, maximum simulated input backlog 17.6954375 s, and
peak sampled RSS 206,602,240 bytes. The measured throughput was below the input
audio rate. Changed geometry has no same-geometry numerical or ground-truth
quality comparison. See [NATIVE_RESULTS](../NATIVE_RESULTS.md) and
[architecture and math](../ARCHITECTURE_AND_MATH.md). This is a local candidate,
not an official NVIDIA recipe or integrated/sustained real-time pass.


## How this selection changes the pipeline

At the application level, this mode reduces input buffering relative to Chunk52 while retaining the cache; its measured component RTF2.1233 shows that this CPU cannot sustain that tested setting. ASR publishes independently of
the speaker lane. Live capture and saved replay use the same selected diarizer;
source selection changes acquisition and motion availability, not the model or
geometry. Saved audio keeps its recorded sample clock and does not use current
IMU pose or apply live gain again.

The native call advances by `24 ×0.08 =1.92 s` once enough context exists. Its maximum
positional extent is `264+80+0+24+1=369` coarse frames. The six submitted integers and
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

The full matched D1-only run sampled RSS up to 206,602,240 bytes. Component RTF 2.12330 and maximum simulated input backlog 17.6954375 seconds show a processing shortfall in that scope; the RSS observation does not qualify a complete application. ASR, embedding, source and GUI memory and CPU competition remain separate.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).
