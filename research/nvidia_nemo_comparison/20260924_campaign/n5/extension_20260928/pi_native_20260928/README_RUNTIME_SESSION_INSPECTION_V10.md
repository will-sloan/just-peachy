# README_RUNTIME_SESSION_INSPECTION_V10

Purpose: Read-only current or closed manager inspection. Historical operations are bound to actual registered manager launch OWNERs; they need not belong to the latest manager process. Any previous manager still alive is rejected. Same all-owner/capture/lease/config/device/resource checks; no mutation.

Inputs: existing candidate install, prior closure, previous native inspection, current bounded scope, absent output. Outputs: actual current/closed identities, raw diagnostics, closure and checked state. Backup/independent restore required before use.

PowerShell from this directory:

    & "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B inspect_runtime_session_v10.py --help

CMD / Anaconda Prompt after activating the existing environment:

    python -B inspect_runtime_session_v10.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection INSPECTION --candidate-install INSTALL --scope SCOPE.json --output NEW_OUTPUT

V9 additionally reads bounded launch OWNER/EXIT/FAILURE and rollback attempt records plus actual/candidate autostart pins to resolve observed startup restoration. No native write or launch. These are new missing startup facts, not a model rerun.

V10 reads the exact issued candidate prior-owner binding before counting new continuation utilities and includes all raw arecord owners. The16-new-utility/1024-total bounds and all native/read-only guards are retained. Used to diagnose candidate21 pre-capture startup failure.
