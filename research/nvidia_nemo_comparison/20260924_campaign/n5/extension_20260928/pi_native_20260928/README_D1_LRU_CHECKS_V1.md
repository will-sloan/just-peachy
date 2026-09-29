# Full native recipe checks with the bounded graph LRU

Purpose: retest the failed native streaming recipe after the isolated48-to8 executable-graph cache repair. This cap applies to compiled graphs, not speaker/FIFO history. See README_D1_LRU_V1.md for the verified one-line build. A second check of the already qualified delayed geometry against its original generic array can detect regressions in that recipe; its old successful run must stay unchanged.

Inputs/outputs and full-source/repeat/reset/EOF/continuous-frame gates are unchanged from README_GEOMETRY_V2.md. `dispatch_d1_lru_geometry_v1.py` uses the preserved d1_geometry_v1.py harness and substitutes only the independently reviewed new library SHAfa8ecbb66124b62fced485d45dd2ec6018634a35d39dbc143e221b9f7230b622. CONFIG/INPUTS bind the8-entry cap and build review. The generic kernel first collects a fresh reference for the repaired streaming recipe; the lane-preserving A76 kernel must match it under the unchanged1e-5 threshold. The earlier48-entry run lacks a complete array because EOF aborted; do not claim complete old/new-cache parity from a new reference.

Retain all audio, original chronology and one ordered native D1 stream. No accuracy score, new capture, playback, download or training. A terminal success is only collected evidence; use the independent review_geometry_v1.py reader from README_REVIEW_GEOMETRY_V1.md and inspect memstats for actual cache bounds/eviction. Keep final process closure and hashes. No application release acceptance follows.

## PowerShell

From this report directory, after a fresh host census and closed native ownership:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py dispatch_d1_lru_geometry_v1.py --profile native_v3_streaming --kernel generic --run-id d1-geometry-stream-lru8-generic-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V7.json'
& $py review_geometry_v1.py --run-id d1-geometry-stream-lru8-generic-v1
```

Only after independent review, use a fresh run ID with `--kernel a76 --reference d1-geometry-stream-lru8-generic-v1`. Refresh the census after15minutes. For delayed regression, use `--profile native_v3_delayed --kernel a76 --reference d1-geometry-delayed-generic-v1` and a distinct ID. Do not rerun an unchanged successful test without a new reason.

## CMD / Anaconda Prompt

Use `cd /d` to this folder; invoke the same explicit Python executable in double quotes, omit `&`, and retain the arguments above. No activation/installation is necessary. Strict SSH stages a new derivative and systemd unit. CPUs2/3,totalCPU200%,one native model thread,Tasks64,600seconds,hard768MiB RLIMIT_AS,850MiB available-RAM and5GiB disk floors remain. Each run reserves16MiB under the combined1GiB allowance. The1GiB integrated request remains pending and is not admitted here. Preserve original rc5 install/app and all earlier evidence.
