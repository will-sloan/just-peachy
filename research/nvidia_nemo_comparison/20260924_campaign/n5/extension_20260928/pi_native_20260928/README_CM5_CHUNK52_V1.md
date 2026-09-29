# One intermediate CM5 recipe candidate

Purpose: investigate the gap between the native1.04second center chunk and21.12second delayed center chunk. This is one selected experiment, not a sweep or an official NVIDIA named preset. It uses52/1/0/80/264/40 (chunk/right/left/FIFO/speaker-cache/refresh in80ms frames). Only center chunk length changes from native streaming13 to52; all other fields are explicit and unchanged. Input buffering is4.24seconds plus frontend support, followed by actual computation. No latency or speed is claimed from preparation.

The pinned runtime validates positive chunk/refresh, nonnegative contexts/FIFO, sufficient speaker cache and total sequence below the positional limit. Actual C-ABI fields and native construction must still pass. Changing geometry may change speaker probabilities and accuracy; retain the candidate for frozen real-life speech/overlap/returning-speaker validation. Do not call it a quality-equivalent replacement.

`prepare_cm5_chunk52_v1.py` adds this profile to a fresh private native-profiles-v3 adapter, preserving every prior profile and the delayed-preset FIFO0 fix. Inputs: native-profiles-v2 and its pinned SHA. Outputs: new adapter and DERIVATIVE.json, initially SOURCE_PREPARED_NOT_EXECUTED.

`dispatch_cm5_chunk52_v1.py` requires the independently reviewed streaming generic/A76 full-source result with the8-entry executable-graph LRU before dispatching this candidate. It uses the existing immutable d1_geometry_v1.py harness, same weights/library and exact saved source. Generic full/repeat runs first; `review_cm5_chunk52_v1.py` independently verifies actual geometry, continuous715127samples/4470frames, repeat/reset/EOF/close and arrays. A fresh A76 run must match that same-geometry generic reference at1e-5. Private outputs include traces, metrics, arrays, owner/admission and scoped REVIEW. No new ASR/WER/DER scoring.

## PowerShell

From this report directory:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py prepare_cm5_chunk52_v1.py
& $py dispatch_cm5_chunk52_v1.py --profile native_cm5_chunk52 --kernel generic --run-id d1-geometry-chunk52-generic-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V8.json'
& $py review_cm5_chunk52_v1.py --run-id d1-geometry-chunk52-generic-v1
```

Preparation is single-use; verify an existing derivative instead of rerunning it. Following independent review, use a new ID with `--kernel a76 --reference d1-geometry-chunk52-generic-v1`. Existing run/review paths must not be overwritten. A paced-input experiment requires its own derivative and evidence; unpaced elapsed time is not live output latency.

## CMD / Anaconda Prompt

Use `cd /d` to this report folder. Run the same commands with the explicit Python path in double quotes and omit `&`; quote the census path. No environment activation, download or installation is needed. The source and dispatch/review scripts use the existing interpreter.

All CPU/RAM/owner/output checks are retained from README_D1_LRU_CHECKS_V1.md: targetCPU2/3,totalCPU200%,one native thread,600seconds,hard768MiB virtual cap,850MiB available RAM,5GiB disk,16MiB reservation within the combined1GiB budget. Host census must be less than15minutes old. Original app/install and all evidence remain unchanged. No recording/playback, silence skipping, training or enrollment. Components are separate from delivered application modes, full release acceptance and independent real-life validation.
