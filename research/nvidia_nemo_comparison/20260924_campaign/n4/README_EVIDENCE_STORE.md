# Bounded storage for a new N4 run

`evidence_store.py` is an importable helper for the forthcoming N4 runner. It
creates a fresh private namespace, reserves one attempt at a time, verifies a
completed attempt's lossless ZIP, publishes the archive index, and then releases
only the verified duplicate files in that newly reserved attempt. Original byte
content remains in the ZIP. RESULT.json, CHECKPOINT.json, reservations, archival
intent and completion receipts stay at their original paths. Existing campaign
directories cannot be adopted. There is no historical-evidence cleanup command.

This is implemented storage infrastructure, **not an admitted full-bank runner**.
No real N2/N3 evidence has been removed. No N4 cell or stage acceptance is claimed.
An actual N4 admission still needs measured per-cell peak allowances, an aggregate
remaining campaign allocation, source/cache contracts and runner integration.

## Inputs and outputs

`initialize(fresh_root, max_bytes=..., cell_reserve_bytes=..., minimum_free=...)`
requires an absent directory with an existing parent. `max_bytes` must be the
remaining allocation for this new run, at most 80 GiB; it does not reset the
campaign's aggregate 80-GiB allowance. `cell_reserve_bytes` must cover a measured
worst-case working cell, simultaneous uncompressed/ZIP copies and metadata.
The reserve cannot be derived solely from the earlier one-cell compression ratio.
The admission binds the store, archive, reader, common and supervisor source files.
Windows requires at least C:50 GiB and G:75 GiB free-space floors. Every supplied
reserve path must exist. The helper uses actual filesystem volumes to account
for pending allocations. Outputs are STORE_ADMISSION.json and a fresh directory.

Use `with EvidenceStore(root).writer() as store:` for the entire runner lifetime,
including inference. The OS lock is released on process exit; ownership records
contain exact PID creation identity. A second writer cannot enter. This is a
local storage lock and does not grant the shared numerical/GPU resource lease.
Keep using the existing campaign supervision interfaces for those resources.

`store.reserve(job_id, cache_key)` takes an ASCII-safe ID and a 64-character
lowercase SHA-256 key and returns a new private attempt path. An unresolved
attempt blocks the next reservation; it is never discarded. Before
reserving, the helper checks current store usage plus the declared cell peak and
all disk floors. The caller must also call `store.guard()` during execution and
before large writes, with the next write size when known. These are cooperative
checks, not OS disk quotas; concurrent external disk writes can consume headroom.

The runner must stop/join all cell producers and bind **every regular file** in
the attempt, including binary journals, before writing RESULT.json. A result
must contain its reservation's job ID/cache key/absolute attempt path, COMPLETE
status, and true `stopped`, `no_error`, `all_samples`, `drained`,
`archive_complete`, `workers_closed` checks. The adjacent parent CHECKPOINT.json
must bind that result, cache key and COMPLETE status. The helper cannot itself
prove a producer was joined; the runner must supply actual closure evidence.

For a failed cell with verified closed workers, `store.retain_failed(result_path)`
requires FAILED result/checkpoint status and an exact complete file inventory.
It writes FAILED_EVIDENCE_RETAINED, removes nothing, and allows the next cell.
All failed bytes still count against the allocation. The runner must count this
cell in its failed denominator. Unclosed workers block continuation.

`store.compact(result_path)` checks those bindings and all files, then reserves a
conservative uncompressed-size-based ZIP allowance. It creates a content-addressed
ZIP using the existing archival helper, rehashes every archived byte and checks
all members through ControllerEvidence. It flushes the ZIP, seals STORE_INTENT,
and atomically publishes ARCHIVE_INDEX.json **before** releasing any originals.
The final STORE_COMPLETE receipt gives exact released byte/file counts and zero
new execution credit. Use ARCHIVE_INDEX.json with `score_controller.py
--archive-index`; see README_EVIDENCE.md and README_SCORING.md.

Call `compact` again after an interrupted removal. It verifies the original
result, checkpoint, reservation, intent and complete archive before accepting
already-missing copies. Remaining copies must still match. Corruption stops the
operation with remaining files intact. A crash before the intent is written is
recoverable only with every source present and a valid complete ZIP. Truncated
ZIP/JSON artifacts are preserved for explicit review, never silently replaced.
File flushes and atomic index replacement provide process-interruption recovery;
this is not a guarantee against filesystem corruption or hardware power loss.

Paths are checked against the admitted root and for symlinks, Windows junctions,
reparse points and hard links before resolution/removal. Only individual bound
files are unlinked. No recursive directory removal or existing-store adoption is
available. Keep the entire store private: its contents may include transcripts,
saved audio and research vectors. Never add it to Git or a public handoff.

## Run the checks

`test_evidence_store.py` creates and removes only its own temporary fixtures. It
tests exact binary/JSON round-trip, index compatibility, retained result and
checkpoint bindings, next-cell admission, interrupted removal/recovery,
corrupt archive and changed source refusal, unbound/missing evidence,
historical/outside-root refusal, single-writer locking, disk/allocation floors,
worker closure, failed-cell retention/budget accounting, late unbound writes,
path traversal and hard-link refusal. It opens no device and
loads no model. The existing archival helper pins compression to CPU4/BelowNormal;
the store restores the caller's exact CPU affinity and priority afterward (also
checked by the round-trip test). Run compression outside candidate resource/paced
measurements; its CPU work and byte counts remain separate storage overhead.

PowerShell, from the campaign worktree:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n4 -p test_evidence_store.py -v
```

CMD/Anaconda Prompt (no activation needed):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B -m unittest discover -s research/nvidia_nemo_comparison/20260924_campaign/n4 -p test_evidence_store.py -v
```

No production invocation is supplied yet: the helper is not connected to an
accepted N4 runner/admission. That integration must retain failed attempts,
call budget guards during writes, and execute archive-aware scoring before a
full-bank run can be admitted. Prior compression/reader receipts remain unchanged.
