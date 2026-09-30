# Required archive: actual controller Stop binding V1

Purpose: change the installed v12 Controller's archive failure behavior so preparation failure cannot continue into source Start, archive-worker failure requests mandatory Stop, and queued Stop/Close cannot erase the first failure. This isolated candidate does not activate the original app or enable a full live field release.

Inputs: exact installed v12 controller, pipeline, session workflow, runtime, manifest/assets pins; retained V102 sessions/publisher/archive wrapper/shared sidecars; fresh CPU14 census and unchanged WINDOW_V5. The factory compiles the exact installed `_start_session` body with two explicit changes: its archive OSError handler rethrows, and a latched failure check precedes the source-start try. Original constructor and engine constructor run. The new command loop services a mandatory Stop flag before subsequent queued commands and preserves the failure until Close. The callback signals an existing source Event immediately when present; it does not join or perform filesystem/queue work on the archive thread. This path's real hardware/source callback is prepared, not qualified by the no-source cases below. Arbitrary blocking command/model startup or concurrency stress is not covered.

Two changed native cases use actual Controller/ApplicationLock/command workers. Queued file Start with a nonexistent file deliberately encounters an injected three-byte conversation publication failure BEFORE that file is opened or any source/model starts. The actual engine constructor is observed through a delegating wrapper, then normal installed cleanup releases it. A separate actual SessionStore/EpochArchive thread faults at its first checkpoint; its callback reaches the actual controller and mandatory Stop, then joined failed archive ownership is released without publisher retries. An explicit queued Stop closes an archive that may attach after the early callback; this is not an attachment-race stress qualification. Stop and a rejected restart preserve ERROR; Close retains the original terminal error, closes the command worker and releases the application lease. No Event-only controller stand-in, model, source, audio, microphone, GUI or physical cleanup claim. The source-event branch is not exercised when there is no source.

The bound archive failure wrapper retains pending bytes and failed primary. Failed archive removal from the in-memory active set occurs only when its real thread joined and closed. It does not rewrite a failed primary as CLOSED or update a failed conversation. Two shared output roots reserve1,851,392B each; actual entry preparation and archive producers use separate fixed failure/closure slots. Other producer/writer integration remains open. The controller's final application JSON is redirected to the bounded receipt group (256KiB/12files/64KiB writes). Data schema uses the same guard; source/journal paths are never entered. Store automatic draft deletion is disabled in this candidate. Existing v12 artifact limits remain, but no claim is made that their whole live maxima fit this no-audio admission.

Outputs: fresh Pi `~/JustPeachy/research/nemotron-20260928/field-controller-stop-v1`, private host `field-controller-stop-v1-evidence`, immutable cases/outer envelopes/closure and exact private target backup. Fresh16MiB admission=8MiB target+8MiB host; retained bounded stage/outer and sampled total guard, not filesystem hardquota or full live composition. Two application data roots are isolated from original data. Fixed32GB Pi/5GiB free; C50GiB/G75GiB;52GiB payload including target/reservations and5GiB combined output unchanged. One native run; preserve every failure and do not retry rejected mutation or closed target. Actual768MiBAS/1MiBstack/CPU2,3/shared200%/Tasks64/300s/Stop60/32MiBfile,gate128MiBCPU3. No MEMCG hardRSS. Finish before Oct1 17:42:44UTC; finalization starts16:42:44UTC. Preserve display270 and baseline.

## PowerShell

Use a fresh reviewed census/version. These exact targets are single-use; do not replay a closed run.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py -B -c "import psutil; psutil.Process().cpu_affinity([14]); import sys,json; from pathlib import Path; sys.path.insert(0,str(Path.cwd().parent)); from window_guard_v5 import snapshot; b=Path(r'G:\Just_Peachy_N1\20260924_campaign\local'); json.dump(snapshot(b,16*1024**2),(b/'n5/research-extension-20260928/pi-native-20260928/HOST_CENSUS_V199.json').open('x',encoding='utf-8'),indent=2)"
& $py -B dispatch_field_controller_stop_v1.py --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V199.json'
& $py -B review_field_controller_stop_v1.py
& $py -B backup_field_controller_stop_v1.py
& $py -B collect_native_closure_v5.py --version 219
```

## Command Prompt / Anaconda Prompt

Use the same census Python body above with this explicit interpreter (no install or conda activation required).

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B dispatch_field_controller_stop_v1.py --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V199.json"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B review_field_controller_stop_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B backup_field_controller_stop_v1.py
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B collect_native_closure_v5.py --version 219
```

Library entry `controller_class(module,sessions,outputs,policy,expected_controller_sha)` returns a subclass for an isolated process after pins and limits are checked. The protocol supplies injection only in the publisher's write function and a delegating engine observer; no production source is substituted. It is not the final operator launcher. Integrate remaining source/config/TRACE/native/archive/host writers and a fresh admitted live run before reporting offline readiness. Review and backup commands operate only on closed evidence; internal gate/worker flags belong to the dispatcher.
