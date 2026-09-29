# Whole native D1 recipes: controlled CM5 checks

Purpose: qualify exact recipe binding, full saved-file coverage, repeat/reset/EOF and same-geometry generic/A76 numerical agreement, then record actual component cost. These are functional/resource observations on the connected CM5, not new ASR/WER/DER accuracy results, real-world speech validation, integrated profiles or release acceptance. All audio is retained. The original rc5 app stays active, so timing is conditional.

`prepare_native_profiles_v2.py` creates a fresh private adapter from native-profiles-v1. The pinned C API applies FIFO overrides only when positive. V1 passed zero with the streaming preset for the delayed candidate, which would leave FIFO80. V2 selects `v3-offline` only for that candidate, preserving FIFO0 from the preset. Other profiles are unchanged. No native ABI or model weights change. Source hashes are in DERIVATIVE.json; the earlier unexecuted preparation remains preserved.

Recipes use80ms coarse frames; public output remains10ms. Order: chunk/right/left/FIFO/cache/refresh. Streaming is13/1/0/80/264/40; delayed is264/1/1/0/264/188. The latter requires about21.2seconds of input before a complete first chunk, plus actual compute. It needs independent captions and Pending labels in a future integration. Different recipes need not match each other's probabilities. The same-recipe kernel max-absolute gate remains1e-5.

Inputs: already staged pinned Q8 D1 weights, exact715127-sample16kHz saved WAV, qualified D1-only2048-node scheduler/8MiB metadata runtime, either retained generic CPU library or lane-preserving A76 CPU library, new adapter, fresh host census and target admission. The harness intercepts the actual C-ABI creation call to verify every recipe field. Pinned C-API/header sources define effective preset handling. No downloads, capture, playback, training or enrollment occur.

Outputs remain private: CONFIG/INPUTS/ADMISSION/OWNER, bounded per-call source-frame/time trace, heartbeat, arrays, case metrics and RESULT. Generic reference runs first and requires an independent REVIEW before A76 dispatch. A76 compares its full output to that same-recipe reference. Both runs test complete frame continuity, sample coverage, resident repeat, repeated EOF, rejected post-finish push, empty reset and model close. These unpaced component measurements do not establish actual paced backlog or integrated caption/label latency. Native abort/timeout logs are preserved even if no RESULT is written.

## Run from Windows PowerShell

Use a fresh run ID and a comprehensive census less than15minutes old. The dispatcher refreshes host window bytes, exact closed owner identities, native boot/PID/start ticks, systemd ownership and RAM/disk before each launch. It refuses existing run directories. A human/operator must inspect and independently review each closed job before another numerical dispatch.

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py prepare_native_profiles_v2.py
& $py dispatch_geometry_v1.py --profile native_v3_streaming --kernel generic --run-id d1-geometry-stream-generic-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V5.json'
```

Preparation is single-use; if the derivative already exists, verify its receipt and reuse it. Do not rerun or overwrite. Following successful independent review of the generic job, use a new ID, `--kernel a76 --reference d1-geometry-stream-generic-v1`. For delayed recipe use `--profile native_v3_delayed`, separately collecting/reviewing its generic reference first. Refresh the census when expired. No automatic sweep is provided.

## CMD / Anaconda Prompt

No environment installation is needed. Use the explicit existing interpreter; an Anaconda Prompt runs the same commands:

```cmd
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" dispatch_geometry_v1.py --profile native_v3_streaming --kernel generic --run-id d1-geometry-stream-generic-v1 --census "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V5.json"
```

The dispatcher uses strict retained SSH host verification and stages immutable inputs into a new Pi research directory. It starts `d1_geometry_v1.py` through systemd-run/taskset under CPUs2/3, CPUquota200%, TasksMax64,600seconds, one native model thread and hard768MiB RLIMIT_AS. At least850MiB RAM available and5GiB disk are required. Each job reserves16MiB under the combined1GiB campaign allowance. No increased cap is authorized by this README; the integrated1GiB request remains pending. The review checkpoint is October1 at17:47:34UTC. Preserve the current install/autostart, all earlier failures and every bound source hash.
