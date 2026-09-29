# A2 native load and prefix lifecycle candidate

Purpose: test the already staged Nemotron English Q8 model on CM5. This is a separate A2 qualification attempt. Reuse the existing 8192-node scheduler-only build as an **unqualified A2 candidate**, retaining the 95% graph guard, original metadata reservations, executable cache and generic CPU kernels. Do not reuse D1's 2048/2MiB/LRU1 settings. Native session source calls the graph helper with exactly one model thread.

Inputs: staged A2 asset (SHA d9a01898d2a611c8764e23a1c2f45e70bbd5a425dc4de93692ac951dd603812d), existing generic ABI/dependencies, scheduler-native-v1 runtime, unchanged application C-ABI adapter, first 32000 samples of original saved 16kHz PCM. No capture, playback, downloads or original installation changes. Private target derivative preserves its complete runtime/source binding; existing evidence is untouched.

Fresh admission: hard virtual address space 1GiB (authorized isolated A2 trial), at least 1.25GiB available RAM, CPUs2/3, total200%, native/model thread1, Tasks64, startup stack1MiB, 180s service/10s stop. Original app remains active, making timings conditional. No MEMCG/RSS/no-swap claim. Combined host+target staging/output reserve32MiB under WINDOW_V2 and original payload/free-space guards. Model weights are reused, not copied. Target log retained at most4MiB; overflow stops this owned service and fails review. Events/result files each bounded2MiB; no full transcripts in public reports. The research lease and exact dispatch identity last through service completion. Actual live systemd properties and cgroup CPU quota are recorded before model load.

Protocol: ABI/create, two independent streams of the exact first2s, 1280-sample pushes, native EOF, repeat equality, idempotent finish, post-finish rejection, explicit stream/recognizer destruction and natural process closure. This short diagnostic cannot qualify full-source, forced-endpoint behavior, accuracy, sustained throughput, B02 integration or N5 acceptance. If native abort occurs, retain logs/envelope/owner evidence; no clean application-finalization claim.

Run from PowerShell in the campaign worktree, using a fresh unused census version:
```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p = 'research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/a2_native_probe_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V36.json'
```
CMD or Anaconda Prompt (no activation required):
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\a2_native_probe_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V36.json
```
The census must come from window_guard_v2.snapshot, be less than15minutes old, and pass its existing supervision/reservations checks. --worker/--gate are internal target entry points, not standalone shortcuts. Fixed run ID refuses overwrite; changes/retries need a fresh version and reviewed admission.

Outputs: private target a2-native-probe-v1/{ADMISSION,BINDING,DISPATCH_OWNER,OWNER,LIVE_ENVELOPE,PROGRESS_LOAD,PROGRESS_LOADED,RESULT,DISPATCH_RESULT}.json, bounded service.log and private EVENTS_*.json when reached; host a2-native-probe-v1-evidence/PREFLIGHT and LAUNCH_RESULT. Independently inspect admission/source hashes, actual envelope, allocation/graph logs, results, exact boot/PID/start closure, resource peaks, output bound and unchanged baseline. Never equate terminal success with acceptance.
