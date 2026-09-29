# V4: correct the native endpoint assertion

V3 completed native inference within the address-space cap but rejected its output with the new harness's incorrect 1,200-frame expectation. The pre-existing N2 protocol (`n2/diarization/run_native_panel.py:136`, `run_fixed_screen.py:344` and D1_HANDOFF.md) specifies `samples // 160 + 1` for nonempty native input: the centered-STFT endpoint gives 1,201 frames for exactly 12 seconds. V4 corrects this harness assertion and reports the 10 ms endpoint support overhang. It does not truncate probabilities, change model timing or loosen model correctness tolerances. Any waveform extraction must intersect actual source support. V3 failure and code remain intact.

Purpose, inputs, resource bounds and scope remain those of README_V3.md. Use the existing V3 runtime/model stage with a fresh d1_smoke_v4.py, this README, INPUTS_V4.json and ADMISSION_V4.json. Output names are OWNER_V4.json, RESULT_V4.json and two `_v4.npy` arrays; V3 files are untouched. No downloads or active-install changes. Saved audio remains functional/resource evidence only, never ASR/WER/DER or independent real-world accuracy evidence.

## PowerShell / Anaconda PowerShell

Copy the four new inputs to the existing `d1-smoke-v3` directory using the verified scp identity in README.md. Verify the new admission expiry and input hashes, then run:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-d1-smoke-v4 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-smoke-v3/d1_smoke_v4.py'
```

## CMD / Anaconda Prompt

Use the same ssh/scp arguments; use double quotes around the remote command. No Windows Python activation is required. Independently inspect the collected result/arrays and exact process closure. Do not infer integrated mode readiness, sustained memory or real-time capacity from the short component smoke.
