# Approved final documentation and handoff

Purpose: reconcile all current operator/acceptance/hardware/checklist entry points
after the user-approved source push, and refresh the small ChatGPT handoff.
`finalize_motion_docs.py` reads existing v27 evidence and never contacts the Pi,
starts capture/models or repeats a healthy runtime check. Old status/receipts and
handoff ZIPs remain historical; only current guides are reconciled.

Inputs: the exact approved/verified source commit ed27d04b, current completion
guides, retained v27 review and the verified publication-v2 ZIP. Outputs: current
documents, MOTION_REMOTE, updated MOTION_HANDOFF_RECEIPT, and private
`imu-integration-20261002/approved-final-docs-v1` with independent before/after
backups, ZIP and expanded readback. The field-run template gains blank motion
observation fields; these are not new measured results.

PowerShell, from this source directory:

```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./finalize_motion_docs.py
```

CMD or activated Anaconda Prompt in the existing project environment:

```bat
python -B finalize_motion_docs.py
```

The helper pins CPU14 before project reads, registers its owner and enforces
600seconds/16MiB cumulative writes plus host free-space floors. Each old guide is
backed up and independently restored before edits. Output labels are one-use;
never rerun a closed or failed label. Git whitelist review, commit and remote
verification happen separately afterward; their receipt avoids a circular
self-hash in the committed documentation/archive. No private media/models enter
Git or the handoff. Earlier deadline receipts are preserved as historical authority.
