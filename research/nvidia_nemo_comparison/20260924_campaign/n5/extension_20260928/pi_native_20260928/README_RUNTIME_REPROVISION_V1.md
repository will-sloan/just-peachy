# Refresh an offline runtime batch from the PC

Purpose: explicitly provision a fresh immutable batch using the existing qualified ten-profile runtime and local model assets. The old batch, recordings, source files, policies and backups remain unchanged. The same one frontend and model implementations are reused. This supports this prepared CM5 and its existing verified dependencies; it is not an SD image for arbitrary machines.

Inputs: existing installed batch and its COMPLETE_CLOSED_RUNTIME_BATCH_PC_COPY directory; full prior-owner binding; prepared installation inputs and independently restored assets; a fresh <=600second host scope; current read-only inspection; new version23..9999 higher than the previous version; new private outputs. Outputs: verified full previous file/hash/owner binding, fresh native census, new measured complete independent allocation, new code/active-file backup and restore, native install/closure, profile shortcuts and an idle manager. No automatic recording/download/enrollment/deletion.

1. Stop/Save/Return/Close any recording and wait for its local backup.
2. Run preserve_runtime_batch_v1.py using README_RUNTIME_BATCH_PRESERVATION_V1.md. It normally closes the manager, copies every complete original and independent local backup, then restores the baseline.
3. Run the read-only inspection below with the preserved batch and latest utility receipt.
4. Run provisioning with that new inspection and a never-used version. New broker IDs10000+4*version through +3 are independently reserved and rejected if already present. Failed roots are never retried.
5. Open a new versioned profile shortcut. It starts idle. Four recording slots/16 total launch slots/24h per idle manager launch,120s microphone or Chunk52,30s saved Streaming remain enforced. Renewal is explicit and requires the PC and enough newly measured storage; it does not reclaim deleted/failed/small/unused allocations.

PowerShell from the source directory:
    & "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B inspect_runtime_reprovision_v1.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection LAST_RECEIPT --previous-install OLD_INSTALL --previous-preservation COMPLETE_BACKUP --scope FRESH_SCOPE.json --output NEW_INSPECTION
    & "C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe" -B provision_field_runtime_v1.py --local LOCAL --private PRIVATE --assets ASSET_RESTORE --prior-closure PRIOR.json --inspection NEW_INSPECTION --inputs PREPARED_INPUTS --scope FRESH_SCOPE.json --output NEW_INSTALL --version 23 --previous-install OLD_INSTALL --previous-preservation COMPLETE_BACKUP

Command Prompt / Anaconda Prompt:
    python -B inspect_runtime_reprovision_v1.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection LAST_RECEIPT --previous-install OLD_INSTALL --previous-preservation COMPLETE_BACKUP --scope FRESH_SCOPE.json --output NEW_INSPECTION
    python -B provision_field_runtime_v1.py --local LOCAL --private PRIVATE --assets ASSET_RESTORE --prior-closure PRIOR.json --inspection NEW_INSPECTION --inputs PREPARED_INPUTS --scope FRESH_SCOPE.json --output NEW_INSTALL --version 23 --previous-install OLD_INSTALL --previous-preservation COMPLETE_BACKUP

Replace all uppercase values with absolute existing verified paths and use fresh output names. Use the operator wrapper supplied with the final package to create its finite scope; do not edit a consumed admission. The helper field_runtime_reprovision_v1.previous is an API, not a CLI: it re-hashes EVERY preserved file/membership and binds policy/actual nested owners. Inputs are the installation, preservation and budget guard; output is the verified previous policy/identity chain.

All CPU/RAM/device/free-space/per-file/cardinality/deadline guards remain. Full raw runtime2988319424B plus unchanged external install reserves=3307886087B. Every operator invocation independently measures existing target+PC usage and reserves new copies; original WINDOW files are unchanged. Prior identity caps remain16 genuinely new continuation utilities/1024 prior identities. If a guard rejects, preserve its output and report the specific failure rather than clearing evidence.
