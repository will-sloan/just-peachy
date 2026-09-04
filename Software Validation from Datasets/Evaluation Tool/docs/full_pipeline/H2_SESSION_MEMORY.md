# H2 bounded session memory

## Scope

Session memory improves continuity after the acoustic/open-set pipeline has produced evidence. It is not a biometric enrollment store and it is not allowed to manufacture a known identity.

The causal order is:

```text
audio evidence -> anonymous cluster -> full-gallery open-set decision
               -> hysteresis/expiry -> bounded roster/history
               -> public label and optional bounded correction
```

Truth labels are never used by the transition algorithm. They are applied after replay only to score warm reacquisition, inheritance, stale-name error, false lock-in, and expiry behavior.

## Stored state

Depending on mode, the runtime may retain:

- bounded recent embeddings per anonymous cluster;
- bounded identity observations and transition history;
- a session-local anonymous speaker profile;
- confirmed known identity, last verification time, and contradiction count;
- a bounded active roster;
- a bounded event/correction history.

The strict runtime tuning supplies hard limits. Baseline maxima are 128 cluster embeddings, 64 session speakers, 32 identity observations per cluster, 64 identity-history entries per cluster, 64 roster entries, and 512 session-history events. Identity evidence is source-clock retained for 120 seconds by default; unmatched known-only evidence is retained for 3 seconds.

Eviction is deterministic and part of the runtime identity because it can affect long-session output. Expired roster entries are removed before active entries when space is needed.

## Hysteresis and release

Confirmation can require one, two, or three consecutive causal passes. The selected score threshold, Top-1/Top-2 margin, minimum evidence, embedding consistency, hysteresis, and expiry are development-frozen together. A contradiction, insufficient evidence, or expiry can hold, release, or force reconfirmation; evaluation cannot retune these transitions.

## M4 active roster and confidence decay

M4 treats the active roster only as a deterministic search-order hint. Every
identity-evidence event asserts that the scored IDs have the same set and count
as the enrolled gallery, completes every gallery score, and only then applies
the open-set policy. No roster membership, score bonus, or threshold change can
turn a partial search into a known identity.

Decay uses source/audio time, never wall time. The frozen half-life reduces the
strength of the most recent genuine full-gallery verification. Crossing the
release floor may return a cluster to Unknown, but decay cannot tentatively or
fully confirm a speaker. Short-turn inheritance does not refresh the genuine
verification timestamp. Hard expiry remains the fail-safe upper bound.

## M5 cluster reconciliation

M5 considers a later fragment only after it has the frozen minimum number of
real identity embeddings. It compares averaged full-gallery score signatures
against older, non-overlapping clusters inside the maximum source-time gap.
The similarity threshold is calibrated from development-calibration speakers
only at the declared false-merge target, frozen, and then applied causally to
the development-selection and held-out cohorts.

A successful merge keeps the older cluster ID and reconciles bounded identity,
roster, anonymous-region, transcript, and revision state. Conflicting known
identities release to Unknown instead of choosing one. Reference truth, future
events, and XVF/spatial signals are not available to the merge decision. The
spatial hook is explicitly inactive and has no result effect in this program.

## Short turns and re-entry

The enhanced mode may inherit a prior label only within the frozen short-turn duration/gap and correction window. Inheritance is rejected when causal evidence contradicts the remembered identity. A generic `Speaker_N` is used while evidence is insufficient. Returning speakers can be reacquired from session state, but the full known gallery remains the safety check.

## Retroactive correction

Corrections are bounded in source time (30 seconds by default) and are emitted as auditable revision events. Older transcript content is immutable. Paragraph reconstruction retains the original words/timestamps and records why a speaker label changed.

## Reset and end-of-session behavior

`reset_session` and `clear_anonymous_memory` clear anonymous clusters, roster, observations, short-turn state, and correction history. The caller chooses whether to keep the readable transcript. Permanent local enrollment profiles are preserved. Normal end-of-session cleanup follows the same anonymous-state rule.

## Long-session acceptance

The 30/60-minute reliability study must demonstrate that every cardinality remains within the frozen limits as source time advances, that expired evidence is reclaimed, that cache/event growth is bounded, and that reset returns volatile counts to zero. Wall-clock acceleration cannot substitute for source-clock expiry evidence.
