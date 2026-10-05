# Full application delivery adapters

Purpose: prepare exact adapters for build21 activation and a selected rich-session
export, retaining the existing inventory, process closure, leases, storage floors,
bounded systemd wrapper and private copy requirements. This does not create a new
runtime or start a campaign. Build17 and all original action sources stay intact.

Run `prepare_delivery_actions.py` from this directory first. Inputs: immutable
original activation/export actions and the exact private build21 package. Outputs:
two adapter source files, private exact backups, independent restores and an AST
review. Only activation and export dispatch functions change; the native export
worker is the exact hash-pinned build21 worker, including its rich artifacts.

PowerShell:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\prepare_delivery_actions.py
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' .\host_full_operations_v6.py --label UNIQUE-LABEL --action .\activate_full_desktop_action_v1.py --payload 'ABSOLUTE-PAYLOAD.json' --writes
```

CMD / Anaconda Prompt:

```bat
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" prepare_delivery_actions.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" host_full_operations_v6.py --label UNIQUE-LABEL --action activate_full_desktop_action_v1.py --payload "ABSOLUTE-PAYLOAD.json" --writes
```

Activation inputs: exact build21 manifest, independently finalized PASS proof and
hash, current boot, preserved data root, disabled-autostart hash, and the sole
observed Just Peachy shortcut hash. It creates verified before/restore copies
before atomically replacing that one shortcut. It launches no app. Rollback uses
the saved build17 desktop bytes; other shortcuts and personal data are untouched.

For export, use the same host command with
`launch_full_recording_export_action_v1.py`. Inputs: current boot/expiry, exact
package/manifest, closed `classic-ui-check-NN` job, its kept session ID, the
preserved runtime-v29 recordings directory, fresh `recording-export-NN` label and
finite independent Pi/PC allocation. The source session must have a native PASS
closure proof. Output: bounded export job containing `selected-recording.zip`,
native encoder-free export receipts and exact child closure. Finish with the
existing `monitor_native_job.py` on its JOB JSON and a fresh private output path;
this copies the whole closed export directory to the PC and verifies hashes.
Copy is the default; source recordings are not deleted. These are guarded APIs,
not commands to reuse consumed labels, expired payloads or historical proofs.

Selected export adapter v1 rejected build21's newer member-guard shape before
export launch. Its partial metadata tree and raw failure stay preserved. Run
`prepare_delivery_export_v2.py` using the same PowerShell or CMD/Anaconda Python
invocation as the first preparer; use `launch_full_recording_export_action_v2.py`
with a fresh export label. It changes only the publication-peer adapter to
recognize the exact final ZIP and its one UUID temporary name. The existing
regular-file, exact inode/two-link, path, file-count, deadline and byte guards
remain. Both visible transaction names are conservatively charged. Inputs and
outputs remain the same; no source recording or runtime module changes.
