# B01 deferred SciPy full-source diagnostic V1

Purpose: test the measured unnecessary startup SciPy mapping identified in the
closed first-use E0 failure. Two top-level resample_poly imports move into the actual
rate-conversion branches of audio.py and enrollment.py. Existing 16k saved audio
needs neither branch. Original eager E0 loading, all model settings and windows,
D1 geometry, history, ASR/PnC and source pacing remain unchanged. This is a separate
full-source run reusing the unchanged short-run deferred-SciPy derivative. No additional application edits. Resampling calls still
use the identical SciPy function if later requested. No microphone or enrollment
path is executed; those routes remain unqualified under the reduced-memory claim.

The diagnostic asserts no SciPy modules after application import or completion,
one real E0 load and no silent fallback. Require actual D1/E0 passage, unchanged
outputs and clean closure before crediting any success. No accuracy scoring.

## Inputs and bounds

Original715127-sample44.6954375-second PCM source, qualified native-stack source/runtime
and installed model assets. Fresh comprehensive host census (<15 minutes), exact
closed identities, boot/install/source hashes, CPUs2/3, total200%, one model thread,
768MiB hard RLIMIT_AS, startup1MiB stack, >=850MiB RAM, >=5GiB target disk. The shared
preview flock stays held through service completion, including this non-UI job.
No visible Tk root is constructed. Service180s, application140s.48MiB output reservation
includes the linked source tree, small logs and private smaps snapshots. Existing
original app stays running, so performance is conditional diagnostic evidence.

## Run once (PowerShell)

From G:\Just_Peachy_N1\20260924_campaign\worktree:

```powershell
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' "$p/dispatch_b01_defer_scipy_full_v1.py" --run-id b01-defer-scipy-full-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V20.json'
```

CMD or Anaconda Prompt (uses the explicitly pinned environment, not the active conda Python):

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/dispatch_b01_defer_scipy_full_v1.py --run-id b01-defer-scipy-full-v1 --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V20.json
```

Do not rerun the same ID or reuse an expired census. Old run paths are immutable.
If storage, source, identities or admission fail, leave the failure and use a fresh
reviewed derivative only when there is a justified change. No higher cap is permitted.

## Outputs / independent review

Private target b01-defer-scipy-full-v1 and host b01-defer-scipy-full-v1-evidence contain admission,
launch/service ownership, logs, memory samples, smaps, source manifest and, if handled,
RESULT/final snapshots. Raw text/audio/vectors remain private. A native abort may have
no RESULT or application finalization; exact OS closure does not qualify clean drain.
Require original eager E0 construction and no SciPy import on this saved-file path, unchanged D1
probabilities/source mapping and E0 vectors, complete coverage, ASR passage, explicit
label lineage, natural process/worker/archive drain before any functional credit.
For a failure record the exact stage/allocation/unit outcome without promoting a mode.
This is one full saved-file functional/resource check, not Stop/restart, endurance or real-life accuracy evidence.

Independent review: use review_b01_scipy_v1.py --run-id b01-defer-scipy-full-v1 as documented in README_B01_SCIPY_REVIEW_V1.md. E0 independent numerical reference remains a separate gate.
