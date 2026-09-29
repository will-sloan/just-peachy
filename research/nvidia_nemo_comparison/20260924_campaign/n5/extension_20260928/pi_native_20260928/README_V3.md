# Native D1 smoke V3: smaller scheduler

Purpose: retest the unchanged 12-second/repeat/EOF protocol under the same 768 MiB hard virtual-address cap after the bounded scheduler repair in README_SCHEDULER.md. No model weights, adapter or chunk/cache parameters change. This is saved-file functional/resource evidence only, with no ASR/WER/DER score or real-world quality claim. The existing application continues running, so component timing is not uncontended.

Inputs: fresh `d1-smoke-v3` directory, hard-linked (unmodified) original D1.gguf/source.wav/adapter, copied original `nemo-arm64` runtime with only libnemo_speech_asr.so replaced by the native scheduler build. Expected replacement SHA256 is `078fd4d0dfc1a0e2b1c6b2bb8b2d2a2a379a02056ff2093878f62f9dc328040b`. INPUTS_V3.json binds every regular library and the script, README and other inputs; ADMISSION_V3.json binds that manifest and the target boot ID. No original files are changed. Output names have V3 suffixes. Memory statistics are enabled to observe actual graph nodes and buffers. Core dumps are disabled. The 768 MiB RLIMIT_AS, CPUs 2/3, one native thread, 600-second wall limit and no-download policy remain; no per-job no-swap enforcement is claimed on this kernel.

Outputs: OWNER_V3.json, RESULT_V3.json, two probability arrays, launch/memory-statistics log. Require independent full-frame and repeat review, unchanged input hashes, exact process closure and service status. The build cannot qualify other graph sizes automatically. Retain failures and choose fresh names for subsequent attempts.

## PowerShell / Anaconda PowerShell

Transfer the new script/README/manifest/admission with the retained SSH key/host arguments in README.md. After a fresh resource/owner check:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-smoke-v3 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-smoke-v3/d1_smoke_v3.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the full remote command instead of single quotes. No Windows environment activation is necessary. All inference runs on the Pi. Keep results private and do not launch the script directly without the unit bounds and an unexpired admission.
