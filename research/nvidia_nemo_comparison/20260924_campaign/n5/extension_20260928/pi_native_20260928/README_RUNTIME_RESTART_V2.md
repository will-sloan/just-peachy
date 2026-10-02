# README_RUNTIME_RESTART_V2

Purpose: Continue after restart-v1: normal Close occurred and manager exited0, but the service was still deactivating at the immediate check. This helper requires it now inactive, exact old manager dead and IDLE_CAPTURE_OFF EXIT. It never repeats that Close. It executes TitaNet shortcut, checks one duplicate exclusion, normal Close with bounded read-only service-settle wait, then executes actual autostart command. Both new launches idle/capture off. All ten desktop bytes are pinned. Native150s bound. No coldboot/physical touch claim.

Inputs: existing candidate install, prior closure, previous native inspection, current bounded scope, absent output. Outputs: actual current/closed identities, raw diagnostics, closure and checked state. Backup/independent restore required before use.

PowerShell from this directory:

    & "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B control_runtime_restart_v2.py --help

CMD / Anaconda Prompt after activating the existing environment:

    python -B control_runtime_restart_v2.py --local LOCAL --private PRIVATE --prior-closure PRIOR.json --previous-inspection INSPECTION --candidate-install INSTALL --scope SCOPE.json --output NEW_OUTPUT
