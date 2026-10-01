# Changed profile dispatch check V1

Purpose: exercise the actual manager2 descriptor/operation functions with the actual prepared common capsule and all six microphone profile definitions. This is one changed integration check, not neural inference or a test sweep. It uses explicitly synthetic policy/process/activation/gallery facts and an in-memory read adapter; it does not stage files on Linux.

Inputs: common BUNDLE.json, backed manager2 source, installed config/backends.json, original TitaNet manifest, fresh bounded host scope, absent output directory. Outputs: real CPU14 REGISTERED_OWNER.json and RESULT.json with exact observed profiles/rejections. Three rejects cover descriptor drift, common code drift and an E0 profile acquiring an E1 dependency. Original policy/member/code-count guards execute.

Back up and independently restore these sources before use. No Pi contact or native/model constructor occurs. Example paths below are single-use; a closed passing check must not be rerun merely for a version change.

PowerShell from the report directory:
```powershell
$py='C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe'
$e='G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928'
& $py -B .\check_runtime_profile_dispatch_v1.py --bundle "$e\deployable-runtime-resume-v1\runtime-profile-capsule-v1\BUNDLE.json" --manager .\field_runtime_manager_v2.py --catalog "$e\field-artifact-install-v2-evidence\target\deployment\releases\b01-offline-20260930-v12\config\backends.json" --titanet-manifest "G:\Just_Peachy_N1\20260924_campaign\local\n2\titanet\export\titanet_manifest.json" --scope "$e\deployable-runtime-resume-v1\HOST_SCOPE_V21.json" --output "$e\deployable-runtime-resume-v1\profile-dispatch-check-v1"
```
CMD/Anaconda Prompt: use the same arguments with the full Python executable in double quotes; replace PowerShell $e with a variable declared using `set "E=G:\Just_Peachy_N1\20260924_campaign\local\n5\research-extension-20260928\pi-native-20260928"` and use `%E%` in each path. Explicit executable: `"C:\Users\amiri\Documents\GitHub\just-peachy\.edge-speech-env\python.exe" -B check_runtime_profile_dispatch_v1.py` followed by the arguments above with those substitutions.

