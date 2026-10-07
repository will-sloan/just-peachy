# Current repair dispatcher memory allowance

Purpose: retain V2's complete owner/source/lease/disk/clock dispatcher and give
its native metadata utility a finite 256 MiB address-space allowance. Two actual
128 MiB failures were observed: Stage30-01 archive decompression and Saved42
launch importing libsqlite3, both before installation or model/capture launch.
Stage30-02 with 256 MiB passed at 111,820,800-byte peak RSS. Historical results
and raw failures remain unchanged; this is a fresh operator derivative.

Current initial available RAM must be at least 978 MiB, retaining extra headroom
for the admitted 128 MiB allowance increase. The later 850 MiB admission, CPU3,
1 MiB stack, file/disk floors, finite lifetime, strict SSH, all owner/capture/
lease checks, early CPU14 host registration and independent source backups are
unchanged. Result records actual native hard AS and peak RSS. Launched runtime
model/source/UI limits are separate and unchanged. No unlimited allocation or
unknown process identity is accepted.

Inputs: reviewed bounded action, fresh payload/label and actual current
baseline. Outputs: private action result, raw I/O, exact utility closure and
memory observation. Failed labels are preserved; use a fresh label/unit.

PowerShell (use fresh prepared paths and operation label):

```powershell
$d='G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928/live_runtime_20261003/core_repair_20261006'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B "$d/host_core_operations_v8.py" --label core-saved43-launch-01 --action 'FRESH_PREPARATION/ACTION.py' --payload 'FRESH_PREPARATION/PAYLOAD.json' --writes
```

Command Prompt/Anaconda Prompt: `powershell -NoProfile`, then the same block.
Replace both placeholders with absolute admitted files. Recording corpus quotas
are removed in the runtime; this finite utility envelope protects the 2 GiB OS
while performing maintenance. It is not a desktop launcher or accuracy test.
