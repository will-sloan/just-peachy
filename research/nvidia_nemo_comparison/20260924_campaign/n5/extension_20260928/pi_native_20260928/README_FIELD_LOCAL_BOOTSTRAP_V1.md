# Manager auxiliary bootstrap and protocol V1

Purpose: prepare the pinned, finite module graph and early native process registration needed to census and export one local manager tree. This is preparation, not a user launcher or native admission.

Inputs: immutable Python sources; exact SHA256 for every source; a fresh request with current boot/config/owner bindings. Native bootstrap input is one network-order 4-byte length plus JSON, at most262144 bytes, with exact keys request/modules/loader. The command binds SHA256 of the complete JSON. The loader is field_local_auxiliary_v1.py source and is covered by that digest. The entry is field_local_manager_export_v2.

Outputs: host check REGISTERED_OWNER/RESULT; native early_owner then exporter HELLO and census/export frames, all using network-order 4-byte sizes. Exporter V1 incorrectly used ASCII length/newline while the receiver expects binary framing; V2 changes only this serialization, struct import and README link. V1 stays immutable and native-unexecuted.

## Host checks (fresh private output only)

PowerShell:
```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B check_field_local_bootstrap_v1.py --output 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\operator-local-bootstrap-v1-preparation\bootstrap-check-v1'
```

CMD:
```bat
cd /d G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B check_field_local_bootstrap_v1.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\operator-local-bootstrap-v1-preparation\bootstrap-check-v1
```

Anaconda Prompt: run the same CMD commands with the existing absolute interpreter. No install or environment mutation. A consumed output is never overwritten or rerun.

## API and native execution contract

analyze(modules,pins,entry) statically checks all transitive imports, strict member/aggregate caps, full reachable graph and top-level import ordering. install performs exact source execution with in-memory origins and a per-module import allowlist. This is cooperative binding of reviewed code, not a security sandbox for hostile Python. Dynamic exec/eval/compile/__import__ in project module ASTs and unknown imports reject. The loader itself uses compile/exec to install verified sources.

Native bootstrap main runs only under a fresh host wrapper that has verified code backups, current native identities and resource admission. It sets CPU3,128MiB hard/soft AS,1MiB stack,FSIZE0,80s alarm; emits actual PID/start/boot before project source execution. It then reads the bounded digest-pinned payload and installs the fully verified graph before invoking exporter2.run. Exporter independently verifies actual shared service2CPU/200%/Tasks64/90sRuntime/10sStop, current boot/config/display270, RAM/disk/capture/leases and tree/owner bindings. Native bootstrap and whole exporter are unexecuted.

Host wrapper must persist early_owner BEFORE sending the payload, compare exporter HELLO to it, apply the original bounded input/output/watchdog/readers, independently close the exact native owner after natural SSH reap, and withhold BACKUP until closure and full host readback. No wrapper is provided by these modules. Native receiver/closure and joint issuer/dispatcher integration remain required. A request with a large inventory may exceed262144B: reject before dispatch; do not raise the ceiling.

The host check compiles the actual graph, loads only a small synthetic pure module pair, and executes only the actual extracted serialization helper against the existing receiver. It does not run the native bootstrap/exporter, Linux resource calls, Journal, source, model, GUI, capture or network. Preserve all old failed/pending roots and the independent155669036B manager mirror plus external broker backup; full617760944B joint proposal remains unadmitted.

