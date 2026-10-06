# Actual speech21 recording export readback

Purpose: verify the complete copy-only recording-export-10 ZIP on the PC after
its actual full closed-unit mirror. Inputs are the pinned current-boot build25
JOB, mirror manifest/completion, native EXPORT and child closure receipts, and
the independently copied selected-recording.zip. No model, recording, native
operation, extraction, content display or source deletion is performed.

The original verify_recording_offload.py digest/central_bound/verify functions
execute with their actual AST unchanged after their full source backup and
independent restore. The old CLI is not invoked; this reviewer registers a full
CPU14 PID/create-time/FILETIME owner before project reads. It checks every mirror
file SHA, native ZIP SHA/extent, natural main and child closure, all ZIP CRCs,
every PC member SHA, exact membership from session/segment/artifact indexes,
contiguous processed/raw sample clocks, and processed replay WAV headers. Native
export supplied a whole-ZIP SHA and artifact extents, not independent original
per-member SHA receipts; this limit remains explicit.

Outputs: fresh private preparation with source/README/original verifier backups
and independent restores, compact proof copies, VERIFY.json, ZIP_MEMBERS.json
and RESULT.json. Budget is 1MiB metadata/600s with existing host storage floors;
the already admitted/copied 54MiB ZIP is read in 64KiB chunks. Source text,
captions, audio and vectors are never printed. The caller checks exact host-owner
absence following natural exit.

PowerShell:
```powershell
$py='C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe'
$s='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/stabilization_20261005'
& $py -B "$s/verify_stabilization_export_v3.py"
```
CMD and Anaconda Prompt: set JP_SOURCE to the same source directory.
```cmd
"C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B "%JP_SOURCE%/verify_stabilization_export_v3.py"
```

The ZIP session.json is deliberately reserialized by the native export. Its hash
must not be substituted for the original recordings/sessions/UUID/session.json
raw-byte hash. That source hash needs a separately bounded native read-only
observation before matched saved replay; this reviewer records it as pending.
This is functional/private copy validation, not transcript or diarization accuracy.

V2 corrects only the actual exported session metadata key from id to session_id.
The V1 review failed at that draft assertion after ZIP/mirror verification; it is
preserved with exact coordinator closure and does not imply an export failure.

V3 matches the actual artifact index schema (path, role, bytes); the selected
session is bound by the immutable native export and exact UUID member prefix.
No source session_id field is invented for an index that deliberately omits it.
V2 failed only this draft assertion and remains immutable with exact host closure.
