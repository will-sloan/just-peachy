# Native D1 smoke V2: explicit address-space bound

Purpose: execute the same saved-audio native D1 component checks as V1 on the confirmed CM5. V1 failed before any model load because this kernel exposes `cpuset cpu io pids` but no memory controller. The systemd MemoryMax property alone did not enforce a limit. V1 code, input manifest, admission and failure are retained.

V2 replaces that unavailable mechanism with a hard Linux `RLIMIT_AS` of 768 MiB before importing NumPy or loading the model. This bounds the process's virtual address space, a stricter/different quantity than resident memory. There are no child processes. CPU affinity 2/3, cgroup CPU quota 200%, one native thread, 64 tasks, 600-second wall limit and ordinary-user execution remain. This kernel cannot enforce a per-job no-swap policy; V2 explicitly records that limitation. Global swap/boot settings are unchanged. Record swap counters around execution and do not accept a timing result as uncontended or swap-free without evidence. A MemoryError is a preserved failure, not permission to increase the limit automatically.

Inputs: the existing independently hashed stage assets (mixed-Q8 D1, generic native library, unchanged adapter and original saved WAV), fresh INPUTS_V2.json binding all retained V1 inputs plus V2 script and this README, and fresh ADMISSION_V2.json binding the inventory boot ID, manifest, limits and expiry. V2 reruns the original V1 asset hashes before inference. No model/package download or active-install change occurs. Saved audio is functional/resource evidence only, never a new ASR/WER or real-world accuracy claim.

Outputs: OWNER_V2.json (PID, start ticks, boot ID, admission hash), RESULT_V2.json, saved_prefix_v2.npy and resident_repeat_v2.npy. These remain private. The unchanged 12-second protocol checks contiguous 1,200 eight-speaker frames, finite probabilities, resident repeat, EOF and reset behavior. This does not qualify an integrated mode or the full-source protocol.

## PowerShell and Anaconda PowerShell

Use the same verified stage and SSH identity documented in README.md. Transfer only the new script, this README and the fresh two JSON files. The existing stage must already have STAGED.json and matching assets. Do not overwrite V1 files or rerun V1 staging.

```powershell
$jpKey='C:\Users\amiri\.ssh\just_peachy_cm5_ed25519'
$jpTarget='peachyprototype@raspberrypi.local'
# Replace LOCAL_FILE and TARGET_NAME with the explicit four-file list above.
scp.exe -i $jpKey -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 LOCAL_FILE "$($jpTarget):/home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-generic-v1/TARGET_NAME"
ssh.exe -i $jpKey -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlias=192.168.2.57 $jpTarget 'systemd-run --user --unit=jp-d1-generic-smoke-v2 --wait --pipe -p TasksMax=64 -p CPUQuota=200% -p RuntimeMaxSec=600 -p TimeoutStopSec=10 -p Nice=10 taskset -c 2,3 /home/peachyprototype/JustPeachy/install/runtimes/proto1-cm5-20260923-rc5/bin/python -B /home/peachyprototype/JustPeachy/research/nemotron-20260928/d1-generic-v1/d1_smoke_v2.py'
```

## CMD and Anaconda Prompt

Use the same `scp.exe` and `ssh.exe` commands with the key written as `"C:\Users\amiri\.ssh\just_peachy_cm5_ed25519"` and the full target instead of PowerShell variables. Surround the whole remote command with double quotes instead of single quotes. No local Python environment activation is required; execution uses the existing Pi runtime.

After execution, inspect the service's MainPID, Result, ExecMainStatus and InvocationID; independently verify output/input hashes, exact owner termination and unchanged active install. Do not dispatch a duplicate or reuse this run's names. Later tests require new scripts/admissions/output names where needed. Original README.md describes inventory, initial staging and subsequent ready-mode priorities; its V1 memory mechanism remains historical.
