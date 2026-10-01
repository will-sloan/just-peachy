# Persistent offline runtime foundation

Purpose: F04/F05 separate an installed user release from historical research expiry. The policy retains Plan2's full independent source, Pi-local mirror and both PC-copy allocations, CPU/RAM/storage floors, 120-second audio maximum and 600-second active operation. Each idle manager launch has a finite24-hour ceiling and uses a preallocated launch slot. A policy never automatically replenishes recordings or credits failed/deleted slots. New installation and reprovision require fresh measured admission and verified backups.

Offline operation needs a verified independent Pi-local copy before the next recording. PC offload can wait for connectivity; its full independent reservation remains charged. This is an explicit production storage rule, not a change to any closed research policy or its historical copy requirements.

Inputs: exact immutable policy with full measured allocation, complete explicit profile availability/pins, distinct recording roots and current actual owner. Outputs: validated policy or a finite user-operation proposal. A pure proposal is not a resource admission or proof of native state. The native supervisor must bind current boot/resource/lease observations and durable records before launch. This initial source is not yet a deployable launcher.

Profiles cover baseline, live D1 Delayed, saved D1 Streaming, saved D1 Chunk52 and D1 anonymous. The policy cannot turn a saved profile into microphone mode or silently replace an unavailable profile. Actual profile manifests are required before availability is enabled. Sherpa ONNX remains ASR; no new model download or Nemotron ASR replacement is involved.

`field_runtime_policy_v1.py` is a library, not a Pi command. Import `validate`, `issue_operation`, `validate_operation` and `next_slot`. `issue_operation(..., now=aware_utc_datetime, owner=actual_pid_boot_start_ticks)` returns a proposal; `next_slot` consumes no storage and is paired with the native durable ledger in the next integration step. Old fixed-deadline dispatchers remain consumed and must not be invoked.

Changed-policy check (host only, no Pi connection): after source backup/readback, run `check_field_runtime_policy_v1.py` with a fresh private output directory. It sets CPU14 and records its actual identity before project imports.

PowerShell:
```powershell
cd 'G:/Just_Peachy_N1/20260924_campaign/worktree/research/nvidia_nemo_comparison/20260924_campaign/n5/extension_20260928/pi_native_20260928'
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./check_field_runtime_policy_v1.py --output 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/deployable-runtime-resume-v1/policy-check-v1'
```

CMD / Anaconda Prompt:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B check_field_runtime_policy_v1.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\deployable-runtime-resume-v1\policy-check-v1
```

Do not rerun a consumed output. The check uses synthetic policy counters/owner/profile hashes; it proves changed pure policy behavior, not current native identity, physical closure, available profiles, copying, persistence or a new resource allowance.
