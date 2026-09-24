# N4 predeclared comparison plan

Status: PREPARATION. No N4 integrated inference or shortlist has been accepted.
The observed N2 and N3 queues remain authoritative for their numerical state.
All 240 scenes are a seen engineering bank; there is no unseen-room claim.

## Population and compositions

All A0/A1/A2/A3 × D0/D1 × E0/E1 = 16 intended profiles retain 480 rows each.
Expected 7,680 integrated scene/tap rows. Unsupported, failed and missing cells
stay in coverage tables. Preparation is not execution. A missing adapter stays
pending until a documented implementation attempt establishes its outcome.
The baseline is the exact N1 Giga/Pyannote/ReDimNet/P0 composition. Every other
profile uses the same shared source, scheduler, event policy and mode semantics.
Native A2/A3 P1 punctuation is retained; P0 remains fixed for A0/A1. Text-layer
contrasts are separate paired diagnostics, never silently substituted raw text.

Keep N2's nominal D1 1.04-second buffer and N3's reviewed nominal ASR setting.
An implementation rescue needs a causal reason and existing boundary/short-turn/
returning/silence regressions; one rescue per family, at most two additional
meaningful sensitivity configurations. Calibration is C-only; Q, room and scene
metadata cannot select thresholds. D0/E1 association units need their own profile.
Uncalibrated operational open names continue to reject to Unknown. Closed-roster
assumptions cannot certify identity or adaptation. Adaptation is off throughout.

`prepare.py` froze a metadata-only 12-scene panel, one scene per family, including
the C105, short/returning-turn and silence regressions; both taps yield 24 cells.
Use that panel also for the gallery present/absent contrast. Report its actual
room/noise/reference distribution, not a claim of balanced independent people.
Use the already frozen N2 15-second E/C/Q rosters and encoder-specific galleries.
Open, selected-plus-Unknown, closed and gallery-absent conditions remain separate.
An outsider absent from the selected roster must remain an explicit denominator;
do not change the roster to improve measured coverage.

## Inference and evidence reuse

Runtime accepts exactly eight audio-only fields. Evaluator manifests never go to
the predictor. Independent scenes reset streams; native EOU does not reset
identity history. Reuse requires identical audio hash/gain, exact model/precision,
preprocessing, state/history, runtime, streaming context and scheduler policy.
Embedding keys also include exact window endpoints and waveform hash. Different
D0/D1 query windows invalidate vectors. A decoder conditioned on changed speaker
mask history must rerun. Integrated keys bind all component evidence parents.
Only complete hash-verified evidence can be reused; a cache key is not evidence.

A direct complete Controller execution is the conservative initial route.
Accelerated stateful evidence may replace redundant inference only after causal
event replay and application parity are demonstrated. Source-paced wall clocks
are never inferred from accelerated events. Separate labels preserve modeled
availability, actual event availability and actual widget delivery. No retroactive
ideal names are used for first display. Present/absent observers using the same
waveform must also preserve their independent mode/state and event histories.

## Metrics and failures

For complete non-overlap references, primary lexical WER is total substitutions
+ deletions + insertions divided by total reference words. Keep raw case/
punctuation-sensitive WER and canonical lexical WER separately. Canonicalization
is frozen before scoring: Unicode NFKC, lowercase, ASCII punctuation removal,
whitespace splitting. Report unchanged raw hypotheses privately. Empty references
yield inserted-word counts/minute, not an arbitrary WER. Complete overlap uses
speaker-stream cpWER and utterance-constrained MIMO-WER where supported, never
chronological simultaneous-reference ordinary WER. Incomplete ambient scenes
retain target-only diagnostics with all-speaker accuracy explicitly unavailable.
Failed execution does not become an empty successful hypothesis; successful
empty output counts every missed target word. Report failed reference words and
audio duration alongside scored denominators. No missing row is dropped.

