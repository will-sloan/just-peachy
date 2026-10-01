# Concrete live admission and outer envelopes

Purpose: complete the process limits around the V112 actual installed Field
Controller, source, D1, visible controls and closed-tree backup. These files are
prepared until a separately recorded native admission is executed. Earlier code
and receipts remain immutable. No runtime or offline acceptance follows from
compilation or preparing a plan.

Selected sources: field_live_gate_v4.py, stage_field_live_entry_v2.py and
dispatch_field_live_entry_v3.py. GateV3 and dispatcherV2 are retained preparation
steps. All use the V112 worker and production source chain without changing its
model, path, byte, session or source acceptance checks.

Gate: CPU3,128MiB hard address space,1MiB hard stack,32MiB file limit and a default
SIGALRM at335s, shortened to the common child hard deadline plus35s. Worker unit:
CPU2,3/shared200%,Tasks64,768MiB address space,1MiB stack,32MiB file size,
RuntimeMax285s and Stop30s. Actual unit values must match before owner ACK.
The gate refuses worker launch if less than285s remains in the already-running
300s common child lifetime. This prevents late launch from moving cleanup past
the gate alarm. Source Stop/drain still follows the retained shared deadline.

Staging: CPU3,128MiB address space,1MiB stack,32MiB file ceiling,30s alarm.
Stage-owner closure utility:128MiB/1MiB/zero file size/10s alarm. Closed-tree
utility: the same limits with30s alarm. Host coordinator requires590..600s
remaining at entry, waits at most345s for live SSH then35s for owned-unit Stop.
The retained mirror has its own110s watchdog/120s caller timeout and refuses
late admission. A failed or absent closure cannot qualify a backup; preserve the
target and obtain a fresh, bounded failure-recovery admission if needed.

Inputs: a private exact PLAN.json with admission, host source pins, coordinator
hash, fresh census, prior host owners, fresh output path and compact stage_files.
The admission binds all Pi source/config pins, exact installed v12 manifest,
quiet-capture authority, baseline identities, prior Pi owners, the selected D1
method evidence, a new measured resource policy and unchanged WINDOW_V5 bytes.
Use the complete164,406,360B reservation (80,106,028 target +84,300,332 host).
Do not dispatch a draft or invent readiness flags. No old policy is edited.

PowerShell, only after source review, backups and the fresh full admission:

    Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
    & 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B dispatch_field_live_entry_v3.py --plan '<private-absolute-PLAN.json>'

CMD and Anaconda Prompt, using the same explicitly selected Python:

    cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
    "C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_live_entry_v3.py --plan "<private-absolute-PLAN.json>"

The native gate/stager are invoked by the pinned coordinator, not directly from
Windows. Outputs are the retained bounded host owner/admission/raw/closure files,
target source/route/native/archive/UI receipts and the independently checked SSH
mirror. Audio, transcripts and images remain private. The Python writer guard is
not a kernel quota or proof of every C-library write. Quiet passage establishes
function and resource behavior only. Physical touch, cold-boot/cable-disconnected
offline operation, gallery and general data actions remain separate gates.
