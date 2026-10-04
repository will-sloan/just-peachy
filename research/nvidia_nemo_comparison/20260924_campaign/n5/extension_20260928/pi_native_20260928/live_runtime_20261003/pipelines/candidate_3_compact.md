# Experimental 3.04-second compact context

Actual 2026-10-03 build02 component evidence: `compact3-02` completed the matched
44.6954375-second /715,127-sample source with4,470 frames and complete EOF, at
component RTF0.85681. Context differs from Chunk52; quality and sustained
whole-pipeline behavior remain unqualified. See [native results](../NATIVE_RESULTS.md).

Purpose: investigate the measured cost of processing a filled native context at
the same nominal 3.04-second input buffer as `candidate_3`. This changes retained
speaker/recent context and may change diarization behavior; it is not a quality
preserving or numerically equivalent optimization.

Inputs: continuous mono 16 kHz samples, live or saved, and ReDimNet/TitaNet or
anonymous identity independently. Geometry is chunk37, right1, left0, FIFO40,
speaker-cache128, update40, explicit `v3-streaming` preset. All samples still reach
the same existing pinned Q8 model. Maximum context is 206 coarse frames, within
the actual 5000-frame model cap; cache128 exceeds the native minimum16.

The model SHA256 remains
`08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1`;
core is the retained LRU8
`fa8ecbb66124b62fced485d45dd2ec6018634a35d39dbc143e221b9f7230b622`;
C ABI wrapper remains
`9600de4c486aa4ea8209b6f2d78ec33fb3148d74c8a4395bd23eeaf00137915f`.
The complete runtime-file manifest is still required by the caller; these three
pins do not replace that check. Binding verifies all six submitted geometry
integers on the actual C structure before model creation.

For PowerShell, CMD or Anaconda Prompt, follow the early CPU14/registered-owner
steps in [command_matrix.md](command_matrix.md) with:

```text
--diarizer nemotron --profile candidate_3_compact --embedding anonymous --source saved --experimental
```

This produces validated configuration JSON only. For an admitted native matched
comparison, use [README_NATIVE_BENCHMARK.md](../README_NATIVE_BENCHMARK.md), keeping
the exact input SHA/model/library and substituting
`--profile candidate_3_compact --experimental`. Start a fresh process for this
geometry. Default source budget is 300 seconds; long repeated replay requires
explicit developer policy, disk reservation and native admission.

Outputs are complete source/frame/EOF probability evidence and measured component
timing when actually executed. Host parameter validation produces no native
output. Actual `compact3-02` completed all 715,127 samples / 4,470 frames with EOF
and closure. Component RTF was 0.856810; first output was 3.68575 s. Peak sampled
RSS was 169,885,696 bytes; maximum cached PSS 164,120,576 bytes, with zero swap.
One late regular call still exceeded its 2.96 s of new audio. Reduced cache/FIFO
changes the context, so there is no same-geometry numerical-equivalence or
ground-truth quality claim. Integrated and sustained behavior remain unqualified.
See [NATIVE_RESULTS](../NATIVE_RESULTS.md) and [architecture and math](../ARCHITECTURE_AND_MATH.md).
The official three recipes and existing 1–5-second candidates remain selectable.

## How this selection changes the pipeline

At the application level, this mode halves the speaker cache and recent FIFO relative to candidate_3; reduced work came with changed historical context, so quality cannot be inferred from its RTF0.8568. ASR publishes independently of
the speaker lane. Live capture and saved replay use the same selected diarizer;
source selection changes acquisition and motion availability, not the model or
geometry. Saved audio keeps its recorded sample clock and does not use current
IMU pose or apply live gain again.

The native call advances by `37 ×0.08 =2.96 s` once enough context exists. Its maximum
positional extent is `128+40+0+37+1=206` coarse frames. The six submitted integers and
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

The short matched D1-only run sampled RSS 169,885,696 bytes, PSS 164,120,576 bytes and VmSize 344,391,680 bytes; owned swap was zero and minimum available RAM was 1,500,643,328 bytes. Its RTF 0.85681 is a short component result. Reduced context changes the information available to the model, so lower memory/time does not establish equivalent speaker quality or whole-application headroom.

All measured native results in this campaign use the 2 GB CM5. A process address-space (AS) ceiling limits virtual mappings, not installed or resident RAM. Sum-of-RSS can count shared pages more than once; aggregate PSS and system-available RAM provide different evidence. Do not add peaks from separate runs. More physical RAM on a 4/8 GB board may provide cache/concurrency margin, but it does not itself remove a fixed AS guard, speed a compute-bound graph or establish better cooling; no 4/8 GB benchmark is claimed. Exact scopes and counters are in [RAM/resources](../RAM_RESOURCE_GUIDE.md) and [native results](../NATIVE_RESULTS.md).
