# Conditional XVF recovery V4

Purpose: one newly admitted conditional maintenance operation bound to the actual V115 stream-start AEC read failure and the V53 recovery/source-restoration precedent. This is not a periodic reset or a live-source qualification.

Inputs: a fresh 600-second PLAN with exact current boot/process identities, all code/config/tool/failure/precedent hashes, census and closure, original WINDOW_V5 hash, and a single-attempt RECOVERY_RESOURCE_POLICY_V1. The authorization is September 29 autonomous Pi maintenance. Owner receipts and all output directories must be new.

Outputs: immutable staging/host restore copies, command and actual systemd-property receipts, complete failed-or-successful closed-tree backup, exact process identities, and an independent review. The worker never opens capture or loads a model. A successful firmware readback does not restore unreadable old volatile state and does not prove audio operation.

## Limits and sequence
CPU14 host coordinator; Pi CPU2,3 shared200%, Tasks64, 768MiB AS, 1MiB stack, one thread, GPU off. Stage/read utilities CPU3/128MiB AS/1MiB stack with hard alarms; gate335s, worker300s/Stop10s. Initial RAM850MiB, sampled stop available192MiB/aggregateRSS640MiB, Pi free5GiB, host C50GiB/G75GiB. Entire admission600s and before 2026-10-01T17:42:44Z.

Reservation22MiB: target8MiB + host14MiB (complete8MiB target mirror, independent before/restore copies, metadata). Explicit measured policy changes only this attempt; WINDOW_V5 and retained usage remain unchanged. Source/code are backed up with independent restore copies before dispatch. Restore copies are verified bytes, not a device volatile-state rollback.

Current VERSION/build/AEC reads precede any mutation. Only an exact AEC255 Resource-could-not-respond failure permits one literal TEST_CORE_BURN 0 send. An uncertain/nonzero reply ends the attempt without retry. After2s, VERSION/build must match. If AEC is already readable, no maintenance command is sent. The fresh combined live source+D1/Stop/Save/Open test remains separate.

## PowerShell
```powershell
Set-Location 'G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928'
& 'C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe' -B .\xvf_recovery_dispatch_v4.py --plan 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\xvf-recovery-v4-preparation\PLAN_V1.json' --owner-receipt 'G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\xvf-recovery-v4-preparation\DISPATCH_OWNER_V1.json'
```

## CMD and Anaconda Prompt
Use the pinned existing Python environment; do not install or download packages.
```bat
cd /d "G:\Just_Peachy_N1\20260924_campaign\worktree\research\nvidia_nemo_comparison\20260924_campaign\n5\extension_20260928\pi_native_20260928"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B xvf_recovery_dispatch_v4.py --plan "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\xvf-recovery-v4-preparation\PLAN_V1.json" --owner-receipt "G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\xvf-recovery-v4-preparation\DISPATCH_OWNER_V1.json"
```

The dispatcher invokes review_xvf_recovery_v4.py automatically after natural gate closure. The reader preserves the complete closed tree before success assertions. If interrupted, do not rerun the closed root or command. Inspect exact owner identities and retained receipts, then create separately reviewed recovery work only where required. Internal --gate/--worker and stage helpers are not standalone operator entry points. No claims of power-loss, concurrent-writer, sustained-source, full-output-limit or physical-touch qualification.
