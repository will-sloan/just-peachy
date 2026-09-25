# Integration findings after D1 full-bank preparation

The initial findings below are a source-inspection checkpoint. The later
implementation update at the end records the first modeled D0/E0 adapter;
neither establishes inference or stage acceptance. The immutable source is
`local/releases/n4-catalog-v3/prototype`, receipt SHA-256
`8050c8bee52a6ec83c95f3514cb81219c3664dd43e172a477d35a54888e610d5`.
It explains the next implementation constraints while full ASR collection runs.

## Preserve two distinct application paths

`app/n2_pipeline.py:N2Engine._accept_activity` consumes each native D1 update,
uses the actual ActivityTimeline contiguous exclusive-window selector, calls
the compatible encoder and resolves the result through N2NameMap. Its native
slot identifiers persist within that independent scene. It retains temporal
name support and calls `_revise_supported_spans`. The latter associates actual
presentation word spans with predicted activity, targets the exact text revision
and span IDs, and publishes `transcript_label_revision`. The `_emit` override
also tries these revisions after raw text publication.

Therefore D1 embeddings must not be passed through D0's anonymous clustering
tracker merely to reuse D0 command replay. That would change the application.
D1 joint replay needs the actual N2 naming/history/span-revision path, with
fresh per-scene state and the intended gallery/mode. The captured anonymous
speaker decisions cannot be silently reused for a different gallery condition.
E0 and E1 namespaces remain separate; only their verified matching D1 query
geometry is shared. D0 queries are different and remain separate evidence.

D1's `_speaker_loop` advances the speaker source watermark after each actual
100-ms read and all activity/embedding work for that read. It processes the
native finish update and its caption revisions before the final infinite
watermark. Its local `ready` argument at final close still holds the last push
value; it is not the time at which native finish/revisions completed. Preserve
call order and the true source-delivery census when reconstructing closure.

## Execute the real S7 policy semantics under an explicit clock contract

`vendor/edge_speech_pipeline/research_s7_policy.py:ObservedClock` accepts an
injected `clock` callable and a once-bound origin. This is an available seam for
testing; no global clock patch or edit to the accepted release is needed.
`ObservedEligibility._eligible` checks current clock age and decision readiness,
in addition to source support and admitted-event ordering. `publication_freshness`
checks the age again under publication. A plain S6C batch result omits these
rules and is insufficient evidence of application parity.

`ObservedPolicyDispatcher` retains the same bounded worker and source-watermark
protocol. Finite source watermarks cannot be ahead of the clock. Its input
allowlist excludes evaluation truth. A future deterministic cache replay must
preserve these rules, predictor commands, worker order and source delivery;
sorting only ASR words or substituting readiness for source watermarks is wrong.

The clock injection API does not by itself qualify replay as observed. If a
modeled clock is used, the enclosing result must say so even though inherited
S7 field names contain `observed` or `monotonic`. Such results cannot supply
first-visible or hardware latency. The current ComponentPresentation adapter
explicitly rejects observed-clock records; a new separately versioned adapter
and tests would be needed to consume actual S7 policy output under any declared
modeled contract. Preserve all original raw ASR and final formatting parents.

Actual Controller parity must be demonstrated separately, with unchanged common
source/UI and explicit event-clock evidence. Per-component isolated call costs
do not measure contention, policy-queue delay, widget application or complete
stack memory. The required source-paced retained-stack panels and continuity
runs remain necessary. No coupled or GUI cells have been counted here.

## Available evidence and next work

- D0 full-bank review: 960 cells passed; global persistent-source activity output
  still needs implementation. Unassigned/conflicting/overlap/tail regions remain
  explicit; embedding windows are not a substitute for DER.
- ASR full bank: active under its immutable admission. Preserve all its bound
  code and run the terminal full reviewer after its exact coordinator exits.
- D1 full bank: 960 cells prepared, with a runtime predecessor gate requiring
  passed ASR full-bank review. No D1 numerical worker or waiter has started.
- Existing command and presentation helpers have narrow tested scopes. Build
  their causal joint integration, gallery/mode factors and metrics without
  promoting a helper test or cache-collection count to integrated acceptance.

All source inspection is read-only. For the exact current process/admission
state and continuation commands use N4_HANDOFF.md and the per-run READMEs.

## First implemented modeled S7 path

`component_s7_replay.py` now merges reconstructed ASR/D0 commands and invokes
the actual S7 dispatcher, observed-eligibility mixin, tracker, publication
freshness check and caption state with an injected zero-origin modeled clock.
The source-progress watermark is never replaced by availability. D0 partial-tail
closure retains its original ready argument and separately waits for source
delivery. Policy queue/compute/publication delay are explicitly zero assumptions;
native worker mixed-clock ages are omitted. No first-visible latency is claimed.

Twelve tests passed, including stale evidence under another lane's delay,
publication expiry, strict watermark equality, stale caption rejection, exact
raw/final preservation, command validation and real worker failure cleanup.
`probe_component_s7.py` then passed eight A0/A1/A2/A3 x O0/O1 development replays
with the accepted D0/E0 component pair. Every source file and compressed/expanded
event binding was reverified. Model loading was forbidden. The output preserved
all 350 raw ASR observations and 27 final utterances; each worker fully drained.
`COMPONENT_S7_REPLAY_CHECK_V1.json` binds the private receipt and exact code.

This path is restricted to Balanced anonymous D0/E0. Its native `observed` and
GUI field names contain modeled values only; complete Controller/widget parity
is still unqualified. Next implement the actual N2NameMap gallery/mode and D1
activity/history/span paths, then qualify exact application parity and integrate
full activity/scoring. Do not generalize this adapter to D1 by using the D0
cluster tracker. Integrated acceptance remains 0/7,680; read
README_COMPONENT_S7_REPLAY.md for API, purpose, limits and all shell commands.
