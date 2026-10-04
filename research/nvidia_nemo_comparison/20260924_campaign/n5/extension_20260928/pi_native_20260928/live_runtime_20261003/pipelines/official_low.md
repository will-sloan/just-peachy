# Official low latency

Purpose: select the `official_low` Nemotron geometry independently of source and identity encoder. Official NVIDIA Nemotron 3 model-card geometry, verified 2026-10-03. A bounded CM5 component attempt is recorded below; this geometry has no new complete integrated-pipeline qualification.

Inputs: mono 16 kHz audio, live or saved; ReDimNet, TitaNet or anonymous identity; the existing pinned Q8 model and retained streaming/Chunk52 LRU8 library. No model conversion or new download.

| Parameter | Value |
| --- | ---: |
| Chunk | 9 |
| Right context | 4 |
| Left context | 0 |
| FIFO | 264 |
| Speaker cache | 264 |
| Update period | 222 |
| Nominal input buffer seconds | 1.04 |

Geometry uses 80 ms encoder frames. Nominal input buffering excludes computation and scheduling. Output probability frames use the separate 10 ms model clock. The explicit preset is `v3-streaming`.

Configuration input:

```python
selection = RuntimeSelection(diarizer="nemotron", embedding="redimnet",
    input_source="live", nemotron_profile="official_low", allow_experimental=True)
policy = SessionPolicy(maximum_session_seconds=300)
selection.validate()
policy.validate()
```

To validate these inputs without native execution, use the registered PowerShell or CMD/Anaconda commands in [README_PIPELINES](../README_PIPELINES.md#run-the-focused-tests), replacing the final test-loading line with the configuration above plus `print(selection.validate(), policy.validate())`, and import `RuntimeSelection, SessionPolicy` from `profiles`. The full command matrix is in [command_matrix.md](command_matrix.md).

Outputs: validated selection JSON, immediate ASR captions and the selected diarizer's speaker evidence when the native worker is admitted. Synthetic tests produce no model results. Actual `raw-qualification-07` passed, and build08 completed a live300 raw/processed GUI workflow. Reviewed derivatives retain that exact source proof; it does not establish this selected model combination's accuracy or throughput. Raw capture eligibility remains separately pinned. See [raw-capture contract](../README_RAW_CAPTURE.md).

For saved audio set `input_source="saved"` and provide a bounded mono PCM16 16 kHz WAV through the runtime. For a kept History recording, replay instead reads the authoritative mono 16 kHz `FLOAT32_LE` segments exactly; its PCM16 convenience WAV is not the exact replay source. Select `embedding="titanet"` for the retained TitaNet namespace or `embedding="anonymous"` for anonymous identity. A developer soak explicitly uses `SessionPolicy(3600, True)`; it needs separate complete resource reservation and native execution evidence.

Actual component attempt `official-low-01` failed safely at the processing drain
deadline. It accepted 558,400 samples (34.9 s) and preserved 3,456 frames without
EOF. Prefix-only RTF was 4.81915; first output was 1.28671 s. The last graph took
6,988.73 ms compute for 720 ms new audio; its early first output did not establish
sustainable throughput. See [NATIVE_RESULTS](../NATIVE_RESULTS.md) for exact source,
timing, RAM and closure evidence. No completed-file, quality or real-time pass.
The recipe remains the [NVIDIA model-card](https://huggingface.co/nvidia/Nemotron-3-Diarization/blob/main/README.md)
geometry, independent of whether it fits this CPU. See [architecture and math](../ARCHITECTURE_AND_MATH.md).


## How this selection changes the pipeline

At the application level, this mode keeps the official large FIFO/cache while computing each0.72 seconds of new audio; the measured mature graph cost greatly exceeded that budget. ASR publishes independently of
the speaker lane. Live capture and saved replay use the same selected diarizer;
source selection changes acquisition and motion availability, not the model or
geometry. Saved audio keeps its recorded sample clock and does not use current
IMU pose or apply live gain again.

The native call advances by `9 ×0.08 =0.72 s` once enough context exists. Its maximum
positional extent is `264+264+0+9+4=541` coarse frames. The six submitted integers and
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

This failed-prefix D1-only run had a separate process high-water RSS observation of 235,307,008 bytes and 1,536,573,440 bytes available RAM at the final observation. The mature graph took about 6,989 ms for 720 ms of new audio, whereas frontend/copy phases were much smaller. The measured bottleneck is compute/drain capacity in this scope, not demonstrated physical RAM exhaustion. No whole-file, integrated-memory or sustained pass follows from the early first output.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).
