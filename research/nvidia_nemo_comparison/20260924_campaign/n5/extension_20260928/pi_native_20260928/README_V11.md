# Native D1 capacity2048 full-source/repeat conformance

Purpose: qualify only the scheduler metadata change from8192 to2048 for the existing D1 low_latency geometry. Preserve V10's lane-preserving CPU library and all generic reference probabilities, model, source, feature/cache/finish semantics and1e-5 threshold. The new capacity retains the95% graph guard. No ASR-model capacity qualification, new recipe, accuracy claim or complete app acceptance follows from this run.

Inputs: a fresh d1-scheduler-full-v11; verified V10 INPUTS and all its hard-linked assets, replacing only the scheduler-linked libnemo_speech_asr.so with scheduler-native-v2/output's separately hashed library, plus d1_smoke_v11.py and this README. Keep original files/inodes immutable. INPUTS_V11.json records every consumed path/hash; ADMISSION_V11.json binds it, actual boot, CPUs2/3,600seconds,hard768MiB address space,CPU200%,Tasks64,one native thread,>=850MiB available,>=5GiB disk and16MiB output reservation. Validate exact old owners/units before launch.

Outputs: OWNER_V11/RESULT_V11, first and resident-repeat arrays, setup/call elapsed/CPU/RTF/RSS/temperature and private memstats logs. Independently verify4470x8 finite probabilities, reference and repeat threshold, continuous frames, empty/reset/EOF/repeated-finish/post-finish behavior and exact closure. Current installed app remains active; timings are conditional diagnostics on saved audio, never new ASR/WER metrics or real-life validation. A native allocator abort is preserved, not relabelled as acceptance.

## PowerShell / Anaconda PowerShell

After the fresh target admission and inputs are staged:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-scheduler-v11 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-scheduler-full-v11/d1_smoke_v11.py'
```

## CMD / Anaconda Prompt / Linux

Use double quotes around the remote command in CMD/Anaconda Prompt. On Linux use systemd-run directly. No activation/install/download/capture/playback. Preserve old admissions/results. A passed D1 component allows only a fresh B01 memory/load/passage/drain retest; source frontend, UI/endurance and real-life speech qualification remain separate.