Established evaluators are pinned separately: MeetEval 0.4.3 for WER/cpWER/MIMO,
pyannote.metrics 4.1 for DER/JER, with dependency/file receipts. Approximate
activity segments use the existing source-to-output mapping and complete scene
duration UEM, 0.25-second collar, overlap included, optimal per-scene mapping.
Pyannote's parameter is total collar width (0.125 seconds each side here).
N2's custom 0.25-second *radius* diagnostic is different and must not be paired
as the same metric. A no-collar descriptive sensitivity can accompany N4.
No additional alignment or timestamp clamping. Zero-reference activity yields
false-alarm seconds with DER/JER unavailable. Estimated 20-ms activity is not
phonetic ground truth. tcpWER is unavailable without exact reference word times.
Custom N2 diagnostics remain labelled as such and are not renamed library DER.

Naming is reported at first-visible, first-final and latest stages: correctly
named known speech; false-known outsider speech; Unknown; acquisition with
never-acquired and short-support rows; stable acquisition; wrong-name exposure;
returning-person consistency; known-track fragmentation; revision count, time
and visibility. Forced/seat-assumed choices remain separate from recognized names.
Cosine, channel probability and calibrated confidence are distinct fields.
All-one-name and all-Unknown controls reveal metric blind spots. No named metric
is populated if the necessary actual timing/visibility receipt is absent.

## Conditions and uncertainty

Per-scene records join evaluator-only family, room, source quality, receiver
orientation/obstruction, actual canonical noise policy/SNR, source level,
overlap and short-turn metadata. SNR refers to original four-microphone scene
construction, not a measurement of the processed mono output. Missing SNR is
unavailable, not clean. Corpora and demographics are metadata, not noise or causal
attributes. Analyze predicted clean-window loss, cross-speaker window mixing,
vector degradation and conservative rejection separately on existing matched
groups. Do not denoise or acquire new data.

Primary paired uncertainty resamples connected dependency clusters linking any
shared actor, text, source, noise seed or matched group; both taps stay together.
Use 2,000 deterministic bootstrap replicates with seed 20260924 and pooled-count
deltas. Fewer than eight available clusters suppresses an inferential interval.
Nine clusters exist in the full bank: intervals remain descriptive and fragile.
Also report matched-family sensitivity, leave-one-room-out and leave-one-connected
actor-group-out deltas. Missing candidate/baseline pairs reduce the explicit
matched denominator. An average improvement cannot override wrong names, missed
target words or material delay. No significance-driven winner is required.

## Resources and release checks

One candidate at a time for controlled resource and paced measurements; CPU GPU
is explicitly disabled. Record cold startup and warmed runs separately, file
bytes, Windows RSS/USS/private/pagefile fields, process tree, threads/CPU, caches,
bounded state, GPU allocated/reserved when exposed and device-wide usage. RSS
across workers is not unique physical memory; shared pages are not counted twice
as a claimed physical total. WSL PSS/cgroups are separate and include workers.
Unknown or sample-missed peaks remain unavailable. Retain teardown receipts.

Plan 1.5 GiB application + 0.5 GiB OS/display/audio for a 2-GiB total device.
Separate 2-GiB planning candidate, 4-GiB candidate, 8-GiB/desktop and unknown tiers.
No desktop result qualifies CM5, CPU throughput or a swap-based fit. Retain
GPU-favored large candidates as explicit higher-memory alternatives.

Shortlist the baseline plus 3–5 materially different functioning alternatives
only after matrix review. Each needs actual common-GUI source-paced execution
of the frozen 24 cells and timing-sensitive repeats, then a 20-minute saved-audio
continuity sequence with truthful actor IDs/capacity and stop/restart evidence.
Concatenated files are not continuous physical XVF state. Record actual producer,
backlog, widget, name and memory timing without subtracting pacing errors.
No default promotion. Preserve the campaign packaging cutoff of
2026-09-28T02:48:19.949192Z and classify PARTIAL if required coverage remains.

Sources: [MeetEval](https://github.com/fgnt/meeteval),
[pyannote.metrics reference](https://pyannote.github.io/pyannote-metrics/reference.html).
