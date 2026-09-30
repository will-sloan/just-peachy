# Absolute child deadline fixtures V1

Purpose: address V72's static finding that a declared 60-second child limit was not a single enforced lifetime. V72 observed children were all short and remain functionally passed. This fresh run qualifies shared monotonic deadline enforcement and closure with small no-capture fixtures. It does not repeat the healthy installed controller, model, writer, GUI or capture protocols.

## Files and behavior

`field_child_deadline_v1.py` binds an exact same-boot monotonic issue/soft/hard deadline to admission maximum 60 seconds including up to 2 seconds cleanup grace. Both parent and child consume the same object; phase waits cannot reset it. The child installs a soft-expiry Python signal handler; the parent sends TERM at soft expiry and KILL at the common hard deadline if necessary. Reaping has a separate one-second timeout after KILL, not extra execution permission. Scheduling and signal-delivery latency are observed, not a hard real-time guarantee. Existing alarms are rejected instead of overwritten.

`field_overlay_launcher_v2.py` is a derivative of the immutable V72 launcher: arm this deadline before verification, hold its existing ownership through cleanup, and use the common time budget for test barriers. The only real launcher path executed here is rejection of an already expired spec, before candidate/dependency/controller entry. `field_overlay_launcher_protocol_v2.py` prepares the matching parent spawn/phase/wait/abort interface. Its healthy controller protocol is NOT executed or newly qualified in this run. Source derivation hashes are in `CHILD_DEADLINE_DERIVATION_V1.json`.

`field_child_deadline_protocol_v1.py` runs seven malformed/expired pre-spawn rejections, one actual expired launcher rejection (itself supervised by a fresh 2-second fixture budget), and three sequential fixture children. `field_deadline_fixture_v1.py` uses fresh private RuntimeLocks with a common 1.2-second lifetime and 250ms cleanup grace: normal exit, cooperative expiry, and deliberate SIGALRM/SIGTERM ignore followed by parent SIGKILL. No descendants are created. Forced death has no logical finalization receipt; exact stale lock bytes are preserved and the existing RuntimeLock interface reclaims only the independently confirmed dead owner. No manual lock deletion or retry of rejected candidate mutations.

`dispatch_field_child_deadline_v1.py` performs fresh host/Pi ownership, baseline, capture, RAM/disk, target-inclusive output/payload and lease checks. It stages a new immutable private run with exact admission/source/config bindings and supervises it using the existing resource envelope. `review_field_child_deadline_v1.py` independently checks source/admission hashes, actual limits, shared timing receipts, signal outcomes, stale-owner recovery and closure. `backup_field_child_deadline_v1.py` preserves and verifies every private target file.

## Inputs and outputs

Inputs: current CPU14 host census, immutable WINDOW_V5, September29 authorization, original installed rc5 identities, retained v12 release RuntimeLock and exact V72 helpers; no audio, models, user speech or network downloads. The dispatcher binds actual source hashes, original config hashes and expiry into ADMISSION.json. It reuses retained files without release/assets/runtime/catalogue copies.

Target output: `~/JustPeachy/research/nemotron-20260928/field-child-deadline-v1` including admission, owners, actual LIVE_ENVELOPE, deadline specs/rejections/READY/RESULT/COLLECTED, preserved stale lock, service/resource receipts and aggregate RESULT. Private host output: `G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\field-child-deadline-v1-evidence` including independent REVIEW, exact BACKUP and target copy. stdout contains only compact status. Expected child codes are 0, 124 and -9; expired real launcher returns 1. Aggregate parent must exit naturally 0 for a pass. Failure evidence is retained.

## Resource and evidence scope

Fresh 4MiB target + 4MiB host reserve, unchanged WINDOW_V5 5GiB output/52GiB payload including prior use and 2.5GiB reservations; fixed 32GB Pi and 5GiB free floor. Parent and sequential child each inherit 768MiB AS, 1MiB stack, CPU2/3, shared 200%/Tasks64/32MiB file limit. Parent systemd 300s/Stop60s; initial 850MiB available and sampled 192MiB available/640MiB aggregate stops. Host coordinator CPU14. There is no model, mic, playback, epoch, GUI or baseline activation. This is real native timer/process/lease evidence, not installed-controller timeout cleanup or full field release acceptance. Existing V72 ownership and successful startup/rollback evidence is not rerun or rewritten.

## Run once from PowerShell

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B dispatch_field_child_deadline_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V165.json'
& $py -B review_field_child_deadline_v1.py
& $py -B backup_field_child_deadline_v1.py
& $py -B collect_native_closure_v5.py --version 165
```

## Command Prompt or Anaconda Prompt

Use the existing Python explicitly; no environment install or activation needed.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_child_deadline_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V165.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_child_deadline_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_child_deadline_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 165
```

These are single-use commands for a fresh target/evidence root and census younger than 15 minutes. Do not rerun a completed dispatcher or overwrite receipts. A stale census requires a fresh numbered census before dispatch, using the existing census command described in README_FIELD_OVERLAY_LAUNCHER_V1. Preserve the failed run and diagnose before preparing any different run. Strict SSH and existing lease interfaces are mandatory; worker/gate are internal dispatcher modes, not user launchers.
