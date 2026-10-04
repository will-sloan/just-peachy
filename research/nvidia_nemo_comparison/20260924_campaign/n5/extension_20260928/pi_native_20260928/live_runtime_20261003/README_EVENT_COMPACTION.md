# Lossless bounded event compaction

`event_compaction.py` is the `events.jsonl` adapter selected by `installed_engine.py`. It keeps one previous `s6d_display` payload and stores smaller structural changes when possible. The replacement, deletion, ordered append and truncation semantics follow the retained v28 `app/bounded_live_artifacts_v1.py` design. New full-record sequence numbers, base identities and SHA256 checks make missing, reordered, altered or cross-session patches fail explicitly.

Every event field, including every ordered native probability and floating-point value, is recovered. Signed zero is preserved. Non-display events are complete literal values in the wrapper; only display payloads use patches. Original JSON whitespace/key order is not retained, but canonical full-event bytes match after recovery. The native speech model, observer events, UI caption flow and SQLite caption API are unchanged by this adapter.

Inputs are complete JSON event strings from the existing journal consumer. Outputs remain bounded numbered `events.jsonl.NNNNNN` segments, the ordinary physical index, and `events.jsonl.compaction.json`. The compaction receipt contains full logical-record count/digest, patch count, physical writer result, and maximum cached payload bytes. The existing worker and launcher commands in `README.md` run this adapter automatically for a freshly built release; do not replace files inside an immutable staged release.

## Fixed bounds and recovery

The original logical-event cap and stored wrapper cap are each 1 MiB. The one retained payload is at most that size; there is no history list or cache per speaker/session. Patch complexity is at most4096 operations and24 levels, with a whole-event fallback inside the same record cap. Crossing a session identity writes a full event. A failed admission never advances the codec's accepted sequence or digest.

The physical queue retains the existing4MiB/512-item bound and8MiB segments. Compaction runs on the existing event consumer, before enqueueing bounded physical bytes. All writers share the same five-sixths metadata allocation. A4096-byte receipt reserve is claimed from that allocation at construction. No source sample, probability, caption field or prior segment is silently discarded. The remaining one sixth and the store's separate allowance cover SQLite and other metadata; this codec does not consume that budget.

Recovery API:

```python
from event_compaction import iter_events
for event in iter_events(event_root / 'events.jsonl',
                         maximum_bytes=80 * 1024**2,
                         maximum_records=100000):
    consume(event)  # Process incrementally; collecting all events defeats the bound.
```

The caller supplies explicit finite byte/record limits and a closed owned event root. Old plain numbered JSONL files are supported. New compact files require their compaction receipt. Default recovery requires complete physical and logical closure, checks every sequence/base/full-event hash, then verifies final logical count/digest and physical byte totals. A consumer must exhaust the iterator before treating the whole stream as verified. `allow_partial=True` permits an explicitly failed prefix, with sequence and per-event validation; it never certifies complete output. The input evidence is read only. No native models are imported by the codec or reader.

## Host checks: PowerShell

```powershell
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$N/test_native_scope.py" --output-root $Q --checks test_compact_display_exact_nested_roundtrip_and_sequence test_compact_display_session_change_and_admission_failure_do_not_alias test_compact_synthetic_hour_has_one_cache_and_complete_timeline
```

## Command Prompt or Anaconda Prompt

No environment activation or installation is needed; use the pinned interpreter:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\test_native_scope.py" --output-root "%Q%" --checks test_compact_display_exact_nested_roundtrip_and_sequence test_compact_display_session_change_and_admission_failure_do_not_alias test_compact_synthetic_hour_has_one_cache_and_complete_timeline
```

The harness pins CPU14 and durably records actual numeric process identity before project imports. Output is a fresh `native-scope-checks-*` folder containing owner/test receipts, synthetic segments and indexes. It performs no SSH, systemd, native models or microphone work.

To round-trip an explicitly selected private prior event file, add `--event-corpus "FULL_PATH_TO_events.jsonl.000000" --checks test_compact_private_closed_corpus_roundtrip`. This reads only that bounded file; it never enumerates or displays audio/transcript text. Its `private-roundtrip/ROUNDTRIP.json` pins source hash/bytes and records exact all-field recovery. The source is hashed again afterwards.

## Actual retained-trace check and limitation

The closed build06 failure trace has2,106 events, including77 display snapshots and one complete393,200-byte native probability event. All fields round-trip exactly. Physical bytes decrease from4,745,541 to2,579,911, with73 display patches and a63,137-byte maximum single-payload cache. Receipt: `audit-preparation/native-scope-checks-c906a3a899884fd58bfd38e215bc13d6/private-roundtrip/ROUNDTRIP.json`. The separate synthetic hour advances source timestamps0..3600, verifies all3,601 records and uses one sub16KiB display cache; it is not a native hour or quality qualification.

Compaction reduces repeated evidence, but does not prove that every possible future300-second/hour-long full pipeline fits its reserved bytes, native CPU time or producer history. A full event above1MiB still fails explicitly. The retained short trace and synthetic roundtrip are not a long-duration pipeline acceptance.
