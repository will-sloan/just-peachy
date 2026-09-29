# B01 compact archive Save/Open supplement V1

Purpose: verify actual controller Save/Open and withdrawn Tk rendering on a fresh copy of `b01-artifact-fixture-v1` archives. Its inference/PCM/drain gates passed independently, but the original harness failed comparing four utterance records with40 nested display segments. This supplement tests the previously unreached presentation path without rerunning models or changing the original failure.

Inputs: immutable source from the model run, its independent `REVIEW_PARTIAL_V1.json`, original40-row final snapshot, exact copied private conversations and configs, fresh WINDOW_V5 census. Each original and copied journal/float/WAV hash is checked; only copied conversation metadata may change through normal controller commands. Models are never loaded, no stream/playback/device query, original app untouched. Original files remain preserved.

Outputs: fresh `b01-artifact-reopen-v1` private archive copy, source/admission/live-unit/owner receipts, opened40-row snapshot, actual widget text and model-load counters. Match stable IDs, raw/formatted text, labels, source intervals, span/word histories and revisions. Normal1.4second Tk event loop permits existing label stabilization; no clock override. This qualifies neither physical display/touch nor live quality/endurance.

Bounds: CPU2/3,total200%,one native thread,768MiB hard virtual,1MiB stacks,64tasks,300seconds/290alarm/10second stop,8MiB hard per-file cap. Initial850MiB RAM and5GiB disk;96MiB combined reservation (48MiB target+48MiB host backup). Existing research lease held through closure. No baseline changes; root remains withdrawn with deiconify blocked.

PowerShell:

```powershell
Set-Location G:\Just_Peachy_N1\20260924_campaign\worktree
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$p='research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& $py -B "$p/b01_artifact_reopen_v1.py" --census 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V66.json'
```

CMD / Anaconda Prompt:

```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928\b01_artifact_reopen_v1.py --census G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\HOST_CENSUS_V66.json
```

Use an unused census if V66 is older than15minutes. Run ID is exclusive and must not be reused. Target-only `--worker`/`--gate` are called by the dispatcher. After closure, independent review from either shell:

```bat
ssh -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local "python3 -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-artifact-reopen-v1/review_b01_artifact_reopen_v1.py"
```

Reader verifies all compared row fields and widget contents, source hashes, original archive unchanged, real resource envelope, zero model loads, natural process/controller/Tk closure. No success is inferred from prepared code or the prior failed harness.
