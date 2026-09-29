# D1-only bounded native metadata arenas

B01 V5/V6/V7 aborted requesting64MiB before scheduler initialization, despite smaller Python stacks, scheduler2048 and finally one glibc arena. The native session constructs model/constant TensorContainers with64MiB temporary and buffer-type metadata arenas, and probes each new compute graph with the same large metadata reservations. These are address-space metadata reservations, not the actual model weights or tensor compute buffers. Current native logs report graph metadata far below8MiB for the retained D1 recipe.

`build_metadata_v1.py` reuses the verified original native source/object manifest and emits a separate session.cpp. It retains scheduler2048 and its95% guard. Only this translation unit's three default TensorContainer constructions and graph metadata probe use8MiB instead of64MiB. Actual buffer allocation, graph fit/headroom, ggml allocation assertions, model/weight precision, CPU kernels and computation remain unchanged. This is deliberately D1-only: no ASR or different geometry qualification is inferred. An8MiB arena exhaustion must fail and remain evidence, never silently expand or bypass the hard cap.

Inputs/outputs: same retained verified inputs as README_SCHEDULER_V2.md, fresh metadata-native-v1 directory, build script/README and BUILD_ADMISSION.json. Outputs include source/hash patch, runtime/static/native library, compiler/link logs and exact owner/result. No bound parent inode changes. A compiled library is not accepted until full-source/repeat/reference/EOF plus integrated load/drain checks pass. No new downloads, recording, playback, training or global OS change.

## PowerShell / Anaconda PowerShell

Stage the new files with strict SSH identity and a fresh target admission after all old owned units close. Then:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-metadata-v1 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/metadata-native-v1/build_metadata_v1.py'
```

## CMD / Anaconda Prompt / Linux

Use double quotes around the remote command in CMD/Anaconda Prompt. Linux runs systemd-run directly. Retain CPUs2/3,CPU200%,Tasks64,one compiler/model thread,hard768MiB address space,>=850MiB available,>=5GiB disk,16MiB output reservation within the combined allowance. No activation/install/download. Do not bind this library to an ASR model without its own tests or edit the original installed app. Follow README_V12.md for the required component conformance gate, then a fresh B01 admission.
