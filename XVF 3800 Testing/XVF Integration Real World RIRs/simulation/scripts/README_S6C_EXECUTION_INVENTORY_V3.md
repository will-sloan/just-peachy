# S6C execution inventory v3 adapter

`s6c_execution_inventory_v3.py` adds exact epoch4 long-native lineage and strict finite owner handling to the preserved, reviewed `s6c_execution_inventory.py`. It never edits that collector, snapshot_v2, native results, or prepared sources. It performs no model calls and never reads audio, vectors, model payloads, prediction payloads or full event logs. Use this adapter for a later inventory after actual long evidence exists; the development checks do not run a full inventory scan.

The original collector still executes receipt/session deduplication, separate index-reference and projection counts, per-worker cumulative model-load maxima, null measurements, byte metadata and active/unverified closure rules. This adapter temporarily replaces only its auxiliary lineage collector, owner-inspection function and native-owner validation. Their original function identities are restored afterward. Every snapshot binds both executors and their maintained READMEs; `INVENTORY_ADAPTER_RECEIPT.json` points to the underlying inventory, which retains its own active/unverified status.

## Inputs and validation

The original collector and README are pinned to the exact reviewed source hashes. The new long-wrapper manifest, admission, native outcome, closure, epoch4 spec, source composition and gallery mapping are consumed through the original exact-buffer `MetadataReader`. Their parsed bytes are preserved in the new snapshot's metadata resolver. The reviewed long-wrapper source/README hashes are explicitly admitted; this is a metadata audit of declared execution authority, not a repeated rehash of native payloads.

A matching `long_native_epoch4/<namespace>/invocations/<id>/ADMISSION.json` must identify exactly the native owner PID/creation, profile/route, fixed gallery/tier, original source composition, namespace, and pinned epoch4 execution manifest. The prepared manifest digest must be correct. Completed native rows also require an exact outer closure and unchanged native `RESULT.json` binding. A successful release claim requires the archived lease to bind the same owner, manifest and admission. Source **composition epoch2** and actual **execution epoch4** are separate fields; the original native RESULT is never rewritten.

An outer completed claim independently requires the real native schema, `COMPLETE` status, exact source duration, gallery row/index and a `NATIVE_COMPLETE_RELEASE_PENDING` outcome before successful release. This applies even when no matching native STARTED has yet entered the collector's observation interval. The earlier helper/README and initial 38-check receipt are preserved; the later check receipt binds the exact pre-repair source snapshots and the added negatives. No actual scan or native evidence was rerun to repair this prospective guard.

An admission before native STARTED is an owner observation, not a model session. A valid active STARTED can be assigned epoch4 before completion. Missing, duplicate, mismatched or unsuccessful outer lineage stays explicit, sets an issue and prevents closure certification. Unwrapped original native results keep their original interpretation. Nonpositive, boolean, missing or nonfinite process identities do not become evidence of closure; native receipt admission rejects invalid physical owners, and owner inspection keeps unavailable status as null. Invalid nonfinite authoritative metadata may fail collection instead of yielding a completed snapshot.

## PowerShell

```powershell
$s6cRepo = 'C:\Users\amiri\Documents\GitHub\just-peachy'
$s6cSim = Join-Path $s6cRepo 'XVF 3800 Testing\XVF Integration Real World RIRs\simulation'
$s6cPython = Join-Path $s6cRepo '.edge-speech-env\python.exe'
$s6cScript = Join-Path $s6cSim 'scripts\s6c_execution_inventory_v3.py'
& $s6cPython $s6cScript checks
```

After the coordinator authorizes a later metadata snapshot and actual long evidence is available, choose a fresh name. This example is not an instruction to scan during a quiet paced period:

```powershell
& $s6cPython $s6cScript collect --version snapshot_v3_after_long
```

## Anaconda Prompt or Windows CMD

The existing exact native Python is called directly; no installation is required:

```bat
set "S6C_REPO=C:\Users\amiri\Documents\GitHub\just-peachy"
set "S6C_SIM=%S6C_REPO%\XVF 3800 Testing\XVF Integration Real World RIRs\simulation"
set "S6C_PYTHON=%S6C_REPO%\.edge-speech-env\python.exe"
set "S6C_SCRIPT=%S6C_SIM%\scripts\s6c_execution_inventory_v3.py"
"%S6C_PYTHON%" "%S6C_SCRIPT%" checks
```

For an authorized later snapshot:

```bat
"%S6C_PYTHON%" "%S6C_SCRIPT%" collect --version snapshot_v3_after_long
```

## Outputs and limits

Each fresh `REPORT/execution_inventory/<version>` retains the original collector's `EXECUTION_INVENTORY.json`, compact CSV, physical rows, declared artifact metadata, metadata byte snapshots and source snapshots. The `auxiliary.execution_inventory_adapter` section additionally contains source2/execution4 lineage, exact wrapper dependencies, and any unverified lineage. The physical JSON rows contain the expanded fields; the preserved original CSV columns retain their existing schema and show the corrected actual epoch. `INVENTORY_ADAPTER_RECEIPT.json` binds the full result and both code paths without altering it afterward.

The observation interval is not atomic; receipts and indexes may arrive at different times. Missing lineage or receipt references cannot be silently counted as complete, failed, or zero. One native execution is counted by the original physical identity/session rules, never by adding wrapper admissions or duplicate index references. This inventory provides source-bound execution accounting, not speech accuracy, HIL continuity, source-paced timing acceptance, whole-study completion, or CM5 validation. The model-free checks use small constructed metadata only and make no empirical long-session claim.
