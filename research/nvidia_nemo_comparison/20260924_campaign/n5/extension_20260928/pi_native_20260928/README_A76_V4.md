# A76 V4: preserve generic integer lane grouping

Purpose: isolate a concrete arithmetic difference found in the retained ggml source. Its generic `ggml_vdotq_s32` fallback sums byte pairs from the low and high halves into each integer lane; native `vdotq_s32` groups four consecutive bytes. The total integer sum agrees, but Q8 dot products scale and accumulate those lanes in floating point before reduction. Different grouping can therefore affect floating results. V8 disabled repacking and produced exactly the V7 probabilities, so repacking did not explain this case.

This candidate retains V3's A76/no-FP16/no-repack flags and changes the native helper to permute bytes in both vectors before `vdotq_s32`, matching the generic grouping. It preserves the original source in place, makes a fresh hard-linked ggml tree, replaces only the new header inode, and records before/after hashes. No quantization, model weights, cache parameters or numerical tolerance is changed. This is a hypothesis until the independent model checks pass.

Inputs: build_cpu_a76_v4.py, q8_lane_check_v1.cpp, this README, fresh BUILD_ADMISSION.json and retained scheduler-native-v1 source/base library/manifest. Stage: `~/JustPeachy/research/nemotron-20260928/cpu-a76-v4`. Outputs: source overlay, output library, owner/result, compiler logs and lane-check logs. The C++ diagnostic includes the actual patched helper and checks every lane against a scalar grouping calculation in 16 impulse and 10,000 deterministic signed random cases, including nonzero accumulators. It also verifies that the ordinary native instruction really differs. This tests software arithmetic, not speech quality. A successful build still requires V9 probability/state checks, then full-source/repeat and integration.

## PowerShell / Anaconda PowerShell

After exact prior owner closure and a fresh resource census, stage the inputs and a new hash-bound admission using the strict SSH/scp identity in README.md. Run one compiler at a time, CPUs2/3, hard768MiB virtual space, >=850MiB RAM available, >=5GiB disk, 64MiB build reservation, no GPU/download/capture:

```powershell
ssh.exe -i C:\Users\amiri\.ssh\just_peachy_cm5_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 peachyprototype@raspberrypi.local 'systemd-run --user --unit=jp-cpu-a76-build-v4 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p LimitCORE=0 -p Nice=10 taskset -c 2,3 python3 -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/cpu-a76-v4/build_cpu_a76_v4.py'
```

## CMD / Anaconda Prompt

Use the same command with double quotes around the remote command. No local activation or installation. Verify BUILD_RESULT.json, lane-check.log, candidate hash and exact closure before V9. A failed diagnostic/build remains preserved in this stage and requires a fresh derivative, not an edit/retry in place. Preserve the current app/global OS settings and original source.
