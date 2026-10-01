# Common live-profile runtime capsule V1

Purpose: prepare one pinned broker code capsule shared by the six microphone profiles (baseline, baseline-titanet, d1-delayed, d1-delayed-titanet, d1-anonymous and baseline-anonymous). It reuses the installed TitaNet/NeMo and ReDimNet controller implementations and separately pinned, read-only speaker galleries. It does not issue a device admission or deploy anything. Four saved-input Streaming/Chunk52 profiles remain separate integration work.

Inputs: the exact previously backed runtime capsule V2, production policy V3 source, profile V1 source, controller-profile V1 source, a fresh bounded HOST_SCOPE JSON and a new absent output directory directly under that scope directory. Original source hashes, 64 code members, 2MiB aggregate code and 128KiB per member are checked. The builder reads cumulative private scope usage before writes; primary capsule, packed backup and full independent expanded restore are all reserved.

Outputs: BUNDLE.json, REVIEW.json, REGISTERED_OWNER.json, BUNDLE_BACKUP.json, independent-restore/ and BACKUP.json. The backup receipt follows full member/hash/readback verification. A failure preserves its partial output; use a reviewed fresh derivative and new output path when a changed implementation is required. No old output is overwritten.

Prerequisite: back up these sources and README and independently restore them within the current host scope before execution. Use the repository's existing Python environment with psutil. CPU14 is set before project reads and the real host identity is registered before import. C:50GiB/G:75GiB free floors and the cumulative scope cap remain.

PowerShell (from the native report directory):
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$e='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\deployable-runtime-resume-v1'
& $py -B .\build_runtime_profile_capsule_v1.py --source-bundle "$e\runtime-capsule-v2\BUNDLE.json" --policy-source .\field_runtime_policy_v3.py --profiles-source .\field_runtime_profiles_v1.py --controller-source .\field_runtime_controller_profile_v1.py --scope "$e\HOST_SCOPE_V16.json" --output "$e\runtime-profile-capsule-v1"
```

CMD or Anaconda Prompt (use the same existing environment, from the native report directory):
```bat
set "PY=C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe"
set "E=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928\deployable-runtime-resume-v1"
"%PY%" -B build_runtime_profile_capsule_v1.py --source-bundle "%E%\runtime-capsule-v2\BUNDLE.json" --policy-source field_runtime_policy_v3.py --profiles-source field_runtime_profiles_v1.py --controller-source field_runtime_controller_profile_v1.py --scope "%E%\HOST_SCOPE_V16.json" --output "%E%\runtime-profile-capsule-v1"
```

The shown output is single-use and the scope expires; a later authorized run requires fresh bounded scope/output inputs, never reuse of a closed result. Import API: field_runtime_profile_capsule_v1.derive(bundle_bytes, policy_bytes, profiles_bytes, controller_bytes) returns the prepared packed bytes and an explicit review. This host preparation does not establish native model operation, actual galleries, recording, offline launch or acceptance. D0 model lifetime is certified only after independently verified exact child-process exit; D1 retains its actual EOF/closure checks.

