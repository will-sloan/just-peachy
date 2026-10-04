# Chunk52

Purpose: select the `chunk52` Nemotron geometry independently of source and identity encoder. Retained experimental Chunk52 LRU8 recipe. Historical unpaced RTF 1.0851342, source wait 4.3 s; not new live qualification.

Inputs: mono 16 kHz audio, live or saved; ReDimNet, TitaNet or anonymous identity; the existing pinned Q8 model and retained streaming/Chunk52 LRU8 library. No model conversion or new download.

| Parameter | Value |
| --- | ---: |
| Chunk | 52 |
| Right context | 1 |
| Left context | 0 |
| FIFO | 80 |
| Speaker cache | 264 |
| Update period | 40 |
| Nominal input buffer seconds | 4.24 |

Geometry uses 80 ms encoder frames. Nominal input buffering excludes computation and scheduling. Output probability frames use the separate 10 ms model clock. The explicit preset is `v3-streaming`.

Configuration input:

```python
selection = RuntimeSelection(diarizer="nemotron", embedding="redimnet",
    input_source="live", nemotron_profile="chunk52", allow_experimental=True)
policy = SessionPolicy(maximum_session_seconds=300)
selection.validate()
policy.validate()
```

To validate these inputs without native execution, use the registered PowerShell or CMD/Anaconda commands in [README_PIPELINES](../README_PIPELINES.md#run-the-focused-tests), replacing the final test-loading line with the configuration above plus `print(selection.validate(), policy.validate())`, and import `RuntimeSelection, SessionPolicy` from `profiles`. The full command matrix is in [command_matrix.md](command_matrix.md).

Outputs: validated selection JSON, immediate ASR captions and the selected diarizer's speaker evidence when the native worker is admitted. Synthetic tests produce no model results. Actual `raw-qualification-07` passed, and build08 completed a live300 raw/processed GUI workflow. Reviewed derivatives retain that exact source proof; it does not establish this selected model combination's accuracy or throughput. Raw capture eligibility remains separately pinned. See [raw-capture contract](../README_RAW_CAPTURE.md).

For saved audio set `input_source="saved"` and provide a bounded mono PCM16 16 kHz WAV through the runtime. For a kept History recording, replay instead reads the authoritative mono 16 kHz `FLOAT32_LE` segments exactly; its PCM16 convenience WAV is not the exact replay source. Select `embedding="titanet"` for the retained TitaNet namespace or `embedding="anonymous"` for anonymous identity. A developer soak explicitly uses `SessionPolicy(3600, True)`; it needs separate complete resource reservation and native execution evidence.

Actual 2026-10-03 component result `chunk52-02`: all 715,127 samples / 4,470 frames
completed with EOF and closure. All 4,470 × 8 probabilities exactly matched the
retained same-geometry reference. Component RTF was 1.08129; first output on the
paced source clock was 5.12488 s. Mature regular calls were slower than their
new audio duration. See [NATIVE_RESULTS](../NATIVE_RESULTS.md) for exact source
and resource evidence. No ground-truth accuracy, integrated or sustained pass.
The separate [two-thread option](chunk52_threads2.md) preserves this geometry and
has its own binary/evidence gate. See [architecture and math](../ARCHITECTURE_AND_MATH.md)
for the pipeline-level explanation; nominal buffering excludes compute.


## How this selection changes the pipeline

At the application level, this mode keeps the retained large speaker cache with smaller blocks; one-thread short throughput was slower than source arrival. ASR publishes independently of
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

The short matched D1-only run sampled at most 190,349,312 bytes RSS, with at least 1,480,802,304 bytes system-available RAM and temperature up to 56.75 C. Component RTF 1.08129 indicates insufficient processing margin in this one-thread scope despite available physical RAM. ASR, embedding, capture and GUI costs are absent; this is not a whole-application memory budget. The two-thread component hour belongs to the separate `chunk52_threads2` selection.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).
