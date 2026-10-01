# Offline broker capsule adapter V2

Purpose: F04 prepares a production manual Delayed broker from the exact backed manual source bundle. It replaces the expired research policy check with the persistent runtime reservation, requires the live manager and shared CPU/task slice, and waits for the manager's actual durable STARTED before broker ACK. The source's obsolete absolute deadline becomes the exact current operation interval (maximum600 seconds); child300/270/30, audio120 seconds, RAM/disk/output/Stop guards remain. Explicit user Start is retained. Source authorization permits user-operated real-world recording, without automatic capture, playback or enrollment.

This is preparation, not a deployed launcher. The native initializer, persistent manager, installed profile binding and device qualification must complete before use. Only d1-delayed is integrated by this version. Contract support for other profile names does not implement those engines.

Inputs: original immutable manual BUNDLE.json (exact SHA is enforced); field_runtime_policy_v2.py and field_local_release_plan_v2.py (exact source SHA enforced). Outputs in a NEW private directory: early CPU14 REGISTERED_OWNER.json, prepared BUNDLE.json and REVIEW.json. Sources must be backed up and independently restored before running. The builder never contacts the Pi, issues a policy, refreshes old evidence or captures audio. Original64 outer/64 child members,2MiB code,128KiB individual member and1MiB packed-bundle caps remain.

PowerShell from this directory:
```powershell
& 'C:/Users/amiri/Documents/GitHub/just-peachy/.edge-speech-env/python.exe' -B ./build_field_runtime_capsule_v2.py --source-bundle 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/operator-manual-release-v1-preparation/manual-bundle-v1/BUNDLE.json' --policy-source ./field_runtime_policy_v2.py --plan-source ./field_local_release_plan_v2.py --output 'G:/Just_Peachy_N1/20260924_campaign/local/n5/research-extension-20260928/pi-native-20260928/deployable-runtime-resume-v1/runtime-capsule-v2'
```

CMD / Anaconda Prompt from this directory:
```bat
C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe -B build_field_runtime_capsule_v2.py --source-bundle G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\operator-manual-release-v1-preparation\manual-bundle-v1\BUNDLE.json --policy-source field_runtime_policy_v2.py --plan-source field_local_release_plan_v2.py --output G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\deployable-runtime-resume-v1\runtime-capsule-v2
```

API: field_runtime_capsule_v2.derive(bundle_bytes, policy_source_bytes, plan_source_bytes) returns packed bytes and a derivation review. It compiles changed sources but executes no native dependency graph. Original source function boundaries are checked before replacement; untouched source bytes remain exact. Failure consumes the output name. There is no direct Pi CLI.

Native integration must provide CONFIG.runtime with actual durable manager launch and reservation identities, exact manager service and shared slice, current settings SHA and independent baseline lifecycle observations. Reboot requires fresh operation boot bindings. The manager polls the broker's actual OWNER and ENVELOPE, verifies its systemd MainPID, then publishes STARTED. The gate independently binds that record before its existing once-only ACK. Full source/local-copy/PC-copy allocations remain independent; local verified backup is required before another recording. No source/process closure or actual device success is claimed by a built capsule.


V2 corrects a prepared-only startup ordering issue: the service is already active before the broker publishes OWNER. In that narrow interval, the current process identity must match the actual service MainPID and shared slice. It cannot authorize a different process. V1 remains immutable and was never run on the Pi.
