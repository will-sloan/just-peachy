# One-hour continuous full-application saved replay

`launch_full_app_soak_action.py` prepares one explicitly admitted headless application job through the SHA-pinned shared qualification dispatcher. It exercises ASR, punctuation, selected primary diarizer, embedding, caption/storage and finalization continuously. It is distinct from `launch_soak_action.py`, which measures one diarization component only.

This source is prepared for the next frozen candidate. It does not run during authoring or tests. It requires a new reviewed native admission, real idle-owner/resource baseline, an admitted immutable candidate and the dedicated host reservation branch. Do not substitute a component soak receipt or claim synthetic checks as native qualification.

## Required input payload

Use a fresh `full-app-hour-NN` label and the exact selected package target/manifest. Required fields:

```json
{
  "schema":"just-peachy.full-app-hour-admission.v1",
  "reviewed":true,
  "reviewer":"<explicit reviewer>",
  "boot_id":"<fresh actual native boot>",
  "expires_unix":"<number: fresh dispatch admission within600s>",
  "package":"<immutable field-runtime-v29-build-NN native path>",
  "package_manifest_sha256":"<exact frozen manifest SHA256>",
  "label":"full-app-hour-01",
  "workflow":"continuous-full-application-repeated-wav",
  "input":"<exact existing native mono PCM16 16kHz WAV path>",
  "input_sha256":"<exact retained input SHA256>",
  "repeat_input_seconds":3600,
  "runtime_seconds":4680,
  "maximum_output_bytes":2306682336,
  "independent_pc_copy_bytes":2306682336,
  "selection":"<complete exact RuntimeSelection dictionary>",
  "policy":{
    "maximum_session_seconds":3600,"developer_soak":true,
    "max_drain_seconds":600,"max_backlog_seconds":120,
    "model_load_seconds":120,"cleanup_seconds":60
  }
}
```

Replace placeholder strings, including `expires_unix`, with actual typed values. Selection is a dictionary, not a string. The first intended selection is saved input, Nemotron `current_delayed`, ReDimNet, continuous embedding and retained attribution, with optional refiner/provisional correction false. Export all exact selection fields from the frozen profile API. An explicit experimental profile may be selected only under its normal separate rules and asset pins. This action refuses the optional parallel refiner: its first combined qualification is a different reviewed workflow.

The default StoragePolicy derives **2,306,682,336 bytes**:1,311,583,712 bytes of conservative audio/session metadata allocation plus995,098,624 bytes of additional metadata/SQLite duplicate headroom and32MiB of bounded job/whole-unit instrumentation. Any custom StoragePolicy must be recomputed exactly through `budget_plan`; the supplied payload must equal the result. The hard ceiling is3GiB, not an automatic allocation. Native free space must exceed the complete allocation plus5GiB. PC C:/50GiB and G:/75GiB floors remain, with complete independent output copy reservation before SSH; the monitor additionally checks twice the job allocation plus8MiB of headroom. No session metadata total or process AS limit is increased.

## Lifetime and evidence

One SessionPolicy permits3600s source +120s model loading +600s drain +60s cleanup. The service adds300s finite startup/launcher/receipt reserve:4680s RuntimeMaxSec,30s TimeoutStopSec, KillMode=control-group. JOB deadline adds at most15s registration slack, therefore<=4725s. Shared CPU2,3, quota200% and TasksMax64 are checked against actual systemd properties. Each model worker remains at768MiB AS; the dispatch/read-only helper remains128MiB. Retained allocator settings and192MiB available-RAM stop floor remain active.

The wrapper records actual owner before project imports, pins package source, takes the research lease, verifies actual unit/invocation/cgroup, publishes UNIT_OWNERSHIP, and launches the ordinary Manager/worker with `--developer-soak --repeat-input-seconds 3600`. Capture stays off. Repetition never restarts model state. The input file is<=32MiB and SHA-pinned before launch; worker/source recheck it.

Outputs include `ADMISSION.json`, `OWNER.json`, `UNIT_OWNERSHIP.json`, `JOB.json`, `JOB_EXIT.json`, bounded logs, complete `data/` recordings/captions/events and the final external scheduler archives. `WHOLE_UNIT_MEMORY.jsonl` samples actual cgroup owners at most1Hz with RSS/PSS/VM/VMpeak/swap, native MemTotal/MemAvailable, boot/invocation and process-sample completeness. It is capped16MiB with16KiB rows; an incomplete process sample is explicitly marked, never presented as a complete aggregate. Worker health retains backlog and source cursor; SQLite/text/artifact growth is recoverable from closed outputs. Physical closure and full copy completion remain separate from logical/quality success.

## Commands

Host-only focused checks register CPU14/actual owner before imports:

```powershell
& $PY -B "$N/test_hour_replay.py" --output-root "$Q/audit-preparation" --retained-vendor "$VENDOR" --checks test_full_app_admission_exact_budget_and_wrapper
& $PY -B "$N/test_job_monitor.py" --output-root "$Q/audit-preparation"
```

CMD/Anaconda Prompt equivalents:

```bat
"%PY%" -B "%N%\test_hour_replay.py" --output-root "%Q%\audit-preparation" --retained-vendor "%VENDOR%" --checks test_full_app_admission_exact_budget_and_wrapper
"%PY%" -B "%N%\test_job_monitor.py" --output-root "%Q%\audit-preparation"
```

`PY` is `C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe`; `N` is this source directory, `Q` the private `B/live-runtime-20261003`, and `VENDOR` the pinned BASE `vendor/edge_speech_pipeline`. No environment/package installation is needed.

Only after the native baseline/review and host reservation branch are ready:

```powershell
& $PY -B "$N/host_operations.py" --label full-app-hour-launch-01 --action "$N/launch_full_app_soak_action.py" --payload "$Q/FRESH_FULL_APP_ADMISSION.json" --writes
& $PY -B "$N/monitor_native_job.py" --job "$Q/full-app-hour-01-JOB.json" --output "$Q/full-app-hour-01-monitor-01" --copy-deadline-seconds 7200
```

```bat
"%PY%" -B "%N%\host_operations.py" --label full-app-hour-launch-01 --action "%N%\launch_full_app_soak_action.py" --payload "%Q%\FRESH_FULL_APP_ADMISSION.json" --writes
"%PY%" -B "%N%\monitor_native_job.py" --job "%Q%\full-app-hour-01-JOB.json" --output "%Q%\full-app-hour-01-monitor-01" --copy-deadline-seconds 7200
```

Persist dispatch `RESULT.json.action_result` as the exact JOB; do not invent owner/invocation fields. Every output directory is fresh. The mirror supports only the exact `full-app-hour-NN` root/unit pair, explicit3600s repeat workflow and2048-file cap. Catalogs enumerate identities without one multi-gigabyte content hash inside a15s helper. Transfers retain16KiB wire frames, contiguous <=1MiB segments, native segment hashes, independent PC readback, then a full PC file hash and unchanged final source membership/identity/closure. Receipt provenance distinguishes that derived whole-file hash from a source whole-file hash. Copy deadline is finite; failure preserves partial bytes and never certifies a complete mirror.
