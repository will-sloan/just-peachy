# Paced intermediate chunk52 candidate

Purpose: measure actual original1x source timing, queue residence, first probabilities and EOF drain for the experimental chunk52 recipe after its independent full-file generic/A76/repeat checks. This does not establish speaker accuracy or an integrated app mode. See README_CM5_CHUNK52_V1.md for the full52/1/0/80/264/40 recipe and its experimental status.

`dispatch_cm5_chunk52_paced_v1.py` binds the unchanged, previously executed d1_geometry_paced_v1.py harness to the new adapter, qualified8-entry executable graph cache library and same-geometry generic reference. It requires independent A76 component reviews before dispatch. Source producer, FIFO200x100ms, explicit overflow failure, producer join and all-sample/state/EOF gates are unchanged. Outputs: private source/call traces, arrays, metrics, RESULT and the independently collected REVIEW from `review_cm5_chunk52_paced_v1.py`.

## PowerShell

From this report directory with a fresh census:

```powershell
$py = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
& $py dispatch_cm5_chunk52_paced_v1.py --profile native_cm5_chunk52 --kernel a76 --run-id d1-geometry-chunk52-paced-v1 --reference d1-geometry-chunk52-generic-v1 --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V8.json'
& $py review_cm5_chunk52_paced_v1.py --run-id d1-geometry-chunk52-paced-v1
```

CMD/Anaconda Prompt: `cd /d` to this directory, use the same explicit Python executable and arguments with double-quoted paths, and omit `&`. No activation/install/download. Refuse existing run IDs; preserve all failed attempts and source hashes. Review only after terminal closure.

All guards from README_GEOMETRY_PACED_V1.md remain: targetCPU2/3,totalCPU200%,one native model thread plus waiting producer,Tasks64,600seconds,hard768MiB virtual cap,>=850MiB available RAM,>=5GiB disk,16MiB output reservation under the combined1GiB allowance. No increased cap, microphone/playback, training/enrollment, silence skipping or changes to current app/install. Model-call work and paced elapsed time have distinct denominators; no long-conversation stability claim follows from this short test.
