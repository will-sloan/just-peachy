# Runtime manager assembly V1

Purpose: assemble one complete manager graph for the six prepared microphone profiles. Inputs are the immutable old manager capsule, new common profile capsule, backed manager2/journal3/backup2 sources and policy3, plus a current host scope. Outputs are BUNDLE.json, an exact packed backup, a complete independently expanded restore, REGISTERED_OWNER.json and REVIEW.json. The original 16-module, 2MiB aggregate and 128KiB/member limits remain.

The source ledger is copied from the common profile capsule. Its health consumer gains the same explicit D0 process-owned model accounting: actual route/load counts plus independently observed exact child death, without inventing D1 EOF evidence. Existing D1 checks and source/archive/lease/free-space checks remain. All transitive project imports are checked; only the separately pinned late broker gate is external.

Prerequisites: source backup and independent restore before execution, current <=600s host scope, C:50GiB/G:75GiB floors and complete cumulative capacity for primary/packed/expanded copies. Fresh output directory directly under the private scope directory. No native invocation, admission or model construction occurs.

PowerShell, from the native report directory:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$e='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\deployable-runtime-resume-v1'
& $py -B .\build_runtime_profile_manager_v1.py --manager-bundle "$e\manager-capsule-v1\BUNDLE.json" --profile-bundle "$e\runtime-profile-capsule-v1\BUNDLE.json" --sources . --scope "$e\HOST_SCOPE_V19.json" --output "$e\profile-manager-capsule-v1"
```
CMD or Anaconda Prompt:
```bat
set "E=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\deployable-runtime-resume-v1"
"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B build_runtime_profile_manager_v1.py --manager-bundle "%E%\manager-capsule-v1\BUNDLE.json" --profile-bundle "%E%\runtime-profile-capsule-v1\BUNDLE.json" --sources . --scope "%E%\HOST_SCOPE_V19.json" --output "%E%\profile-manager-capsule-v1"
```
The example scope expires and output is single-use. Preserve failures and use a new reviewed derivative/output if implementation changes are required. Scope/source binding failures must stop before dependent execution. This builder prepares code only; installer, runtime descriptors, actual native deployment, saved profiles and offline acceptance remain separate work.

