# B01 V8 with separately qualified bounded D1 metadata

Purpose: retest combined Sherpa ASR + D1 Nemotron diarization + E0 ReDimNet using actual shared-app-v2 Controller after the native metadata repair. Prerequisite: independent D1 V12 original full-source/repeat/reference/EOF pass and exact owner closure. V8 harness behavior is V7 unchanged; only its README and separately hashed D1 runtime binding differ. Preserve1MiB Python stacks (no resetting getter), one process-local glibc arena, one native thread/model, original source pacing and all60-second inference/drain gates. No silent fallback or skipped audio.

Inputs/outputs are as in README_B01_ARENA_V1.md, with fresh b01-short-v8, b01_native_short_v8.py and empty private data. Bind n2_runtime.json's library/dependency paths/hashes to d1-metadata-full-v12/nemo-arm64/lib and the independently reviewed V12 receipt. Every old shared source/model/prefix remains hash verified. Outputs include OWNER/RESULT, immediate MEMORY.jsonl, snapshot/progress and actual journals/finalization. Independently inspect192000 paired source/ASR/identity samples, caption text, D1 frame/time coverage, embedding calls, no backend fallback and final worker/handle closure. No microphone, playback, GUI window, new WER/DER score or release acceptance.

## PowerShell / Anaconda PowerShell

After fresh target admission, boot/exact-owner/unit/resource/input checks:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-b01-short-v8 --wait --pipe --setenv=MALLOC_ARENA_MAX=1 -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=180 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/b01-short-v8/b01_native_short_v8.py'
```

## CMD / Anaconda Prompt / Linux

Use double quotes around the remote command for CMD/Anaconda Prompt; Linux runs systemd-run directly. No activation/install/download. Retain CPUs2/3,CPU200%,Tasks64,180seconds,hard768MiB virtual address space,>=850MiB available,>=5GiB disk and16MiB output reservation. Existing rc5 app remains running; timing is conditional. Even a narrow pass still needs full-file, Stop/restart, mode/UI/storage/backend and sustained real-life evidence before an accepted new release or real-time claim. This is a test harness, not an installed user-facing launcher.
