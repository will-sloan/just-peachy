# Actual native name emission metrics

Purpose: add two separate wall-emission measurements to unchanged S6C core/name scores. This is a pure reporting API for a source-bound paced collector; it never opens models, starts workers, changes prediction timestamps, or rescores words. No empirical paced result is produced by the fixtures.

1. Source-span-attributed decision emission: first any, correct and confirmed-correct name result emitted by a native `speaker_decision`, relative to the unique `source_started` UTC plus the mapped occurrence file-support start. An event qualifies only when its actual source span intersects exactly one complete-reference occurrence and positive sole support. An event processed after the turn can qualify; this is source-attributed processing/decision delay, not phonetic, current-speaker or GUI latency.
2. Retained transcript row: actual emitted partial/final/revision UTC starts or changes that row's state. Only the most recently arrived readable ASR span classifies it. A preset 0.5-second contiguous confirmed-correct interval qualifies at its **attainment time**, not its retrospective onset. Observation ends at the exact successful `session_finalization_v3.finished_utc`, and short remaining row lifetimes are explicitly censored. This is retained-row wall time, not live active-source exposure. No final-span backfill or word timestamps are inferred.

Mixed/repeated-occurrence/incomplete/unmapped spans remain unqualified. Unqualified rows are excluded from eligible never-correct counts. Enrolled, withheld, intended-but-unavailable and no-gallery populations remain separate; an identity absent from the actual gallery cannot attain a correct known name. All occurrences remain in output with separate missing/no-qualified-event statuses. A foreign assigned name remains wrong where truth qualifies. The decision stream has no invented wall-time expiry; original V3 modeled-source freshness stays in its separate existing metric.

An actual empty-string partial/final clears readable text and updates its arrived span, producing `no_readable_text` row time rather than named-word exposure. A revision retains the last actual readable/nonreadable state and arrived span; it cannot resurrect earlier text. Nonstring actual ASR text is rejected. As in unchanged V3 names, ASR arrived-span sample times use the common paired origin and intersect identity-tap mapped activity once. For split routes this deliberately measures identity-attribution support, not ASR word alignment, and never remaps through both taps.

Inputs to `analyze(events, value, support, gallery, q, admission, finalization)`:

- `events`: exact original native event JSONL records in file order, already byte-verified by the caller; includes exactly one source_started and session_completed plus all speaker/identity/transcript emissions.
- `value`: admitted same-native shared-parity prediction, including exact decision IDs in order; `support` and corpus-qualified `q` are the unchanged V3 source mapping inputs.
- `gallery`: exact loaded-gallery/scorer-map row resolved by the existing `gallery_for`; includes intended/available identities and actual profiles. Do not substitute a declared roster without load/source admission.
- `admission`: caller's verified canonical closed source-paced cell metadata: source_kind=CANONICAL_SINGLE_SCENE_PAIR, realtime=true, native_session_complete=true, zero source_offset_samples and inserted_gap_samples, and exact case_id/profile_id/asr_tap/identity_tap. This API does not replace the collector's immutable manifest/worker/PCM/owner checks.
- `finalization`: exact byte-verified successful native finalization JSON, including mandatory finalization_error=null and closed handles/lanes. UTC end must follow session_completed.

Output is a serializable dictionary containing per-occurrence delays/statuses/roster scope, attributed and unqualified decision emissions, native row intervals and exposure partitions, stable attainment records, clock observations and limitations. The caller binds this dictionary to its exact event/support/Q/gallery/prediction/finalization/metadata sources and helper hashes, then writes separate result tables. Repetitions/candidates/clips must never be pooled as independent source cases.

The source UTC marker precedes the producer's first read; source start plus file offset is nominal pacing, not an instrumented physical playback timestamp. Native `compute_finished_elapsed_sec` and modeled availability are retained separately. UTC differences use timezone-aware datetime subtraction, retaining the native microsecond resolution; the stable duration comparison rounds to that resolution rather than losing precision through epoch-sized floating timestamps. Relevant backward UTC timestamps invalidate all wall metrics without sorting/clamping; counts and occurrences remain. The API checks only stated metadata semantics and decision IDs, so downstream immutable source-byte admission remains essential.

Strict-empty scenes additionally retain assigned decision emissions, readable assigned row-emission counts, assigned row counts and assigned-name retained row-seconds. No reference identity or WER is invented. Simultaneously retained rows can overlap, so row-seconds are not session-wall seconds. Empty-text clearing remains excluded from assigned readable exposure.

Run the 30 pure fixtures with no native data/model calls. Use a fresh output filename; publication refuses overwrite. Initial unexecuted versions are preserved under `independent_review/paced_name_emissions_before_text_guard_v1/SOURCE_INDEX.json` and `paced_name_emissions_before_empty_guard_v2/SOURCE_INDEX.json`; the prospective guards change no empirical result.

PowerShell:
```powershell
$sim = 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
Set-Location -LiteralPath $sim
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' scripts/s6c_paced_name_emissions.py --self-test --output reports/S6C/20260910T123540Z/independent_review/PACED_NAME_EMISSION_CHECKS_V3.json
```

Anaconda Prompt / CMD:
```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" scripts\s6c_paced_name_emissions.py --self-test --output reports\S6C\20260910T123540Z\independent_review\PACED_NAME_EMISSION_CHECKS_V3.json
```

To integrate from a reviewed collector, import `s6c_paced_name_emissions` and call `analyze` with the admitted buffers above. There is deliberately no command-line native data admission or automatic directory discovery. The API is initially held for independent review; do not report fixture outputs as empirical naming results.
