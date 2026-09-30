# Persistent transport close failures V1

Purpose: keep a failed transport close failed on every subsequent call. The retained V76 transport marks its physical socket closed before checking child outcome; its next close otherwise returns without the prior error. This thin, versioned subclass serializes callers, calls the exact retained close once, and saves the finite SourceFault code/detail independently of caller mutations. It never changes the retained transport or saved failure evidence. A successful outcome can return idempotently; this protocol deliberately does not rerun healthy transport.

Unexpected ordinary exceptions become CLOSE_FINALIZATION_EXCEPTION with original type/message. An interruption such as KeyboardInterrupt propagates on its first call and remains an explicit failed outcome on subsequent calls. Nonfinite/non-JSON details explicitly become CLOSE_FAILURE_DETAIL_UNSERIALIZABLE; they are not claimed as faithfully retained detail. An already-closed object with no outcome rejects CLOSE_OUTCOME_UNAVAILABLE. No automatic retry or cleanup deletion. Locks serialize callers; this does not supply a deadline for a stalled close operation or make physical cleanup complete after an interruption. The constructor adapter is prepared but not exercised against a new transport process.

Inputs: fresh CPU14 host census; exact retained V76 transport/helper source and four private failure case/closure hashes; current authority/baseline and source-bound admission. Four detached objects reuse saved owner-quota, ready-quota, result-quota and parent-blocked outcomes. Each invokes the actual retained close with a closed-process view and counted watcher/socket stand-ins, followed by two repeat calls. No source constructor, subprocess, socket I/O, timer, healthy transport, model, capture, controller or GUI runs. Original missing closure stays missing. Five additional small latch cases cover two concurrent callers, unexpected exception, nonfinite detail, interruption and already-closed/no-outcome. These are functional replay/fixture evidence, not new process cleanup or live qualification.

Outputs: fresh private target field-transport-close-latch-v1 and host field-transport-close-latch-v1-evidence, CLOSE_LATCH_CASES.json, RESULT/resource/admission/owner receipts, independent review and exact private backup. Code/derivation/this README are frozen before dispatch. No release/catalogue/audio/asset copies. Dispatcher samples unique boot/PID/start-tick identities instead of summing duplicate owner paths; a no-child run does not independently stress duplicate child records. Parent768MiBAS,1MiB stacks,CPU2/3/shared200%,Tasks64,300s/Stop60/32MiBfile,4MiB target+4MiB host. Initial850MiB available, sampled192MiB available/640MiB aggregate stop. Fixed32GB/5GiB free, WINDOW_V5 output5GiB/total52GiB including retained2.5GiB reservations remain unchanged. No whole-run allocation or capture admission.

## PowerShell

Run once with a fresh numbered census under15minutes. Do not overwrite receipts or rerun a bound target. The internal --gate/--worker flags are dispatcher plumbing.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; b=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); json.dump(snapshot(b,8*1024**2),(b/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V170.json').open('x',encoding='utf-8'),indent=2)"
& $py -B dispatch_field_transport_close_latch_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V170.json'
& $py -B review_field_transport_close_latch_v1.py
& $py -B backup_field_transport_close_latch_v1.py
& $py -B collect_native_closure_v5.py --version 169
```

## Command Prompt / Anaconda Prompt

Use the existing explicit interpreter; no environment installation or activation. If census V170 already exists, use it only while fresh; never recreate it. A later run requires new source/run/version and a new numbered census using the same Python census command above with the full quoted interpreter instead of `& $py`.

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_transport_close_latch_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V170.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_transport_close_latch_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_transport_close_latch_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 169
```

Recovery: preserve failure evidence and use a separately reviewed derivative/admission. The live entry/GUI/outer artifact and host guards remain pending; this adapter does not enable capture or alter installed pointers/baseline. No new timing, audio, quality, endurance or field-release claim.
