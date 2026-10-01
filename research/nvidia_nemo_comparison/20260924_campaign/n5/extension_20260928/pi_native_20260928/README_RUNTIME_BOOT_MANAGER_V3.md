# Runtime boot manager V3 and launch preparation

Purpose: F04/F18/F19 current-boot activation checks and F06/F07 deployable profile/shortcut inputs. Native manager3 is a derivative of manager2. It changes only bootstrap_manager and bundle_for_operation, adding current_activation. The complete old manager/broker/journal/copy behavior and original limits remain. Prepared sources are not an activated or qualified runtime.

The immutable ACTIVATION records the original controlled switch, including its two exact stopped baseline identities and config pins. At every new manager entry and before staging a recording, current_activation independently checks actual current boot/manager PID ticks, absence of both prior owners AND any newly launched original frontend, settings auto-start=false, current/live/install/display270 hashes, actual enabled270 display, CM5/aarch64/32GB device, capture closed, leases free, actual manager service and shared CPU2-3/200%/Tasks64 slice. Only then does it derive a current-boot CONFIG in memory. The original activation and earlier launch files are never rewritten. Actual early manager ownership still precedes project imports, and old incomplete/pending launch slots remain fenced. Actual offline/reboot/recovery qualification is still required.

prepare_runtime_launch_v1.py selects the exact backed common six-profile capsule and prior16-module manager. It checks unrelated manager definitions are AST-identical, inserts backed manager3, compiles all members, creates exact packed backup and complete independent expanded restore. It binds native gallery inventory into separate E0/ReDimNet and empty E1/TitaNet snapshot manifests. No enrollment/vector conversion. Existing Delayed GGUF/library paths stay as recorded in the actual common capsule. Four saved Streaming/Chunk52 profiles remain explicitly unavailable pending their integration.

Inputs: prior manager and common capsule BUNDLEs, source directory, actual installed backends.json catalogue, read-only native inspection4 directory, existing TitaNet manifest, fresh scope, absent output, proposed release ID and TitaNet version. Outputs are private manager bundle/backup/expanded restore, six profile descriptors, INSTALL_INPUTS.json and review. It references the already backed common capsule without copying it repeatedly. No policy is issued. The launcher preview intentionally uses a zero policy SHA and is NOT dispatchable.

API launch_assets(release_id, actual_policy_sha256, profiles, python_path) produces the final fixed systemd launcher, shared slice unit, profile desktop entries and idle default autostart entry. The shell accepts only exact listed profiles, uses the existing pinned native Python and sets offline/one-thread environment. All shortcuts run one fixed service and versioned manager; duplicate service ownership is rejected. The executable resides in the separately reserved profiles sibling, not an unallocated directory inside the strict journal root. Installing these files, binding the actual measured policy, GUI session environment, active-file backups/restore, normal baseline exit, activation and rollback remain installer responsibilities.

PowerShell, from this native source directory:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$b='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928'
$e="$b\deployable-runtime-resume-v1"
& $py -B .\prepare_runtime_launch_v1.py --manager-bundle "$e\profile-manager-capsule-v1\BUNDLE.json" --profile-bundle "$e\runtime-profile-capsule-v1\BUNDLE.json" --sources . --catalog "$b\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12\config\backends.json" --inspection "$e\install-inspection-v4" --titanet-manifest 'G:\Just_Peachy_N1\20260924_campaign\local\n2\titanet\export\titanet_manifest.json' --scope "$e\HOST_SCOPE_V30.json" --output "$e\boot-launch-inputs-v1" --release-id field-runtime-v1 --titanet-version 2
```
CMD and Anaconda Prompt:
```bat
set "B=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928"
set "E=%B%\deployable-runtime-resume-v1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B prepare_runtime_launch_v1.py --manager-bundle "%E%\profile-manager-capsule-v1\BUNDLE.json" --profile-bundle "%E%\runtime-profile-capsule-v1\BUNDLE.json" --sources . --catalog "%B%\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12\config\backends.json" --inspection "%E%\install-inspection-v4" --titanet-manifest "G:\Just_Peachy_N1\20260924_campaign\local\n2\titanet\export\titanet_manifest.json" --scope "%E%\HOST_SCOPE_V30.json" --output "%E%\boot-launch-inputs-v1" --release-id field-runtime-v1 --titanet-version 2
```
Sources require exact backup and independent restore before use. Native manager invocation is emitted by launch_assets after a real installation; never launch the preview or turn an old consumed root into a production release. TitaNet installation-v1 failed on initial RAM before target mkdir and remains preserved; use the eventual controlled baseline switch to obtain headroom before a fresh changed installation.

