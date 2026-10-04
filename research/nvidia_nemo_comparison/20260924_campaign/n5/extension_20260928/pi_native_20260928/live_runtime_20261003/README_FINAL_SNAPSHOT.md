# Streamed final scheduler history

`final_snapshot.py` replaces only the final scheduler snapshot representation in the new candidate's engine adapter. Frozen releases are unchanged. The retained scheduler still owns its original finite (up to4096) latest utterance records; ASR decisions, timestamps, labels, revisions and history fields are unchanged.

The original terminal path copied `list(_utterances.values())`, deep-copied every row, added observed-clock history, serialized that list in the completed event/summary, then took a second snapshot for the revised transcript. A long session could therefore hit the 1MiB logical event ceiling even though presentation state is bounded.

The replacement requires a physically closed, error-free policy worker with accepted=completed, a closed scheduler and empty event heap. It takes shallow shadow dispatcher/scheduler instances under the scheduler's lock, points **only the shadow** at an empty row mapping and invokes the original snapshot methods for metadata. It never changes the original mapping and never copies an all-history list. Each original insertion-ordered row is deep-copied once, annotated by the retained observed-clock method and immediately written to disk. Shadow metadata and source fields are tested against the actual retained implementation.

## Input/output and bounds

`ClosedSchedulerSnapshot(dispatcher, session_directory, shared_disk_budget)` produces terminal `schema_version=just-peachy.scheduler-external.v1`, the original snapshot schema, all original non-row metadata and `utterances_external`. No empty list is presented as complete history. The external reference gives local basename, record count, bytes, SHA256, segment count and pinned index SHA.

`scheduler-utterances.jsonl.000000` etc. contain `{sequence,row}` JSONL. Maximum logical row is1MiB, segment8MiB and row count4096. A single row exceeding the bound fails explicitly. The closing index appears only after full fsync. All row bytes and an8KiB finite receipt allowance draw from the existing shared metadata budget. No new overlapping allocation is introduced.

`iter_rows(directory,reference)` reads one row at a time, checking sequence/count/size and the complete canonical byte digest. **Consume the iterator to EOF before claiming complete validation**; rows before EOF are a provisional prefix. It does not rebuild a giant JSON object. Every original JSON field and list order is recoverable, including signed zero; original whitespace/key order are not a semantic promise.

The latest labelled transcript is similarly an external ordered archive. It retains the pinned final-row filter, punctuation replacement only on exact raw-text equality, and original transcript row schema. Its reference is `telemetry.latest_labelled_transcript_external`. The final summary retains original summary fields but claims its finite <=1MiB bytes from the same shared budget before publication.

This removes the extra full-history copies and giant terminal-event payload. It does **not** remove upstream scheduler4096-row/event-ID bounds, or claim constant memory for the native models or the retained original history. Failed/partial archives remain available as evidence but are never marked complete.

## Run and verify

The module is imported by `installed_engine.py`; it is not a standalone native command. The only host entrypoint needed is `test_hour_replay.py`, which registers CPU14/actual owner before project reads. Inputs are source path, private output root and the pinned retained vendor directory. Outputs include exact round-trip and4096-row synthetic archives plus `TEST_RESULT.json`.

PowerShell:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$N/test_hour_replay.py" --output-root "$Q" --retained-vendor "$VENDOR" --checks test_actual_retained_snapshot_exact_order_fields_and_revised test_full_history_never_copied_by_original_snapshot test_closed_guard_corruption_and_budget_failure
```

CMD and Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\test_hour_replay.py" --output-root "%Q%" --retained-vendor "%VENDOR%" --checks test_actual_retained_snapshot_exact_order_fields_and_revised test_full_history_never_copied_by_original_snapshot test_closed_guard_corruption_and_budget_failure
```

These are host contracts, not native qualification. See `README_DEVELOPER_REPLAY.md` for the explicit hour policy and its separate output-reservation requirement.
