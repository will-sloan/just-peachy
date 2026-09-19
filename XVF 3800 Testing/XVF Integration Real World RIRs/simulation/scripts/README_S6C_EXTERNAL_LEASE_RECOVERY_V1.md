# Exact external historical lease recovery V1

Purpose: externally archive the exact preserved C: quiet lease from controls_fast_v1 after its original 80 cells completed and all recorded owners closed. The original coordinator failed when Path.rename tried to move that lease from C: to its G: invocation. This helper does not rerun any native work, delete a stale lock, fabricate an original success record, or change original files.

This source is prospective. No real recovery or root authority is created by the fixture command. Root must independently approve the exact helper, README, audit and future recovery namespace after review.

## Exact inputs and authorization

The helper is intentionally limited to this one event: root audit runtime_failure_review/CONTROLS_FAST_V1_ARCHIVE_FAILURE_OWNER_AUDIT_V1.json SHA74a60af5483852cae05ac156c7c251a4890b684d737e080b22be01080c2ea914, original258-byte lease SHA9dfcfa166cecad8b4edfaf1b64f867f3485de18c8d7a8cf7c9cb8e6563ca44f3, and failed historical observer SHA99cb60a62e8bdbfc2b2e9666fa368604395b4f3e0837cf56e20535efa7614591. The Python OSError records errno18; Windows reported WinError17. It pins the full reviewed canonical Lfast_v2 source SHA079642ba24d59f625a6ae0c4342d9a26f51e56221f29b5a50f54830adfa22d67 and extracts only the unchanged release_lease function AST. That module is never imported or executed.

CLI takes --authority ABSOLUTE_JSON SHA256. Root's new authority must contain schema s6c-external-historical-lease-release-authority.v1, status AUTHORIZED_EXACT_EXTERNAL_LEASE_ARCHIVE, exact path/bytes/sha256 bindings for helper, readme and root_audit, a fresh simple namespace, and aware expires_utc no later than2026-09-13T11:35:40Z. This description is not an authorization. The helper refuses changed audit/source/lease or already existing recovery output.

Actual recovery reads only compact metadata: the exact audit, original manifest/LAUNCH/COMPLETION/quiet admission/failed dispatcher/failed scanner and80 bound COMPLETE JSONs. It checks the complete unique grid, original job keys and exact recorded owner lists. No referenced PCM, model, events, trajectory, native outputs or scientific table is reopened. All160 recorded child observations and both coordinator/dispatcher identities are freshly queried by PID+creation immediately before archival. Live, unknown or access-denied ownership retains the lease. It does not perform a global process census; authority concerns the exact recorded owner chain.

## Release and outputs

Only after those checks, recovery creates REPORT/runtime_failure_review/external_lease_recovery/NAMESPACE on C:. The archive is PRESERVED_ORIGINAL_QUIET_LEASE.json inside that fresh directory. Both resolved drive and actual filesystem device must match the source lease. The exact reviewed release_lease rechecks source bytes and performs a same-volume rename, then verifies archive bytes. There is no cross-volume copy or deletion. Existing archive targets are refused.

ADMISSION.json records root authority, exact original evidence, source pins and current owner observations. RESULT.json records EXTERNAL_ARCHIVE_RELEASED only when the exact source bytes are verified in the C: archive. Failed or unverified rename gets EXTERNAL_ARCHIVE_FAILED_OR_UNVERIFIED and raises; all evidence remains. A pre-mutation admission failure can leave ADMISSION without RESULT while retaining the lease; that namespace must be reviewed rather than reused. A result-publication failure after rename also requires manual root inspection; no automatic retry exists.

The original G: QUIET_OWNER_CLOSED.json remains absent. Original coordinator exit1, failed SCANNER_OUTCOME, failed dispatcher RESULT and all original source/manifests/cells remain unchanged. Recovery's own PID/creation/argv is recorded; root must observe recovery process exit before subsequent work. External archival establishes only the separately recorded lease resolution. It does not make original observer status COMPLETE or establish scientific acceptance.

## Inventory and post-analysis

Held V7 rejects missing original historical archive and failed historical SCANNER_OUTCOME, even if native cells are complete. Unmodified V7 must continue to do so. An explicit separate recovery adapter must bind this result plus the original failed records, current closed owners and exact80-cell audit, and label external closure separately. Do not manufacture a G-side archive or project FAILED into original COMPLETE. Source-only diagnosis confirms future paced B36fast_v1 has the same C-to-G rename path; B36 continuous uses a C: REPORT invocation with reviewed release_lease and has no identical cross-volume path. A prospective paced B36 fix requires a separately named/admitted wrapper and manifests plus explicit metadata/analysis recognition; no held helper changes are authorized silently.

## Tests and commands

test_s6c_external_lease_recovery_v1.py shares this README. Inputs: current helper, this README, exact reviewed L source and a new output directory. Output: a source-bound SOURCE_CHECKS.json. Fixtures use private temporary JSONs and mocked owner states only. They test original80-grid/owner/failure guards, exact release AST, same-volume byte archival, archive collisions, changed lease bytes, simulated rename failure and device mismatch. No real lease, audit, native session or process is accessed by the test.

PowerShell (existing EDGE interpreter; no environment changes):

```powershell
Set-Location 'C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts'
$edgePy = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $edgePy -B test_s6c_external_lease_recovery_v1.py --output '..\reports\S6C\20260910T123540Z\runtime_failure_review\recovery_source_checks_NEW'
# Only after exact independent review and root authority:
& $edgePy -B s6c_external_lease_recovery_v1.py recover --authority 'ABSOLUTE_ROOT_AUTHORITY.json' EXACT_AUTHORITY_SHA
```

Anaconda Prompt / CMD (no activation or installation required):

```bat
cd /d "C:\Users\amiri\Documents\GitHub\just-peachy\XVF 3800 Testing\XVF Integration Real World RIRs\simulation\scripts"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B test_s6c_external_lease_recovery_v1.py --output "..\reports\S6C\20260910T123540Z\runtime_failure_review\recovery_source_checks_NEW"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B s6c_external_lease_recovery_v1.py recover --authority "ABSOLUTE_ROOT_AUTHORITY.json" EXACT_AUTHORITY_SHA
```

