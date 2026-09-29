# D1 metadata8MiB full-source/repeat conformance

Purpose: repeat the original full44.6954375-second/repeat/reference/EOF protocol after the D1-only metadata arena repair. Inputs, outputs, gates and exclusions are those of README_V11.md, using fresh d1-metadata-full-v12, d1_smoke_v12.py, INPUTS_V12/ADMISSION_V12 and this README. Replace only libnemo_speech_asr.so with metadata-native-v1/output's hashed library. Retain the exact model, reference arrays, adapter, low_latency geometry and lane-preserving CPU kernel. Require the unchanged1e-5 reference/repeat tolerance, continuous4470x8 output, reset/empty/EOF/post-finish and closed owner/model. No ASR/WER scoring, new geometry, real-time or application qualification.

## PowerShell / Anaconda PowerShell

After fresh target identity/resource/input checks and admission:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-metadata-v12 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-metadata-full-v12/d1_smoke_v12.py'
```

## CMD / Anaconda Prompt / Linux

CMD/Anaconda Prompt use double quotes around the remote command; Linux uses systemd-run directly. No activation/download/install. Preserve CPUs2/3,totalCPU200%,Tasks64,600seconds,one native thread,hard768MiB virtual space,>=850MiB available and>=5GiB disk,16MiB output reservation. Original rc5 app stays active; recorded timing is conditional. Preserve earlier failed attempts and component passes; do not overwrite their code or admissions. Only independent conformance review permits a new integrated B01 memory/passage/drain test.
