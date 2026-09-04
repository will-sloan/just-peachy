# H2 product modes

All three modes use the same Sherpa + Pyannote + ReDimNet2 H2 architecture and the same frozen open-set identity policy. They differ only in user-visible unknown-speaker behavior and bounded session memory.

| Mode | Unmatched voice | Anonymous continuity | Confirmed-name memory | Short-turn inheritance | Active roster |
|---|---|---:|---:|---:|---:|
| `H2_KNOWN_ONLY` | `Unknown` | No | Yes, subject to the frozen identity state machine | No | No |
| `H2_SESSION_ANONYMOUS` | session-local `Speaker_N` | Yes | No | No | No |
| `H2_SESSION_MEMORY_ENHANCED` | session-local `Speaker_N` | Yes | Yes | Yes, bounded and contradiction-checked | Yes |

## H2_KNOWN_ONLY

Use this when the product should name enrolled people and otherwise display only `Unknown`. Unmatched evidence is retained for at most the declared short buffer (3 seconds by default) and is not used to create a persistent anonymous profile. Anonymous continuity metrics are not applicable.

This is the simplest public behavior, but repeated unknown speakers cannot keep a stable session-local label.

## H2_SESSION_ANONYMOUS

Use this when the transcript should distinguish recurring unenrolled speakers without guessing a real name. Internal `Unknown_N` identifiers are displayed as `Speaker_N`. Profiles exist only in the current session and are cleared on reset/end.

This mode tests the value and resource cost of anonymous continuity separately from known-name memory.

## H2_SESSION_MEMORY_ENHANCED

This is the intended primary user-experience candidate. It adds a bounded active roster, confirmed-name memory, warm reacquisition, short-turn inheritance, expiry/decay, contradiction accounting, cluster reconciliation, and bounded retroactive label correction.

Memory does not bypass the open-set score/margin/evidence gates for a new identity and does not narrow the enrolled gallery. A stale name must release or require reconfirmation according to the frozen causal policy.

## Labels and confidence

User view shows a simple generic/anonymous label and tentative/confirmed state. It never converts a raw cosine score into a misleading confidence percentage. Research view may show the raw score, Top-1/Top-2 margin, evidence duration, quality gate, threshold, cluster, and event provenance. A value is called confidence only if it has been explicitly calibrated as such.

## Lifecycle and privacy

- Permanent enrollment profiles are local and survive ordinary session reset.
- Anonymous profiles, active roster, causal history, and unmatched buffers are volatile.
- `reset_session(preserve_transcript=...)` and `clear_anonymous_memory(preserve_transcript=...)` never delete permanent enrollment profiles.
- A new session starts with no anonymous-memory carry-over.

The final default mode is selected only from development and untouched held-out evidence; this document does not predeclare that result.

