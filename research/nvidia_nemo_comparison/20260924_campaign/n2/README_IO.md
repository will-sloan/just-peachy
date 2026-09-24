# Bounded Windows status-file replacement

`io_utils.py` stages/fsyncs JSON, then retries `os.replace` only for Windows `PermissionError` codes 5, 32 and 33. Backoff starts at 10 ms and is capped at 200 ms, with a two-second replacement retry deadline. Other errors propagate immediately. Persistent failure preserves the original destination and unique temporary JSON. No permissions, security settings or file-sharing policies are changed.

`test_io_utils.py` injects two transient sharing failures followed by success, a persistent access denial bounded to two seconds, and an unrelated error that must not retry. These tests use temporary synthetic JSON only; there is no model/audio/GPU work.

PowerShell:

```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree'
$n2Python = 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$n2Scripts = 'research\nvidia_nemo_comparison\20260924_campaign\n2'
& $n2Python "$n2Scripts\test_io_utils.py"
& $n2Python "$n2Scripts\diarization\resume_native.py" --output 'G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\fixed-cuda-all-v1'
```

Command Prompt or Anaconda Prompt:

```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree"
set "N2_PYTHON=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "N2_SCRIPTS=research\nvidia_nemo_comparison\20260924_campaign\n2"
"%N2_PYTHON%" "%N2_SCRIPTS%\test_io_utils.py"
"%N2_PYTHON%" "%N2_SCRIPTS%\diarization\resume_native.py" --output "G:\Just_Peachy_N1\20260924_campaign\local\n2\diarization\fixed-cuda-all-v1"
```

The resume wrapper is specifically for an existing stopped native-screen output. It validates the original/frozen runner and interpreter hashes, checks previous PID/creation-time ownership has ended, and exclusively writes a new `io_resumes/<attempt>/IO_RESUME_AMENDMENT.json` before calling the unchanged original coordinator. The amendment preserves prior progress/index/owner/error snapshots and binds the original runner, frozen numerical runner, adapter, helper, wrapper and unchanged numerical contract. It replaces only the parent module's atomic JSON helper; subprocess workers continue executing the original frozen model runner. Existing error artifacts and completed checkpoints stay intact. Current checkpoint integrity is rechecked by the original coordinator; completed cells are skipped, and failed cells are not automatically retried.

The wrapper derives all numerical arguments from the existing admission (all three profiles, CUDA0/CPU14 for this screen), so this IO recovery does not change the cache key or rerun completed work. `--prepare-only` validates/resumes the index without inference. Outputs are the amendment/result receipts plus the original progress and new per-cell checkpoints. Launch only after the campaign coordinator grants the existing GPU/CPU slot; the original OS writer lock still prevents concurrent numerical owners. A reader retaining a file handle longer than two seconds still causes an explicit failure.

The actual recovery completed all 288 cells with zero numerical failures. It verified/skipped 195 existing completions and ran the remaining 93; the original 195 result bindings remained identical. The immutable amendment/result and preserved original failure are under `fixed-cuda-all-v1/io_resumes/20260924T171812_8e665c82`. `diarization/FULL_NATIVE_SCREEN_RECEIPT.json` binds the final status, and `IO_TEST_RECEIPT.json` records the three actual passing injected IO tests. The final coordinator and model worker ended. The final index elapsed time describes only this resume, not the sum of all screen launches.
