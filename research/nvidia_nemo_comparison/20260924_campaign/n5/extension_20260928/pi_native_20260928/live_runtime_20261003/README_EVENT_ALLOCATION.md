# Complete bounded event retention

`installed_engine.py` gives every event, transcript, clock, final-history and optional caption-attribution writer access to one shared `DiskBudget`. Build07 used five sixths of the session's already reserved metadata bytes. New build08 sessions explicitly select `metadata_split=text3_sqlite1_v1`: three quarters shared text and one quarter SQLite plus its existing base allowance. The global total is unchanged and old stored-session ledger limits remain unchanged. `SegmentedText` keeps the existing1MiB logical-record,4MiB pending-byte,512-item queue and8MiB segment ceilings. It preserves each accepted UTF-8 record exactly once. No probability field is removed or rounded, and no failed output is deleted.

The actual build06 45-second saved trial reserved 28,573,696 metadata bytes. Its event writer stopped after 4,745,541 bytes because the former one-sixth partition was 4,762,282 bytes. Accepted and completed counts matched. The largest persisted record was 393,200 bytes. This was a per-writer disk allocation failure, not evidence that the logical-record bound or physical RAM was exhausted. The aggregate writer reservation is unchanged at 23,811,413 bytes.

The corrected index and metrics report which bound refused a record and the incoming byte count. An aggregate refusal does not advance the refused writer's accepted cursor or the shared budget. Previously accepted bytes remain drainable and recoverable in numbered segments, in order. Index `complete` remains false on any refusal.

## Run the focused host checks

Inputs: the runtime sources and a fresh private evidence parent. The test executable pins CPU14 and durably records its actual numeric process identity before importing runtime code. It uses synthetic probability rows, two auxiliary writers, exact decoded-field/hash comparisons, a crossed former per-writer limit, aggregate exhaustion, and an oversized record. It performs no native, model, hardware, SSH or systemd work.

PowerShell:

```powershell
$N='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003'
$Q='G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/live-runtime-20261003/audit-preparation'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$N/test_native_scope.py" --output-root $Q --checks test_event_shared_allocation_preserves_large_probability_records test_event_aggregate_exhaustion_is_explicit_and_cursor_stays test_event_logical_record_bound_remains_finite
```

Command Prompt or Anaconda Prompt, with the same directories:

```bat
set "N=G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\live_runtime_20261003"
set "Q=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\live-runtime-20261003\audit-preparation"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B "%N%\test_native_scope.py" --output-root "%Q%" --checks test_event_shared_allocation_preserves_large_probability_records test_event_aggregate_exhaustion_is_explicit_and_cursor_stays test_event_logical_record_bound_remains_finite
```

Outputs: a fresh `native-scope-checks-*` folder, `REGISTERED_OWNER.json`, synthetic numbered event segments and indexes, and `TEST_RESULT.json`. The command prints its evidence path and pass/fail counts.

## Duration reservation limits

The metadata formula remains `16 MiB + maximum_session_seconds * 256 KiB`. New-session08 shared text is71,565,312 bytes at300seconds and720,371,712 bytes at3600seconds; SQLite is24,903,680 and241,172,480 respectively with its1MiB base allowance. Absent an explicit split, legacy specs retain5/6 text and1/6 SQLite, including the immutable07 package and already-created ledger rows. These are hard allocations, not evidence of long-duration sufficiency.

Actual closed07 combined saved trial `pipeline-qualification-04` retained715,127 samples/44.6954375seconds. All3,550 event records closed completely; events occupied4,481,399 physical bytes from7,223,429 logical bytes. All work/text files totaled4,689,467 bytes. SQLite occupied188,416 physical bytes and393,252 conservative ledger bytes. The private verified review is `Q/audit-preparation/pipeline-allocation-review-5d6a078ff14d4f4085f6dd0868096878/REVIEW.json`; it binds the complete mirror manifest and recovers every compact event. Linear projections are377.71MB/hour text and31.67MB/hour SQLite. Combining that SQLite projection with the prior actual raw05 source-only150.87MB/hour projection gives182.55MB/hour, above the former161.13MB allowance but below the new241.17MB allowance. This conservative addition includes short-run fixed overhead and is **a projection, not a measured hour pass**. The new720.37MB text allocation also exceeds the measured short-run text projection, without increasing the total.

In the failed build06 trace,77 repeated `s6d_display` snapshots contributed2,848,958 bytes; build07 lossless display compaction fixed redundant disk growth without dropping fields. Retained display rows are individually bounded, while final scheduler history contains up to4096 rows. Build08 externalizes terminal scheduler rows as described in `README_FINAL_SNAPSHOT.md`, retaining every field/order without a giant terminal event. Actual300second/hour full-application growth, raw variability and optional-refiner output still require their own bounded measurement; the component-only Nemotron soak cannot qualify those paths.
